#!/bin/bash

set -eu

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

mkdir -p "$HOME/.copilot/extensions"

for ext_dir in "$DIR/extensions"/*/; do
    ext_name=$(basename "$ext_dir")
    target="$HOME/.copilot/extensions/$ext_name"

    if [ -L "$target" ]; then
        rm "$target"
    elif [ -e "$target" ]; then
        echo >&2 "Moving existing $target to $target.orig"
        mv "$target" "$target.orig"
    fi

    ln -s "$ext_dir" "$target"
    echo >&2 "Installed Copilot extension: $ext_name"
done
