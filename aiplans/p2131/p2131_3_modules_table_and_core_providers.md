---
Task: t2131_3_modules_table_and_core_providers.md
Parent Task: aitasks/t2131_testmap_code_modules_tier.md
Sibling Tasks: aitasks/t2131/t2131_1_*.md, aitasks/t2131/t2131_2_*.md, aitasks/t2131/t2131_4_*.md … aitasks/t2131/t2131_12_*.md
Archived Sibling Plans: aiplans/archived/p2131/p2131_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2131_3 — Modules table, codemap and Gradle providers, `modules` verb (coarse)

## Context

- **Parent goal.** The code-module tier.
- **This child.** It creates the **table** and the **inference** with the two
  providers whose data is already exposed: the codemap and Gradle. Go and
  Python are t2131_4; membership is t2131_5; reach is t2131_6.
- **Wave:** B/C, as work package M2.7.
- **Depends on:** t2131_1.
- **Archived providers it consumes:** M2.1 t1853_1, M2.3 t1853_3, M2.5
  t1853_5 and M2.6 t1853_6.

This coarse plan records what the parent pass fixed for this slice. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first.** No human step. Agent rows keep `by:`.

> **Revised 2026-10-24 (user decision): flat code modules, no submodules.**
> Defaults 4 and 5 below are the flat versions; the contract is the
> proposal's component *Code modules* (t2131_1).

**Defaults consumed:** 1–6 and 12. The design-relevant points:
- **(1) Split between packages.**
  - `registry` owns the schema, the `_modules.yaml` loader and renderer
    (`KnownFields(true)`), the hand `modules:` table, path → module lookup and
    the `MODULE_*` rules.
  - `internal/testmap/modules` (above `deps`) owns the providers and the
    `modules --scan` writer.
- **(3) Freshness.** `MODULES_DRIFT` in `check`, measured against 300 ms. If
  over budget, the consumers fail toward full instead.
- **(4) Names (flat).** No nested records, no parent/child relation, no
  qualified ids. A generated name is `<provider prefix>:<native id>`
  (`codemap:<dir>`, `gradle:<Gradle path>`), with `/` written as `:` and the
  repository root directory as `.`; an unnameable root is
  `MODULE_REFUSED:<provider>|<root>|unnameable`. The prefixes are reserved
  for generated names. A nested hand key is refused.
- **(5) Precedence and boundaries.** Hand > agent (slot reserved here) >
  codemap > Gradle > Go/Python.
  - Codemap: every entry at any depth is a module rooted at its `path`.
    Gradle: every included project at any depth, rooted at its
    `projectDir`. Both are subtree providers: deepest root wins, and nesting
    creates no membership or expansion.
  - No subtree module at the repository root: the Gradle root project `:`
    and a codemap root entry are `MODULE_REFUSED:<provider>|.|repository_root`.
  - Each mapped path has exactly one owner; two hand modules claiming one
    path are `REGISTRY_INVALID`.
  - `MODULE_CONFLICT:` is printed once per winner/loser pair whose path sets
    overlap but differ, and for a hand/agent name collision.
  - There is no guessing fallback.
- **(6) `deps:` evidence.** Module → module `deps:` with one file-level
  evidence pair each, for inspection only.

## Reading list

- The proposal component *Code modules* (from t2131_1), *Registry loader and
  writer* (~2195) and *Scoped-row registry and areas* (~2831).
- `registry/scoped.go` (122-182, 334-342, 408-413), `registry/scan.go`
  (199-287), `registry/write.go` and `registry/areas_import.go` (79-126).
- `deps/graph.go` (119-155) and `deps/gradle.go` (144-312, line 273).
- `axes/axes.go` (352-376) and `cost/table.go`.
- CLI tests: `cmd/ait-testmap/areas_test.go` and `scancheck_test.go`.

## Owned files / provides / consumes

- **Owns:**
  - `registry/modules.go` and `registry/rules_modules.go` (new);
  - `internal/testmap/modules/**` (new: driver, `codemap` and `gradle`
    providers, `deps:` evidence);
  - `cmd/ait-testmap/modules.go` (new);
  - the `verbs.go` and `main_test.go` edits;
  - the README rows.
- **Provides:**
  - `ModulesOf(reg)`;
  - path → module lookup;
  - a provider interface for t2131_4 and t2131_9;
  - the `modules` verb;
  - the `MODULES_DRIFT` signal for t2131_6.
- **Consumes:**
  - `deps.Graph` (`Modules`, `ModuleOf`, `Facts`);
  - `registry.RegisterFile` / `RegisterHandTable` / `RegisterRule`;
  - the codemap file, read only.

## Step 0 — Reality check

1. Re-verify the anchors above.
2. Confirm that the `registry` side compiles with **no** `deps` import.
3. Measure provider overlap on a combined Gradle + codemap fixture.
4. Measure the `MODULES_DRIFT` cost against the 300 ms `check` budget, using
   the cached `deps.Scan`. Decide whether drift lives in `check` or only in
   the consumers.
5. Re-read the amended proposal component.
6. Record the outcome here.

## Implementation steps (coarse)

1. **Registry types.**
   - `Module{Name, Provider, By, Root, Paths, Gradle, Evidence, Deps}` (flat;
     `Root` for subtree and package providers, `Paths` for glob providers);
   - the hand table;
   - `_modules.yaml` load and render;
   - the lookup.
2. **The `modules` package.**
   - the driver;
   - the codemap provider (every entry at any depth; names from paths, so
     duplicate entry names across parents are harmless; a root entry is
     refused);
   - the Gradle provider (every project at any depth; `:` refused as
     `repository_root`; flags `gradle-dynamic`);
   - the name rule and `MODULE_REFUSED:`;
   - ownership (deepest root), precedence and `MODULE_CONFLICT:`;
   - `deps:` evidence.
3. **The `modules` verb.** `--list`, `--explain <path>` and `--scan
   [--apply]`, drift-gated. Update the verb-table test.
4. **The check rules.** `MODULE_CONFLICT` and `MODULES_DRIFT`.
5. **README rows.** Layout, registry tables, verbs, dependency graph.
6. **Commit.** `feature: … (t2131_3)`.

## Verification / acceptance

`ait engine test` is green, plus:
- a `_modules.yaml` load → render golden round trip;
- a codemap fixture with duplicate entry names across parents (distinct
  `codemap:` names), and a codemap root entry refused;
- a Gradle `projectDir` override;
- `gradle-dynamic` flagged;
- root `:` refused as `MODULE_REFUSED:gradle|.|repository_root`;
- the proposal's worked example 4 (a deeply nested Gradle project owns its
  subtree; no expansion to the enclosing project);
- a hand override wins and is reported; a reserved-prefix hand name refused;
  a hand/agent name collision;
- a nested `submodules:` / `children:` hand key refused;
- an unnameable root (`:` in a directory name) refused;
- a reserved `provider: agent` row loads;
- `TestVerbTableMatchesProposal` updated;
- exact-line CLI tests for the `modules` verb;
- a `MODULES_DRIFT` negative control.

## Step 9 reference

Shared post-implementation. Current branch, no merge.
