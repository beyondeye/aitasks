---
Task: t1789_fix_task_push_automerge_loop_flaky_tests.md
Base branch: main
Output branch: main
---

# t1789 — Automerge-loop flake: pin rerere + auto-maintenance off across the task-data reconciliation window

## Context

`tests/test_task_push.sh` Tests 54 and 56 (the t1727 multi-round auto-merge
replay) fail intermittently, and only under load. The task asked for the flake
to be made deterministic first, then for its cause to be fixed (not the retry
count).

**Diagnosed (evidence, not inference).** An instrumented harness replayed Test
54's fixture with every `_ait_data_git` call and every merge-driver run traced
(scratchpad `repro54.sh`):

| variant (60 iterations each, run in parallel for load) | failures |
|---|---|
| user's real config (×2 runs) | **6 / 120** |
| `GIT_CONFIG_GLOBAL=/dev/null` | 0 / 60 |
| `rerere.enabled=false` | 0 / 60 |
| `maintenance.auto=false` | 0 / 60 |
| `maintenance.autoDetach=false` | 0 / 60 |

All 6 failures show the same trace: round 1's `git rebase --continue` commits
A′, starts picking B, and dies with
`fatal: Unable to create '.git/MERGE_RR.lock': File exists` (rc 128). The
user's global config has `rerere.enabled=true` and the tests inherit it. The
commit step records a rerere resolution and triggers
`git maintenance run --auto`, which detaches (`maintenance.autoDetach` defaults
to true). That background run contends for rerere's `MERGE_RR.lock` while the
sequencer records B's preimage. Because the pick dies mid-way, round 2's
`--continue` sees "staged changes", the loop returns 2, and the rebase is
correctly aborted → `failed`. The loop's fail-closed logic is right; the git
environment leaking into a framework-owned multi-step reconciliation is the
defect.

**Also a production defect.** `_task_pull_rebase` (every pick/push) and
`ait sync` run the same pipeline in the real, long-lived data worktree. For a
user with rerere enabled, its rr-cache is non-empty, so even the first pick can
race. Worst case the race hits `rebase --abort` (`rerere clear` takes the same
lock) and wedges the shared worktree.

**The fix has two halves, and each is tested separately.**
- **rerere off.** No command of ours ever opens `MERGE_RR.lock`, so a
  concurrent rerere-gc from *any* source (our own earlier commands, the sweep's
  commits, another session) cannot break the rebase. It also stops rerere
  autoupdate from pre-staging resolutions behind the engine's
  `--diff-filter=U` probe.
- **Auto-maintenance off.** No git command inside the reconciliation window
  spawns a detached `git maintenance run`, which can also run `gc --auto`
  (`pack-refs`, reflog expire) and contend for *ref* locks while the rebase
  updates refs. The window starts at the fetch that feeds the rebase. That is
  the post-review correction: `ait sync`'s `do_fetch` and its push-retry
  refetch run immediately before `do_pull_rebase`, so they are in the window.
  Maintenance still runs on the next ordinary git command.

Current-branch mode (profile `fast`): no worktree, work on `main`.
Note: `main` advanced mid-planning (`e2f12c499`, t1731). It touched only
`aitask_sync.sh` among this plan's targets; the line numbers below are
post-t1731.

## Scope rule (stated once, in the constant's comment)

Pinned: every **porcelain** git command that **feeds, starts, advances or
aborts** a framework-owned rebase of the task data.

| site | file:line (current) | how |
|---|---|---|
| `_task_pull_rebase` pull (its own fetch child inherits `-c`) | `lib/task_utils.sh:1274` | `_ait_data_git "${AIT_RECONCILE_GIT_OPTS[@]}" pull --rebase --quiet` |
| `ait_rebase_abort_if_ours` abort | `lib/task_utils.sh:1158` | `"$runner" "${AIT_RECONCILE_GIT_OPTS[@]}" rebase --abort` |
| `ait_automerge_advance` continue / skip | `lib/task_automerge.sh:203,219` | `_ait_data_git "${AIT_RECONCILE_GIT_OPTS[@]}" rebase --continue` / `--skip` |
| `do_fetch` | `aitask_sync.sh:1803` | `_git_with_timeout "${AIT_RECONCILE_GIT_OPTS[@]}" fetch origin` |
| `do_push` retry refetch | `aitask_sync.sh:1995` | same |
| `do_pull_rebase` pull | `aitask_sync.sh:1837` | `task_git "${AIT_RECONCILE_GIT_OPTS[@]}" pull --rebase --quiet` |
| `do_pull_rebase` aborts ×5 | `aitask_sync.sh:1866,1874,1927,1932,1938` | `_ait_data_git "${AIT_RECONCILE_GIT_OPTS[@]}" rebase --abort` |

