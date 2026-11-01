#!/bin/bash

set -eu

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$HOME/.local/bin"
for source in "$DIR"/*; do
    [[ "$(basename "$source")" == "install.sh" ]] && continue
    [[ -f "$source" && -x "$source" ]] || continue
    target="$HOME/.local/bin/$(basename "$source")"
    if [[ -L "$target" ]]; then
        rm "$target"
    elif [[ -e "$target" ]]; then
        echo "scripts: Skipping $target, already exists"
        continue
    fi
    echo "scripts: Creating symlink $target -> $source"
    ln -s "$source" "$target"
done

# The claude sandbox script needs a dedicated ssh-tpm-agent instance (unit files
# are symlinked into ~/.config/systemd/user by dotfiles/install.sh). The keys in
# ~/.config/claude-ssh must be generated separately per machine.
if command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1 \
    && [[ -e "$HOME/.config/systemd/user/ssh-tpm-agent-claude.socket" ]]; then
    systemctl --user daemon-reload
    systemctl --user enable --now ssh-tpm-agent-claude.socket
fi
