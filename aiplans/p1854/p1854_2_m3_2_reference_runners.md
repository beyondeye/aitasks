---
Task: t1854_2_m3_2_reference_runners.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1854_2 — M3.2 Reference runners

## Context

Parent goal: M3 — Runners, scheduling and cost. This is **M3.2 Reference
runners**, wave **B**. It provides the builtins built into the binary, so
every target repository can list and run its units without a project
script. Provider: M3.1 (`t1854_1`).

This coarse plan records what the proposal fixes for M3.2. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first (user directive, 2026-10-11).** Human review belonged to
an older design. No runner shipped here may make a human action a
precondition of any path. A human-only step met in the proposal is reported
to its owning parent with a note, never encoded here.

## Proposal reading list

From `aidocs/testing_engine/n014_explorer_006_proposal.md` (M3 cut fixed in
`6a3a81efc`):

- the Module Map row for M3.2;
- *Reference runners (M3.2)*;
- *Runner contract and repository (M3.1)*, the contract these runners
  implement;
- *Onboarding → Detection, per target repository*, for what each target
  needs from the builtins;
- *Assumptions → `assumption_batch_per_unit_timing_reportable`*;
- *Tradeoffs → `tradeoff_batch_misreport_risk`*;
- *Open questions* item 8 (the bash-file per-file exit default);
- *Invariants every module honours*.

Also read:

- the parent plan `aiplans/p1854_testmap_m3_runners_scheduling_and_cost.md`
  (Deviations 3, 5, 6);
- `goengines/README.md`.

## Owned files / provides / consumes

- **Owns:**
  - `goengines/internal/testmap/runner/builtin/**`;
  - the `runner` row in `verbs.go`.
- **Provides:** runners for every target repository without a project
  script. Consumers: M4.5; M6.2; M8.4 (`fallback_command`); M10.4
  (`gradle-class`, `device`); M10.5.
- **Consumes:** M3.1, specifically:
  - the contract;
  - the `builtin:` registration seam;
  - the manifest handle field;
  - top-level / child rows.
- **Not owned (moved):** the serial carve-out agreement check in
  `tests/test_serial_carveout_doc_drift.sh` is M10.1's. There is no `bash-file
  list --invocations`; the seeder reads M2.3's facts directly.

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded in this plan file)

Execute and record here, before writing any code:

1. Re-read the proposal's Module Map row for M3.2, its component
   subsection, and the row of every interface it consumes (*Cross-module
   interfaces*).
2. Inspect the **actual current state** of every provider on the merge
   target: verbs, line protocols, files, hooks and tests. Name the task and
   commit that landed each one. The proposal and this coarse plan are claims
   to verify, never facts. Specifically:
   - M3.1 as landed (`t1854_1`): the runner contract types, the `builtin:`
     registration seam, the manifest's allocator-handle field, the
     top-level / child row marking, and the reconciliation hooks. If M3.1
     has not landed, **stop**.
   - The `./ait test` recursion: decide how a `full` suite command that
     reaches `./ait test` (and through it `aitask_test.sh`, against
     Invariant 5) is refused, and record the rule.
   - The parent plan's *Repository reality anchors* (verified 2026-10-13 at
     `a2395c309`): re-verify each one this child relies on.
3. Tabulate every difference: *proposal says* / *coarse plan says* /
   *repository has*.
4. Decide per difference: adapt this child to reality; revise this coarse
   plan; or revise the proposal (cut errors and interface changes go there,
   per the parent body's protocol §1). Record the decision and its reason.
5. Send a note (`/aitask-note`) to every downstream child whose assumptions
   a difference or decision breaks (M6.1/M6.2 children of t1857, M10
   children of t1861), hedging what the tree cannot prove.
6. Re-confirm that every file this child will touch is owned by M3.2, or is
   the owner's named extension (the "one owning submodule" rule).

## Implementation steps (coarse)

1. Step 0 — Reality check (above).
2. The `runner <name>` verb (replace the `runner` stub row) and the builtin
   registration into M3.1's `builtin:` scheme.
3. `bash-file`, `pytest` (junitxml; `testmap:batch no` units run outside
   the batch), `go-test` (per-file `-run` regex, `-json`), and
   `engine-test` (over `goengines/`).
4. `gradle-class`: a `--tests <lowering>` batch, one invocation per
   `group_by` group, JUnit XML inverted to ids through the list table, and
   the zero-match trap as a mechanism failure.
5. `suite` (any command as one unit, optional child rows); the `full`
   wrapper's three `children:` post-processors: pytest junitxml, bash-file
   per-file exit, and `go test -json`. Then `device`, which reads the
   manifest handle and refuses without one. Then the recursion refusal.

## Verification

- Each builtin lists and runs one passing and one failing unit on a fixture
  repo.
- pytest: the junitxml inversion works, and `testmap:batch no` units run
  outside the batch.
- `go-test -json` works per file.
- `gradle-class`, against a fake Gradle emitting JUnit XML, makes one
  invocation per `group_by` group and trips the zero-match trap.
- `suite` produces child rows through each of the three `children:`
  post-processors.
- `device` reads a fixture handle and refuses without one.
- `engine-test` lists the `goengines/` packages.
- A `full` suite command reaching `./ait test` is refused.
- `ait engine test` is green, and the Invariants 4–5 tripwire passes.
- No path shipped here requires a human action (automation-first).

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival; current
branch, no merge).
