#!/bin/bash

set -e
set -u

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

for f in "${DIR}"/*; do
    if [ "$(basename "$f")" == "$(basename "$0")" ]; then
        continue
    fi
    target="${HOME}/.config/systemd/user/$(realpath --relative-to="${DIR}" "$f")"
    if [ -e "${target}" ]; then
        continue
    fi

    # Install the unit file
	mkdir -p "$(dirname "${target}")"
    ln -s "$f" "${target}"

    case  "$f" in 
        *.service) systemctl --user enable "$f"
    esac
done

