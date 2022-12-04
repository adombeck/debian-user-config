#!/bin/bash

set -eu
set -x

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

APP="org.chromium.Chromium"

# Reset previously applied app overrides
sudo flatpak override --reset "$APP"

# Allow read-write access to the app data directory
sudo flatpak override --filesystem="$HOME/.var/app/$APP" "$APP"

# Allow access to PulseAudio to be able to play sound
sudo flatpak override --socket=pulseaudio "$APP"

# Allow access to ~/.local/share/applications and ~/.local/share/icons in
# a modified home directory to be able to install PWAs.
# The created files must be copied manually to the actual applications
# and icons directories to be able to use the PWA.
CHROMIUM_HOME=$(realpath "$DIR/../org.chromium.Chromium")
mkdir -p "${CHROMIUM_HOME}/.local/share/applications" "${CHROMIUM_HOME}/.local/share/icons"
sudo flatpak override --env=HOME="$CHROMIUM_HOME" "$APP"
sudo flatpak override --filesystem="$CHROMIUM_HOME/.local/share/applications:rw" "$APP"
sudo flatpak override --filesystem="$CHROMIUM_HOME/.local/share/icons:rw" "$APP"
