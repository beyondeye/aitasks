---
Task: t2290_stop_tests_and_helpers_leaking_tmp_dirs.md
Base branch: main
Output branch: main
---

# t2290 — Stop tests and helpers leaking `/tmp` dirs

## Context

`/tmp` is a tmpfs with a 1M-inode cap. It filled up twice. Some of that is
aitasks: tests and helpers leave directories behind on every run. Measured now
(own uid): `roadmap_run_*` 972, `ait_txn_snap_*` 69, `ait_assert_counters_*` 58,
`ait_ril_pending_*` 28, `tmp.*` 244, `t79_2_driver*` 540, `t45_*` 160. Inodes
are at 72%.

Attribution done during planning, by reading files only:
- **`t79_2_driver*`**: not ours. The name comes from `thinking_backend`
  (`scripts/tests/test_verify_t79_2.py`).
- **`tmp.*` holding `app/heavy-lock` and `admit*`**: not ours. That naming
  comes from `thinking_app` (`tools/verification/heavy-lock-characterize.sh`).
  Nothing in aitasks produces `heavy-lock` or `admit-ample`.
- **`t45_*` (`t45_4guard*`: `bin/ deadline marker state`)**: no producer found
  in aitasks. Most likely a sibling agent driver. Step 6 confirms this
  empirically.
- **`ait_txn_snap_*`**: most of them are EMPTY dirs. That means
  `txn_snap_init` ran and its cleanup never did. Cause:
  `tests/test_txn_snapshot.sh` calls `txn_snap_init` back to back (lines 136-165)
  with no cleanup in between. `txn_snap_init` overwrites `_TXN_SNAP_DIR` without
  dropping the previous directory. The dirs that do contain blobs are the
  deliberate "restore incomplete, keep the bytes" path, written by the C-group
  tests into the global `/tmp`. Production: `aitask_fold_mark.sh:530-533` runs
  `txn_snap_init` and then `txn_snap_add` (which can `die`) BEFORE it installs
  the EXIT trap, so a die there leaks the dir.
- **`ait_ril_pending_*`**: `_ril_move_seam` simulates a crash with
  `kill -KILL "$BASHPID"`, so no trap can run. That is correct for a crash test.
  The tests that arm it (`test_release_notify.sh`,
  `test_release_notify_branch_mode.sh`) let `mktemp` write into the global
  `TMPDIR`.
- **`ait_assert_counters_*`**: the file is removed only by
  `assert_counters_load` in the footer. A test that dies or times out early
  leaks it. An EXIT trap installed at init would not help: 30 of the 32 files
  that opt in install their own `trap … EXIT` after `assert_counters_init`, which
  overwrites it.

## Plan

