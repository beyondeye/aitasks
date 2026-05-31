---
priority: medium
effort: medium
depends: [t873_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [873_1, 873_2, 873_3, 873_4]
created_at: 2026-05-31 13:24
updated_at: 2026-05-31 13:24
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
