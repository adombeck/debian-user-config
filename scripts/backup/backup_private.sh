#!/bin/bash

set -e
set -u
set -v

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi


# Unlock and mount backup_external
if ! dmsetup info backup_external; then
  cryptsetup open --type tcrypt --veracrypt /dev/disk/by-id/usb-Seagate_Expansion_NA8KRRYV-0:0 backup_external
  mount /dev/mapper/backup_external /media/backup_external
fi

# Unlock and mount private
if ! dmsetup info private; then
  cryptsetup luksOpen /home/user/private private
  mount /dev/mapper/private /media/private
fi

# Create a new borg backup
label="$(date +%Y-%m-%d)"
borg create --progress --stats "/media/backup_external/private_backup::${label}" /media/private

