---
Task: t2028_crew_git_ops_strand_or_commit_unfinished_rebase.md
Base branch: main
Output branch: main
---

# t2028 — crew git writers never strand, nor commit into, an unfinished merge or rebase

## Context

The crew worktree (`.aitask-crews/crew-<id>/`) is shared by the runner, the
agents and the crew CLIs. t2018 made the runner's own pull safe and taught it
to *hold* when `crew_merge_state()` reports an unfinished merge or rebase
(`PULL_UNSAFE`). Three paths can still create such a state, or conclude one:

1. **The addwork / setmode publish step, `crew_pull_rebase`**
   (`.aitask-scripts/lib/agentcrew_utils.sh:170`, moved there by t2024). It
   does a bounded fetch and then a live-worktree `git rebase --no-autostash`. A
   conflict stops the rebase in place, and nobody reports it. addwork still
   prints `ADDED:`, so brainstorm goes on to write the agent's input into a
   worktree that is mid-rebase.
2. **The addwork / setmode commit steps themselves.**
   `aitask_crew_addwork.sh:330-337` and `aitask_crew_setmode.sh:120-129`
   mutate, `git add` and `git commit` with no state check. Against a stopped
   rebase that conflicts on `w1_status.yaml`, setmode returns `UPDATED:`, moves
   the detached HEAD and commits the conflict markers (reproduced in review).
3. **The Python commit path, `git_commit_push_if_changes`**
   (`.aitask-scripts/agentcrew/agentcrew_utils.py:552`). It runs `git add -A`
   and `git commit` unconditionally, for the runner and for `ait crew status
   set` terminal transitions.

Two lines of the architecture doc are also stale (lines 222 and 313), and the
stale-agent action block at lines 354-357 repeats the line-222 claim.

### Design decisions

- **Report, never auto-abort.** `git rebase --abort` is a hard reset. It
  discards anything another process wrote *or staged* while the rebase was
  stopped, and no worktree-versus-index check sees a staged write (confirmed in
  review). In a shared worktree, the safety of an abort cannot be proved, so a
  stopped rebase is left in place and reported. To make stops rare, a rebase is
  only opened after git proves it clean in memory, which is t2018's rule.
- **A crew commit cannot conclude or join another operation, by
  construction.** `git commit` concludes a merge (it reads MERGE_HEAD) and
  commits onto a rebase's detached HEAD. So any check placed before it leaves a
  window, and any check after it has to guess which commit was ours. Review
  showed that a parent-equals-`pre` check falsely rejects a healthy crew when
  another writer commits on top. Every crew commit therefore uses plumbing:
  1. `tree = write-tree`. This fails on unmerged entries, which is fail-closed.
  2. Re-check the state.
  3. `new = commit-tree tree -p pre` (with `-S` when `commit.gpgSign` is set,
     like `_sign_args`).
  4. `update-ref <branch> new pre`, an atomic compare-and-swap on the
     *branch ref*.

  `commit-tree` never reads MERGE_HEAD, and `update-ref` on the named branch
  never touches a detached HEAD. The swap succeeds only if the branch is still
  exactly `pre`, so `new` is reliably identified as ours and is a plain child
  of `pre`.
- **Why a new operation cannot slip in.** `git merge` and `git rebase` refuse
  to start on an index with staged changes (confirmed in review). So once this
  writer has staged, another operation can only begin after someone *commits*
  those staged changes. That moves the branch, and our swap then fails with no
  side effects. A failed swap is ordinary concurrency, not interference: the
  writer retries from the state check, at most 3 attempts. When the tree
  already equals HEAD's tree, the content was committed by the other writer,
  and that is success with no empty commit. There is no post-commit guessing
  and no quarantine.

## Implementation

### 1. Shell — `.aitask-scripts/lib/agentcrew_utils.sh`

- **`crew_merge_state <wt>`** (new) prints `merge_in_progress`,
  `rebase_in_progress`, `unmerged_paths` or `probe_failed`, or nothing when
  clean. It is a line-for-line mirror of the Python `crew_merge_state`:
  `rev-parse -q --verify MERGE_HEAD` (rc 1 means none, any other rc means
  `probe_failed`); then `rev-parse --git-path rebase-merge|rebase-apply`,
  resolved against `<wt>` when relative; then `ls-files -u`. A "keep in sync"
  comment on both sides, as `crew_is_terminal` has.
