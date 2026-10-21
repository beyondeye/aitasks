---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Postponed
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-21 22:06
updated_at: 2026-10-21 22:06
---

## Context

Child **M3.2j — `device` adapter** of t1854. Wave **4**. **Postponed:** it
needs an emulator / adb integration environment, which the reference host
does not have (2026-10-21), and M3.3's allocator (t1854_3) to fill the
manifest's `handle`. See the parent's *M3.2 re-decomposition (2026-10-21)*
section. Consumer: M10.4 (aitasks_mobile `androidDeviceTest`, emulator
allocator).

**Un-park it** (set `Ready`) when both hold: t1854_3 and t1854_11 have landed,
and an emulator environment is available locally or in CI.

## Acceptance criteria (specific)

- **Classes.** `accounting: cases`; Step 0 decides `discovery:`. Connected tests have no dry run, so an explicit inventory, or the androidTest source set with candidate semantics, is the choice.
- **Handle.** It reads the manifest's `handle` (exported as `ANDROID_SERIAL` and `AIT_TESTMAP_HANDLE`). Without one it writes nothing and exits 75 (a clean refusal, `DEVICE_NO_HANDLE:<runner>` on stderr).
- **Shared driver.** It uses t1854_11's Gradle driver: default `./gradlew {module}:connectedDebugAndroidTest`, the class filter `-Pandroid.testInstrumentationRunnerArguments.class=<FQN,…>`, and reports in the fresh report directory.
- **Support.** A **real-emulator** integration test is required before support is claimed. Until then the adapter is not registered for production.

## Key files to modify

- `goengines/internal/testmap/runner/builtin/device*.go` (owned).

## Provides / consumes

- **Provides:** the `device` builtin, to M10.4.
- **Consumes:** t1854_11 (the Gradle driver) and t1854_3 (the allocator handle); through t1854_11, the foundation.

## Step 0 — Reality check (mandatory, before any code; recorded in the plan)

Inspect t1854_3's allocator and handle and t1854_11's driver as landed. Choose
the discovery class. Tabulate the differences and decide each one.

## Acceptance criteria common to every adapter (t1854_8 – t1854_13)

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
