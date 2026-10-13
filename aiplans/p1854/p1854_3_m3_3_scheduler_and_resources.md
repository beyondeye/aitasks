---
Task: t1854_3_m3_3_scheduler_and_resources.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_4_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1854_3 — M3.3 Scheduler and resources

## Context

Parent goal: M3 — Runners, scheduling and cost. This is **M3.3 Scheduler
and resources**, wave **C**. It owns the declared host resources, the wave
plan `run` executes, and the exit-75 semantics. Providers:

- M3.1 (`t1854_1`);
- **M2.5 (`t1853_5`)**, for kind data and scoped rows.

This coarse plan records what the proposal fixes for M3.3. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first (user directive, 2026-10-11).** Human review belonged to
an older design. No verb shipped here may make a human action a
precondition of any path:

- `concurrency`, `--serial` / `--parallel` and `resources.yaml` are values;
- the schedule report and `schedule --check` are informational, never
  gates.

Two steps that currently involve a person belong to onboarding (M6), which
is asked to automate them:

- trusting `concurrency` after reviewing the schedule report;
- confirming `runners.yaml` per runner.

## Proposal reading list

From `aidocs/testing_engine/n014_explorer_006_proposal.md` (M3 cut fixed in
`6a3a81efc`):

- the Module Map row M3.3;
- *Scheduler and resources (M3.3)*;
- *Broad-test scheduling and staleness policy*, the scheduling half;
- *Runner contract and repository*, for the canonical grouping function and
  the plan seam;
- *Architecture → Vocabulary*: Runner and resource; Kind and scoped row;
- *Assumptions → `assumption_existing_locks_wrappable`*,
  `assumption_broad_tests_area_scoped`;
- *Tradeoffs → `tradeoff_resource_declaration_completeness`*,
  `tradeoff_broad_scope_coarseness`;
- *Invariants every module honours*.

Also read:

- the parent plan `aiplans/p1854_testmap_m3_runners_scheduling_and_cost.md`
  (Deviations 1, 3, 4, 9, 12);
- `goengines/README.md`.

## Owned files / provides / consumes

- **Owns:**
  - `goengines/internal/testmap/sched/**`;
  - the `schedule` row in `verbs.go`;
  - the scheduler plugged into M3.1's `run` plan-executor seam, and the
    manifest handle written from the allocator (named extensions of M3.1).
- **Provides:** `resources.yaml`, the wave plan, and exit 75 semantics, to
  M4.5, M6.1 (`RESOURCE_HINT` → entries) and M6.4 (`needs:` bindings).
- **Consumes:**
  - M3.1: the grouping function, plan seam, manifest handle field and
    per-invocation record;
  - M2.5: kind data → wave class, and scoped rows.

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded in this plan file)

Execute and record here, before writing any code:

1. Re-read the proposal's Module Map row for M3.3, its component
   subsections, and the row of every interface it consumes (*Cross-module
   interfaces*).
2. Inspect the **actual current state** of every provider on the merge
   target: verbs, line protocols, files, hooks and tests. Name the task and
   commit that landed each one. The proposal and this coarse plan are claims
   to verify, never facts. Specifically:
   - M3.1 as landed (`t1854_1`): the plan-executor seam, the grouping
     function's signature and its wave-class input, the manifest handle
     field, and the built-in plan's resource refusal. If M3.1 has not
     landed, **stop**.
   - M2.5 as landed (`t1853_5`): how kinds and scoped rows reach the
     registry. If M2.5 has not landed, **stop**: this child must not invent
     the kind data.
   - `platform.Lock` / `NewGroup` and the pool cap.
   - The parent plan's *Repository reality anchors* (verified 2026-10-13 at
     `a2395c309`): re-verify each one this child relies on.
3. Tabulate every difference: *proposal says* / *coarse plan says* /
   *repository has*.
4. Decide per difference: adapt this child to reality; revise this coarse
   plan; or revise the proposal (cut errors and interface changes go there,
   per the parent body's protocol §1). Record the decision and its reason.
   Fix the `schedule` / `schedule --check` line names, which are homed in the
   *Scheduler and resources* component.
5. Send a note (`/aitask-note`) to every downstream child whose assumptions
   a difference or decision breaks (M4.5, M6.1, M6.4), hedging what the tree
   cannot prove.
6. Re-confirm that every file this child will touch is owned by M3.3 or is
   the owner's named extension (the "one owning submodule" rule).

## Implementation steps (coarse)

1. Step 0 — Reality check (above).
2. `resources.yaml` parse: resource kinds `mutex` / `semaphore` /
   `admission` / `allocator`, scopes `host` / `worktree` / `run`, and
   `acquired_by` planning.
3. `flock(2)` slot files, taken in canonical order.
4. Admission exec with 75 deferral and backoff up to the run deadline;
   allocator exec with signal-safe release, with the held handle written
   into the manifest.
5. The kind → wave class mapping. Waves are a pure ordering over M3.1's
   wave-homogeneous invocations, which are never re-formed. Ordering rules:
   - `broad` invocations run only after a green `unit` wave;
   - after a red wave the skip is printed;
   - variant-bearing units go in the unit wave;
   - admission-holding invocations run last.

   Also `device_policy: filter_by_resource`, and `concurrency` (serial at
   bootstrap, with `--serial` / `--parallel`).
6. Execute under `errgroup` (cap 8). Add the `schedule` verb (replacing the
   stub row), its report, and `schedule --check`. Plug the scheduler into
   M3.1's `run`.

## Verification

- Two real processes contend on a `mutex` slot and serialize; a `semaphore`
  admits n.
- Runs that acquire `{a,b}` and `{b,a}` never deadlock.
- The `host` / `worktree` / `run` scope slot paths are distinct and correct.
- An admission command that answers 75 is retried with backoff, and the run
  exits 75 at the deadline (advisory `skip:admission_refused`).
- **The allocator is released under SIGINT and SIGTERM** of the engine
  process.
- Invocations are identical to the grouping function's output, and the
  executed invocation count equals the estimate's group count for the same
  selection.
- Two `batch: no` units with otherwise identical fields run as two
  invocations.
- **Mixed selection, failing unit test.** The case: a selection of unit and
  integration tests that share runner, group and resources, the unit test
  fails, and `broad_after_unit: true` is set. The integration invocation is
  not run, and the skip is printed.
- Variant-bearing units ride the unit wave; admission-holding invocations run
  last.
- `device_policy: filter_by_resource` applies; runs are serial by default,
  and `--serial` / `--parallel` work.
- The pool never exceeds 8.
- The `schedule` report works; `schedule --check` refuses an undeclared
  resource name.
- The allocator handle reaches the manifest.
- `ait engine test` is green; the Invariants 4–5 tripwire passes.
- No path shipped here requires a human action (automation-first).

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival; current
branch, no merge).
