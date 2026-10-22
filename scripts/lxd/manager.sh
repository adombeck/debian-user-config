#!/usr/bin/env bash

PRIVATE_LXD_UNIT=copilot-lxd.service
PRIVATE_LXD_LEASE_FD=
# Used by the calling sandbox wrapper.
# shellcheck disable=SC2034
PRIVATE_LXD_BIND_ARGS=()

private_lxd_client() {
    env LXD_DIR="$PRIVATE_LXD_STATE" LXD_CONF="$HOST_XDG_RUNTIME_DIR/copilot-lxd-manager/client" \
        /snap/lxd/current/bin/lxc "$@"
}

start_private_lxd() {
    local directory launcher service_pid namespace_pid
    local manager="$HOST_XDG_RUNTIME_DIR/copilot-lxd-manager"
    for executable in /snap/lxd/current/sbin/lxd /usr/bin/unshare /usr/bin/slirp4netns; do
        if [[ ! -x "$executable" ]]; then
            echo "error: private LXD dependency is missing: $executable" >&2
            return 1
        fi
    done
    for device in /dev/net/tun /dev/fuse; do
        if [[ ! -c "$device" || ! -r "$device" || ! -w "$device" ]]; then
            echo "error: private LXD requires access to $device" >&2
            return 1
        fi
    done
    PRIVATE_LXD_STATE="$HOME/.local/share/copilot-lxd"
    PRIVATE_LXD_RUNTIME="$HOST_XDG_RUNTIME_DIR/copilot-lxd"
    launcher="$HOME/.local/libexec/debian-user-config/copilot-lxd-bwrap"
    if [[ ! -r /etc/apparmor.d/debian-user-config-copilot-lxd ]]; then
        echo "error: install the private LXD policy with: sudo $SCRIPT_DIR/../apparmor/install-lxd.sh" >&2
        return 1
    fi
    for directory in "$HOME/.local" "$HOME/.local/share" "$PRIVATE_LXD_STATE" "$PRIVATE_LXD_STATE/client" "$PRIVATE_LXD_RUNTIME" "$manager" "$(dirname "$launcher")"; do
        if [[ -L "$directory" || (-e "$directory" && ! -d "$directory") ]]; then
            echo "error: invalid private LXD directory: $directory" >&2
            return 1
        fi
        mkdir -p "$directory"
        if [[ "$(stat -c %u "$directory")" != "$USER_ID" ]]; then
            echo "error: private LXD directory is not owned by the current user: $directory" >&2
            return 1
        fi
    done
    chmod 700 "$PRIVATE_LXD_STATE" "$PRIVATE_LXD_STATE/client" "$PRIVATE_LXD_RUNTIME" "$manager" "$(dirname "$launcher")"
    if [[ -L "$manager/lock" || -L "$manager/leases" ||
        -L "$launcher" || (-e "$launcher" && ! -f "$launcher") ]]; then
        echo "error: refusing unexpected private LXD launcher or lock paths" >&2
        return 1
    fi
    exec {PRIVATE_LXD_LOCK_FD}>>"$manager/lock"
    flock -x "$PRIVATE_LXD_LOCK_FD"
    exec {PRIVATE_LXD_LEASE_FD}>>"$manager/leases"
    flock -s "$PRIVATE_LXD_LEASE_FD"
    if ! systemd_user is-active --quiet "$PRIVATE_LXD_UNIT"; then
        install -m 755 "$BWRAP_BIN" "$launcher"
        rm -f -- "$PRIVATE_LXD_STATE/unix.socket"
        systemd_run_user --unit="$PRIVATE_LXD_UNIT" --collect --quiet \
            --property=Type=exec --property=Delegate=yes \
            --property=DelegateSubgroup=supervisor \
            --property=MemoryMax=8G --property=TasksMax=4096 --property=CPUQuota=400% \
            --property=TimeoutStopSec=30 --property=StandardOutput=journal --property=StandardError=journal \
            -- /usr/bin/python3 "$SCRIPT_DIR/lxd/service.py" \
            "$PRIVATE_LXD_STATE" "$PRIVATE_LXD_RUNTIME" "$PROJECTS_DIR" "$launcher"
    fi
    service_pid="$(systemd_user show --property=MainPID --value "$PRIVATE_LXD_UNIT")"
    if [[ ! "$service_pid" =~ ^[1-9][0-9]*$ ]]; then
        echo "error: private LXD supervisor is not running" >&2
        return 1
    fi
    local ready=false
    for ((attempt=0; attempt<600; attempt++)); do
        if [[ -S "$PRIVATE_LXD_STATE/unix.socket" ]] &&
            private_lxd_client query /1.0 >/dev/null 2>&1; then
            ready=true
            break
        fi
        if ! systemd_user is-active --quiet "$PRIVATE_LXD_UNIT"; then
            break
        fi
        sleep 0.1
    done
    if [[ "$ready" != true ]]; then
        echo "error: private LXD failed to start; inspect journalctl --user -u $PRIVATE_LXD_UNIT" >&2
        return 1
    fi
    namespace_pid="$(<"$PRIVATE_LXD_RUNTIME/namespace.pid")"
    if [[ ! "$namespace_pid" =~ ^[1-9][0-9]*$ ]] ||
        [[ "$(<"/proc/$namespace_pid/attr/current")" != "debian-user-config-copilot-lxd (enforce)" ]] ||
        ! awk -v uid="$USER_ID" 'NR == 1 {valid = ($1 == 0 && $2 == uid && $3 == 1)} END {exit !valid}' "/proc/$namespace_pid/uid_map"; then
        echo "error: private LXD namespace or AppArmor confinement is not active" >&2
        return 1
    fi
    local pools networks
    pools="$(private_lxd_client storage list --format csv -c n)"
    networks="$(private_lxd_client network list --format csv -c n)"
    if ! grep -Fxq builds <<<"$pools"; then
        private_lxd_client storage create builds dir
    fi
    if ! grep -Fxq builds <<<"$networks"; then
        private_lxd_client network create builds ipv4.address=10.42.0.1/24 ipv4.nat=true ipv6.address=none
    fi
    configure_private_lxd_profile default
    local projects
    projects="$(private_lxd_client project list --format csv -c n)"
    if grep -Fxq snapcraft <<<"$projects" &&
        [[ "$(private_lxd_client project get snapcraft features.profiles)" == true ]]; then
        configure_private_lxd_profile snapcraft
    fi
    # shellcheck disable=SC2034
    PRIVATE_LXD_BIND_ARGS=(
        --bind "$PRIVATE_LXD_STATE/unix.socket" /tmp/copilot-runtime/lxd/unix.socket
        --bind "$PRIVATE_LXD_STATE/unix.socket" /var/lib/lxd/unix.socket
        --ro-bind "$SCRIPT_DIR/lxd/client" /tmp/copilot-runtime/lxd-bin/lxd
        --ro-bind "$SCRIPT_DIR/lxd/snapcraft" /tmp/copilot-runtime/lxd-bin/snapcraft
        --bind "$PRIVATE_LXD_STATE/client" "$PRIVATE_LXD_STATE/client"
    )
    SANDBOX_ENV_ARGS+=(
        --setenv LXD_DIR /tmp/copilot-runtime/lxd
        --setenv LXD_CONF /tmp/copilot-runtime/lxd-client
        --setenv SNAPCRAFT_BUILD_ENVIRONMENT lxd
        --setenv COPILOT_SNAPCRAFT_HOME "$PRIVATE_LXD_STATE/client"
        --setenv PATH "/tmp/copilot-runtime/lxd-bin:$SANDBOX_PATH"
    )
    flock -u "$PRIVATE_LXD_LOCK_FD"
}

