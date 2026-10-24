---
Task: t2131_5_test_module_membership.md
Parent Task: aitasks/t2131_testmap_code_modules_tier.md
Sibling Tasks: aitasks/t2131/t2131_1_*.md … aitasks/t2131/t2131_4_*.md, aitasks/t2131/t2131_6_*.md … aitasks/t2131/t2131_12_*.md
Archived Sibling Plans: aiplans/archived/p2131/p2131_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2131_5 — Test → module membership, `testmap:module`, area refs (coarse)

## Context

- **Parent goal.** The code-module tier.
- **This child.** It computes **which tests belong to which modules**, adds
  the correcting annotation, and lets areas reference modules.
- **Wave:** C (M2.7). Depends on t2131_3.
- **Archived providers:** M2.2 t1853_2 (grammar v3), M2.5 t1853_5 (areas) and
  M2.6 t1853_6 (adoption tables).

This coarse plan records what the parent pass fixed for this slice. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first:** no human step.

**Default 8 — membership**, computed at load in `registry` and never
persisted:
- **Base membership.**
  - Path containment, **plus** the modules of covered sources: `_scanned.yaml`
    covers, and hand, adopted and seeded edges.
  - Covered-source modules count even when path membership exists. This
    repo's `tests/` → `.aitask-scripts/` is the motivating case.
- **`testmap:module <name>…`.**
  - **Grammar.** A new key, allowed on any kind (unlike `area`). It reaches
    the loader through an optional `ScannedRow` field, byte-identical when
    empty.
  - **Effect.** It replaces **only** the path-derived part; covered-source
    modules stay.
  - **Drops.** An attempted drop is a finding.
- **Unresolved tests** produce `MODULE_UNRESOLVED:` (Info, counted). They are
  never guessed.

**Default 9 — areas reference modules** (revised 2026-10-24, user decision:
flat code modules; the codemap-import change is removed).
- An area may list `modules: [<name>…]`, expanded at load to those modules'
  **effective** paths. An unknown or dropped name is
  `DEAD_SCOPE:<file>|areas|<area>|module:<name>`.
- `areas --import-codemap` is **unchanged**. It keeps copying `<path>/**`
  globs and never writes module references, so an imported area's breadth
  never depends on the modules table. There is no M2.5 deviation.
- Membership has one kind only; nothing is inherited.

## Reading list

- Proposal *Code modules* (from t2131_1), *Annotation scanner and rewriter*
  (~2326-2505) and *Scoped-row registry and areas* (~2831).
- `annot/grammar.go` (48-65, 80-89, 413-533, 536-557) and `annot/source.go`
  (141-199).
- `registry/inputs.go` (33-63), `registry/scan.go` (17-44), `registry/load.go`
  (400-410) and `registry/scoped.go` (369-376, 421-469, 669-672).
- The goldens in `registry/testdata/scoped/` (`registry/areas_import.go` is
  read only, to confirm it needs no change).

## Owned files / provides / consumes

- **Owns:**
  - the `testmap:module` key (grammar, bridge, `ScannedRow` field, render,
    drift);
  - membership in `registry/modules.go`;
  - the findings in `rules_modules.go`;
  - the area module refs;
  - `modules --explain <test-id>`.
- **Provides:** `MembersOf` (test → modules with source tags), which t2131_6
  consumes. Also `MODULE_UNRESOLVED:`, which t2131_9 consumes.
- **Consumes:** the t2131_3 table and lookup; the adopted and seeded tables
  (M2.6).

## Step 0 — Reality check

1. Which effective-edge sources exist at load: covers, hand edges, adopted,
   seeded.
2. How unknown `testmap:area` names are treated. Mirror that for unknown
   module ids (refuse vs finding).
3. Confirm that `areas --import-codemap` still writes `<path>/**` globs and
   needs no change.
4. Record the outcome here.

## Implementation steps (coarse)

1. **Grammar.** Add the key (parser, `Annotated()`, goldens, conformance
   records). Then `UnitAnnotation` → `ScannedRow` field → render and
   `SCAN_DRIFT`.
2. **Membership** with source tags. The annotation semantics.
3. **Findings.** `MODULE_UNRESOLVED`, unknown id, and annotation drop.
4. **Areas.** `modules:` refs, expanded at load to effective paths, and the
   `DEAD_SCOPE:…|module:<name>` refusal.
5. **`modules --explain <test-id>`.**
6. **Commit.** `feature: … (t2131_5)`.

## Verification / acceptance

`ait engine test` is green, plus:
- parse goldens and `TestParseErrors` cases;
- a `ScannedRow` round trip, byte-identical when empty;
- the flat-`tests/` fixture gets the membership;
- the annotation replaces only path membership, and a drop is a finding;
- `MODULE_UNRESOLVED:` is counted, not failing;
- an area module ref expands to effective paths, and an unknown or dropped
  ref is refused;
- the proposal's worked example 3 (a test belonging to two modules through
  its covered sources);
- `areas --import-codemap` still writes `<path>/**` globs: with a hand `api`
  over `services/api/public/**`, the imported area `api` stays
  `services/api/**`.

## Step 9 reference

Shared post-implementation. Current branch, no merge.
