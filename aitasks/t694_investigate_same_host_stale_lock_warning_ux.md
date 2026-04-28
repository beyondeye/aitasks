---
priority: low
effort: low
depends: []
issue_type: chore
status: Ready
labels: [aitask_pick, task_workflow]
created_at: 2026-04-28 10:18
updated_at: 2026-04-28 10:18
---

## Context

Spun off from t692 (multi-PC self-reclaim warning). t692 added a `LOCK_RECLAIM:` signal in `aitask_lock.sh` that fires when the same email picks a task already locked on a *different* host. Same-host stale locks (locked by you on this same machine, but `locked_at` is hours old) were explicitly **out of scope** for t692 — user direction during planning was to "create followup investigation task, define actual need of the fix, scope, etc."

## Investigation goals

Determine whether same-host stale locks warrant a warning analogous to t692's multi-PC reclaim prompt, and if so, define:

1. **Need.** How often do users actually re-pick a task they started hours ago on the same host? Is the silent-refresh behavior they get today a problem, or just fine? Anecdotes / Slack mentions / past aitask review findings would help.
2. **Threshold.** What `locked_at`-age threshold is "stale"? 1 hour? 4 hours? Project-configurable in `project_config.yaml`? Per-user in `userconfig.yaml`?
3. **UX.** Same prompt as t692 (`LOCK_RECLAIM:` → "Reclaim and continue" / "Pick a different task")? Or quieter (just an info line, no confirmation)? Same prompt risks fatigue if it fires every morning when resuming yesterday's work.
4. **Edge cases.**
   - Hostname tracking under Docker / SSH / containers where `hostname` can be ephemeral or duplicated.
   - Interaction with `aitask_lock.sh --cleanup` (currently only removes locks for archived tasks — would need extending if we treat time-based stale locks as cleanup candidates).
   - What if the user has multiple local clones on the same machine with different working copies? Each runs same hostname but represents different work-in-progress.

## Deliverable

A short design doc / plan file (or a follow-up implementation task) that:
- Recommends fix-or-not based on the investigation.
- If fix: specifies threshold, prompt UX, where the threshold lives (config key + default).
- If not: documents the rationale so this question doesn't get re-litigated.

## Out of scope

- Cross-user lock takeover (already handled).
- Multi-PC reclaim (handled by t692).
- Auto-expiry of live locks across all dimensions — this task is specifically about *same-host stale* warnings.

## Notes

- See `aiplans/archived/p692_*.md` after t692 archives for the precedent design.
- The `LOCK_RECLAIM:` plumbing in `aitask_lock.sh` / `aitask_pick_own.sh` / task-workflow Step 4 is fully reusable — same-host stale handling would just add a second trigger condition (age threshold) alongside the existing hostname-mismatch one.
