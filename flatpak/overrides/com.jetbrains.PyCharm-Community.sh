#!/bin/bash

set -eu

APP="com.jetbrains.PyCharm-Community"

# First, remove all existing --user settings for the app
flatpak override --user --reset "$APP"

# Don't allow access to $HOME
# flatpak override --user --nofilesystem=home "$APP"

# Make PyCharm search the custom girepository-1.0 for typelibs for stub 
# generation.
# This assumes that you copied the girepository from the host:
#
#    cp -a /usr/lib/x86_64-linux-gnu/girepository-1.0 ~/flatpak-shared-ro/
#
flatpak override --user --env=PYTHONPATH="$HOME/flatpak-shared-ro/girepository-1.0" "$APP"