**Deliberately not pinned (the rationale goes in the comment):**
- the two `merge --ff-only` convergence steps (`aitask_sync.sh:1722`,
  guarded merge; `:2165`, `main`) and `task_data_converge`'s
  fetch + ff-only merge (`task_utils.sh:1580,1604`). No rebase follows them
  on the success path, and an ff-only merge never invokes rerere.
- the sweep's auto-commits (`auto_commit`). They precede the window, and they
  go through the shared commit helper every writer uses. The rerere half
  already makes the rebase immune to any rerere-gc they spawn; see the Risk
  residual.

## Implementation

### 0. Empirical check (scratchpad, git 2.55): decides the final site list

Using `GIT_TRACE=<file>` in a throwaway repo, confirm that each of these logs
`run_command: … maintenance run --auto` when unpinned and does not when run with
`-c maintenance.auto=false`:
- `fetch`
- `pull --rebase` (this also confirms `-c` propagates to its fetch and rebase
  children)
- `rebase --continue`
- `rebase --abort`

Also check `push`. If `push` spawns maintenance too, add `do_push`'s initial
push (`aitask_sync.sh:1957`) to the table, since it precedes the
refetch → rebase in the same run.

Check the trace timing that Tests 63/16/17 depend on:
- with `maintenance.autoDetach=false` set in the repo, the unpinned command's
  `trace: run_command: git maintenance run` line is present **by the time the
  command returns**, every time (loop it ≥50× under load);
- with the default detach, whether any maintenance-related trace line arrives
  *after* return, which is the race the trace tests must not depend on.

Record the results in the plan's Final Implementation Notes.

### 1. `lib/task_utils.sh`

- Next to `AIT_AUTOMERGE_GAVE_UP_SENTINEL` (~line 1188), add
  `AIT_RECONCILE_GIT_OPTS=(-c rerere.enabled=false -c maintenance.auto=false)`.
  Its comment covers:
  - the scope rule above, including the exclusions and why;
  - the `MERGE_RR.lock` race and the ref-lock contention from detached
    maintenance;
  - that rerere autoupdate conflicts with the `--diff-filter=U` probe contract;
  - "maintenance still runs on the next ordinary git command";
  - that the options go **before** the subcommand, so `task_git` (whose guard
    reads `$1`) can carry them only for a non-recovery verb.
- Apply it at the two task_utils sites in the table. Update
  `ait_rebase_abort_if_ours`'s doc comment: "`<runner>` is invoked as
  `"$runner" <git options> rebase --abort`".

### 2. `lib/task_automerge.sh` — `ait_automerge_advance`

Apply it to `--continue` and `--skip`, with a one-line pointer comment. The probe
lines are unchanged. Test 13's pin (calls *to* the helpers) and the A1 row's
`:203` anchor are unaffected.

### 3. `aitask_sync.sh`

- Fetch, refetch and pull, as in the table. Guard behaviour is identical:
  `pull` was never read-only or a recovery verb, so the state check still runs;
  `_git_with_timeout` just forwards `"$@"` after `-C`.
- The five aborts → `_ait_data_git` + options. `task_git` would refuse a
  leading `-c` mid-rebase (`_ait_git_subcmd_is_recovery` reads `$1`), and
  bypassing the guard is behaviour-identical because it always admitted
  `--abort`.
- Confirm `AIT_RECONCILE_GIT_OPTS` is in scope there (the script sources
  `task_utils.sh`; the array is read at call time).

### 4. Tests

