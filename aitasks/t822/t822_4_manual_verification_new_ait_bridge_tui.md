---
priority: medium
effort: medium
depends: [t822_3]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [822_2]
created_at: 2026-05-24 09:36
updated_at: 2026-05-24 09:36
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
