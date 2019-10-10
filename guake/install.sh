#!/bin/bash

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

sudo apt-get install -y guake

echo "Loading guake config"
dconf load / < "$DIR/guake.dconf"

