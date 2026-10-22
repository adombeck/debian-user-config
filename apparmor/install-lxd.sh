#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" != 0 || "$(awk '/^NoNewPrivs:/ {print $2}' /proc/self/status)" == 1 ]]; then
    echo "error: run sudo $0 from a normal host shell" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
install -o root -g root -m 644 "$SCRIPT_DIR/debian-user-config-copilot-lxd" \
    /etc/apparmor.d/debian-user-config-copilot-lxd
apparmor_parser -r /etc/apparmor.d/debian-user-config-copilot-lxd
echo "Installed the AppArmor policy for Copilot's rootless private LXD."
