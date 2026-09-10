---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [bash_scripts, robustness, syncer]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: upstream_defect
created_at: 2026-09-10 15:47
updated_at: 2026-09-10 16:09
---

## Origin

Spawned from t1725_4 during Step 8b review.

## Upstream defect

- `tests/test_task_push.sh` — Test 54 ("two replayed commits both auto-merge
  (loop, not one shot)") fails in the t1725_4 post-change run
  (`TASK_SYNC_STATUS` = `failed`, `TASK_SYNC_AUTOMERGED` unset, stderr: "rebase hit
  conflicts and was aborted"); Test 56 ("AIT_AUTOMERGE_MAX_ROUNDS junk/0 cannot
  disable the cap", case `abc`: "falls closed to the default, so the replay
  converges — expected 'synced', got 'failed'") fails on a **pristine
  `git archive HEAD` export (b874e7058)** with no t1725_4 changes present.

## Diagnostic context

- Found while attributing red suites for t1725_4, which touched only
  `aitask_sync.sh`, `aitask_live_endpoint.sh`, `lib/tmux_exec.sh`, the new
  `lib/pane_state_probe.py` and sync/live-endpoint tests — nothing in the
  automerge path.
- The HEAD control was run from a `git archive HEAD | tar -x` copy (no stash, no
  restore in the shared worktree), so the failure is committed state, not another
  session's uncommitted edits.
- The failing case **differs between runs** (Test 54 in one, Test 56 in the
  other), so this looks flaky/environment-sensitive rather than a single
  deterministic regression. Runs were made on a busy box with other agent sessions
  live.
- Area: the t1727 automerge loop — `lib/task_utils.sh::_task_pull_rebase`,
  `lib/task_automerge.sh`, `AIT_AUTOMERGE_MAX_ROUNDS` parsing. t1727's archived
  plan (`aiplans/archived/p1727_*`) is the design record.
- Not t1696's scope (data-branch convergence after an off-branch metadata push),
  though t1696 also lists `tests/test_task_push.sh`; coordinate if both land close
  together.

## Suggested fix

First make it deterministic: run Tests 54–56 in isolation repeatedly (and under
load) to separate a real loop/cap defect from fixture timing (remote-ahead setup,
fetch freshness — the stderr notes the remote side is "as of the last successful
fetch"). Then fix the cause, not the retry count.
