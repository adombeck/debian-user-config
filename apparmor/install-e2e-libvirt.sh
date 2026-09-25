#!/usr/bin/env bash

set -euo pipefail

if [[ "$(grep -E '^NoNewPrivs:' /proc/self/status | awk '{print $2}')" == 1 ]]; then
    echo "error: run this installer from a normal host shell, not inside a sandbox" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POLICY_SOURCE="$SCRIPT_DIR/debian-user-config-copilot-e2e-libvirt"
POLICY_TARGET="/etc/apparmor.d/debian-user-config-copilot-e2e-libvirt"

if [[ ! -r "$POLICY_SOURCE" ]]; then
    echo "error: E2E libvirt AppArmor policy not found: $POLICY_SOURCE" >&2
    exit 1
fi

run_root() {
    if [[ "$(id -u)" -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

run_root install -d -m 0755 /etc/apparmor.d
run_root install -o root -g root -m 0644 "$POLICY_SOURCE" "$POLICY_TARGET"
run_root apparmor_parser -r "$POLICY_TARGET"

echo "Installed the AppArmor confinement for Copilot's rootless E2E libvirt session."
