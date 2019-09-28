#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"


# Install oh-my-zsh
if [ -d $HOME/.oh-my-zsh ]; then
	echo "oh-my-zsh already installed. skipping."
else
	$DIR/install-oh-my-zsh.sh
fi

# Install powerline-fonts for the agnoster theme
sudo apt install -y fonts-powerline

# Install guake terminal
$DIR/install-guake.sh

