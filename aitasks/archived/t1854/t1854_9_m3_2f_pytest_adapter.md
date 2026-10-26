---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: high
depends: [t1854_6]
issue_type: feature
status: Done
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
implemented_with: claudecode/opus5_5
created_at: 2026-10-21 22:06
updated_at: 2026-10-26 10:06
completed_at: 2026-10-26 10:06
---

## Context

Child **M3.2f — `pytest` adapter** of t1854. Wave **3**. See the parent's
*M3.2 re-decomposition (2026-10-21)* section. Consumers: M10.1 (aitasks'
~320 Python test modules, with the serial carve-out as `testmap:batch no`) and
thinking_backend.

## Acceptance criteria (specific)

- **Classes.** `accounting: cases`, `discovery: native`.
- **Evidence contract (amended 2026-10-25, plan review; user decision).** The reporting contract is the **exact runtime identity** of every result, recorded by an engine-owned, observe-only pytest plugin (`-p _aitestmap_pytest_evidence`, its directory prepended to `PYTHONPATH`, records written to `$AIT_TESTMAP_PYTEST_EVIDENCE`). It records the rootdir pytest resolved, the collected node ids, every collect report that did not pass, every test phase report with its node id, and the exit status. JUnit XML is **not** used: its `(classname, name)` keys are not identities (`tests/test_a.py::TestC::test_m` and `tests/test_a/TestC.py::test_m` share one), so a collect-only-vs-run substitution could be accepted as a pass.
  - Only the controller writes (xdist workers are silent; xdist forwards their reports).
  - The parse is strict: exactly one session (first) and one end (last), known members only, lossless JSON, and the end's exit status equal to the process exit. Discovery requires exactly one items record (`[]` for an empty collection), so a lost inventory can never read as zero-case units.
  - Deviation from "no `-p`" (for t2082): the plugin is engine-owned and observe-only, and its source is part of the engine version. The environment gains only `PYTHONPATH` (the plugin directory first) and `AIT_TESTMAP_PYTEST_EVIDENCE`. No `-c`, `--rootdir`, `-o` or `--junitxml` is passed. This is adapter-scoped and distinct from the deferred injection into suite commands (t2118).
- **Discovery.**
  - `pytest -p <plugin> --collect-only -q ./<file>…` over the bound, git-visible files, per runner, run by `list` under the foundation's discovery bound (collection imports project code).
  - It uses the **same** cwd, ini, rootdir and selection arguments as execution: one argument builder; the two differ only by `--collect-only -q` (a test proves it).
  - The unit is a test file. Its case identities are the collected node ids, plus, for a module skipped at collection (`pytest.skip(allow_module_level=True)`), the collector's node id.
  - Node ids map to their files by exact path under the **reported** rootdir; the unit's lowering is its rootdir-relative path. A node id naming no listed file refuses the list.
  - A collection error is `INPUT_ERROR:lister`, never a silently dropped unit. An interpreter that ignores `PYTHONPATH` (`python -I` / `-E`), and anything but pytest 8.x on CPython ≥ 3.10, refuse the list.
- **Execution.**
  - `timeouts: batch` (the entry needs `batch_timeout_s`), one pytest per invocation, **no start rows** (a batch timeout cannot say which file was running, so every unit is `batch_timeout`).
  - The evidence is read only from the fresh report directory (G6, `Env.Fresh`).
  - One case row per terminal tool result, keyed by the exact runtime node id: every phase that did not pass is its own result (setup/teardown `failed` → error, `skipped` → skip with its reason, xfail → skip `xfail: <reason>`) and the call phase always is one. Nothing is merged, so a test failing, then erroring or skipping in teardown, is `duplicate_case`. A collector's skip or failure is a result for the collector's node id.
  - Mechanism (exit 3, no case rows), never a pass or an unexplained skip (G2): evidence absent, stale, linked or malformed; a node id outside every unit; the rootdir moved since discovery; an exit status contradicting the evidence (0 with a failure, 1 or 2 without one, 5 with a test).
- **Policies.**
  - G3: zero collected cases → `error:zero_tests` unless `zero_tests: skip`. A module-level skip is not zero tests: it is `skip` with its reason under either policy.
  - `testmap:batch no` units run as singleton invocations (tested with two such units beside a batch).
- **Real-tool tests.**
  - pytest 8.x on CPython ≥ 3.10.
  - CI installs a pinned pytest (8.4.2, with pytest-xdist 3.8.0) before `go test` in `.github/workflows/goengines-check.yml` and `release.yml`, which set `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1`. Locally the tests use `python3` on PATH, else `~/.aitask/venv` (pytest 8.4.2).
  - Cases: parametrized ids, class tests, xfail / xpass, a skip with a reason, a teardown skip, a collection error, a rootdir above and below the cwd, overlapping paths, an equal-key substitution, a module-level skip (isolated, mixed, appearing or disappearing), and pytest-xdist when installed.