- **`crew_unsafe_report <wt> <state> <what-happened>`** writes the one warning
  shape to stderr: "crew worktree <top> has <an unfinished merge | an
  unfinished rebase | unmerged paths | a state git could not report> (<state>):
  <what-happened>. The crew runner holds until it is resolved; `git -C <top>
  status` shows it (`git -C <top> rebase --abort` / `merge --abort` undoes it
  and resets the tracked files)." The text map is the same as
  `brainstorm_crew._MERGE_STATE_TEXT`. `<top>` is `git rev-parse
  --show-toplevel`, so setmode's `.` reads correctly. Use `warn` for fixed text
  and raw `printf … >&2` for git-provided paths, following the `crew_push`
  precedent.
- **`crew_require_clean <wt> <what-happened>`**: when `crew_merge_state` is
  non-empty, it calls `crew_unsafe_report` and then `die`s.
- **`_crew_sign_args <wt>`**, mirroring `_sign_args`: `config --type=bool
  commit.gpgSign` rc 1 → no flag; `true` → `-S`; any other failure means the
  setting cannot be read, so return 1 (no commit).
- **`crew_commit_paths <wt> <message> <path>...`** is the one guarded commit
  used by addwork and setmode. Up to 3 attempts:
  1. `crew_require_clean "$wt" "<paths> written but not staged or committed"`
  2. `git -C "$wt" add -- <paths>`
  3. `ref=$(symbolic-ref -q HEAD)`. If this fails, it is a detached HEAD
     outside any state the probe names: report and `die`. Then
     `pre=$(rev-parse --verify HEAD^{commit})`.
  4. `tree=$(write-tree)`. On failure, run `crew_require_clean` (which names
     the state) and otherwise `die` with git's message.
  5. `crew_require_clean "$wt" "<paths> staged but not committed"`. This
     catches a state that appeared during the add or the write-tree; we never
     unstage, because a `reset` would rewrite the other operation's index.
  6. If `tree` equals `$(rev-parse "$pre^{tree}")` → nothing is left to
     commit (another writer committed it): return 0.
  7. `new=$(commit-tree $sign "$tree" -p "$pre" -m "$message")`.
  8. `git -C "$wt" update-ref -m "commit: $message" "$ref" "$new" "$pre"`.
     - On success, return 0.
     - On failure, the branch moved: loop back to step 1.
  9. After the attempts are exhausted, `die` with "<paths> staged but not
     committed: the crew branch kept moving".

  Hooks do not run for these commits, which is the same trade-off t2018
  documented for the runner's synthetic merge commit. State that in the
  function comment, along with why plumbing is used at all.

### 2. `crew_pull_rebase` — same file

1. Run `crew_merge_state` first. If it reports a state, call
   `crew_unsafe_report … "not rebased or published"` and return 2.
2. Upstream resolution and the bounded fetch stay unchanged. These failures
   still return 1 quietly, as today.
3. **Proof gate:** run `git -C "$wt" merge-tree --write-tree --no-messages
   --name-only HEAD '@{u}'`, resetting `rc=0` first.
   - `0` → rebase.
   - `129` (git < 2.38) → rebase as today. The runner also defers diverged
     merges there, so skipping would stop old git from ever linearising.
   - `1` → warn "crew branch not rebased onto its upstream: it conflicts in
     <paths>; left unchanged and not published". The paths are lines 2+ of the
     output, mirroring `_merge_diverged`. Return 1. The worktree is never
     touched.
   - any other status → warn that the proof failed, and return 1 without
     rebasing (fail closed).
4. `git -C "$wt" rebase --no-autostash --quiet >/dev/null 2>&1` → on success,
   return 0.
5. On failure, run `crew_merge_state` again:
   - empty → the rebase refused before starting (a dirty tree, the common case
     with live heartbeats). Return 1 quietly, as today.
   - any state → **leave it**: `crew_unsafe_report … "the rebase onto the
     upstream stopped and was left in progress (an abort would reset files
     other crew processes may have written or staged)"`. Return 2.
6. Header comment: the proof gate, the never-abort rule and why, and the return
   contract (0 rebased; 1 not rebased, with the worktree as it was; 2 an
   unsafe state is left in place).

