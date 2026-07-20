---
priority: medium
effort: medium
depends: [1123]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1123]
created_at: 2026-07-05 11:52
updated_at: 2026-07-05 11:52
boardidx: 170
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1123

## Verification Checklist

- [ ] Launch a completed task's agent + shadow; ask "review the implementation" and confirm minimonitor's 'c' picker forwards the REAL emitted concerns (not concern-format.md's placeholder example). This is the live re-run of the t1121 item #1 that failed and drove t1123.
- [ ] Confirm that if the shadow reads/quotes concern-format.md during the review, its format example is NOT isolated by the picker (no contiguous open→items→close block remains in the doc).
- [ ] Confirm the shadow stays advisory-only during the impl-challenge review (no keystrokes sent to the followed pane).
