---
Task: t1599_3_sync_per_task_commits_and_live_lock_skip.md
Parent Task: aitasks/t1599_scope_task_data_commits_to_their_own_paths.md
Sibling Tasks: aitasks/t1599/t1599_1_*.md, aitasks/t1599/t1599_2_*.md, aitasks/t1599/t1599_4_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# p1599_3 — `aitask_sync.sh`: per-task commits + live-lock skip

## Context

The highest-risk child of t1599. **18 of 66** sync auto-commits on the live
`aitask-data` branch carry more than two task/plan files.

Unlike the other two primary sites, this sweep is **intentional**: its job is to
leave the worktree clean so the later `pull --rebase` can run. Path-scoping alone
is therefore not the answer — the policy changes.

Owns `.aitask-scripts/aitask_sync.sh` and `.aitask-scripts/aitask_lock.sh`.

Two corrections to the parent task's framing: `aitask_pick_own.sh --sync` does
**not** call this script (it calls `task_sync` + `aitask_lock.sh --cleanup`), and
`aitask_sync.sh` has no `--sync` flag. The sweep fires from `ait sync`
(`ait:234`), the board TUI (`aitask_board.py:11467`), and the syncer TUI
(`syncer_app.py:2116`).

## Step 1 — Pre-phase (risk mitigations)

**`sync_caller_no_commit_audit`** — before touching `auto_commit`.

Two new outcomes become possible: a legitimately **no-commit** run, and a
**deferred rebase**. Audit `parse_sync_output` (`lib/sync_action_runner.py:87-140`)
and the three consumers, and fix which status tokens these must emit so none
classifies them as an error. **Record the chosen tokens in this plan** before
redesigning.

Two existing contracts to preserve: `run_sync_batch`
(`sync_action_runner.py:169-188`) never reads `returncode` — it classifies on the
first non-empty stdout line; and `auto_commit` is best-effort and always
returns 0.

## Step 2 — NUL-delimited porcelain

`git status --porcelain` (no `-z`) puts a rename on one line naming **two**
paths, and C-quotes paths containing spaces. Archive moves are exactly this
shape, so it is not a corner case.

Use `task_git status --porcelain -z`. **Ordering trap:** with `-z` a rename emits
`<new>` **first**, then `<orig>` — the reverse of the arrow display. Pin it in a
test.

## Step 3 — Group by owning task

Derive the owner from `aitasks/t<N>_*.md`, `aitasks/t<P>/t<P>_<C>_*.md`,
`aitasks/archived/…`, `aiplans/p<N>_*.md`, `aiplans/p<P>/p<P>_<C>_*.md`.

For a rename resolve **both** paths: same owner → group normally; **different
owners → skip and report as ambiguous**. Never guess an owner for an entry that
legitimately names two.

Commit each group path-scoped, under a message naming its real task.

## Step 4 — Never auto-commit an ownerless path

`aitasks/metadata/*`, artifacts and stray files are **skipped and reported**, not
swept into a residual commit. `stats_config.json` has four commits in its whole
history and **three are swallows** — a residual commit would leave that exact
case unfixed. Add `--commit-unowned` as an explicit opt-in.

## Step 5 — Live-lock skip, via the canonical seam

Reuse `lock_holder_liveness()` / `is_lock_holder_alive()` in `lib/pid_anchor.sh`
(the t1466 gate). **Do not reimplement liveness.**

Fetch the lock branch **once**: extend `aitask_lock.sh --list` (dispatch
`:724-726`, impl `:414`) with a `--batch` form emitting
`LOCK:<id>|<email>|<host>|<pid>|<starttime>|<kind>`. Leave the human output
unchanged. Lock YAML schema is at `aitask_lock.sh:270-276`.

Routing: `dead` → commit; `alive` → skip; `unknown` → **skip**. Fail safe.

## Step 6 — Three lock-availability statuses; do NOT fail open