### 3. Callers

- **`aitask_crew_addwork.sh`:**
  - Pre-mutation guard: `crew_require_clean "$WT_PATH" "nothing was written"`
    after the validations and before the first write (before `# --- Create
    agent files ---`, ~line 177).
  - Replace the commit subshell (lines 330-337) with `crew_commit_paths
    "$WT_PATH" "crew: Add agent …" <same paths>`, keeping `$GIT_ADD_GROUPS`
    in its unquoted, optional form.
  - Publish: `pr_rc=0; crew_pull_rebase "$WT_PATH" || pr_rc=$?`. When `pr_rc`
    is 2: skip the push, print no `ADDED:` line, and `die "Agent '<name>' is
    registered (committed) but not published: the crew worktree is left unsafe
    (see above)"`. A non-zero exit is deliberate: brainstorm's `_run_addwork`
    then raises instead of writing the agent's input into a worktree that an
    abort would reset. The `_AIT_CREW_STOP` flow is unchanged.
- **`aitask_crew_setmode.sh`:**
  - Pre-mutation guard after the status gate and before the `tmpfile`
    rewrite: `crew_require_clean "$WT_PATH" "launch_mode was not changed"`.
  - In the commit block, use `crew_commit_paths . "<message>"
    "${AGENT_NAME}_status.yaml"`. For `crew_pull_rebase .`, rc 2 skips
    `crew_push` and makes the subshell `die`, so `UPDATED:` is never printed.

### 4. Python — `.aitask-scripts/agentcrew/agentcrew_utils.py`

- Add the new helper **`_commit_index(worktree, message) -> tuple[str, str]`**.
  It is the same plumbing sequence as `crew_commit_paths` steps 3-8, over
  whatever is staged, reusing `_commit_id`, `_sign_args` and `crew_merge_state`.
  It returns:
  - `("committed", new)`;
  - `("nothing", "")` when the tree equals HEAD's;
  - `("unsafe", state)`;
  - `("moved", "")` when the swap failed;
  - `("failed", detail)`.
- **Publication contract** (stated in the docstring): a call that saw staged
  work publishes the branch once that work is on it, **whoever committed it**.
  `ait crew status set` relies on its terminal transition reaching origin on
  its own (`agentcrew_status.py:138-142`). A concurrent writer that commits the
  shared index, including our staged change, must not silently cancel that
  push. A call that never had staged work stays a no-op, as today.
- `git_commit_push_if_changes`, with `had_work = False` and up to 3 attempts:
  1. If `crew_merge_state` reports a state, warn and return. Nothing is
     staged, committed or pushed.
  2. `git add -A`. If `diff --cached --quiet` shows nothing staged: when
     `had_work` is set, our earlier staged work was committed by another
     writer, so **push** and return; otherwise return. If there is staged
     work, set `had_work = True`.
  3. `_commit_index`:
     - `committed` → push;
     - `nothing` (the tree equals HEAD's; already committed by another
       writer) → **push**;
     - `unsafe` → warn "staged but not committed" and return (never unstage);
     - `moved` → retry from step 1;
     - `failed` → warn and return.
  4. After the attempts are exhausted, warn "the crew branch kept moving".

  The push stays subject to the guard at the start of the attempt: a state
  check runs at step 1 of the same attempt, and a push never runs after an
  `unsafe` result. Pushing HEAD's ancestry is safe in itself, because only
  completed commits reach the branch ref.
- Warnings always go to stderr, batch mode included: this is the only signal
  that a terminal `ait crew status set` transition was left uncommitted, and
  stderr is not machine-parsed. Format, like `git_pull`'s:
  `[HH:MM:SS] git commit skipped (<message>): <reason> in <wt>; …`.
- Callers are unchanged: the runner's next `git_pull` returns `PULL_UNSAFE`
  and holds, and `cmd_set` has already recorded the status locally, which the
  runner reads.
- Docstrings: explain why plumbing is used, the retry, and that hooks do not
  run.

### 5. Docs

