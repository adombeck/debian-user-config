#!/bin/bash

APP="com.spotify.Client"

# First, remove all existing --user settings for the app
flatpak override --user --reset "$APP"

# Don't allow access to $HOME
flatpak override --user --nofilesystem=home "$APP"

