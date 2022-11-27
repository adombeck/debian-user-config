#!/bin/bash

# Reset previously applied global overrides
sudo flatpak override --reset

# Disallow access to the filesystem
sudo flatpak override --nofilesystem=host:reset

# Disallow access to devices
sudo flatpak override --nodevice=all

# Disallow access to sockets (except for wayland)
sudo flatpak override --nosocket=x11 --nosocket=fallback-x11 --nosocket=pulseaudio --nosocket=system-bus --nosocket=session-bus --nosocket=ssh-auth --nosocket=pcsc --nosocket=cups --nosocket=gpg-agent

# Allow read-only access to the ~/flatpak-shared-ro directory
sudo flatpak override --filesystem=~/flatpak-shared-ro:ro
