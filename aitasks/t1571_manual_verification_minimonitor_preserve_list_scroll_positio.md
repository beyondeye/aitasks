---
priority: medium
effort: medium
depends: [1539]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1539]
anchor: 1539
followup_kind: manual_verification
created_at: 2026-08-18 14:20
updated_at: 2026-08-18 14:20
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1539
