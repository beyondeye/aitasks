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
- **Committing task-data paths: use `task_git_commit_scoped`, never a bare
  `task_git commit`.** A `task_git commit -m "…"` with no `--` pathspec commits
  the **entire index**, not the paths you staged. The task-data branch is shared
  by every concurrent session, so whatever another agent has staged at that
  instant lands in a commit whose message names *your* task — provenance is lost
  and half-finished work gets pushed. Staging narrowly is not enough: the race is
  between your `add` and your `commit`.
  ```bash
  source "$SCRIPT_DIR/lib/task_utils.sh"

  local -a paths=( "$task_file" )
  [[ "$_stage_labels" == true ]] && paths+=( "$LABELS_FILE" )

  local crc=0
  task_git_commit_scoped "ait: Update task t42" "${paths[@]}" || crc=$?
  # 0 = committed, 2 = verified nothing to commit, 1 = failed. Do not conflate
  # 2 and 1: reporting a real failure as "nothing to commit" hides it.
  ```
  Pass `--no-stage` when the call site has already staged deliberately (an
  `add -u` that stages only tracked deletions, say) — the helper's own
  `add -- <paths>` stages **untracked** files under a directory pathspec, which
  would widen the set. **Build the pathspec conditionally**, exactly like the
  staging: `commit -- <paths>` commits *worktree* content, so naming a shared
  file such as `labels.txt` unconditionally carries a concurrent session's edit
  even when you never staged it.

  **`./ait git commit` is the same seam, not a different one** (t1728). `ait`
  sources `lib/task_utils.sh` and dispatches `git` straight to `task_git`, so a
  `./ait git commit` with no `--` pathspec commits the whole index exactly as
  above. There is no separate `ait_git_commit_scoped` and none is needed: source
  `task_utils.sh` and call the same helpers. Absorb the status with `|| crc=$?`
  — under `set -euo pipefail` a bare call returning 2 aborts the script *after*
  your file was written — and write the follow-up branch as a real `if … fi`, not
  `(( crc == 1 )) && warn …`, which is a complete `&&` list and fails the script
  whenever the test is false.

  **When the path may already be tracked *and* staged by another session, reach
  for `ait_commit_paths_staging_untracked` instead** (t1702, in the same file).
  The scoped helper's default `add` fixes the commit but introduces a second
  shared-index hazard: an `add` of a **tracked** path replaces the index entry
  another session staged for that same path, and it does so even when your
  commit then fails. The t1702 caller stages only paths git does not track yet,
  unstages exactly those on failure, and delegates to
  `task_git_commit_scoped --no-stage`. Arm its cleanup **in the caller** —
  `trap 'ait_unstage_staged_by_us' EXIT` — and **compose** it with any EXIT trap
  the script already has, or you will silently drop that one.

  `tests/test_no_unscoped_task_commit.sh` enforces both seams. Its limits are
  stated in its header and worth repeating: it reassembles `\`-continued lines
  and greps them, so it will **not** see a commit built through a variable; the
  `./ait git commit` pattern is matched against the quote-stripped line so
  recovery-hint prose inside message strings is ignored, and it carries a
  second, seam-specific allowlist holding one file whose hints span multiple
  physical lines. Neither pattern detects the tracked-path staging hazard above
  — that one is covered by behavioural controls, not by the scanner.

  **The same hazard exists at the INSTRUCTION layer** (t1748), where a skill
  procedure tells an agent to run the command and the agent obeys it literally.
  The cure there is neither bash seam — an agent following markdown cannot call a
  bash function — but `./.aitask-scripts/aitask_task_commit.sh -m "<msg>"
  <paths>`, the t1702 wrapper with the trap already armed. The rule for procedure
  authors lives in `aidocs/framework/skill_authoring_conventions.md`; the same
  guard's third scan covers the skill and doc trees.
- **System libs added to `./ait`'s source-on-startup chain must also be added
  to `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` in the same PR.**
  43 tests scaffold a fake `.aitask-scripts/lib/` via that helper; a missing
  entry crashes every one of them with `No such file or directory` the next
  time `./ait` (or a helper that learns to source the new lib) is invoked
  from the fake repo. Current baseline: `aitask_path.sh`, `terminal_compat.sh`,
  `tmux_exec.sh`, `python_resolve.sh`, `yaml_utils.sh`, `atomic_write.sh`,
  `atomic_write.py`, `cross_repo_reexec.sh`, `followup_kinds_sh.sh`,
  `followup_kinds.py`, `stale_lock.sh`, `registry_lock.sh`. A lib with a runtime sibling in another language (the
  bridge pattern — `followup_kinds_sh.sh` shells out to `followup_kinds.py`)
  must have **both** copied, or it fails closed inside every scaffolded test.

  **Python fixtures get the same guarantee by derivation, not by a list.**
  `tests/lib/shell_startup_closure.py` reads the startup chain out of the
  scripts themselves and copies its transitive closure, so a Python fixture
  cannot drift the way `tests/test_desync_state.py` did when `stale_lock.sh`
  joined `lib/task_utils.sh` in t1725_1 (t1745). Never hand-list the chain in a
  Python fixture; call `copy_startup_closure()`.

  That derivation rests on a **format contract**, enforced by
  `tests/test_shell_startup_closure.py`: a lib needed at startup is sourced
  **unconditionally, at column 0**, in one of three spellings —
  `source "${SCRIPT_DIR}/lib/x.sh"`,
  `source "$(dirname "${BASH_SOURCE[0]}")/x.sh"`, or
  `source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/x.sh"`. A lazy or
  conditional source stays **indented** (the framework's live ones sit inside
  function bodies). Bash itself attaches no meaning to indentation, so this is a
  convention the contract test enforces rather than something the tooling can
  infer — classifying by lexical function-body depth was tried and rejected, as
  it falsely flags the idiomatic
  `if [[ -r … ]]; then source …; fi`. Consequences when you edit a scanned lib:
  a column-0 source through a *variable* path (`source "$dir/x.sh"`) fails the
  contract test by design; and a source that must genuinely be conditional yet
  is required at startup will **not** be derived — add it to the consuming
  fixture's explicit extras.
