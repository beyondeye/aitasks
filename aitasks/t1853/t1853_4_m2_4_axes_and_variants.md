---
priority: medium
effort: medium
depends: [t1853_1, t1854_1]
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-11 17:42
updated_at: 2026-10-13 19:18
---

## Context

Child **M2.4 — Axes and variants** of t1853 (test map, module M2). Wave **C**.
Variant expansion for the selector and evidence. **Providers:** M2.1
(`t1853_1`) and **M3.1 (`t1854_1`)** — the runner contract's `describe`
(edge wired at t1854's coarse pass; M3 cut fixed in `6a3a81efc`, where
`axis:` / `token_format:` are this child's extension alone and M3.1 refuses
them until it lands).

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
(M2 cut fixed in `3bc0de8ac`) — Module Map row M2.4, components *Variant axes
(M2.4)* and *Axis resolver verbs (M2.4)*, *Architecture → Vocabulary* (Axis
and variant), *Assumptions → `assumption_axis_sources_declarable`,
`assumption_axis_membership_declarable`*, *Tradeoffs →
`tradeoff_axis_declaration_burden`, `tradeoff_axis_projection_coarseness`,
`tradeoff_intersection_can_underselect`*. Parent plan:
`aiplans/p1853_testmap_m2_registry_and_map_model.md` (Deviations 3, 5).

**Coarse plan only.** `aiplans/p1853/p1853_4_m2_4_axes_and_variants.md`
records what the proposal fixes; its **Step 0 — Reality check** (mandatory,
before any code, recorded in the plan) inspects M2.1 and M3.1's actual
`describe` surface.

## Scope (from the proposal, after the M2 cut fix)

- `aitestmap/axes.yaml` `{name, facets[], values{value: {facet: v}},
  sources{facet: {v: [globs]}}}` and the axes table in M2.1's loader.
- Runner-side `axis:` / `token_format:` in `describe` (named extension of
  M3.1's `describe` parse); `<unit>@<value>` ids.
- The facet join and forced-facet resolution as library API; the `select
  --axis` flag is parsed by M4.1's `select`.
- `axes --list | --check | --explain <path>` (`AXIS:<axis>.<facet>|<value or
  ->|<why>`).
- The three axis check rules `DEAD_AXIS_SOURCE`, `UNKNOWN_VARIANT`,
  `UNCOVERED_VALUE` (registered into M2.1's `check`); observed sources widen
  only.

## Key files to modify

- `goengines/internal/testmap/axes/**` — new package (owned).
- `goengines/cmd/ait-testmap/verbs.go` — replace only the `axes` stub row.
- The axes table and rules into M2.1's loader / `check`; the `describe` fields
  into M3.1's parse (named extensions).

## Reference files for patterns

- M2.1's `registry` (table registration, `check` rule framework); M3.1's runner
  contract; `goengines/internal/testmap/fixture/`.

## Provides / consumes

- **Provides:** variant expansion and the facet join (M4.1, M4.3, M6.4; M3.4 treats variant ids as opaque and does not consume M2.4).
- **Consumes:** M2.1, M3.1.

## Implementation plan (coarse)

1. Step 0 — Reality check.
2. `axes.yaml` schema + table; id expansion; facet join / forced facet.
3. The three rules; the `axes` verb; the `describe` extension.

## Verification

- `axes --list` counts; `--check` the three rules; `--explain` `AXIS:` lines
  incl. `-`; `<unit>@<value>` ids; facet join and forced facet; observed
  sources widen only.

## Automation-first (user directive, 2026-10-11)

Human review belonged to an older design. The proposal keeps level-3 axis
*declaration* with a person (owned by M6.4 / M10); this child ships only the
data and verbs and makes no human action a precondition.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1853_1** id=2026-10-12T08:28:00Z.817726dd0c04a9892edee1c9 from=t1853_1 from_verified=yes at=2026-10-12T08:28:00Z base=c07193265578ec723aa5994ca4bf20ed5116222e base_branch=main dirty=yes host=omg16
>
> | M2.1 (registry core) landed in 0d04347ab; the proposal contract is at c07193265. Advisory, as of that tree; re-verify in your Reality check.
> | 
> | Registration points (goengines/internal/testmap/registry):
> | - Tables in hand files: RegisterHandTable(key, TableLoader). Until a submodule registers them, the keys scopes/areas are refused as REGISTRY_INVALID ("table ... not supported by this engine").
> | - Reserved files: RegisterFile(name, FileLoader). _scoped.yaml, areas.yaml, observed.yaml, seeded.yaml and adopted.yaml (and any other _-prefixed name) are refused until registered, never read as hand files. Each file passes testmap.CheckContract before its loader runs.
> | - Keep loaded data in Registry.Ext (map[string]any).
> | - Check rules: RegisterRule(CheckRule{Name, Patterns, Run}) from an init() in your own file; rules run in registration order. Run returns ([]Finding, error). Return an error, never a guess, when you cannot inspect: the run aborts with CHECK_ERROR exit 3 and never prints CHECK:. A rule that judges declared globs lists them in Patterns so it shares the run's single MatchFiles pass: a strict GlobWalk over an exclude-aware, no-follow view; existing files only.
> | - Severity: Always | StrictPastBootstrap | Info (an absent bootstrap_until means no bootstrap window).
> | - The one merge rule: a union of every file's rows in file-name order. owns: globs apply to source paths and are judged over concrete existing files.
> | 
> | For M2.4: axes.yaml lives outside registry/ and is NOT loaded by M2.1, so extend Load for it. ScannedRow.Variants is a plain sorted list of values (the final proposal's form, not n006's {axis, values}); the axis association is yours. Your three rules register as above.

> **✉ note:t1853_2** id=2026-10-12T14:30:54Z.f82dd881add813a6b95bad9b from=t1853_2 from_verified=yes at=2026-10-12T14:30:54Z base=7229dee868985aafae8cd16e493614d1904311b5 base_branch=main dirty=no host=omg16
>
> | M2.2 landed in f096db065 (contract in the proposal at 7229dee86). Advisory, as of that tree.
> | 
> | - annot.ParseFile already parses `testmap:axis <axis>.<facet>=<value>` into annot.File.Units[i].Axes ([]KeyVal{Key, Args, Line}). Only the shape is validated; no axis or value check is made.
> | - Only covers reach the registry today: registry.UnitAnnotation carries Member / Line / Covers. Extend it additively and fill the new field in toRegistry (goengines/internal/testmap/annot/source.go), as a named extension.
> | 
> | No human-only step was met.

> **✉ note:t1854_1** id=2026-10-14T14:40:29Z.eaaceed71f24bc84bfa69d5b from=t1854_1 from_verified=yes at=2026-10-14T14:40:29Z base=02e4a1badd5a7a8af9d2e250e7108cb8e1cd993e base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1854_1 (M3.1), as landed in 3d1a2b628: the describe parse refuses unknown keys, including axis: and token_format:. Your named extension is runner.RegisterDescribeKey("axis") / ("token_format") (call once each; registering an M3.1 key or a duplicate panics). Registered values land raw (yaml.Node) in Describe.Ext and survive the runners.yaml override merge. A describe must be exactly one YAML document. list kind 'variant' rows must carry @<variant>.
