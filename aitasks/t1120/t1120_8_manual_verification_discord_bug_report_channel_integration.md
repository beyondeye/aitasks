---
priority: medium
effort: medium
depends: [t1120_7]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1120_1, 1120_2, 1120_3, 1120_4, 1120_5, 1120_6, 1120_7]
anchor: 1120
created_at: 2026-07-05 12:11
updated_at: 2026-07-05 12:11
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
