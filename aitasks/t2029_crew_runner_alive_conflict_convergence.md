---
priority: low
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness, syncer]
gates: [risk_evaluated]
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-10-16 01:06
updated_at: 2026-10-16 01:06
---

## Origin

Risk-mitigation ("after") follow-up for t2018, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — content conflict on _runner_alive.yaml is deferred, not converged

- A true content conflict on `_runner_alive.yaml` (adjacent-line edits since the merge
  base: a runner restarted with a new `interval` while a remote stop is pending, or a
  takeover runner rewriting the file) is deferred on each iteration, not converged; the
  remote stop stays unseen until resolved by hand. Outside "a file the runner
  dirtied", but reachable · severity: low · → mitigation:
  crew_runner_alive_conflict_convergence

## Goal

Converge a conflicted runner pull on `_runner_alive.yaml` instead of deferring it forever.

After t2018 (commit ab2cf4b37), `git_pull` in `.aitask-scripts/agentcrew/agentcrew_utils.py` proves a diverged merge clean in memory (`merge-tree --write-tree`), then fast-forwards to it with a protected `merge --ff-only --no-overwrite-ignore`. When `merge-tree` reports a conflict, the pull is deferred (`merge_conflict: <paths>`) and nothing is written. When the only conflicted path is the runner's own `_runner_alive.yaml`, the runner owns the file and knows how each side's fields should combine:
- keep the incoming `requested_action` (a remote stop must win);
- keep the runner's own identity and heartbeat fields (`status`, `pid`, `hostname`, `started_at`, `last_heartbeat`, `next_check_at`, `interval`), which it rewrites after the pull anyway.

Build the resolved blob in memory, never in the live worktree. For example: read both sides' YAML with `git show`, merge field-wise, `hash-object -w`, then build the merged tree from merge-tree's result plus that blob and `commit-tree` it (signed per `commit.gpgSign`, as `_merge_diverged` does). Advance with the same `_advance()`. Any other conflicted path, or an unparseable side, keeps today's deferral.

Constraints carried over from t2018: never open a merge or write conflict markers in the live crew worktree; never stash, rewrite or revert another process's uncommitted file; `--no-autostash` stays. Extend `tests/test_crew_pull_no_autostash.sh`, whose harness already drives `git_pull` and `run_loop`. Turn the conflict scenario from cell 8 (but on `_runner_alive.yaml`: a local `interval: 60` commit plus a peer `requested_action: stop`) into a convergence cell: the stop is honoured, the push converges, and the merge commit carries the resolved fields.
