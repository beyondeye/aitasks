---
priority: medium
effort: medium
depends: [t1216_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1216_1, 1216_2, 1216_3, 1216_4]
anchor: 1111
created_at: 2026-07-27 22:27
updated_at: 2026-07-27 22:27
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
