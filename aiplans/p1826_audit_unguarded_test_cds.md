---
Task: t1826_audit_unguarded_test_cds.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1826 — Audit unguarded `cd`s in bash tests: guard every one, plus a harmless start cwd

## Context

t1815 found that `tests/test_data_branch_setup.sh` leaked fixture task files into
the live `aitasks/` and made commits in the real repository. The cause was a
`cd` into a fixture directory with no `|| exit 1`: when the `cd` failed, the
subshell stayed in the invoking directory (the repo root) and wrote there. t1815
fixed that file with a scratch-cwd backstop. This task audits every other
`tests/*.sh` for the same shape and fixes the real hits.

### Audit results (read-only triage, done during planning)

- A prototype scanner (logical lines, heredoc bodies skipped, `cd`/`pushd` only
  in command position) finds **587 unguarded or weakly guarded sites in 172
  files** (`tests/*.sh` + `tests/lib/*.sh`):
  - 492 have no guard;
  - 78 use `cd X && …`, which does not protect the lines after it;
  - 17 use `|| true` / `|| return`.

  154 are already `|| exit`-guarded, and 2001 are `$(cd … && pwd)`-style
  `&&` chains confined to one group.
- Nearly every fixture site is followed within a few lines by writes
  (`git init/config/add/commit/push`, `> aitasks/…`, `mkdir`, `rm -rf`) or a
  framework script call.
- **`set -e` does not make these safe.** errexit is suppressed inside `$( … )`,
  in `if`/`||`/`&&`/`!` contexts, and after `set +e`. The common `setup_project`
  shape `pushd`es inside a function and the caller writes relative paths
  afterwards.
- **A target's name does not say whether it is a fixture or the live repo.**
  `$REPO` is a fixture in `test_atomic_task_file_writes.sh`,
  `test_gate_plan_approval_transitions.sh` and the `test_artifact_*` /
  `test_attach_*` files. `$REPO_ROOT` is the live repo in
  `test_tmux_control.sh`, which `cd`s back to it 9 times, and in
  `test_tmux_control_resilience.sh`. About 160 persistent `cd`s return to
  `$PROJECT_DIR`/`$REPO_ROOT`/`$ORIG_DIR`, so the live repo can become the cwd
  **mid-file**. A failed fixture `cd` after that point leaks, whatever cwd the
  file started in. **So a start-of-file backstop alone is not a durable
  invariant, and a lint that exempts "intentional" targets by name would pass
  exactly that leak.**
- Unquoted empty targets are a separate trap: `cd $x` with `x=""` goes to
  `$HOME` and returns 0, so no guard fires.

### Secondary goal: the unexplained 2026-09-02 09:09:18 `t1_alpha.md` truncation

Evidence (for the Final Implementation Notes):
- Only two files name `t1_alpha`: `test_data_branch_setup.sh` (guarded since
  f408721ea) and `tests/test_boardcol_update.sh`. t1815 missed the second one.
  It writes after a `pushd` into a `mktemp` dir, and always non-empty content,
  so it cannot produce an empty file.
- The Claude transcripts active at 06:07–06:10 UTC (sessions 8ef3f1dd, 96d557a3,
  7d28780a) ran no test. They ran `aitask_pick_own.sh --sync` at 06:07:27 and
  `aitask_create.sh` at 06:09:31, and edited a plan.
- The data-branch reflog has nothing at 09:09:18 (09:07:09 commit, 09:09:35
  "Add task t1679").
- Task worktrees get a `.aitask-data` symlink into the live data dir
  (`aiwork/t1794_4_impl` today is current). A failed `cd` in a test run from a
  worktree therefore leaks into the live tree too. The fix covers this, because
  it does not depend on the invoking directory.
- No Python test writes to the live `aitasks/`; all write under fixture roots.
- Remaining candidates, none proven: a git rewrite of the tracked 0-byte file
  inside `.aitask-data` (stash/restore/autostash, which the HEAD reflog does not
  show), or a non-Claude agent. **Result: unexplained. No second leak source in
  `tests/`.**

## Design — two layers

