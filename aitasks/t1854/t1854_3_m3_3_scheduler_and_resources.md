---
priority: medium
effort: high
depends: [t1854_1, t1853_5, t1854_6]
issue_type: feature
status: Postponed
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-13 19:17
updated_at: 2026-10-30 12:09
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1854_1** id=2026-10-14T14:40:25Z.8309b96590403b5840dda1ee from=t1854_1 from_verified=yes at=2026-10-14T14:40:25Z base=02e4a1badd5a7a8af9d2e250e7108cb8e1cd993e base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1854_1 (M3.1), as landed in 3d1a2b628. Verify against goengines/README.md → Interfaces ("run seams", "grouping function").
> | 
> | - Plug in with runner.RegisterExecutor(Executor):
> |   - Execute(ctx, invs []*Invocation, invoke InvokeFunc) ([]Outcome, error);
> |   - return one Outcome per invocation, in the order given;
> |   - set inv.Handle (the allocator handle) before calling invoke(ctx, inv); it reaches the runner through the manifest's "handle";
> |   - never re-form, split or drop invocations;
> |   - an error is a framework error (exit 3).
> | - Registering a second executor panics. Until yours is registered, the built-in serial plan refuses any invocation with a non-empty resource set (RUN_ERROR:scheduler-unavailable|<key>, exit 3) before anything runs.
> | - Wave class: runner.RegisterWaveClassifier(func(registry.ID) WaveClass) supplies M2.5's kind → unit|broad mapping. A nil classifier, or "", means unit.
> | - Group(units, wave) is pure and order-independent. Key.String() is `["runner","group",[resources],"unit|broad","<batch id or empty>"]`. A unit is a singleton when its runner has `batch: false`, it carries `testmap:batch no`, or its runner has `timeouts: none`.
> | - Exit precedence over records: 3 (mechanism) > 75 (any invocation refused) > 1 > 2 > 0. Admission deferral is yours; M3.1 only propagates a runner's exit 75.

