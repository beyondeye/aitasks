---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [bash_scripts]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2261
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-10 18:02
updated_at: 2026-11-12 12:12
---

## Origin

Spawned from t2271 during planning review. t2271 deliberately deferred this
defect and shipped a visible, fail-safe limitation in its place.

## Upstream defect

`ait_unstage_staged_by_us` (`.aitask-scripts/lib/task_utils.sh`) cannot unwind
the paths a run staged once the data worktree is wedged (mid-merge, rebase,
cherry-pick, revert or bisect). Its `task_git reset` is not a guard-exempt
subcommand (`_ait_git_subcmd_is_readonly` / `_ait_git_subcmd_is_recovery`), so
the guard would die inside the cleanup. Before t2271 that die was silent and
the entries stayed in the shared `.aitask-data` index. Since t2271 the cleanup
does not reset at all on a wedge (unless `AIT_GIT_SKIP_STATE_CHECK=1`): it
leaves the entries and names them on stderr. The entries still sit in the
shared index, where another session's bare commit can collect them.

## Why a simple bypass is unsafe (measured in t2271's plan review)

While an operation is in progress, no index state proves that an entry we
staged is still ours. A counter-example was reproduced against real git:

1. A run staged a new untracked file.
2. The incoming branch of a `git merge --autostash` also adds that file with
   identical content.
3. The merge stops on a conflict in another file.

The staged file then has a normal stage-0 entry: it is absent from HEAD, has no
unmerged entries, and has the same blob OID. Yet it belongs to MERGE_HEAD's
incoming changes. Resetting it removes it from the pending merge. So none of
these checks establishes ownership: HEAD absence, `ls-files -u`, blob-OID
equality.

## Candidate directions

- **Serialize staging against operations.** Hold the data-index lock across
  stage → commit, and make the operations that wedge the worktree (the sync's
  pull/rebase) take the same lock. Then a wedge can never appear mid-run, and
  any wedge seen at cleanup predates our staging (which the pre-flight refuses).
- **Record an ownership witness at stage time** that an operation cannot forge:
  for example, a per-run marker that the cleanup can compare with the
  operation's start (`ORIG_HEAD` / `MERGE_HEAD` mtime ordering, or the reflog).
  This needs careful analysis; it may still be undecidable.
- Otherwise, keep the current "name it, leave it" behaviour and give
  `ait git-health` a check that lists staged entries no session owns.

## Requirements

- A real-operation regression (an actual `git merge` / `git rebase` driven to
  a stop, as in the counter-example above), not fabricated index entries.
- When a safe unwind lands, flip the "preserved" assertions in
  `tests/test_task_commit_scoped.sh` (Test 9e) and
  `tests/test_issue_update_ledger.sh` (case u).
- Keep the stderr naming for any entry the cleanup still cannot prove is
  ours.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-12T10:12:54Z status=pass attempt=1 type=human
