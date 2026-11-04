---
Task: t2191_precheck_nonregular_gitignore_before_git_probes.md
Base branch: main
Output branch: main
---

# t2191 — Refuse a non-regular .gitignore before any git probe; chain the per-rule writer

## Context

t2185 hardened the framework's own reads and writes of the main `.gitignore`
against a FIFO / directory / read-only file. Its premise ("git itself does not
block on a FIFO `.gitignore`") was measured to be false in general on git 2.56.0:
with an untracked FIFO `.gitignore`, or a tracked one swapped for a FIFO once git
walks a directory, `git ls-files --others --exclude-standard`, `git status` and
`git add` block forever. `ait setup`'s `main()` reaches exactly that probe in
`snapshot_pre_setup_dirty` → `_ait_list_framework_changes`
(`.aitask-scripts/aitask_setup.sh:4773`, called from `main()` at `:5738`) before
any of t2185's code runs, so `ait setup` still hangs. `install.sh`'s
`snapshot_pre_install_dirty` → `_install_list_changes` (`install.sh:1277/1330`)
runs the same probe, with `.gitignore` and `.aitask-scripts/` among its
pathspecs (not yet measured — measured in step 1 below).

"Skip every .gitignore step" cannot fix this: git's own reads are what block,
and nearly every git call setup makes (`ls-files --others`, `status`, `add`)
reads `.gitignore`. The only sound fix is **one early precondition, before any
git command, that refuses**.

The same task also fixes a second, independent defect: `_ait_add_gitignore_rules`
(`aitask_setup.sh:3164`) writes `{ echo ""; echo "# $comment"; printf ...; }`
and checks only the last status, so a failed separator glues the comment onto a
last line with no newline (`keep-me` → `keep-me# comment`, rc 0, "Added"). That's
the same defect t2185 fixed in `_ait_ensure_gitignore_block` with `&&`.

## Rebase on t2188 (landed mid-implementation, commit 57094479b)

t2188 was implemented concurrently in this checkout and committed right after
this plan was approved. That commit changes three things for this plan:

- **The second bullet has landed there.** `_ait_add_gitignore_rules` now chains
  `echo "" && echo "# $comment" && printf …` (append branch) and
  `echo "# $comment" && printf …` (create branch). Its regression test is
  `tests/test_setup_git.sh` 27n: a no-fault control, separator fault, comment
  fault and create-branch fault. **Step 3 and Test 27m below are therefore
  dropped**: re-doing them would duplicate t2188's code and test, and "27m" is
  now t2188's CRLF case. Before archival, verify that 27n passes and covers the
  `keep-me` gluing.
- **The 27f FIFO comment rewrite (step 5) landed in t2188's commit.** It was
  edited here before the shared-file gate was re-checked, and t2188's path-scoped
  commit absorbed it. It cites `main()`'s refusal and Test 29, which become true
  once this task lands. Nothing further to edit there.
- **Fixtures:** installer case N3 reuses t2188's `to_branch_mode` helper (an
  orphan `aitask-data` branch at `.aitask-data/`, the production layout) instead
  of a hand-rolled `git worktree add`. Line numbers in `aitask_setup.sh` moved
  (`_ait_add_gitignore_rules` now ≈ `:3197`). Insert the new helpers near
  `ensure_git_repo` (≈ `:1099`), away from t2188's `.gitignore`-table edits.

## Design decisions

- **Predicate = the helpers' own gate.** A path "exists" when `-e || -L`. It is
  refused when it exists and is not `-f`, so a regular file or a symlink to one
  passes. This is the exact predicate `_ait_add_gitignore_rules`,
  `_ait_ensure_gitignore_block` and `_ait_rewrite_data_gitignore_lines` already
  apply. The refused shapes are: FIFO, device, socket, directory, dangling
  symlink, and a symlink to anything that is not a regular file. A symlink
  `.gitignore` → regular file stays supported (test_gitignore_data_symlinks.sh
  Case E). Using one predicate means the check holds whichever shapes block a
  given git version: git <2.32 follows symlinks, so there a symlink to a FIFO
  blocks too. Only stat-based tests are used (`-e -L -f -p -d`), never an open.
