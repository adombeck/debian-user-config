#!/bin/bash

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

sudo apt-get install -y guake

echo "Loading guake config"
dconf load /apps/guake/ < "$DIR/guake.dconf"

echo "Adding keybinding to toggle Guake via F10"
set-gnome-keybinding.py "Toggle Guake" "guake --toggle" "F10"
