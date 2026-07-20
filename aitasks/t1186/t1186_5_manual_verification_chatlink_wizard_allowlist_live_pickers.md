---
priority: medium
effort: medium
depends: [t1186_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1186_1, 1186_2, 1186_3, 1186_4]
anchor: 1149
created_at: 2026-07-20 22:51
updated_at: 2026-07-20 22:51
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
