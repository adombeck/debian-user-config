#!/usr/bin/env python3

"""Per-session VM snapshots for the shared Copilot E2E libvirt service."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path


VIRSH_BIN = "/usr/bin/virsh"


def fail(message):
    print(f"error: {message}", file=sys.stderr)
    return 1


def run(command, *, check=True):
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as error:
        raise RuntimeError(f"could not run {command[0]}: {error}") from error

    if check and result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        if output:
            raise RuntimeError(f"{' '.join(command)} failed: {output}")
        raise RuntimeError(f"{' '.join(command)} failed with status {result.returncode}")
    return result


def virsh(*arguments, check=True):
    return run([VIRSH_BIN, *arguments], check=check)


def inside(path, root):
    try:
        return os.path.commonpath((os.path.realpath(path), os.path.realpath(root))) == os.path.realpath(root)
    except ValueError:
        return False


def validate_paths(args):
    shared_dir = Path(args.shared_data_dir)
    session_dir = Path(args.session_data_dir)
    expected_session_dir = shared_dir / "sessions" / args.session_id

    if not shared_dir.is_dir() or shared_dir.is_symlink():
        raise RuntimeError(f"shared E2E data directory is invalid: {shared_dir}")
    if session_dir.is_symlink() or not session_dir.is_dir():
        raise RuntimeError(f"session E2E data directory is invalid: {session_dir}")
    if os.path.realpath(session_dir) != os.path.realpath(expected_session_dir):
        raise RuntimeError("session E2E data directory is outside its assigned session path")
    if not inside(session_dir, shared_dir):
        raise RuntimeError("session E2E data directory is outside shared E2E storage")
    if not os.path.isabs(args.socket_dir) or ".." in Path(args.socket_dir).parts:
        raise RuntimeError("libvirt socket directory must be an absolute host path")
    if not re.fullmatch(r"[A-Za-z0-9]+", args.session_id):
        raise RuntimeError("invalid E2E session identifier")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.vm_alias):
        raise RuntimeError("invalid E2E VM alias")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.vm_name):
        raise RuntimeError("invalid E2E session VM name")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.release):
        raise RuntimeError("invalid E2E VM release")
    if args.vm_alias != args.base_vm_name:
        raise RuntimeError("E2E VM alias must match the shared base VM name")
    if args.vm_name != f"{args.vm_alias}-copilot-{args.session_id}":
        raise RuntimeError("session VM name is not scoped to its Copilot session")

    artifacts_dir = session_dir / args.release
    if artifacts_dir.is_symlink():
        raise RuntimeError(f"refusing to use symlinked session artifacts: {artifacts_dir}")
    if artifacts_dir.exists() and not artifacts_dir.is_dir():
        raise RuntimeError(f"session artifacts path is not a directory: {artifacts_dir}")
    artifacts_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not inside(artifacts_dir, session_dir):
        raise RuntimeError("session artifacts directory is outside session E2E storage")


def virsh_domain_exists(vm_name):
    return virsh("dominfo", vm_name, check=False).returncode == 0


def ensure_base_domain(base_vm_name, shared_data_dir, release):
    if virsh_domain_exists(base_vm_name):
        return

    base_name = base_vm_name.removesuffix(f"-{release}")
    candidates = (
        Path(shared_data_dir) / "current" / release / f"{base_name}.xml",
        Path(shared_data_dir) / release / f"{base_name}.xml",
        Path(shared_data_dir) / "current" / release / f"{base_vm_name}.xml",
        Path(shared_data_dir) / release / f"{base_vm_name}.xml",
    )
    for candidate in candidates:
        if candidate.is_symlink() or not candidate.is_file() or not inside(candidate, shared_data_dir):
            continue
        try:
            domain = ET.parse(candidate).getroot()
        except ET.ParseError:
            continue
        if domain.findtext("name") != base_vm_name:
            continue
        virsh("define", str(candidate))
        return

    raise RuntimeError(
        f"shared E2E base VM {base_vm_name} is not defined and its domain XML was not found"
    )


def shared_snapshot_xml(base_vm_name, snapshot_name):
    output = virsh("snapshot-dumpxml", base_vm_name, snapshot_name).stdout
    try:
        return ET.fromstring(output)
    except ET.ParseError as error:
        raise RuntimeError(
            f"could not parse shared snapshot metadata for {base_vm_name}/{snapshot_name}: {error}"
        ) from error


def snapshot_disk_path(snapshot, shared_dir):
    disks = snapshot.findall("./disks/disk")
    disk = next((item for item in disks if item.get("name") == "vda"), None)
    if disk is None:
        raise RuntimeError("shared snapshot has no vda disk")
    if disk.get("snapshot") != "external":
        raise RuntimeError(
            "shared E2E snapshots must use external vda disks to support isolated VM overlays"
        )

    source = disk.find("source")
    path = source.get("file") if source is not None else None
    if not path:
        raise RuntimeError("shared snapshot vda does not reference a disk image")
    if not inside(path, shared_dir):
        raise RuntimeError(f"shared snapshot disk is outside shared E2E storage: {path}")
    if os.path.islink(path) or not os.path.isfile(path):
        raise RuntimeError(f"shared snapshot disk is missing or unsafe: {path}")
    try:
        image_info = json.loads(run(["qemu-img", "info", "--output=json", path]).stdout)
    except (json.JSONDecodeError, RuntimeError) as error:
        raise RuntimeError(f"could not inspect shared snapshot disk {path}: {error}") from error
    image_format = image_info.get("format")
    if image_format != "qcow2":
        raise RuntimeError(
            f"shared snapshot disk must be qcow2, got {image_format or 'unknown'}: {path}"
        )
    return os.path.realpath(path), image_format


def base_active_disk_path(base_vm_name):
    output = virsh("domblklist", base_vm_name, "--details").stdout
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 4 and fields[2] == "vda":
            return os.path.realpath(fields[3])
    raise RuntimeError(f"shared base VM has no vda disk: {base_vm_name}")


def shared_artifacts_dir(base_vm_name, shared_data_dir):
    path = base_active_disk_path(base_vm_name)
    if not inside(path, shared_data_dir):
        raise RuntimeError(f"shared base VM disk is outside shared E2E storage: {path}")
    return Path(path).parent


def copy_shared_source_markers(args):
    source_dir = shared_artifacts_dir(args.base_vm_name, args.shared_data_dir)
    destination_dir = Path(args.session_data_dir) / args.release
    pattern = f"{args.base_vm_name}.*.stable-snapshot-source"

    for source in source_dir.glob(pattern):
        if source.is_symlink() or not source.is_file() or not inside(source, args.shared_data_dir):
            raise RuntimeError(f"shared snapshot source marker is unsafe: {source}")

        destination = destination_dir / source.name
        if destination.is_symlink():
            raise RuntimeError(f"refusing to use symlinked session snapshot marker: {destination}")
        if destination.exists():
            if not destination.is_file():
                raise RuntimeError(f"session snapshot marker is not a file: {destination}")
            continue
        atomic_write_bytes(destination, source.read_bytes())


def session_snapshot_names(vm_name):
    result = virsh("snapshot-list", vm_name, "--name", check=False)
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def domain_state(vm_name):
    result = virsh("domstate", vm_name, check=False)
    if result.returncode != 0:
        return ""
    return result.stdout.strip().splitlines()[-1].lower()


def stop_session_vm(vm_name):
    state = domain_state(vm_name)
    if state in {"running", "idle", "blocked", "paused", "shutdown", "in shutdown", "pmsuspended"}:
        virsh("destroy", vm_name)
    elif state not in {"", "shut off", "crashed"}:
        raise RuntimeError(f"unexpected state for session VM {vm_name}: {state}")


def session_disk(domain, disk_path):
    devices = domain.find("devices")
    if devices is None:
        raise RuntimeError("session domain XML has no devices section")
    for disk in devices.findall("disk"):
        target = disk.find("target")
        if target is None or target.get("dev") != "vda":
            continue
        source = disk.find("source")
        if source is None:
            source = ET.SubElement(disk, "source")
        source.attrib.clear()
        source.set("file", str(disk_path))
        return
    raise RuntimeError("session domain XML has no vda disk")


def session_agent_socket(domain, socket_dir, vm_name):
    path = os.path.join(socket_dir, "qemu", "run", f"{vm_name}.sock")
    if len(os.fsencode(path)) >= 108:
        raise RuntimeError(f"session VM guest-agent socket path is too long: {path}")

    devices = domain.find("devices")
    if devices is None:
        raise RuntimeError("session domain XML has no devices section")
    for channel in devices.findall("channel"):
        target = channel.find("target")
        if (
            channel.get("type") != "unix"
            or target is None
            or target.get("name") != "org.qemu.guest_agent.0"
        ):
            continue
        source = channel.find("source")
        if source is None:
            source = ET.SubElement(channel, "source")
        source.set("mode", "bind")
        source.set("path", path)
        return


def isolate_domain(domain, args, disk_path):
    name = domain.find("name")
    if name is None:
        raise RuntimeError("shared snapshot domain XML has no name")
    name.text = args.vm_name

    domain_uuid = domain.find("uuid")
    if domain_uuid is None:
        domain_uuid = ET.SubElement(domain, "uuid")
    domain_uuid.text = str(uuid.uuid4())

    title = domain.find("title")
    if title is None:
        title = ET.SubElement(domain, "title")
    title.text = f"Copilot E2E session {args.session_id}"

    session_disk(domain, disk_path)
    session_agent_socket(domain, args.socket_dir, args.vm_name)

    for interface in domain.findall("./devices/interface"):
        if interface.get("type") == "user":
            continue
        mac = interface.find("mac")
        if mac is None:
            continue
        suffix = uuid.uuid4().int & 0xFFFFFF
        mac.set(
            "address",
            f"52:54:00:{(suffix >> 16) & 0xff:02x}:{(suffix >> 8) & 0xff:02x}:{suffix & 0xff:02x}",
        )

    for cid in domain.findall("./devices/vsock/cid"):
        if cid.get("auto") == "yes":
            cid.attrib.pop("address", None)


def atomic_write_xml(path, element):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f"refusing to overwrite symlinked session domain XML: {path}")
    fd, temporary_path = tempfile.mkstemp(prefix=".session-domain.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            ET.indent(element)
            stream.write(ET.tostring(element, encoding="utf-8", xml_declaration=True))
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def atomic_write_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f"refusing to overwrite symlinked E2E marker: {path}")
    fd, temporary_path = tempfile.mkstemp(prefix=".e2e-marker.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def create_overlay(backing_path, backing_format, overlay_path):
    overlay_path = Path(overlay_path)
    overlay_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if overlay_path.exists() or overlay_path.is_symlink():
        raise RuntimeError(f"refusing to overwrite existing session disk: {overlay_path}")
    run(
        [
            "qemu-img",
            "create",
            "-f",
            "qcow2",
            "-F",
            backing_format,
            "-b",
            backing_path,
            str(overlay_path),
        ]
    )
    os.chmod(overlay_path, 0o600)


def define_session_domain(snapshot, args, session_disk_path):
    shared_domain = snapshot.find("domain")
    if shared_domain is None:
        raise RuntimeError("shared snapshot has no domain configuration")

    session_domain = ET.fromstring(ET.tostring(shared_domain))
    isolate_domain(session_domain, args, session_disk_path)
    artifacts_dir = Path(args.session_data_dir) / args.release
    xml_name = args.vm_alias.removesuffix(f"-{args.release}")
    xml_path = artifacts_dir / f"{xml_name}.xml"
    atomic_write_xml(xml_path, session_domain)
    virsh("define", str(xml_path))


def replace_session_disk(args, session_disk_path):
    output = virsh("dumpxml", args.vm_name, "--inactive").stdout
    try:
        domain = ET.fromstring(output)
    except ET.ParseError as error:
        raise RuntimeError(f"could not parse session VM XML: {error}") from error
    session_disk(domain, session_disk_path)
    session_agent_socket(domain, args.socket_dir, args.vm_name)

    artifacts_dir = Path(args.session_data_dir) / args.release
    xml_name = args.vm_alias.removesuffix(f"-{args.release}")
    xml_path = artifacts_dir / f"{xml_name}.xml"
    atomic_write_xml(xml_path, domain)
    virsh("define", str(xml_path))


def session_vda_path(vm_name):
    output = virsh("dumpxml", vm_name, "--inactive").stdout
    try:
        domain = ET.fromstring(output)
    except ET.ParseError as error:
        raise RuntimeError(f"could not parse session VM XML: {error}") from error
    devices = domain.find("devices")
    if devices is None:
        raise RuntimeError("session VM XML has no devices section")
    for disk in devices.findall("disk"):
        target = disk.find("target")
        if target is not None and target.get("dev") == "vda":
            source = disk.find("source")
            if source is not None and source.get("file"):
                return os.path.realpath(source.get("file"))
    raise RuntimeError(f"session VM {vm_name} has no file-backed vda disk")


def prepare_session_domain(args, snapshot):
    backing_path, backing_format = snapshot_disk_path(snapshot, args.shared_data_dir)
    if backing_path == base_active_disk_path(args.base_vm_name):
        raise RuntimeError(
            f"shared snapshot {args.snapshot} points to the base VM's mutable active disk"
        )

    artifacts_dir = Path(args.session_data_dir) / args.release
    base_disk_path = artifacts_dir / f"{args.vm_alias}.qcow2"
    if virsh_domain_exists(args.vm_name):
        active_disk = session_vda_path(args.vm_name)
        if not inside(active_disk, args.session_data_dir):
            raise RuntimeError(
                f"session VM {args.vm_name} uses a disk outside its private data directory: {active_disk}"
            )
        return base_disk_path

    if base_disk_path.exists() or base_disk_path.is_symlink():
        raise RuntimeError(
            f"session disk exists without its VM definition; refusing to reuse it: {base_disk_path}"
        )
    create_overlay(backing_path, backing_format, base_disk_path)
    define_session_domain(snapshot, args, base_disk_path)
    return base_disk_path


def prepare(args):
    validate_paths(args)
    ensure_base_domain(args.base_vm_name, args.shared_data_dir, args.release)
    copy_shared_source_markers(args)
    snapshot = shared_snapshot_xml(args.base_vm_name, args.snapshot)
    prepare_session_domain(args, snapshot)
    print(f"prepared isolated E2E VM {args.vm_name} from shared snapshot {args.base_vm_name}/{args.snapshot}")


def restore(args):
    validate_paths(args)
    if args.force:
        reset_session_vm(args)

    if virsh_domain_exists(args.vm_name):
        if args.snapshot in session_snapshot_names(args.vm_name):
            virsh("snapshot-revert", args.vm_name, args.snapshot)
            state = domain_state(args.vm_name)
            if state == "shut off":
                virsh("start", args.vm_name)
            elif state == "paused":
                virsh("resume", args.vm_name)
            elif state != "running":
                raise RuntimeError(
                    f"session VM {args.vm_name} is not running after snapshot revert: {state}"
                )
            print(f"restored session snapshot {args.snapshot} on {args.vm_name}")
            return

    ensure_base_domain(args.base_vm_name, args.shared_data_dir, args.release)
    copy_shared_source_markers(args)
    snapshot = shared_snapshot_xml(args.base_vm_name, args.snapshot)
    stop_session_vm(args.vm_name)
    artifacts_dir = Path(args.session_data_dir) / args.release
    domain_exists = virsh_domain_exists(args.vm_name)
    if not domain_exists:
        prepare_session_domain(args, snapshot)
        virsh("start", args.vm_name)
        if domain_state(args.vm_name) != "running":
            raise RuntimeError(f"session VM did not reach running state: {args.vm_name}")
        print(
            f"started isolated E2E VM {args.vm_name} from shared snapshot "
            f"{args.base_vm_name}/{args.snapshot}"
        )
        return

    backing_path, backing_format = snapshot_disk_path(snapshot, args.shared_data_dir)
    if backing_path == base_active_disk_path(args.base_vm_name):
        raise RuntimeError(
            f"shared snapshot {args.snapshot} points to the base VM's mutable active disk"
        )
    if not inside(session_vda_path(args.vm_name), args.session_data_dir):
        raise RuntimeError(f"session VM {args.vm_name} uses a disk outside its private data directory")
    overlay_path = artifacts_dir / (
        f"{args.vm_name}.baseline-{re.sub(r'[^A-Za-z0-9_.-]', '_', args.snapshot)}-{time.time_ns()}.qcow2"
    )
    create_overlay(backing_path, backing_format, overlay_path)
    if domain_exists:
        replace_session_disk(args, overlay_path)

    virsh("start", args.vm_name)
    if domain_state(args.vm_name) != "running":
        raise RuntimeError(f"session VM did not reach running state: {args.vm_name}")
    print(
        f"started isolated E2E VM {args.vm_name} from shared snapshot "
        f"{args.base_vm_name}/{args.snapshot}"
    )


def reset_session_vm(args):
    if virsh_domain_exists(args.vm_name):
        stop_session_vm(args.vm_name)
        virsh("undefine", args.vm_name, "--snapshots-metadata")

    artifacts_dir = Path(args.session_data_dir) / args.release
    if artifacts_dir.is_symlink():
        raise RuntimeError(f"refusing to remove symlinked session artifacts: {artifacts_dir}")
    if artifacts_dir.exists():
        if not artifacts_dir.is_dir() or not inside(artifacts_dir, args.session_data_dir):
            raise RuntimeError(f"refusing to remove unsafe session artifacts: {artifacts_dir}")
        shutil.rmtree(artifacts_dir)
    artifacts_dir.mkdir(mode=0o700, parents=True, exist_ok=True)


def session_vm_context():
    session_id = os.environ.get("AUTHD_E2E_SESSION_ID", "")
    vm_name = os.environ.get("VM_NAME", "")
    if not session_id or not vm_name:
        return None
    if not re.fullmatch(r"[A-Za-z0-9]{8}", session_id):
        raise RuntimeError("invalid E2E session identifier")
    suffix = f"-copilot-{session_id}"
    if vm_name.endswith(suffix):
        session_vm_name = vm_name
        vm_alias = os.environ.get("AUTHD_E2E_BASE_VM_NAME") or vm_name.removesuffix(suffix)
    else:
        vm_alias = os.environ.get("AUTHD_E2E_BASE_VM_NAME") or vm_name
        session_vm_name = f"{vm_alias}{suffix}"
    return session_id, vm_alias, session_vm_name


def virsh_domain_index(arguments):
    for index, argument in enumerate(arguments):
        if argument in {"--domain", "-d"}:
            return index + 1 if index + 1 < len(arguments) else None
    return next(
        (index for index, argument in enumerate(arguments) if not argument.startswith("-")),
        None,
    )


def virsh_snapshot_name(command, arguments, domain_index):
    for option in ("--snapshotname", "--snapshot"):
        if option in arguments:
            index = arguments.index(option)
            return arguments[index + 1] if index + 1 < len(arguments) else None
    if command == "snapshot-revert" and domain_index is not None:
        return next(
            (
                argument
                for argument in arguments[domain_index + 1 :]
                if not argument.startswith("-")
            ),
            None,
        )
    return None


def virsh_output(arguments):
    result = run([VIRSH_BIN, *arguments], check=False)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


def session_snapshot_names_or_error(vm_name):
    result = virsh("snapshot-list", vm_name, "--name", check=False)
    if result.returncode == 0:
        return {line.strip() for line in result.stdout.splitlines() if line.strip()}
    if virsh_domain_exists(vm_name):
        raise RuntimeError(result.stderr.strip() or f"could not list snapshots for {vm_name}")
    return set()


def session_args(vm_alias, snapshot):
    session_id, context_alias, session_vm_name = session_vm_context() or ("", "", "")
    if not session_id or context_alias != vm_alias:
        raise RuntimeError(f"not an E2E session VM: {vm_alias}")

    release = os.environ.get("RELEASE")
    if not release:
        if "-" not in vm_alias:
            raise RuntimeError("RELEASE is required for session VM operations")
        release = vm_alias.rsplit("-", 1)[1]

    values = {
        "AUTHD_E2E_SHARED_DATA_DIR": os.environ.get("AUTHD_E2E_SHARED_DATA_DIR"),
        "AUTHD_E2E_SESSION_DATA_DIR": os.environ.get("AUTHD_E2E_SESSION_DATA_DIR"),
        "AUTHD_E2E_LIBVIRT_SOCKET_DIR": os.environ.get("AUTHD_E2E_LIBVIRT_SOCKET_DIR"),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(f"missing required E2E environment variables: {', '.join(missing)}")

    return argparse.Namespace(
        action="restore",
        base_vm_name=vm_alias,
        vm_name=session_vm_name,
        vm_alias=vm_alias,
        snapshot=snapshot,
        release=release,
        session_id=session_id,
        shared_data_dir=values["AUTHD_E2E_SHARED_DATA_DIR"],
        session_data_dir=values["AUTHD_E2E_SESSION_DATA_DIR"],
        socket_dir=values["AUTHD_E2E_LIBVIRT_SOCKET_DIR"],
        force=False,
    )


def virsh_proxy(arguments):
    if not arguments:
        return virsh_output(arguments)

    context = session_vm_context()
    if context is None:
        return virsh_output(arguments)
    session_id, vm_alias, session_vm_name = context
    command, *command_arguments = arguments
    domain_index = virsh_domain_index(command_arguments)
    if (
        domain_index is None
        or command_arguments[domain_index] not in {vm_alias, session_vm_name}
    ):
        return virsh_output(arguments)

    mapped_arguments = [
        session_vm_name if argument == vm_alias else argument
        for argument in arguments
    ]
    if command not in {"snapshot-list", "snapshot-revert", "snapshot-delete"}:
        return virsh_output(mapped_arguments)

    if command == "snapshot-list":
        if "--name" not in command_arguments:
            return virsh_output(mapped_arguments)
        local_names = session_snapshot_names_or_error(session_vm_name)
        shared_names = virsh("snapshot-list", vm_alias, "--name", check=False)
        if shared_names.returncode != 0:
            sys.stderr.write(shared_names.stderr)
            return shared_names.returncode
        names = []
        seen = set()
        for output in (
            "\n".join(sorted(local_names)),
            shared_names.stdout,
        ):
            for name in output.splitlines():
                name = name.strip()
                if name and name not in seen:
                    seen.add(name)
                    names.append(name)
        if names:
            sys.stdout.write("\n".join(names) + "\n")
        return 0

    snapshot = virsh_snapshot_name(command, command_arguments, domain_index)
    if not snapshot:
        return virsh_output(mapped_arguments)

    local_names = session_snapshot_names_or_error(session_vm_name)
    if snapshot in local_names:
        return virsh_output(mapped_arguments)

    shared_result = virsh("snapshot-list", vm_alias, "--name", check=False)
    if shared_result.returncode != 0:
        sys.stderr.write(shared_result.stderr)
        return shared_result.returncode
    shared_names = {line.strip() for line in shared_result.stdout.splitlines() if line.strip()}
    if snapshot not in shared_names:
        return virsh_output(mapped_arguments)
    if command == "snapshot-delete":
        sys.stderr.write(f"info: leaving shared baseline snapshot {snapshot} unchanged\n")
        return 0

    restore(session_args(vm_alias, snapshot))
    return 0


def parse_args():
    session_id = os.environ.get("AUTHD_E2E_SESSION_ID")
    configured_vm_name = os.environ.get("VM_NAME")
    configured_base_vm_name = os.environ.get("AUTHD_E2E_BASE_VM_NAME")
    suffix = f"-copilot-{session_id}" if session_id else ""
    if configured_vm_name and suffix and configured_vm_name.endswith(suffix):
        default_vm_alias = configured_base_vm_name or configured_vm_name.removesuffix(suffix)
        default_vm_name = configured_vm_name
    else:
        default_vm_alias = configured_base_vm_name or configured_vm_name
        default_vm_name = (
            f"{default_vm_alias}{suffix}" if default_vm_alias and suffix else None
        )

    parser = argparse.ArgumentParser(
        description="Create and reset a per-Copilot authd E2E VM."
    )
    parser.add_argument("action", choices=("prepare", "restore"))
    parser.add_argument(
        "--base-vm",
        dest="base_vm_name",
        default=configured_base_vm_name or default_vm_alias,
    )
    parser.add_argument("--vm", dest="vm_name", default=default_vm_name)
    parser.add_argument("--vm-alias", default=default_vm_alias)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--release", default=os.environ.get("RELEASE"))
    parser.add_argument("--session-id", default=session_id)
    parser.add_argument("--shared-data-dir", default=os.environ.get("AUTHD_E2E_SHARED_DATA_DIR"))
    parser.add_argument("--session-data-dir", default=os.environ.get("AUTHD_E2E_SESSION_DATA_DIR"))
    parser.add_argument("--socket-dir", default=os.environ.get("AUTHD_E2E_LIBVIRT_SOCKET_DIR"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not args.vm_alias:
        args.vm_alias = args.base_vm_name
    if not args.base_vm_name:
        args.base_vm_name = args.vm_alias
    if not args.vm_name and args.vm_alias and args.session_id:
        args.vm_name = f"{args.vm_alias}-copilot-{args.session_id}"
    if not args.release and args.vm_alias and "-" in args.vm_alias:
        args.release = args.vm_alias.rsplit("-", 1)[1]

    missing = [
        name
        for name, value in (
            ("VM_NAME or AUTHD_E2E_BASE_VM_NAME", args.base_vm_name),
            ("VM_NAME", args.vm_alias),
            ("session VM name", args.vm_name),
            ("RELEASE", args.release),
            ("AUTHD_E2E_SESSION_ID", args.session_id),
            ("AUTHD_E2E_SHARED_DATA_DIR", args.shared_data_dir),
            ("AUTHD_E2E_SESSION_DATA_DIR", args.session_data_dir),
            ("AUTHD_E2E_LIBVIRT_SOCKET_DIR", args.socket_dir),
        )
        if not value
    ]
    if missing:
        parser.error(f"missing required E2E environment variables: {', '.join(missing)}")
    return args


def main():
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "virsh":
            return virsh_proxy(sys.argv[2:])
        args = parse_args()
        if args.action == "prepare":
            prepare(args)
        else:
            restore(args)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        return fail(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
