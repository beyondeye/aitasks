---
priority: medium
effort: medium
depends: [t1569_4, t1569_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [t1569_1, t1569_3, t1569_4, t1569_5, t1569_6]
anchor: 1569
followup_kind: manual_verification
created_at: 2026-08-27 11:34
updated_at: 2026-08-27 11:34
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1569_1] Run `ait board` By-Trail view on a trail gathered with --with-inflight and confirm the new in-flight facts are visible without breaking the existing rendering.
- [ ] [t1569_1] Confirm an ordinary trail refresh (no --with-inflight) is unchanged and does not touch the network.
- [ ] [t1569_3] Drive the checker on the live repo and confirm CLEAR_CAVEATED is rendered visibly differently from CLEAR, not collapsed into it.
- [ ] [t1569_3] Confirm an UNCHECKABLE result names the specific in-flight task it could not rule out, not an undifferentiated "something is unknown".
- [ ] [t1569_4] Run /aitask-pick on a real task and confirm the preflight appears AFTER the remote drift check, not before.
- [ ] [t1569_4] Confirm a freshly claimed candidate does NOT conflict with itself (task-workflow locks it at Step 4, long before the plan exists).
- [ ] [t1569_4] Confirm each of CLEAR / CLEAR_CAVEATED / CONFLICT / UNCHECKABLE presents its intended disposition, and that UNCHECKABLE prints an operator remedy the user can actually act on.
- [ ] [t1569_4] Confirm the preflight re-runs on implementation re-entry (resume an in-flight task via the IMPLEMENT route).
- [ ] [t1569_5] Confirm score components AND origin quality (exact/topic/unknown) are legible per entry in the rendered trail, and that a topic-quality entry does not read like an exact one.
- [ ] [t1569_5] Confirm an uncheckable run is visibly hedged rather than silently green, including the UNKNOWN_HISTORY cause which is the easiest to render as a false all-clear.
- [ ] [t1569_6] Run /aitask-backlog-roadmap end-to-end on the live repo and confirm it produces a usable ordering.
- [ ] [t1569_6] Confirm the lanes are visually distinct in the By-Trail view via the coordination_only glyph.
- [ ] [t1569_6] Confirm neither the preflight nor the roadmap ever describes a pass as "safe to run in parallel" - both must say "no known conflict at check time" - and that the residual race is discoverable from the workflow docs.
- [ ] [t1569_6] Confirm the run summary surfaces the resolution-quality histogram and states plainly that the lanes are an estimate that reserves nothing.
