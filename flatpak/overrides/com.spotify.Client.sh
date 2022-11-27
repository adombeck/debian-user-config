#!/bin/bash

APP="com.spotify.Client"

# Reset previously applied app overrides
sudo flatpak override --reset "$APP"

# Allow read-only access to Picures and Music
sudo flatpak override --filesystem=xdg-pictures:ro --filesystem=xdg-music:ro "$APP"

