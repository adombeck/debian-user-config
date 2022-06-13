#!/bin/bash

set -euo pipefail
set -x

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

if ! dmsetup info backup_external 2>/dev/null; then
  cat /etc/data_external.key | cryptsetup open --type tcrypt --veracrypt \
	  /dev/disk/by-id/usb-Seagate_Expansion_NA8KRRYV-0:0 backup_external
  mount /dev/mapper/backup_external /media/backup_external
fi

