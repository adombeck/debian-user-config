#!/usr/bin/env bash

set -euo pipefail

echo "The Copilot E2E sudo policy is obsolete; rootless E2E no longer uses host sudo." >&2
echo "Install the scoped AppArmor profile with ./apparmor/install.sh." >&2
echo "Remove a previously installed policy with ./sudoers/uninstall.sh." >&2
exit 1
