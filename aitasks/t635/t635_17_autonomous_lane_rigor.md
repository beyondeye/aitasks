---
priority: low
effort: medium
depends: [t635_12, t635_15]
issue_type: feature
status: Ready
labels: [gates, aitakspickrem, remote]
created_at: 2026-06-10 18:56
updated_at: 2026-06-14 13:34
---

## Context

Phase 6 of `aidocs/gates/integration-roadmap.md` (priority D3 #4):
making the autonomous lanes (aitask-pickrem / aitask-pickweb) trustworthy
by using machine gates as hard verification the lane cannot skip.

## Scope

- pickrem/pickweb run `ait gates run <task-id>` as their non-skippable
  verify step (framework doc integration table row for aitask-pickrem).
- Respect human gates: stop at pending-human without escalating or
  self-signaling; report the pending state in the run summary.
- Archive guard becomes profile-ENFORCED for headless profiles (no escape
  hatch): a task with non-pass declared gates is never archived by an
  autonomous run.
- Profile flag `auto_complete_on_all_gates_pass`: lets the autonomous lane
  finalize (status Done + archival) only when every declared gate passes.
- pickweb constraint: no cross-branch operations — gate ledger appends and
  sidecar logs follow the existing `.aitask-data-updated/` local-storage
  model.

## Coordination (from t635_2)

t635_2 established the gate execution-profile key pattern (`record_gates`,
registered in `.aitask-scripts/lib/profile_editor.py` under the "Gates"
`PROFILE_FIELD_GROUPS` entry). When this task adds
`auto_complete_on_all_gates_pass`, register it the same way (schema + field info
+ the "Gates" group).

## References

- `aidocs/gates/aitask-gate-framework.md` (integration table,
  aitask-pickrem row)
- `aidocs/gates/integration-roadmap.md` (Phase 6)
