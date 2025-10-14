" Generate a commit message using copilot-commit-msg
command! CommitMsg call CommitMsg()

function! CommitMsg()
  " Store basic context
  let g:commitmsg = {'win': win_getid(), 'buf': bufnr('%')}

  " Find the line matching the marker
  let marker = '# Everything below it will be ignored.'
  let lnum = search('^' . escape(marker, '#') . '$', 'n')
  if lnum > 0 && lnum < line('$')
    let input = join(getline(lnum + 1, line('$')), "\n")
  else
    let input = ''
  endif

  " Capture stdout; redirect stderr to temp file
  let errfile = tempname()
  let cmd = 'copilot-commit-msg 2>' . shellescape(errfile)
  let out_lines = systemlist(cmd, input)

  " If stderr present, append as comments
  if filereadable(errfile) && getfsize(errfile) > 0
    let errs = readfile(errfile)
    if len(errs) > 0
      call extend(out_lines, [''])
      call extend(out_lines, map(errs, {_,v -> '# ' . v}))
    endif
  endif
  call delete(errfile)

  " Open a split with combined stdout + stderr
  silent! vsplit | enew
  silent! file [CommitMsg Output]
  call setline(1, out_lines)
  let g:commitmsg.output_win = win_getid()
  let g:commitmsg.output_buf = bufnr('%')

  " Make buffer temporary and readonly
  setlocal buftype=nofile bufhidden=wipe nobuflisted noswapfile readonly nomodifiable
  redraw!

  echomsg "Commit message generated. Use :RO or :CO if you want to apply it."
endfunction

" Alias for CommitMsg
command! CM call CommitMsg()
