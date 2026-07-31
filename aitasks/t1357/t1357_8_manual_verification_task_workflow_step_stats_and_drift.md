---
priority: medium
effort: medium
depends: [t1357_7]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1357_1, 1357_2, 1357_3, 1357_4, 1357_5, 1357_6, 1357_7]
anchor: 1357
created_at: 2026-07-31 11:03
updated_at: 2026-07-31 11:03
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
