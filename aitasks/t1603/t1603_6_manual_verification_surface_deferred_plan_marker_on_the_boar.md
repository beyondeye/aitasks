---
priority: medium
effort: medium
depends: [t1603_5]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1603_1, 1603_2, 1603_3, 1603_4, 1603_5]
anchor: 1595
followup_kind: manual_verification
created_at: 2026-08-30 13:32
updated_at: 2026-08-30 13:32
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
