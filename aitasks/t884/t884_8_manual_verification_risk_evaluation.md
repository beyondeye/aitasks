---
priority: medium
effort: medium
depends: [t884_7]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [884_1, 884_2, 884_3, 884_4, 884_5, 884_6, 884_7]
created_at: 2026-06-01 00:35
updated_at: 2026-06-01 00:35
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
