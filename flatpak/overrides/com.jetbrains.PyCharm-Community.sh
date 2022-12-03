#!/bin/bash

set -eu
set -x

APP="com.jetbrains.PyCharm-Community"

# Reset previously applied app overrides
sudo flatpak override --reset "$APP"

# PyCharm doesn't support Wayland yet, see https://youtrack.jetbrains.com/issue/JBR-3206
sudo flatpak override --socket=fallback-x11 "$APP"

# Allow read-write access to the app data directory
sudo flatpak override --filesystem=$HOME/.var/app/com.jetbrains.PyCharm-Community "$APP"

# Allow read-write access to ~/projects and ~/git
sudo flatpak override --filesystem=$HOME/projects --filesystem=$HOME/git "$APP"

# Make PyCharm search the custom girepository-1.0 for typelibs for stub 
# generation.
# This assumes that you copied the girepository from the host:
#
#    cp -a /usr/lib/x86_64-linux-gnu/girepository-1.0 ~/flatpak-shared-ro/
#
sudo flatpak override --env=PYTHONPATH="$HOME/flatpak-shared-ro/girepository-1.0" "$APP"

# TODO: Generated via scripts/generate-gi-stubs.sh
sudo flatpak override --env=PYTHONPATH="$HOME/flatpak-shared-ro/gi-stubs" "$APP"

