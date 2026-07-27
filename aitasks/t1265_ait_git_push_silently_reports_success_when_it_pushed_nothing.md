---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: []
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 635
implemented_with: claudecode/opus5
created_at: 2026-07-27 09:16
updated_at: 2026-07-27 22:28
---

## Problem

`task_push` (`.aitask-scripts/lib/task_utils.sh:192-207`) is best-effort by
design: it tries push, falls back to `pull --rebase`, retries up to 3 times, and
then `return 0` regardless. Both `_task_push_once` and `_task_pull_rebase`
suppress stderr (`2>/dev/null`), so a completely failed push is
**indistinguishable from a successful one** — no output, exit 0.

Observed live at the end of the t635_27 verification run: `./ait git push`
printed nothing and exited 0, but pushed nothing. Root cause chain:

1. `git push` rejected — `non-fast-forward` (origin/aitask-data had advanced by
   2 commits from a concurrent session).
2. `git pull --rebase` refused — `cannot pull with rebase: You have unstaged
   changes` (another session's uncommitted edits to `t1223_3` files in the data
   worktree).
3. All 3 attempts consumed; `return 0`.

Three commits (verification state, plan, archival) were left unpushed with no
signal to the user. This is a realistic steady state, not an edge case:
concurrent sessions on a shared checkout routinely leave the data worktree
dirty, which permanently blocks the rebase fallback.

## Impact

Archival and task-state commits can silently fail to reach the remote. Another
PC then picks a task that is already done, or misses gate-ledger state. The
failure is invisible precisely when concurrency makes it most likely.

## Fix direction

Keep the non-fatal contract (do not abort the workflow), but **stop being
silent**. Suggested:
- Return a distinct status from `task_push` (pushed / up-to-date / failed).
- On failure, print an actionable warning naming the reason (non-fast-forward vs
  dirty-worktree-blocked-rebase) and the unpushed commit count, e.g.
  `warning: 3 commit(s) not pushed — data worktree has unstaged changes blocking
  rebase; reconcile with 'ait syncer'`.
- Do not stash or commit other sessions' in-flight edits to unblock the rebase.

## Verification

Test: with origin ahead and the data worktree dirty, `ait git push` still exits
0 but emits the warning and reports the unpushed count.

## Related

Memory note `project_ait_git_push_silent_noop_on_divergence` records this
pattern; this task is the source-side fix.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-27T19:28:59Z status=pass attempt=1 type=human
