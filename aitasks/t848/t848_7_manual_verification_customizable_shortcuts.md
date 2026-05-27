---
priority: medium
effort: medium
depends: [t848_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [848_1, 848_2, 848_3, 848_4, 848_5, 848_6]
created_at: 2026-05-27 17:47
updated_at: 2026-05-27 17:47
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
