---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [bash_scripts, git, concurrency, performance]
gates: [risk_evaluated]
folded_tasks: [2156]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-10-30 01:34
updated_at: 2026-10-30 01:35
---

## Problem

A merge-lock waiter in `aitask_merge_task.sh begin` polls far too often. The merge lock is held for minutes (the merge, the verification run, and sometimes a person resolving a conflict). A 50 ms poll makes no sense for that and wastes resources.

- `.aitask-scripts/lib/merge_lock.sh:78-79`: `_MERGE_LOCK_SLEEP=0.05`, `_MERGE_LOCK_ATTEMPTS_PER_SEC=20`. These were copied from `registry_lock.sh` (delta 4 in the file header), whose critical sections last milliseconds. That reasoning does not carry over to the merge lock.
- `.aitask-scripts/aitask_merge_task.sh:150-163` (`cmd_begin`) loops over 2 s slices (`slice=2`). Each slice calls `merge_lock_acquire`, which runs `stale_lock_acquire` with about 40 retries 50 ms apart. The `WAITING:<holder>:<elapsed>` line every ~2-3 s is the progress cadence, not the retry interval. The real rate is about 20 attempts/s, or ~6,000 over the 300 s "Wait and retry" budget (`merge-broker.md` `begin / BUSY`).
- Each failed attempt spawns several processes: `.gc` guard mkdir, lock mkdir, the holder-liveness seam (`_merge_lock_liveness_seam` → `merge_lock_liveness` → `lock_holder_liveness`, which runs inside the guard), then guard release.
- Because waiters take the `.gc` guard every 50 ms, they also starve the holder's own release. See the merged t2156 below: that is a correctness defect (leaked lock), not only a cost.

## Goal

1. **Long, jittered waiter poll for the merge lock.** Replace the 50 ms poll with an interval on the order of tens of seconds (the starting proposal is ~30 s; settle the exact value in planning). Add jitter so concurrent waiters do not retry in lockstep. Keep the first attempt immediate, so an uncontended `begin` gains no latency.
2. **Keep the existing timeout behavior unchanged:**
   - `--wait-secs N` remains a bound on the total wait. The sleep before each attempt is clamped to the remaining budget, and one final attempt is made at or just before the deadline. A lock freed shortly before the deadline is still acquired. `begin` must never overrun its budget by a whole interval.
   - `BUSY:<holder>:<waited>` and `WAITING:<holder>:<elapsed>` keep their shape and stream (verdict on stdout, progress on stderr). Emit one `WAITING` line per poll, not per 2 s slice.
   - `--wait-secs 0` still means exactly one attempt.
   - Existing broker tests that use `--wait-secs 1` / `--wait-secs 5` must keep their meaning. If they need a short interval to stay fast, add a test seam that follows the repo's existing seam conventions (compare `AIT_MERGE_LOCK_DISABLED`). Do not shorten the production default to make them pass.
3. **Scope the change to the merge lock.** `registry_lock.sh` and other `stale_lock.sh` callers keep their short polls. Their locks really are millisecond-scale. Any change to the shared core must be opt-in per caller.
4. **Fix the release-side starvation (merged t2156) on its own terms.** A longer waiter interval makes guard contention less likely but does not prove starvation is gone. For example, N waiters entering `begin` together still collide on the first immediate attempt, and jitter only spreads out the attempts that follow. The holder's `finish`/`abort` release must be able to win the guard under contention, through one of t2156's release-side options or an equivalent.

## Verification

- `bash tests/test_merge_lock_broker.sh`, `bash tests/test_merge_lock_concurrency.sh` (Case 2, N=51), and `bash tests/test_merge_broker_rendered_verdicts.sh` pass on Linux.
- **macOS:** `tests/test_merge_lock_concurrency.sh` Case 2 passes, with all 51 merges landing and no leaked holder, and Cases 12/13 do not cascade. If no macOS host is available in-session, record that explicitly and spawn a manual-verification follow-up. Do not mark it as done.
- **The release fix needs its own regression**, one that fails with the release-side fix reverted while the new long poll is still in place (with the poll forced short through the seam, or with waiters hammering the guard directly). A passing Case 2 after only the interval change does not prove the starvation is fixed.
- A timeout test: a lock held past `--wait-secs N` returns `BUSY` within N plus a small grace, not N plus an interval. A lock released just before the deadline is acquired.
- Measure attempts per minute for one waiter before and after (count `stale_lock_acquire` iterations or liveness probes), and record the numbers in the plan.

## Notes for planning

- Docs that mention the wait or poll behavior: the `merge_lock.sh` header (delta 4), `merge-broker.md` (`--wait-secs 120` entry text, `begin / BUSY`), and `website/content/docs/concepts/locks.md` if it describes waiting. Regenerate goldens if any `.md.j2` or procedure changes.
- Check how the attended agent runs `begin --wait-secs 120` / `300` against its shell tool's default command timeout (often 120 s). The waits plus the merge itself can exceed it. Make sure the procedure gives an adequate timeout, or flag this to the owning procedure.

## Merged from t2156: fix merge lock release guard starvation


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

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t2156** (`t2156_fix_merge_lock_release_guard_starvation.md`)
