set nocompatible

" Initialize Pathogen
" runtime bundle/vim-pathogen/autoload/pathogen.vim
" execute pathogen#infect()

" Enable syntax highlighting
syntax on
filetype plugin indent on

" Colorscheme see https://github.com/hukl/Smyck-Color-Scheme
color smyck

" Add line numbers
set number
set ruler
set cursorline

" Disable Backup and Swap files
set noswapfile
set nobackup
set nowritebackup

" Set encoding
set encoding=utf-8

" Whitespace stuff
set nowrap
set tabstop=4
set shiftwidth=4
set softtabstop=4
set expandtab

" Show trailing spaces and highlight hard tabs
set list listchars=tab:»·,trail:·

" allow backspacing over everything in insert mode
set backspace=indent,eol,start

" Strip trailing whitespaces on each save
" fun! <SID>StripTrailingWhitespaces()
"     let l = line(".")
"     let c = col(".")
"     %s/\s\+$//e
"     call cursor(l, c)
" endfun
" autocmd BufWritePre * :call <SID>StripTrailingWhitespaces()

" Close window if last remaining window is NerdTree
autocmd bufenter * if (winnr("$") == 1 && exists("b:NERDTree") && b:NERDTree.isTabTree()) | q | endif

" Search related settings
set incsearch
set hlsearch

" Map Ctrl+l to clear highlighted searches
nnoremap <silent> <C-l> :<C-u>nohlsearch<CR><C-l>

" Highlight characters behind the 80 chars margin
:au BufWinEnter * let w:m2=matchadd('ColumnMargin', '\%>80v.\+', -1)

" Disable code folding
set nofoldenable

" NERDTree configuration
let NERDTreeIgnore=['\.pyc$', '\.rbc$', '\~$']
map <Leader>n :NERDTreeToggle<CR>

" Enable Syntastic
let g:syntastic_check_on_open=1
let g:syntastic_go_checkers = ['go']
let g:syntastic_javascript_checkers=['eslint']

" Use dedicated syntax checkers for these languages
let g:syntastic_mode_map = {
    \ "mode": "active",
    \ "passive_filetypes": ["erlang"] }

" Ignorde JS files on CTAGS generation
let g:vim_tags_ignore_files = ['.gitignore', '.svnignore', '.cvsignore', '*.js', '*.json', '*.css']

" make uses real tabs
au FileType make set noexpandtab

" use real tabs in shell scripts
au FileType sh set noexpandtab

" Ruby uses 2 spaces
au FileType ruby set softtabstop=2 tabstop=2 shiftwidth=2

" Go uses tabs
au FileType go set noexpandtab tabstop=4 shiftwidth=4

" Go Foo
let g:go_fmt_command = "goimports"

" Thorfile, Rakefile, Vagrantfile and Gemfile are Ruby
au BufRead,BufNewFile {Gemfile,Rakefile,Vagrantfile,Thorfile,config.ru}    set ft=ruby

" add json syntax highlighting
au BufNewFile,BufRead *.json set ft=javascript

" make Python follow PEP8 ( http://www.python.org/dev/peps/pep-0008/ )
au FileType python set softtabstop=4 tabstop=4 shiftwidth=4 textwidth=79

" ctrp custom ignores
let g:ctrlp_custom_ignore = {
  \ 'dir':  '\.git$\|\.hg$\|\.svn$\|\.eunit$',
  \ 'file': '\.exe$\|\.so$\|\.dll\|\.beam$\|\.DS_Store$'
  \ }


" Use Ag instead of Ack
let g:ackprg = 'ag --nogroup --nocolor --column'

" Gitgutter
let g:gitgutter_sign_column_always = 1
set updatetime=250

" Enable spell checking in git commit messages
autocmd Filetype gitcommit setlocal spell