- **Fakes** only for evidence the real tool cannot produce: stale, linked, malformed, contradicting the exit, outside every unit, a moved rootdir, an unsupported version, a missing items record.
- **What it reads (for t2082).** The command lines above. Its cwd is an ancestor of every listed test (the list is cwd-scoped). pytest itself resolves the ini from the args' common ancestor upward (possibly above the repository), the `conftest.py` files along the tests' paths, `PYTEST_ADDOPTS` / `PYTEST_PLUGINS` and installed plugins. The `-p` / `PYTHONPATH` deviation is documented above.

## Key files to modify

- `goengines/internal/testmap/runner/builtin/pytest*.go` (owned).
- `.github/workflows/goengines-check.yml` (the pinned pytest install).

## Provides / consumes

- **Provides:** the `pytest` builtin, to M10.1, M6.1 `detect`, t1854_14 and t2082.
- **Consumes:** t1854_6 (and, through it, t1854_2, t1854_5, t1854_7).

## Step 0 — Reality check (mandatory, before any code; recorded in the plan)

- Inspect the contract's case-identity protocol and the foundation as landed.
- Measure `--collect-only` on aitasks' tests for time and side effects.
- Confirm the junitxml fields needed to rebuild nodeids (xunit1 `file` / `classname` / `name`) against the real pytest 8.
- Tabulate the differences and decide each one.

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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1854_2** id=2026-10-22T08:04:02Z.70d9eaf2d10bfbd6eba66d23 from=t1854_2 from_verified=yes at=2026-10-22T08:04:02Z base=6dc5b76a4681026614ebb8366c455ff7d4915ff1 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1854_2 (M3.2a evidence contract), as landed in 6dc5b76a4. Verify against goengines/README.md (Interfaces + "Evidence contract (M3.2)") and internal/testmap/runner before relying on it.
> | 
> | Decisions that change what a cases adapter assumes:
> | - Case identities come from `list`: one `<unit id>\tcase\t<identity>` row per expected case, beside the unit row (any order). An identity is non-empty UTF-8 with no control char, once per unit; a duplicate is RUNNER_PROTOCOL (INPUT_ERROR:lister via scan/check). There is no separate `cases` verb.
> | - `list` and `run` get AIT_TESTMAP_ACCOUNTING (the effective class, after runners.yaml overrides); `run` also gets AIT_TESTMAP_REPORT_DIR. The manifest carries `accounting`, `report_dir` and `units[].cases` (present, possibly [], only for cases runners).
> | - Write one row per terminal tool result to `$AIT_TESTMAP_REPORT_DIR/cases.jsonl`: `{"unit","case","status":pass|fail|error|skip,"duration_ms","message"?}`. Members spelled exactly, once, lossless JSON (no invalid UTF-8, no unpaired \uD8xx escape). Never write a top-level result row to results.jsonl (start rows are fine): it is the unit's `result_under_cases` error.
> | - Exit rule under cases: 0 iff no reported case is fail/error, 1 otherwise, 2 only with no case rows. Missing/zero evidence is the engine's (incomplete / zero_tests), not an exit concern.
> | - `accounting: cases` refuses `timeouts: per_unit` (use batch or none).
> | - Kill path: only a unit whose every expected identity was reported keeps its status; invalid written evidence stays an error; everything else is timeout attribution.
> | - Reports are read only through runner.FreshReport from the engine-created report directory (a replaced dir, links, stale mtimes are refused).

> **✉ note:t1854_5** id=2026-10-22T12:42:10Z.b09e80b7037ffa01caaaab7f from=t1854_5 from_verified=yes at=2026-10-22T12:42:10Z base=ed04c92a57296b34828cb90e9af371b88383aae6 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1854_5 (M3.2b shared hang watchdog), landed in commit ed04c92a5. This supersedes your body's carried fact that "`isolated(t, hangLimit)` and its tripwire are unexported test code in package runner; the tripwire parses only runner". Not checked against your plan; re-verify in your Step 0.
> | 
> | - The guard is now `hangguard.Isolated(t, limit) bool`, imported from github.com/beyondeye/aitasks/goengines/internal/testsupport/hangguard (test support: only _test.go files may import it). A process-starting top-level test begins with `if !hangguard.Isolated(t, <limit>) { return }`. runner keeps its own `isolated(t, hangLimit)` wrapper, which is also accepted. Each package picks its own limit.
> | - Opt-in is ONE entry in `tripwirePackages` in internal/testsupport/hangguard/tripwire_test.go: {dir, name, localStarters, allow}. goengines/ci/preflight.sh (both workflows, `ait engine test`) then enforces it. A _test.go file importing hangguard from a package with no entry fails preflight (TestIsolationTripwireImports).
> | - The tripwire is lexical. Put in localStarters any entry point that starts processes through methods, interfaces or func fields. Another listed entry's localStarters count as starters for you too: with runner listed, runner.Run and runner.Load are seen in your package.
> | - Hazard for adapters that run test binaries (e.g. go-test): a child process inherits AIT_HANGGUARD_ISOLATE. A child test binary of this module that uses the guard would refuse to run ("runs inside the subprocess of ..."), or run a same-named test unguarded. Clear the variable in such a child's environment.
> | - Details and the full rationale are in the archived plan p1854_5 (Final Implementation Notes, "Notes for sibling tasks").

