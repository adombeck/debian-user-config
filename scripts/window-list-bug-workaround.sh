#!/bin/bash

# This is a workaround for an issue I experience with the window-list
# GNOME extension: Whenever I open a new window, it misses the icon
# in the window list. The workaround is to disable and re-enable
# the extension.

set -eu

EXTENSION_ID="window-list@gnome-shell-extensions.gcampax.github.com"
gnome-extensions disable "${EXTENSION_ID}"
gnome-extensions enable "${EXTENSION_ID}"