### Pre-phase (risk mitigations)
1. [shared_runner_hunk_gate] Before editing `tests/run_all_python_tests.sh`
   or `CLAUDE.md`, run `git diff -- tests/run_all_python_tests.sh CLAUDE.md`
   and `git log -1 --format=%h -- tests/run_all_python_tests.sh`. Record which
   hunks belong to other sessions; the known one is t2281's
   `AIT_QUESTIONS_STATE_DIR` export. Make my edits around them.

   **Commit through a pinned-base plumbing commit.**
   - `git commit -- <f>` commits the whole working-tree file, foreign hunk
     included.
   - The shared index already holds other sessions' staged `A` entries, so a
     bare `git commit` is unsafe too.
   - A private index plus porcelain `git commit` is also unsafe. If another
     session commits after `read-tree`, `git commit` takes the NEW HEAD as
     parent but writes the OLD tree, which silently reverts that commit.

   So the base is pinned explicitly, and the ref moves only by compare-and-swap.
   No hooks are configured (`.git/hooks` has only samples, and
   `core.hooksPath` is unset), so `commit-tree` skips nothing.
   ```bash
   S=<scratch>/commit; mkdir -p "$S"
   base=$(git rev-parse --verify HEAD^{commit})          # pin
   # my.patch = diff of each touched file between $base and $base+only-my-edits
   # (for a file with no foreign hunk: `git diff $base -- <f>`; otherwise build
   # it from `git show $base:<f>` + my edits applied to a scratch copy).
   GIT_INDEX_FILE="$S/idx" git read-tree "$base"
   GIT_INDEX_FILE="$S/idx" git apply --cached --check "$S/my.patch"
   GIT_INDEX_FILE="$S/idx" git apply --cached "$S/my.patch"
   tree=$(GIT_INDEX_FILE="$S/idx" git write-tree)
   git diff --name-status "$base" "$tree"     # MUST list exactly my files
   git diff "$base" "$tree"                   # inspect: only t2290 lines
   new=$(git commit-tree "$tree" -p "$base" -F "$S/msg")
   ```

   **Hold the real-index lock across publication.** The shared index must
   never hold base entries for my paths while HEAD already names `$new`. In
   that window another session's ordinary `git commit` would take `$new` as
   parent and write the stale entries, reverting t2290. An isolated repro has
   confirmed this happens. So the lock is taken, and reconciliation decided,
   **before** the ref moves:

   ```bash
   idx=$(git rev-parse --git-path index); lk="$idx.lock"
   ( set -o noclobber; : > "$lk" ) 2>/dev/null   # O_EXCL create == git's own lock
   ```
   1. **Preconditions, before the lock:** no split index (`core.splitIndex`
      unset, and no `sharedindex.*` in the git dir). If one is present, stop
      and do not publish.
   2. **Acquire `index.lock`.** Retry up to 5 times, 0.5s apart. If it is
      still held, stop and do not publish.

      While this session holds it, no porcelain commit or staging can run:
      `git commit` / `git add` hold `index.lock` for their whole run, so
      none is mid-flight either.
   3. `cp "$idx" "$S/real"`. This copy is authoritative while the lock is
      held.
   4. For each touched path `p`, compare
      `GIT_INDEX_FILE="$S/real" git ls-files -s -- p` with `$base:p`'s mode
      and blob, or absent vs absent.
      - **Any path differs** (foreign staging): `rm -f "$lk"`, **do not
        publish**, and report the path and its staged blob. The user decides;
        nothing has changed anywhere.
   5. Prepare the new index on the copy:
      `GIT_INDEX_FILE="$S/real" git update-index --add --cacheinfo <mode>,<$new:p blob>,p`
      for each path. Verify that the `ls-files -s` output before and after
      differs only in those paths' entries. On any failure, `rm -f "$lk"`
      and do not publish.
   6. **Publish the ref:** `git update-ref -m "commit: t2290" HEAD "$new" "$base"`
      (CAS).
      - **It refuses** (HEAD moved through a plumbing writer or a ref update
        that does not take the index lock): `rm -f "$lk"`, discard `$new`, and
        redo from `base=`. Nothing was published.
   7. **Publish the index immediately**, still holding the lock:
      `cat "$S/real" > "$lk" && mv "$lk" "$idx"`. The `mv` is the release.
      - **It fails after the ref moved:** report loudly. HEAD is `$new` and
        the index is stale. The report names the exact
        `git update-index --cacheinfo` commands and the revert hazard. Then
        `rm -f "$lk"`.

   Every "stop" before step 6 leaves the branch and the index exactly as they
   were. No path exposes a new HEAD on top of an unreconciled shared index,
   apart from step 7's single-`mv` failure, which is reported.

   Finally `git status --short -- <my files>`. Expected: only foreign, unstaged
   hunks remain.

### 1. `tests/test_roadmap_run.py` (confirmed leak)
In `_RunHarness.setUp`, directly after `mkdtemp`, add
`self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)`, and import
`shutil` if it is not already imported. `addCleanup` runs even when `setUp`
fails later on, which `tearDown` does not.

### 2. `.aitask-scripts/lib/txn_snapshot.sh`: make `txn_snap_init` re-entrant
At the top of `txn_snap_init`, before `mktemp`, release any registry dir it
owns: call `txn_snap_cleanup`. `txn_snap_cleanup` already keeps the dir when
`_TXN_SNAP_RESTORE_INCOMPLETE=true`, so a dir kept for recovery survives. The
report has already named that dir to the user, and `txn_snap_init` then resets
the flag for the new registry. Add a comment saying why. This fixes the
back-to-back inits in the test and any production path that calls `txn_begin`
twice in one process.

