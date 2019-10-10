#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

dconf load /org/gnome/ < "$DIR/gnome.dconf"

# Enable udisks TCRYPT support
sudo touch /etc/udisks2/tcrypt.conf

