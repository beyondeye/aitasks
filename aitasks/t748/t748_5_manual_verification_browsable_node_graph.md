---
priority: medium
effort: medium
depends: [t748_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [748_1, 748_2, 748_3, 748_4]
created_at: 2026-05-17 10:16
updated_at: 2026-05-17 10:16
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