configure_private_lxd_profile() {
    private_lxd_client --project "$1" profile edit default <<EOF
config:
  boot.autostart: "false"
  # Root is already mapped to the host user by the outer namespace.
  security.privileged: "true"
  raw.lxc: |
    lxc.apparmor.profile=unchanged
    lxc.mount.entry=/run/copilot-securityfs sys/kernel/security none bind,create=dir 0 0
    lxc.cap.drop=
    lxc.cap.drop=sys_time sys_module sys_rawio mac_override
description: Private Copilot build containers
devices:
  root:
    type: disk
    path: /
    pool: builds
  eth0:
    type: nic
    network: builds
    name: eth0
  fuse:
    type: unix-char
    source: /dev/fuse
    path: /dev/fuse
  snapcraft-launcher:
    type: disk
    source: $SCRIPT_DIR/lxd/snapcraft
    path: /usr/local/bin/snapcraft
    readonly: "true"
EOF
}

cleanup_private_lxd() {
    [[ -n "$PRIVATE_LXD_LEASE_FD" ]] || return 0
    flock -x "$PRIVATE_LXD_LOCK_FD"
    flock -u "$PRIVATE_LXD_LEASE_FD"
    if flock -xn "$PRIVATE_LXD_LEASE_FD"; then
        if ! systemd_user stop "$PRIVATE_LXD_UNIT"; then
            echo "warning: could not stop the private LXD service" >&2
        fi
    fi
    flock -u "$PRIVATE_LXD_LOCK_FD"
}
