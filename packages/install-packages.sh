#!/bin/bash

set -eu

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

packages="$(grep -v "^#" "$DIR/packages.list")"
echo "$packages" | xargs --open-tty sudo apt-get install

