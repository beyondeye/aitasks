---
priority: medium
effort: medium
depends: [t1243_14]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1243_3, 1243_4, 1243_5, 1243_6, 1243_7, 1243_8, 1243_9, 1243_10, 1243_11, 1243_12, 1243_13]
anchor: 1243
created_at: 2026-07-28 01:21
updated_at: 2026-07-28 01:21
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