- `aidocs/agentcrew/agentcrew_architecture.md`:
  - line 222 → "Log stale agents (heartbeat timeout exceeded; status
    unchanged)";
  - lines 354-357 ("Action on stale agent: Status set to Error …") → logged
    only, status unchanged;
  - line 313 → the real git writers: the runner (`add -A`, each iteration),
    `ait crew status set` (terminal transitions), and `addwork` / `setmode`
    (their own files plus the rebase-publish).
  - Add the rule: every crew commit refuses while a merge or rebase is
    unfinished, and commits via `commit-tree` plus a compare-and-swap
    `update-ref`, so it can never conclude or join one. A rebase is opened only
    when proven clean and is never auto-aborted.
- `website/content/docs/commands/crew.md`: after the `PULL_UNSAFE` paragraph
  (~line 180), add one short current-state paragraph:
  - while such a state exists, `addwork` and `setmode` refuse and change
    nothing, and runner and `ait crew status set` commits are skipped with a
    warning;
  - when the rebase would conflict, the branch is left un-rebased; a rebase
    that stops anyway is left in place and reported, and `addwork` exits
    non-zero.

  Then run `python3 check_links.py --build`.

### 6. Tests — extend `tests/test_crew_pull_no_autostash.sh` (cells 16-22)

**Fixtures.**
- Two new peer changes for `setup_crew_remote_fixture`:
  - `status_conflict`: the peer rewrites w1's `launch_mode` to another value.
  - `meta_conflict`: the peer appends a different agent at the point in the
    `_crew_meta.yaml` `agents` list where addwork appends.
