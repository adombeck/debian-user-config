#!/bin/bash

flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

flatpak install flathub com.jetbrains.PyCharm-Community
flatpak install flathub com.spotify.Client
