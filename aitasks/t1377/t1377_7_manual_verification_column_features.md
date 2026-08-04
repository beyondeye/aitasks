---
priority: medium
effort: medium
depends: [t1377_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1377_2, 1377_3, 1377_5, 1377_6]
anchor: 1243
created_at: 2026-08-04 10:02
updated_at: 2026-08-04 10:02
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
