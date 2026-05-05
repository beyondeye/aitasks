---
priority: medium
effort: medium
depends: [t749_7]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [749_1, 749_2, 749_3, 749_4, 749_5, 749_6]
created_at: 2026-05-05 10:48
updated_at: 2026-05-05 10:48
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
