---
priority: medium
effort: medium
depends: [t2211_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [2211_1, 2211_2, 2211_3, 2211_4, 2211_5, 2211_6]
anchor: 2175
followup_kind: manual_verification
created_at: 2026-11-05 15:40
updated_at: 2026-11-05 15:40
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
