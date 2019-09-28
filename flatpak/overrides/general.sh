#!/bin/bash

# First, remove all existing --user settings
flatpak override --user --reset

# Allow read-only access to the ~/flatpak-shared-ro directory
flatpak override --user --filesystem=~/flatpak-shared-ro:ro
