#!/bin/bash

# First, remove all existing --user settings for com.jetbrains.PyCharm-Community
flatpak override --user --reset com.jetbrains.PyCharm-Community

# Don't allow access to /home
# flatpak override --user --nofilesystem=/home/ com.jetbrains.PyCharm-Community

# Make PyCharm search the custom girepository-1.0 for typelibs for stub 
# generation.
# This assumes that you copied the girepository from the host:
#
#    cp -a /usr/lib/x86_64-linux-gnu/girepository-1.0 ~/flatpak-shared-ro/
#
flatpak override --user --env=PYTHONPATH="$HOME/flatpak-shared-ro/girepository-1.0" com.jetbrains.PyCharm-Community
