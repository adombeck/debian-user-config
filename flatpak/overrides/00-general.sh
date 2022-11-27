#!/bin/bash

# First, disallow access to the filesystem
flatpak override --nofilesystem=host:reset

# Allow read-only access to the ~/flatpak-shared-ro directory
flatpak override --filesystem=~/flatpak-shared-ro:ro
