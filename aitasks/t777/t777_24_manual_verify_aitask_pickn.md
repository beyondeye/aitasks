---
priority: medium
effort: medium
depends: [t777_23]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [777_6]
created_at: 2026-05-18 15:52
updated_at: 2026-05-18 15:52
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
