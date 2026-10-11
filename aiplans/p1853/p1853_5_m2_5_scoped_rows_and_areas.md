---
Task: t1853_5_m2_5_scoped_rows_and_areas.md
Parent Task: aitasks/t1853_testmap_m2_registry_and_map_model.md
Sibling Tasks: aitasks/t1853/t1853_1_*.md, aitasks/t1853/t1853_2_*.md, aitasks/t1853/t1853_3_*.md, aitasks/t1853/t1853_4_*.md, aitasks/t1853/t1853_6_*.md
Archived Sibling Plans: aiplans/archived/p1853/p1853_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1853_5 — M2.5 Scoped rows and areas

## Context

Parent goal: M2 — Registry and map model (everything that reads and writes
`aitestmap/` without running a test). This is **M2.5 Scoped rows and areas**, wave
**B**: the scoped join and the kind vocabulary for broad tests. Providers: M2.1 (`t1853_1`).

This coarse plan records what the proposal fixes for M2.5. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first (user directive, 2026-10-11).** Human review belonged to an
older design. No verb, load rule or check rule shipped here may make a human
action a precondition of any path; `by: human:<email>` is an optional recorded
value, never a gate. A human-only step met in the proposal is reported to its
owning parent (note), never encoded here.

## Proposal reading list

`aidocs/testing_engine/n014_explorer_006_proposal.md` (M2 cut fixed in `3bc0de8ac`): Module Map row M2.5; *Scoped-row registry and areas (M2.5)*; *Broad-test scheduling and staleness policy (M2.5 staleness half)*; *Architecture → Vocabulary* (Kind and scoped row); `assumption_areas_express_suite_blast_radius`, `assumption_broad_tests_area_scoped`; `tradeoff_area_glob_coarseness`, `tradeoff_broad_scope_coarseness`; *Architecture → The
registry directory, Where state lives, Line-protocol index*; *Invariants every
module honours*; *Assumptions → The map and freshness (M2, M4)* and *Variants,
broad tests and runners (M2, M3)*; *Tradeoffs → Map and registry structure
(M2, M3)*. Parent plan `aiplans/p1853_testmap_m2_registry_and_map_model.md`
(Deviations from the proposal). Engine rules: `goengines/README.md` ("Rules
for engine submodules", "Interfaces"). Owns cells read `internal/<pkg>` as
`goengines/internal/testmap/<pkg>`.

## Owned files / provides / consumes

- **Owns:** the scopes and areas tables in `goengines/internal/testmap/registry/` (named extension of M2.1); the `areas` and `classify` rows in `verbs.go`.
- **Provides:** the scoped join, the kind vocabulary, the onboarding signals (M4.1, M6.4).
- **Consumes:** M2.1 (loader, `check` registration).

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded in this plan file)

Execute and record here, before writing any code:

1. Re-read the proposal's Module Map row for M2.5, its component
   subsections, and the row of every interface it consumes (*Cross-module
   interfaces*).
2. Inspect the **actual current state** of every provider on the merge target
   — verbs, line protocols, files, hooks and tests — and name the task and
   commit that landed each. The proposal and this coarse plan are claims to
   verify, never facts. Specifically:
- M2.1 as landed: table / rule registration API.
- The current shape of `aitasks/metadata/code_areas.yaml` written by `aitask_codemap.sh --scan` (read-only input; the engine never runs the script — Invariant 5).
   - The parent plan's *Repository reality anchors* (verified 2026-10-11 at
     `2fe3f8cb7`) — re-verify each one this child relies on.
3. Tabulate every difference: *proposal says* / *coarse plan says* /
   *repository has*.
4. Decide per difference: adapt this child to reality; revise this coarse
   plan; or revise the proposal (cut errors and interface changes go there,
   per the parent body's protocol §1). Record the decision and its reason.
5. Send a note (`/aitask-note`) to every downstream child whose assumptions a
   difference or decision breaks, hedging what the tree cannot prove.
6. Re-confirm that every file this child will touch is owned by M2.5 or is
   the owner's named extension (the "one owning submodule" rule).

## Implementation steps (coarse)

1. Step 0 — Reality check (above).
2. `_scoped.yaml` rows `{test, kind, runner, areas, globs, triggers, reads_from, needs, reviewed_at, line}`, `registry/areas.yaml` and `areas:` blocks; the two tables in the loader; `owns:` by area name.
3. `areas` verb incl. `--import-codemap` reading `code_areas.yaml`.
4. Rules `DEAD_SCOPE`, `KIND_MISMATCH|CONVERT_TO_SUITE`; scoped rows exempt from per-edit digest staleness.
5. Kind ranking data, triggers, `reads`; the distance-1 scoped join as a function M4.1 calls.
6. `classify --suggest` with the convention and resource signals plus `fanout:<n>`, on `CLASSIFY:<test>|<kind>|<reason>`; the signal list extensible for M6.4's p95 signal.

## Verification

- `_scoped.yaml` / `areas.yaml` merge goldens.
- `areas --import-codemap` from a fixture `code_areas.yaml`.
- `owns:` by area name.
- `DEAD_SCOPE`, `KIND_MISMATCH|CONVERT_TO_SUITE` on fixtures.
- Scoped rows never digest-stale.
- `CLASSIFY:` lines for each shipped signal and `fanout:<n>`.
- `ait engine test` (`go vet` + `go test` over `goengines/`) green; the
  Invariants 4–5 tripwire in `goengines/guards_test.go` passes.
- No path shipped here requires a human action (automation-first).

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival; current
branch, no merge).
