"""Opt-in integration checks for a running private Copilot LXD service."""

import json
import os
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path


@unittest.skipUnless(
    os.environ.get("COPILOT_TEST_PRIVATE_LXD") == "1",
    "set COPILOT_TEST_PRIVATE_LXD=1 while the private service is running",
)
class PrivateLXDTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        expected = Path.home() / ".local/share/copilot-lxd"
        if Path(os.environ.get("LXD_DIR", "")) != expected:
            raise RuntimeError("These tests must not connect to the host LXD service")
        cls.name = f"copilot-isolation-{uuid.uuid4().hex[:12]}"
        cls.lxc("init", "ubuntu:24.04", cls.name)
        cls.addClassCleanup(cls.lxc, "delete", "--force", cls.name)
        try:
            cls.lxc("start", cls.name)
        except RuntimeError as error:
            log = cls.lxc("info", "--show-log", cls.name).stdout
            raise RuntimeError(f"{error}\n{log}") from error

    @staticmethod
    def lxc(*args, check=True, input=None):
        result = subprocess.run(
            ["/snap/lxd/current/bin/lxc", *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=90,
            input=input,
        )
        if check and result.returncode:
            raise RuntimeError(f"lxc {args!r}: {result.stderr}")
        return result

    def test_root_and_apparmor_stay_confined(self):
        mapping = self.lxc(
            "exec", self.name, "--", "cat", "/proc/self/uid_map"
        ).stdout.splitlines()
        self.assertEqual(mapping[0].split(), ["0", str(os.getuid()), "1"])
        state = json.loads(
            self.lxc("query", f"/1.0/instances/{self.name}/state").stdout
        )
        namespace_pid = (
            Path(os.environ["XDG_RUNTIME_DIR"]) / "copilot-lxd/namespace.pid"
        ).read_text()
        profile = (
            Path(f"/proc/{namespace_pid}/root/proc/{state['pid']}/attr/current")
            .read_text()
            .strip()
        )
        self.assertEqual(
            profile,
            "debian-user-config-copilot-lxd//&:copilot-lxd:unconfined (enforce)",
        )

    def test_child_policy_cannot_replace_outer_profile(self):
        name = self.lxc(
            "exec", self.name, "--", "cat", "/sys/kernel/security/apparmor/.ns_name"
        ).stdout.strip()
        self.assertEqual(name, "copilot-lxd")
        policy = "profile debian-user-config-copilot-lxd { }\n"
        self.lxc(
            "exec",
            self.name,
            "--",
            "apparmor_parser",
            "-r",
            "-K",
            input=policy,
        )
        try:
            profile = subprocess.run(
                [
                    "aa-exec",
                    "-p",
                    "debian-user-config-copilot-lxd",
                    "--",
                    "cat",
                    "/proc/self/attr/current",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            ).stdout.strip()
            self.assertEqual(profile, "debian-user-config-copilot-lxd (enforce)")
        finally:
            self.lxc(
                "exec",
                self.name,
                "--",
                "apparmor_parser",
                "-R",
                "-K",
                input=policy,
            )

    def test_project_mount_is_writable_without_host_root(self):
        with tempfile.TemporaryDirectory(dir=Path.home() / "projects") as directory:
            self.lxc(
                "config",
                "device",
                "add",
                self.name,
                "project",
                "disk",
                f"source={directory}",
                "path=/mnt/project",
            )
            try:
                self.lxc("exec", self.name, "--", "touch", "/mnt/project/created")
                self.assertEqual(
                    (Path(directory) / "created").stat().st_uid, os.getuid()
                )
            finally:
                self.lxc("config", "device", "remove", self.name, "project")

    def test_private_home_and_host_socket_are_not_mountable(self):
        for source in (
            str(Path.home() / ".copilot"),
            "/var/snap/lxd/common/lxd/unix.socket",
        ):
            with self.subTest(source=source):
                result = self.lxc(
                    "config",
                    "device",
                    "add",
                    self.name,
                    "forbidden",
                    "disk",
                    f"source={source}",
                    "path=/mnt/forbidden",
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertRegex(result.stderr, "Missing source path|does not exist")


if __name__ == "__main__":
    unittest.main()
