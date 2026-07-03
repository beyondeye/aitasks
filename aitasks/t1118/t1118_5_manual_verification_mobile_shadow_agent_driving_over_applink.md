---
priority: medium
effort: medium
depends: [t1118_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1118_2, 1118_3, 1118_4]
anchor: 1118
created_at: 2026-07-03 11:31
updated_at: 2026-07-03 11:31
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
