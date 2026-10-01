#!/usr/bin/env bash

set -euo pipefail

if [[ "$(grep -E '^NoNewPrivs:' /proc/self/status | awk '{print $2}')" == 1 ]]; then
    echo "error: run this installer from a normal host shell, not inside a sandbox" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POLICY_SOURCE="$SCRIPT_DIR/debian-user-config-copilot-podman"
E2E_LIBVIRT_POLICY_SOURCE="$SCRIPT_DIR/debian-user-config-copilot-e2e-libvirt"
AUTHD_TEST_POLICY_SOURCE="$SCRIPT_DIR/debian-user-config-copilot-authd-tests"
LOCAL_POLICY="/etc/apparmor.d/local/bwrap-userns-restrict"
INSTALLED_POLICY="/etc/apparmor.d/debian-user-config-copilot-podman"
INSTALLED_E2E_LIBVIRT_POLICY="/etc/apparmor.d/debian-user-config-copilot-e2e-libvirt"
INSTALLED_AUTHD_TEST_POLICY="/etc/apparmor.d/debian-user-config-copilot-authd-tests"
TRANSITION_RULE='priority=110 @{HOME}/.local/libexec/debian-user-config/copilot-podman Px -> debian-user-config-copilot-podman,'
AUTHD_TEST_TRANSITION_RULE='priority=110 @{HOME}/projects/authd*/.authd-test-tmp.*/go-build*/b*/*.test Px -> debian-user-config-copilot-authd-tests,'

for source in "$POLICY_SOURCE" "$E2E_LIBVIRT_POLICY_SOURCE" "$AUTHD_TEST_POLICY_SOURCE"; do
    if [[ ! -r "$source" ]]; then
        echo "error: AppArmor policy source not found: $source" >&2
        exit 1
    fi
done

BWRAP_POLICY=
for candidate in \
    /etc/apparmor.d/bwrap-userns-restrict \
    /usr/share/apparmor/extra-profiles/bwrap-userns-restrict \
    /etc/apparmor.d/usr.bin.bwrap
do
    if [[ -r "$candidate" ]]; then
        BWRAP_POLICY="$candidate"
        break
    fi
done
if [[ -z "$BWRAP_POLICY" ]]; then
    echo "error: could not locate the bwrap-userns-restrict AppArmor policy" >&2
    exit 1
fi

run_root() {
    if [[ "$(id -u)" -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

run_root install -d -m 0755 /etc/apparmor.d/local
run_root install -m 0644 "$POLICY_SOURCE" "$INSTALLED_POLICY"
run_root install -m 0644 "$E2E_LIBVIRT_POLICY_SOURCE" "$INSTALLED_E2E_LIBVIRT_POLICY"
run_root install -m 0644 "$AUTHD_TEST_POLICY_SOURCE" "$INSTALLED_AUTHD_TEST_POLICY"

if ! run_root grep -Fq -- "$TRANSITION_RULE" "$LOCAL_POLICY" 2>/dev/null; then
    {
        printf '\n# BEGIN debian-user-config Copilot Podman transition\n'
        printf '%s\n' "$TRANSITION_RULE"
        printf '# END debian-user-config Copilot Podman transition\n'
    } | run_root tee -a "$LOCAL_POLICY" >/dev/null
fi

if ! run_root grep -Fq -- "$AUTHD_TEST_TRANSITION_RULE" "$LOCAL_POLICY" 2>/dev/null; then
    {
        printf '\n# BEGIN debian-user-config authd test profile transition\n'
        printf '%s\n' "$AUTHD_TEST_TRANSITION_RULE"
        printf '# END debian-user-config authd test profile transition\n'
    } | run_root tee -a "$LOCAL_POLICY" >/dev/null
fi

run_root apparmor_parser -r "$INSTALLED_POLICY"
run_root apparmor_parser -r "$INSTALLED_E2E_LIBVIRT_POLICY"
run_root apparmor_parser -r "$INSTALLED_AUTHD_TEST_POLICY"
run_root apparmor_parser -r "$BWRAP_POLICY"

echo "Installed the scoped Copilot Podman, E2E libvirt, and authd test AppArmor policies."
