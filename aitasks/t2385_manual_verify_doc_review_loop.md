---
priority: medium
effort: medium
depends: [2369]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [2369]
premise_baseline: 251595ebb3deb534c2d40600297359c03aad28ae @ 2026-11-27 11:21
anchor: 2258
followup_kind: manual_verification
created_at: 2026-11-27 11:21
updated_at: 2026-11-27 11:21
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t2369
