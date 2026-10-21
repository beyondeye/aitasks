---
Task: t1854_2_m3_2_reference_runners.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md, aitasks/t1854/t1854_5_*.md, aitasks/t1854/t1854_6_*.md, aitasks/t1854/t1854_7_*.md, aitasks/t1854/t1854_8_*.md, aitasks/t1854/t1854_9_*.md, aitasks/t1854/t1854_10_*.md, aitasks/t1854/t1854_11_*.md, aitasks/t1854/t1854_12_*.md, aitasks/t1854/t1854_13_*.md, aitasks/t1854/t1854_14_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1854_2 — M3.2a Evidence contract

## Context

**Coarse plan only**, written at the M3.2 re-decomposition (2026-10-21). The
task body `aitasks/t1854/t1854_2_m3_2_reference_runners.md` is authoritative. It holds the
shared evidence guarantees (G1–G10), the carried reality-check facts and the
acceptance criteria below. Its **Step 0 — Reality check** is mandatory, runs
before any code, and is recorded in this file; the detailed design is written
here after Step 0.

Child **M3.2a — Evidence contract** of t1854 (test map, module M3). Wave **1**.

On 2026-10-21 M3.2 ("Reference runners") was re-decomposed around trustworthy
test evidence. The decision is in the parent's *M3.2 re-decomposition
(2026-10-21)* section and in `aiplans/p1854_testmap_m3_runners_scheduling_and_cost.md`.
This task keeps the id t1854_2 and the old file name, and is **rescoped**: it
writes the evidence guarantees into M3.1's runner contract **before any
production runner exists**. It registers no builtin.

It is a named extension of M3.1 (`goengines/internal/testmap/runner/`) and of
M3.4 (`goengines/internal/testmap/cost/`). Every other M3.2 sibling consumes
it.

Automation-first (user directive, 2026-10-11): no path may make a human action
a precondition.

## Owned files

- `goengines/internal/testmap/runner/{describe,config,list,results,outcome,invoke,run}.go` (named extensions of M3.1), plus a new `reconcile.go`.
- `goengines/internal/testmap/cost/{hook,eligibility,ledger}.go` (named extensions of M3.4).
- `goengines/cmd/ait-testmap/run.go` (the output lines), `scancheck.go` (`DISCOVERY:`).
- `goengines/README.md`; the proposal (M3.2's row and component only, plus OQ 8 and *Named follow-ups*).

## Provides / consumes

- **Provides:** the evidence contract and the shared reconciler, to t1854_6, t1854_8–t1854_14, M4.5, M6.1, M8.4.
- **Consumes:** M3.1 (t1854_1), M3.4 (t1854_4), t1985.

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded here)

Re-read the guarantees below and the parent's re-decomposition section.
Inspect `runner` and `cost` as they are on the merge target. Decide the
case-identity protocol shape. Tabulate every difference against this body,
decide each one, and send notes to any sibling whose assumptions change.
Re-confirm that every touched file is M3.2a's or a named extension.

Also, as in every M3 child:

- tabulate *task body says* / *repository has* for every difference;
- decide each one (adapt, revise this plan, or revise the proposal per the parent's protocol);
- send a note (`/aitask-note`) to each sibling or downstream task whose assumptions a decision breaks;
- re-confirm that every touched file is this task's or a named extension of its owner.

## Implementation steps (coarse)

1. Step 0 (above).
2. Implement each acceptance criterion below, tests first where a refusal is specified.
3. Red proofs: isolated mutants for every fail-closed rule the criteria name, restored byte-identical.
4. README Interfaces rows and the proposal edits the criteria name.
5. `ait engine test` green.

## Verification (= the task's acceptance criteria)
- **Describe keys.** `describe` gains `accounting: cases|unit|aggregate` (default `unit`) and `discovery: native|inventory|candidates` (default `candidates`). An unknown value is refused, and `runners.yaml` may override both (the existing D6 override rule).
- **Zero-test policy.** `runners.yaml` entries gain `zero_tests: error|skip` (default `error`, G3).
- **Expected case identities (G1a).**
  - A `cases` runner's discovery hands the engine each unit's case identities. The protocol shape is decided in Step 0: case rows in `list`, or a separate `cases` verb run in the same `Load`, so discovery is fresh for every run.
  - The engine passes them in the manifest (`units[].cases`).
  - An identity is a non-empty, line-safe string, unique within its unit. A duplicate at discovery is `INPUT_ERROR:lister`.
- **Case results.**
  - The adapter writes strict case rows to `<report_dir>/cases.jsonl`: `{"unit","case","status":pass|fail|error|skip,"duration_ms","message"?}`.
  - Under `accounting: cases`, a top-level result row from the adapter is refused (start rows stay allowed). The **engine** derives the unit's result by G1a / G1b, and computes `cases_expected / passed / failed / errored / skipped` into the result and the record.
  - Under `unit` / `aggregate`, a case row is refused.
- **One shared reconciler.**
  - It is keyed `(parent?, unit, case?)`, and both top-level `cases` units and (from t1854_14) suite child evidence go through it (G7).
  - It takes the expected identities from discovery and the reported terminal results. It returns engine-derived statuses and counters, plus the reconciliation errors.
  - Its API is what t1854_14 calls.
- **Tests (case accounting).** Expected `{a,b}`, with each of these reported:
  - `{a,a}` → `error:duplicate_case`;
  - `{a,c}` → `error:unexpected_case` (+ `incomplete`);
  - `{a}` → `incomplete`;
  - `{a,b,b}` → `duplicate_case`.

  Also: mixed pass and skip → `pass`, with the skip counted and listed; fail beside error → `fail`; error without fail → `error`; all skip → `skip`; zero expected → G3 under both policies. The same matrix is driven through the reconciler with **child-keyed** input. Isolated mutants (count-only reconciliation; adapter-supplied counters trusted) must turn the equal-count tests red.
- **Output.** `RUN_ACCOUNTING:<selected>|<cases>|<unit>|<aggregate>|<unaccounted>` (text and JSON), and `DISCOVERY:<runner>|candidates` from `run`, `scan` and `check`.
- **Freshness (G6).** The manifest gains `report_dir`, which the engine creates empty for every invocation. A `FreshReport(path, invStart)` helper refuses a file older than the start, a symbolic link, or a path outside the directory. A test covers each refusal.
- **Reporting-contract seam (G7).** `runner.RegisterReportingContract(name)`, with `children:` refused at load while the name is unregistered. M3.1's existing child-row tests register a test-only contract.
- **Ledger (M3.4).** Ledger rows record `accounting` and `discovery`. An `aggregate` result never anchors (`opaque:aggregate`); every other existing anchor decision is unchanged, and its tests stay green.
- **Docs.**
  - `goengines/README.md` Interfaces rows: the guarantee table and the status proves / does-not-prove table.
  - Proposal `aidocs/testing_engine/n014_explorer_006_proposal.md`: split the Module Map M3.2 row into M3.2a–k (the sibling table in the parent), rewrite the *Reference runners* component around G1–G10, change Open question 8's default to "no per-file evidence without an explicit report", and add the deferred integrations to *Named follow-ups (not v1)*.
- **Tests.** Every rule is pinned by a test in package `runner` / `cost` under the existing `isolated` guard. An isolated mutant proves each G2 / G3 / G6 / G7 refusal load-bearing. `ait engine test` is green.

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival on the
current branch, no merge).
