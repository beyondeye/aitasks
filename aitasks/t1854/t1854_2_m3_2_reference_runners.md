---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: [t1854_1, t1985]
issue_type: feature
status: Implementing
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
implemented_with: claudecode/opus5_5
created_at: 2026-10-13 19:17
updated_at: 2026-10-22 09:51
---

## Context

Child **M3.2a — Evidence contract** of t1854 (test map, module M3). Wave **1**.

On 2026-10-21 M3.2 ("Reference runners") was re-decomposed around trustworthy
test evidence. The decision is in the parent's *M3.2 re-decomposition
(2026-10-21)* section and in `aiplans/p1854_testmap_m3_runners_scheduling_and_cost.md`.
This task keeps the id t1854_2 and the old file name, and is **rescoped**: it
writes the evidence guarantees into M3.1's runner contract **before any
production runner exists**. It registers no builtin.

It is a named extension of M3.1 (`goengines/internal/testmap/runner/`) and of
M3.4 (`goengines/internal/testmap/cost/`). Every other M3.2 sibling consumes
it.

## Scope

All guarantees below except G8 / G8a (t1854_6) and G9 (t1854_7). G10 is
documented here and applied per adapter.

## Acceptance criteria

- **Describe keys.** `describe` gains `accounting: cases|unit|aggregate` (default `unit`) and `discovery: native|inventory|candidates` (default `candidates`). An unknown value is refused, and `runners.yaml` may override both (the existing D6 override rule).
- **Zero-test policy.** `runners.yaml` entries gain `zero_tests: error|skip` (default `error`, G3).
- **Expected case identities (G1a).**
  - A `cases` runner's discovery hands the engine each unit's case identities. The protocol shape is decided in Step 0: case rows in `list`, or a separate `cases` verb run in the same `Load`, so discovery is fresh for every run.
  - The engine passes them in the manifest (`units[].cases`).
  - An identity is a non-empty, line-safe string, unique within its unit. A duplicate at discovery is `INPUT_ERROR:lister`.
- **Case results.**
  - The adapter writes strict case rows to `<report_dir>/cases.jsonl`: `{"unit","case","status":pass|fail|error|skip,"duration_ms","message"?}`.
  - Under `accounting: cases`, a top-level result row from the adapter is refused (start rows stay allowed). The **engine** derives the unit's result by G1a / G1b, and computes `cases_expected / passed / failed / errored / skipped` into the result and the record.
  - Under `unit` / `aggregate`, a case row is refused.
- **One shared reconciler.**
  - It is keyed `(parent?, unit, case?)`, and both top-level `cases` units and (from t1854_14) suite child evidence go through it (G7).
  - It takes the expected identities from discovery and the reported terminal results. It returns engine-derived statuses and counters, plus the reconciliation errors.
  - Its API is what t1854_14 calls.
- **Tests (case accounting).** Expected `{a,b}`, with each of these reported:
  - `{a,a}` → `error:duplicate_case`;
  - `{a,c}` → `error:unexpected_case` (+ `incomplete`);
  - `{a}` → `incomplete`;
  - `{a,b,b}` → `duplicate_case`.

  Also: mixed pass and skip → `pass`, with the skip counted and listed; fail beside error → `fail`; error without fail → `error`; all skip → `skip`; zero expected → G3 under both policies. The same matrix is driven through the reconciler with **child-keyed** input. Isolated mutants (count-only reconciliation; adapter-supplied counters trusted) must turn the equal-count tests red.
- **Output.** `RUN_ACCOUNTING:<selected>|<cases>|<unit>|<aggregate>|<unaccounted>` (text and JSON), and `DISCOVERY:<runner>|candidates` from `run`, `scan` and `check`.
- **Freshness (G6).** The manifest gains `report_dir`, which the engine creates empty for every invocation. A `FreshReport(path, invStart)` helper refuses a file older than the start, a symbolic link, or a path outside the directory. A test covers each refusal.
- **Reporting-contract seam (G7).** `runner.RegisterReportingContract(name)`, with `children:` refused at load while the name is unregistered. M3.1's existing child-row tests register a test-only contract.
- **Ledger (M3.4).** Ledger rows record `accounting` and `discovery`. An `aggregate` result never anchors (`opaque:aggregate`); every other existing anchor decision is unchanged, and its tests stay green.
- **Docs.**
  - `goengines/README.md` Interfaces rows: the guarantee table and the status proves / does-not-prove table.
  - Proposal `aidocs/testing_engine/n014_explorer_006_proposal.md`: split the Module Map M3.2 row into M3.2a–k (the sibling table in the parent), rewrite the *Reference runners* component around G1–G10, change Open question 8's default to "no per-file evidence without an explicit report", and add the deferred integrations to *Named follow-ups (not v1)*.
- **Tests.** Every rule is pinned by a test in package `runner` / `cost` under the existing `isolated` guard. An isolated mutant proves each G2 / G3 / G6 / G7 refusal load-bearing. `ait engine test` is green.

## Key files to modify

