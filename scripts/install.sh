#!/bin/bash

set -e
set -u

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

function install() {
  local dir=$1
  for f in "$dir"/*; do
    # Don't copy this script itself
    if [ "$(basename "$f")" == "$(basename "$0")" ]; then
      continue
    fi

    # Recurse into directories
    if [ -d "$f" ]; then
      install "$f"
      continue
    fi

    # Install regular files to /usr/local/bin
    local target
    target="/usr/local/bin/$(basename "$f")"
    if [ -e "${target}" ]; then
      # Don't overwrite existing files
      echo "scripts: Skipping $target, already exists"
      continue
    fi

    # Install the script
    echo "scripts: Creating symlink $target -> $f"
    sudo ln -s "$f" "${target}"
  done
}

install "${DIR}"

# Add shortcut for the window-list workaround
"${DIR}/set-gnome-keybinding.py" "Reload window-list extension" "window-list-bug-workaround.sh" "<Ctrl><Shift>W"
