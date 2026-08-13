---
priority: medium
effort: medium
depends: [t1505_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1505_1, 1505_2, 1505_3, 1505_4]
anchor: 1210
followup_kind: manual_verification
created_at: 2026-08-13 12:31
updated_at: 2026-08-13 12:31
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
