---
Task: t1854_13_m3_2j_device_adapter.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md, aitasks/t1854/t1854_5_*.md, aitasks/t1854/t1854_6_*.md, aitasks/t1854/t1854_7_*.md, aitasks/t1854/t1854_8_*.md, aitasks/t1854/t1854_9_*.md, aitasks/t1854/t1854_10_*.md, aitasks/t1854/t1854_11_*.md, aitasks/t1854/t1854_12_*.md, aitasks/t1854/t1854_14_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1854_13 — M3.2j device adapter

## Context

**Coarse plan only**, written at the M3.2 re-decomposition (2026-10-21). The
task body `aitasks/t1854/t1854_13_m3_2j_device_adapter.md` is authoritative. It holds the
shared evidence guarantees (G1–G10), the carried reality-check facts and the
acceptance criteria below. Its **Step 0 — Reality check** is mandatory, runs
before any code, and is recorded in this file; the detailed design is written
here after Step 0.

Child **M3.2j — `device` adapter** of t1854. Wave **4**. **Postponed:** it
needs an emulator / adb integration environment, which the reference host
does not have (2026-10-21), and M3.3's allocator (t1854_3) to fill the
manifest's `handle`. See the parent's *M3.2 re-decomposition (2026-10-21)*
section. Consumer: M10.4 (aitasks_mobile `androidDeviceTest`, emulator
allocator).

**Un-park it** (set `Ready`) when both hold: t1854_3 and t1854_11 have landed,
and an emulator environment is available locally or in CI.

Automation-first (user directive, 2026-10-11): no path may make a human action
a precondition.

## Owned files

- `goengines/internal/testmap/runner/builtin/device*.go` (owned).

## Provides / consumes

- **Provides:** the `device` builtin, to M10.4.
- **Consumes:** t1854_11 (the Gradle driver) and t1854_3 (the allocator handle); through t1854_11, the foundation.

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded here)

Inspect t1854_3's allocator and handle and t1854_11's driver as landed. Choose
the discovery class. Tabulate the differences and decide each one.

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
- **Classes.** `accounting: cases`; Step 0 decides `discovery:`. Connected tests have no dry run, so an explicit inventory, or the androidTest source set with candidate semantics, is the choice.
- **Handle.** It reads the manifest's `handle` (exported as `ANDROID_SERIAL` and `AIT_TESTMAP_HANDLE`). Without one it writes nothing and exits 75 (a clean refusal, `DEVICE_NO_HANDLE:<runner>` on stderr).
- **Shared driver.** It uses t1854_11's Gradle driver: default `./gradlew {module}:connectedDebugAndroidTest`, the class filter `-Pandroid.testInstrumentationRunnerArguments.class=<FQN,…>`, and reports in the fresh report directory.
- **Support.** A **real-emulator** integration test is required before support is claimed. Until then the adapter is not registered for production.

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