**Existing stub to adapt.** `test_task_push.sh` Test 41's `_ait_data_git`
override keys on `$1 == rebase && $2 == --abort`; it must skip leading
`-c <k=v>` pairs, or the real abort runs. The audit found nothing else to
change:
- Test 42's `stub_removes`/`stub_fails` and Test 46's `ctrl_runner` ignore
  their args.
- The `test_sync_branch_mode_automerge.sh` shims loop over all args or grep
  `$*` substrings.
- No sync-suite shim (including the t1731 suites) is keyed on a git positional
  arg.

**rerere half: `MERGE_RR.lock` held for the whole run.** This is the race made
deterministic.
- **Test 61** (`test_task_push.sh`): the Test 54 two-commit fixture with
  `git config rerere.enabled true` set **locally** and a pre-created
  `.git/MERGE_RR.lock`.
  - Positive control: a raw `git pull --rebase` fails naming `MERGE_RR.lock`.
    Clean up with `git -c rerere.enabled=false rebase --abort`, then assert
    `probe_wedge` is empty.
  - Then `task_sync`: `synced`, `TASK_SYNC_AUTOMERGED=1`, `(2 file(s))`,
    2 ahead, no wedge, and the lock file **still exists** (rerere never ran).
    Remove the lock afterwards.
- **Test 62**: Test 50's body-conflict fixture, rerere on locally, lock held.
  Expect `failed` / `rebase_conflict` and `probe_wedge` empty: the abort landed
  instead of dying in `rerere clear`. Remove the lock, then
  `assert_next_commit_succeeds`.
- **Test 15** (`test_sync_branch_mode_automerge.sh`): `setup_branch_mode_repos`,
  rerere on in the data worktree, and a held lock at
  `$(git -C .aitask-data rev-parse --git-path MERGE_RR.lock)`.
  - Positive control as in Test 1: a raw fetch + rebase fails naming the lock;
    clean up with a rerere-off abort.
  - `run_sync` → `AUTOMERGED`, no unmerged paths, `assert_no_rebase_wedge`.

**Maintenance half: nothing inside the window spawns
`git maintenance run --auto`.** This is observed directly through `GIT_TRACE`,
independent of any lock.

**Trace-only fixture rule (applies to Tests 63, 16 and 17, including their
positive and mutant controls).**
- Set `git config maintenance.autoDetach false` in the fixture repo (for branch
  mode, `git -C .aitask-data config …`) **before** any fixture command runs.
  The unpinned control and mutant commands then run maintenance in the
  foreground, and their trace is complete when the command returns.
  Otherwise a detached child can write after `task_sync` / `run_sync` returns,
  and an unpinned mutant could look clean just because the assertion won the
  scheduling race.
- The pinned commands are unaffected: `-c maintenance.auto=false` on the command
  line outranks the repo config, and nothing is spawned at all.
- Anchor every assertion on the **spawning parent's** line,
  `run_command: git maintenance run`, never on the child's own output.
- The held-lock tests (61, 62, 15) keep default detach: they remain the
  separate real-concurrency proof.

- **Test 63** (`test_task_push.sh`): the two-commit fixture, `task_sync` run
  with `GIT_TRACE="$TEST_TMPDIR/trace63"` exported for the call. `task_sync`
  runs only `remote`/`rev-parse`/`rev-list` plus the pinned reconciliation
  commands. Assert the trace has no `maintenance run`.
  - Positive control: `GIT_TRACE=… git fetch origin` in the same fixture *does*
    log it, so the observation isn't vacuous.
- **Test 16** (`test_sync_branch_mode_automerge.sh`), the `do_fetch` site.
  - Add an argv-keyed PATH shim in the file's existing style. For any
    invocation containing `fetch`, `pull` or `rebase` it execs the real git
    with `GIT_TRACE=<log>` and appends the argv to `<bindir>/git.log`. It traces
    only those commands, so the sweep's commits, outside the window, cannot
    pollute the verdict.
  - `run_sync` through the shim: `AUTOMERGED`, and the trace log has no
    `maintenance run`.
  - Positive control: an unpinned `git -C .aitask-data fetch origin` through the
    same shim is logged with `maintenance run`.
  - **Committed mutant control**, in the `assert_defect_present` style of Tests
    10–14. In a second fixture, a new `_sync_replace` removes the options from
    the fixture copy's `do_fetch` line: an exactly-once literal replacement,
    mirroring `_automerge_replace`. The anchor is the
    `|| fetch_exit=$?` line, which is distinct from the refetch's
    `|| refetch_exit=$?`. The defect must be observable: the log now contains
    `maintenance run`.