**Layer 1 (the invariant, lint-enforced, target-agnostic):** every `cd`/`pushd`
in `tests/*.sh` and `tests/lib/*.sh` is either
- **guarded with an unconditional `exit`**: `cd "$X" || exit 1`, or
  `|| { …; exit …; }` where `exit` is the **last** command in the braces, so
  nothing like `[[ … ]] && exit` passes. Only `exit` counts. `|| return` relies
  on every caller checking, and the `setup_project` shape proves they don't. In
  a subshell `exit` ends only the subshell, whose `cd` never affected the
  caller.
- an **`&&` chain confined to one subshell**: the `cd` is the first command
  inside `(` or `$(` (never `{`, which shares the caller's cwd), and only `&&`
  connectors lead to that group's closing `)`. If the `cd` fails nothing else in
  the group runs, and the cwd outside the group never changed. The canonical
  form is `$(cd "$d" && pwd)`.
- or it carries an explicit, reviewed exemption on the line:
  `# cd-guard: <reason>`.

**Conditional forms are violations**: `if`/`elif cd …; then`, `while`/`until
cd …`, `! cd …`, and `cd … || true` / `|| return`. A failed `if cd` with no
`else` carries on after `fi` in the previous cwd, a failed loop condition carries
on after `done`, and `! cd` turns failure into success. After an earlier return
to the live repo, the relative writes that follow would leak. Such a site must
be rewritten into an accepted form or carry a `# cd-guard:` exemption with a
reason a reviewer can check. The prototype scan found no conditional sites
today, so this costs no extra edits and only closes the door.

Also, a variable target must be quoted, so an empty variable fails instead of
going to `$HOME`. Because the rule never looks at the target, a
`cd "$PROJECT_DIR"` re-entry followed by any later fixture `cd` is covered: the
later `cd` is guarded, or the lint fails. No list of "intentional" names
exists to go stale.

**Layer 2 (defense in depth):** the shared helper `enter_scratch_cwd` in
`tests/lib/scratch_cwd.sh` moves the process at start-up into a **per-user,
empty, read-only (0555), never-deleted** directory. It covers what Layer 1 does
not: relative writes a file makes **before** any `cd`, and lint false negatives
(`cd` via `eval` or a computed command). It is read-only and never
trap-cleaned, because 48 of the flagged files set their own `trap … EXIT`,
which would replace a helper trap. Nothing can write into it, so concurrent
runs can share it. `find .` after a failure stays instant, unlike `cd /`.

**Root lifecycle (bounded):** root uses the **same single** path
`ait-test-cwd-0`. Root ignores 0555, so a leak under root can land in that one
directory, never in the repo. The non-empty check then makes the **next** run
fail closed and name the directory. Retention is exactly one directory per
UID. No per-run `mktemp` and no unbounded accumulation.

```bash
# tests/lib/scratch_cwd.sh
enter_scratch_cwd() {
    command -v git >/dev/null 2>&1 || { echo "FAIL: git not found"; exit 1; }
    local base="${TMPDIR:-/tmp}"; base="${base%/}"
    local dir; dir="$base/ait-test-cwd-$(id -u)"
    if [[ ! -d "$dir" ]]; then
        mkdir -m 0555 "$dir" 2>/dev/null || [[ -d "$dir" ]] \
            || { echo "FAIL: cannot create scratch cwd '$dir'"; exit 1; }
    fi
    [[ -O "$dir" && ! -L "$dir" ]] \
        || { echo "FAIL: scratch cwd '$dir' is not a directory owned by uid $(id -u)"; exit 1; }
    chmod 0555 "$dir" || { echo "FAIL: cannot make '$dir' read-only"; exit 1; }
    if [[ -n "$(ls -A "$dir")" ]]; then
        echo "FAIL: scratch cwd '$dir' is not empty — a test wrote into it" \
             "(possible under root, which ignores 0555); inspect it, then remove it"
        exit 1
    fi
    if git -C "$dir" rev-parse --git-dir >/dev/null 2>&1; then
        echo "FAIL: scratch dir '$dir' resolves to a git repository" \
             "(TMPDIR='${TMPDIR:-}' GIT_DIR='${GIT_DIR:-}'); refusing to run fixtures there"
        exit 1
    fi
    cd "$dir" || { echo "FAIL: cannot enter scratch cwd '$dir'"; exit 1; }
    AIT_TEST_SCRATCH_CWD="$dir"
}
```

## Implementation

1. **Scanner, one definition: `tests/lib/cd_guard_scan.py`.** It is used by the
   lint test and by the one-off rewrite. It:
   - joins `\`-continued lines;
   - skips comment lines and heredoc bodies (`<<[-]['"]WORD` … `WORD`);
   - finds `cd`/`pushd` in command position (line start, or after `(`, `$(`,
     `;`, `&&`, `||`, `|`, `{`, `then`, `do`, `else`);
   - classifies each site. Accepted: `guarded | subshell-andchain | exempt`.
     Violations: `unguarded | unconfined-andchain | conditional | weak-or |
     unquoted`. `conditional` covers `if`/`elif`/`while`/`until`/`!` before the
     `cd`. `guarded` requires `exit` as the last command of a `|| { … }` body.
     `subshell-andchain` requires a `(`/`$(` opener; a `{` group is
     `unconfined-andchain`;
   - with `--check <paths…>`, prints `file:line:<class>: <text>` per violation
     and exits 1 if there are any;
   - with `--needs-helper <paths…>`, lists the files that contain any `cd`/`pushd`
     other than a single-group `$(cd … && pwd…)` derivation.

   Pure stdlib, no framework imports.

2. **Add `tests/lib/scratch_cwd.sh`** (above). No `set -e` in the sourced lib.
   The header comment covers: the t1815 history, both layers and why each
   exists, why the dir is read-only instead of trap-cleaned, the root retention
   rule, and the call-order rule (after `PROJECT_DIR` is derived, before any
   `ORIG_DIR="$(pwd)"` capture).

3. **Guard every violating site (≈587 in ≈172 files).** A one-off scratchpad
   rewrite driven by the scanner inserts ` || exit 1` right after the `cd`/
   `pushd` word and its arguments/redirections, for these shapes:
   - end of logical line;
   - before `;`;
   - before `&&`. `cd X || exit 1 && a` keeps the success path identical.

   It also quotes bare `$VAR`/`${VAR}` targets. It prints each rewrite and a
   per-file count, and never touches heredoc bodies.
   - `conditional` sites (none today) are converted by hand to
     `cd … || exit 1` plus explicit branch logic, or exempted with a reason.
   - The 17 `weak-or` sites (`|| true`, `|| return …`) are reviewed **by hand**.
     Each becomes `|| exit 1`, or keeps its form with
     `# cd-guard: <reason>` when failure is provably harmless. Example:
     `test_task_worktree_helper.sh:29` `cleanup(){ cd "$PROJECT_DIR" || true; …}`
     removes only absolute paths.
   - Any shape the rewrite cannot place is listed and fixed by hand.
   - Afterwards, `cd_guard_scan.py --check tests/*.sh tests/lib/*.sh` must
     report 0 violations.

4. **Adopt the helper** in every file `--needs-helper` lists, including
   `tests/test_data_branch_setup.sh`, whose inline t1815 block becomes the
   helper call so there is one definition. Insert it right after the
   `PROJECT_DIR=`/`REPO_ROOT=` derivation line and before any `ORIG_DIR="$(pwd)"`:
   ```bash
   # Start from an empty read-only dir, never the invoking one (t1826).
   . "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
   enter_scratch_cwd
   ```
   Before inserting, check each file for later `BASH_SOURCE`/`$0`/`dirname`
   re-derivations or `$(pwd)` captures relative to the starting cwd, and pin
   them to `$SCRIPT_DIR`.

5. **Enforcement test `tests/test_cd_guard_lint.sh`** (self-contained,
   `asserts.sh`, PASS/FAIL summary):
   - **Live tree:** `cd_guard_scan.py --check tests/*.sh tests/lib/*.sh` → 0
     violations. Every `--needs-helper` file calls `enter_scratch_cwd` before its
     first `cd`/`pushd` line.
   - **Scanner self-controls** (synthetic files in a temp dir, each asserting
     the expected class):
     - **re-entry:** guarded `cd "$PROJECT_DIR" || exit 1`, then unguarded
       `cd "$fixture"` → violation. This proves the rule is target-agnostic;
     - `REPO="$TMP/repo"; cd "$REPO"` → violation;
     - `(cd "$X" && a; b)` → violation;
     - a top-level `cd "$X" && cmd` → violation;
     - `cd $x` → unquoted violation;
     - `|| return 1` / `|| true` → weak-or violation;
     - `if cd "$x"; then …; fi`, `while cd "$x"; do … done`, and `! cd "$x"` →
       conditional violation. A behavioral companion runs
       `cd "$sentinel"; if cd /nonexistent; then :; fi; : > leaked` and confirms
       the file lands in the sentinel, which proves the form really is unsafe;
     - `{ cd "$x" && a; }` → unconfined-andchain violation;
     - `cd "$x" || { echo e; [[ -n "$y" ]] && exit 1; }` → violation (`exit` is
       not last);
     - `$(cd "$d" && pwd)`, `(cd "$x" && a && b)`, `cd "$x" || { echo e; exit 1; }`,
       and `# cd-guard: reason` → clean;
     - a `cd` inside a heredoc body → clean;
     - a helper-needing file that lacks `enter_scratch_cwd` → flagged.
   - **Helper behavior:**
     (a) after the call the cwd is empty, and not writable (skipped under
     root);
     (b) exported `GIT_DIR=<sentinel>/.git` → exit 1 with the refusal;
     (c) `TMPDIR` inside a sentinel repo → exit 1;
     (d) a non-empty scratch dir → exit 1 with the "not empty" message
     (private `TMPDIR`);
     (e) two calls with the same `TMPDIR` reuse one directory, so the count of
     `ait-test-cwd-*` entries stays 1 (bounded retention);
     (f) **leak control:** in a sentinel git repo as cwd, a script runs
     `cd "$PROJECT_DIR"`-style re-entry into the sentinel, then a forced-failing
     guarded fixture `cd`, then `: > aitasks/t1_alpha.md; git init -q .`. The
     sentinel is unchanged. The same script with the guard removed creates
     `aitasks/t1_alpha.md` in the sentinel, which proves the control can fail.

6. **Document** a new short section in `aidocs/framework/testing_conventions.md`,
   "Every `cd` in a bash test is `exit`-guarded". It covers: the rule and its
   accepted forms; why `set -e`, `|| return` and target names are not enough;
   the `# cd-guard:` exemption; the start-cwd helper and its root retention; and
   the lint that enforces it. Current-state prose only.

### Post-phase (risk mitigations)

1. [sample_cwd_regression_review] After the before/after runs, list every
   edited file whose baseline run skipped or failed (tmux/docker/environment
   dependent), so its run cannot prove behavior is unchanged. Read that file's
   diff and its top-level code for relative writes or relative script calls
   made before any `cd`, and for a `|| exit 1` that landed in a cleanup/trap
   path. Fix any found, and record the reviewed list in the Final
   Implementation Notes.

## Verification

All harness scripts, mutants and sentinels live in the scratchpad. Nothing is
stashed and nothing is restored in the shared worktree.

1. **Before/after runs.** Before editing, run every file the rewrite will touch
   on the current tree (4 in parallel, 300 s timeout each) and record exit
   status and PASS/FAIL counts. After the edits, run the same set again. Every
   file must match or improve. Environment-dependent files are compared
   like-for-like with their own baseline. Across the full after-run, the live
   `aitasks/` listing, mtimes and `./ait git status` are unchanged, and
   `ait-test-cwd-$(id -u)` is still empty.
2. **Per-file negative control, run mechanically for every edited file:**
   - Snapshot the repo with `git archive HEAD` plus the working-tree edits into
     `<scratch>/proj`, then `git init` and commit there (a sentinel standing in
     for the live repo).
   - Build pre-fix (HEAD) and post-fix copies of each test, with `SCRIPT_DIR`/
     `PROJECT_DIR` pinned to `<scratch>/proj`.
   - In both copies, force the first write-followed `cd`/`pushd` site to fail by
     replacing its target with `/nonexistent/ait-leak-probe`. Use Python with a
     printed substitution count that must be 1. Where the file has a live-root
     re-entry (`cd "$PROJECT_DIR"`/`$REPO_ROOT`), force the first fixture site
     **after** that re-entry, so the re-entry path itself is exercised.
   - Run each copy with cwd = a fresh sentinel repo, under a timeout. Record new
     files, `git status --porcelain` and commit counts in both the cwd sentinel
     and `<scratch>/proj`.
   - Expected: post-fix leaks nothing anywhere. The table records per file
     whether pre-fix leaked (control proven) or not, and why not.
3. `bash tests/test_cd_guard_lint.sh`: all PASS. Remove one guard in a scratch
   copy and point `--check` at it: it fails naming that line.
4. `shellcheck tests/lib/scratch_cwd.sh tests/test_cd_guard_lint.sh`: clean.
   shellcheck output of a sample of edited files shows no new findings compared
   with HEAD.

## Commits

The worktree is shared and `main` advances, so commit **only named paths**.
First re-check that no edited test file was changed by another session since
the rewrite. Commit with `git commit -- <every edited path>` and check
`git show --stat <sha>`. Message:
`bug: Guard every cd in bash tests and start them from a read-only cwd (t1826)`.
Commit the plan via `aitask_task_commit.sh`.

## Step 9 (Post-Implementation)

Profile fast, current branch: no merge. Run the gates (`risk_evaluated`) and
archive per task-workflow Step 9.

## Risk

### Code-health risk: medium
- The change touches ≈172 test files (≈587 guard insertions plus helper calls).
  `|| exit 1` in a path that used to tolerate a failed `cd` (cleanup, trap) now
  ends the file early. A file depending on the invoking cwd breaks. Both are
  caught by before/after runs, except in environment-dependent files that
  cannot run here · severity: medium · → mitigation: inline post-phase sample_cwd_regression_review
- A mechanical rewrite of shell source can misplace an insertion in unusual
  syntax. The scanner reports unplaceable shapes, `bash -n` runs on every
  edited file, and the before/after runs back it up · severity: medium ·
  → mitigation: none (accepted)
- A line-based scanner has false negatives (`eval`, computed commands). Layer 2
  covers them for the start cwd only · severity: low · → mitigation: none (accepted)
- Contributors must now guard every new `cd`. The lint names the line and the
  convention doc; that friction is the point · severity: low · → mitigation: none (accepted)

### Goal-achievement risk: medium
- The `t1_alpha.md` truncation stays unexplained. Transcripts, reflog and code
  search rule out a Claude-run test and any other writer in `tests/`, but not a
  git rewrite inside `.aitask-data` or a non-Claude agent · severity: medium ·
  → mitigation: live_tree_leak_tripwire
- The audit covers bash tests only. A Python test that `os.chdir`s into the
  repo and fails a fixture step is outside the lint (none found today) ·
  severity: low · → mitigation: live_tree_leak_tripwire

### Planned mitigations
- timing: after | name: live_tree_leak_tripwire | type: test | priority: low | effort: medium | inline_risk: low | added_complexity: medium | addresses: unexplained t1_alpha.md truncation; bash-only audit scope | desc: Snapshot the live aitasks/ (names, sizes, mtimes) before and after run_all_python_tests.sh and fail loudly if a suite run changed it
- timing: post-phase | name: sample_cwd_regression_review | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: cwd dependence and new early exits in edited files whose baseline cannot prove behavior unchanged | desc: Review edited files whose baseline run skipped or failed for relative writes before any cd and for exit guards in cleanup paths

## Post-Review Changes

### Change Request 1 (2026-09-17 13:45)
- **Requested by user:** (1) the unquoted-target check looked only at the first character after `cd`, so `cd -- $x || exit 1` and `cd -P $x || exit 1` passed as guarded although an empty `$x` sends them to `$HOME` with rc 0; (2) the negative-control harness excluded every `$( … )` site, so files whose only guard changes were inside command substitutions were reported as helper-only with no control run.
- **Changes made:** (1) `cd_guard_scan.py` now finds the directory operand after options (`-L`/`-P`/`-e`/`-@`), `--` and redirections (`_words`, `_unquoted_operand`); a missing operand or one starting with an unquoted `$` is `unquoted`. `test_cd_guard_lint.sh` gained `cd -- $x`, `cd -P $x` (violations) and quoted `--`/`-P --`+redirection (clean) cases, plus a behavioral probe proving `cd -- $empty || exit 1` writes into `$HOME`. (2) The scratchpad harness now picks the first violating site of any kind; the 88 previously skipped files were re-run.
- **Files affected:** `tests/lib/cd_guard_scan.py`, `tests/test_cd_guard_lint.sh` (harness is scratchpad-only).
- **Re-run result:** 8 of the 88 had real guard changes (`test_codeagent.sh`, `test_codeagent_trail.sh`, `test_codeagent_work_report.sh`, `test_explain_context_cross_repo.sh`, `test_merge_lock_concurrency.sh`, `test_revert_analyze_batch.sh`, `test_sandbox_docker_smoke.sh`, `test_verified_update_flags.sh`) — all inside `$( … )`. Pre-fix and post-fix both clean for all 8: the forced command substitutions run read-only commands (dry-run invokes, `--help`, `git show`), so the failure cannot write — no leak control is possible there, and none is claimed. The remaining 80 are genuinely helper-only (`test_data_branch_setup.sh`'s one `|| exit 1` match is inside a comment). Lint test 63/63; tree `--check` clean.

### Change Request 2 (2026-09-17 14:10)
- **Requested by user:** (1) ineffective guards still classified as accepted: `cd X || { echo "x; exit 1"; }` (exit inside a string), `cd X || exit 1 | cat` (exit in a pipeline subshell) and `cd X; echo '# cd-guard: harmless'` (marker inside a string) — bash continues in all three; (2) `cd 2>& 1 $x || exit 1` passed because a separated `>&`/`<&` operator's descriptor was taken as the operand; (3) the live-tree lint failed after concurrent t1823_2 added two cwd-changing tests without the helper; (4) SC2016 on the single-quoted HOME probe.
- **Changes made:** (1) `_terminating_exit` requires the `exit` word to be code and the command not piped/backgrounded (`_ends_command_here`); `|| { … }` is split on real (unquoted) `;`/newline separators, its last command must be such an exit, and the group itself must not be piped/backgrounded; unrecognised forms fail closed as `weak-or`. Exemptions now require the `# cd-guard:` match to sit in COMMENT context. (2) `_REDIR`/`_REDIR_ALONE` cover `>&`, `<&`, `&>>`, `<>`, `>|` as separate words, consuming the next word as the target. (3) `tests/test_brainstorm_discuss_skill_contract.sh` and `tests/test_skill_render_aitask_brainstorm_discuss.sh` (committed by t1823_2, unmodified in the worktree) got the helper block; their guarded `cd "$PROJECT_DIR" || exit 1` is untouched; both pass (7/7, 249/249). The pending t1823 siblings get an `ait note` about the rule. (4) Narrow `# shellcheck disable=SC2016` with a reason on the eval'd probes.
- **Regressions added (permanent, test_cd_guard_lint.sh):** classification cases for all of the above plus accepted controls (exit with its own redirection, multi-line guard group, quoted `}` inside the group); behavioral probes proving the string-exit, piped-exit, string-marker and `2>& 1 $empty` forms really continue. Lint 76/76; `shellcheck -x -P tests` clean; tree `--check` and `--helper-order` clean.
- **Files affected:** `tests/lib/cd_guard_scan.py`, `tests/test_cd_guard_lint.sh`, `tests/test_brainstorm_discuss_skill_contract.sh`, `tests/test_skill_render_aitask_brainstorm_discuss.sh`.

### Change Request 3 (2026-09-17 14:35)
- **Requested by user:** three non-terminating forms still classified `guarded`, all confirmed to print CONTINUED in bash: a guard group with a trailing redirection AND a pipeline (`|| { echo error; exit 1; } >/dev/null | cat`), an exit whose own redirection can fail before it runs (`|| exit 1 >/nonexistent/.../log`), and `|| exit"_missing" 1`, which bash concatenates into the command name `exit_missing`.
- **Changes made:** `_terminating_exit` is now deliberately narrow and fails closed. The `exit` word must be code, its only argument may be a numeric status or `$?`, and both the word and the status must end at a real terminator — so a quoted suffix no longer counts as a word boundary. `_terminator_ok` accepts end of input, newline, `;`, `)`, `}` and an `&&`/`||` chain (the exit runs either way, so the chain is dead code), and rejects `|`, `&` and every redirection. The `|| { … }` group applies the same rule to its last command and additionally requires its closing `}` to be followed by a real terminator, which is what rejects the redirected-and-piped group.
- **Deliberate consequence:** `cd X || exit 1 >&2` is now `weak-or`. Its case in the lint test flipped from `guarded` to `weak-or` — a redirection that fails means the exit never runs. No site in the tree uses that form.
- **Regressions added:** classification cases for the three reported forms plus accepted controls (`|| exit`, `|| exit $?`, `|| exit 1 && echo ok`, a guard group followed by `&&`), and behavioral probes proving each rejected form continues.
- **Verification:** lint 85/85; `--check` and `--helper-order` clean over `tests/*.sh` + `tests/lib/*.sh`; `shellcheck -x -P tests` clean.
- **Files affected:** `tests/lib/cd_guard_scan.py`, `tests/test_cd_guard_lint.sh`.

### Change Request 4 (2026-09-17 14:50)
- **Requested by user:** `_terminator_ok` accepted `&&`/`||` after the exit without asking whether the containing list is backgrounded later. `cd /nonexistent/... || exit 1 && echo ok & wait; echo CONTINUED` classified `guarded` but prints CONTINUED — the trailing `&` backgrounds the whole AND/OR list, so the exit ends only that background shell.
- **Changes made:** accepting an `&&`/`||` continuation now requires `_list_synchronous`, which scans to the end of that command list (`;`, newline, the enclosing `)`/`}`, or end of input) and rejects it if a `&` backgrounds the list first. Nested groups are skipped: a backgrounded **subshell** is accepted, because its `cd` never moved the caller's cwd. The synchronous chain the mechanical rewrite produces (`cd X || exit 1 && …`) stays accepted.
- **Regressions added:** classification cases for the backgrounded list (rejected), the same chain kept synchronous (accepted control) and a backgrounded subshell (accepted), plus a behavioral probe proving the backgrounded list continues in the old cwd.
- **Verification:** lint 89/89; `--check` and `--helper-order` clean; `shellcheck -x -P tests` clean.
- **Files affected:** `tests/lib/cd_guard_scan.py`, `tests/test_cd_guard_lint.sh`.

### Change Request 5 (2026-09-17 15:05)
- **Requested by user:** `_list_synchronous` still returns True at the first depth-zero `;`/newline, so a backgrounded list spread over a newline or containing a keyword compound (`if …; fi &`, a `for` loop) classifies `guarded` and prints CONTINUED.
- **Finding: not a defect — and the CR4 change it extends was an over-correction.** Measured directly (`bash -c`, cwd = a probe dir): `cd /nonexistent/... || exit 1 && : > leaked &  wait` writes NO file, and neither does the compound-command nor the newline-continued variant, while the unguarded control `cd /nonexistent/...; : > leaked & wait` DOES write one. `&` backgrounds the **whole** list, the `cd` included, so a failed cd leaves only that background subshell in the old cwd and the `exit` ends it before anything else in the list runs. The parent never attempted the `cd`, so its cwd was never wrong — the printed CONTINUED is the parent proceeding correctly, not a command running after a failed cd. A pipeline is different, and stays rejected: `cd X || exit 1 | cat` runs the exit in a subshell while the PARENT carries on past the failed cd (that probe does leak).
- **Changes made:** removed `_list_synchronous` (CR4) and restored the unconditional acceptance of an `&&`/`||` continuation, with the reason recorded at the call site. A direct `&` or `|` on the exit itself stays rejected, conservatively — no site in the tree uses either.
- **Regressions added (permanent):** `no_leak_probe` asserting no leak for the backgrounded list, the backgrounded compound-command list and the newline-continued list, paired with a `leak_probe` control that leaks with the guard removed — so the claim is measured rather than asserted. The CR4 classification case flipped back to `guarded`.
- **Verification:** lint 92/92; `--check` and `--helper-order` clean; `shellcheck -x -P tests` clean.
- **Files affected:** `tests/lib/cd_guard_scan.py`, `tests/test_cd_guard_lint.sh`.

## Final Implementation Notes
- **Actual work done:** Added `tests/lib/cd_guard_scan.py` (the rule + `--check` / `--json` / `--needs-helper` / `--helper-order`), `tests/lib/scratch_cwd.sh` (`enter_scratch_cwd`) and `tests/test_cd_guard_lint.sh` (92 assertions). Guarded 544 sites mechanically plus 17 by hand (13 `|| return`/`|| true` → `|| exit 1`; 4 `# cd-guard:` exemptions), and inserted the helper block into 240 test files — including the two t1823_2 files committed mid-task, and `test_data_branch_setup.sh`, whose inline t1815 block now calls the helper. Documented the convention in `aidocs/framework/testing_conventions.md`.
- **Deviations from plan:** (a) The plan sized the work at ~587 sites / ~172 files from a prototype; the finished scanner (heredoc/quote-aware, `$(…)`-aware) found 544 auto-fixable sites in 161 files, plus helper adoption in 240. (b) The helper's root path is the same single per-user directory rather than a per-run `mktemp` — retention stays at one directory per uid. (c) Five review rounds hardened the scanner well past the planned rule (see Post-Review Changes 1-5); one of them (CR5) found the reported behavior was not a defect and the preceding CR4 fix was an over-correction, so it was reverted and replaced with measured probes.
- **Issues encountered:** The first after-run showed 5 real regressions in tmux tests — the helper block landed before a `BASH_SOURCE`-relative derivation, which then resolved against the scratch dir. Fixed by moving the block below those lines, and the scanner now flags that ordering (`--helper-order`). My first move script keyed on a line regex and pushed the block into two heredoc bodies (`test_ls_boardcol_filter.sh`, `test_explain_context.sh`); reverted, and the ordering check now uses the scanner's quote/heredoc mask. `test_task_git.sh:709` was rewritten although `(cd a && cd b && pwd)` was already safe; the scanner now accepts later elements of a confined `&&` chain (`_chain_opener`) and the edit was reverted. A `>\|` double-escape in the redirection regex briefly matched every word.
- **Key decisions:** The rule is target-agnostic — `$REPO` is a fixture in some files and `$REPO_ROOT` the live repo in others, so any name-based exemption would pass the exact leak this task exists to close. Only `exit` counts as a guard (`|| return` relies on callers that demonstrably do not check). Accepted syntax is narrow and fails closed rather than growing into a shell parser. The helper is read-only and trap-free because 48 adopting files install their own `trap … EXIT`.
- **Upstream defects identified:** None
- **Verification results:**
  - Before/after runs of all 240 touched files: after matches baseline. Six were non-zero in the baseline; five still are, with identical logs (three are live-tmux environment refusals), and `test_skill_verify.sh` improved (baseline timeout → pass). `test_skill_render_uniform.sh` failed once on a same-second mtime and passes on rerun.
  - Per-file negative control (forced `cd` failure, sentinel cwd + sentinel repo copy): post-fix leaked nothing in all 160 files with a forceable site; pre-fix leaked in 50 of them (control proven). 80 files are genuinely helper-only. The 8 whose only guards are inside `$( … )` are clean in both variants — those substitutions run read-only commands, so no leak control is possible and none is claimed.
  - Live tree unchanged across the full after-run (identical `aitasks/`+`aiplans/` listing with sizes and mtimes); `/tmp/ait-test-cwd-$(id -u)` still empty; no fixture-named files.
  - `bash tests/test_cd_guard_lint.sh` 92/92; `--check` and `--helper-order` clean; `shellcheck -x -P tests tests/lib/scratch_cwd.sh tests/test_cd_guard_lint.sh` clean; `bash -n` on every edited file.
  - Post-phase `sample_cwd_regression_review`: reviewed the files whose run cannot prove behavior — `test_frozen_agents_acceptance.sh`, `test_frozen_standin_spike.sh`, `test_monitor_shadow_spawn_live.sh` (live-tmux refusals, helper-only or helper + one `cd "$REPO_ROOT"` guard), `test_codeagent_explore_relay.sh` (live part skipped), `test_sandbox_docker_smoke.sh`, plus the two pre-existing failures `test_aitask_merge_boardgroup.sh` and `test_workflow_phase_standalone.sh`. None writes relative paths before its first `cd`. The only cleanup-path guards added are `cd "$ORIG_DIR" || exit 1` in the crew `cleanup_test_repo` helpers and `cd "$PROJECT_DIR" || exit 1` in a few cleanups — both targets always exist; `test_task_worktree_helper.sh`'s `|| true` cleanup kept its form under an exemption.
- **Secondary goal (t1_alpha.md truncation):** still unexplained, and no second leak source exists in `tests/`. `tests/test_boardcol_update.sh` does write that name (t1815 said nothing else did) but always with non-empty content, inside a `pushd`ed mktemp dir. The Claude transcripts active at 06:07-06:10 UTC ran no test; the data-branch reflog has nothing at 09:09:18. Remaining candidates, unproven: a git rewrite inside `.aitask-data` (stash/restore/autostash, invisible to the HEAD reflog) or a non-Claude agent. Recorded here as the audit's answer.
