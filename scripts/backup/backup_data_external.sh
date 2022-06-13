#!/bin/bash

set -e
set -u
set -x

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

DIR=$(dirname "$(readlink -f "$0")")

# Unlock and mount backup_external
"${DIR}/unlock_and_mount_backup_external.sh"

# Unlock and mount data_external
"${DIR}/unlock_and_mount_data_external.sh"

# Create a new borg backup
label="$(date +%Y-%m-%d)"
borg create --progress --stats "/media/backup_external/data_external_backup::${label}" /media/data_external