### 3. `.aitask-scripts/aitask_fold_mark.sh`: arm the trap before the snapshot loop
Reorder lines 530-534 to:
```bash
txn_snap_init
trap '_fold_abort_cleanup' EXIT
ait_archive_rearm_exit_trap
for _p in "${fold_paths[@]}"; do txn_snap_add "$_p"; done
_fold_txn_active=true
```
Before `_fold_txn_active=true`, `_fold_abort_cleanup` only runs
`txn_snap_cleanup`, so a die inside `txn_snap_add` now drops the dir and rolls
nothing back, which is correct because nothing has been mutated yet. The
top-level trap line keeps its exact text. `test_fold_mark.sh:1689-1714` pins
that column-0 line by `grep -cxF`, so it stays at count 1. Read
`test_fold_mark.sh:1600-1660` (the arming-site check) before editing, then run
it.

### 4. Test-side: send deliberate leftovers into each test's own scratch dir
- `tests/test_txn_snapshot.sh`: after `TMP="$(mktemp -d)"`, set
  `export TMPDIR="$TMP/tmp"; mkdir -p "$TMPDIR"`. The kept C-group dirs then
  land under `$TMP`, which the existing `cleanup` trap removes. Check first that
  no assertion compares a path against `/tmp` literally.
- `tests/test_release_notify.sh` and `tests/test_release_notify_branch_mode.sh`:
  do the same with `TMPDIR` under their `$TMP`, set after `TMP` is created, so
  the SIGKILL seam's `ait_ril_pending_*` files land in a dir that gets cleaned.
  Production `release_issue_ledger.sh` stays unchanged. A real SIGKILL cannot
  run cleanup, and the seam has to stay faithful to a real crash.

### 5. `tests/lib/asserts.sh`: reclaim stale counter files
- Name the file `ait_assert_counters_<pid>_XXXXXX`, where `<pid>` is `$$` of
  the process that runs `assert_counters_init`, which is the top-level test
  shell.
- In `assert_counters_init`, before creating the file, sweep
  `${TMPDIR:-/tmp}/ait_assert_counters_*`. Remove a file only when all of these
  hold:
  - its name carries a pid;
  - `kill -0 <pid>` fails (owner gone);
  - it is older than 60 minutes (`find -mmin +60`, which is portable).

  Leave legacy files with no pid in the name alone. For a live owner, the pid
  check and the age check together make a false delete very unlikely. If a
  false delete did happen, `assert_counters_load` already fails closed on a
  missing record, so it would show up as a FAIL and never as a false PASS.
- Why sweep instead of trapping: tests overwrite the EXIT trap (30 of 32). A
  sweep also covers SIGKILL and timeouts.
- Why this sweep is safe when the guard-dir one was not: the counter file has
  exactly one reader, the owner's footer. Once the owner is dead, nobody
  reads it again. A surviving orphan subshell that appends afterwards only
  recreates a sentinel-less file under the same pid-tagged name, which the
  next sweep collects. It never corrupts a live run. A guard dir, in
  contrast, is the working directory of possibly still-running workers.
- Extend the existing counter tests. Find them with `grep -l
  assert_counters_init tests/test_*assert*`, or use the t1207 test. Add three
  cases: a dead-pid old file is reclaimed, a live-pid file is kept, a legacy
  name is kept.

### 6. Guard: per-run `TMPDIR` with a leftover report (warn-only)
New `tests/lib/tmpdir_guard.sh`, sourced. The whole lifecycle lives in the
lib, so the runner and the wrapper cannot drift apart. It has four functions:

- **`tmpdir_guard_begin <label>`**
  - `mktemp -d "${TMPDIR:-/tmp}/ait_<label>_$$_XXXXXX"`. Remember the
    original `TMPDIR` and export the new dir as `TMPDIR`.
  - The guard dir always lives under the **original** `TMPDIR` (default
    `/tmp`), never under `$HOME`. Redirecting into `/home` breaks
    `tests/test_shadow_q_harness.py`, because its sandbox refuses any ancestor
    that contains `.claude` (see memory test-env-tmp-quota). Begin refuses
    any computed path containing `/.claude`.
  - **No automatic reclamation.** A SIGKILLed runner cannot run its handler,
    and its process-group workers may outlive it. Deleting such a dir safely
    would need liveness evidence (pgids, `/proc` cwd/fd scans, platform
    fallbacks), and that is out of scope here. Begin only **reports**:
    `TMPDIR GUARD: <n> guard dir(s) from earlier runs remain: <names…>
    (likely a killed run; remove by hand once no process uses them)`, capped
    at 5 names, for `ait_<label>_*` dirs other than its own. It never deletes
    them. Automatic reclamation goes to a follow-up task (step 8).
  - Install traps through a chain helper that prepends to any existing trap,
    the same pattern as `txn_chain_exit_trap`. EXIT runs
    `tmpdir_guard_end`. INT, TERM and HUP record the signal, terminate the
    child (below), and `exit $((128+n))`, which then runs the EXIT handler.
