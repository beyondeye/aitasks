---
priority: medium
effort: low
depends: []
issue_type: bug
status: Folded
labels: [tmux, test_infrastructure]
gates: [risk_evaluated]
folded_into: 2167
anchor: 1689
followup_kind: upstream_defect
created_at: 2026-10-26 16:35
updated_at: 2026-10-30 01:34
---

## Origin

Spawned from t2152 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/stale_lock.sh:689-694` — `stale_lock_release` waits only 40×50 ms (about 2 s) for the `.gc` guard.
  - Every merge-lock waiter (`_MERGE_LOCK_SLEEP=0.05`, `lib/merge_lock.sh:78`) takes that same guard on each poll and runs the holder-liveness seam (`_STALE_LOCK_LIVENESS_FN` → `merge_lock_liveness` → `lock_holder_liveness`) inside it (`stale_lock.sh` `_stale_lock_reclaim_under_gc`).
  - With N contenders the guard is almost never free. The holder's `finish` gives up with "stale_lock: guard '…' busy — lock '…' NOT released", the merge lock leaks with a live holder, and every waiter then sits out its whole wait budget.

## Diagnostic context

- `tests/test_merge_lock_concurrency.sh` Case 2 (N=51 concurrent callers) fails on macOS, on unmodified HEAD bdf78abab (run from a `git archive` copy, so the t2152 change is not involved):
  - only 3 of 51 merges land, then the lock stays `HELD:t25|…|unknown`;
  - the 600 s case guard expires;
  - Cases 12/13 then cascade (`LOCK_UNAVAILABLE:guard_busy`, leftover holders).
- After t2152 the macOS holder probe is the `bsdinfo` Python probe (~20-30 ms) instead of two `ps` forks. That raises guard occupancy further: 1 merge before the leak instead of 3. The defect itself predates t2152.
- A 60-way concurrent `get_pid_identity` stress returned 900/900 identical `bsdinfo` tokens, so a flaky identity probe is ruled out: the cause is guard starvation, not an identity mismatch in `merge_lock_authorize`.
- No CI job runs this suite.

## Suggested fix

Make the release side able to win the guard under contention. Options:
- give `stale_lock_release` a longer, backed-off guard wait (bounded by a leaked-guard detector rather than a fixed 2 s);
- have waiters back off or jitter between guarded probes instead of re-taking the guard every 50 ms;
- move the expensive token probe out of the guarded section, keeping only the decision under the guard.

Verify with `bash tests/test_merge_lock_concurrency.sh` on macOS, Case 2 in particular.
