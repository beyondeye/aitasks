---
Task: t1853_4_m2_4_axes_and_variants.md
Parent Task: aitasks/t1853_testmap_m2_registry_and_map_model.md
Sibling Tasks: aitasks/t1853/t1853_1_*.md, aitasks/t1853/t1853_2_*.md, aitasks/t1853/t1853_3_*.md, aitasks/t1853/t1853_5_*.md, aitasks/t1853/t1853_6_*.md
Archived Sibling Plans: aiplans/archived/p1853/p1853_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1853_4 — M2.4 Axes and variants

## Context

Parent goal: M2 — Registry and map model (everything that reads and writes
`aitestmap/` without running a test). This is **M2.4 Axes and variants**, wave
**C**: variant expansion for the selector and evidence. Providers: M2.1 (`t1853_1`) and **M3.1 (`t1854_1`)** — wired into `depends:` at t1854's coarse pass (M3 cut in `6a3a81efc`: `axis:` / `token_format:` are M2.4's alone; M3.1 refuses them until this child lands).

This coarse plan records what the proposal fixes for M2.4. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first (user directive, 2026-10-11).** Human review belonged to an
older design. No verb, load rule or check rule shipped here may make a human
action a precondition of any path; `by: human:<email>` is an optional recorded
value, never a gate. A human-only step met in the proposal is reported to its
owning parent (note), never encoded here.

## Proposal reading list

`aidocs/testing_engine/n014_explorer_006_proposal.md` (M2 cut fixed in `3bc0de8ac`): Module Map row M2.4; *Variant axes (M2.4)*; *Axis resolver verbs (M2.4)*; *Architecture → Vocabulary* (Axis and variant); `assumption_axis_sources_declarable`, `assumption_axis_membership_declarable`, `assumption_variant_universe_from_runner_list`; `tradeoff_axis_declaration_burden`, `tradeoff_axis_projection_coarseness`, `tradeoff_intersection_can_underselect`; *Architecture → The
registry directory, Where state lives, Line-protocol index*; *Invariants every
module honours*; *Assumptions → The map and freshness (M2, M4)* and *Variants,
broad tests and runners (M2, M3)*; *Tradeoffs → Map and registry structure
(M2, M3)*. Parent plan `aiplans/p1853_testmap_m2_registry_and_map_model.md`
(Deviations from the proposal). Engine rules: `goengines/README.md` ("Rules
for engine submodules", "Interfaces"). Owns cells read `internal/<pkg>` as
`goengines/internal/testmap/<pkg>`.

## Owned files / provides / consumes

- **Owns:** `goengines/internal/testmap/axes/**`; the `axes` row in `verbs.go`; the axes table + the three rules into M2.1's loader / `check` (named extension of M2.1); `axis:` / `token_format:` in M3.1's `describe` parse (named extension of M3.1).
- **Provides:** variant expansion and the facet join / forced-facet resolution (M4.1, M4.3, M6.4; M3.4 treats variant ids as opaque).
- **Consumes:** M2.1 (loader, `check` registration, `_scanned.yaml` `variants:`); M3.1 (`describe`, `list`).

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded in this plan file)

Execute and record here, before writing any code:

1. Re-read the proposal's Module Map row for M2.4, its component
   subsections, and the row of every interface it consumes (*Cross-module
   interfaces*).
2. Inspect the **actual current state** of every provider on the merge target
   — verbs, line protocols, files, hooks and tests — and name the task and
   commit that landed each. The proposal and this coarse plan are claims to
   verify, never facts. Specifically:
- M3.1 as landed: the `describe` surface, where `axis:` / `token_format:` attach, and its task / commit. If M3.1 has not landed, **stop** — this child is wave C and must not design against a missing provider.
- M4.1's plan for `select --axis` (send a note if the API shape differs).
   - The parent plan's *Repository reality anchors* (verified 2026-10-11 at
     `2fe3f8cb7`) — re-verify each one this child relies on.
3. Tabulate every difference: *proposal says* / *coarse plan says* /
   *repository has*.
4. Decide per difference: adapt this child to reality; revise this coarse
   plan; or revise the proposal (cut errors and interface changes go there,
   per the parent body's protocol §1). Record the decision and its reason.
5. Send a note (`/aitask-note`) to every downstream child whose assumptions a
   difference or decision breaks, hedging what the tree cannot prove.
6. Re-confirm that every file this child will touch is owned by M2.4 or is
   the owner's named extension (the "one owning submodule" rule).

## Implementation steps (coarse)

1. Step 0 — Reality check (above).
2. `axes.yaml` schema `{name, facets[], values{value: {facet: v}}, sources{facet: {v: [globs]}}}` and the axes table in the loader.
3. `axis:` / `token_format:` in `describe`; `<unit>@<value>` id expansion.
4. Facet join (changed paths → facet values via `sources`) and forced-facet resolution as library API; observed sources widen only.
5. The three rules `DEAD_AXIS_SOURCE`, `UNKNOWN_VARIANT`, `UNCOVERED_VALUE` registered into `check`.
6. `axes --list` (facets, values, variant counts from `_scanned.yaml`), `--check`, `--explain <path>` (`AXIS:<axis>.<facet>|<value or ->|<why>`); replace the `axes` stub row.

## Verification

- `axes --list` counts on a fixture.
- `--check` reports each of the three rules on a fixture.
- `--explain` prints `AXIS:` lines incl. `-` for no hit.
- `<unit>@<value>` ids; facet join and forced facet; observed sources widen only.
- `ait engine test` (`go vet` + `go test` over `goengines/`) green; the
  Invariants 4–5 tripwire in `goengines/guards_test.go` passes.
- No path shipped here requires a human action (automation-first).

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival; current
branch, no merge).
