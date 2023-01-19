#!/bin/bash

set -e
set -u

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

maybe_create_symlink() {
  local source="${1}"
  local target="$HOME/$(realpath --relative-to="$DIR" "${source}")"
  echo "target: $target"

  if [[ "$f" == "$DIR/.gitmodules" ]] || [[ "${source}" == "$DIR/.nfs"* ]]; then
    echo "Skipping ${source}"
    return
  fi

  # If the target is a .d directory, create symlinks for the config
  # files in the directory, instead of for the directory itself.
  # This allows the user to still put their own config files in there
  # without committing them to to git.
  if [ -d "${source}" ] && [ "${source: -2}" = ".d" ]; then
    mkdir -p "${target}"
    for f in "${source}"/*; do
      maybe_create_symlink "$f"
    done
    return
  fi

  # Check if the dotfile is already present in the home directory
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
  ln -s "${source}" "${target}"
}

for f in "$DIR"/.[!.]*; do
  if [ "${f#"${DIR}/"}" = ".config" ]; then
    for c in .config/*; do
      maybe_create_symlink "$c"
    done
  else
    maybe_create_symlink "$f"
  fi
done

# Set zsh as the default shell
if [ "${SHELL}" != "/usr/bin/zsh" ]; then
  read -p "Do you want to set zsh as your default shell? (Y/n)"
  if [ "$REPLY" != "n" ]; then
    if sudo chsh $USER -s /usr/bin/zsh; then
      echo "Done. zsh will be your default shell the next time you log in."
    fi
  fi
fi
