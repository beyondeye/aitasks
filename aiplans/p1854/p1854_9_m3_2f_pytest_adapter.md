---
Task: t1854_9_m3_2f_pytest_adapter.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md, aitasks/t1854/t1854_5_*.md, aitasks/t1854/t1854_6_*.md, aitasks/t1854/t1854_7_*.md, aitasks/t1854/t1854_8_*.md, aitasks/t1854/t1854_10_*.md, aitasks/t1854/t1854_11_*.md, aitasks/t1854/t1854_12_*.md, aitasks/t1854/t1854_13_*.md, aitasks/t1854/t1854_14_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1854_9 — M3.2f pytest adapter

## Context

**Coarse plan only**, written at the M3.2 re-decomposition (2026-10-21). The
task body `aitasks/t1854/t1854_9_m3_2f_pytest_adapter.md` is authoritative. It holds the
shared evidence guarantees (G1–G10), the carried reality-check facts and the
acceptance criteria below. Its **Step 0 — Reality check** is mandatory, runs
before any code, and is recorded in this file; the detailed design is written
here after Step 0.

Child **M3.2f — `pytest` adapter** of t1854. Wave **3**. See the parent's
*M3.2 re-decomposition (2026-10-21)* section. Consumers: M10.1 (aitasks'
~320 Python test modules, with the serial carve-out as `testmap:batch no`) and
thinking_backend.

Automation-first (user directive, 2026-10-11): no path may make a human action
a precondition.

## Owned files

- `goengines/internal/testmap/runner/builtin/pytest*.go` (owned).
- `.github/workflows/goengines-check.yml` (the pinned pytest install).

## Provides / consumes

- **Provides:** the `pytest` builtin, to M10.1, M6.1 `detect`, t1854_14 and t2082.
- **Consumes:** t1854_6 (and, through it, t1854_2, t1854_5, t1854_7).

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded here)

- Inspect the contract's case-identity protocol and the foundation as landed.
- Measure `--collect-only` on aitasks' tests for time and side effects.
- Confirm the junitxml fields needed to rebuild nodeids (xunit1 `file` / `classname` / `name`) against the real pytest 8.
- Tabulate the differences and decide each one.

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
- **Classes.** `accounting: cases`, `discovery: native`.
- **Discovery.**
  - `pytest --collect-only -q` per runner, run by `list` under the foundation's discovery bound (collection imports project code).
  - It uses the **same** cwd, ini, rootdir and selection arguments as execution; Step 0 pins the exact shared argument set, and a test proves the two agree.
  - The unit is a test file; its case identities are the collected nodeids.
  - A collection error is `INPUT_ERROR:lister`, never a silently dropped unit.
- **Execution.**
  - `timeouts: batch` (the entry needs `batch_timeout_s`).
  - `--junitxml` into the fresh report directory (G6).
  - Each report testcase maps to **exactly one** collected nodeid; no match or several matches is G2 `error`. The adapter writes one case row per testcase and the engine reconciles them.
- **Policies.**
  - G3: zero collected cases → `error:zero_tests` unless `zero_tests: skip`.
  - `testmap:batch no` units run as singleton invocations (tested with two such units beside a batch).
- **Real-tool tests.**
  - pytest 8.x on CPython ≥ 3.10.
  - CI installs a pinned pytest in `.github/workflows/goengines-check.yml` and sets `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1`. Locally the tests use `~/.aitask/venv` (pytest 8.4.2).
  - Cases: parametrized ids, class tests, xfail / xpass, a skip with a reason, a collection error, a rootdir above the cwd, and pytest-xdist when installed.
- **Fakes** only for malformed / ambiguous / stale report cases.
- **What it reads (for t2082).** It passes no `-c` / `--rootdir` / `-p` plugin, and the cwd is an ancestor of every listed test (the list is cwd-scoped). Any deviation decided in Step 0 is written down.

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
