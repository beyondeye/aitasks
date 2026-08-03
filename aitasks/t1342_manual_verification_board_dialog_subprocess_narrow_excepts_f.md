---
priority: medium
effort: medium
depends: [1314]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1314]
created_at: 2026-07-29 22:00
updated_at: 2026-07-29 22:00
boardidx: 97280
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1314

## Verification Checklist

- [ ] Open `ait board`, press Enter on a task to open the task detail dialog
- [ ] Press `l` (Lock): the "Locking task..." overlay appears and CLEARS, then a "Locked t<id>" toast fires
- [ ] Press `u` (Unlock) on a task with status Implementing: the overlay clears BEFORE the reset-confirmation dialog appears, and the confirmation dialog is the screen you can answer (not popped away)
- [ ] Press `u` (Unlock) on a task with status Ready: overlay clears, "Unlocked t<id>" toast, dialog dismisses with no confirmation prompt
- [ ] Press `r` (Revert) on a task with uncommitted edits: reverts and dismisses; on an unmodified task the failure path notifies "Revert failed: ..." without crashing the board
- [ ] Induce a real subprocess failure (e.g. `chmod -x .aitask-scripts/aitask_lock.sh`) then press Lock and Unlock: each degrades to an error toast, the board stays responsive, and NO overlay is left stranded on screen (restore with `chmod +x` afterwards)
- [ ] Induce the same failure for Revert (e.g. make the git binary unavailable to the board) and confirm it notifies instead of crashing the TUI