- **Behaviour change, stated.** A directory or dangling-symlink `.gitignore`
  used to let a full `ait setup` / upgrade finish, with every `.gitignore` helper
  printing an rc-2 warning. It now stops up front with one fix instruction.
  Direct helper calls are unchanged (Tests 27f/40 call the helpers directly), so
  t2185's per-helper hardening stays as defence in depth.
- **Which paths: the `.gitignore` files the framework writes**, which are also
  the ones its first git probes read:
  - `<project>/.gitignore`: setup and upgrade helpers write it; both snapshots
    read it.
  - `<project>/.aitask-data/.gitignore`: written by `setup_data_branch`; the
    data-worktree baseline (the first probe in both snapshots) reads it.
  - `<project>/.aitask-scripts/.gitignore`: install.sh `cp`s the seed onto it;
    both snapshots walk `.aitask-scripts/`.

  An absent path passes; legacy mode has no `.aitask-data`.
  **Out of scope, documented in the helper comment:** nested user `.gitignore`
  files, `.git/info/exclude` and `core.excludesFile` are git's own reads of
  user-owned files that setup never writes. Also the git root's `.gitignore`
  when aitasks is installed in a subdirectory (`ensure_git_repo` warns about
  that layout).
- **Refuse, don't warn.** Each script calls `die` with one message that lists
  every offending path and its kind, and gives a non-destructive fix: move it
  aside (`mv <path> <path>.bak`), restore a regular file
  (`git checkout -- <path>` if tracked), then re-run. The setup message names
  `ait setup` (the CLI convention for repair). install.sh says "re-run the
  install / upgrade", because it cannot tell whether `ait upgrade` or a curl
  pipe invoked it.
- **install.sh carries its own copy.** It cannot source setup before extraction
  (a fresh install has no setup script; on an upgrade the old one may predate
  the function). So it gets a mirrored helper, the same convention as
  `_install_list_changes` / `_install_framework_paths`, with a "Mirrors …" note
  and a parity test. Its check runs at the top of `main()`, before the
  network/tarball work, on both install and upgrade: on a fresh install the
  `ait setup` that must follow would refuse anyway. Note that `ait upgrade`
  downloads the *target* release's install.sh, so this only takes effect when
  upgrading to a release that contains it.

## Implementation steps

### 1. Red proofs first (before touching the scripts)

Write the new tests (steps 5–7) first. Run them against the unfixed scripts and
record the red results in the plan's Final Implementation Notes:
- setup `main()` harness, untracked FIFO and tracked FIFO → expect `124`
  (hang) pre-fix. The directory case expects refusal but reaches the
  data-branch stub pre-fix → red.
- install.sh upgrade cases N1–N4, run with
  `INSTALL_SH=<scratchpad>/install_prefix.sh` (from `git show HEAD:install.sh`)
  → expect `124`. This is the measurement of `snapshot_pre_install_dirty` the
  task asks for, per location. If a shape does *not* hang, record which, and
  what it did instead (e.g. extracted and committed). Keep the case as a
  refusal test anyway: the uniform predicate does not depend on it, and a red
  result is either a hang or a missing refusal.
- setup `.aitask-data/` and `.aitask-scripts/` cases: same recording (hang vs
  reaches the data-branch stub).
- `_ait_add_gitignore_rules` fault cases → rc 0 with the glued line pre-fix.

### 2. `aitask_setup.sh` — the predicate and the main() step

Add near the other `.gitignore` helpers (around `:3140`, after the t2178 block
comment):

