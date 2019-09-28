#!/bin/bash

cat << EOF
WARNING: This script will:
 * install Debian unstable sources
 * upgrade all packages to Debian unstable
Do you want to continue? (y/N)
EOF

read
if [ "$REPLY" != "y" ]; then
	exit 1
fi

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

sudo apt install apt-transport-tor

if [ -f /etc/apt/sources.list ]; then
	sudo mv -i /etc/apt/sources.list /etc/apt/sources.list.orig
fi

cp "$DIR/sources.list" /etc/apt/sources.list

sudo apt-get update && sudo apt-get dist-upgrade -y

