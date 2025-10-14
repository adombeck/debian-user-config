" Shared Copilot output utilities

" Replace or copy from the output buffer, then close it
command! RO call s:UseOutputBuffer('replace')
command! CO call s:UseOutputBuffer('copy')

function! s:UseOutputBuffer(action)
  " Prefer rephrase context, fallback to commitmsg context
  let l:info = get(g:, 'ai_rephrase_ctx', {})
  if empty(l:info)
    let l:info = get(g:, 'ai_commitmsg_ctx', {})
  endif
  if type(l:info) != type({}) || empty(l:info)
    echoerr "No output buffer found"
    return
  endif

  let l:out_buf = get(l:info, 'output_buf', -1)
  if l:out_buf == -1 || !bufexists(l:out_buf)
    echoerr "No output buffer found"
    return
  endif

  " Get only non-comment lines (skip stderr)
  let l:lines = filter(getbufline(l:out_buf, 1, '$'), {_,v -> v !~ '^# ' && v !~ '^$'})

  " Jump to original buffer/window
  if has_key(l:info,'win') | call win_gotoid(l:info.win) | endif
  if bufnr('%') != get(l:info,'buf',-1) | execute 'buffer!' l:info.buf | endif

  " Replace or copy lines"
  let [l:s, l:e] = l:info.range
  if a:action ==# 'replace'
    execute l:s . ',' . l:e . 'delete _'
    call append(l:s - 1, l:lines)
    echo printf('Replaced lines %d–%d (stderr ignored).', l:s, l:e)
  elseif a:action ==# 'copy'
    call append(0, l:lines)
    echo 'Prepended rephrased output (stderr ignored).'
  endif

  " Close output buffer/window
  if has_key(l:info,'output_win') && win_gotoid(l:info.output_win)
    close
  endif
  if bufexists(l:out_buf)
    execute 'bdelete!' l:out_buf
  endif

  if has_key(l:info,'win') | call win_gotoid(l:info.win) | endif
endfunction
