---
priority: medium
effort: high
depends: [t1854_12, t1854_8, t1854_9, t1854_10]
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-21 22:06
updated_at: 2026-10-21 22:07
---

## Context

Child **M3.2k — Suite reporting contract** of t1854. Wave **4**. See the
parent's *M3.2 re-decomposition (2026-10-21)* section.

It gives a `full: true` `suite` runner per-test **child** evidence, but only
from reports the suite command writes **explicitly**, with attribution
verified by the shared engine reconciler (G7). It replaces the rejected
design's injected `BASH_ENV` traps and pytest plugins. Those automatic
integrations are deferred to two standalone Postponed tasks that depend on
this one. Proposal Open question 8 is answered "no per-file evidence without
an explicit report".

## Acceptance criteria (specific)

- **Documented formats**, written explicitly by the command into `$AIT_TESTMAP_REPORT_DIR` (the fresh report directory):
  - JUnit XML (e.g. the project's own `pytest --junitxml=$AIT_TESTMAP_REPORT_DIR/…`);
  - a `go test -json` stream file;
  - an engine-native per-test JSONL. This is the documented way a bash suite reports per-file exits (a small documented helper may write it).

  Each format is registered with `runner.RegisterReportingContract`, which un-refuses the matching `children:` names.
- **Verified attribution through the shared reconciler (G7).**
  - Each report entry is translated into a candidate `(suite parent, subsumed unit, case identity)` result. A `unit`-class subsumed runner (bash-file) uses the unit's own identity as its single case.
  - The expected identities come from each subsumed runner's own discovery in the same `Load`.
  - The engine reconciles them with **G1a / G1b**: exactly one terminal result per expected identity; a duplicate, unexpected or missing identity is an error whatever the counts; child statuses and counters are engine-derived, never taken from the report.
  - Entries that map to no subsumed unit, or ambiguously, and stale reports are refused.
  - A discovered subsumed unit with no evidence is `unaccounted` in `RUN_ACCOUNTING`, and child coverage is never claimed complete while any is.
- **No injection.** The adapter sets nothing in the command's environment except `AIT_TESTMAP_REPORT_DIR` and the t1854_7 marker: no `BASH_ENV`, no `PYTHONPATH`, no `PYTEST_ADDOPTS`.
- **Tests on the suite path**, with real tools producing the reports where possible:
  - expected `{a,b}`, reported `{a,a}` → `duplicate_case`;
  - `{a,c}` → `unexpected_case` + `incomplete`;
  - `{a}` → `incomplete`;
  - mixed pass and skip → `pass`, with the skip listed;
  - fail beside skip → `fail`;
  - a subsumed unit absent from every report → `unaccounted`;
  - a bash file reported twice → `duplicate_case`;
  - a stale report → refused.

  Isolated mutants (per-unit count matching, report-supplied counters) must turn the equal-count cases red.
- **Real-tool tests** per format, through the real pytest, go and bash adapters (G10).

## Key files to modify

- `goengines/internal/testmap/runner/builtin/report*.go` (owned).
- The reconciler call site in `runner` (a named extension, through t1854_2's API).
- `goengines/README.md`; the proposal (the *Reference runners* component and OQ 8).

## Provides / consumes

- **Provides:** child evidence for `full` suites, to M10.5 (thinking_app `verify-active`), M8 and the deferred automatic integrations.
- **Consumes:** t1854_12 (suite), t1854_8 / t1854_9 / t1854_10 (formats and discovery), and t1854_2 (the reconciler).

## Step 0 — Reality check (mandatory, before any code; recorded in the plan)

Inspect the reconciler API, the suite adapter and the three adapters'
identities as landed. Fix each format's identity mapping. Tabulate the
differences and decide each one.

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

> **✉ note:t1854_2** id=2026-10-22T08:04:20Z.dfef9825e36e26d08cbfce78 from=t1854_2 from_verified=yes at=2026-10-22T08:04:20Z base=6dc5b76a4681026614ebb8366c455ff7d4915ff1 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1854_2 (M3.2a), as landed in 6dc5b76a4. Verify the API in internal/testmap/runner/reconcile.go before relying on it.
> | - Reconciler: runner.Reconcile([]Expectation{Key: EvidenceKey{Parent: suite id, Unit: subsumed id}, Cases, ZeroTests, Taints}, []CaseResult{Key, Case, Status, DurationMS, Message}) -> ([]Reconciled, stray). A unit-class subsumed runner: pass Cases = [its own id] per your plan. Report-level faults go in Taints (runner.ReasonMalformedCase / ReasonRejectedReport); report the `stray` results yourself. Reconciled has Status, Reasons (errors), Policy (zero_tests), Counts, Skipped, Complete, Terminal; TestReconcileMatrix already drives child keys.
> | - Register each report format with runner.RegisterReportingContract(name); until then `children:` is RUNNER_INVALID and child rows are invalid_child.
> | - Reports: read through runner.FreshReport(ReportDir, path); the dir is $AIT_TESTMAP_REPORT_DIR / manifest report_dir.
> | - RunAccounting.Unaccounted today counts subsumed units (terminal suite selected, not themselves selected) with no valid child row (accountFor in run.go); swap its source to reconciled child evidence.
> | - The child-row path in ValidateRows (rowContext.Children) is M3.1's; replacing it with the reconciler is yours.

> **✉ note:t1854_5** id=2026-10-22T12:42:23Z.a5cc19f3f781db65d9e6ac6a from=t1854_5 from_verified=yes at=2026-10-22T12:42:23Z base=ed04c92a57296b34828cb90e9af371b88383aae6 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1854_5 (M3.2b shared hang watchdog), landed in commit ed04c92a5. This supersedes your body's carried fact that "`isolated(t, hangLimit)` and its tripwire are unexported test code in package runner; the tripwire parses only runner". Not checked against your plan; re-verify in your Step 0.
> | 
> | - The guard is now `hangguard.Isolated(t, limit) bool`, imported from github.com/beyondeye/aitasks/goengines/internal/testsupport/hangguard (test support: only _test.go files may import it). A process-starting top-level test begins with `if !hangguard.Isolated(t, <limit>) { return }`. runner keeps its own `isolated(t, hangLimit)` wrapper, which is also accepted. Each package picks its own limit.
> | - Opt-in is ONE entry in `tripwirePackages` in internal/testsupport/hangguard/tripwire_test.go: {dir, name, localStarters, allow}. goengines/ci/preflight.sh (both workflows, `ait engine test`) then enforces it. A _test.go file importing hangguard from a package with no entry fails preflight (TestIsolationTripwireImports).
> | - The tripwire is lexical. Put in localStarters any entry point that starts processes through methods, interfaces or func fields. Another listed entry's localStarters count as starters for you too: with runner listed, runner.Run and runner.Load are seen in your package.
> | - Hazard for adapters that run test binaries (e.g. go-test): a child process inherits AIT_HANGGUARD_ISOLATE. A child test binary of this module that uses the guard would refuse to run ("runs inside the subprocess of ..."), or run a same-named test unguarded. Clear the variable in such a child's environment.
> | - Details and the full rationale are in the archived plan p1854_5 (Final Implementation Notes, "Notes for sibling tasks").

> **✉ note:t15** id=2026-10-25T08:54:31Z.ba6cfd0020f6061e6763328a from=aitasks_go#t15 at=2026-10-25T08:54:31Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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
