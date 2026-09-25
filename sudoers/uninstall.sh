#!/usr/bin/env bash

set -euo pipefail

if [[ "$(grep -E '^NoNewPrivs:' /proc/self/status | awk '{print $2}')" == 1 ]]; then
    echo "error: run this uninstaller from a normal host shell, not inside a sandbox" >&2
    exit 1
fi

POLICY_TARGET="/etc/sudoers.d/debian-user-config-copilot"
HELPER_DIR="/usr/local/libexec/debian-user-config"

run_root() {
    if [[ "$(id -u)" -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

run_root rm -f -- \
    "$POLICY_TARGET" \
    "$HELPER_DIR/copilot-setup-vsock" \
    "$HELPER_DIR/copilot-e2e-guestfish"
run_root rmdir -- "$HELPER_DIR" 2>/dev/null || true
run_root visudo -c >/dev/null

echo "Removed the legacy Copilot E2E sudo policy and helpers."
