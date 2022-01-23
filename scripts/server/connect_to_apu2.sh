#!/bin/bash

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")

source "${SCRIPT_DIR}/start_keychain.sh"
ssh -p 22012 -i ~/.ssh/id_ed25519 user@ducknet.cc
