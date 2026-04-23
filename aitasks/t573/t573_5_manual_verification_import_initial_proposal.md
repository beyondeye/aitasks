---
priority: medium
effort: medium
depends: [t573_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [573_1, 573_2, 573_3, 573_4]
created_at: 2026-04-23 11:05
updated_at: 2026-04-23 11:05
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
