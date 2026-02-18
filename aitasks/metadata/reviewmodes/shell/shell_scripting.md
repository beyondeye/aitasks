---
name: Shell Scripting
description: Check variable quoting, error handling, portability, and shellcheck patterns
environment: [bash, shell]
reviewtype: conventions
reviewlabels: [quoting, portability, shellcheck, error-handling]
---

## Review Instructions

### Variable Safety
- Flag unquoted variable expansions — always use `"$var"` instead of `$var` to prevent word splitting and globbing (SC2086)
- Check for `set -euo pipefail` (or equivalent) near the top of scripts — missing this means errors are silently ignored
- Look for uninitialized variables used without defaults — use `"${var:-default}"` or `"${var:?error message}"`
- Flag unquoted command substitutions — use `"$(command)"` instead of `$(command)` (SC2046)
- Check for variables used in arithmetic that could be empty — `$(( $count + 1 ))` fails if `$count` is unset
- Look for `eval` usage — almost always avoidable and a security risk with user-controlled input

### Error Handling
- Flag missing error checks after critical commands (file operations, network calls, directory changes)
- Check for `cd` without error handling — `cd /some/dir || exit 1` prevents operating in the wrong directory
- Look for missing `trap` for cleanup on exit — temporary files, lock files, and processes should be cleaned up
- Flag piped commands where only the last exit code is checked — use `set -o pipefail` or check `${PIPESTATUS[@]}`
- Check for `rm -rf` with variable paths — if the variable is empty, this could delete from the wrong location
- Look for missing `|| true` on commands that are expected to fail sometimes (e.g., `grep` returning no matches)

### Portability
- Flag bashisms in scripts with `#!/bin/sh` shebang: `[[ ]]`, `source`, arrays, `{a,b}` brace expansion, `$'string'`, `function` keyword
- Check for GNU-specific flags used without fallback (e.g., `sed -i` behaves differently on macOS vs Linux)
- Look for reliance on non-POSIX tools without checking availability (`readlink -f` not available on macOS, use `realpath` or a function)
- Flag `echo -e` for escape sequences — use `printf` instead (more portable)
- Check that scripts specify the intended shell in the shebang (`#!/usr/bin/env bash` for bash scripts, `#!/bin/sh` for POSIX)

### ShellCheck Patterns
- SC2086: Double quote to prevent globbing and word splitting — `"$var"` instead of `$var`
- SC2046: Quote command substitution — `"$(cmd)"` instead of `$(cmd)`
- SC2034: Variable appears unused — remove or export it, or prefix with `_` if intentionally unused
- SC2155: Declare and assign separately — `local var; var=$(cmd)` instead of `local var=$(cmd)` (exit code lost)
- SC2164: Use `cd ... || exit` in case cd fails
- SC2012: Use `find` or glob instead of `ls` to iterate files (ls output parsing is fragile)
- SC2129: Use `{ cmd1; cmd2; } >> file` instead of repeated `>> file` redirections
- SC2162: Use `read -r` to prevent backslash interpretation