- `goengines/internal/testmap/runner/{describe,config,list,results,outcome,invoke,run}.go` (named extensions of M3.1), plus a new `reconcile.go`.
- `goengines/internal/testmap/cost/{hook,eligibility,ledger}.go` (named extensions of M3.4).
- `goengines/cmd/ait-testmap/run.go` (the output lines), `scancheck.go` (`DISCOVERY:`).
- `goengines/README.md`; the proposal (M3.2's row and component only, plus OQ 8 and *Named follow-ups*).

## Reference files for patterns

- `runner/results.go` (`ValidateRows`, per-id protocol errors) and `runner/outcome.go` (the outcome table, cause precedence).
- `aiplans/archived/p1854/p1854_1_m3_1_runner_contract_and_repository.md` (*Contract shapes*).
- `aiplans/archived/p1854/p1854_4_m3_4_cost_ledger.md` (eligibility).

## Provides / consumes

- **Provides:** the evidence contract and the shared reconciler, to t1854_6, t1854_8–t1854_14, M4.5, M6.1, M8.4.
- **Consumes:** M3.1 (t1854_1), M3.4 (t1854_4), t1985.

## Step 0 — Reality check (mandatory, before any code; recorded in the plan)

Re-read the guarantees below and the parent's re-decomposition section.
Inspect `runner` and `cost` as they are on the merge target. Decide the
case-identity protocol shape. Tabulate every difference against this body,
decide each one, and send notes to any sibling whose assumptions change.
Re-confirm that every touched file is M3.2a's or a named extension.

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

> **✉ note:t1985** id=2026-10-15T05:57:54Z.11b5d7546ae2ff68e4c5792c from=t1985 from_verified=yes at=2026-10-15T05:57:54Z base=a81352ffb83835a8bed91624f991841c01902cee base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1985 (hang watchdog for the runner package's tests), as of commit a81352ffb:
> | 
> | - Package goengines/internal/testmap/runner now runs every process-starting test through `if !isolated(t, hangLimit) { return }`. It re-executes the test in a subprocess under a 20 s bound, reports HANG:<test>|<limit> with a goroutine dump, and kills leftover runner processes by an env marker. That marker is needed because execRunner Setsids each runner, so a session or tree kill misses them.
> | - M3.2's new package (runner/builtin/**) cannot import that helper: it lives in package runner's _test.go files (watchdog_unix_test.go, watchdog_linux_test.go). If the builtin runners' tests start real pytest / go test / bash processes and could hang, the same protection would need the helper moved to a shared internal test package, or a local equivalent. Whether that is worth it is your call; nothing requires it today.
> | - Related: the M3.2 builtins run as `<self> runner <name>` via SelfExe. In runner-package tests that is the test binary only if a test sets it so (today repo_test.go stubs it with a script).

> **✉ note:t1998** id=2026-10-15T21:03:09Z.fe97069b8246b589453566a6 from=t1998 from_verified=yes at=2026-10-15T21:03:09Z base=a669462a3cc2140f3fec671c5c9099a4d0dc27da base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1998 (hang-guard tripwire), as of commit b82f4becc. Not checked against your plan.
> | 
> | - Your new package goengines/internal/testmap/runner/builtin/** is outside both runner-package hang protections:
> |   - the watchdog guard `isolated(t, hangLimit)` is unexported test code in package runner (watchdog_unix_test.go), so builtin's tests cannot call it;
> |   - the source tripwire (runner/isolation_tripwire_test.go, run alone before the suite by goengines/ci/preflight.sh) parses only the runner directory itself.
> | - Consequence: a builtin test that starts a process (fixture.New, exec.Command, Run, Load, …) and hangs will wait for go test's own timeout, and no tripwire will flag it.
> | - Options to weigh in your own planning, if your builtin tests start processes:
> |   - keep the process-starting tests in package runner, where both protections apply;
> |   - or give builtin its own watchdog and tripwire. That would mean extending t1998's analyzer, which is directory-scoped by design, and adding builtin to ci/preflight.sh.

> **✉ note:t2081** id=2026-10-20T12:23:56Z.af27fbbd21e517cd240f4579 from=t2081 from_verified=yes at=2026-10-20T12:23:56Z base=d9569b6ad2b1fd5615f3c96312a1f177f6d2550a base_branch=main dirty=no host=omg16
>
> | Context from t2081 (committed d9569b6ad), for when you design the reference runners:
> | 
> | - Anchor eligibility (cost/eligibility.go) now also checks the *implicit* inputs of a test's framework (cost/implicit.go). With no runners implemented, these rules are keyed on the test file's scanner language (Facts(test).Lang), not on a runner:
> |   - pytest: config and conftest/__init__ files in ancestor dirs of the test;
> |   - go: module/workspace files of every reached package's ancestors, and any path under a reached package's tree that the no-follow scan cannot see;
> |   - Gradle: scripts, wrapper, buildSrc, build-logic, included builds, module resources.
> | - Any runner behaviour that reads inputs outside those rules invalidates the rules. Examples: a cwd that is not an ancestor of the test, `pytest -c` / `--rootdir` / `-p` plugins, go-test per-package units. Gradle `filter_scope: whole_run` is already `opaque:whole-run`.
> | - t2082 (align_implicit_inputs_with_reference_runners) owns re-aligning the rules once your runners land. Naming what each runner reads (command line, cwd, config flags) in your plan or Final Notes makes that cross-check direct.

> **👁 note:read** id=2026-10-21T12:33:37Z.a5c4b434f672de37d1ec5da1 by=t1854_2 at=2026-10-21T12:33:37Z mode=explicit ids=2026-10-14T14:40:22Z.2574bb9073e9e268803b4cca,2026-10-15T05:57:54Z.11b5d7546ae2ff68e4c5792c,2026-10-15T21:03:09Z.fe97069b8246b589453566a6,2026-10-20T12:23:56Z.af27fbbd21e517cd240f4579

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-22T06:51:46Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-22T08:01:55Z status=pass attempt=1 type=human
