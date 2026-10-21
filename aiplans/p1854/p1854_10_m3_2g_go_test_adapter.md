---
Task: t1854_10_m3_2g_go_test_adapter.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md, aitasks/t1854/t1854_5_*.md, aitasks/t1854/t1854_6_*.md, aitasks/t1854/t1854_7_*.md, aitasks/t1854/t1854_8_*.md, aitasks/t1854/t1854_9_*.md, aitasks/t1854/t1854_11_*.md, aitasks/t1854/t1854_12_*.md, aitasks/t1854/t1854_13_*.md, aitasks/t1854/t1854_14_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1854_10 — M3.2g go-test + engine-test adapters

## Context

**Coarse plan only**, written at the M3.2 re-decomposition (2026-10-21). The
task body `aitasks/t1854/t1854_10_m3_2g_go_test_adapter.md` is authoritative. It holds the
shared evidence guarantees (G1–G10), the carried reality-check facts and the
acceptance criteria below. Its **Step 0 — Reality check** is mandatory, runs
before any code, and is recorded in this file; the detailed design is written
here after Step 0.

Child **M3.2g — `go-test` and `engine-test` adapters** of t1854. Wave **3**.
See the parent's *M3.2 re-decomposition (2026-10-21)* section. Consumers:
aitasks_go (`go test ./...`) and the engine's own suite (`engine-test` over
`goengines/`).

Automation-first (user directive, 2026-10-11): no path may make a human action
a precondition.

## Owned files

- `goengines/internal/testmap/runner/builtin/gotest*.go` (owned).

## Provides / consumes

- **Provides:** the `go-test` and `engine-test` builtins, to aitasks_go, the engine suite, t1854_14 and t2082.
- **Consumes:** t1854_6 (and, through it, t1854_2, t1854_5, t1854_7).

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded here)

- Inspect the contract and the foundation as landed.
- Confirm `go test -list` output and `-json` event shapes on go 1.26 and 1.27.
- Decide how a Go identity encodes Fuzz targets and examples. Examples without `// Output:` never run, so they are not cases.
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
  - `go test -list '.*' ./<pkg>` under the foundation's discovery bound. It compiles the package and runs its `init`, so it is project code.
  - Names are cross-checked against a `go/parser` scan of the package's `_test.go` files under the **same** build context (`GOFLAGS`, tags, GOOS / GOARCH, via `go/build` `MatchFile`). A mismatch refuses discovery.
  - The unit is the test file; its case identities are its top-level `Test*` / `Fuzz*` names.
- **Execution.**
  - `timeouts: batch`, `group_by: dir`.
  - `go test -json -count=1 -run '^(…)$'`, one process per package.
  - Each top-level test's terminal event becomes one case row (subtests roll up into their top-level test).
  - A build failure makes the package's units `error`; a listed name with no terminal event is incomplete → `error`.
  - A duplicate name across two files of one package is refused at discovery.
- **`engine-test`.**
  - The same adapter with engine defaults: module root `goengines/`, bind `goengines/**/*_test.go`, `go vet ./<pkg>` before each package (a vet failure fails that package's units with message `go vet`).
  - Units stay per test file, so t2081's per-file Go rules hold.
  - Acceptance: `list` covers every package of `go list ./...` (in `goengines/`) that has test files.
- **Real-tool tests** (go ≥ 1.26, the module's floor; CI already has go):
  - fixture modules;
  - a build-tagged file;
  - a duplicate name across files;
  - a test removed between list and run (substitution → `unexpected_case` / `incomplete`);
  - a panicking test;
  - a package that fails to build.
- **What it reads (for t2082).** Per-file units, the `-run` filter, the cwd, and `-count=1`.

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
