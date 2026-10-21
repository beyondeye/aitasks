---
Task: t1854_6_m3_2c_supervised_execution.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md, aitasks/t1854/t1854_5_*.md, aitasks/t1854/t1854_7_*.md, aitasks/t1854/t1854_8_*.md, aitasks/t1854/t1854_9_*.md, aitasks/t1854/t1854_10_*.md, aitasks/t1854/t1854_11_*.md, aitasks/t1854/t1854_12_*.md, aitasks/t1854/t1854_13_*.md, aitasks/t1854/t1854_14_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1854_6 — M3.2c Supervised execution foundation

## Context

**Coarse plan only**, written at the M3.2 re-decomposition (2026-10-21). The
task body `aitasks/t1854/t1854_6_m3_2c_supervised_execution.md` is authoritative. It holds the
shared evidence guarantees (G1–G10), the carried reality-check facts and the
acceptance criteria below. Its **Step 0 — Reality check** is mandatory, runs
before any code, and is recorded in this file; the detailed design is written
here after Step 0.

Child **M3.2c — Supervised execution foundation** of t1854. Wave **2**. See
the parent's *M3.2 re-decomposition (2026-10-21)* section.

No production runner may be enabled before process supervision is complete.
This task owns G8 (containment that a descendant cannot leave by changing its
process group or session) and G8a (per-invocation cleanup ownership that
survives a builtin crash). It also adds the `ait-testmap runner <name>` verb
and the builtin scaffold, with **no production adapter registered**. Every
adapter (t1854_8–t1854_13) depends on this task, and through it on the
recursion guard t1854_7.

Automation-first (user directive, 2026-10-11): no path may make a human action
a precondition.

## Owned files

- The new `goengines/internal/procsup/**` and `goengines/internal/testmap/runner/builtin/**` (the scaffold only).
- `runner/exec_unix.go`, `runner/proc_*.go`, `runner/invoke.go`, `runner/plan.go`, `runner/run.go` (named extensions of M3.1).
- `cmd/ait-testmap/verbs.go` (the `runner` row), a new `cmd/ait-testmap/builtin.go`, `main_test.go`.
- `goengines/README.md`.

## Provides / consumes

- **Provides:** supervision, the boundaries and the scaffold, to t1854_8–t1854_13, t1854_3 and `testmap_pidns_invocation_boundary`.
- **Consumes:** t1854_2 (the contract), t1854_5 (the hang guard), t1854_7 (the recursion guard).

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded here)

