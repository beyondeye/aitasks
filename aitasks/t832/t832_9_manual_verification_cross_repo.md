---
priority: medium
effort: medium
depends: [t832_8]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [832_1, 832_2, 832_3, 832_4, 832_5, 832_6, 832_7, 832_8]
created_at: 2026-05-26 18:39
updated_at: 2026-05-26 18:39
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
