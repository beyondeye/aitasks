---
priority: medium
effort: high
depends: [t1854_2, t1854_5, t1854_7]
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-21 22:06
updated_at: 2026-10-21 22:07
---

## Context

Child **M3.2c — Supervised execution foundation** of t1854. Wave **2**. See
the parent's *M3.2 re-decomposition (2026-10-21)* section.

No production runner may be enabled before process supervision is complete.
This task owns G8 (containment that a descendant cannot leave by changing its
process group or session) and G8a (per-invocation cleanup ownership that
survives a builtin crash). It also adds the `ait-testmap runner <name>` verb
and the builtin scaffold, with **no production adapter registered**. Every
adapter (t1854_8–t1854_13) depends on this task, and through it on the
recursion guard t1854_7.

## Acceptance criteria

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

## Key files to modify

- The new `goengines/internal/procsup/**` and `goengines/internal/testmap/runner/builtin/**` (the scaffold only).
- `runner/exec_unix.go`, `runner/proc_*.go`, `runner/invoke.go`, `runner/plan.go`, `runner/run.go` (named extensions of M3.1).
- `cmd/ait-testmap/verbs.go` (the `runner` row), a new `cmd/ait-testmap/builtin.go`, `main_test.go`.
- `goengines/README.md`.

## Reference files for patterns

- `runner/exec_unix.go` (`execRunner`, `capWriter`, `sweepSession`) and `runner/cleanup_linux_test.go`.
- `runner/watchdog_*` (as moved by t1854_5).

## Provides / consumes

- **Provides:** supervision, the boundaries and the scaffold, to t1854_8–t1854_13, t1854_3 and `testmap_pidns_invocation_boundary`.
- **Consumes:** t1854_2 (the contract), t1854_5 (the hang guard), t1854_7 (the recursion guard).

## Step 0 — Reality check (mandatory, before any code; recorded in the plan)

- Inspect M3.1's exec and sweep code, t1854_2's contract and t1854_7's guard as landed.
- Prove the subreaper behaviour, and that a cgroup v2 leaf works on the reference host.
- Decide CI coverage.
- Tabulate the differences, decide each one, and note t1854_3 of the final `Boundary` API.

## Evidence guarantees (M3.2, shared by every sibling — decided 2026-10-21)

