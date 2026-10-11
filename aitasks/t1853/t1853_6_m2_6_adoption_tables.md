---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-11 17:42
updated_at: 2026-10-11 17:42
---

## Context

Child **M2.6 — Adoption tables** of t1853 (test map, module M2). Wave **B**
(moved from E in the M2 cut fix: its consumers M4.1, M4.2, M4.4 and M8.2 are
waves C–D). The seeded-edge and adopted-edge rows the selector, `stale`,
`readiness` and the `onboard` verbs read and write. **Providers:** M2.1
(`t1853_1`) and M2.2 (`t1853_2`).

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
(M2 cut fixed in `3bc0de8ac`) — Module Map row M2.6, components *Registry
loader and writer (M2.6 adoption tables)* and *Adoption ledger (M2.6 data)*,
*Architecture → Where state lives* (seed queue, adopted-edge provenance, phase
ledger rows), *The Adoption Model → The three states, with `by:`*. Parent
plan: `aiplans/p1853_testmap_m2_registry_and_map_model.md` (Deviations 1, 3, 8).

**Coarse plan only.** `aiplans/p1853/p1853_6_m2_6_adoption_tables.md` records
what the proposal fixes; its **Step 0 — Reality check** (mandatory, before any
code, recorded in the plan) inspects M2.1 and M2.2 as they landed, incl. the
post-re-stamp hook's actual shape.

## Scope (from the proposal, after the M2 cut fix)

- The `seeds` table (`registry/seeded.yaml`) and the `adopted` table
  (`registry/adopted.yaml`) in M2.1's loader, each with its own `contract:`.
- `onboard.yaml`'s `rejections[]`, `reviews[]`, `kind_proposals[]`,
  `calibration[]` as read tables.
- Load rules: `SEED_SHADOWED` (a seed whose `(test, covers)` is also a stamped
  edge is dropped and reported), `ADOPTED_ORPHAN`, absent-`by:`-is-human.
- The write routing API for every verb that touches the three files (`onboard
  seed`, `onboard adopt` forms, `annotate --author`, `onboard reject`,
  `attribute --propose`, re-stamps) — later verbs call it, never write around it.
- `SEEDED:<n>` and `ADOPTED:<n>|human <h>|agent <a>|auto <m>` on `check`.
- **Fills M2.2's post-re-stamp hook** in `annotate` / `verify` (named extension
  of M2.2): an automated re-stamp (agent or engine) refreshes the matching
  `adopted.yaml` row and keeps its `by:` — a machine claim is never turned into
  a reviewed edge; only an explicit human actor deletes the row.

## Key files to modify

- The two tables and the `onboard.yaml` reader in
  `goengines/internal/testmap/registry/` (named extension of M2.1).
- The hook fill in `goengines/internal/testmap/annot/` (named extension of M2.2).
- M2.1's `check` (the two count lines and the two load-rule reports).

## Reference files for patterns

- M2.1's `registry` (loader, merge, sorted writer); M2.2's `annot` (hook);
  `goengines/internal/testmap/contract.go`.

## Provides / consumes

- **Provides:** the seeded / adopted rows and the `seeded.yaml` schema (M4.1,
  M4.2, M4.4, M6.2, M6.3, M7.1, M7.2, M8.2); the write routing.
- **Consumes:** M2.1, M2.2.

## Implementation plan (coarse)

1. Step 0 — Reality check.
2. Tables + `onboard.yaml` reader + load rules.
3. Write routing API; `check` lines.
4. The hook fill; command-level tests.

## Verification

- Goldens for the two adoption-table merges, the `by:` merge, the absent-`by:`
  rule and the shadow rule; `ADOPTED_ORPHAN`; per-file `contract:` refusal;
  the `SEEDED:` / `ADOPTED:` lines on `check`; write-routing unit tests per
  verb row.
- **Command-level re-stamp cases** through the real `verify` and `annotate`
  verbs, on a fixture with two `adopted.yaml` rows (the re-stamped edge and an
  unrelated one): an automated actor refreshes the matching row and keeps its
  `by:`; an explicit human actor deletes it; in both the unrelated row is
  byte-identical; re-stamping an edge with no provenance row leaves
  `adopted.yaml` untouched.

## Automation-first (user directive, 2026-10-11)

Human review belonged to an older design. `by: human:<email>` is an optional
recorded value, never a gate; no path shipped here waits on a person. The
absent-`by:`-is-human reading and person-only rejection are flagged to their
owning parents (M6, M7) for automation.
