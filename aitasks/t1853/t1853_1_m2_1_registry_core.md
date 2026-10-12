---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
implemented_with: claudecode/opus5_5
created_at: 2026-10-11 17:42
updated_at: 2026-10-12 08:56
---

## Context

Child **M2.1 — Registry core** of t1853 (test map feature, module M2 — Registry
and map model). Wave **A**. The loaded registry every other engine package
reads, plus the `scan` and `check` verbs. **Provider:** M1.2 (`t1852_2`,
landed in `33012bff7`, archived — so not listed in `depends:`).

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
(M2 cut fixed in `3bc0de8ac`) — Module Map `#### M2` row M2.1, components
*Registry loader and writer (M2.1 core)* and *Enumeration and reconciliation
(M2.1)*, *Architecture → Vocabulary / The registry directory / Where state
lives / Line-protocol index*, *Invariants*, *Assumptions → The map and
freshness*, *Variants, broad tests and runners*, *Tradeoffs → Map and registry
structure*. Parent plan: `aiplans/p1853_testmap_m2_registry_and_map_model.md`
(Deviations 2 and 3). Engine rules: `goengines/README.md`.

**Coarse plan only.** `aiplans/p1853/p1853_1_m2_1_registry_core.md` records
what the proposal fixes and does not design internals; its **Step 0 — Reality
check** (mandatory, before any code, recorded in the plan) inspects the M1.2
tree as it is when this child is picked.

## Scope (from the proposal, after the M2 cut fix)

- `aitestmap/` layout; the id grammar `<path>[#<member>][@<variant>]`.
- The loader and its one merge rule over `aitestmap/registry/*.yaml`, with the
  **edges / rules / waivers** tables; `owns:` routing by glob. The scopes and
  areas tables land from M2.5, the axes table from M2.4, the seeds and adopted
  tables from M2.6 — leave the loader shaped for them.
- `config.yaml` schema with every key and default (the canonical block under
  *The registry directory*), `exclude:` globs (never listed, never
  `UNREGISTERED`), `docs:`, `notes:` ≤ 10 lines, `broad_threshold_s`.
- `check` with its rule framework and the rules `STALE_PATH`, `UNSTAMPED`
  (past `bootstrap_until` under `require_stamp`), `UNANNOTATED_MEMBER`,
  `DEAD_MEMBER`, `UNREGISTERED`, `UNMAPPED_ARTIFACT`; `CONTRACT_MISMATCH`
  through `testmap.CheckContract`.
- `scan --apply` persisting each member's `variants:` to `_scanned.yaml`,
  defined over **two injected inputs**: the annotation source (M2.2 plugs its
  scanner in) and the unit lister (M3.1 plugs the runner repository in). Tested
  here with fixture implementations of both.
- Deterministic sorted writes, only on change.

## Key files to modify

- `goengines/internal/testmap/registry/**` — new package (core; owned).
- `goengines/cmd/ait-testmap/verbs.go` — replace only the `scan` and `check`
  stub rows.
- `goengines/bench/baseline.txt` — the new `scan` / `check` benchmarks.

## Reference files for patterns

- `goengines/internal/testmap/contract.go` (`CheckContract`,
  `ContractMismatchError`); `goengines/internal/lineproto/` (line + exit
  helpers); `goengines/internal/testmap/fixture/` (fixture repos);
  `goengines/guards_test.go` (Invariants 4–5 tripwire);
  `goengines/README.md` "Rules for engine submodules".

## Provides / consumes

- **Provides:** the loaded registry and id grammar (every engine package);
  `check`; the injection points M2.2 and M3.1 plug into.
- **Consumes:** M1.2 only.

## Implementation plan (coarse)

1. Step 0 — Reality check (see the plan).
2. Package `registry`: id grammar, config schema, loader + merge, sorted writer.
3. `check` framework + the owned rules; `scan --apply` over the two inputs.
4. Verb rows, goldens, benchmarks.

## Verification

- Golden tests for the core merges and the id grammar (member and variant
  fragments); one fixture per owned check rule; a newer `contract:` →
  `CONTRACT_MISMATCH` exit 3; re-`scan --apply` with no change is
  byte-identical; `exclude:` paths never listed / never `UNREGISTERED`;
  `scan --apply` persists `variants:` via a fixture lister;
  `UNMAPPED_ARTIFACT`; bench `scan` / `check` < 300 ms on the aitasks shape,
  baseline recorded. `ait engine test` green.

## Automation-first (user directive, 2026-10-11)

Human review belonged to an older design. No verb, load rule or check rule
shipped here may make a human action a precondition of any path; a human-only
step met in the proposal is reported to its owning parent, not encoded.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-12T05:55:58Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-12T08:27:21Z status=pass attempt=1 type=human
