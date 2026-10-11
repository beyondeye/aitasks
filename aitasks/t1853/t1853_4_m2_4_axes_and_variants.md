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

Child **M2.4 — Axes and variants** of t1853 (test map, module M2). Wave **C**.
Variant expansion for the selector, cost and evidence. **Providers:** M2.1
(`t1853_1`) and **M3.1 (pending: t1854 not decomposed)** — the runner
contract's `describe`. The `depends:` entry for M3.1 is added when t1854's
children exist (t1854's coarse pass, or the cross-linking task t1863).

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

- **Provides:** variant expansion and the facet join (M4.1, M3.4, M4.3, M6.4).
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
