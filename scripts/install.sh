#!/bin/bash

set -e
set -u

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

for f in "${DIR}"/*; do
	if [ "$(basename "$f")" == "$(basename "$0")" ]; then
		continue
	fi
	target="/usr/local/bin/$(realpath --no-symlinks --relative-to="${DIR}" "$f")"
	if [ -e "${target}" ]; then
		continue
	fi

	# Install the script
	sudo ln -s "$f" "${target}"
done

