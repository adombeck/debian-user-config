#!/bin/bash

set -e
set -u
set -x

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

# Unlock and mount backup_external
if ! dmsetup info backup_external 2>/dev/null; then
  cat /etc/data_external.key | cryptsetup open --type tcrypt --veracrypt \
	  /dev/disk/by-id/usb-Seagate_Expansion_NA8KRRYV-0:0 backup_external
  mount /dev/mapper/backup_external /media/backup_external
fi

# Unlock and mount data_external
if ! dmsetup info data_external 2>/dev/null; then
  cat /etc/data_external.key | cryptsetup open --type tcrypt --veracrypt \
	  /dev/disk/by-id/usb-ATA_WDC_WD30EFRX-68E_0123456789ABCDE-0:0-part2 data_external
  mount /dev/mapper/data_external /media/data_external
fi

# Create a new borg backup
label="$(date +%Y-%m-%d)"
borg create --progress --stats "/media/backup_external/data_external_backup::${label}" /media/data_external

