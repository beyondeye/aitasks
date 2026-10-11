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

Child **M2.5 — Scoped rows and areas** of t1853 (test map, module M2). Wave
**B**. The scoped join and the kind vocabulary for broad tests. **Provider:**
M2.1 (`t1853_1`).

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
(M2 cut fixed in `3bc0de8ac`) — Module Map row M2.5, components *Scoped-row
registry and areas (M2.5)* and *Broad-test scheduling and staleness policy
(M2.5 staleness half)*, *Architecture → Vocabulary* (Kind and scoped row),
*Assumptions → `assumption_areas_express_suite_blast_radius`,
`assumption_broad_tests_area_scoped`*, *Tradeoffs →
`tradeoff_area_glob_coarseness`, `tradeoff_broad_scope_coarseness`*. Parent
plan: `aiplans/p1853_testmap_m2_registry_and_map_model.md` (Deviations 3, 6).

**Coarse plan only.** `aiplans/p1853/p1853_5_m2_5_scoped_rows_and_areas.md`
records what the proposal fixes; its **Step 0 — Reality check** (mandatory,
before any code, recorded in the plan) inspects M2.1 as it landed.

## Scope (from the proposal, after the M2 cut fix)

- `_scoped.yaml` rows `{test, kind, runner, areas, globs, triggers,
  reads_from, needs, reviewed_at, line}`; `registry/areas.yaml` and `areas:`
  blocks in hand files; the scopes and areas tables in M2.1's loader.
- `areas --import-codemap` — reads `aitasks/metadata/code_areas.yaml`; never
  runs `aitask_codemap.sh` (Invariant 5).
- `owns:` by area name; kind ranking data; triggers; `reads`.
- Check rules `DEAD_SCOPE`, `KIND_MISMATCH|CONVERT_TO_SUITE`; scoped rows
  exempt from per-edit digest staleness.
- The scoped join (distance 1) as data + function for M4.1 (the ranking, the
  suite budget and `DEFERRED` are M4.1's verbs; missing-trigger attribution is
  M4.4's).
- `classify --suggest` with the source-set / directory-convention and the
  resource-declaration signals plus `fanout:<n>` above `unit_covers_max`, on
  `CLASSIFY:<test>|<kind>|<reason>`. The recorded-p95 signal lands from M6.4
  (named extension; it needs M3.4's cost ledger) — leave the signal list
  extensible.

## Key files to modify

- The scoped tables in `goengines/internal/testmap/registry/` (named extension
  of M2.1's loader).
- `goengines/cmd/ait-testmap/verbs.go` — replace only the `areas` and
  `classify` stub rows.

## Reference files for patterns

- M2.1's `registry`; `.aitask-scripts/aitask_codemap.sh` (the shape of
  `code_areas.yaml` only); `goengines/internal/testmap/fixture/`.

## Provides / consumes

- **Provides:** the scoped join, the kind vocabulary, the onboarding signals
  (M4.1, M6.4).
- **Consumes:** M2.1.

## Implementation plan (coarse)

1. Step 0 — Reality check.
2. Tables + merge; `areas` verb incl. `--import-codemap`.
3. Rules; staleness exemption; scoped join API.
4. `classify --suggest`.

## Verification

- `_scoped.yaml` / `areas.yaml` merge goldens; `areas --import-codemap` from a
  fixture `code_areas.yaml`; `owns:` by area name; `DEAD_SCOPE`,
  `KIND_MISMATCH|CONVERT_TO_SUITE`; scoped rows never digest-stale;
  `CLASSIFY:` lines for each shipped signal and `fanout:<n>`.

## Automation-first (user directive, 2026-10-11)

Human review belonged to an older design. The proposal keeps *kind changes*
with a person (applied by M6.4); this child only suggests and makes no human
action a precondition.