- **Ephemeral cross-process mutexes: use `lib/stale_lock.sh`, never a
  hand-rolled `/tmp` mkdir lock.** `stale_lock_acquire <dir> <retries>
  <sleep> <label>` / `stale_lock_release <dir> <token>` (the token comes back
  in `STALE_LOCK_TOKEN`; never call acquire inside a command substitution, or
  the token is stranded in the subshell), with `ait_lock_dir <name>` resolving
  a per-user, per-repo lock path — `AITASKS_LOCK_DIR` is the documented env
  seam tests use for isolation instead of encoding uniqueness in task ids.
  The helper's stale reclaim is single-winner (observation and destruction
  serialized under a `.gc` guard) and **never displaces a live holder**: dead
  PIDs are reclaimed, tokenless dirs only after 120s, and a wedged lock is
  named in the caller's exhaustion error rather than self-healed (t1496 —
  the hand-rolled copies in `aitask_gate.sh`/`aitask_create.sh` stole live
  locks under contention). **The `.gc` guard carries a holder record**
  (`<lock_dir>.gc/h.<pid>.<nonce>`, t1598), so a process killed inside the
  guard's few-file-op section leaves a guard naming a dead pid and the next
  acquire frees it. Liveness decides at **any** duration — a guard held across
  a long legitimate section (`aitask_merge_task.sh` runs `git reset --hard`
  under one) is never displaced, which is why age alone was rejected. A guard
  with **no** record — left by pre-t1598 code, or by a foreign holder — is
  reclaimed only where the caller passes `stale_lock_acquire`'s 5th argument,
  which is a decision about the **lock dir**: every call site reaching one lock
  dir must pass the same window, and `merge_lock.sh` deliberately passes none.
  Two cases still need a human and both are fail-safe: a recycled holder pid
  reads as alive, and a hung holder is never displaced. The cure is still
  `rmdir`-only but now takes two arguments, since a guard carrying a record is
  not empty: `rmdir '<lock_dir>.gc'/h.* '<lock_dir>.gc'`.
  `stale_lock_describe` / `registry_lock_describe` name the guard and its
  holder, and a caller whose failure is otherwise silent should surface that
  hint.
- **Persistent-registry mutexes: use `lib/registry_lock.sh`,** the
  API-preserving adapter over that same core (t1507 — it used to carry its own
  observe-then-`mv` reclaim, i.e. the t1496 race). `registry_lock_acquire <dir>
  [timeout_secs] [label]` / `registry_lock_release <dir>` differ from the core
  in exactly three documented ways, spelled out in the lib header: the API
  budgets **seconds** rather than attempts (a `date +%s`-quantized deadline, so
  the promise is "never busy before the integer clock reaches
  `start + timeout`", *not* a real-time minimum wait); release **always returns
  0** because every caller is `set -euo pipefail` and calls it bare after its
  mutation already committed; and the core's tokenless age reclaim becomes
  reachable. Its lock paths are **caller-chosen fixed shared locations** (the
  per-user config dir, the data worktree, `/tmp`) and are deliberately not
  routed through `ait_lock_dir`'s per-repo scoping — those ledgers are shared
  across repositories by design. Consumers: `ait projects`, `ait attach` /
  artifact manifests (`lib/attachment_lock.sh`), agent marks, shadow
  rejections, `ait gates sync-registry`. (This lock family is distinct from
  `aitask_lock.sh`, the git-visible *task ownership* lock.)
- **Two dots in `git diff` are not a commit range.** `git log A..B` means
  "commits in B not in A", but `git diff A..B` is just `git diff A B` — an
  endpoint-to-endpoint comparison — so it also reports files changed only by the
  *local* side. Whenever the two endpoints can diverge, use three dots
  (`git diff A...B`), which diffs from the merge base and yields "what B
  changed". This is the t1724 bug: `aitask_remote_drift_check.sh` computed its
  remote-changed file set with `<base>..origin/<base>` and reported the user's
  own landed commits as remote drift, inflating `OVERLAP` — the *strong* half of
  the check — and training the user to click past a real hit.

  **The discriminator is whether the left side is an ancestor of the right.**
  When it is, the two forms are identical by definition, so these existing sites
  are correct as written and must not be "fixed": `aitask_revert_analyze.sh`
  (`<hash>^..<hash>`), `.claude/skills/aitask-qa/change-analysis.md` and
  `.claude/skills/aitask-shadow/impl-challenge.md` (`<first>^..<last>`), and
  `.claude/skills/aitask-docs-gap/SKILL.md` (`<release-tag>..HEAD`). Because a
  grep cannot tell an ancestor pair from a divergent one, there is deliberately
  no scan guard for this — it would flag all four. Check the endpoints by hand.
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
