---
priority: low
effort: medium
depends: [t635_12, t635_15]
issue_type: feature
status: Ready
labels: [gates, aitakspickrem, remote]
created_at: 2026-06-10 18:56
updated_at: 2026-07-26 00:00
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
  hatch): a task with non-pass gates in its **enforced active set** is never
  archived by an autonomous run. (Enforced set = `active_gates`, NOT the raw
  `gates:` declared intent — see Premise refresh below.)
- Profile flag `auto_complete_on_all_gates_pass`: lets the autonomous lane
  finalize (status Done + archival) only when every gate in the **enforced
  active set** passes.
- pickweb constraint: no cross-branch operations — gate ledger appends and
  sidecar logs follow the existing `.aitask-data-updated/` local-storage
  model.

## Coordination (from t635_2)

t635_2 established the gate execution-profile key pattern (`record_gates`,
registered in `.aitask-scripts/lib/profile_editor.py` under the "Gates"
`PROFILE_FIELD_GROUPS` entry). When this task adds
`auto_complete_on_all_gates_pass`, register it the same way (schema + field info
+ the "Gates" group).

## Coordination (from t635_4)

Gate-guarded archival (t635_4) added the archival guard + the `--ignore-gates`
escape-hatch flag on `aitask_archive.sh`, and the **interactive** archival offers
(Step 9 immediate "Resolve now & archive" + Step 3 Check 4). This task owns:
(1) `auto_complete_on_all_gates_pass` — the profile auto-apply of those offers
(register it in `profile_editor.py` under the "Gates" group, per the t635_2 note
above); (2) making the archive guard **profile-enforced** for headless lanes (the
scope bullet above) — attended profiles keep the `--ignore-gates` escape hatch
available, headless profiles must NOT pass it. See
`aidocs/gates/gate-guarded-archival.md`.

## Premise refresh (2026-07-26 — t635_33 active-gates model)

This task was last updated 2026-06-14; **t635_33 landed 2026-07-19** and changed
what "the task's gates" means. Refreshed against live source:

- **Declared vs enforced.** Raw `gates:` is the task's *declared intent*;
  `active_gates` (materialized at claim by `aitask_gate.sh materialize-active`)
  is the *enforced set*. `gate_ledger.py` states it directly: "Every enforcer
  reads through `read_active_tuple_from_text` … Raw `gates:` stays the task's
  declared intent; `active_gates` is the enforced set." The scope bullets above
  were reworded accordingly.
- **Do not hand-roll a declared-based check.** The existing archive guard
  already resolves correctly: `aitask_archive.sh` `gate_guard()` calls
  `aitask_gate.sh archive-ready`, and the orchestrator reads
  `read_active_gates_from_text` (`gate_orchestrator.py:369,542`). The profile-
  ENFORCED headless variant must reuse that path, not re-derive from `gates:`.
  (Note `aitask_gate.sh`'s own help text and several comments still say
  "declared gates" for `archive-ready` — stale wording over correct code.)
- **The ceiling invariant constrains this task's design.** t635_33's
  user-confirmed rule: a gate filtered out by the profile ceiling is
  **invisible**, or at most reported as "skipped: execution profile" — **never
  a hard error**. A headless archive guard written against declared intent
  would block on gates the profile deliberately filtered, which is exactly the
  hard-error outcome that invariant forbids.
- **Today's headless config makes this latent.** `remote.yaml` declares
  `rendered_gates: []` and has no `record_gates` / `default_gates`, so the
  remote lane currently materializes `active_gates: []` and enforces nothing.
  Verify the new policy against a headless profile whose ceiling is non-empty,
  or the tests will pass vacuously.
- **Coordination unchanged:** t1109 still owns verifying t635_15's stop-clean /
  sign / record / re-pend behavior — but see t1109's own premise refresh; its
  procedure needs restating against the empty-ceiling remote profile before it
  can confirm anything for this task.

## References

- `aidocs/gates/aitask-gate-framework.md` (integration table,
  aitask-pickrem row)
- `aidocs/gates/gate-guarded-archival.md` (t635_4 — archival guard + --ignore-gates)
- `aidocs/gates/integration-roadmap.md` (Phase 6)
