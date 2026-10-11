---
Task: t1853_6_m2_6_adoption_tables.md
Parent Task: aitasks/t1853_testmap_m2_registry_and_map_model.md
Sibling Tasks: aitasks/t1853/t1853_1_*.md, aitasks/t1853/t1853_2_*.md, aitasks/t1853/t1853_3_*.md, aitasks/t1853/t1853_4_*.md, aitasks/t1853/t1853_5_*.md
Archived Sibling Plans: aiplans/archived/p1853/p1853_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1853_6 — M2.6 Adoption tables

## Context

Parent goal: M2 — Registry and map model (everything that reads and writes
`aitestmap/` without running a test). This is **M2.6 Adoption tables**, wave
**B**: the seeded-edge and adopted-edge rows the selector, `stale`, `readiness` and the `onboard` verbs read and write. Providers: M2.1 (`t1853_1`) and M2.2 (`t1853_2`).

This coarse plan records what the proposal fixes for M2.6. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first (user directive, 2026-10-11).** Human review belonged to an
older design. No verb, load rule or check rule shipped here may make a human
action a precondition of any path; `by: human:<email>` is an optional recorded
value, never a gate. A human-only step met in the proposal is reported to its
owning parent (note), never encoded here.

## Proposal reading list

`aidocs/testing_engine/n014_explorer_006_proposal.md` (M2 cut fixed in `3bc0de8ac`): Module Map row M2.6; *Registry loader and writer (M2.6 adoption tables)*; *Adoption ledger (M2.6 data)*; *Architecture → Where state lives* (seed queue, adopted-edge provenance, phase ledger); *The Adoption Model → The three states, with `by:`*; *Architecture → The
registry directory, Where state lives, Line-protocol index*; *Invariants every
module honours*; *Assumptions → The map and freshness (M2, M4)* and *Variants,
broad tests and runners (M2, M3)*; *Tradeoffs → Map and registry structure
(M2, M3)*. Parent plan `aiplans/p1853_testmap_m2_registry_and_map_model.md`
(Deviations from the proposal). Engine rules: `goengines/README.md` ("Rules
for engine submodules", "Interfaces"). Owns cells read `internal/<pkg>` as
`goengines/internal/testmap/<pkg>`.

## Owned files / provides / consumes

- **Owns:** the seeds and adopted tables and the `onboard.yaml` reader in `goengines/internal/testmap/registry/` (named extension of M2.1); the `SEEDED:` / `ADOPTED:` lines and load-rule reports in `check`; the fill of M2.2's post-re-stamp hook in `annot` (named extension of M2.2); goldens for the `by:` merge and the shadow rule.
- **Provides:** seeded / adopted rows and the `seeded.yaml` schema (M4.1, M4.2, M4.4, M6.2, M6.3, M7.1, M7.2, M8.2); the write routing every later writer of the three files calls.
- **Consumes:** M2.1 (loader, `check`, sorted writer); M2.2 (the post-re-stamp hook).

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded in this plan file)

Execute and record here, before writing any code:

1. Re-read the proposal's Module Map row for M2.6, its component
   subsections, and the row of every interface it consumes (*Cross-module
   interfaces*).
2. Inspect the **actual current state** of every provider on the merge target
   — verbs, line protocols, files, hooks and tests — and name the task and
   commit that landed each. The proposal and this coarse plan are claims to
   verify, never facts. Specifically:
- M2.2 as landed: the hook's actual signature and how the actor is represented.
- Which later writers (M4.2, M6.x, M7.x) have plans yet; their write-routing needs are the API's consumers.
   - The parent plan's *Repository reality anchors* (verified 2026-10-11 at
     `2fe3f8cb7`) — re-verify each one this child relies on.
3. Tabulate every difference: *proposal says* / *coarse plan says* /
   *repository has*.
4. Decide per difference: adapt this child to reality; revise this coarse
   plan; or revise the proposal (cut errors and interface changes go there,
   per the parent body's protocol §1). Record the decision and its reason.
5. Send a note (`/aitask-note`) to every downstream child whose assumptions a
   difference or decision breaks, hedging what the tree cannot prove.
6. Re-confirm that every file this child will touch is owned by M2.6 or is
   the owner's named extension (the "one owning submodule" rule).

## Implementation steps (coarse)

1. Step 0 — Reality check (above).
2. `seeded.yaml` and `adopted.yaml` row schemas (per *Where state lives*) with their own `contract:`; the two tables in the loader.
3. `onboard.yaml` reader for `rejections[]`, `reviews[]`, `kind_proposals[]`, `calibration[]`.
4. Load rules `SEED_SHADOWED`, `ADOPTED_ORPHAN`, absent-`by:`-is-human.
5. Write routing API (one entry per verb row in the *Registry loader* routing list).
6. `SEEDED:<n>` and `ADOPTED:<n>|human <h>|agent <a>|auto <m>` on `check`.
7. Fill the post-re-stamp hook: an automated actor refreshes the matching row and keeps its `by:`; an explicit human actor deletes it.

## Verification

- Goldens for the two adoption-table merges, the `by:` merge, the absent-`by:` rule and the shadow rule.
- `ADOPTED_ORPHAN`; per-file `contract:` refusal.
- `SEEDED:` / `ADOPTED:` lines on `check`.
- Write-routing unit tests per verb row.
- **Command-level re-stamp cases** through the real `verify` and `annotate` verbs, on a fixture with two `adopted.yaml` rows (the re-stamped edge and an unrelated one): an automated actor refreshes the matching row and keeps its `by:`; an explicit human actor deletes it; in both the unrelated row is byte-identical; re-stamping an edge with no provenance row leaves `adopted.yaml` untouched.
- `ait engine test` (`go vet` + `go test` over `goengines/`) green; the
  Invariants 4–5 tripwire in `goengines/guards_test.go` passes.
- No path shipped here requires a human action (automation-first).

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival; current
branch, no merge).
