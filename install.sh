#!/bin/bash

set -eu

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Install dotfiles
"$DIR/dotfiles/install.sh"

