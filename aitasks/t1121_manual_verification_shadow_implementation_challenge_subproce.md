---
priority: medium
effort: medium
depends: [1119]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1119]
created_at: 2026-07-05 10:19
updated_at: 2026-07-05 10:19
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1119

## Verification Checklist

- [ ] Launch a completed task's agent + shadow; ask "review the implementation" and confirm the emitted ===AITASK-CONCERNS=== block forwards via minimonitor's 'c' picker showing the REAL concerns (not the doc's placeholder example — the fixed pollution bug).
- [ ] Confirm the shadow stays advisory-only during impl-challenge — it never types into the followed agent's pane.
- [ ] Archived-plan fallback: run impl-challenge on an already-archived task; confirm it reads the archived plan's Final Implementation Notes and does NOT falsely warn "too early".
- [ ] Too-early gate: run impl-challenge on an in-flight task with no ## Final Implementation Notes; confirm it warns it is probably too early and offers abort/proceed.
