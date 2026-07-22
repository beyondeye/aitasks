---
priority: medium
effort: medium
depends: [t1162_5]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1162_1, 1162_2, 1162_3, 1162_4, 1162_5]
anchor: 1162
created_at: 2026-07-22 11:02
updated_at: 2026-07-22 11:02
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
