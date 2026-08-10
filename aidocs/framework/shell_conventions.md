# Shell Conventions

General shell style for the aitasks framework's bash scripts. Read this when
writing or editing any shell script under `.aitask-scripts/`. Shell-specific
portability quirks (BSD vs GNU tooling) live in
`aidocs/framework/sed_macos_issues.md`; language-agnostic code style lives in
`aidocs/framework/code_conventions.md`.

- **Shebang:** Always `#!/usr/bin/env bash`, never `#!/bin/bash`. macOS system
  bash is 3.2; `env bash` picks up brew-installed bash 5.x from PATH.
- All scripts use `set -euo pipefail`.
- **Beware silent `set -e` aborts via `"$(...)"` capture.** A helper that does
  `warn "..."; return 1` looks loud, but when a caller runs
  `out="$(helper)" || return`, the warning is captured into `$out` (never shown)
  and the non-zero status propagates — under `set -e` the whole script exits
  with no visible error. Emit such diagnostics to **stderr** (`warn "..." >&2`)
  so they survive command substitution, and make best-effort callers non-fatal
  (`|| return 0` / `|| true`) so a recoverable failure degrades to a no-op
  instead of killing the run. (This was the root cause of a silent `ait setup`
  abort; see `aidocs/framework/sed_macos_issues.md` "Files Fixed in t931".)
- **A bare `return` inherits the previous command's status.** In an `else`
  branch that status is the just-failed condition's `1`, so an "early return,
  nothing to do" reads as a failure and — under `set -euo pipefail` — kills any
  unguarded caller with no message at all. Write `return 0` whenever the branch
  means *success* or *a non-fatal no-op*, especially when the preceding command
  is a conditional that can fail. A bare `return` is correct only where you
  **intend** to forward the previous command's status to the caller; say so in a
  comment when you do. (`install.sh:895` aborted the whole installer this way
  after a successful download, leaving the target directory empty; see t1414.)
- Error helpers: `die()` (fatal), `warn()`, `info()` from `terminal_compat.sh`.
- Guard against double-sourcing with `_AIT_*_LOADED` variables.
- Platform detection: `detect_platform()` returns `github|gitlab|bitbucket`
  from git remote URL.
- Task/plan resolution functions live in `task_utils.sh`.
- **Platform-specific CLIs (gh/glab/bitbucket):** encapsulate in bash scripts
  that route via `detect_platform()`. `SKILL.md` must call a script
  subcommand, never `gh`, `glab`, or the Bitbucket API directly.
- **Archive format details (tar.gz/tar.zst/zstd):** encapsulate in bash
  scripts. `SKILL.md` must call a script subcommand — never raw archive
  tooling. Format migrations then happen in one place.
- Use `sed_inplace()` from `terminal_compat.sh` — never `sed -i`.
- **Replacing a file in place: use `lib/atomic_write.sh`, never `> "$file"` or a
  `mv` from `$TMPDIR`.** `> "$file"` truncates before any bytes are written, so
  a concurrent reader sees the file empty or half-written; a `mv` whose temp
  lives in `$TMPDIR` degrades into a non-atomic copy whenever `$TMPDIR` is on a
  different filesystem. The helper stages a dot-prefixed temp beside the
  *resolved* target and renames it in:
  ```bash
  source "$SCRIPT_DIR/lib/atomic_write.sh"

  _my_body() { build_header || return 1; cat "$src" || return 1; }
  ait_atomic_render "$dest" _my_body || die "could not write $dest"

  ait_atomic_write_text "$dest" "$content"   # when you already hold the text
  ```
  **Renderers must not rely on `set -e`.** Bash disables errexit inside a
  function whose exit status is being tested, so a mid-renderer failure followed
  by a successful command commits a partial file — guard every fallible command
  with `|| return 1`. A pure `echo`/`printf` sequence needs no guards; anything
  that can fail on its own (`awk`, a helper function, a `[[ … ]] && echo` as the
  *last* line) does. The full contract is documented at the top of
  `lib/atomic_write.sh`; `lib/atomic_write.py` is the Python sibling.
- **System libs added to `./ait`'s source-on-startup chain must also be added
  to `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` in the same PR.**
  43 tests scaffold a fake `.aitask-scripts/lib/` via that helper; a missing
  entry crashes every one of them with `No such file or directory` the next
  time `./ait` (or a helper that learns to source the new lib) is invoked
  from the fake repo. Current baseline: `aitask_path.sh`, `terminal_compat.sh`,
  `tmux_exec.sh`, `python_resolve.sh`, `yaml_utils.sh`, `atomic_write.sh`,
  `atomic_write.py`, `cross_repo_reexec.sh`, `followup_kinds_sh.sh`,
  `followup_kinds.py`. A lib with a runtime sibling in another language (the
  bridge pattern — `followup_kinds_sh.sh` shells out to `followup_kinds.py`)
  must have **both** copied, or it fails closed inside every scaffolded test.
- **Avoid `claude -p` / `claude --print` (headless print mode) in scripts and
  skills.** Claude Code bills headless print mode at a higher per-token rate
  than interactive invocations against an existing session. Default to
  interactive mode; gate any genuinely non-interactive need (e.g. CI) behind an
  explicit opt-in flag (as `ait codeagent --headless` does for `batch-review`).
  This applies to skill `.md` files too. See
  `aidocs/framework/skill_authoring_conventions.md` ("Do not route skill
  invocation through `claude -p`") for the skill-rendering rationale.

> **macOS portability quirks** (BSD sed vs GNU sed — incl. GNU-only `\?`/`\+`/`\|`
> BRE quantifiers; gawk-only awk features like 3-arg `match()`; `grep -P`
> unavailable; `wc -l` padding; `mktemp --suffix`; `base64 -D` vs `-d`): see
> `aidocs/framework/sed_macos_issues.md`. After fixing one such bug, sweep the
> tree for the whole class — these footguns travel in families.
