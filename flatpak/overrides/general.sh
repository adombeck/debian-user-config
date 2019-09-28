#!/bin/bash

# First, remove all existing --user settings
flatpak override --user --reset

# Commented out because there is currently no use case
#flatpak override --user --filesystem=~/flatpak-shared-ro:ro
