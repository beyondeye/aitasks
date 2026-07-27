---
priority: medium
effort: medium
depends: [t1231_3]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1231_1, 1231_2, 1231_3]
anchor: 1065
created_at: 2026-07-27 08:45
updated_at: 2026-07-27 08:45
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
