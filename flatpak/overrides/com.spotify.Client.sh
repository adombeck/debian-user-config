#!/bin/bash

APP="com.spotify.Client"

# Allow read-only access to Picures and Music
flatpak override --user --filesystem=xdg-pictures:ro --filesystem=xdg-music:ro "$APP"

