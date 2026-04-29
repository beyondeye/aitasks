---
priority: medium
effort: medium
depends: [t717_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [717_1, 717_2, 717_3, 717_4]
created_at: 2026-04-30 00:49
updated_at: 2026-04-30 00:49
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.