- **Test 17**, the push-retry refetch site. Enable the sync seams (the marker
  under `AITASKS_LOCK_DIR`) and set `AIT_SYNC_SEAM_pre_push` to a hook that
  pushes a new commit from pc2, so the first push is rejected and `do_push`
  takes the refetch → `do_pull_rebase` → retry path. Through the Test 16 shim,
  assert:
  - the refetch ran (`git.log` has two `fetch origin` entries);
  - the run converged;
  - no `maintenance run` was logged.
  - **Committed mutant control:** strip the options from the refetch line only
    (`|| refetch_exit=$?` anchor); the defect must be observable.

**Mutant runs during implementation (not committed)** for the task_utils and
task_automerge sites. Revert the options per site in a scratch copy and confirm
the matching tests go red:
- the pull and `--continue` sites: Tests 61 and 63
- the abort site: Test 62
- the sync pull site: Tests 15 and 16

Record the outcomes in Final Implementation Notes.

**Not done (deliberately):** no `GIT_CONFIG_GLOBAL=/dev/null` suite
isolation. Real-config runs are what exposed this production race, and every
new test pins its own config locally. The crew scripts' code-branch
`git pull --rebase` calls are outside this pipeline and are untouched.

## Verification

1. `bash tests/test_task_push.sh` and `bash tests/test_sync_branch_mode_automerge.sh`
   pass, including the new tests and their controls.
2. The neighbouring suites pass: `test_sync.sh`, `test_sync_guarded_merge.sh`
   (t1731), `test_sync_rebase_gate.sh`, `test_sync_deferral_and_quarantine.sh`,
   `test_sync_auto_commit_scoping.sh`, `test_sync_protect_paths.sh`,
   `test_task_git.sh`, `test_pick_own_scoped_commit.sh`,
   `test_remote_drift_check.sh`.
3. Flake gone under load with the real global config (rerere on): the repro
   harness at 2×60 iterations in parallel shows **0 failures** (baseline 6/120),
   and 6 concurrent full `test_task_push.sh` runs ×2 are all green (baseline
   1/12 red).
4. The step-0 trace results and the uncommitted mutant outcomes are recorded.
5. `shellcheck` on the three changed scripts shows no new findings.

## Step 9 (Post-Implementation)

Current-branch mode: nothing to merge. After the Step 8 review and commit, the
orchestrator runs the `risk_evaluated` gate; archive with
`./.aitask-scripts/aitask_archive.sh 1789`.

## Risk

### Code-health risk: low
- Touches the load-bearing task-data pipeline in three files, 12 call sites.
  Each edit is the same mechanical options insertion from one constant, under a
  stated scope rule. The audit found one positional-arg stub to adapt (Test
  41) · severity: low · → mitigation: none (plan step 4 plus the full suite
  runs)
- Behaviour change: rerere no longer records or replays during task-data
  reconciliation (the auto-merge driver is the authority there, and rerere
  autoupdate fights the engine's probe contract), and auto-maintenance is
  deferred to the next ordinary git command · severity: low · → mitigation:
  none (accepted; stated in the constant's comment)

### Goal-achievement risk: low
- The mechanism is proven by a controlled experiment (every failure names
  `MERGE_RR.lock`; each single-knob variant is 0/60), and each half has its
  own deterministic test and mutant control · severity: low · → mitigation:
  none
- Residual: detached maintenance spawned *before* the window (the sweep's
  auto-commits, a claim commit before `task_push`) or by another session can
  still contend on non-rerere locks such as ref locks. The `MERGE_RR.lock`
  failure, the one observed, is closed for every source by the rerere half.
  This is the same class as the existing documented `_task_pull_rebase`
  concurrency RESIDUAL · severity: low · → mitigation: none (accepted,
  documented in the constant's comment)