```bash
# --- Non-regular .gitignore precondition (t2191) ---
# git reads .gitignore files on every untracked-file walk (`ls-files --others
# --exclude-standard`, `status`, `add`), and opening one that is a FIFO blocks
# until a writer appears (measured, git 2.56.0: untracked FIFO, and a tracked
# one swapped for a FIFO once git walks a directory). snapshot_pre_setup_dirty
# is such a walk and runs before any helper that guards its own open, so main()
# refuses up front. The predicate is the helpers' own gate: exists (-e or -L)
# and not -f. Stat-only: nothing here opens the path.
# Scope: the .gitignore files the framework writes, which are also the ones its
# first probes read. Nested user .gitignore files, .git/info/exclude and
# core.excludesFile are git's own reads of files setup never writes.
# Mirrored by _install_framework_gitignores / _install_gitignore_nonregular_kind
# in install.sh — change both.
_ait_framework_gitignores() {
    local d="$1"
    printf '%s\n' "$d/.gitignore" "$d/.aitask-data/.gitignore" "$d/.aitask-scripts/.gitignore"
}

# _ait_gitignore_nonregular_kind <path> -> 0 and prints what it is when the
# path exists but is not a regular file (or a symlink to one); 1 otherwise.
_ait_gitignore_nonregular_kind() {
    local p="$1"
    [[ -e "$p" || -L "$p" ]] || return 1
    [[ -f "$p" ]] && return 1
    if [[ -L "$p" && ! -e "$p" ]]; then echo "a dangling symlink"
    elif [[ -L "$p" ]]; then echo "a symlink to something that is not a regular file"
    elif [[ -p "$p" ]]; then echo "a FIFO (named pipe)"
    elif [[ -d "$p" ]]; then echo "a directory"
    else echo "not a regular file"
    fi
    return 0
}

# Refuse to run when a framework .gitignore is not a regular file. MUST run in
# main() before any git command (see above).
refuse_nonregular_gitignores() {
    local project_dir="$SCRIPT_DIR/.." p kind found=""
    while IFS= read -r p; do
        kind="$(_ait_gitignore_nonregular_kind "$p")" || continue
        found+=$'\n'"  ${p#"$project_dir/"} is $kind"
    done < <(_ait_framework_gitignores "$project_dir")
    [[ -z "$found" ]] && return 0
    die "Cannot run setup: a .gitignore is not a regular file:$found
  git reads these files on every status and add, and cannot read one that is
  not a regular file — a FIFO or a device blocks it indefinitely — so setup
  stops before running any git command.
  Fix: move each aside (e.g. mv .gitignore .gitignore.bak), put back a regular
  file ('git checkout -- .gitignore' if it is tracked), then re-run 'ait setup'."
}
```

(Implementation detail: `$( )` around the kind helper keeps errexit-safe status
via `|| continue`. Print paths relative to the project root.)

In `main()`: call `refuse_nonregular_gitignores` right after the
`info "aitask framework setup"` banner and before `detect_os`. That puts it
before `install_cli_tools` (the first side effect), `ensure_git_repo` and
`snapshot_pre_setup_dirty`. Update `snapshot_pre_setup_dirty`'s header comment
with one line: "main() has already refused a non-regular .gitignore
(refuse_nonregular_gitignores)". `--hooks-only` and `--help` exit earlier and
run no untracked-file walk, so they are left unguarded.

### 3. ~~`aitask_setup.sh` — chain `_ait_add_gitignore_rules`~~ (landed in t2188, see above)

Append branch: `{ echo "" && echo "# $comment" && printf '%s\n' "${missing[@]}"; }`.
Create branch: `{ echo "# $comment" && printf '%s\n' "${missing[@]}"; }`.
Add the same short `&&`-not-newline comment `_ait_ensure_gitignore_block`
carries. Any failed write then reaches the existing `_ait_gitignore_note_partial`
/ rc-2 path; no other change.

### 4. `install.sh` — mirrored helper and the main() call

Add `_install_framework_gitignores` and `_install_gitignore_nonregular_kind`
(bodies identical to the setup ones; header "Mirrors
_ait_framework_gitignores / _ait_gitignore_nonregular_kind in aitask_setup.sh —
change both"), plus `refuse_nonregular_gitignores_install` using
`$INSTALL_DIR`. Its message is the same, ending "then re-run the install /
upgrade." Call it first in `main()`, right after the
`info "aitask framework installer"` banner. Bash 3.2-safe: no `+=` on strings is
fine in 3.2, no namerefs, no `mapfile`.

### 5. Tests — `tests/test_setup_git.sh`

- ~~**Test 27m — per-rule writer chain (t2191).**~~ Dropped: t2188's 27n covers it. Original text kept for the record: Direct calls to
  `_ait_add_gitignore_rules` in `$( )` subshells. Inside each, a counter `echo`
  shadow fails only call N
  (`echo() { _n=$((_n+1)); (( _n == N )) && return 1; builtin echo "$@"; }`).
  Each subshell prints `rc=… partial=… added=… n=…`; `n` is the control that
  proves the fault fired.
  - control: no-newline `keep-me` file, no fault → rc 0; `keep-me` is still a
    whole line; `rule-a/` added; the comment is on its own line.
  - fault on call 1 (separator) → `rc=2 partial=`; the file is byte-identical
    (`cmp`). Pre-fix: rc 0 and the line becomes `keep-me# Some comment`.
  - fault on call 2 (comment) → `rc=2 partial=yes`; `rule-a/` absent; the file
    is exactly the original plus `\n`. Pre-fix: rc 0, rule added with no
    comment.
  - create branch (no file), fault on call 1 → rc 2, `rule-a/` not present.
