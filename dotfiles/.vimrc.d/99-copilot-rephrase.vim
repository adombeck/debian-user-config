" Rephrase a range of lines with copilot-rephrase
command! -range Rephrase call Rephrase(<line1>, <line2>)
function! Rephrase(line1, line2)
  " Use whole buffer if no range given
  if a:line1 == a:line2 && a:line1 == line('.')
    let s = 1 | let e = line('$')
  else
    let s = a:line1 | let e = a:line2
  endif

  let g:rephrase = {'range':[s,e], 'win':win_getid(), 'buf':bufnr('%')}
  let input = join(getline(s, e), "\n")

  " Capture stdout; redirect stderr to a temp file
  let errfile = tempname()
  let cmd = 'copilot-rephrase 2>' . shellescape(errfile)
  let out_lines = systemlist(cmd, input)

  " If there were stderr messages, append them commented
  if filereadable(errfile) && getfsize(errfile) > 0
    let errs = readfile(errfile)
    if len(errs) > 0
      call extend(out_lines, [''])
      call extend(out_lines, map(errs, {_,v -> '# ' . v}))
    endif
  endif
  call delete(errfile)

  " Open split with combined stdout + stderr
  silent! vsplit | enew
  silent! file [Rephrase Output]
  call setline(1, out_lines)
  let g:rephrase.output_win = win_getid()
  let g:rephrase.output_buf = bufnr('%')

  setlocal buftype=nofile bufhidden=wipe nobuflisted noswapfile readonly nomodifiable
  redraw!

  echomsg "Rephrased output ready. Use :RO or :CO."
endfunction

" Alias for Rephrase
command! -range R call Rephrase(<line1>, <line2>)