- Inspect M3.1's exec and sweep code, t1854_2's contract and t1854_7's guard as landed.
- Prove the subreaper behaviour, and that a cgroup v2 leaf works on the reference host.
- Decide CI coverage.
- Tabulate the differences, decide each one, and note t1854_3 of the final `Boundary` API.

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
- **Containment (G8), `goengines/internal/procsup`.**
  - **The subreaper tree.**
    - The supervising process (the builtin, and also the engine's runner execution in M3.1's `runner/exec_unix.go`, a named extension that closes M3.1's documented `setsid()` residual) sets `PR_SET_CHILD_SUBREAPER`.
    - It tracks its contained processes as the `/proc` parent-pid tree below itself; orphans and `setsid()` callers reparent to it and stay in the tree.
    - Cleanup SIGKILLs the tree, repeating until it is empty or a bound expires. A survivor is `cleanup_incomplete`; an unreadable `/proc` is `cleanup_unverified`.
  - **cgroup v2.** When a delegated cgroup v2 subtree is writable and a leaf is proven usable (Step 0 settles the "no internal processes" rule for the engine's own scope), each unit gets a leaf, killed with `cgroup.kill` and verified empty through `cgroup.procs`. The record reports `CONTAINMENT:subreaper|cgroup`.
  - **Platforms without either (darwin).** Production adapters refuse with `CONTAINMENT_UNAVAILABLE:<platform>` (mechanism, exit 3). This is G8's enforceable support restriction. Only a test-only adapter may run uncontained there, and it is marked as such.
  - **The engine sweep.** M3.1's session sweep stays as a second pass, its tests green. The session enumeration and kill routines move into `procsup`, shared by both.
- **Per-invocation ownership boundary (G8a).**
  - `procsup.Boundary` is opened by the engine for each invocation, before the runner starts. It is a cgroup v2 leaf when delegated, else `tree` (the engine's subreaper tree). **No PID-namespace backend here**; that is the separate task `testmap_pidns_invocation_boundary`.
  - `Kill` / `Verify` act on the boundary's members only, and the record reports `boundary:cgroup|tree`.
  - `Boundary.Overlappable()` is true only for cgroup. M3.1's `invoke` cleans up through the boundary, never through the engine-wide tree.
  - **The executor seam rule** (enforced in `runner.Run`, a named extension of M3.1's `plan.go`): an executor may start overlapping invocations only when every boundary is overlappable. Otherwise `Run` serializes them and prints `PARALLEL_REFUSED:containment`.
  - **Invariant, pinned by a test:** under every enabled backend, t1854_7's cleared-environment (`env -i`) recursion refusal and its fixture-repository allowance pass. The test is parameterized over the backends, so any later backend must join it.
- **Real-process overlap test.**
  - Two invocations run in parallel through a test executor. Invocation A's builtin is SIGKILLed while it holds a `setsid()`, double-forked descendant. Invocation B runs to completion meanwhile.
  - **Expected:** A's descendant is killed and A's record carries its cause. Every one of B's processes survives until B's normal exit, B's results are intact, and B has no cause.
  - An isolated mutant that cleans up with the engine-wide tree must turn the "B unaffected" assertion red.
  - It runs on a host with a delegated cgroup; on any other host it asserts the serial refusal.
  - On 2026-10-21 the reference host's session scope was writable. Step 0 confirms that a leaf works there and decides CI coverage. An environment declared to have a cgroup boundary sets `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1`, so a missing boundary fails there instead of passing as serial.
- **Supervision API.**
  - It runs each command in its own process group, inside the containment.
  - Timeout: SIGTERM to the group, a grace period, then the containment kill and verification.
  - Context cancellation and the supervisor's own exit path (deferred cleanup) follow the same path. If the builtin is SIGKILLed, the engine's boundary cleans up.
  - stdout and stderr go to files, bounded.
  - The same API runs native discovery, under a discovery bound below `ListTimeout`.
- **Tests against real processes**, every one under the t1854_5 watchdog:
  - timeout;
  - cancellation;
  - a child that ignores SIGTERM;
  - a grandchild in its own process group;
  - a double-forked orphan;
  - **a child that calls `setsid()`, and a double-fork `setsid()` daemon** (an isolated mutant that drops the subreaper must turn them red);
  - a zombie;
  - output past the cap;
  - a builtin that crashes mid-unit or is SIGKILLed while a `setsid()` descendant runs, where nothing is left behind (an engine-path test);
  - the forced `CONTAINMENT_UNAVAILABLE` refusal.
- **Platforms.** Linux (kernel ≥ 3.4, `/proc`) is supported. Darwin is compiled and vetted only, and refuses production adapters.
- **Scaffold.**
  - `ait-testmap runner <name> describe|list|run --manifest <path>` with a builtin registry; `UNKNOWN_BUILTIN:<name>` → 64. This replaces `stub("runner")` in `verbs.go` (`main_test.go` stub list updated).
  - Shared helpers: manifest read, the results writer (start rows, `cases.jsonl` rows per t1854_2), the fresh-report reader, `runners.yaml` entry lookup, and an argv splitter. The splitter refuses shell metacharacters (`$`, backtick, `;`, `|`, `&`, `<`, `>`, newline); tools run through exec, never through a shell.
  - **No production adapter is registered.** A test-only adapter exercises the scaffold end to end through `runner.Run`.
- **Coordination with t1854_3 (M3.3).** Its `errgroup` parallel execution consumes `Boundary.Overlappable()`, and t1854_3 depends on this task.
- **Docs.** README Interfaces rows for `procsup`, `Boundary`, `runner <name>` and the support restriction. `ait engine test` is green.

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival on the
current branch, no merge).