- **Test 29 — refuse a non-regular .gitignore before any git probe (t2191).**
  - (a) Predicate table, bounded child (`run_bounded 15`). Each case's
    `_ait_gitignore_nonregular_kind` status and output:
    - absent → 1
    - regular → 1
    - symlink→regular → 1
    - FIFO → 0 "a FIFO (named pipe)"
    - directory → 0 "a directory"
    - dangling symlink → 0 "a dangling symlink"
    - symlink→FIFO → 0 "a symlink to …"
  - (b) End-to-end through the real `main()`, in a bounded child
    (`run_bounded 30`, `HOME=` scratch, stdin `</dev/null`). The child sources
    setup with `--source-only`, sets `SCRIPT_DIR`, and stubs the side-effecting
    early steps: `detect_os() { OS=linux; }`, `install_cli_tools() { :; }`,
    `check_bash_version() { :; }`, and `setup_data_branch() { echo
    REACHED_DATA_BRANCH; exit 0; }`. Then it runs `main`. **Every protected
    location gets its own case**, so a wrapper that iterates only part of the
    path list fails here:
    - root untracked FIFO (repo committed with no `.gitignore`, then `mkfifo`)
    - root tracked FIFO (`new_gitignore_repo`, then `rm` + `mkfifo`)
    - root directory
    - `.aitask-data/.gitignore` FIFO, in a real linked data worktree
      (`git branch aitask-data` + `git worktree add .aitask-data aitask-data`)
      so the data-baseline probe actually runs pre-fix
    - `.aitask-scripts/.gitignore` FIFO (the fixture commits a regular
      `.aitask-scripts/.gitignore` first — `setup_fake_project` creates none —
      then swaps it for a FIFO; `.aitask-scripts/` is a snapshot pathspec git
      walks)
    - multi-path: root and `.aitask-scripts/.gitignore` both FIFOs → one
      refusal naming **both** (proves the wrapper accumulates instead of
      stopping at the first)

    Each must give rc 1 within the bound (not 124), with the "not a regular
    file" message naming that case's path(s) — the relative path, matched
    exactly. It must not print `REACHED_DATA_BRANCH`. The offending path must
    still be the same shape (`-p` / `-d`), with no new commit.
    Controls: a regular `.gitignore`, and a symlink → regular `.gitignore`, each
    → `REACHED_DATA_BRANCH`, rc 0. These prove the harness gets past
    `ensure_git_repo` + `snapshot_pre_setup_dirty`, so a refusal is the check's
    doing.
  - (c) Structural: in `declare -f main`, `refuse_nonregular_gitignores`
    precedes `install_cli_tools`, `ensure_git_repo` and
    `snapshot_pre_setup_dirty` (the Test 22 pattern).
- **Rewrite 27f's FIFO comment** (`:904-910`) to the measured truth: git 2.56
  blocks on a FIFO `.gitignore` when it is untracked, and on a tracked one once
  git walks a directory. `main()` now refuses before the snapshot (Test 29), and
  the direct-call fixture keeps skipping the snapshot for that reason.