`check_lock` (`:378-401`) fails **open** today — "not locked" covers an absent
branch, a network failure and an empty branch alike. `--batch` must distinguish
`LOCKS_NONE` and `LOCKS_UNINITIALIZED` (both → commit) from `LOCKS_UNAVAILABLE`
(→ skip every task-owned file, commit nothing).

An unreadable lock branch is not evidence of no locks. Availability-over-safety
is an **explicit** `--assume-unlocked` operator choice, never a silent
consequence of an outage.

Narrowing: `check_remote` (`:154-162`) exits before `auto_commit`, so this path
only ever runs with a remote present.

## Step 7 — Protect the rebase

Leaving files dirty breaks the invariant `auto_commit` exists to maintain.
Verified: `git pull --rebase` refuses with unstaged changes (rc 128), so
`do_pull_rebase` emits `ERROR:pull_rebase_failed` and `main()` exits 1 (`:504`) —
one protected file blocking fetch/pull/push for the CLI and both TUIs.

**Stashing is rejected**: it would move another live session's edits into a stash
they do not know about (the t635_33 hazard).

Protected-dirty early exit: commit eligible groups, always fetch; if
`remote_ahead == 0` continue; if `remote_ahead > 0` **skip the rebase**, emit the
deferred status naming count/reason/holder, and **exit 0**.

Staging detail: only `add` an **untracked** path, immediately before its own
group's commit. A path left staged blocks the rebase just as an unstaged one.

## Step 7b — Carry protected-dirty state into `do_push`

`remote_ahead` is sampled once from the step-5 fetch, so a remote advance
afterwards still reaches `do_push`. Its retry (`:456-470`) runs
`task_git pull --rebase --quiet 2>/dev/null || true` — with protected files the
rebase refuses, `|| true` **swallows** it, the un-rebased push is rejected again,
and the run reports a misleading `ERROR:push_failed`, bypassing the protection.

Hold protected-dirty state (count + reasons + holders) in a script-scope variable
set during grouping and consult it in `do_push`: protected + rejected → defer
(no rebase, no retry, deferred token, exit 0); unset → today's behaviour.

Also stop the retry path swallowing a genuine rebase failure — route on its exit
status instead of blind-retrying a push that cannot succeed.

## Step 8 — Report

Name each skipped file with its reason and, where known, its holder.

## Verification

Fixture: `tests/test_sync_branch_mode_automerge.sh:47-76`. Lock seeding:
`plant_lock` in `tests/test_crash_recovery_pid_anchor.sh:40-145`.

Live lock → skipped; dead lock → committed; `unknown` → skipped; mixed → correct
partition in one run; nothing eligible → no commit (`rev-list --count`);
rename/move grouping incl. a same-owner archive move and an ambiguous cross-task
rename, asserting the `-z` `<new>\0<orig>` ordering; a path containing a space;
ownerless → skipped; `LOCKS_UNAVAILABLE` → nothing committed;
`LOCKS_UNINITIALIZED` → committed; `--assume-unlocked` and `--commit-unowned`
→ committed.

**Rebase protection:** remote-ahead + one live-locked dirty file → exit **0**
with the deferred token, not `ERROR:pull_rebase_failed`, and the fetch still
happened. Control: nothing protected → the rebase still runs.

**Push-retry race:** inject via a `pre-push` hook in the fixture that, on first
invocation, pushes from a sibling clone — a documented git seam, not a
production test hook. Our push is then rejected exactly once, deterministically
entering the retry path. Protected → exit 0 + deferred token, not
`ERROR:push_failed`; unprotected → rebase+retry succeeds.

**Negative controls (required):** the bystander/ownerless assertions must FAIL
against the pre-fix `add aitasks/ aiplans/`.

`shellcheck .aitask-scripts/aitask_sync.sh .aitask-scripts/aitask_lock.sh`, plus
the `sync_action_runner` Python tests.

Post-implementation cleanup, archival and merge follow **Step 9** of the shared
task workflow.