- **`tmpdir_guard_run <cmd…>`** runs one phase:
  - Under `set -m`, start `"$@" </dev/null &` so the child gets its own
    process group, then `wait`.
  - Why: a trapped signal is otherwise deferred until a foreground child
    exits on its own. Under a non-job-control shell, background children
    ignore SIGINT, so forwarding INT would do nothing.
  - On a caught signal, the handler sends `kill -TERM -- -<pgid>` to the whole
    group, so xdist workers and nested `bash` tests are included. It then
    waits for the group to exit, polling `kill -0 -- -<pgid>` for up to 10s,
    then sends `kill -KILL -- -<pgid>`. Only after that does anything get
    removed, so no child is still writing into the dir.
  - The phase's real exit status comes back as `$?`. The rc contract is
    unchanged.
- **`tmpdir_guard_end`** is idempotent, guarded by a done-flag.
  - It lists the top-level entries left in the guard dir. If there are any,
    it prints `TMPDIR LEFTOVERS (<n>): <names…>` to stderr, capped at 20
    names with "… and K more".
  - Then it runs `chmod -R u+w` (some tests `chmod a-w`) and `rm -rf`, and
    restores `TMPDIR`.
  - It never changes the exit status, and every command is guarded.
    Warn-only.
- **Ordering:** the runner calls `tmpdir_guard_end` explicitly **before** its
  verdict banner, so the banner stays the last line on the normal path (t1179,
  pinned by `tests/test_python_runner_exit_status.sh`). The EXIT trap is then
  a no-op. On a signal no banner is printed, as today. The report and cleanup
  still run, and the exit is 128+n.

How the runner and wrapper use it:

- **`tests/run_all_python_tests.sh`:**
  - Call `tmpdir_guard_begin pyrun` after the `AIT_QUESTIONS_STATE_DIR`
    export. That export is t2281's uncommitted hunk. Placing the guard after
    it keeps that path's current value.
  - Route both phases through `tmpdir_guard_run`.
  - Place `tmpdir_guard_begin` after argument parsing and after the "no test
    files selected" `exit 2` check, directly before `set +e`. The early exits
    then create no guard dir. Any later error exit, including `set -e` aborts,
    is still covered by the EXIT trap.
  - xdist workers inherit the env, and pytest's `tmp_path` base moves under
    the guard dir.
- **New `tests/run_shell_test.sh <test.sh> [args…]`:** the same three calls
  around `bash <test.sh> "$@"`. It returns the test's own status. Document it
  in CLAUDE.md `### Testing` with two lines: optional, and the tool for
  hunting leaks. Running `bash tests/test_x.sh` directly stays the default.

Tests, in a new `tests/test_tmpdir_guard.sh`:

- **(a)** A stub test leaves a file: the report names it, the dir is gone,
  and the status passes through for both 0 and 3.
- **(b)** A clean stub: no report.
- **(c)** A read-only leftover is still removed.
- **(d) Interrupted run:**
  - Setup: a stub sleeps in a child, the wrapper gets `kill -TERM <wrapper>`,
    and the stub's child writes a file every 0.1s.
  - Expect:
    - exit 143;
    - the report is printed;
    - the guard dir is gone;
    - no stub process survives (`kill -0` on the recorded pids);
    - nothing is recreated after removal (re-check after 1s).
- **(e)** INT behaves the same, with exit 130.
- **(f)** A pre-existing `ait_<label>_*` dir from an "earlier run" is reported
  by name and **left in place** with its contents intact. Its own dir is not
  reported.
- **(g)** Existing EXIT traps chain rather than being clobbered.
- Also run `tests/test_python_runner_exit_status.sh` to confirm the banner is
  still the last line.

**Shared-file gate:** see Pre-phase `shared_runner_hunk_gate`. Never commit
t2281's line.