- A PATH `git` wrapper stub, written once like the harness, that execs the real
  git by absolute path (never recursing) and logs every subcommand to
  `HARNESS_GIT_LOG`. Its hooks:
  - `HARNESS_GIT_MERGE_TREE_RC=<rc>` answers `merge-tree` with that status.
  - `HARNESS_GIT_AFTER_REBASE_STAGE=<file>` appends a line to that tracked file
    *and stages it* after a `rebase` that left a rebase state.
  - `HARNESS_GIT_INJECT=<kind>@<point>` runs a concurrent writer once at
    `<point>`, which is one of:
    - `after-add`;
    - `after-write-tree`, before the step-5 state check;
    - `before-update-ref`, after the check and `commit-tree`, so only the
      swap stands between the writer and the branch;
    - `after-update-ref`.

    `<kind>` is one of:
    - `merge`: the explicit two-step writer. It commits the shared staged
      index (`commit -qm "concurrent writer"`), consuming the staged paths of
      the operation under test, then opens `merge --no-commit --no-ff` of a
      side commit prepared on a disjoint path. `git merge` refuses on a dirty
      index, so a bare merge injection would fail before creating any state.
    - `commit`: an ordinary concurrent writer that **commits the shared
      index**. It writes and stages a heartbeat line in `_runner_alive.yaml`
      and runs `commit -qm "concurrent heartbeat"`, which consumes the staged
      change of the operation under test. The result is a plain single-parent
      commit, with no merge or rebase.
    - `commit-own`: an ordinary concurrent writer that **commits only its own
      path**. It writes the heartbeat line, then runs `commit -qm "concurrent
      heartbeat" --only -- _runner_alive.yaml`. Our staged change stays staged
      and is *not* consumed, so the retry genuinely has work to commit.

    The fixture asserts which shape it produced. After a `commit` injection,
    the concurrent commit contains the operation's change (`git show
    <concurrent>:<path>`). After a `commit-own` injection, it does not, and
    the change is still staged.

    It prints `INJECTED:ok <kind> <concurrent-commit> [<merge-head>]` only when
    every step succeeded (and for `merge`, MERGE_HEAD exists), and
    `INJECTED:failed <step> <rc>` otherwise.
- The Python harness gains `commit <wt> --inject <kind>@<point>`, with the
  same writers and the same `INJECTED:` contract, through its existing
  `git_cmd` seam (points keyed on the `add` / `write-tree` / `update-ref`
  subcommands).
- **Every injection cell asserts `INJECTED:ok` before asserting anything about
  the guard**, so a setup failure is never read as a guard result.
- Helpers:
  - `wt_state_snapshot`: HEAD, `symbolic-ref`, `ls-files -s`,
    `crew_merge_state`;
  - `assert_linear <cell> <n>`: every commit in the last n is single-parent;
  - `assert_no_unsafe_report <cell>`: stderr has no "unfinished" / "git
    commit skipped".

**Cells.**
- **16 (proof gate, git ≥ 2.38, `need_merge_tree`):**
  - 16a: setmode vs `status_conflict` → rc 0 and `UPDATED:`. No state. HEAD is
    attached at setmode's commit, the remote is unchanged, and stderr names
    `w1_status.yaml` and "not rebased".
  - 16b: addwork vs `meta_conflict` → the same, with `ADDED:w2`.
- **17 (a stopped rebase is left and reported; wrapper merge-tree → 129):**
  - 17a: setmode vs `status_conflict` → rc ≠ 0, no `UPDATED:`,
    `rebase_in_progress`, the remote is unchanged, and stderr carries the
    report and its remedy.
  - 17b: addwork vs `meta_conflict` → rc ≠ 0, no `ADDED:`, no push, and the
    state is left.
- **18 (a staged foreign write survives):** as 17a, plus
  `HARNESS_GIT_AFTER_REBASE_STAGE=_runner_alive.yaml`. The injected line is
  present in the worktree **and** in the index (`git show
  :_runner_alive.yaml`), the state is still `rebase_in_progress`, and nothing
  aborted it.
- **19 (proof error; wrapper merge-tree → 128):** setmode → there is no
  `rebase` in the git log, the worktree is untouched beyond setmode's own
  commit, and stderr says the proof failed.
- **20 (CLI against an existing state; real scripts):** one cell for each of
  {setmode, addwork} × {merge left open by hand, stopped rebase made by hand}.
  Each asserts rc ≠ 0, no `UPDATED:` / `ADDED:`, and `wt_state_snapshot`
  identical before and after. setmode's status file bytes are unchanged, and
  addwork wrote no `w2_*` file.
- **21 (concurrent writers during setmode's commit; shell):** each cell first
  asserts `INJECTED:ok`.
  - 21a: `merge@after-add` → rc ≠ 0; MERGE_HEAD is still present; HEAD equals
    the concurrent writer's commit (setmode made no commit); stderr says
    "staged but not committed"; the remote is unchanged.
  - 21b: `merge@after-write-tree` → the step-5 check refuses before any
    commit object is used. The assertions are those of 21a.
  - 21b': `merge@before-update-ref` → the swap fails because the concurrent
    writer moved the branch, and the retry's step-1 check refuses. The
    assertions are those of 21a, and no commit concluded the merge: MERGE_HEAD
    is present, and HEAD is still the concurrent writer's commit, not
    setmode's dangling `new`.
  - 21c **control (genuine retry)**: `commit-own@before-update-ref` → the
    swap fails, and the retry commits setmode's change **on top of** the
    concurrent commit. Assert: rc 0, `UPDATED:`, HEAD's parent is the
    concurrent commit and HEAD contains setmode's `launch_mode`,
    `assert_linear`, `assert_no_unsafe_report`, and the push happened (remote
    tip == local tip).
  - 21c' **control (consumed)**: `commit@before-update-ref` → the concurrent
    writer committed setmode's staged change, so the retry finds nothing left
    to commit. Assert: rc 0, `UPDATED:`, HEAD is the concurrent commit and
    contains setmode's `launch_mode` (no empty commit), `assert_linear`,
    `assert_no_unsafe_report`, and the push happened (remote tip == local
    tip).
  - 21d **control**: `commit@after-update-ref` (an ordinary commit lands right
    after setmode's commit) → rc 0, `UPDATED:`, `assert_linear`,
    `assert_no_unsafe_report`, and a later setmode (another mode) still
    succeeds: normal operation continues.
  - 21e **control**: `commit@after-add` (the concurrent writer's commit
    includes setmode's staged path) → rc 0, `UPDATED:`, no empty commit (HEAD
    is the concurrent commit), `assert_no_unsafe_report`, and the push
    happened.
- **22 (Python `git_commit_push_if_changes`):** each injection cell first
  asserts `INJECTED:ok`.
  - 22a: a stopped rebase plus a dirty `w1_alive.yaml` → no commit, HEAD and
    the state are unchanged, the file is still unstaged, and stderr says "git
    commit skipped … rebase_in_progress".
  - 22b: `merge@after-add` and 22c: `merge@before-update-ref` → MERGE_HEAD is
    still present, there is no commit on top of the concurrent writer's (none
    concluding the merge), and the warning appears.
  - 22d **control (genuine retry)**: `commit-own@before-update-ref` with a
    terminal-status change staged by the call → the swap fails, and the retry
    commits the change on top of the concurrent commit. No warning,
    `assert_linear`, the status change is in HEAD, and the push happened. A
    runner `--once` iteration afterwards runs normally (no `PULL_UNSAFE`).
  - 22d' **control (consumed; the review's reproduction)**:
    `commit@before-update-ref` → the concurrent commit contains the
    terminal-status change. Assert that it is in HEAD, that there is no empty
    commit and no warning, `assert_linear`, and that **the push happened**
    (remote tip == local tip, so the transition reached origin).
  - 22e **control**: `commit@after-update-ref` → no warning, `assert_linear`,
    and a follow-up call commits normally.
  - 22f: `status set --status Completed` during a stopped rebase → the status
    is written but not committed, and the warning appears.
  - 22g control: after `rebase --abort`, the same call commits and pushes.
- Update the file header (cells 16-22, t2028).

## Verification

- **Red proof:** add a scratch `git worktree add` at HEAD (non-destructive) and
  copy in the new test file. Cells 16-18, 20, 21a/b and 22a-c, f must fail
  against the old code (stranded rebases, commits into merges or rebases);
  then remove the worktree. The controls (21c-e, 22d, e, g) are expected green
  on both sides: they pin that the new design does not regress healthy
  concurrency. Cell 19's proof-error branch is new behaviour.
- **Green:** `bash tests/test_crew_pull_no_autostash.sh`, plus the regression
  set:
  - `test_crew_publish_upstream.sh`;
  - `test_brainstorm_addwork_deadline.sh` (D2's slow rebase is
    non-conflicting, so the proof passes and the rebase still runs; D1's
    signer stub must also see `commit-tree -S` the way it saw `commit`, so
    check it);
  - `test_crew_setmode.sh`, `test_crew_addwork_output_instructions.sh`,
    `test_crew_groups.sh`, `test_crew_init.sh`, `test_crew_cleanup.sh`;
  - `test_agentcrew_terminal_push.sh`, `test_crew_runner.sh`,
    `test_crew_git_noninteractive.sh`, `test_agentcrew_error_recovery.sh`;
  - the Python crew/brainstorm modules through
    `bash tests/run_all_python_tests.sh --test-dir <scratch dir linking
    test_brainstorm_crew.py, test_agentcrew_rollup.py>`.
- `shellcheck` on the three edited shell files.
- `cd website && python3 check_links.py --build`.
- Step 9 (Post-Implementation): commit the code, docs and tests as
  `bug: … (t2028)`, then archive via the task-workflow.

## Risk

### Code-health risk: medium
- Crew commits move from `git commit` to plumbing (`write-tree`,
  `commit-tree`, compare-and-swap `update-ref`). Hooks no longer run, the HEAD
  reflog is not written, and signing must be passed explicitly, so anything
  relying on `git commit` side effects in crew worktrees changes ·
  severity: medium · → mitigation: none. This is the same trade-off t2018
  accepted for the runner's merge commit. `_sign_args` / `_crew_sign_args` keep
  signing, and the deadline test's signer stub (D1/D2) plus the
  publish/terminal-push suites exercise the real paths.
- addwork now exits non-zero when it leaves an unsafe worktree, which changes
  what brainstorm's `_run_addwork` sees (it raises, where before it went on to
  write input) · severity: low · → mitigation: none. This is intended, covered
  by 17b, and `_run_addwork` already turns a non-zero exit into a
  `RuntimeError` carrying stderr.
- The shell and Python `crew_merge_state` / commit sequences are parallel
  implementations that could drift · severity: low · → mitigation: none,
  covered by sync comments and by mirrored shell/Python cells (20/22a,
  21a-e/22b-e).

### Goal-achievement risk: low
- The no-slip-in argument rests on `git merge` / `git rebase` refusing to
  start on an index with staged changes · severity: low · → mitigation: none.
  This is confirmed in review, and a writer that bypasses it must still move
  the branch to commit, which fails the swap. Cells 21a/b and 22b/c inject the
  real sequence.
