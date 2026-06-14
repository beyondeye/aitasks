---
priority: high
effort: medium
depends: [t635_5, t635_6]
issue_type: feature
status: Ready
labels: [gates, aitask_pick]
created_at: 2026-06-10 18:53
updated_at: 2026-06-10 18:53
---

## Context

Phase 2 of `aidocs/gates/integration-roadmap.md` (decision D8): aitask-pick
stays the single user-facing front door — it becomes gate-aware instead of
a second "gates workflow" growing beside it.

## Scope

- aitask-pick lists in-flight tasks (ledger entries present, not archived)
  in their own pick-list section, showing derived gate/checkpoint state
  (e.g. "3/4 — pending review").
- Picking an in-flight task routes through the resume logic (t635_5 /
  t635_6) — resume from the first unmet checkpoint, never restart at
  planning.
- The board's existing agent launch (`/aitask-pick <n>`,
  `.aitask-scripts/board/aitask_board.py` ~4390/4543/4710) gains re-entry
  with no board change.
- Selection rules: in-flight tasks must remain distinguishable from Ready
  tasks; direct selection (`/aitask-pick <n>`) of an in-flight task resumes
  with a confirmation showing the derived state.
- Per-profile rendering + goldens regeneration as usual.

## Out of scope

Board In-Flight view (t635_9); pickrem/pickweb autonomous-lane behavior
(t635_17).

## Coordination (from t635_4)

Gate-guarded archival (t635_4) added Step 3 **Check 4**: on pick, a task whose
declared gates now all pass (`aitask_gate.sh archive-ready` → `ALL_PASS`) is
offered archival. The in-flight pick section this task builds should surface
those deferred-archival tasks (status `Implementing` + `## Gate Runs` entries,
not archived) and route an `ALL_PASS` one to that archival offer. **Consume**
`aitask_gate.sh archive-ready` / `gate_ledger.archive_status` for the derived
state — do NOT fork the decision. See `aidocs/gates/gate-guarded-archival.md`.

## References

- `aidocs/gates/integration-roadmap.md` (Phase 2, D8)
- `.claude/skills/aitask-pick/SKILL.md.j2` (Steps 0b-2d task listing)
