export ZSH=~/.zsh

export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8

# Required to set PATHs for snap
emulate sh -c 'source /etc/profile'

# Add user specific PATHs
emulate sh -c 'source ~/.profile'

ZSH_THEME="agnoster"

plugins=(bgnotify)

source $ZSH/oh-my-zsh.sh

if [ -d ~/.zshrc.d ]; then
    for f in ~/.zshrc.d/*(N); do
        source "$f"
    done
fi

# Extend Autocomplete Search Path
fpath=($HOME/.zsh/lib/completions $fpath)

# Load and run compinit
autoload -U compinit
compinit -i

# Go Path related exports
export GOPATH=~/go
export PATH=$PATH:$GOPATH/bin

# Hide user@host from prompt
DEFAULT_USER=$USER
prompt_context(){}

# Make Ctrl-d close the shell
unsetopt ignoreeof

# Fix space being removed after tab completion
ZLE_SPACE_SUFFIX_CHARS=$'|&'

# Keep background processes running when closing terminal
setopt NO_HUP
setopt NO_CHECK_JOBS

# Disable Software Flow Control which causes terminal to hang on C-s (at least in vim)
stty -ixon

# Disable beep
unsetopt BEEP

# Share history betweeh zsh shells
setopt share_history

# Set the EDITOR variable to vim
export EDITOR=vim

# Disable paste magic
DISABLE_MAGIC_FUNCTIONS=1

# Set a high history size
HISTSIZE=500000
SAVEHIST=100000

# Enable thefuck
eval $(thefuck --alias)

# Enable fzf shell extensions
source /usr/share/doc/fzf/examples/completion.zsh
source /usr/share/doc/fzf/examples/key-bindings.zsh
bindkey '^F' fzf-file-widget
export FZF_DEFAULT_COMMAND='fdfind --type f --hidden --follow --exclude .git'
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"

# To be able to execute shell history via enter and copy it to the
# command-line on left/right arrow key. Only works in combination
# with my 0001-execute-history-by-default patch.
FZF_CTRL_R_OPTS="--expect=left --expect=right"
