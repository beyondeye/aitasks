---
Task: t1862_update_gate_design_docs_to_enforced_set.md
Base branch: main
Output branch: main
---

# t1862 — Update gate design docs to the enforced active set

## Context

Two internal design docs describe archival and dependency unblocking in terms of
the **declared** `gates:` field. Since t635_33 the shipped code reads the
**enforced** `active_gates` tuple (materialized at claim time), falling back to
the raw `gates:` field only when no valid tuple exists. A future agent reading
these docs first is pointed at superseded behaviour. Docs-only; no code change.

Ground truth (`.aitask-scripts/lib/gate_ledger.py`):
- `read_active_tuple_from_text()` (~L692) — the single validated reader: tuple
  present + both profileless digest halves valid → authoritative (even `[]`);
  absent/stale/corrupt → raw `gates:` with `filtered=[]`. Bash twin:
  `_active_set_csv` in `aitask_gate.sh` (~L816).
- `archive_status()` / `archive_status_from_text()` (~L1864/1907) evaluate
  `read_active_gates_from_text(text)`; `_archive_status_from_state` uses
  `_gate_satisfied` = `pass` **or `skip`** (`SATISFIED_STATUSES`).
- `_dependents_status_for_text()` (~L1410): `required_unblock_gates(active,
  also_effective, registry)` where `also_effective = also − active_gates_filtered`;
  satisfied = `pass`/`skip`.

## Changes

1. `aidocs/gates/gate-guarded-archival.md`
   - **Criterion (L28-43):** reword to "every gate in the task's **enforced
     active set** is terminal-satisfied (`pass` or `skip`)", defining the active
     set as the `active_gates` tuple materialized at claim (t635_33), falling
     back to the declared `gates:` field when the tuple is absent, stale or
     corrupt (`read_active_tuple_from_text` / bash `_active_set_csv`). State the
     consequence: a declared-but-profile-filtered gate never blocks archival.
     Adjust the contrast paragraph ("archival requires *all* declared gates" →
     all *active* gates).
   - **Result table (L47-51):** `NO_GATES` = empty active set; `ALL_PASS` /
     `BLOCKED` phrased over active gates.
   - **Dormancy section (L193):** "guard keys off the declared `gates:` field" →
     keys off the enforced active set (declared field is its input/fallback).
   - Bump `updated:` frontmatter date.
2. `aidocs/gates/dependency-unblock-semantics.md`
   - **Pseudocode (L56-66):** `active = U.active_gates (validated tuple; else
     U.gates)`, `also = U.also_blocks_dependents − U.active_gates_filtered`,
     `required = {g ∈ active : blocks_dependents} ∪ also`, "satisfied (pass/skip)".
     Add a short paragraph citing t635_33: a profile-filtered gate never holds
     dependents; `also` entries are dropped only when they are declared-but-
     filtered, so independent blockers (e.g. an undeclared `merge_approved`)
     survive; an invalid tuple degrades both reads together (filtered = []).
   - **"Required set" wording** in the t1416 paragraph (L125) and the
     Dormancy paragraph (L172-176): "declared" → "active".
   - Bump `updated:`.
3. `aidocs/gates/ledger-driven-reentry.md` L33-34: "which reads declared gates …
   every *declared* gate pass?" → enforced active set / every *active* gate.

Out of scope (noted, not edited): `aidocs/gates/integration-roadmap.md:87`
("every declared gate is pass") is the historical roadmap statement of decision
D5; the archival doc is the authoritative current-state description.

## Verification

- Re-read each edited passage against the cited functions in `gate_ledger.py`.
- `grep -n "declared" aidocs/gates/gate-guarded-archival.md aidocs/gates/dependency-unblock-semantics.md aidocs/gates/ledger-driven-reentry.md`
  — remaining hits must refer to the declared field as intent/fallback only.
- No code or tests touched; no website content touched.

## Step 9

Current-branch profile: commit docs (`bug: … (t1862)`), plan via
`aitask_task_commit.sh`, then `ait gates run` + archival per task-workflow Step 9.

## Risk

### Code-health risk: low
None identified. (Docs-only edits to three internal design docs; no code, tests or generated artifacts.)

### Goal-achievement risk: low
- Rewording could misstate an edge of the fallback (stale/corrupt tuple → declared field, filtered=[]) · severity: low · → mitigation: none (verified line-by-line against `read_active_tuple_from_text` during implementation)

## Final Implementation Notes
- **Actual work done:** Rewrote the archival criterion + result table + Dormancy line in `gate-guarded-archival.md`, the unblock pseudocode (with a new t635_33 paragraph) plus three "declared" wording sites in `dependency-unblock-semantics.md`, and the archival-contrast sentence in `ledger-driven-reentry.md`, all to describe the enforced `active_gates` set with the validated-tuple → raw `gates:` fallback.
- **Deviations from plan:** Also corrected the satisfaction predicate from "`pass`" to "`pass` or `skip`" (`SATISFIED_STATUSES`) in both criteria, since it sat in the same sentences being rewritten; and fixed the D5 problem-statement line (L26) of the dependency doc.
- **Issues encountered:** None.
- **Key decisions:** Left `aidocs/gates/integration-roadmap.md:87` untouched — it is the historical roadmap statement of decision D5, not a current-state description.
- **Upstream defects identified:** None
