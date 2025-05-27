#!/bin/bash

set -e
set -u
set -x

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

maybe_create_symlink() {
  local source="${1}"
  local target
  target="$HOME/$(realpath --no-symlinks --relative-to="$DIR" "${source}")"
  echo >&2 "target: $target"

  # Check if the dotfile is already present in the home directory
  if [ -L "${target}" ]; then
    # The file is a symlink, so it's probably safe to just delete it.
    echo >&2 "Updating symlink for ${source}"
    rm "${target}"
    ln -s "${source}" "${target}"
    return
  fi

  if [ -e "${target}" ]; then
    echo >&2 -e "The file ${target} already exists.\nDo you want to move the file to ${target}.orig? Else it will be skipped. (y/N) "
    read
    if [ "$REPLY" != "y" ]; then
      echo >&2 "Skipping ${source}"
      return
    else
      mv -i "${target}" "${target}.orig"
    fi
  fi

  echo >&2 "Creating symlink for ${source}"
  mkdir -p "$(dirname "${target}")"
  ln -s "${source}" "${target}"
}

for f in "$DIR"/.[!.]*; do
  if [ "${f#"${DIR}/"}" = ".gitmodules" ] || [[ "${f}" == "$DIR/.nfs"* ]]; then
    echo "Skipping ${f}"
    return
  fi

  name=$(basename "$f")
  if [ -d "${f}" ] && { [ "$name" = ".config" ] || [ "$name" = ".var" ] || [[ "$name" == *".d" ]]; }; then
    # For .d directories and the ".config" and ".var" directories, create
    # symlinks for all files in the directory, instead of the directory itself.
    # This allows the user to still put their own config files in there without
    # committing them to to git.
    while IFS= read -u3 -r -d '' c; do
      maybe_create_symlink "$c"
    done 3< <(find "${f}" -type f -o -type l -print0)
  else
    # For all other files and directories, just symlink the file or directory
    # itself.
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
