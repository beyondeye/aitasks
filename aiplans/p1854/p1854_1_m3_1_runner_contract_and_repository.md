---
Task: t1854_1_m3_1_runner_contract_and_repository.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1854_1 — M3.1 Runner contract and repository

## Context

Parent goal: M3 — Runners, scheduling and cost (everything that executes a
test and records what it cost). This is **M3.1 Runner contract and
repository**, wave **B**. It delivers:

- the runner interface every builtin and project script implements;
- the engine `run` verb;
- the canonical grouping function;
- the seams that M3.2, M3.3, M3.4, M2.1 (`scan` / `check`) and M2.4 land
  into.

Providers: M1.2 (`t1852_2`), M2.1 (`t1853_1`) and M2.2 (`t1853_2`), all
landed and archived.

This coarse plan records what the proposal fixes for M3.1. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first (user directive, 2026-10-11).** Human review belonged to
an older design. No verb or seam shipped here may make a human action a
precondition of any path. A human-only step met in the proposal is reported
to its owning parent with a note, never encoded here.

## Proposal reading list

Read `aidocs/testing_engine/n014_explorer_006_proposal.md` (M3 cut fixed in
`6a3a81efc`):

- the Module Map row M3.1;
- *Runner contract and repository (M3.1)*;
- *Cross-module interfaces* (the three M3.1 rows);
- *Architecture*: *Process map*, *Where state lives* (the "runs, ledger,
  predictions" row), *Line-protocol index* (the M3 row);
- *The Run Surface → Output and exit contract*;
- *Assumptions → Variants, broad tests and runners*
  (`assumption_variant_universe_from_runner_list`,
  `assumption_batch_per_unit_timing_reportable`);
- *Tradeoffs*: `tradeoff_batch_misreport_risk`,
  `tradeoff_whole_run_filter_soundness`;
- *Invariants every module honours*.

Also read the parent plan `aiplans/p1854_testmap_m3_runners_scheduling_and_cost.md`
(Deviations 1, 2, 3, 7, 8, 9, 10, 11, 12, 13) and the engine rules in
`goengines/README.md` ("Rules for engine submodules", "Interfaces"). Owns
cells read `internal/<pkg>` as `goengines/internal/testmap/<pkg>`.

## Owned files / provides / consumes

- **Owns:**
  - `goengines/internal/testmap/runner/**` (except `builtin/`, which is
    M3.2's);
  - the `run` row in `cmd/ait-testmap/verbs.go`;
  - the `Lister` wiring in `testmapInputs()` (`cmd/ait-testmap/scancheck.go`;
    named extension of M2.1);
  - the `batch` / `needs` fields in `annot/source.go` `toRegistry` and
    `registry.UnitAnnotation` (named extension of M2.2).
- **Provides:**
  - the runner contract, `results.jsonl` (top-level / child rows) and
    `runner.json` — to M3.2, M3.3, M3.4, M6.1;
  - the canonical grouping function — to M3.3, M4.1, M3.4;
  - the plan-executor seam — to M3.3;
  - the ordered multi-subscriber post-run hook — to M3.4, M4.4;
  - the engine per-invocation record (`cause`, HEAD start/end, the
    modified-path set) — to M3.4;
  - the manifest allocator-handle field — to M3.3, M3.2;
  - the lister — to M2.1;
  - the `describe` parse — to M2.4.
- **Consumes:** M1.2 (`lineproto`, `platform`, `gitx`, `fixture`), M2.1
  (`registry.UnitLister`, `Listing`, `ListedUnit`, `InputError`, the id
  grammar) and M2.2 (`annot` parse, `toRegistry`).

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded in this plan file)

Execute these steps and record the outcome here before writing any code:

1. Re-read the proposal's Module Map row for M3.1, its component subsection,
   and the row of every interface it consumes (*Cross-module interfaces*).
2. Inspect the **actual current state** of every provider on the merge
   target: its verbs, line protocols, files, hooks and tests. Name the task
   and commit that landed each one. The proposal and this coarse plan are
   claims to verify, never facts. In particular:
   - `registry.UnitLister` / `Listing` / `ListedUnit` and `InputError` in
     `goengines/internal/testmap/registry/inputs.go`; `testmapInputs()` in
     `goengines/cmd/ait-testmap/scancheck.go` (M2.1, `0d04347ab`).
   - `annot/source.go` `toRegistry`, and which annotation fields reach
     `registry.UnitAnnotation` today (only `covers` at `a2395c309`) (M2.2,
     `f096db065`).
   - `lineproto` exit codes / `Enforce`; `platform.Lock` / `NewGroup`;
     `gitx` for HEAD and the modified-path set (M1.2, `33012bff7`).
   - Whether M2.5 (`t1853_5`) has landed, and how it carries kinds. The
     grouping function takes the wave class as an input either way.
   - The parent plan's *Repository reality anchors* (verified 2026-10-13 at
     `a2395c309`): re-verify each anchor this child relies on.
