---
priority: medium
effort: medium
depends: [t1747_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1747_1, 1747_2, 1747_3, 1747_4, 1747_5, 1747_6]
anchor: 1733
followup_kind: manual_verification
created_at: 2026-09-09 11:29
updated_at: 2026-09-09 11:29
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
