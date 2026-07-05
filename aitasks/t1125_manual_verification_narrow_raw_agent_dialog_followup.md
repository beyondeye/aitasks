---
priority: medium
effort: medium
depends: [1122]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1122]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-05 11:46
updated_at: 2026-07-05 16:16
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1122

## Verification Checklist

- [ ] In a minimonitor pane, press `j` then `e` → the "Launch Code Agent (no task)" dialog appears with rows STACKED VERTICALLY (narrow layout), fitting the small pane
- [ ] In a wide TUI (ait board or full ait monitor), press `j` then `e` → the dialog stays in its FULL-WIDTH layout (no regression)
- [ ] Confirm the launched raw agent itself is unchanged (agent/model/tmux-target selectable, empty prompt) in both layouts
