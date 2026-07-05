---
priority: medium
effort: medium
depends: [1119]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1119]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-05 10:19
updated_at: 2026-07-05 10:43
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1119

## Verification Checklist

- [fail] Launch a completed task's agent + shadow; ask "review the implementation" and confirm the emitted ===AITASK-CONCERNS=== block forwards via minimonitor's 'c' picker showing the REAL concerns (not the doc's placeholder example — FAIL 2026-07-05 10:43 follow-up t1123
- [x] Confirm the shadow stays advisory-only during impl-challenge — PASS 2026-07-05 10:43 Shadow impl-review cycles captured from pane %33 repeatedly stated read-only behavior and did not send keystrokes to followed pane %31; followed-agent changes came through the user review prompt.
- [x] Archived-plan fallback: run impl-challenge on an already-archived task; confirm it reads the archived plan's Final Implementation Notes and does NOT falsely warn "too early". — PASS 2026-07-05 10:43 t1119 resolves to archived task with active PLAN_FILE:NOT_FOUND; impl-challenge.md explicitly falls back to aiplans/archived/p1119_*.md, and aiplans/archived/p1119_shadow_implementation_challenge_subprocedure.md exists with ## Final Implementation Notes, so the too-early gate is bypassed for archived t1119.
- [x] Too-early gate: run impl-challenge on an in-flight task with no ## Final Implementation Notes; confirm it warns it is probably too early and offers abort/proceed. — PASS 2026-07-05 10:43 t1088 is Implementing with active plan aiplans/p1088_applink_history_coordinate_verify.md and no ## Final Implementation Notes; impl-challenge.md requires warning that review is probably too early and offering abort/proceed before reviewing partial working-tree state.