### 6. Tests — `tests/test_install_upgrade_dirty_baseline.sh`

- Source `tests/lib/proc_fixtures.sh`. Add `run_install_bounded <secs> <dir>
  <tarball> [args]`: the `run_install` env, through `run_bounded`, into a log,
  setting `OUT`/`RC`.
- **Case N — a non-regular .gitignore stops the upgrade before any git probe.**
  Each protected location runs through the real installer `main()`. Case P2
  only proves the helpers agree, not that
  `refuse_nonregular_gitignores_install` iterates every path:
  - N1: `make_project`, then an untracked FIFO `.gitignore`.
  - N2: `make_project`, commit a regular `.gitignore`, then `rm` + `mkfifo`.
  - N3: `make_project`, then `to_branch_mode` (t2188's fixture), commit main
    with a regular `.gitignore`, then `mkfifo .aitask-data/.gitignore`. The worktree is real so the data
    baseline probe — the first one `snapshot_pre_install_dirty` runs — actually
    reaches it pre-fix.
  - N4: `make_project` (its install committed the seeded
    `.aitask-scripts/.gitignore` — asserted as a fixture precondition with
    `git ls-files --error-unmatch`, so a case built on an untracked or absent
    file fails loudly), then `rm` + `mkfifo .aitask-scripts/.gitignore`. This is
    also the file extraction would `cp` the seed onto.
  - Each: bounded upgrade (`--force`, 30s) → rc 1, not 124. The output carries
    the "not a regular file" message naming **that case's** relative path. Nothing
    was extracted: `.aitask-scripts/VERSION` is still the old one and `ait`
    lacks the t1964 upgrade marker. HEAD is unchanged, and the offending path is
    still a FIFO (`-p`).
- **Case P2 — predicate parity.** A bounded child sources both scripts
  `--source-only`, and runs `_install_gitignore_nonregular_kind` and
  `_ait_gitignore_nonregular_kind` over the step-5 shape set. Both must give
  identical status+output for every shape. Also
  `_install_framework_gitignores` = `_ait_framework_gitignores`, as path
  suffixes. This is the P pattern.

### 7. Verification

- Red-before/green-after for every new case (step 1), recorded in Final
  Implementation Notes with exact rc values.
- `bash tests/test_setup_git.sh`, `bash tests/test_install_upgrade_dirty_baseline.sh`,
  `bash tests/test_data_branch_setup.sh`, `bash tests/test_gitignore_data_symlinks.sh`,
  `bash tests/test_setup_help_flag.sh`: all PASS.
- `shellcheck .aitask-scripts/aitask_setup.sh install.sh`: no new findings.
- Full-flow check (extension-points rule). In a scratchpad dir: `git init`,
  `bash install.sh --dir <d> --local-tarball <built tarball>`, `mkfifo
  <d>/.gitignore`, then `run_bounded 30 … ./ait setup` → refuses within
  seconds, naming `.gitignore`. Post-fix only: pre-fix this would run
  `install_cli_tools`.
- Before recording it in Final Implementation Notes, probe whether the
  data-branch `.gitignore` writers in `setup_data_branch` (`:1869-1905`,
  unchecked `>>` and `grep`) abort setup on a read-only
  `.aitask-data/.gitignore`. That fault is not covered by this precondition,
  so if confirmed it is an upstream defect.

### 8. Step 9 (Post-Implementation)

Current-branch mode: no merge; commit code (`bug: … (t2191)`) and plan
separately, run the gate orchestrator / build verification, archive via
`aitask_archive.sh 2191`, push.

## Risk

### Code-health risk: low
- A directory / dangling-symlink `.gitignore` now stops a full `ait setup` / upgrade up front instead of letting it finish with per-helper warnings — a deliberate behaviour change on states every `.gitignore` step already failed on · severity: low · → mitigation: none (stated in Design decisions; direct helper calls and their t2185 hardening are unchanged)
- install.sh carries a mirrored copy of the predicate and path list, which can drift from setup's — and either refusal wrapper could iterate only part of its list while the helpers still agree · severity: low · → mitigation: none (addressed in plan: Case P2 parity over every shape for the helpers; every protected location gets its own case through the real `main()` of both scripts — setup Test 29(b) and installer N1–N4 — plus a multi-path accumulation case)
- The 27m fault tests key on which `echo` call is which inside the writer, so a reordering of the helper's writes would silently move the fault · severity: low · → mitigation: none (addressed in plan: each case prints the counter `n` and asserts the expected bytes, so a moved fault fails visibly)

### Goal-achievement risk: low
- The precondition covers only the `.gitignore` files the framework writes; a FIFO nested user `.gitignore`, `.git/info/exclude` or `core.excludesFile` still blocks git · severity: low · → mitigation: none (documented boundary — user-owned files setup never writes)
- `snapshot_pre_install_dirty`'s hang is unmeasured; a shape that does not hang pre-fix would weaken that case's red proof · severity: low · → mitigation: none (addressed in plan: measured in step 1, the case stays a refusal test either way)
- `ait upgrade` downloads the target release's install.sh, so the install.sh guard protects only upgrades to releases that contain it · severity: low · → mitigation: none (inherent to the upgrade design)

## Post-Review Changes

### Change Request 1 (2026-11-04 10:30)
- **Requested by user:** `t29_refused` (tests/test_setup_git.sh) ran its shape check as an unquoted command string (`$($shape && …)`, callers passing `"test -p $d/.gitignore"`). With spaces in TMPDIR, word splitting gave `test` extra arguments and falsely failed all six preservation assertions (reviewer reproduced 729 passed / 6 failed). Pass the shape operation and paths as separate arguments and quote each path.
- **Changes made:** `t29_refused <label> <dir> <-p|-d> <commits-before> <relpath>...` — the shape is a `test` operator argument, each relative path is checked with `test "$shape" "$d/$rel"` (one quoted word), and the expected `"  <rel> is <kind>"` refusal line is derived from the same shape (so callers no longer hand-write both). The multi-path case now checks each path's preservation separately (735 → 736 checks). Verified: `test_setup_git.sh` 736/736 with a normal TMPDIR and with `TMPDIR` containing spaces; `test_install_upgrade_dirty_baseline.sh` 200/200 with a spaced TMPDIR (its new N/P2 cases already quote every path).
- **Files affected:** tests/test_setup_git.sh

## Final Implementation Notes
- **Actual work done:** One early precondition in both entry points. `aitask_setup.sh` gains `_ait_framework_gitignores` (`:1113`), `_ait_gitignore_nonregular_kind` and `refuse_nonregular_gitignores` (`:1135`), called in `main()` (`:5817`) right after the banner and before `detect_os`, so ahead of `install_cli_tools`, `ensure_git_repo` and `snapshot_pre_setup_dirty`. `install.sh` gains the mirrored `_install_framework_gitignores`, `_install_gitignore_nonregular_kind` and `refuse_nonregular_gitignores_install` (`:157`), called first in `main()` (`:1785`), before the download and `snapshot_pre_install_dirty`. Both refuse (`die`) when the root, `.aitask-data/` or `.aitask-scripts/` `.gitignore` exists but is not a regular file (or a symlink to one). They name every offending path with its kind and give a non-destructive fix (`mv` aside, `git checkout --`, re-run). Tests: `tests/test_setup_git.sh` Test 29 — (a) the predicate table over 7 shapes; (b) one real-`main()` case per protected location (root untracked FIFO, root tracked→FIFO, root directory, `.aitask-data/.gitignore` FIFO in a real linked worktree, `.aitask-scripts/.gitignore` tracked→FIFO), a two-file accumulation case, and regular / symlink→regular controls; (c) structural order in `main()`. `tests/test_install_upgrade_dirty_baseline.sh` gains `run_install_bounded`, cases N1–N4 (one per location, through the real installer: refusal named, VERSION / `ait` / HEAD unchanged, FIFO kept), and P2 (setup/install predicate and path-list parity over every shape).
- **Deviations from plan:** (1) The second bullet (chain `_ait_add_gitignore_rules`' writes) and its regression test were **not** done here. t2188, implemented concurrently in this checkout, landed both in commit `57094479b` (chained writes in both branches, Test 27n: control, separator, comment and create-branch faults). Duplicating them would have repeated t2188's code and test, and "27m" is t2188's CRLF case. 27n passes in this task's final run (736/736). (2) The planned 27f comment rewrite landed inside t2188's commit `57094479b`, not this task's. It was edited here before the shared-file gate was re-checked, and t2188's path-scoped commit of `tests/test_setup_git.sh` absorbed it seconds later. It cites `main()`'s refusal and Test 29, both true as of this task's commit. (3) Helpers were inserted beside `ensure_git_repo` rather than near the `.gitignore` table, to stay clear of t2188's edits there. (4) N3 reuses t2188's `to_branch_mode` fixture.
- **Issues encountered:** Concurrent session t2188 had uncommitted hunks in `aitask_setup.sh` and three of the four test files when implementation began (the session-start `git status` was clean). After it committed, the gate (`git diff --quiet HEAD -- <file>`) was re-run before every first edit. One review change: `t29_refused` executed a command string through unquoted `$shape`, which broke under a TMPDIR with spaces (Change Request 1). A stray backgrounded `git status` against the full-flow fixture's FIFO `.gitignore` blocked as expected and was killed (12s; pid checked before the kill).
- **Key decisions:** The predicate is the `.gitignore` helpers' own gate (`-e || -L`, then `-f`), not "only shapes that block git". It holds whatever a given git version does (git <2.32 follows symlinks, so a symlink to a FIFO blocks there). It deliberately changes behaviour for a directory or dangling-symlink `.gitignore`: full setup / upgrade now stop up front instead of finishing with per-helper rc-2 warnings. Direct helper calls (Tests 27f/40) are unchanged. Covered paths are the `.gitignore` files the framework writes. Nested user `.gitignore` files, `.git/info/exclude`, `core.excludesFile` and the git root's `.gitignore` for a subdirectory install are out of scope (documented in the helper comment). install.sh refuses on fresh installs too: the `ait setup` that must follow would refuse anyway. `ait upgrade` runs the *target* release's install.sh, so the installer guard protects only upgrades to a release containing it.
- **Measurements (git 2.56.0, one host — omg16; bounded at 30s):** Red, pre-fix:
  - setup `main()` (stubbed early steps): root untracked FIFO **124**, root tracked→FIFO **124**, `.aitask-data/.gitignore` FIFO **124**, root+scripts FIFOs **124**; root directory rc 0 and `.aitask-scripts/.gitignore` tracked→FIFO rc 0 — both ran on to the data-branch step, the scripts FIFO did **not** hang in setup's minimal fixture.
  - pre-fix installer (`git show HEAD:install.sh`), N1–N4: all **124**, each stopping right after the changelog, i.e. in `snapshot_pre_install_dirty` — including N4, the `.aitask-scripts/.gitignore` FIFO, in a real installed tree.
  - P2: 127 (helper absent).

  Green, post-fix: `test_setup_git.sh` 736/736 (6s vs 2m06s pre-fix), also under a TMPDIR with spaces; `test_install_upgrade_dirty_baseline.sh` 200/200 (also with spaces); `test_data_branch_setup.sh` 501/501; `test_gitignore_data_symlinks.sh` 0 failed; `test_setup_help_flag.sh` 23/23. Full flow: real `install.sh --local-tarball` into a scratch repo, `mkfifo .gitignore`, bounded `./ait setup` → rc 1 in <1s, naming `.gitignore`, FIFO kept. `shellcheck` finds nothing in the new lines (27 findings vs HEAD's 28, all pre-existing).
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_setup.sh:1921 — setup_data_branch's fresh-worktree writes to .aitask-data/.gitignore are unchecked `>>` appends and unguarded greps under main()'s errexit, the shape t2185/t2188 hardened for the main .gitignore; a FIFO there is now refused up front, but a write failure (e.g. a umask that strips owner write on the fresh checkout) would abort setup — not probed`