3. Tabulate every difference in three columns: *proposal says* / *coarse
   plan says* / *repository has*.
4. Decide, per difference: adapt this child to reality; revise this coarse
   plan; or revise the proposal (cut errors and interface changes go there,
   per the parent body's protocol §1). Record the decision and its reason.
   The exact encoding of the per-invocation record and the hook payload is
   decided here and recorded.
5. Send a note (`/aitask-note`) to every downstream child whose assumptions
   a difference or decision breaks (t1854_2..4, t1853_4, and t1855's
   M4.1/M4.4 children once they exist). Hedge what the tree cannot prove.
6. Re-confirm that every file this child will touch is owned by M3.1 or is
   the owner's named extension (the "one owning submodule" rule).

## Implementation steps (coarse)

1. Step 0 — Reality check (above).
2. Contract types and parse for `describe` (every field listed in the
   component except `axis:` / `token_format:`, which are refused as
   unknown), `list` TSV (a malformed row gives `INPUT_ERROR:lister`),
   `results.jsonl` (top-level / child marking) and `runner.json`.
3. The repository: `runners.yaml` first-match bindings + per-test override,
   the `builtin:` scheme (a registration seam M3.2 fills), `command:` /
   `cwd:` overrides, shadow-by-name with its resolution record,
   `subsumed_by:`, `fallback_command:` (suite runners only), `full: true` +
   `children:`.
4. The canonical grouping function `(runner, group_by group, resource set,
   wave class, batch identity)`: singleton for `batch: no`; the wave class
   is an input, and no kind data means `unit`.
5. `run --manifest` (ids, lowerings, groups, allocator-handle field),
   per-unit timeouts, `units_expected` / `units_reported` reconciliation,
   and the exit contract `0/1/2/75/64` through `lineproto.Enforce`.
6. The engine `run` verb (replace the `run` stub row): the plan-executor
   seam; the built-in serial plan refusing a non-empty resource set (exit
   3); `run --all` honouring `subsumed_by`; the engine-owned per-invocation
   record under `.aitask-testmap/runs/<run-id>/`; the ordered
   multi-subscriber post-run hook.
7. Named extensions: the `Lister` in `testmapInputs()`; `batch` / `needs`
   into `toRegistry`.

## Verification

- `describe` parse goldens per field; an unknown field (including `axis:`
  until M2.4) is refused.
- `list` TSV parse with member and variant ids and the artifact column; a
  malformed row gives `INPUT_ERROR:lister`.
- First-match bindings and the per-test override; shadow-by-name picks the
  project script and records why.
- The grouping function:
  - each key component splits invocations;
  - two `batch: no` units with otherwise identical fields give two
    singleton invocations;
  - the same runner, group and resources with wave class `unit` vs `broad`
    give two invocations;
  - missing kind data means `unit`.
- Results mark each row top-level or child.
- A per-unit timeout fails that unit with a timeout cause.
- Reconciliation: zero-reported-some-expected and no-registered-id are
  mechanism failures, and missing ids fail.
- Runner exit 75 gives run exit 75; an out-of-contract code gives 3.
- `run --all` runs a `subsumed_by` pair's suite once and never the subsumed
  runner. `full: true` child rows land under their parent.
  `fallback_command:` is accepted only on a suite runner.
- A non-empty resource set under the built-in plan exits 3.
- `scan` / `check` with the real lister on a fixture repo no longer exits
  `INPUT_UNAVAILABLE:lister`.
- **Provenance, red-proved:** a fixture with a staged deletion, an unstaged
  deletion, an untracked file and a modified tracked file records all four
  in the modified-path set; HEAD advanced mid-run is recorded; a mechanism
  failure records its `cause`.
- Hook subscribers fire once each, in registration order.
- `ait engine test` (`go vet` + `go test` over `goengines/`) is green, and
  the Invariants 4–5 tripwire in `goengines/guards_test.go` passes.
- No path shipped here requires a human action (automation-first).

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival; current
branch, no merge).
