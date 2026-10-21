---
Task: t1854_11_m3_2h_gradle_class_adapter.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md, aitasks/t1854/t1854_5_*.md, aitasks/t1854/t1854_6_*.md, aitasks/t1854/t1854_7_*.md, aitasks/t1854/t1854_8_*.md, aitasks/t1854/t1854_9_*.md, aitasks/t1854/t1854_10_*.md, aitasks/t1854/t1854_12_*.md, aitasks/t1854/t1854_13_*.md, aitasks/t1854/t1854_14_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1854_11 — M3.2h gradle-class adapter

## Context

**Coarse plan only**, written at the M3.2 re-decomposition (2026-10-21). The
task body `aitasks/t1854/t1854_11_m3_2h_gradle_class_adapter.md` is authoritative. It holds the
shared evidence guarantees (G1–G10), the carried reality-check facts and the
acceptance criteria below. Its **Step 0 — Reality check** is mandatory, runs
before any code, and is recorded in this file; the detailed design is written
here after Step 0.

Child **M3.2h — `gradle-class` adapter** of t1854. Wave **3**. See the
parent's *M3.2 re-decomposition (2026-10-21)* section. Consumers: M10.4
(aitasks_mobile, one runner per source set) and M10.5 (thinking_app, until its
project runner exists).

Automation-first (user directive, 2026-10-11): no path may make a human action
a precondition.

## Owned files

- `goengines/internal/testmap/runner/builtin/gradle*.go` (owned).
- `.github/workflows/goengines-check.yml` (the Java / Gradle setup).

## Provides / consumes

- **Provides:** the `gradle-class` builtin and the shared Gradle driver, to t1854_13 (device), M10.4, M10.5 and t2082.
- **Consumes:** t1854_6 (and, through it, t1854_2, t1854_5, t1854_7).

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded here)

- Prove `--test-dry-run` on Gradle 9.x with JUnit 5 and `kotlin.test`: its report shape, and whether its identities equal execution's.
- Decide the report routing.
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
- **Classes.** `accounting: cases`, `discovery: native` if Step 0 confirms it.
- **Discovery (Step 0 evaluates and decides).**
  - Gradle's `--test-dry-run` (Gradle ≥ 8.3) is a native collector with the **same** task configuration and filters as execution.
  - The alternative is an explicit inventory. A source scan (e.g. Kotlin / Java test-annotation candidates) may only seed `candidates` and never claims complete discovery.
  - The case identity is the JUnit `classname#name`; the unit is the test class's file (kind `class`).
- **Reports.** They are routed into the fresh report directory (G6), for example by an adapter-owned init script setting the JUnit XML output location. Step 0 compares that with reading `build/test-results` under the freshness check, and stale XML is never read.
- **Execution.**
  - `timeouts: batch`, one invocation per module group: `group_by: regex:^(?:(.*?)/)?src/`, with a `{module}` placeholder in `command:` (default `./gradlew {module}:test`).
  - `--tests <FQN>` for each class in the invocation.
  - Attribution goes through the discovery inventory, including nested `Outer$Inner` classes.
  - A listed case with no result is incomplete; an unknown classname is unexpected.
- **Real-tool tests.**
  - A fixture Gradle project in the test tree (JDK 21, Gradle 9.x — `9.4.1` / `9.5.1` are cached locally — JUnit 5 and `kotlin.test`).
  - CI uses `actions/setup-java` + `gradle/actions/setup-gradle`.
  - Cases: a Kotlin file whose class name differs from the file name, a nested class, a parameterized test, a skip, an unmatched filter.
  - Optional: a read-only smoke run against aitasks_mobile's `commonTest` (a cross-repo project, via `ait projects`).
  - Without a working integration environment the task ends with the adapter **pending**, not registered for production.
- **What it reads (for t2082).** The task path, the filter flags, `filter_scope: per_unit`, and the init script (if any).

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
