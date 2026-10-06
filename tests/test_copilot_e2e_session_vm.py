#!/usr/bin/env python3

"""Tests for the wrapper's per-session VM snapshot helper."""

import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace
from unittest.mock import patch

from scripts.e2e.copilot_e2e_session_vm import (
    copy_shared_source_markers,
    create_overlay,
    parse_args,
    snapshot_disk_path,
    virsh_proxy,
)


class SessionVMDiskTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("qemu-img") or not shutil.which("qemu-io"):
            self.skipTest("qemu-img and qemu-io are required")
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.shared_directory = self.root / "shared"
        self.shared_directory.mkdir()
        self.snapshot_disk = self.shared_directory / "common.qcow2"
        subprocess.run(
            ["qemu-img", "create", "-f", "qcow2", str(self.snapshot_disk), "16M"],
            check=True,
            stdout=subprocess.DEVNULL,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_session_overlays_have_private_writes(self):
        session_a = self.root / "session-a" / "vm.qcow2"
        session_b = self.root / "session-b" / "vm.qcow2"
        create_overlay(self.snapshot_disk, "qcow2", session_a)
        create_overlay(self.snapshot_disk, "qcow2", session_b)

        subprocess.run(
            ["qemu-io", "-c", "write -P 0xa5 1M 512", str(session_a)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            ["qemu-io", "-c", "read -P 0x00 1M 512", str(session_b)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            ["qemu-io", "-c", "read -P 0x00 1M 512", str(self.snapshot_disk)],
            check=True,
            stdout=subprocess.DEVNULL,
        )

        info = json.loads(
            subprocess.run(
                ["qemu-img", "info", "--output=json", str(session_a)],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )
        self.assertEqual(info["backing-filename"], str(self.snapshot_disk))

    def test_snapshot_disk_must_stay_inside_shared_storage(self):
        external_disk = self.root / "external.qcow2"
        subprocess.run(
            ["qemu-img", "create", "-f", "qcow2", str(external_disk), "16M"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        snapshot = ET.fromstring(
            "<domainsnapshot><disks><disk name='vda' snapshot='external' type='file'>"
            f"<source file='{external_disk}'/></disk></disks></domainsnapshot>"
        )

        with self.assertRaisesRegex(RuntimeError, "outside shared E2E storage"):
            snapshot_disk_path(snapshot, self.shared_directory)


class SessionVMConfigurationTests(unittest.TestCase):
    def test_session_configuration_comes_from_wrapper_environment(self):
        environment = {
            "VM_NAME": "e2e-runner-noble",
            "RELEASE": "noble",
            "AUTHD_E2E_SESSION_ID": "1234abcd",
            "AUTHD_E2E_SHARED_DATA_DIR": "/tmp/e2e/shared",
            "AUTHD_E2E_SESSION_DATA_DIR": "/tmp/e2e/shared/sessions/1234abcd",
            "AUTHD_E2E_LIBVIRT_SOCKET_DIR": "/run/user/1000/copilot-e2e/libvirt",
        }
        with patch.dict(os.environ, environment, clear=True), patch(
            "sys.argv",
            [
                "copilot_e2e_session_vm.py",
                "restore",
                "--snapshot",
                "authd-installed",
            ],
        ):
            args = parse_args()

        self.assertEqual(args.base_vm_name, "e2e-runner-noble")
        self.assertEqual(args.vm_name, "e2e-runner-noble-copilot-1234abcd")
        self.assertEqual(args.vm_alias, "e2e-runner-noble")
        self.assertEqual(args.session_id, "1234abcd")
        self.assertEqual(args.snapshot, "authd-installed")


class SessionVMMarkerTests(unittest.TestCase):
    def test_copy_shared_marker_without_overwriting_session_marker(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            shared_directory = root / "shared"
            session_directory = shared_directory / "sessions" / "1234abcd"
            shared_artifacts = shared_directory / "noble"
            session_artifacts = session_directory / "noble"
            shared_artifacts.mkdir(parents=True)
            session_artifacts.mkdir(parents=True)
            marker_name = "e2e-runner-noble.authd-google.stable-snapshot-source"
            source = shared_artifacts / marker_name
            target = session_artifacts / marker_name
            source.write_text("stable-key\n")
            args = SimpleNamespace(
                base_vm_name="e2e-runner-noble",
                shared_data_dir=str(shared_directory),
                session_data_dir=str(session_directory),
                release="noble",
            )

            with patch(
                "scripts.e2e.copilot_e2e_session_vm.shared_artifacts_dir",
                return_value=shared_artifacts,
            ):
                copy_shared_source_markers(args)
                self.assertEqual(target.read_text(), "stable-key\n")
                target.write_text("session-key\n")
                copy_shared_source_markers(args)

            self.assertEqual(target.read_text(), "session-key\n")


class SessionVMVirshHookTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "VM_NAME": "e2e-runner-noble",
                "RELEASE": "noble",
                "AUTHD_E2E_SESSION_ID": "1234abcd",
                "AUTHD_E2E_SHARED_DATA_DIR": "/tmp/e2e/shared",
                "AUTHD_E2E_SESSION_DATA_DIR": "/tmp/e2e/shared/sessions/1234abcd",
                "AUTHD_E2E_LIBVIRT_SOCKET_DIR": "/run/user/1000/copilot-e2e/libvirt",
            },
            clear=True,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_snapshot_list_includes_shared_baselines(self):
        outputs = iter(
            (
                CompletedProcess([], 0, "authd-installed\n", ""),
                CompletedProcess([], 0, "initial-setup\nauthd-installed\n", ""),
            )
        )
        with patch(
            "scripts.e2e.copilot_e2e_session_vm.virsh",
            side_effect=lambda *args, **kwargs: next(outputs),
        ), patch("sys.stdout", new_callable=io.StringIO) as stdout:
            status = virsh_proxy(["snapshot-list", "e2e-runner-noble", "--name"])

        self.assertEqual(status, 0)
        self.assertEqual(stdout.getvalue(), "authd-installed\ninitial-setup\n")

    def test_shared_snapshot_revert_uses_private_overlay(self):
        outputs = iter(
            (
                CompletedProcess([], 0, "", ""),
                CompletedProcess([], 0, "initial-setup\n", ""),
            )
        )
        with patch(
            "scripts.e2e.copilot_e2e_session_vm.virsh",
            side_effect=lambda *args, **kwargs: next(outputs),
        ), patch("scripts.e2e.copilot_e2e_session_vm.restore") as restore:
            status = virsh_proxy(
                ["snapshot-revert", "e2e-runner-noble", "initial-setup"]
            )

        self.assertEqual(status, 0)
        args = restore.call_args.args[0]
        self.assertEqual(args.base_vm_name, "e2e-runner-noble")
        self.assertEqual(args.vm_name, "e2e-runner-noble-copilot-1234abcd")
        self.assertEqual(args.snapshot, "initial-setup")

    def test_shared_snapshot_delete_keeps_baseline_immutable(self):
        outputs = iter(
            (
                CompletedProcess([], 0, "", ""),
                CompletedProcess([], 0, "authd-installed\n", ""),
            )
        )
        with patch(
            "scripts.e2e.copilot_e2e_session_vm.virsh",
            side_effect=lambda *args, **kwargs: next(outputs),
        ), patch("sys.stderr", new_callable=io.StringIO) as stderr:
            status = virsh_proxy(
                [
                    "snapshot-delete",
                    "--domain",
                    "e2e-runner-noble",
                    "--snapshotname",
                    "authd-installed",
                ]
            )

        self.assertEqual(status, 0)
        self.assertIn("leaving shared baseline snapshot", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
