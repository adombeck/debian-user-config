#!/bin/bash

set -eu

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

for f in "$DIR"/overrides/*.sh; do
	echo "Executing $f"
	"$f"
done
