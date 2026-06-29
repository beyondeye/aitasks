---
priority: medium
effort: medium
depends: [1041]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1041]
created_at: 2026-06-22 09:30
updated_at: 2026-06-22 09:30
boardidx: 110
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1041

## Verification Checklist

- [ ] In a real crew worktree with all member agents Completed but a stale _crew_status.yaml (Running/80), `ait crew report --crew <id>` shows Completed and 100%.
- [ ] `ait crew dashboard` (TUI) shows the derived status/progress in BOTH the crew list (CrewCard) and the detail view for that same stale crew.
- [ ] `ait crew cleanup --crew <id>` cleans a crew whose persisted status is stale-Running but whose member agents are all terminal (Completed/Aborted/Error).
- [ ] A Killing crew with a live runner still shows Killing in the dashboard; once the runner stops (or heartbeat goes stale), it rolls forward to the derived terminal state.
- [ ] An all-aborted crew is reported as Aborted (not Completed) and is cleanup-eligible.
