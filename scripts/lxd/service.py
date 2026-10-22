#!/usr/bin/env python3
"""Run a private, rootless LXD service for the Copilot sandbox."""

import argparse
import json
import os
import select
import signal
import subprocess
from pathlib import Path


def wait_for_byte(fd, process, timeout=30):
    if not select.select([fd], [], [], timeout)[0] or not os.read(fd, 1):
        raise RuntimeError(
            f"Private LXD networking did not start (rc={process.poll()})"
        )


def run(state, runtime, projects, bwrap):
    payload = Path("/snap/lxd/current").resolve(strict=True)
    cgroup = Path("/sys/fs/cgroup") / Path(
        Path("/proc/self/cgroup").read_text().strip().split("::", 1)[1]
    ).relative_to("/")
    if cgroup.name != "supervisor":
        raise RuntimeError("Private LXD must run in a delegated supervisor subgroup")
    delegated = cgroup.parent
    environment = {
        "PATH": f"{payload}/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": "/root",
        "LANG": "C.UTF-8",
        "LXD_DIR": "/var/lib/copilot-lxd",
        "LXD_CONF": "/root/.config/lxc",
        "LXD_EXEC_PATH": str(payload / "sbin/lxd"),
        "LXD_LXC_TEMPLATE_CONFIG": str(payload / "lxc/config"),
        "LXD_LXC_HOOK": str(payload / "lxc/hooks"),
        "LD_LIBRARY_PATH": f"{payload}/lib:{payload}/lib/x86_64-linux-gnu",
    }
    initialization = """
set -euo pipefail
if [[ "$(< /proc/self/attr/current)" != debian-user-config-copilot-lxd* ]]; then
    echo "error: private LXD AppArmor profile is not active" >&2
    exit 1
fi
mount -t sysfs -o ro sysfs /sys
mount -t cgroup2 cgroup2 /sys/fs/cgroup
echo 1 >/proc/sys/net/ipv4/ip_forward
for controller in cpu memory pids; do
    echo "+$controller" >/sys/fs/cgroup/cgroup.subtree_control
done
mkdir -p /var/snap/lxd/common/lxc /root/.config/lxc
printf 'root:0:65536\\n' >/etc/subuid
printf 'root:0:65536\\n' >/etc/subgid
printf 'root:x:0:0:root:/root:/bin/bash\\n' >/etc/passwd
printf 'root:x:0:\\n' >/etc/group
printf 'nameserver 10.0.2.3\\n' >/etc/resolv.conf
printf '127.0.0.1 localhost\\n' >/etc/hosts
chmod 755 /etc
for ((attempt=0; attempt<600; attempt++)); do
    if [[ -e /run/copilot-lxd/network-ready ]]; then
        exec /usr/bin/python3 -c '
import ctypes
import os
apparmor = ctypes.CDLL("libapparmor.so.1", use_errno=True)
if apparmor.aa_stack_onexec(b":copilot-lxd:unconfined") != 0:
    raise OSError(ctypes.get_errno(), "Cannot enter private AppArmor namespace")
# The transition sanitizes LD_LIBRARY_PATH. Restore it after entering the
# child namespace, before loading the snap-provided daemon and libraries.
os.execv("/usr/bin/env", ["env", "LD_LIBRARY_PATH=" + os.environ["LD_LIBRARY_PATH"], os.environ["LXD_EXEC_PATH"]])
'
    fi
    sleep 0.05
done
echo "error: private LXD network did not become ready" >&2
exit 1
"""
    info_read, info_write = os.pipe()
    ready_read, ready_write = os.pipe()
    network_ready = runtime / "network-ready"
    namespace_pid = runtime / "namespace.pid"
    network_ready.unlink(missing_ok=True)
    namespace_pid.unlink(missing_ok=True)
    worker = None
    network = None
    try:
        worker = subprocess.Popen(
            [
                "/usr/bin/bash",
                "-euc",
                'echo $$ >"$1/cgroup.procs"; shift; exec "$@"',
                "--",
                str(delegated),
                "/usr/bin/unshare",
                "--user",
                "--map-root-user",
                "--map-users=auto",
                "--map-groups=auto",
                "--cgroup",
                "--",
                "/usr/bin/bash",
                "-euc",
                'mkdir -p "$1/worker"; echo $$ >"$1/worker/cgroup.procs"; shift; exec "$@"',
                "--",
                str(delegated),
                str(bwrap),
                "--unshare-pid",
                "--unshare-net",
                "--unshare-ipc",
                "--unshare-uts",
                "--die-with-parent",
                "--new-session",
                "--cap-add",
                "ALL",
                "--info-fd",
                str(info_write),
                "--clearenv",
                *[
                    arg
                    for key, value in environment.items()
                    for arg in ("--setenv", key, value)
                ],
                "--ro-bind",
                "/usr",
                "/usr",
                "--symlink",
                "usr/bin",
                "/bin",
                "--symlink",
                "usr/sbin",
                "/sbin",
                "--symlink",
                "usr/lib",
                "/lib",
                "--symlink",
                "usr/lib64",
                "/lib64",
                "--ro-bind",
                "/snap",
                "/snap",
                "--ro-bind",
                "/etc/ssl",
                "/etc/ssl",
                "--ro-bind",
                "/etc/os-release",
                "/etc/os-release",
                "--ro-bind",
                "/etc/nsswitch.conf",
                "/etc/nsswitch.conf",
                "--dev",
                "/dev",
                "--dev-bind",
                "/dev/net/tun",
                "/dev/net/tun",
                "--dev-bind",
                "/dev/fuse",
                "/dev/fuse",
                "--proc",
                "/proc",
                "--ro-bind",
                "/sys",
                "/sys",
                "--bind",
                "/sys/kernel/security",
                "/run/copilot-securityfs",
                "--tmpfs",
                "/tmp",
                "--chmod",
                "1777",
                "/tmp",
                "--dir",
                "/root",
                "--dir",
                "/etc",
                "--bind",
                str(state),
                "/var/lib/copilot-lxd",
                "--bind",
                str(state / "client"),
                str(state / "client"),
                "--ro-bind",
                str(runtime),
                "/run/copilot-lxd",
                "--bind",
                str(projects),
                str(projects),
                "--chdir",
                "/",
                "/usr/bin/bash",
                "-euc",
                initialization,
            ],
            pass_fds=(info_write,),
        )
        os.close(info_write)
        info_write = None
        if not select.select([info_read], [], [], 30)[0]:
            raise RuntimeError("Private LXD namespace launcher did not start")
        with os.fdopen(info_read) as stream:
            info_read = None
            child_pid = json.load(stream)["child-pid"]
        with namespace_pid.open("x") as stream:
            stream.write(str(child_pid))
        network = subprocess.Popen(
            [
                "/usr/bin/slirp4netns",
                "--configure",
                "--disable-host-loopback",
                "--ready-fd",
                str(ready_write),
                "--userns-path",
                f"/proc/{child_pid}/ns/user",
                str(child_pid),
                "tap0",
            ],
            pass_fds=(ready_write,),
        )
        os.close(ready_write)
        ready_write = None
        wait_for_byte(ready_read, network)
        network_ready.touch(mode=0o600)
        while True:
            if network.poll() is not None:
                raise RuntimeError(
                    f"Private LXD network exited with {network.returncode}"
                )
            try:
                return worker.wait(timeout=1)
            except subprocess.TimeoutExpired:
                continue
    finally:
        for fd in (info_read, info_write, ready_read, ready_write):
            if fd is not None:
                os.close(fd)
        for process in (worker, network):
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
        network_ready.unlink(missing_ok=True)
        namespace_pid.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state", type=Path)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("projects", type=Path)
    parser.add_argument("bwrap", type=Path)
    args = parser.parse_args()
    if os.getuid() == 0:
        parser.error("start the private LXD service as a normal user, not root")

    def stop(_signum, _frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    return run(args.state, args.runtime, args.projects, args.bwrap)


if __name__ == "__main__":
    raise SystemExit(main())
