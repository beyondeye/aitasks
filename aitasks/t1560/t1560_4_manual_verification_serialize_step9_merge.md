---
priority: medium
effort: medium
depends: [t1560_3]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1560_1, 1560_2, 1560_3]
anchor: 1560
followup_kind: manual_verification
created_at: 2026-08-18 12:26
updated_at: 2026-08-18 12:26
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