| # | guarantee |
|---|---|
| G1 | **Command outcome ≠ accounting.** Every top-level result carries the accounting class its runner declares (`describe` `accounting:`): **`cases`** (the engine holds the unit's expected case **identities** from discovery and reconciled them, identity by identity, against the adapter's terminal case results in this invocation); **`unit`** (the unit is one executable whose exit is its verdict, e.g. a bash test script; this is the default for project scripts); **`aggregate`** (one command over many tests; proves the command's exit only). A run prints both `RUN_RESULT` (outcomes) and `RUN_ACCOUNTING:<selected>\|<cases>\|<unit>\|<aggregate>\|<unaccounted>` |
| G1a | **Case reconciliation is identity-based and engine-owned.** Each expected case identity needs **exactly one** terminal result (`pass\|fail\|error\|skip`). A missing identity, a duplicate (two results for one identity), an unexpected identity (not in the expected set) or a malformed identity makes the unit `error:incomplete\|duplicate_case\|unexpected_case`, whatever the totals. That catches equal-count substitutions (`{a,b}` expected, `{a,a}` or `{a,c}` reported). The counters (`cases_expected / passed / failed / errored / skipped`) are **computed by the engine from the validated case results**, never taken from the adapter, and an adapter never writes the top-level result of a `cases` unit (start rows only) |
| G1b | **Unit status from validated cases**, in order: any case `fail` → `fail`; else any case `error` → `error`; else zero expected cases → G3; else every case `skip` → `skip`; else (every case `pass` or `skip`, ≥ 1 `pass`) → `pass`, with its skipped cases counted and listed in the evidence. A unit with a reconciliation error (G1a) is `error` before any of this applies |
| G2 | **Never a pass, never an unexplained skip.** Evidence that is **missing** (an expected case or unit with no result), **ambiguous** (a report entry that inverts to zero or several cases or units), **stale** (a report the invocation did not produce) or **incomplete** (G1a) makes the unit `error` with a stated reason, or makes the whole invocation a mechanism failure. It is never `pass`, and never `skip` |
| G3 | **Zero tests is an explicit policy.** A `cases` unit that executed zero cases is `error:zero_tests`, unless its runner entry sets `zero_tests: skip`. In that case it is `skip`, with reason `zero_tests` printed and in the ledger. It is never a pass |
| G4 | **`skip` comes only from the tool's own per-case skip verdicts (with their reasons) or from G3.** An adapter never synthesizes one |
| G5 | **Discovery is declared, and discovery is not execution.** `describe` `discovery:` is one of three classes. **`native`**: the framework's own collector, run under the same configuration and selection rules as execution, and bounded like execution because it may run project code. **`inventory`**: an explicit, enumerable rule or list, such as "each bind-matched script is one unit", or a committed inventory file. **`candidates`**: a source scan, which never claims complete discovery; `check` and `run` print `DISCOVERY:<runner>\|candidates`, and completeness consumers (M8 `full`) are told. The default for project scripts is `candidates` |
| G6 | **Freshness.** An adapter reads reports only from the per-invocation report directory, which the engine creates empty. A file older than the invocation start, a symbolic link, or a path outside that directory is refused as stale |
| G7 | **Child rows only through a registered reporting contract** (t1854_14). Until one is registered, `children:` is refused at load. A suite's exit is never read as individual test results. **Child evidence takes the same reconciliation route as top-level evidence.** Each subsumed unit's expected identities come from its own runner's discovery in the same `Load`. Its case identities (a `cases` runner) or its own identity (a `unit` runner) are reconciled by the **one shared engine reconciler** under G1a and G1b. Child statuses and counters are engine-derived, and a discovered subsumed unit with no reconciled evidence counts as `unaccounted` in `RUN_ACCOUNTING`, never as implicitly covered |
| G8 | **Supervision with containment.** Every process an adapter starts, for discovery or for execution, runs bounded and cancellable, inside a **containment that a descendant cannot leave by changing its process group or session**. On Linux this is `PR_SET_CHILD_SUBREAPER` on the supervising process plus a parent-pid descendant tree, which still holds every orphaned and every `setsid()` descendant. A cgroup v2 leaf is used when a delegated cgroup is writable. Cleanup kills the whole contained tree and verifies it empty; a survivor or an unverifiable host is a mechanism failure. **Enforceable support restriction:** on a platform without verified containment (darwin today), production adapters refuse to run (`CONTAINMENT_UNAVAILABLE:<platform>`, mechanism, exit 3) instead of running uncontained. A documented prohibition is never counted as containment |
| G8a | **Cleanup ownership is per invocation and survives a builtin crash.** Each invocation runs inside its own ownership boundary, whose membership the kernel keeps even after every process between it and the engine has died. **Initially that is a cgroup v2 leaf per invocation** (delegated subtree) only. Cleanup kills exactly that boundary's members. Without a delegated cgroup, the only boundary is the engine's subreaper tree, which cannot tell invocations apart once a builtin dies. Invocations then **must not overlap**: the engine refuses parallel execution (`PARALLEL_REFUSED:containment`) and runs serially, where the tree has a single owner. Killing the engine's whole tree is never used to clean up one invocation. **Every boundary backend must keep G9's cleared-environment recursion detection working before it is enabled.** For that reason a PID-namespace backend is deferred to its own task (below): PIDs, parent visibility and `/proc` differ across namespaces, and the ancestry backstop has no namespace-aware mapping |
| G9 | **Recursion.** Every engine entry point that starts runner processes refuses a nested entry for the **same repository** at runtime, including through indirect calls: `run`, and `Load` (so `scan`, `check`, and later `test` / `select`) — native discovery runs project code too. Engine tests against fixture repositories are allowed. The guard is a prerequisite of **every** production adapter (through the foundation) |
| G10 | **Support claims.** An adapter is *supported* only for the tool versions and platforms its real-tool integration tests run against, in CI (`AIT_TESTMAP_REQUIRE_REAL_TOOLS=1` turns their skips into failures there) or in a documented environment. Fakes serve targeted failure tests only. With no integration environment, the adapter stays **pending** |

What each status proves:

| status | proves | does not prove |
|---|---|---|
| `pass` | it ran in this invocation, under its bound. `cases`: every expected case identity has exactly one terminal result, none failed or errored, at least one passed (skipped cases are counted and listed). `unit`: the executable exited 0. `aggregate`: the command exited 0 | that the assertions are meaningful; that skipped cases ran; anything about cases discovery did not find (`candidates`); which tests ran inside an `aggregate` |
| `fail` | at least one case failed (whatever the rest), or the executable / command exited non-zero | where the fault is |
| `error` | the unit could not be judged: a case error with no failure, collection or build failure, incomplete / duplicate / unexpected / ambiguous / stale evidence, `zero_tests`, a protocol violation | anything about the code under test |
| `skip` | every expected case was skipped by the tool (with reasons), or G3 applied | any behaviour |
| `timeout` / `not_started` / `batch_timeout` / `missing` / `refused` | unchanged from M3.1 | — |

## Carried reality-check facts (verified 2026-10-21 at main `ab1704c89`; re-verify in Step 0)

- **M3.1 builtin protocol** (t1854_1, `3d1a2b628`).
  - Register with `runner.RegisterBuiltin(name)`; registering a name twice panics, and an unregistered builtin is `RUNNER_UNRESOLVED`.
  - A `builtin: <b>` runner runs as `runner.SelfExe()` + `runner <b> describe|list|run --manifest <abs>`, in the runner's `cwd`, under `Setsid`.
  - Env: `AIT_TESTMAP_ROOT`, `AIT_TESTMAP_RUNNER`, `AIT_TESTMAP_COMMAND` (the `command:` override) and, on `run`, `AIT_TESTMAP_RUN_ID`.
  - `runner.Manifest` is exported (indented JSON, with a `handle` field). `runner.LoadConfig` exposes `Entry{Bind, Cwd, Command, SubsumedBy, Overrides, OverrideKeys}` and `Config.Terminal`.
  - The `runner` verb is still `stub("runner")` in `goengines/cmd/ait-testmap/verbs.go`, and `main_test.go` `TestStubsExit64` expects `NOT_IMPLEMENTED:runner`.
- **Timeout model** (`runner/timeout.go`).
  - `per_unit`: the runner bounds each unit, writes start rows, and reports `timeout`.
  - `batch`: the `runners.yaml` entry must set `batch_timeout_s`.
  - `none`, the default: every unit is a singleton invocation, bounded by the engine.
  - `testmap:batch no` already makes a unit a singleton (`Unit.BatchNo` → `Key.Batch`).
  - An out-of-contract run exit is `mechanism/runner_exit:<n>`, and the run exit contract is 0/1/2/75/64.
- **Cleanup today.**
  - The engine sweeps the runner's whole **session** on every exit path (`exec_unix.go`, `proc_linux.go` / `proc_darwin.go`).
  - A process that calls `setsid()` escapes that sweep; M3.1 records this as a residual.
  - `t1854_3` (M3.3) plans `errgroup` **parallel** execution of invocations through `runner.RegisterExecutor`.
- **Hang guards** (t1985 `a81352ffb`, t1998 `b82f4becc`).
  - `isolated(t, hangLimit)` and its tripwire are unexported test code in package `runner`.
  - The tripwire parses only the `runner` directory, and `goengines/ci/preflight.sh` runs it alone before the suite.
  - A new package is covered by neither (inbox notes from t1985 / t1998 on t1854_2).
- **Eligibility** (M3.4 t1854_4 `487271c89`, t2080, t2081 `d9569b6ad`).
  - A child row is never an anchor (`opaque:child`), nor is a `full` / suite unit (`opaque:suite`).
  - `runnerConfig` treats `runners.yaml`, `runners/**` and each whitespace token of `command:` as runner inputs.
  - `cost/implicit.go` rules key on the test's **language**, not on a runner. Per t2081, a runner whose cwd is not an ancestor of the test, which uses `pytest -c` / `--rootdir` / `-p`, or which runs go-test per-package units, invalidates them. t2082 re-aligns the rules once the adapters land, so every adapter records **what it reads** (command line, cwd, config flags) in its plan or Final Notes.
- **Invariant 5 tripwire** (`goengines/guards_test.go`). It forbids the literal `aitask_*.sh` (and others) in non-test Go code unless the line carries `// invariant5-ok: <why>`.
- **Tools on the reference host** (2026-10-21):
  - bash 5.3, go 1.27.2 (module floor 1.26), pytest 8.4.2 in `~/.aitask/venv`, JDK 21;
  - Gradle 9.4.1 / 9.5.1 cached in `~/.gradle/wrapper/dists`, with aitasks_mobile registered as a project;
  - no `adb` / emulator;
  - unprivileged user + pid namespaces work, and the session cgroup v2 scope is writable.
- **Automation-first** (user directive, 2026-10-11). No path may make a human action a precondition. A human-only step met in the proposal is reported to its owning parent with a note.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1854_2** id=2026-10-22T08:04:14Z.39f1c58de47119c58cad433c from=t1854_2 from_verified=yes at=2026-10-22T08:04:14Z base=6dc5b76a4681026614ebb8366c455ff7d4915ff1 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1854_2 (M3.2a evidence contract), as landed in 6dc5b76a4. Verify against goengines/README.md and internal/testmap/runner before relying on it.
> | 
> | For the scaffold's shared helpers, reuse rather than re-implement:
> | - Report directory: runner.NewReportDir(path) creates it and records identity + Start; runner.FreshReport(d ReportDir, path) is the fresh-report reader (refuses outside paths, a replaced/symlinked report dir, inner links, non-regular, stale, >64 MiB). invoke.go already creates `inv-NNN/report/` per invocation.
> | - runner.ValidateCases(data, killed, expected, registered) validates cases.jsonl (strict, lossless JSON; malformed-line attribution); runner.CasesFile is the name. A results writer for cases rows should emit exactly `{"unit","case","status","duration_ms","message"?}`.
> | - Env the engine sets: AIT_TESTMAP_ACCOUNTING (list and run), AIT_TESTMAP_REPORT_DIR (run). Manifest gained `accounting`, `report_dir`, `units[].cases`.
> | - invoke.go changed (caseEvidence, NewReportDir use) — rebase your exec/invoke extension on it.