### 7. Empirical attribution (task scope item 2)
- Run the whole Python suite through the guarded runner.
- Run every `tests/test_*.sh` through `tests/run_shell_test.sh` with xargs at
  `-P 4`, in the background, logging each test's leftover report into the
  scratchpad. Live/tmux tests are included. Their tmux sockets live under
  `TMUX_TMPDIR`/`/tmp` (`tests/lib/tmux_isolation.sh`), never under `TMPDIR`,
  so the guard does not affect them.
- **The guard's report is not complete evidence.** It sees only its private
  `TMPDIR`, and tests bypass it on purpose. Examples:
  - `tests/test_setup_python_install.sh:18` creates under `/tmp`;
  - `tests/test_trails_focus_mailbox_live.py:52` passes `dir="/tmp"`;
  - `tests/lib/tmux_isolation.sh` allocates `TMUX_TMPDIR` outside `TMPDIR`.

  So step 7 has two more parts.
- **Static audit of the bypasses.** Inventory every explicit `/tmp` /
  `TMPDIR`-override site in `tests/` and `.aitask-scripts/` with one grep
  regex: `mktemp … -p /tmp` / `--tmpdir=/tmp`, `dir="/tmp"` or
  `dir='/tmp'`, literal `"/tmp/…"`, `TMUX_TMPDIR=`, and `TMPDIR=`
  reassignments. 64 files match the first cut. For each site, read its
  cleanup and classify it:
  - `cleaned on every exit` (trap or addCleanup covers it);
  - `cleaned on success only` (fix, if small);
  - `not cleaned` (fix);
  - `intentionally persistent` (name why).

  The table goes into Final Implementation Notes.
- **Global-`/tmp` observation as a second channel.**
  - Before the post-phase run, `touch` a marker. After it, list
    `find /tmp -maxdepth 1 -user $(id -u) -newer <marker>`. Exclude the
    session's own `/tmp/claude-<uid>`.
  - Concurrent agents write to `/tmp` during that window, so a new entry
    counts as attributed to aitasks only when its prefix or contents match a
    producer site found by the static audit or the guard report. Everything
    else is listed as "observed during the run, unattributed".
- **Group findings by producer.**
  - Fix small aitasks-owned producers (missing trap/`addCleanup`) in this
    task.
  - List the rest as file and prefix pairs, with one follow-up task if there
    are more than a handful.
- **Ownership claims need positive producer evidence, never absence.**
  - `t79_2_driver*` → thinking_backend: its source names it.
  - `tmp.*` holding `app/heavy-lock` / `admit*` → thinking_app: its source
    names it.
  - `t45_*` stays **"unattributed: no producer found in aitasks or the
    registered sibling repos"**. Its absence from the guarded runs is
    recorded as supporting evidence only.
  - Any remaining `tmp.*` with other contents stays unattributed the same way.

