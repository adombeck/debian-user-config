#!/bin/sh

set -e
set -u

if [ "${1:-}" = "--enable" ]; then
	STATUS="disabled"
else
	STATUS="enabled"
fi

for code in XHC EHC1 EHC2 USB1 USB2; do
	if grep "${code}" /proc/acpi/wakeup | grep -q "${STATUS}"; then
		sudo /bin/sh -c "echo "${code}" > /proc/acpi/wakeup"
	fi
done

