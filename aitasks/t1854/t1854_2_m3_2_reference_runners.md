---
priority: medium
effort: high
depends: [t1854_1]
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-13 19:17
updated_at: 2026-10-13 19:18
---

## Context

Child **M3.2 — Reference runners** of t1854 (test map, module M3). Wave
**B**. These are the builtins built into the binary, so every target
repository can list and run its units without a project script.
**Provider:** M3.1 (`t1854_1`).

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
(M3 cut fixed in `6a3a81efc`):

- the Module Map row M3.2;
- the component *Reference runners (M3.2)*;
- *Onboarding → Detection, per target repository*, for what each target
  needs;
- *Assumptions → `assumption_batch_per_unit_timing_reportable`*;
- *Tradeoffs → `tradeoff_batch_misreport_risk`*;
- *Open questions* item 8: the bash-file per-file exit is the default.

Parent plan: `aiplans/p1854_testmap_m3_runners_scheduling_and_cost.md`
(Deviations 3, 5 and 6).

**Coarse plan only.** `aiplans/p1854/p1854_2_m3_2_reference_runners.md`
records what the proposal fixes. Its **Step 0 — Reality check** is
mandatory, runs before any code, and is recorded in the plan. It inspects
M3.1 as landed (the contract, the manifest handle field, the top-level /
child row marking).

## Scope (from the proposal, after the M3 cut fix)

- `ait-testmap runner <name>`: replace only the `runner` stub row.
- `bash-file`. **No `list --invocations`**: the seeder reads M2.3's facts
  directly.
- `pytest`: junitxml; `testmap:batch no` honoured, so those units run
  outside the batch.
- `go-test`: per-file `-run` regex, `-json`.
- `gradle-class`:
  - a `--tests <lowering>` batch, one invocation per `group_by` group;
  - JUnit XML inverted to ids through the list table;
  - the zero-match trap is a mechanism failure.
- `suite`: any command as one unit, with optional child rows from a
  `children:` post-processor.
- `device`: reads the allocator handle from the manifest's handle field
  (M3.3 fills it) and refuses without one.
- `engine-test`: over `goengines/`.
- The `full` suite wrapper's `children:` post-processors:
  - pytest junitxml;
  - bash-file per-file exit;
  - `go test -json`.
- **Out of scope:** the serial carve-out agreement check in
  `tests/test_serial_carveout_doc_drift.sh` moves to **M10.1**, which writes
  the annotations it checks.
- **Recursion refusal (for the Reality check to decide).** A `full` suite
  command that reaches `./ait test` recurses, and through `aitask_test.sh`
  it would also violate Invariant 5. The Reality check decides how it is
  refused.

## Key files to modify

- `goengines/internal/testmap/runner/builtin/**`: a new package (owned).
- `goengines/cmd/ait-testmap/verbs.go`: replace only the `runner` stub row.

## Reference files for patterns

- M3.1's `internal/testmap/runner` contract and its fixture runners.
- `goengines/internal/testmap/fixture`.
- `tests/run_all_python_tests.sh`, for the pytest invocation shape and the
  serial carve-out.

## Provides / consumes

- **Provides:** runners for every target repository without a project script
  (M4.5, M6.2, M8.4 `fallback_command`, M10.4 `gradle-class` / `device`,
  M10.5).
- **Consumes:** M3.1.

## Implementation plan (coarse)

1. Step 0 — Reality check (in the plan file).
2. The `runner <name>` verb and the builtin registration into M3.1's
   `builtin:` scheme.
3. `bash-file`, `pytest`, `go-test`, `engine-test`.
4. `gradle-class` with JUnit inversion and the zero-match trap.
5. `suite` + the three `children:` post-processors; `device`.

## Verification

- Each builtin lists and runs one passing and one failing unit on a fixture
  repo.
- pytest:
  - junitxml inversion;
  - `testmap:batch no` units run outside the batch.
- `go-test -json`, per file.
- `gradle-class`, against a fake Gradle emitting JUnit XML:
  - one invocation per `group_by` group;
  - the zero-match trap.
- `suite` child rows through each of the three post-processors.
- `device`:
  - reads a fixture handle;
  - refuses without one.
- `engine-test` lists the `goengines/` packages.
- A `full` suite command reaching `./ait test` is refused.
- `ait engine test` is green.

## Automation-first (user directive, 2026-10-11)

Human review belonged to an older design. No path shipped here may make a
human action a precondition. A human-only step met in the proposal is
reported to its owning parent with a note, never encoded here.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1854_1** id=2026-10-14T14:40:22Z.2574bb9073e9e268803b4cca from=t1854_1 from_verified=yes at=2026-10-14T14:40:22Z base=02e4a1badd5a7a8af9d2e250e7108cb8e1cd993e base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1854_1 (M3.1), as landed in 3d1a2b628. Verify against goengines/README.md → Interfaces and internal/testmap/runner before relying on it.
> | 
> | - Builtins: call runner.RegisterBuiltin(name) for each builtin you ship; registering a name twice panics. A runners.yaml `builtin: <name>` runs `<ait-testmap> runner <name> describe|list|run --manifest <abs>` in the runner's cwd. Env: AIT_TESTMAP_ROOT, AIT_TESTMAP_RUNNER, AIT_TESTMAP_COMMAND (the `command:` override), AIT_TESTMAP_RUN_ID. An unregistered builtin is refused (RUNNER_UNRESOLVED). An executable aitestmap/runners/<name>.sh shadows it.
> | - Timeout model: every builtin must declare `timeouts:` in its describe and prove it with its own enforcement and cleanup tests.
> |   - per_unit: write `{"id":…,"event":"start"}` before each unit, bound it by the manifest's timeout_s, kill that unit's process group on expiry, report status "timeout", and continue to the next unit. A result reported past timeout_s plus 2 s is flagged timeout_not_enforced.
> |   - batch: the runners.yaml entry needs batch_timeout_s.
> |   - none (the default): the engine runs each unit as a singleton and bounds it itself.
> |   - Suggested modes: bash-file per_unit; pytest none (or per_unit with a per-test kill); go-test batch; gradle-class batch; suite none; device none.
> | - Cleanup: the runner leads its own session, and the engine sweeps that whole session on every exit path. A test may use its own process group (setpgid) but must never call setsid().
> | - Manifest: indented JSON with run_id, invocation, group, handle, timeouts, deadline_s, results, runner_json, and units[{id, lowering, timeout_s}]. Parse it as JSON. `device` reads `handle`; it is empty unless an executor held an allocator.
> | - results.jsonl is strict:
> |   - result rows: `{"id","status":pass|fail|skip|error|timeout,"duration_ms","parent"?,"message"?}`;
> |   - a row with a parent is a child row, valid only under `full: true`, with the parent in the manifest and the child id registered;
> |   - `timeout` is accepted only from a per_unit runner.
> | - describe overrides: a runners.yaml entry may override any describe key (unit, full, children, …). `children:` is an opaque post-processor name; M3.1 only checks that it requires `full: true`.
> | - group_by: none, file, dir, or regex:<re> (the first submatch of the id path).
> | - Exit contract: run exits 0/1/2/75/64. With exit 75, emit nothing at all, or the invocation is exit_mismatch instead of a refusal. An exit-0 suite with a failing child row is exit_mismatch.
