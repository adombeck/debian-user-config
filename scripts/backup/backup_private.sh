#!/bin/bash

set -e
set -u
set -v

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

DIR=$(dirname "$(readlink -f "$0")")

# Unlock and mount backup_external
"${DIR}/unlock_and_mount_backup_external.sh"

# Unlock and mount private
if ! dmsetup info private; then
  cryptsetup luksOpen /home/user/private private
  mount /dev/mapper/private /media/private
fi

# Create a new borg backup
label="$(date +%Y-%m-%d)"
borg create --progress --stats "/media/backup_external/private_backup::${label}" /media/private

