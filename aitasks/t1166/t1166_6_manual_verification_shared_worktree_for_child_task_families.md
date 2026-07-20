---
priority: medium
effort: medium
depends: [t1166_5]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1166_1, 1166_2, 1166_3, 1166_4, 1166_5]
anchor: 1166
created_at: 2026-07-20 12:11
updated_at: 2026-07-20 12:11
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