### Post-phase (risk mitigations)
1. [full_guarded_suite_run] After steps 1-7 are implemented, run
   `bash tests/run_all_python_tests.sh` (guarded) with
   `set -o pipefail; … 2>&1 | tee <scratch>/py.log`. Then run every
   `tests/test_*.sh` through `tests/run_shell_test.sh` with `xargs -P 4`,
   logging per-test status and leftovers to `<scratch>/sh/<name>.log`.
   - Compare failures against a baseline run of the same tests unguarded
     (plain `bash`). Any test that passes unguarded but fails guarded is a
     guard regression: fix it in this task, either in the guard or in the
     test's hard-coded `/tmp` assumption.
   - Tabulate the leftovers by producer, using all three channels from step 7:
     the guard reports, the static bypass audit, and the global-`/tmp` marker
     diff.
   - Then interrupt one real guarded Python run with `kill -TERM` about 20s
     in. Confirm three things:
     - the guard dir is gone;
     - no pytest or xdist process remains (`pgrep -f` on the run's pgid);
     - the exit status is 143.
   - Done when:
     - there are zero guard-only failures;
     - the interrupted run cleans up;
     - every leftover is fixed, listed with an owner backed by producer
       evidence, or explicitly marked unattributed.

### 8. Follow-up task
After implementation, create one task with `aitask_create.sh --batch`:
**"Reclaim guard dirs left by SIGKILLed test runs"** (enhancement,
priority low). It covers:
- per-run metadata (owner pid plus phase pgids);
- a liveness check: dead owner, dead pgids, no cwd/fd user via `/proc` or
  `lsof`, and retention when this cannot be verified;
- the dead-wrapper-with-surviving-writer case.

Point it at `tests/lib/tmpdir_guard.sh` and this plan.

### 9. Step 9 (Post-Implementation)
Commit the code (`bug: … (t2290)`) through the private-index procedure in the
pre-phase. It applies to every touched file, because the shared index holds
other sessions' staged entries. Commit the plan via
`aitask_task_commit.sh`. Then archive per task-workflow Step 9.

## Verification
- `bash tests/test_txn_snapshot.sh`, `bash tests/test_fold_mark.sh`,
  `bash tests/test_release_notify.sh`,
  `bash tests/test_release_notify_branch_mode.sh`, the counters test, and
  `bash tests/test_tmpdir_guard.sh`: each passes. Run each through
  `tests/run_shell_test.sh` too: no leftovers.
- `python -m pytest tests/test_roadmap_run.py`, then
  `ls /tmp/roadmap_run_* | wc -l`: the count is unchanged before and after.
- `bash tests/run_all_python_tests.sh`: the last line is the verdict, and the
  leftover report (if any) comes before it.
- `bash tests/test_python_runner_exit_status.sh`,
  `bash tests/test_serial_carveout_doc_drift.sh`.
- `shellcheck` on the touched `.sh` files.

## Risk

### Code-health risk: low
- The per-run `TMPDIR` changes the environment of every Python test. A test
  that assumes `TMPDIR` is `/tmp`, or builds a long unix-socket path under
  `TMPDIR`, could break · severity: low (residual: addressed by inline
  post-phase full_guarded_suite_run) · → mitigation: inline post-phase
  full_guarded_suite_run
- `run_all_python_tests.sh` carries another in-flight task's (t2281)
  uncommitted hunk. A careless commit would ship it under t2290 · severity:
  low (residual: addressed by inline pre-phase shared_runner_hunk_gate) · →
  mitigation: inline pre-phase shared_runner_hunk_gate
- The asserts.sh sweep deletes files. A wrong pid/age test could delete a live
  record · severity: low · → mitigation: requires dead pid AND age over 60m; a
  false delete fails closed as a FAIL
- The signal-forwarding phase runner (`set -m`, process-group TERM→KILL)
  changes how every phase process is started. Stdin becomes `/dev/null`, and
  a test that expects to share the runner's process group could behave
  differently · severity: low · → mitigation: the post-phase
  full_guarded_suite_run compares against an unguarded baseline, plus test
  cases (d)-(e)
- The plumbing commit (`commit-tree` + CAS `update-ref`) bypasses porcelain
  safety nets · severity: low · → mitigation: pinned base, full
  `diff $base $tree` inspection before the ref moves, and CAS refusal on any
  interleaving
- Real-index reconciliation could overwrite a concurrently staged entry ·
  severity: low · → mitigation: the compare and the replace both run while
  this session holds `index.lock` (O_EXCL), published by rename. A held lock,
  a split index or any failed step defers with an explicit report
- Guard dirs from SIGKILLed runs are not reclaimed automatically. They
  accumulate until removed by hand · severity: low · → mitigation: begin
  reports them by name; automatic reclamation is the follow-up task from
  step 8

### Goal-achievement risk: medium
- Most of the `/tmp` volume (`tmp.*` 1.3G, `t79_2_driver*`, `t45_*`) is not
  aitasks'. This task only stops the aitasks share · severity: medium · →
  mitigation: none. Out of scope by the task's own definition; recorded as
  not-ours
- The guard covers only runs that go through the runner or wrapper. Direct
  `bash tests/test_x.sh` runs still leak from any unfixed producer ·
  severity: low (residual: addressed by inline post-phase
  full_guarded_suite_run) · → mitigation: inline post-phase
  full_guarded_suite_run

### Planned mitigations
- timing: pre-phase | name: shared_runner_hunk_gate | type: chore | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health (another task's uncommitted hunk in the shared runner) | desc: stage only t2290's hunks in run_all_python_tests.sh / CLAUDE.md via git apply --cached
- timing: post-phase | name: full_guarded_suite_run | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: low | addresses: code-health (TMPDIR assumptions) + goal-achievement (guard coverage) | desc: full Python + shell suite under the guard vs an unguarded baseline; fix guard-only failures, tabulate leftovers
