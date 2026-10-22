---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-21 22:06
updated_at: 2026-10-21 22:06
---

## Context

Child **M3.2d — Recursion guard** of t1854. Wave **1**. See the parent's *M3.2
re-decomposition (2026-10-21)* section.

A test, a suite command, or a framework's native discovery (pytest collection
imports `conftest.py`; `go test -list` runs package `init`) can start another
engine run of the **same repository**. Through `./ait test` that would also
reach `aitask_test.sh`, against Invariant 5. Command-text inspection is only an
early diagnostic (t1854_12). This task owns the **runtime** protection (G9)
and is a prerequisite of every production adapter through t1854_6.

It is a named extension of M3.1's `runner.Run` and `runner.Load`.

## Acceptance criteria

- **Repository identity.** The realpath of the git common dir. Another worktree of the same repository has the same identity.
- **The guard.** Every engine entry that starts runner processes — `Run`, and `Load` (so the `describe` / `list` discovery behind `scan` and `check`; later `test` / `select`) — refuses when that identity is already active: `RUN_ERROR:recursion|<root>`, exit 3, before any runner process starts.
- **The marker.** Active identities travel in `AIT_TESTMAP_ACTIVE`, which the engine exports to every runner process (`describe`, `list`, `run`).
- **The `env -i` backstop.** A per-repository run lock under `.aitask-testmap/` records the holder's pid and start time. A nested entry whose holder is one of its own ancestors is refused. A concurrent, non-ancestor run of the same repository is not affected by this check.
- **Tests:**
  - nested `run` of the same repository through `sh -c`, `bash` and `python` subprocesses → refused;
  - the same under `env -i` → refused by the ancestry backstop;
  - another worktree of the same repository → refused;
  - **originating in discovery:** a project runner whose `list` calls `ait-testmap check` / `run` on the same repository → refused;
  - **originating in execution:** a runner whose `run` does the same → refused;
  - a fixture repository → allowed, from both paths;
  - goengines' own suite under an active marker → green.

  These tests are written so t1854_6 can parameterize them over its boundary backends.
- **Docs.** The README Interfaces row. `ait engine test` is green.
- **Owner coordination (notes sent at implementation time):**
  - **t1856 (M5.1):** `aitask_test.sh` calls the guard first and never strips the marker; its own tests use fixture repositories.
  - **t1855 (M4.5):** the `test` verb runs through the same guard.

## Key files to modify

- `goengines/internal/testmap/runner/{run,repo}.go` and a new `recursion.go`, with tests.
- `goengines/cmd/ait-testmap/run.go` (the error line).
- `goengines/README.md`.

## Reference files for patterns

- `runner/run.go` (`Run`), `runner/repo.go` (`Load`, `Runner.command` env).
- `internal/gitx` (common dir).
- `internal/platform` (`Lock`).

## Provides / consumes

- **Provides:** G9, to t1854_6 (and so every adapter), t1854_12, t1859_4, M4.5, M5.1 and `testmap_pidns_invocation_boundary`.
- **Consumes:** M3.1 (t1854_1, landed).

## Step 0 — Reality check (mandatory, before any code; recorded in the plan)

- Inspect `Run` / `Load` and every caller that reaches them (`scan`, `check`, `run`, and the in-process tests that call them).
- Confirm that no engine test runs `Run` / `Load` against the real repository while a marker would be active.
- Tabulate the differences and decide each one.

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

> **✉ note:t1854_5** id=2026-10-22T12:42:05Z.9683437533939050badc36c9 from=t1854_5 from_verified=yes at=2026-10-22T12:42:05Z base=ed04c92a57296b34828cb90e9af371b88383aae6 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1854_5 (M3.2b shared hang watchdog), landed in commit ed04c92a5. This supersedes your body's carried fact that "`isolated(t, hangLimit)` and its tripwire are unexported test code in package runner; the tripwire parses only runner". Not checked against your plan; re-verify in your Step 0.
> | 
> | - The guard is now `hangguard.Isolated(t, limit) bool`, imported from github.com/beyondeye/aitasks/goengines/internal/testsupport/hangguard (test support: only _test.go files may import it). A process-starting top-level test begins with `if !hangguard.Isolated(t, <limit>) { return }`. runner keeps its own `isolated(t, hangLimit)` wrapper, which is also accepted. Each package picks its own limit.
> | - Opt-in is ONE entry in `tripwirePackages` in internal/testsupport/hangguard/tripwire_test.go: {dir, name, localStarters, allow}. goengines/ci/preflight.sh (both workflows, `ait engine test`) then enforces it. A _test.go file importing hangguard from a package with no entry fails preflight (TestIsolationTripwireImports).
> | - The tripwire is lexical. Put in localStarters any entry point that starts processes through methods, interfaces or func fields. Another listed entry's localStarters count as starters for you too: with runner listed, runner.Run and runner.Load are seen in your package.
> | - Hazard for adapters that run test binaries (e.g. go-test): a child process inherits AIT_HANGGUARD_ISOLATE. A child test binary of this module that uses the guard would refuse to run ("runs inside the subprocess of ..."), or run a same-named test unguarded. Clear the variable in such a child's environment.
> | - Details and the full rationale are in the archived plan p1854_5 (Final Implementation Notes, "Notes for sibling tasks").

> **👁 note:read** id=2026-10-22T16:37:28Z.a10d842e228276093f45e8b3 by=t1854_7 at=2026-10-22T16:37:28Z mode=explicit ids=2026-10-22T12:42:05Z.9683437533939050badc36c9
