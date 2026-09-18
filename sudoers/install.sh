#!/usr/bin/env bash

set -euo pipefail

if [[ "$(grep -E '^NoNewPrivs:' /proc/self/status | awk '{print $2}')" == 1 ]]; then
    echo "error: run this installer from a normal host shell, not inside a sandbox" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POLICY_SOURCE="$SCRIPT_DIR/debian-user-config-copilot"
VSOCK_HELPER_SOURCE="$SCRIPT_DIR/copilot-setup-vsock"
GUESTFISH_HELPER_SOURCE="$SCRIPT_DIR/copilot-e2e-guestfish"
POLICY_TARGET="/etc/sudoers.d/debian-user-config-copilot"
HELPER_DIR="/usr/local/libexec/debian-user-config"
VSOCK_HELPER_TARGET="$HELPER_DIR/copilot-setup-vsock"
GUESTFISH_HELPER_TARGET="$HELPER_DIR/copilot-e2e-guestfish"

for source in "$POLICY_SOURCE" "$VSOCK_HELPER_SOURCE" "$GUESTFISH_HELPER_SOURCE"; do
    if [[ ! -r "$source" ]]; then
        echo "error: sudo policy source not found: $source" >&2
        exit 1
    fi
done

if [[ "$(id -u)" -eq 0 ]]; then
    TARGET_UID="${SUDO_UID:-}"
else
    TARGET_UID="$(id -u)"
fi
if [[ ! "$TARGET_UID" =~ ^[1-9][0-9]*$ ]]; then
    echo "error: run this installer as the Copilot user or via sudo from that user" >&2
    exit 1
fi

TEMP_POLICY="$(mktemp)"
trap 'rm -f "$TEMP_POLICY"' EXIT
sed "s/__COPILOT_UID__/#${TARGET_UID}/" "$POLICY_SOURCE" >"$TEMP_POLICY"
visudo -cf "$TEMP_POLICY" >/dev/null

run_root() {
    if [[ "$(id -u)" -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

run_root install -d -m 0755 "$HELPER_DIR"
run_root install -o root -g root -m 0755 "$VSOCK_HELPER_SOURCE" "$VSOCK_HELPER_TARGET"
run_root install -o root -g root -m 0755 "$GUESTFISH_HELPER_SOURCE" "$GUESTFISH_HELPER_TARGET"
run_root install -d -m 0750 /etc/sudoers.d
run_root install -o root -g root -m 0440 "$TEMP_POLICY" "$POLICY_TARGET"
run_root visudo -cf "$POLICY_TARGET" >/dev/null

echo "Installed the passwordless Copilot E2E sudo policy for UID $TARGET_UID."
