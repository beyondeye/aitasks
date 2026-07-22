---
priority: medium
effort: medium
depends: [t1210_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1210_2, 1210_3, 1210_4, 1210_5]
anchor: 1210
created_at: 2026-07-22 16:17
updated_at: 2026-07-22 16:17
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
