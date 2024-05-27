#!/bin/bash

set -eu

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Install dotfiles
"$DIR/dotfiles/install.sh"

# Install systemd services
"$DIR/systemd/install.sh"

# Configure GNOME
"$DIR/gnome-config/install.sh"

# Configure guake terminal
"$DIR/guake/install.sh"

