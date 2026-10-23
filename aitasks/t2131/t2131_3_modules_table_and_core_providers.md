---
priority: medium
effort: high
depends: [t2131_1]
issue_type: feature
status: Ready
labels: [testmap, go_engine, testing]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-23 11:50
updated_at: 2026-10-23 11:50
---

## Context

Child 3 of t2131 (test-map code-module tier).
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`, defaults 1–6 and 12.
- **Coarse plan:** `aiplans/p2131/p2131_3_modules_table_and_core_providers.md`.
- **Wave:** B/C, as work package **M2.7 — Code modules**.
- **Depends on:** t2131_1 (the proposal amendment that fixes the contract).
- **Archived providers it consumes:** M2.1 (t1853_1), M2.3 (t1853_3), M2.5 (t1853_5) and M2.6 (t1853_6).

This child creates the modules **table** and its **inference** with the two providers whose data the dependency graph already exposes: the codemap and Gradle. Go and Python packages are t2131_4. Membership is t2131_5. Reach is t2131_6.

**Automation-first:** no human step anywhere. Agent rows keep `by:` provenance.

**Design defaults, quoted from the parent plan:**
- **(1) Home.** `registry` owns:
  - the schema and the `_modules.yaml` loader and renderer (`KnownFields(true)`);
  - the hand `modules:` table;
  - path → module lookup;
  - the `MODULE_*` rules.

  A new package `internal/testmap/modules`, above `deps` (import direction `registry ← annot ← deps`), owns the providers and the `modules --scan` writer. The `runner` grouping (t2131_10) needs the `registry`-side lookup only.
- **(2) Verb `modules`.** It takes `--list`, `--explain <path>` and `--scan [--apply]`. The `--scan` writer is drift-gated like `scan --apply`. The verb is added to the proposal verb list, so `TestVerbTableMatchesProposal` changes.
- **(3) Freshness.** `check` gains `MODULES_DRIFT` (like `SCAN_DRIFT`): a live re-inference over the cached `deps.Scan`, within the 300 ms budget. If that is over budget, drift detection moves to the consumers, still failing toward full.
- **(4) Ids and tiers.** Names are id fragments, and the qualified form is `<module>/<submodule>`. Submodules nest under their module in YAML, so two tiers are enforced by the schema. Submodule names are unique within their module.
- **(5) Providers, in precedence order.** Rank 1 wins:
  1. hand overrides;
  2. `provider: agent` proposals (**reserve the slot now**: enum value + `by:`; t2131_9 writes them);
  3. the codemap (`aitasks/metadata/code_areas.yaml`, read directly and never run; parent → module, child → submodule; duplicate child names across parents are fine);
  4. Gradle (`:a` → module, `:a:b` → submodule, deeper folds into `:a:b`; **the root project `:` is not a module**, because `within("")` contains every path);
  5. Go / Python (t2131_4).

  Every row records `provider:` and its evidence. A disagreement is always `MODULE_CONFLICT:`, even when precedence settles it. There is no guessing fallback.
- **(6) Module → module `deps:`.** One file-level evidence pair each. Inspection only.

## Key Files to Modify

- `goengines/internal/testmap/registry/modules.go` (new): types, loader (`RegisterFile("_modules.yaml")`, `RegisterHandTable("modules")`), render, path → module lookup, `ModulesOf(reg)`.
- `goengines/internal/testmap/registry/rules_modules.go` (new): `MODULE_CONFLICT`, `MODULES_DRIFT` (`RegisterRule`).
- `goengines/internal/testmap/modules/` (new package): the inference driver, the `codemap` and `gradle` providers, and the `deps:` evidence.
- `goengines/cmd/ait-testmap/verbs.go`, `modules.go` (new), `main_test.go` (`proposalVerbs`, `TestStubsExit64` list).
- `goengines/README.md`: the layout and interface rows (registry tables, verbs, dependency graph).

## Reference Files for Patterns

- `registry/scoped.go`:
  - `_scoped.yaml` plus the `areas:` / `scopes:` hand tables (122-182, 408-413);
  - `WithGenerated` live view;
  - `checkAreaName` (334-342).
- `registry/scan.go`: the drift-gated writes (199-287) and `ScannedDoc`. `registry/write.go`: `Render` / `WriteFile` / `GeneratedHeader`.
- `registry/areas_import.go` `ReadCodemap` (79-126). The codemap reader to reuse, **without** its flattening.
- `deps/graph.go` `Modules()` / `ModuleOf()` (119-155). `deps/gradle.go` (dynamic widening, line 273).
- `axes/axes.go:352-376` (a package above `registry` registering from `init`). `cost/table.go` (a generated table written by its own verb).
- CLI test style: `cmd/ait-testmap/areas_test.go`, `scancheck_test.go` (`repo(t)`, `write`).

## Implementation Plan

1. **Step 0 — Reality check.**
   - Measure provider overlap on a combined Gradle + codemap fixture.
   - Measure `MODULES_DRIFT` against the 300 ms `check` budget.
   - Confirm that the `registry` side needs no `deps` import.
   - Re-read the amended proposal component.
2. Registry schema, loader, renderer, hand table and lookup. The `provider` enum includes the reserved `agent`.
3. The `modules` package: the driver, the codemap and Gradle providers, precedence, conflicts and `deps:` evidence.
4. The `modules` verb and its CLI tests. Update the verb-table test.
5. The `MODULE_CONFLICT` and `MODULES_DRIFT` check rules.
6. README interface rows.

## Verification Steps

`ait engine test` is green, plus:
- a `_modules.yaml` load → render golden round trip;
- a codemap fixture with duplicate child names across parents;
- a Gradle `projectDir` override;
- `gradle-dynamic` flagged;
- root `:` excluded;
- a hand override wins and is reported;
- three-tier input refused;
- a reserved `provider: agent` row loads;
- exact-line CLI tests for `modules --list` / `--explain` / `--scan [--apply]`;
- a `MODULES_DRIFT` negative control.
