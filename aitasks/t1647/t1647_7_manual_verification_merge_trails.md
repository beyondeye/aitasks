---
priority: medium
effort: medium
depends: [t1647_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1647_1, 1647_2, 1647_3, 1647_4, 1647_5, 1647_6]
anchor: 1647
followup_kind: manual_verification
created_at: 2026-09-01 18:55
updated_at: 2026-09-01 18:55
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
