---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [documentation, gates]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1687
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-22 16:56
updated_at: 2026-09-22 17:11
---

## Origin

Spawned from t1687_1 during Step 8b review.

## Upstream defect

- `aidocs/gates/gate-guarded-archival.md:28-33` — the stated criterion says a task may archive iff "every *declared* gate" passes, but `archive_status_from_text` reads the enforced active set (t635_33): a profile-filtered gate never blocks archival. Internal design doc is stale.
- `aidocs/gates/dependency-unblock-semantics.md:57-60` — the unblock pseudocode computes `required` from `U.gates` (declared); `dependents_status` reads the enforced set and drops profile-filtered `also_blocks_dependents` entries. Internal design doc is stale.

## Diagnostic context

While writing the website Gates concept page (t1687_1), every claim was checked
against `lib/gate_ledger.py`. Both design docs describe archival and dependency
unblocking in terms of the **declared** `gates:` field; the shipped code reads
the **enforced** `active_gates` tuple introduced by t635_33:

- `archive_status_from_text` docstring: "Reads the ENFORCED active set
  (t635_33): a profile-filtered gate can never block archival."
- `dependents_status` docstring: "Reads the ENFORCED active set (t635_33) — a
  profile-filtered gate must not hold dependents. `also_blocks_dependents`
  entries are filtered by the persisted `active_gates_filtered` list, dropping
  exactly the declared-but-filtered gates while keeping independent blockers."

The website page (`website/content/docs/concepts/gates.md`) follows the code.
The internal docs are what a future agent reads first, so they currently point
it at superseded behaviour. (`ledger-driven-reentry.md` also contrasts itself
with archival "which reads declared gates" — check that sentence while there.)

## Suggested fix

Update the criterion sections of both docs to state the enforced set (with the
declared set as the fallback when no valid tuple exists — `_active_set_csv` /
`read_active_tuple_from_text`), citing t635_33. Docs-only; no code change.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-22T14:11:28Z status=pass attempt=1 type=human
