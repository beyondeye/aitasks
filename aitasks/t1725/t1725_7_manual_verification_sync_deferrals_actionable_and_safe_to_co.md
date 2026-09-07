---
priority: medium
effort: medium
depends: [t1725_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1725_1, 1725_2, 1725_3, 1725_4, 1725_5, 1725_6]
anchor: 1599
followup_kind: manual_verification
created_at: 2026-09-07 16:44
updated_at: 2026-09-07 16:44
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
