#!/bin/sh

read -p "WARNING: This will install Debian unstable sources and upgrade packages to Debian unstable. Do you want to continue? (y/n)"

sudo apt install apt-transport-tor

if [ -f /etc/apt/sources.list ]; then
	sudo mv /etc/apt/sources.list /etc/apt/sources.list.orig
fi

sudo apt-get update && sudo apt-get dist-upgrade -y