> **✉ note:t1985** id=2026-10-15T05:57:39Z.0e7d81e2019590b1d434d27d from=t1985 from_verified=yes at=2026-10-15T05:57:39Z base=a81352ffb83835a8bed91624f991841c01902cee base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1985 (hang watchdog for the runner package's tests), as of commit a81352ffb:
> | 
> | - Every process-starting test in goengines/internal/testmap/runner (anything reaching Run, runAll, timedRun, Load, registry.Scan/Check, execRunner, sweepSession, newRepo/fixture.New, exec.Command) now starts with
> |       if !isolated(t, hangLimit) {
> |           return
> |       }
> |   The test then runs in a re-executed subprocess under a 20 s bound, with a HANG:<test>|<limit> report and env-marker cleanup of its runner processes (watchdog_unix_test.go / watchdog_linux_test.go).
> | - If M3.3 adds scheduler or executor tests that drive Run, they likely need this guard as their first statement. Otherwise a hang in the scheduler waits for go test's suite timeout, and their processes are not swept by the watchdog.
> | - Follow-up t1998 (isolation_tripwire) will add a go/ast tripwire that fails on an unguarded process-starting test. Until it lands, the convention is unenforced.
> | - The isolated helper and hangLimit are _test.go code of package runner; tests in other packages cannot import them.

> **✉ note:t1998** id=2026-10-15T21:03:12Z.2ac2e5263801cc6a36fa54ff from=t1998 from_verified=yes at=2026-10-15T21:03:12Z base=a669462a3cc2140f3fec671c5c9099a4d0dc27da base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1998 (hang-guard tripwire), as of commit b82f4becc. It updates the t1985 note you already carry. Not checked against your plan.
> | 
> | - The `if !isolated(t, hangLimit) { return }` convention is now ENFORCED in package goengines/internal/testmap/runner.
> |   - runner/isolation_tripwire_test.go fails any top-level test there that reaches a process start without that exact guard as its first statement.
> |   - "Reaches" is followed transitively through package-level functions and vars. The starters are Run, Load, sweepSession, exec.Command/CommandContext, os.StartProcess, syscall.ForkExec/StartProcess, registry.Scan/Check, fixture.New, and anything in internal/gitx.
> |   - goengines/ci/preflight.sh runs the tripwire alone before `go test ./...`, in goengines-check.yml, release.yml and `ait engine test`. A violation stops the run before the suite starts.
> | - The analysis is name-based. Calls through methods, interfaces and func-typed fields are not followed:
> |   - a guarded test that starts processes only through such a path (e.g. a scheduler method) fails as "guarded, but the tripwire sees no process start"; add the entry point to localStarters or importStarters in that file;
> |   - an unguarded test on such a path is not seen at all.
> | - Unguarded process-starting controls need an isolationAllow entry with a reason. Dot imports in package runner are refused.
> | - Your new package internal/testmap/sched/** is outside both protections. The isolated() guard is unexported runner test code, and the tripwire parses only the runner directory. Process-starting tests there (e.g. the two-real-processes mutex contention case) get neither unless you keep them in runner or extend the analyzer and preflight to sched.

> **✉ note:t1853_5** id=2026-10-18T15:59:21Z.28f35a4aead8fd43ae0a81e5 from=t1853_5 from_verified=yes at=2026-10-18T15:59:21Z base=6f6d1ed799167c432f1ae5ed90abeb346b712f4f base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1853_5 (M2.5) as landed in 6f6d1ed79; re-verify in your Reality check.
> | 
> | The kind data your wave classifier maps is `registry.ScopedOf(reg).KindOf(id)`:
> | - It returns `unit | integration | e2e | device`, looked up in this order: the id's effective row, else its base (the variant's unit), else the file-level row, else unit.
> | - `registry.IsBroad(kind)` is the `broad` test.
> | 
> | M2.5 deliberately does NOT call `runner.RegisterWaveClassifier`. That registration is yours, and a second registration panics.
> | 
> | Variant-bearing units are never broad. BuildScoped refuses them from annotations, and check reports `SCOPE_INVALID` for hand rows. So `@variant` ids always map to `unit`.
> | 
> | The kind ranking for ordering is `registry.KindRank`.

> **✉ note:t1854_2** id=2026-10-21T19:10:36Z.3057c721cce19984f35a3f86 from=t1854_2 from_verified=yes at=2026-10-21T19:10:36Z base=5582dd4f455372f5ba40a43b6d2dffe2101089b3 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_2 (the M3.2 re-decomposition, 2026-10-21). Edges are as of the commit this note records; nothing is implemented yet.
> | - You now depend on t1854_6 (M3.2c supervised execution). It owns G8a: per-invocation cleanup ownership that survives a builtin crash.
> | - Parallel invocations are allowed only when every invocation's `procsup.Boundary` is overlappable (a cgroup v2 leaf). On a host with only the engine's subreaper tree, `runner.Run` serializes them and prints `PARALLEL_REFUSED:containment`. Your `errgroup` execution and `concurrency: parallel` should consume `Boundary.Overlappable()` rather than parallelize unconditionally.
> | - Why: once one builtin dies, its orphans are adopted by the engine and parent-pid ancestry no longer identifies their invocation, so a tree-wide kill would hit healthy sibling invocations.
> | - A PID-namespace backend is deferred to t2119.
> | - The device adapter (t1854_13, Postponed) depends on you for the manifest `handle`.
> | - Details: parent t1854, section "M3.2 re-decomposition (2026-10-21)", and t1854_6's body.

> **✉ note:t1854_5** id=2026-10-22T12:41:59Z.f2512e77d167ea1c6df36b2c from=t1854_5 from_verified=yes at=2026-10-22T12:41:59Z base=ed04c92a57296b34828cb90e9af371b88383aae6 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1854_5 (M3.2b shared hang watchdog), landed in commit ed04c92a5. This supersedes your body's carried fact that "`isolated(t, hangLimit)` and its tripwire are unexported test code in package runner; the tripwire parses only runner". Not checked against your plan; re-verify in your Step 0.
> | 
> | - The guard is now `hangguard.Isolated(t, limit) bool`, imported from github.com/beyondeye/aitasks/goengines/internal/testsupport/hangguard (test support: only _test.go files may import it). A process-starting top-level test begins with `if !hangguard.Isolated(t, <limit>) { return }`. runner keeps its own `isolated(t, hangLimit)` wrapper, which is also accepted. Each package picks its own limit.
> | - Opt-in is ONE entry in `tripwirePackages` in internal/testsupport/hangguard/tripwire_test.go: {dir, name, localStarters, allow}. goengines/ci/preflight.sh (both workflows, `ait engine test`) then enforces it. A _test.go file importing hangguard from a package with no entry fails preflight (TestIsolationTripwireImports).
> | - The tripwire is lexical. Put in localStarters any entry point that starts processes through methods, interfaces or func fields. Another listed entry's localStarters count as starters for you too: with runner listed, runner.Run and runner.Load are seen in your package.
> | - Hazard for adapters that run test binaries (e.g. go-test): a child process inherits AIT_HANGGUARD_ISOLATE. A child test binary of this module that uses the guard would refuse to run ("runs inside the subprocess of ..."), or run a same-named test unguarded. Clear the variable in such a child's environment.
> | - Details and the full rationale are in the archived plan p1854_5 (Final Implementation Notes, "Notes for sibling tasks").

> **✉ note:t1854_6** id=2026-10-25T06:58:35Z.1c1ae992cd7e175321a5cc69 from=t1854_6 from_verified=yes at=2026-10-25T06:58:35Z base=60ca89154aa0d66ceec006c9f8c6b764fe661ae6 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_6 (M3.2c supervised execution), as landed in commit 60ca89154. Verify against goengines/README.md (Interfaces: "supervised execution", "halt", "runner.Overlappable / PARALLEL_REFUSED") before relying on it.
> | 
> | - G8a was revised from cgroup leaf / subreaper tree to a dedicated per-start supervisor (procsup). Each invocation's runner runs under its own supervisor, a subreaper of its own subtree only, so cleanup never touches another invocation.
> | - runner.Overlappable() is true on Linux, including CI. Your errgroup / concurrency: parallel execution may overlap invocations there. Where it is false (darwin, no supervisor), runner.Run wraps the InvokeFunc and serializes overlap itself, printing PARALLEL_REFUSED:containment (RunReport.ParallelRefused). There is no Boundary type: consume runner.Overlappable(), not a per-invocation boundary.
> | - A supervisor's death or a failed cleanup halts the process's procsup:
> |   - in-flight invocations are cancelled (mechanism halted:<detail>; terminal units and attributable errors kept, the rest missing, never timeout);
> |   - queued invocations are refused before start (mechanism halted:<detail>, units not_started).
> |   Your executor needs no special handling, but a run that halts exits 3.
> | - Pass the ctx you receive to invoke: procsup.Start refuses an already-cancelled ctx before launching, and turns a later cancellation into a supervisor cancel.
> | - Any test binary that runs runners needs procsup.MaybeSupervise() as the first statement of its TestMain.

> **✉ note:t15** id=2026-10-25T08:54:13Z.6674004487b275fe391a791e from=aitasks_go#t15 at=2026-10-25T08:54:13Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
>
> | Coordination notice from aitasks_go (t15 ship-path decision; schedule in trail
> | art:trail-go-ship-path owned by aitasks_go#t22). Advisory context, not an
> | instruction. It does not change this task's scope.
> | 
> | WHAT IS PLANNED
> | ait-testmap Go development (public goengines/) will move ONCE into the private
> | aitasks_go repository, at a cutover performed by aitasks_go#t22. After that,
> | goengines/ here receives exported snapshots only (no tests, bench or ci), and
> | engine work happens in aitasks_go. As of 2026-10-25 the cutover has no date.
> | Its prerequisites are aitasks_go t20 and t21 and aitasks t2138.
> | 
> | UNTIL THE CUTOVER: CONTINUE THIS TASK HERE, AS NORMAL
> | To keep the cutover cheap and safe:
> | 1. Land goengines/ changes on main promptly. Avoid long-lived branches,
> |    worktrees or unmerged PRs touching goengines/, because the cutover has to
> |    wait for, or hand off, every one of them.
> | 2. Keep engine commits (goengines/**) separate from framework-side commits
> |    (the aitask_testmap.sh shim, installer/setup, skills, docs, aitestmap/).
> |    Mixed tasks will be split along that line, and separate commits keep both
> |    the split and the history migration clean.
> | 3. If goengines tests start reading data from outside goengines/ (as with the
> |    t1954 corpus under aidocs/testing_engine/), record that path in this
> |    task's plan. The migration must copy it into the private module.
> | 4. Add no new Go binary or non-testmap package to goengines/. ait-monitord is
> |    being re-homed to aitasks_go (aitasks_go#t23), and ait-tui is developed
> |    there.
> | 5. Keep the contracts and guards as usual: the dependency allowlist, the
> |    Invariant 4-5 tripwire, the hang guard, bench baselines, and the
> |    version/verb/exit-code interface. The migration carries them over verbatim
> |    and checks that nothing changed.
> | 
> | FREEZE PROTOCOL
> | Shortly before the cutover, aitasks_go#t22 will send this task a
> | "goengines freeze in effect" note. From that note until a matching
> | "goengines freeze lifted" note, do not claim or start goengines work here. A
> | task that is Implementing or locked at that time is never relocated under its
> | agent: t22 waits for it to land, or arranges an explicit checkpointed handoff
> | (commit/push, handoff note, release the lock, back to Ready).
> | 
> | AFTER THE CUTOVER
> | If this task still has engine work pending, it is re-homed to aitasks_go
> | (engine-only) or split (the Go part there, the framework part here), and the
> | original carries a pointer. Framework-side work (the shim, installer, skills,
> | docs, aitestmap/ and the n014 spec) stays in this repository permanently. An
> | emergency public fix to goengines/ after the cutover needs a
> | `Return-To: aitasks_go` trailer plus a return task in aitasks_go
> | (`ait create --batch --project aitasks_go`).

> **✉ note:t22_3** id=2026-10-29T22:22:26Z.d3594340b431efdd4490623f from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:22:26Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:11:15Z.e507a43897f6f36615a5ce5b from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:11:15Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Re-homed: the engine work of this task moved to aitasks_go#t60_1
> | (beyondeye/aitasks_go). This task is Postponed as a pointer and must not be
> | picked. History of its completed siblings: aitasks_go
> | aidocs/aitasks_go/testmap_history/.

> **✉ note:t22_4** id=2026-10-30T10:15:07Z.678e0edede680cadc46f0dba from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:15:07Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | goengines freeze lifted (aitasks_go#t22 cutover complete).
> | Public goengines/ is now an export target: never edit it here; changes
> | arrive from beyondeye/aitasks_go via promote/export.sh.
> | - Engine work of this task now lives in aitasks_go#t60_1; this task is
> |   Postponed and kept only as a pointer.
