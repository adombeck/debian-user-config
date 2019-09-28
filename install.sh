#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Install powerline-fonts for the agnoster theme
sudo apt install -y fonts-powerline

# Install guake terminal
$DIR/install-guake.sh

