---
priority: high
risk_code_health: high
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [git, bash_scripts, robustness, crash_recovery, task_metadata]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1677, 1678]
assigned_to: dario-e@beyond-eye.com
anchor: 1599
implemented_with: claudecode/opus5
created_at: 2026-08-25 12:49
updated_at: 2026-09-02 09:03
completed_at: 2026-09-02 09:03
---

## Context

Parent: t1599. This is the **highest-risk** child and carries its own plan and
review.

`aitask_sync.sh:176-177` does `task_git add aitasks/ aiplans/` then an unscoped
`ait: Auto-commit task changes before sync`. Measured on the live `aitask-data`
branch: **18 of 66** sync auto-commits carry more than two task/plan files.

Unlike the other two sites, this sweep is **intentional** — its job is to leave
the worktree clean so the later `pull --rebase` can run. So path-scoping alone
is not the answer; the policy has to change.

**Correction to the parent task's description:** `aitask_pick_own.sh --sync`
does **not** call this script. It calls `task_sync` (a `pull --rebase` helper in
`lib/task_utils.sh`) plus `aitask_lock.sh --cleanup`. This sweep fires only from
`ait sync` (`ait:234`), the board TUI (`aitask_board.py:11467`), and the syncer
TUI (`syncer_app.py:2116`). Note also `aitask_sync.sh` has **no `--sync` flag**
— only `--batch` and `--help`.

## Exclusive script ownership

This child owns **`.aitask-scripts/aitask_sync.sh`** and
**`.aitask-scripts/aitask_lock.sh`**. Do NOT edit `aitask_pick_own.sh`
(t1599_1), `aitask_fold_mark.sh` (t1599_2), or t1599_4's sweep targets.

## Step 1 (pre-phase risk mitigation): `sync_caller_no_commit_audit`

Do this FIRST, before touching `auto_commit`.

