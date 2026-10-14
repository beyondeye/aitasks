---
priority: medium
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
created_at: 2026-10-13 19:17
updated_at: 2026-10-14 10:47
---

## Context

Child **M3.1 — Runner contract and repository** of t1854 (test map, module
M3). Wave **B**. This is the runner interface every builtin and project
script implements, the engine `run` verb, and the seams the rest of M3 (and
M2.1's `scan` / `check`) plug into. **Providers:** M1.2 (`t1852_2`), M2.1
(`t1853_1`) and M2.2 (`t1853_2`). All three are landed and archived, so the
task has no `depends:` entries.

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
(M3 cut fixed in `6a3a81efc`):

- the Module Map row M3.1;
- the component *Runner contract and repository (M3.1)*;
- *Architecture → Process map, Where state lives* (the "runs, ledger" row),
  *Line-protocol index* (the M3 row);
- *The Run Surface → Output and exit contract*;
- *Assumptions → Variants, broad tests and runners*;
- *Tradeoffs → `tradeoff_batch_misreport_risk`,
  `tradeoff_whole_run_filter_soundness`*.

Parent plan: `aiplans/p1854_testmap_m3_runners_scheduling_and_cost.md`
(Deviations 1, 2, 3, 7, 8, 9, 10, 11, 12, 13).

**Coarse plan only.** `aiplans/p1854/p1854_1_m3_1_runner_contract_and_repository.md`
records what the proposal fixes. Its **Step 0 — Reality check** is
mandatory: it runs before any code, and its outcome is recorded in the plan.
It inspects the actual providers: the `registry.UnitLister` seam,
`testmapInputs()`, and `annot/source.go` `toRegistry`.

## Scope (from the proposal, after the M3 cut fix)

- **Runner verbs.**
  - `describe`: `unit file|class|method|variant|suite`, `batch`, `needs`,
    `group_by:`, `filter_scope:`, `full:`, `children:`, `artifact_glob:`.
    **`axis:` / `token_format:` are M2.4's** named extension; refuse them as
    unknown until it lands.
  - `list` TSV `<id> <kind> <lowering> [<artifact>]` with member and variant
    ids. A malformed row is `INPUT_ERROR:lister`, never skipped.
    `SCAFFOLD_TODO` recognition is M6.4's.
  - `run --manifest` with ids, lowerings, groups and an **allocator-handle
    field** (empty when none is held; M3.3 fills it).
  - `results.jsonl` per id, with child rows under a suite parent; every row
    is marked top-level or child.
  - `runner.json` with per-group overhead rows.
- **Runner repository.**
  - `runners.yaml` first-match bindings + per-test override.
  - The `builtin:` scheme with `command:` / `cwd:` overrides.
  - Shadow-by-name, with a resolution record that M4.1's `explain` prints.
- **The canonical grouping function** `(runner, group_by group, resource
  set, wave class, batch identity)`. It is one pure function, shared by
  M3.3, M4.1 and M3.4's estimate.
  - `batch identity` is the unit's own id for a `batch: no` unit, so such
    units are singletons.
  - `wave class` (`unit` | `broad`) is the caller's input, derived from
    M2.5's kinds; no kind data means `unit`.
- **Execution semantics.**
  - Per-unit timeouts.
  - `units_expected` / `units_reported` reconciliation: zero reported with
    some expected, and a row that maps to no registered id, are mechanism
    failures.
  - The exit contract `0/1/2/75/64`.
  - `subsumed_by:`, `fallback_command:` (suite runners only), and
    `full: true` + `children:`.
- **Named extensions into landed modules.**
  - The runner-backed **UnitLister** wired into `scan` / `check` (named
    extension of M2.1, via `testmapInputs()` in
    `goengines/cmd/ait-testmap/scancheck.go`).
  - `batch` / `needs` into `registry.UnitAnnotation` (named extension of
    M2.2's `toRegistry`).
- **The engine `run` verb.**
  - `run --all` honours `subsumed_by`.
  - It runs over a **plan-executor seam**. The built-in serial plan runs one
    invocation per grouping key and **refuses a non-empty resource set
    (exit 3)** until M3.3 plugs in.
  - It has an **ordered, multi-subscriber post-run hook** (M3.4 subscribes;
    M4.4 may).
  - It keeps an **engine-owned per-invocation record** under
    `.aitask-testmap/runs/<run-id>/`. The record holds `cause` (empty |
    mechanism failure | timeout | reconciliation), HEAD at start and end,
    and the modified-path set at both moments: staged/unstaged changes,
    deletions, and untracked non-ignored files.

## Key files to modify

- `goengines/internal/testmap/runner/**` — new package (owned), excluding
  `builtin/` (M3.2).
- `goengines/cmd/ait-testmap/verbs.go` — replace only the `run` stub row.
- `goengines/cmd/ait-testmap/scancheck.go` — set `Lister` in
  `testmapInputs()` (named extension of M2.1).
- `goengines/internal/testmap/annot/source.go` — add `batch` / `needs` to
  `toRegistry`, plus the additive `registry.UnitAnnotation` fields (named
  extension of M2.2).

## Reference files for patterns

- `goengines/internal/testmap/registry/inputs.go` — the `UnitLister` /
  `Listing` / `ListedUnit` contract and `InputError`.
- `goengines/cmd/ait-testmap/scancheck.go` — the wiring point.
- `goengines/internal/lineproto` — exit codes and `Enforce`.
- `goengines/internal/platform` — `Lock`, `NewGroup`.
- `goengines/internal/gitx` — `RevParse`, `ListFiles`, scrubbed `Env`.
- `goengines/internal/testmap/fixture` — fixture repos.
- `goengines/README.md` — "Rules for engine submodules", "Interfaces".

## Provides / consumes

- **Provides:**
  - the runner contract, `results.jsonl`, the per-invocation record, the
    plan-executor seam, the post-run hook and the grouping function (M3.2,
    M3.3, M3.4, M4.1, M4.4, M6.1);
  - the lister (M2.1);
  - the `describe` parse (M2.4).
- **Consumes:** M1.2, M2.1, M2.2 (all landed).

## Implementation plan (coarse)

1. Step 0 — Reality check (in the plan file).
2. The contract types and the parse of `describe` / `list` / `results.jsonl`
   / `runner.json`.
3. The repository: `runners.yaml` bindings, `builtin:`, overrides,
   shadow-by-name.
4. The grouping function; the plan-executor seam with the built-in serial
   plan.
5. The `run` verb: manifest, timeouts, reconciliation, exit contract,
   `subsumed_by`, `full: true` children.
6. The per-invocation record (cause + provenance); the post-run hook.
7. The lister wiring into `scan` / `check`; `batch` / `needs` into the
   registry.

## Verification

- Goldens:
  - `describe` parse goldens; unknown fields (incl. `axis:`) refused;
  - `list` TSV incl. member / variant ids and the artifact column;
  - a malformed `list` row gives `INPUT_ERROR:lister`.
- Repository:
  - bindings + per-test override;
  - shadow-by-name with its resolution record.
- Grouping function:
  - each key component splits invocations;
  - two `batch: no` units with otherwise identical fields give two
    invocations;
  - a `unit` vs `broad` wave class gives two invocations;
  - no kind data means `unit`.
- Run semantics:
  - timeouts fail the unit with a timeout cause;
  - reconciliation mechanism failures;
  - runner exit 75 → 75, and an out-of-contract code → 3;
  - `run --all` runs a `subsumed_by` suite once;
  - `full: true` child rows land under their parent;
  - a non-empty resource set under the built-in plan exits 3.
- Real-lister `scan` / `check` on a fixture repo (no `INPUT_UNAVAILABLE`).
- **Provenance, red-proved:**
  - a staged deletion, an unstaged deletion, an untracked file and a
    modified file are all recorded;
  - HEAD moving mid-run is recorded;
  - a mechanism failure carries its `cause`.
- Hook subscribers fire once each, in order.
- `ait engine test` green; the Invariants 4–5 tripwire in
  `goengines/guards_test.go` passes.

## Automation-first (user directive, 2026-10-11)

Human review belonged to an older design. No path shipped here may make a
human action a precondition. A human-only step met in the proposal is
reported to its owning parent with a note, never encoded here.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-14T07:47:56Z status=pass attempt=1 type=human
