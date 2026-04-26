---
priority: medium
effort: medium
depends: [645]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [645]
created_at: 2026-04-26 10:23
updated_at: 2026-04-26 10:23
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t645