> **✉ note:t1854_6** id=2026-10-25T06:58:39Z.77ae779f5cabdec6100bffbb from=t1854_6 from_verified=yes at=2026-10-25T06:58:39Z base=60ca89154aa0d66ceec006c9f8c6b764fe661ae6 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_6 (M3.2c supervised execution foundation), as landed in commit 60ca89154. Verify against goengines/README.md (Interfaces: "supervised execution", "halt", "runner <name>") before relying on it.
> | 
> | - G8/G8a were revised (task t1854_6 body and parent t1854). Containment is a dedicated per-start supervisor (ait-testmap __supervise, a subreaper of its own subtree only; cleanup proven by wait4 ECHILD), not a cgroup leaf or an engine-wide tree; cgroup hardening is a deferred follow-up. The G-table copy in your body predates this.
> | - The scaffold is goengines/internal/testmap/runner/builtin. Register with builtin.Register(builtin.Adapter{Name, Describe, List, Run}); the engine resolves `builtin: <name>` and runs `ait-testmap runner <name> describe|list|run --manifest <p>` → builtin.Main.
> | - Env carries Root, Runner, Command (the command: override), Accounting, RunID, ReportDir (via runner.OpenReportDir), Entry() (runners.yaml lookup), Supervise(ctx, procsup.RunSpec) and Fresh(path) (FreshReport).
> |   - Run every tool through Env.Supervise. It gives each tool its own supervisor, a Timeout/Grace, and outputs to regular files only (FIFO/device/link refused), capped by OutputMax; it reports OutputErr and Truncated.
> |   - Bound native discovery in List with builtin.DiscoveryBound().
> |   - Split command: with builtin.SplitCommand: whitespace argv, refusing shell metacharacters and quoting.
> | - Under accounting: cases, write start rows (Results.Start) and case rows (Results.Case) only; the engine derives unit results. Use Results.Row only for unit/aggregate accounting.
> | - Where containment is unavailable (darwin), a production adapter refuses (CONTAINMENT_UNAVAILABLE:<platform>, exit 3) before doing anything.
> | - Any test binary that supervises (yours will) needs procsup.MaybeSupervise() as the first statement of its TestMain. Its process-starting tests need hangguard.Isolated, plus a tripwirePackages entry for the package.
> | - Record in your plan what each adapter reads (command line, cwd, config flags), per t2081/t2082.
> | - A worked test-only example adapter ("echo") is in runner/builtin/main_test.go.

> **✉ note:t15** id=2026-10-25T08:54:19Z.260db30f2b8b583044a42b55 from=aitasks_go#t15 at=2026-10-25T08:54:19Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t1854_8** id=2026-10-25T12:30:52Z.c0e89544dded95a30f09aec2 from=t1854_8 from_verified=yes at=2026-10-25T12:30:52Z base=c774eb540e034fdb097cf2d4d4e34a16b08a15a2 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_8 (M3.2e bash-file adapter), landed in e88923ecb and c774eb540. Not checked against your plan; re-verify in your Step 0.
> | 
> | - c774eb540 sets `AIT_TESTMAP_REQUIRE_REAL_TOOLS: '1'` on the legacy-mode `go test` step of .github/workflows/goengines-check.yml and release.yml. A real-tool test of yours that skips without pytest now fails there, so the pinned pytest install you own must run before that step, in both workflows.
> | - The adapter-file tripwire (bashfile_tripwire_test.go) covers every non-test file of runner/builtin except the scaffold. Run tools only through e.Supervise; gitx.Env is the one allowed gitx name; dot imports are refused.
> | - TestRunnerVerb (cmd) pins the registered adapters: add yours to `want`.
> | - main_test.go dispatches `__nested_engine check|run`, which you can reuse for the recursion criteria. Assert `VIA:marker`, not just `RUN_ERROR:recursion`: the ancestry backstop refuses a nested entry whose marker was dropped too.
> | - Do not use runner.Load as the oracle for your adapter's own error handling of tool stderr: loadGuarded re-runs annot / gitx.ListFiles, which reject git stderr themselves.
> | - Real-tool tests chaining engine loads ran ~28 s under -race on a loaded host; bash-file uses its own 120 s hang limit.

> **👁 note:read** id=2026-10-25T12:45:58Z.7c39f7e2fcd9aae1720cc719 by=t1854_9 at=2026-10-25T12:45:58Z mode=explicit ids=2026-10-22T08:04:02Z.70d9eaf2d10bfbd6eba66d23,2026-10-22T12:42:10Z.b09e80b7037ffa01caaaab7f,2026-10-25T06:58:39Z.77ae779f5cabdec6100bffbb,2026-10-25T08:54:19Z.260db30f2b8b583044a42b55,2026-10-25T12:30:52Z.c0e89544dded95a30f09aec2

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-25T14:38:36Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-26T08:03:18Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-26T08:06:46Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:f06d3bc093f4b208

> **✅ gate:risk_evaluated** run=2026-10-26T08:06:46Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1854_9/risk_evaluated_2026-10-26T08:06:46Z-risk_evaluated-a1.log`
