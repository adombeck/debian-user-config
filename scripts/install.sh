#!/bin/bash

set -eu

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$HOME/.local/bin"
for source in "$DIR"/*; do
    [[ "$(basename "$source")" == "install.sh" ]] && continue
    target="$HOME/.local/bin/$(basename "$source")"
    if [[ -L "$target" ]]; then
        rm "$target"
    elif [[ -e "$target" ]]; then
        echo "scripts: Skipping $target, already exists"
        continue
    fi
    echo "scripts: Creating symlink $target -> $source"
    ln -s "$source" "$target"
done
