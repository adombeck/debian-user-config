#!/bin/bash

set -eu

for p in patches/*; do
    sudo patch --forward --dir / -p1 < "$p" || true
done
