#!/bin/bash

set -eu

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

flatpak install --system flathub com.jetbrains.PyCharm-Community
flatpak install --system flathub com.spotify.Client

"${DIR}/apply-overrides.sh"
