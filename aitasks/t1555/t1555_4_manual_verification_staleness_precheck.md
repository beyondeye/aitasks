---
priority: medium
effort: medium
depends: [t1555_3]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1555_1, 1555_2, 1555_3]
anchor: 1538
followup_kind: manual_verification
created_at: 2026-08-17 19:00
updated_at: 2026-08-17 19:00
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
