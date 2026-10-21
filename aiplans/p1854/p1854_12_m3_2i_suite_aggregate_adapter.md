---
Task: t1854_12_m3_2i_suite_aggregate_adapter.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md, aitasks/t1854/t1854_5_*.md, aitasks/t1854/t1854_6_*.md, aitasks/t1854/t1854_7_*.md, aitasks/t1854/t1854_8_*.md, aitasks/t1854/t1854_9_*.md, aitasks/t1854/t1854_10_*.md, aitasks/t1854/t1854_11_*.md, aitasks/t1854/t1854_13_*.md, aitasks/t1854/t1854_14_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1854_12 — M3.2i suite aggregate adapter

## Context

**Coarse plan only**, written at the M3.2 re-decomposition (2026-10-21). The
task body `aitasks/t1854/t1854_12_m3_2i_suite_aggregate_adapter.md` is authoritative. It holds the
shared evidence guarantees (G1–G10), the carried reality-check facts and the
acceptance criteria below. Its **Step 0 — Reality check** is mandatory, runs
before any code, and is recorded in this file; the detailed design is written
here after Step 0.

Child **M3.2i — `suite` aggregate adapter** of t1854. Wave **3**. See the
parent's *M3.2 re-decomposition (2026-10-21)* section.

It wraps any command as **one aggregate unit**: the pre-onboarding
`test_command` (with `fallback_command:`), thinking_app's `verify-active`,
aitasks_go's `go test ./...`. Per-test child evidence is **not** here. That is
t1854_14's explicit reporting contract, and `children:` stays refused until it
lands (G7).

Automation-first (user directive, 2026-10-11): no path may make a human action
a precondition.

## Owned files

- `goengines/internal/testmap/runner/builtin/suite*.go` (owned).

## Provides / consumes

- **Provides:** the `suite` builtin, to t1859_4 (M8.4 `fallback_command`), t1854_14, M6.1 `detect` and M10.5.
- **Consumes:** t1854_6 and t1854_7 (and, through t1854_6, t1854_2 and t1854_5).

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded here)

Inspect the foundation, the contract and the guard as landed. Re-check t1857's
`detect` recursion note (the pre-enable `test_command` snapshot). Tabulate the
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
- **Classes.** `accounting: aggregate`, `discovery: inventory`.
- **The unit.** One per runner entry, id `aitestmap/runners.yaml#<name>`, kind `suite`. That file exists and has no member blocks, so there is no member drift.
- **Run.** The command (`command:`, required — `describe` refuses without it) runs through the foundation as `sh -c` (the same trust as `test_command`), with output to a log in the invocation directory, never to the builtin's capped stdout. `timeouts: none` (an engine singleton).
- **Result.** The command's exit is the aggregate result. A pass proves only that the command exited 0; no individual test result is ever inferred from it. `aggregate` never anchors (t1854_2).
- **Recursion.**
  - An early **diagnostic**: `describe` refuses a command whose words name the test front (`ait test`, `ait testmap test|run`, `ait-testmap test|run`, or a word whose basename is `aitask_test.sh`) with `SUITE_RECURSION:<runner>|<word>`. The `aitask_test.sh` literal carries `// invariant5-ok: named only to refuse it`.
  - The **runtime** protection is t1854_7's guard.
  - Test: a nested `./ait`-style call hidden behind a script is refused at runtime.
- **`fallback_command:`** stays M3.1's key (only on `unit: suite`); this adapter does not run it (M8.4 does).
- **Real-tool tests.** Real `sh` commands: pass, fail, a timeout with a `setsid` descendant (contained), an output past the cap.

Common to every adapter:

- **It runs only through the t1854_6 foundation.** Discovery and execution run inside the containment, under the t1854_7 recursion marker. There is no direct `exec`; a package-level tripwire test enforces it, and every test runs under the t1854_5 hang guard.
- **Recursion.** A real-tool test where the adapter's **discovery** (or inventory step) and its **execution** each try a nested `run` / `check` of the same repository: both are refused with `RUN_ERROR:recursion`, and the invocation reports it. The same nested call against a fixture repository succeeds.
- **`cases` adapters (pytest, go-test, gradle-class, device).**
  - The adapter writes one case row per terminal tool result, keyed by the **same identity its discovery produced**.
  - It never collapses or deduplicates rows itself, so the engine's reconciler (t1854_2) sees duplicates.
  - Tests: an equal-count substitution produced by the real tool (a test renamed between discovery and execution) → `error:incomplete` / `unexpected_case`; colliding identities at discovery → `duplicate_case`.
- **Containment.** Where the foundation reports `CONTAINMENT_UNAVAILABLE`, the adapter refuses; it never runs uncontained.
- **Support claims (G10).**
  - The supported tool versions and platforms are stated in `describe` docs and in the README row.
  - Real-tool integration tests run in CI with `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1` (skips become failures there) or in a documented environment.
  - Fakes are used only for targeted failure cases (malformed, ambiguous or stale reports).
  - Without an integration environment the adapter stays **pending** and is not registered for production.
- **What it reads.** Final Implementation Notes list the adapter's command line, cwd and the config flags it passes, for t2082.
- `ait engine test` is green.

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival on the
current branch, no merge).
