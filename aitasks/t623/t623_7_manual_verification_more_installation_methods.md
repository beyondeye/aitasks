---
priority: medium
effort: medium
depends: [t623_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [623_1, 623_2, 623_3, 623_4, 623_5, 623_6]
created_at: 2026-04-23 08:56
updated_at: 2026-04-23 08:56
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
