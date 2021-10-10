#!/bin/bash

eval $(ssh-agent)
/usr/bin/keychain $HOME/.ssh/id_{ed25519,rsa}
source $HOME/.keychain/`hostname`-sh
