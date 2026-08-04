---
priority: medium
effort: medium
depends: [t1405_7]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1405_1, 1405_2, 1405_3, 1405_4, 1405_5, 1405_6, 1405_7]
anchor: 1405
created_at: 2026-08-04 16:49
updated_at: 2026-08-04 16:49
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
