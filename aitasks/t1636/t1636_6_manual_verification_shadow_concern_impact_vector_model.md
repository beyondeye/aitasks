---
priority: medium
effort: medium
depends: [t1636_5]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1636_1, 1636_2, 1636_3, 1636_4, 1636_5]
anchor: 1636
followup_kind: manual_verification
created_at: 2026-08-30 14:58
updated_at: 2026-08-30 14:58
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
