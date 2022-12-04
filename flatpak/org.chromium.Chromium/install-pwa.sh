#!/bin/bash

set -eu

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

for app in "$DIR/.local/share/applications/"*; do
	echo "Installing $HOME/.local/share/applications/$(basename "$app")"
	cat "$app"
	echo
	cp "$app" "$HOME/.local/share/applications"
done

cp -a "$DIR/.local/share/icons/"* ~/.local/share/icons
