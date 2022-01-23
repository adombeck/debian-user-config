#!/bin/bash

set -eu

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Install packages
"$DIR/packages/install-sources.sh"
"$DIR/packages/install-packages.sh"

# Install dotfiles
"$DIR/dotfiles/install.sh"

# Install and configure flatpaks
"$DIR/flatpak/install-flatpaks.sh"
"$DIR/flatpak/apply-overrides.sh"

# Configure GNOME
"$DIR/gnome-config/install.sh"

# Configure guake terminal
"$DIR/guake/install.sh"

