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

# Create a new borg backup
LABEL=${LABEL:-$(date +%Y-%m-%d)}
borg create --patterns-from home-patterns.txt --progress --stats "/media/backup_external/home::${LABEL}" /home

