---
priority: medium
effort: medium
depends: [t1544_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1544_1, 1544_4, 1544_5, 1544_6]
anchor: 1544
followup_kind: manual_verification
created_at: 2026-08-17 22:08
updated_at: 2026-08-17 22:08
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
