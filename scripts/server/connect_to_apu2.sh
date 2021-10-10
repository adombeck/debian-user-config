#!/bin/bash
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

source /home/user/server-scripts/start_keychain.sh
ssh -p 22012 user@ducknet.cc
