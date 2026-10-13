---
priority: medium
effort: high
depends: [t1854_1, t1853_5]
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-13 19:17
updated_at: 2026-10-13 19:18
---

## Context

Child **M3.3 — Scheduler and resources** of t1854 (test map, module M3). Wave
**C**. It covers the declared host resources, the wave plan `run` executes,
and the exit-75 semantics. **Providers:** M3.1 (`t1854_1`) and **M2.5**
(`t1853_5`, kind data and scoped rows).

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
(M3 cut fixed in `6a3a81efc`):

- the Module Map row M3.3;
- the components *Scheduler and resources (M3.3)* and *Broad-test
  scheduling and staleness policy* (the scheduling half);
- *Architecture → Vocabulary* (Runner and resource; Kind and scoped row);
- *Assumptions → `assumption_existing_locks_wrappable`*;
- *Tradeoffs → `tradeoff_resource_declaration_completeness`,
  `tradeoff_broad_scope_coarseness`*.

Parent plan: `aiplans/p1854_testmap_m3_runners_scheduling_and_cost.md`
(Deviations 1, 3, 4, 9 and 12).

**Coarse plan only.** `aiplans/p1854/p1854_3_m3_3_scheduler_and_resources.md`
records what the proposal fixes. Its mandatory **Step 0 — Reality check**
runs before any code and is recorded in the plan. It inspects:

- M3.1's plan-executor seam, grouping function and handle field;
- M2.5's kind data.

**Stop if M2.5 has not landed.**

## Scope (from the proposal, after the M3 cut fix)

- **Resources:**
  - resource kinds `mutex` / `semaphore` / `admission` / `allocator`;
  - scopes `host` / `worktree` / `run`;
  - `acquired_by` planning and `aitestmap/resources.yaml`.
- **Locking and admission:**
  - `flock(2)` slot files, taken in canonical order;
  - admission exec with 75 deferral and backoff up to the run deadline; a
    refusal at the deadline is exit 75 (advisory `skip:admission_refused`);
  - allocator exec with signal-safe release, writing the held handle into
    M3.1's manifest handle field.
- **Execution:**
  - `errgroup` execution of the invocations that **M3.1's grouping function
    forms — never re-formed**;
  - the kind → wave class mapping from M2.5's kind data (`unit` and
    variant-bearing → `unit`; `integration|e2e|device` → `broad`);
  - `broad_after_unit` waves as a pure ordering over those wave-homogeneous
    invocations: broad invocations run only after a green unit wave, and
    their skip after a red wave is printed;
  - admission-holding invocations run last within their wave.
- **Policy:**
  - `device_policy: filter_by_resource`;
  - `concurrency: serial|parallel` (serial at bootstrap; `--serial` /
    `--parallel`).
- **Verbs:** the `schedule` report and its check half, `schedule --check`,
  which has its own lines and is never a gate.
- **Integration:** plugs the scheduler into M3.1's `run` seam (a named
  extension of M3.1).

## Key files to modify

- `goengines/internal/testmap/sched/**` — new package (owned).
- `goengines/cmd/ait-testmap/verbs.go` — replace only the `schedule` stub row.
- M3.1's `run` plan-executor seam — the named extension.

## Reference files for patterns

- `goengines/internal/platform/lock_unix.go` (`Lock`) and `platform.NewGroup`
  (cap 8).
- M3.1's grouping function and the fixture runners.
- thinking_app's heavy-run lock with exit-75 admission is the reference
  project (proposal *Onboarding → Detection*).

## Provides / consumes

- **Provides:** `resources.yaml`, the wave plan, exit 75 semantics (M4.5,
  M6.1, M6.4).
- **Consumes:** M3.1; M2.5.

## Implementation plan (coarse)

1. Step 0 — Reality check (in the plan file).
2. `resources.yaml` parse; slot files and canonical-order acquisition.
3. Admission (75 deferral, backoff, deadline) and the allocator (signal-safe
   release, handle).
4. The kind → wave class mapping; waves; ordering; concurrency.
5. The `schedule` verb and `schedule --check`; plug into `run`.

## Verification

- Mutex and semaphore:
  - two real processes contend on a `mutex` slot and serialize;
  - a `semaphore` admits n.
- `{a,b}` / `{b,a}` acquisitions never deadlock.
- The `host` / `worktree` / `run` scope paths are distinct.
- An admission command answering 75 is retried with backoff, and the run
  exits 75 at the deadline.
- The allocator is released on SIGINT and SIGTERM of the engine process.
- Grouping:
  - invocations equal the grouping function's output;
  - the executed count equals the estimate's group count;
  - two `batch: no` units give two invocations.
- **A mixed unit + integration selection** sharing runner, group and
  resources, where the unit test fails, under `broad_after_unit: true`: the
  integration invocation is not run and the skip is printed.
- Waves:
  - variant-bearing units ride the unit wave;
  - admission-holding invocations run last.
- Policy:
  - `device_policy: filter_by_resource`;
  - serial by default, with `--serial` / `--parallel`.
- The pool never exceeds 8.
- `schedule --check` refuses an undeclared resource name.
- The allocator handle reaches the manifest.
- `ait engine test` is green.

## Automation-first (user directive, 2026-10-11)

Human review belonged to an older design. No path shipped here may make a
human action a precondition. The "review the schedule report before trusting
concurrency" step and "confirm runners per runner" belong to onboarding (M6),
which is asked to automate them. A human-only step met in the proposal is
reported to its owning parent with a note, never encoded here.
