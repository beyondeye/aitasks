---
priority: medium
effort: medium
depends: [1677]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1677]
anchor: 1599
followup_kind: manual_verification
created_at: 2026-09-03 12:21
updated_at: 2026-09-03 12:21
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1677
