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
    ensure_initial_baseline,
    isolate_domain,
    parse_args,
    provision_initial_baseline,
    snapshot_disk_path,
    validate_paths,
    virsh_proxy,
)


class InitialBaselineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.args = SimpleNamespace(
            base_vm_name="e2e-runner-resolute",
            vm_name="e2e-runner-resolute-copilot-1234abcd",
            vm_alias="e2e-runner-resolute",
            shared_data_dir=str(self.root),
            session_data_dir=str(self.root),
            release="resolute",
        )
        self.prefix = "scripts.e2e.copilot_e2e_session_vm."
        self.ensure = patch(self.prefix + "ensure_base_domain").start()
        self.exists = patch(self.prefix + "virsh_domain_exists", return_value=False).start()
        self.snapshots = patch(self.prefix + "session_snapshot_names_or_error", return_value=set()).start()
        self.disk = patch(self.prefix + "session_vda_path", return_value=str(self.root / "missing.qcow2")).start()
        self.state = patch(self.prefix + "domain_state", return_value="shut off").start()
        self.provision = patch(self.prefix + "provision_initial_baseline").start()
        self.addCleanup(patch.stopall)

    def test_existing_shared_baseline_is_reused(self):
        self.snapshots.side_effect = [set(), {"initial-setup", "authd-installed"}]
        ensure_initial_baseline(self.args)
        self.provision.assert_not_called()

    def test_existing_private_baseline_is_reused(self):
        self.snapshots.return_value = {"initial-setup"}
        ensure_initial_baseline(self.args)
        self.ensure.assert_not_called()
        self.provision.assert_not_called()

    def test_missing_domain_is_provisioned_automatically(self):
        self.exists.return_value = False
        ensure_initial_baseline(self.args)
        self.provision.assert_called_once_with(self.args)

    def test_stale_definition_with_missing_disk_is_rebuilt(self):
        ensure_initial_baseline(self.args)
        self.provision.assert_called_once_with(self.args)

    def test_existing_unmarked_disk_is_not_replaced(self):
        self.exists.return_value = True
        image = self.root / "existing.qcow2"
        image.touch()
        self.disk.return_value = str(image)
        with self.assertRaisesRegex(RuntimeError, "refusing to replace"):
            ensure_initial_baseline(self.args)
        self.provision.assert_not_called()

    def test_active_baseline_is_not_replaced(self):
        self.exists.return_value = True
        self.state.return_value = "running"
        with self.assertRaisesRegex(RuntimeError, "still running"):
            ensure_initial_baseline(self.args)
        self.provision.assert_not_called()

    def test_shared_vm_with_other_snapshots_is_left_unchanged(self):
        self.snapshots.side_effect = [set(), {"authd-installed"}]
        ensure_initial_baseline(self.args)
        self.provision.assert_called_once_with(self.args)

    def test_provisioning_failure_is_reported(self):
        self.provision.side_effect = RuntimeError("cloud-init failed")
        with self.assertRaisesRegex(RuntimeError, "cloud-init failed"):
            ensure_initial_baseline(self.args)

    def test_completed_cloud_init_is_required_before_creating_snapshot(self):
        vm_dir = self.root / "e2e-tests" / "vm"
        vm_dir.mkdir(parents=True)
        (vm_dir / "cloud-init-scripts").mkdir()
        (vm_dir / "cloud-init-template-resolute.yaml").write_text(
            "#cloud-config\nkey: ${SSH_PUBLIC_KEY}\njournal: ${SOCAT_ADDRESS}\n"
        )
        xml = (
            "<domain><name>base</name><devices>"
            "<disk><source file='${IMAGE_FILE}'/><target dev='vda'/></disk>"
            "</devices></domain>"
        )
        (vm_dir / "e2e-runner-template.xml").write_text(xml)
        key = self.root / "test.pub"
        key.write_text("ssh-ed25519 test\n")
        cache = self.root / "cache" / "authd-e2e-tests"
        cache.mkdir(parents=True)
        (cache / "resolute-server-cloudimg-amd64.img").touch()
        self.args.session_id = "1234abcd"
        self.args.socket_dir = "/tmp/e2e/libvirt"
        commands = []

        def run_command(command, **kwargs):
            commands.append(command)
            output = ""
            if command[:2] == ["git", "rev-parse"]:
                output = str(self.root)
            elif command[:2] == ["systemctl", "--version"]:
                output = "systemd 258\n"
            elif command[0] == "/usr/bin/env":
                output = json.dumps({"v1": {"errors": ["package install failed"]}})
            return CompletedProcess(command, 0, output, "")

        with patch.dict(os.environ, {
            "SSH_PUBLIC_KEY_FILE": str(key), "XDG_CACHE_HOME": str(self.root / "cache"),
        }), patch(
            self.prefix + "run", side_effect=run_command,
        ), patch(self.prefix + "virsh"), patch(
            self.prefix + "domain_state", return_value="shut off",
        ), self.assertRaisesRegex(RuntimeError, "package install failed"):
            provision_initial_baseline(self.args)
        self.assertFalse(any("force_create_snapshot" in argument for command in commands for argument in command))
        self.assertTrue((self.root / "resolute" / "e2e-runner-resolute.bootstrap").exists())


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
            f"<source file='{external_disk}'/></disk></disks>"
            f"<domain><devices><disk><source file='{external_disk}'/>"
            "<target dev='vda'/></disk></devices></domain></domainsnapshot>"
        )

        with self.assertRaisesRegex(RuntimeError, "outside shared E2E storage"):
            snapshot_disk_path(snapshot, self.shared_directory)

    def test_snapshot_uses_frozen_disk_not_new_writable_overlay(self):
        active_disk = self.shared_directory / "active.qcow2"
        create_overlay(self.snapshot_disk, "qcow2", active_disk)
        subprocess.run(
            ["qemu-io", "-c", "write -P 0xa5 1M 512", str(active_disk)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        snapshot = ET.fromstring(
            "<domainsnapshot><disks><disk name='vda' snapshot='external'>"
            f"<source file='{active_disk}'/></disk></disks>"
            f"<domain><devices><disk><source file='{self.snapshot_disk}'/>"
            "<target dev='vda'/></disk></devices></domain></domainsnapshot>"
        )
        frozen_disk, disk_format = snapshot_disk_path(snapshot, self.shared_directory)
        self.assertEqual(frozen_disk, str(self.snapshot_disk))
        overlay = self.root / "restored.qcow2"
        create_overlay(frozen_disk, disk_format, overlay)
        subprocess.run(
            ["qemu-io", "-c", "read -P 0x00 1M 512", str(overlay)],
            check=True,
            stdout=subprocess.DEVNULL,
        )

    def test_snapshot_without_saved_domain_is_rejected(self):
        snapshot = ET.fromstring(
            "<domainsnapshot><disks><disk name='vda' snapshot='external'>"
            f"<source file='{self.snapshot_disk}'/></disk></disks></domainsnapshot>"
        )
        with self.assertRaisesRegex(RuntimeError, "frozen disk image"):
            snapshot_disk_path(snapshot, self.shared_directory)


class SessionVMConfigurationTests(unittest.TestCase):
    def test_selected_data_directory_must_match_assigned_session(self):
        args = SimpleNamespace(
            shared_data_dir="/tmp/shared",
            session_data_dir="/tmp/shared/sessions/1234abcd",
            session_id="1234abcd",
        )
        with patch.dict(os.environ, {"AUTHD_E2E_DATA_DIR": "/tmp/elsewhere"}):
            with self.assertRaisesRegex(RuntimeError, "assigned session storage"):
                validate_paths(args)

    def test_session_domain_uses_rootless_network_and_external_confinement(self):
        domain = ET.fromstring(
            "<domain><name>e2e-runner-noble</name><devices>"
            "<disk><source file='/shared/base'/><target dev='vda'/></disk>"
            "<interface type='network'><source network='default'/>"
            "<model type='virtio'/></interface>"
            "<vsock><cid auto='yes' address='5'/></vsock>"
            "</devices><seclabel type='none' model='apparmor'/></domain>"
        )
        args = SimpleNamespace(
            vm_name="e2e-runner-noble-copilot-1234abcd",
            session_id="1234abcd",
            socket_dir="/run/user/1000/copilot-e2e/libvirt",
        )
        isolate_domain(domain, args, "/session/private.qcow2")
        self.assertEqual(domain.findtext("name"), args.vm_name)
        interface = domain.find("./devices/interface")
        self.assertEqual(interface.get("type"), "user")
        self.assertIsNone(interface.find("source"))
        self.assertEqual(interface.find("model").get("type"), "virtio")
        self.assertIsNone(domain.find("seclabel"))
        self.assertEqual(
            domain.find("./devices/disk/source").get("file"), "/session/private.qcow2"
        )
        self.assertIsNone(domain.find("./devices/vsock/cid").get("address"))

    def test_session_domain_rejects_unknown_managed_network(self):
        domain = ET.fromstring(
            "<domain><name>base</name><devices>"
            "<disk><source file='/shared/base'/><target dev='vda'/></disk>"
            "<interface type='network'><source network='special'/></interface>"
            "</devices></domain>"
        )
        args = SimpleNamespace(
            vm_name="base-copilot-1234abcd",
            session_id="1234abcd",
            socket_dir="/run/user/1000/copilot-e2e/libvirt",
        )
        with self.assertRaisesRegex(RuntimeError, "only the default managed network"):
            isolate_domain(domain, args, "/session/private.qcow2")

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
        ), patch(
            "scripts.e2e.copilot_e2e_session_vm.virsh_domain_exists", return_value=True,
        ), patch("sys.stdout", new_callable=io.StringIO) as stdout:
            status = virsh_proxy(["snapshot-list", "e2e-runner-noble", "--name"])

        self.assertEqual(status, 0)
        self.assertEqual(stdout.getvalue(), "authd-installed\ninitial-setup\n")

    def test_snapshot_list_works_without_a_shared_domain(self):
        with patch(
            "scripts.e2e.copilot_e2e_session_vm.session_snapshot_names_or_error",
            return_value={"initial-setup"},
        ), patch(
            "scripts.e2e.copilot_e2e_session_vm.virsh_domain_exists", return_value=False,
        ), patch("sys.stdout", new_callable=io.StringIO) as stdout:
            status = virsh_proxy(["snapshot-list", "e2e-runner-noble", "--name"])
        self.assertEqual(status, 0)
        self.assertEqual(stdout.getvalue(), "initial-setup\n")

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
