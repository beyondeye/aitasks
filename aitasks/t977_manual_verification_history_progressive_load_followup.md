---
priority: medium
effort: medium
depends: [975]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [975]
created_at: 2026-06-11 12:57
updated_at: 2026-06-11 12:57
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t975
