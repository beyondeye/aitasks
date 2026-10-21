---
Task: t1854_14_m3_2k_suite_reporting_contract.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md, aitasks/t1854/t1854_5_*.md, aitasks/t1854/t1854_6_*.md, aitasks/t1854/t1854_7_*.md, aitasks/t1854/t1854_8_*.md, aitasks/t1854/t1854_9_*.md, aitasks/t1854/t1854_10_*.md, aitasks/t1854/t1854_11_*.md, aitasks/t1854/t1854_12_*.md, aitasks/t1854/t1854_13_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1854_14 — M3.2k Suite reporting contract

## Context

**Coarse plan only**, written at the M3.2 re-decomposition (2026-10-21). The
task body `aitasks/t1854/t1854_14_m3_2k_suite_reporting_contract.md` is authoritative. It holds the
shared evidence guarantees (G1–G10), the carried reality-check facts and the
acceptance criteria below. Its **Step 0 — Reality check** is mandatory, runs
before any code, and is recorded in this file; the detailed design is written
here after Step 0.

Child **M3.2k — Suite reporting contract** of t1854. Wave **4**. See the
parent's *M3.2 re-decomposition (2026-10-21)* section.

It gives a `full: true` `suite` runner per-test **child** evidence, but only
from reports the suite command writes **explicitly**, with attribution
verified by the shared engine reconciler (G7). It replaces the rejected
design's injected `BASH_ENV` traps and pytest plugins. Those automatic
integrations are deferred to two standalone Postponed tasks that depend on
this one. Proposal Open question 8 is answered "no per-file evidence without
an explicit report".

Automation-first (user directive, 2026-10-11): no path may make a human action
a precondition.

## Owned files

- `goengines/internal/testmap/runner/builtin/report*.go` (owned).
- The reconciler call site in `runner` (a named extension, through t1854_2's API).
- `goengines/README.md`; the proposal (the *Reference runners* component and OQ 8).

## Provides / consumes

- **Provides:** child evidence for `full` suites, to M10.5 (thinking_app `verify-active`), M8 and the deferred automatic integrations.
- **Consumes:** t1854_12 (suite), t1854_8 / t1854_9 / t1854_10 (formats and discovery), and t1854_2 (the reconciler).

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded here)

Inspect the reconciler API, the suite adapter and the three adapters'
identities as landed. Fix each format's identity mapping. Tabulate the
differences and decide each one.

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
- **Documented formats**, written explicitly by the command into `$AIT_TESTMAP_REPORT_DIR` (the fresh report directory):
  - JUnit XML (e.g. the project's own `pytest --junitxml=$AIT_TESTMAP_REPORT_DIR/…`);
  - a `go test -json` stream file;
  - an engine-native per-test JSONL. This is the documented way a bash suite reports per-file exits (a small documented helper may write it).

  Each format is registered with `runner.RegisterReportingContract`, which un-refuses the matching `children:` names.
- **Verified attribution through the shared reconciler (G7).**
  - Each report entry is translated into a candidate `(suite parent, subsumed unit, case identity)` result. A `unit`-class subsumed runner (bash-file) uses the unit's own identity as its single case.
  - The expected identities come from each subsumed runner's own discovery in the same `Load`.
  - The engine reconciles them with **G1a / G1b**: exactly one terminal result per expected identity; a duplicate, unexpected or missing identity is an error whatever the counts; child statuses and counters are engine-derived, never taken from the report.
  - Entries that map to no subsumed unit, or ambiguously, and stale reports are refused.
  - A discovered subsumed unit with no evidence is `unaccounted` in `RUN_ACCOUNTING`, and child coverage is never claimed complete while any is.
- **No injection.** The adapter sets nothing in the command's environment except `AIT_TESTMAP_REPORT_DIR` and the t1854_7 marker: no `BASH_ENV`, no `PYTHONPATH`, no `PYTEST_ADDOPTS`.
- **Tests on the suite path**, with real tools producing the reports where possible:
  - expected `{a,b}`, reported `{a,a}` → `duplicate_case`;
  - `{a,c}` → `unexpected_case` + `incomplete`;
  - `{a}` → `incomplete`;
  - mixed pass and skip → `pass`, with the skip listed;
  - fail beside skip → `fail`;
  - a subsumed unit absent from every report → `unaccounted`;
  - a bash file reported twice → `duplicate_case`;
  - a stale report → refused.

  Isolated mutants (per-unit count matching, report-supplied counters) must turn the equal-count cases red.
- **Real-tool tests** per format, through the real pytest, go and bash adapters (G10).

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival on the
current branch, no merge).
