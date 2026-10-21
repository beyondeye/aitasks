---
Task: t1854_5_m3_2b_shared_hang_watchdog.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md, aitasks/t1854/t1854_6_*.md, aitasks/t1854/t1854_7_*.md, aitasks/t1854/t1854_8_*.md, aitasks/t1854/t1854_9_*.md, aitasks/t1854/t1854_10_*.md, aitasks/t1854/t1854_11_*.md, aitasks/t1854/t1854_12_*.md, aitasks/t1854/t1854_13_*.md, aitasks/t1854/t1854_14_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1854_5 — M3.2b Shared hang watchdog

## Context

**Coarse plan only**, written at the M3.2 re-decomposition (2026-10-21). The
task body `aitasks/t1854/t1854_5_m3_2b_shared_hang_watchdog.md` is authoritative. It holds the
shared evidence guarantees (G1–G10), the carried reality-check facts and the
acceptance criteria below. Its **Step 0 — Reality check** is mandatory, runs
before any code, and is recorded in this file; the detailed design is written
here after Step 0.

Child **M3.2b — Shared hang watchdog** of t1854 (refactor). Wave **1**. See
the parent's *M3.2 re-decomposition (2026-10-21)* section.

The t1985 hang watchdog (`isolated`, `runChild`, `reapMarked`, the bounded
output scanning) and the t1998 source tripwire are unexported test code in
package `goengines/internal/testmap/runner`. Every new process-starting M3.2
package (the t1854_6 foundation, every adapter) would be outside them. The
inbox notes from t1985 and t1998 on t1854_2 flagged this. This task makes both
reusable **without changing runner's behaviour**.

Automation-first (user directive, 2026-10-11): no path may make a human action
a precondition.

## Owned files

- `goengines/internal/testmap/runner/watchdog_{unix,linux,other}_test.go` and `isolation_tripwire_test.go` (moved / reduced to wrappers).
- The new `goengines/internal/testsupport/hangguard/**`.
- `goengines/ci/preflight.sh`.

## Provides / consumes

- **Provides:** the hang guard for t1854_6, t1854_7 and every adapter.
- **Consumes:** t1985, t1998 (landed).

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded here)

Inspect the watchdog and the tripwire as landed, and list every unexported
identifier the move touches. Confirm that the controls can run from a non-test
package (`testing.T` in non-test code). Decide where the package list lives.
Tabulate the differences and decide each one.

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
- **Extraction.** The watchdog moves to `goengines/internal/testsupport/hangguard`: non-test Go code, imported only from `_test.go` files (a guard test asserts that no non-test file imports it). `runner` keeps a one-line `isolated(t, limit)` wrapper, so its guarded tests are untouched.
- **No behaviour change.** Every runner test stays guarded and passes. The watchdog's own controls (`TestIsolationControls` `HANG` / `LEAK`, `TestReapMarkedUncertainty`, `TestChildRunPattern`, `TestScanOutput`) pass from their new home.
- **Generalized tripwire.** It runs over a **declared list** of package directories, each with its own local starters and allowlist. `runner` is the first entry. `goengines/ci/preflight.sh` runs the tripwire for every listed package, so a new package opts in with one list entry. Every entry point that calls preflight (both workflows, `ait engine test`) needs nothing more.
- **Proof.** A second package (a tiny test-only fixture package, or the first real consumer if it lands first) carries a red-proved negative control: an unguarded process-starting test fails the tripwire, and a guarded test that starts nothing is `unseen`.
- `ait engine test` and both workflows stay green.

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival on the
current branch, no merge).
