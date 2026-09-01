---
priority: medium
effort: medium
depends: [t1657_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1657_3, 1657_4, 1657_5]
anchor: 1657
followup_kind: manual_verification
created_at: 2026-09-01 12:42
updated_at: 2026-09-01 12:42
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
