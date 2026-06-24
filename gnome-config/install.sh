#!/bin/bash

set -eu

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Install gnome-shell extensions
if [ ! -e "${DIR}/extensions/gnome-clipboard-history/bundle.zip" ]; then
    make -C "${DIR}/extensions/gnome-clipboard-history" bundle
fi
gnome-extensions install --force "${DIR}/extensions/gnome-clipboard-history/bundle.zip"

(cd "${DIR}/extensions/activate-window-by-title" && zip -q /tmp/activate-window-by-title.zip extension.js metadata.json LICENSE)
gnome-extensions install --force /tmp/activate-window-by-title.zip
rm /tmp/activate-window-by-title.zip


# Load the GNOME config
dconf load /org/gnome/ < "$DIR/gnome.dconf"

# Enable udisks TCRYPT support
sudo touch /etc/udisks2/tcrypt.conf