After this redesign a run can legitimately produce **no commit**, and can
legitimately **defer the rebase**. Both are new outcomes. Audit
`parse_sync_output` (`lib/sync_action_runner.py:87-140`) and the three
consumers — `ait:234` (execs, so the exit code reaches the user's shell),
`aitask_board.py:11474-11503`, `syncer_app.py:2127-2160` — and determine which
status tokens these outcomes must emit so none of them classifies them as an
error. **Record the required tokens in this child's plan before redesigning.**

Important existing contract: `run_sync_batch` (`sync_action_runner.py:169-188`)
**never reads `result.returncode`** — it classifies purely on the first non-empty
stdout line. And `auto_commit` is best-effort today (`2>/dev/null || true` on
both mutating lines, always returns 0). Preserve both properties.

## Step 2: Parse the dirty set with a NUL-delimited porcelain

`git status --porcelain` (no `-z`) renders a rename on ONE line naming TWO paths,
and C-quotes any path containing a space. Verified:

```
R  aitasks/t42_some_task.md -> aitasks/archived/t42_some_task.md
 M "aitasks/t43_with space.md"
```

A naive `cut -c4-` therefore hands the grouper a single string containing two
paths — it can match two owners at once, or the wrong one — and a quoted path
does not exist on disk under that name. **Archive moves are exactly this shape**,
so it is not a corner case.

Use `task_git status --porcelain -z` and parse NUL-delimited. Verified output for
the same state:

```
R  aitasks/archived/t42_some_task.md\0aitasks/t42_some_task.md\0 M aitasks/t43_with space.md\0
```

**Ordering trap:** with `-z` a rename emits **`<new>` first, then `<orig>`** —
the reverse of the arrow display — and quoting is gone. Pin this in a test.

## Step 3: Group by owning task id

Owner derivation: `aitasks/t<N>_*.md`, `aitasks/t<P>/t<P>_<C>_*.md`,
`aitasks/archived/…`, `aiplans/p<N>_*.md`, `aiplans/p<P>/p<P>_<C>_*.md`.

For a rename, resolve the owner of **both** paths:
- same owner (the archive case) → group normally;
- **different owners → skip and report as an ambiguous cross-task rename.**
  Never guess an owner for an entry that legitimately names two.

Commit each group path-scoped under a message naming its real task.

## Step 4: NEVER auto-commit an ownerless path

Anything with no derivable task id — `aitasks/metadata/*`, artifacts, stray
files — is **skipped and reported**, not swept into a residual commit.

This is the documented failure mode: `aitasks/metadata/stats_config.json` has
four commits in its entire history and **three are swallows** (`da9dfeb89`,
`c4445b4eb`, `442c65179`). A residual auto-commit would leave that exact case
unfixed — still committing and pushing an in-flight edit without its author.

These files simply stay dirty until the session that changed them commits them,
which is now safe because after t1599_1 the claim path no longer sweeps them
either. Add an explicit `--commit-unowned` opt-in for anyone who wants the old
behaviour.

## Step 5: Skip files whose owning task is held by a LIVE lock

**Reuse the canonical seam — do not reimplement liveness.**
`lock_holder_liveness()` and `is_lock_holder_alive()` in `lib/pid_anchor.sh`
(the t1466 gate) return `alive` / `dead` / `unknown`.

Fetch the lock branch **once** and enumerate, rather than one
`aitask_lock.sh --check` (and one `git fetch`) per task. Extend
`aitask_lock.sh --list` (dispatch at `:724-726`, impl `list_locks()` at `:414`)
with a `--batch` machine-readable form emitting
`LOCK:<id>|<email>|<host>|<pid>|<starttime>|<kind>`. Extend the existing helper
rather than forking its scan logic; leave the human `--list` output unchanged.

Lock YAML schema is built at `aitask_lock.sh:270-276` (`task_id`, `locked_by`,
`locked_at`, `hostname`, `pid`, `pid_starttime`, `pid_starttime_kind`).

**Per-verdict routing:** `dead` → commit (the recovery case); `alive` → skip;
`unknown` → **skip** (treat as live). Fail safe.

## Step 6: Three distinct lock-availability statuses — do NOT fail open

`check_lock` (`:378-401`) and `list_locks` currently fail **open**: they return
"not locked" for a genuinely absent branch, a network failure, and an empty
branch alike. Sweeping in that state would recreate the precise cross-session
swallow this task exists to stop — an outage can easily coincide with a live
editor.

`--batch` must distinguish three states:

| status | meaning | action |
|---|---|---|
| `LOCKS_NONE` | branch readable, no locks held | commit all owned groups |
| `LOCKS_UNINITIALIZED` | lock branch does not exist — locking was never set up, so no task in this repo *can* be locked | commit all owned groups |
| `LOCKS_UNAVAILABLE` | branch exists but unreadable (fetch/network/ls-tree failure) | **skip every task-owned file and report**; commit nothing |

An unreadable lock branch is not evidence of no locks. The
availability-over-safety choice is made **explicitly** by the operator via
`--assume-unlocked`, never silently by an outage.

Useful narrowing: `main()` runs `check_remote` (`:154-162`) at step 2, which
exits 0 with `NO_REMOTE` **before** `auto_commit` at step 3 — so `auto_commit`
only ever runs when a remote exists, and the no-remote case never reaches this
decision.

## Step 7: Protect the rebase — a skipped file must not break the sync

**This is the invariant `auto_commit` actually exists to maintain.** Verified:

```
$ git status --porcelain   ->   M aitasks/t2_b.md
$ git pull --rebase
error: cannot pull with rebase: You have unstaged changes.
error: Please commit or stash them.            rc=128
```

`do_pull_rebase`'s non-conflict branch then emits `ERROR:pull_rebase_failed` and
`return 1`, and `main()` exits 1 (`:504`). So one correctly-protected file would
block fetch/pull/push for `ait sync` and both TUIs. Unacceptable.

**Stashing is NOT the answer.** `git stash` / `rebase.autoStash` would move
another live session's in-flight edits into a stash they do not know about — the
exact hazard recorded from t635_33, where a concurrent stash+reset swept a
session's unstaged work. Never stash a file being protected *because* another
session owns it.

**Protected-dirty early exit.** After grouping, if any file is protected (live
lock / unknown liveness / locks unavailable / ownerless / ambiguous rename):

- commit every eligible group as normal, and always run the read-only fetch;
- `remote_ahead == 0` → continue normally (`do_push` needs no clean tree, so
  local commits still publish);
- `remote_ahead > 0` → **skip `do_pull_rebase` entirely**, emit the deferred
  status naming count/reason/holder, and **exit 0** — a deferral, not an error.

Deferring is also right on its own merits: rebasing the shared data branch
underneath a live session's uncommitted work is the clobber hazard that argues
for leaving reconciliation to the owning session. The cost is bounded and
self-clearing — the deferral ends when that session commits.

**Staging detail:** only ever `add` an **untracked** path, and only immediately
before its own group's commit. A path left staged by a failed add/commit blocks
the rebase just as an unstaged one does.

## Step 7b: Carry protected-dirty state into `do_push`

The step-7 guard alone is NOT enough. `remote_ahead` is sampled once, from the
step-5 fetch. On a branch several sessions push to in parallel, the remote can
advance *after* that fetch, so a run that correctly saw `remote_ahead == 0` still
reaches `do_push` and gets its push rejected. Today's retry (`:456-470`) then
does exactly the wrong thing:

```bash
elif [[ $push_exit -ne 0 ]]; then
    _git_with_timeout fetch origin 2>/dev/null || true
    task_git pull --rebase --quiet 2>/dev/null || true   # <-- failure SWALLOWED
    _git_with_timeout push origin 2>/dev/null || retry_exit=$?
    if [[ $retry_exit -ne 0 ]]; then batch_out "ERROR:push_failed"; return 1; fi
```

With protected files present the `pull --rebase` refuses (rc 128), `|| true`
swallows it, the still-un-rebased push is rejected again, and the run reports
`ERROR:push_failed` — bypassing the protection and blaming the push for a
failure the protected files caused. This is an ordinary shared-branch race.

Fix: hold protected-dirty state (count + reasons + holders) in a script-scope
variable set during grouping, and consult it in `do_push`:

- **protected-dirty set, push rejected** → do NOT `pull --rebase`, do NOT retry.
  Emit the deferred token and return the deferred outcome (exit 0). Local
  commits publish on a later run.
- **protected-dirty unset** → today's fetch + rebase + retry, unchanged.

While here, stop the retry path swallowing a genuine rebase failure: check the
rebase's exit status and route on it rather than blind-retrying a push that
cannot succeed. Blind-retrying is what turns a diagnosable cause into
`ERROR:push_failed`.

## Step 8: Report

Report skipped files with their reason: live lock / unknown liveness / locks
unavailable / ownerless / ambiguous rename. Name the holder where known.

## Verification

Fixture: `tests/test_sync_branch_mode_automerge.sh:47-76`
(`setup_branch_mode_repos` — bare remote, clone, orphan `aitask-data` branch +
worktree) is the closest template. `tests/test_sync.sh` covers legacy mode.
Lock seeding: `plant_lock` in `tests/test_crash_recovery_pid_anchor.sh:40-145`
writes a lock blob directly onto `origin/aitask-locks` via
`hash-object`/`mktree`/`commit-tree`/`push`.

Tests:
- live lock → file skipped and left dirty
- stale/dead lock → file committed
- `unknown` liveness → skipped
- mixed locked + unlocked → correct partition in ONE run
- nothing eligible → clean no-op, no commit created (`rev-list --count`
  unchanged, the `tests/test_gate_record.sh:100-107` idiom)
- **rename/move grouping** — a same-owner archive move (committed) and an
  ambiguous cross-task rename (skipped + reported); assert the `-z`
  `<new>\0<orig>` ordering explicitly
- a path containing a space (proves the `-z` parser)
- ownerless file → skipped and reported, NOT committed
- `LOCKS_UNAVAILABLE` → nothing committed; `LOCKS_UNINITIALIZED` → committed;
  `--assume-unlocked` → committed; `--commit-unowned` → committed
- **rebase protection:** remote-ahead branch + one live-locked dirty file →
  assert exit **0** with the deferred token, NOT `ERROR:pull_rebase_failed`, and
  that the fetch still happened. Control: nothing protected → the rebase still
  runs.
- **push-retry race (remote advance after the initial fetch):** inject through a
  documented git seam, not a production test hook — install a `pre-push` hook in
  the fixture's data repo that, on its first invocation, pushes a commit from a
  sibling clone to the same remote. Our push is then genuinely rejected exactly
  once, deterministically entering `do_push`'s retry path. With a protected
  dirty file present, assert exit **0** with the deferred token and NOT
  `ERROR:push_failed`; without one, assert the existing rebase+retry succeeds.

**Negative controls (required).** The bystander/ownerless assertions must FAIL
against the pre-fix `add aitasks/ aiplans/`.

Test conventions per `tests/test_lock_force.sh`; source
`tests/lib/test_scaffold.sh` then `tests/lib/asserts.sh`. Assertion argument
order is `assert_contains <desc> <needle> <haystack>`. If any test body runs
inside a `( … )` subshell, opt into the file-backed counters
(`assert_counters_init` + `assert_counters_load`) per CLAUDE.md.

Also run `shellcheck .aitask-scripts/aitask_sync.sh .aitask-scripts/aitask_lock.sh`
and `bash tests/run_all_python_tests.sh --test-dir tests` for the
`sync_action_runner` Python tests.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-01T14:32:37Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-02T05:54:20Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-02T06:03:45Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:351140f1d75e11b2

> **✅ gate:risk_evaluated** run=2026-09-02T06:03:45Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1599_3/risk_evaluated_2026-09-02T06:03:45Z-risk_evaluated-a1.log`
