---
priority: medium
effort: medium
depends: [t1037_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1037_1, 1037_2, 1037_3, 1037_4]
anchor: 1037
created_at: 2026-06-21 11:48
updated_at: 2026-06-21 11:48
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
