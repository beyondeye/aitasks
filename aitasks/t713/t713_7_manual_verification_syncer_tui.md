---
priority: medium
effort: medium
depends: [t713_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [713_1, 713_2, 713_3, 713_4, 713_5, 713_6]
created_at: 2026-04-29 15:01
updated_at: 2026-04-29 15:01
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
