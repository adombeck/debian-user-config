#!/bin/bash

set -eu

APP="com.jetbrains.PyCharm-Community"

# Make PyCharm search the custom girepository-1.0 for typelibs for stub 
# generation.
# This assumes that you copied the girepository from the host:
#
#    cp -a /usr/lib/x86_64-linux-gnu/girepository-1.0 ~/flatpak-shared-ro/
#
flatpak override --user --env=PYTHONPATH="$HOME/flatpak-shared-ro/girepository-1.0" "$APP"

# Allow read-write access to ~/projects and ~/git
flatpak override --user --filesystem=/home/user/projects --filesystem=/home/user/git "$APP"

