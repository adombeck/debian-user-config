#!/bin/bash

set -e
set -u

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

for f in "$DIR"/.[!.]*; do
	if [[ "$f" == "$DIR/.gitmodules" ]] || [[ "$f" == "$DIR/.nfs"* ]]; then
		echo "Skipping $f"
		continue
	fi

    # Check if the dotfile is already present in the home directory
    target="$HOME/$(basename "$f")"
    if [ -L "${target}" ]; then
        # The file is a symlink, so it's probably safe to just delete it.
		echo "Updating symlink for $f"
        rm "${target}"
	    ln -s "$f" "$HOME"
		continue
    fi

    if [ -f "${target}" ]; then
		echo -e "The file ${target} already exists.\nDo you want to move the file to ${target}.orig? Else it will be skipped. (y/N) "
		read
		if [ "$REPLY" != "y" ]; then
		    echo "Skipping $f"
            continue
        else
            mv -i "${target}" "${target}.orig"
        fi
    fi

	echo "Creating symlink for $f"
	ln -s "$f" "$HOME"
done

