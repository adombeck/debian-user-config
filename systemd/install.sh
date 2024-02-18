#!/bin/bash

set -e
set -u

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"


maybe_create_symlink() {
  local source="${1}"
  local target="${2}"
  echo "target: $target"

  # Check if the target already exists
  if [ -L "${target}" ]; then
    # The file is a symlink, so it's probably safe to just delete it.
    echo "Updating symlink for ${source}"
    rm "${target}"
    ln -s "${source}" "${target}"
    return
  fi

  if [ -e "${target}" ]; then
    echo -e "The file ${target} already exists.\nDo you want to move the file to ${target}.orig? Else it will be skipped. (y/N) "
    read
    if [ "$REPLY" != "y" ]; then
      echo "Skipping ${source}"
      return
    else
      mv -i "${target}" "${target}.orig"
    fi
  fi

  echo "Creating symlink for ${source}"
  mkdir -p "$(dirname "${target}")"
  ln -s "${source}" "${target}"
}

for f in "${DIR}"/*; do
    if [ "$(basename "$f")" == "$(basename "$0")" ]; then
        continue
    fi
    if [ "$(basename "$f")" == "units-to-enable" ]; then
        continue
    fi

    target="${HOME}/.config/systemd/user/$(realpath --relative-to="${DIR}" "$f")"
    maybe_create_symlink "$f" "${target}"

    case  "$f" in 
        *.service) systemctl --user enable "$f"
    esac
done

# Enable the units listed in the units-to-enable file
if [ -f "${DIR}/units-to-enable" ]; then
  while read -r unit; do
    systemctl --user enable "${unit}"
  done < "${DIR}/units-to-enable"
fi
