---
priority: medium
effort: medium
depends: [2167]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [2167]
anchor: 2167
followup_kind: manual_verification
created_at: 2026-10-30 11:35
updated_at: 2026-10-30 11:35
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t2167
