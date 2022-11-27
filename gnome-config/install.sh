#!/bin/bash

set -eu

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Install gnome-shell extensions
make -C "${DIR}/extensions/gnome-clipboard-history" bundle
gnome-extensions install --force "${DIR}/extensions/gnome-clipboard-history/bundle.zip"

# Load the GNOME config
dconf load /org/gnome/ < "$DIR/gnome.dconf"

# Enable udisks TCRYPT support
sudo touch /etc/udisks2/tcrypt.conf

