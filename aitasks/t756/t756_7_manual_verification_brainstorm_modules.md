---
priority: medium
effort: medium
depends: [t756_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [756_1, 756_2, 756_3, 756_4, 756_5, 756_6]
created_at: 2026-06-01 17:38
updated_at: 2026-06-01 17:38
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
