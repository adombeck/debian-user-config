#!/bin/bash

set -euo pipefail
set -x

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

# Unlock and mount data_external
if ! dmsetup info data_external 2>/dev/null; then
  cat /etc/data_external.key | cryptsetup open --type tcrypt --veracrypt \
	  /dev/disk/by-id/usb-ATA_WDC_WD30EFRX-68E_0123456789ABCDE-0:0-part2 data_external
  mount /dev/mapper/data_external /media/data_external
fi

