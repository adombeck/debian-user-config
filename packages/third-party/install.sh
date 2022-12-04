#!/bin/bash

set -eu

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

for subdir in $(ls "$DIR"); do
	"${DIR}/${subdir}/install.sh"
done
