---
priority: medium
effort: medium
depends: [t1223_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1223_1, 1223_2, 1223_3, 1223_4, 1223_5, 1223_6]
anchor: 1223
created_at: 2026-07-23 18:42
updated_at: 2026-07-23 18:42
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
