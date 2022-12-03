#!/bin/bash

set -euo pipefail

# Based on https://github.com/pygobject/pygobject-stubs/issues/5#issuecomment-639541725

GI_REPO_PATH="${1:-/usr/lib/x86_64-linux-gnu/girepository-1.0/}"
export PYTHONPATH=/var/lib/flatpak/app/com.jetbrains.PyCharm-Community/current/active/files/pycharm/plugins/python-ce/helpers
for typelib in $(ls -1 "${GI_REPO_PATH}"); do
        echo "generating ${typelib%-*}"
        python3 -m generator3 -d /tmp/out -p "gi.repository.${typelib%-*}" "${GI_REPO_PATH}/${typelib}"
done

mv /tmp/out/gi /tmp/out/gi-stubs

echo "Now move /tmp/out/gi-stubs to some site-packages directory where 
the Python interpreter configured in PyCharm can find it, for example
/var/lib/flatpak/app/com.jetbrains.PyCharm-Community/current/active/files/lib/python3.8/site-packages/gi-stubs"

