#!/bin/bash

set -eu

for f in overrides/*.sh; do
	echo "Executing ./$f"
	"./$f"
done
