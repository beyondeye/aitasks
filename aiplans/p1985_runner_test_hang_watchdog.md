---
Task: t1985_runner_test_hang_watchdog.md
Base branch: main
Output branch: main
---

# t1985 — Hang watchdog for the runner package's process-starting tests

## Context

t1854_1's reviewer found that the runner tests assert their timing bounds only
**after** `Run` returns (`timedRun` in `timeout_run_test.go`, the in-loop check
in `TestRunReportFilesAreSafe`). A regression that makes `Run` hang (a blocking
report read, a sweep that never terminates, a lost `WaitDelay`) never reaches
those assertions: the suite sits until `go test -timeout` (10 min). The
t1854_1 red proof showed exactly that.

Goal: every runner test that starts a process fails **within its own bound**,
with a clear `HANG:<test>|<limit>` message, and leaves no process behind.
**Scope (user decision, 2026-10-14):** every process-starting test in the
package (~33), not just the 11 named ones. Every `Run`/`Load` goes through the
sweep and `readReport`, so a never-terminating sweep would hang them all. Pure
tests (`TestTimeoutDeadline`, the parsers, the grouping tests) stay in-process.

### Finding that shapes the design (verified in source)

The task assumes that SIGKILLing the test subprocess's session cleans up. **It
does not**: `execRunner` (`exec_unix.go:101`) starts every runner with
`Setsid: true`, so runner processes and their fixture `sleep`s live in
**their own sessions**. Killing the child's session leaves them alive, and once
the child dies they are orphaned to init, so walking the process tree cannot
find them either. They do carry the child's environment, though:
`invoke.go:124` / `repo.go:295` pass `os.Environ()` through, and `gitx.Env`
only scrubs `GIT_*`. So the parent gives each launch a **unique env marker**,
and after the child ends it kills every process whose `/proc/<pid>/environ`
carries that marker. The marker is the same variable that tells the child
which test to run.

**Plan review (2026-10-14), both concerns verified and addressed below:**
1. Once a process's environ matches the marker, a failed or unparsable
   `stat` read must not drop it from the cleanup result. The design
   distinguishes `ENOENT`/`ESRCH` from inspection failures, keeps known-owned
   uncertainty until the process is observed gone, and adds
   `TestReapMarkedUncertainty`.
2. A child given `^name$` loses the parent's subtest `-run`/`-skip`
   selection and its effective `-cpu`. Verified in Go 1.27 `testing`:
   `splitRegexp` is per level, and `runTests` sets `GOMAXPROCS` in the parent.
   The child now gets a rewritten `-run`, a verbatim `-skip` and the
   effective GOMAXPROCS, pinned by a differential control.

The watchdog must **not** reuse `sweepSession`/`sessionProcs`/`parseStat`.
Those are the code under test, and "a sweep that never terminates" is one of
the regressions it has to survive. It gets its own minimal `/proc` reader.

## Implementation

### 1. `goengines/internal/testmap/runner/watchdog_unix_test.go` (`//go:build unix`, new)

File comment: the mechanism, the Setsid finding above, and the residuals: a
process that clears its environment or execs setuid escapes the marker scan.
The runner contract forbids both and no fixture does either. It also gives a
**debug recipe**: `AIT_RUNNER_TEST_ISOLATE='<TestName>|debug' go test -run '^<TestName>$'`
(or the same env under `dlv test`) runs the body in-process, because that is
exactly the child path.

Constants:
- `isolateEnv = "AIT_RUNNER_TEST_ISOLATE"`. Value `<test name>|<pid>.<unixnano>`,
  unique per launch, so concurrent `go test` runs on the box never match each
  other's processes.
- `hangLimit = 20 * time.Second`. Normal durations are ≤3.2 s (measured:
  `TestCleanupEveryKillPath` 3.18 s), and the limit sits below the fixtures'
  `exec sleep 30`, so a lost deadline reads as a HANG, not as a slow pass.
- `quitGrace = 2 * time.Second`, `reapBound = 5 * time.Second`, `outputCap = 64 << 10`.

`func isolated(t *testing.T, limit time.Duration) bool`. Guarded tests start
with `if !isolated(t, hangLimit) { return }`.
- If `isolateEnv` is set: this is the child. When its name part equals
  `t.Name()`, return true and the body runs. When it names another test,
  call `t.Fatalf` (never recurse).
- Otherwise call `runChild(t, t.Name(), limit, parentSettings())`, then
  `t.Error` each line of `c.problems(name, limit)`, `t.Skip` if the child
  skipped, `t.Log(c.output)` when `testing.Verbose()`, and return false.

#### Child execution settings (the child must run the body as the parent would)

`type childSettings struct { run, skip string; cpu, parallel int; short, failfast, fullpath bool; coverdir string }`

`func parentSettings() childSettings` reads the live `testing` flags through
`flag.Lookup("test.<x>").Value`. `cpu` is **`runtime.GOMAXPROCS(0)`, not the
`-test.cpu` string.** Go 1.27's `runTests` applies each `-test.cpu` value
with `runtime.GOMAXPROCS(procs)` in the parent before running the tests
(`testing.go:2710-2711`), so a re-executed child would otherwise start at the
default. Reading the effective value also handles a list (`-cpu=1,3`): each
pass spawns its own child at that pass's value. Each child keeps
`-test.count=1`, so the parent's repetitions are not multiplied.

`func (s childSettings) args(name string, limit time.Duration) ([]string, error)`.
Every `test.*` flag Go 1.27 defines, decided explicitly:

| flag | child gets |
|---|---|
| `test.run` | **rewritten** by `childRunPattern` (below): the top level is pinned to `name` and the parent's sub-levels are kept |
| `test.skip` | forwarded **verbatim**. The child evaluates the same per-level skip on the same `name/…` paths, so subtest exclusions are identical |
| `test.cpu` | `s.cpu` (the effective GOMAXPROCS) |
| `test.count` | `1` |
| `test.v` | `true` always (PASS detection). The output is relayed through `t.Log` only when the parent is verbose |
| `test.short`, `test.failfast`, `test.fullpath`, `test.parallel` | forwarded |
| `test.paniconexit0` | always set (as `go test` does) |
| `test.timeout` | `2*limit`, a backstop if the parent itself dies |
| `test.gocoverdir` | forwarded when non-empty (checked in Verification 3) |
| `test.shuffle` | not forwarded: it reorders top-level tests only, and the child runs one |
| `test.coverprofile`, `cpuprofile`, `memprofile`(+`rate`), `blockprofile`(+`rate`), `mutexprofile`(+`fraction`), `trace`, `outputdir`, `artifacts`, `testlogfile` | **not** forwarded: the child would overwrite the parent's files. Profiles and the test log cover the parent process only (documented in the file comment) |
| `test.list` | n/a (a `-list` run runs no tests) |

`func childRunPattern(name, parentRun string) (string, error)` implements the
`-test.run` rewrite:
- `splitRunPattern(s) [][]string` is a faithful port of `testing.splitRegexp`
  (`match.go:168-215`): alternatives on a top-level `|`, levels on a
  top-level `/`, bracket and paren depth tracked, and the character after `\`
  skipped. Elements are kept **raw**. The child's own `testing` applies
  `rewrite` again, and `rewrite` is idempotent.
- Keep each alternative whose first element matches `name` under the testing
  matcher's rule: `regexp.MatchString(rewrite(elem0), name)`, where `rewrite`
  and `isSpace` are ported verbatim from `match.go:284-317`.
- Empty `parentRun`, or any kept alternative with a single level, gives
  `^name$` (all subtests). Otherwise the pattern is the kept alternatives,
  each written as `^QuoteMeta(name)$/<elem1>/<elem2>…`, joined with `|`.
- No alternative keeps `name`: return an error, and `isolated` calls
  `t.Fatalf`. Reaching this means the port disagrees with `testing` (the
  parent did run `name`). It fails closed and never widens to `^name$`.

`type childRun struct { hung bool; state *os.ProcessState; output string; elapsed time.Duration; leftover []string /* "<pid>:<comm>" */; cleanupErr error }`

`func runChild(t *testing.T, name string, limit time.Duration, s childSettings, env ...string) childRun`:
- Refuse a subtest name (contains `/`): top-level tests only.
- `exe, _ := os.Executable()`, not `os.Args[0]`. The arguments come from `s.args(name, limit)`.
- Env: `os.Environ()` + `env...` + `TMPDIR=<parent t.TempDir()>/tmp` + the
  marker. TMPDIR puts the child's `t.TempDir()` fixture repos under the
  parent's temp dir, so a killed child leaks nothing into `/tmp`.
- Stdout and stderr go to a **file** in the parent's temp dir, not a pipe. A
  leaked process holding the pipe could otherwise block `Wait`.
- `SysProcAttr{Setsid: true}`. `Start`, with `Wait` in a goroutine sending to `done`.
- If `done` fires first: normal exit.
- If the timer fires first (`limit`): `hung = true`. Send `SIGQUIT` to the
  child pid only (the Go runtime dumps every goroutine, which shows where the
  body hangs), then wait up to `quitGrace`. If the child is still unreaped,
  `SIGKILL` its group (`-pid`) and receive `done`. If it already exited, skip
  the group kill: a reaped pid's number may be reused, and the marker scan
  covers its group anyway.
- Always: `leftover, cleanupErr = reapMarked(marker, reapBound)`, then read
  the output file, capped at `outputCap` with a `[truncated N bytes]` note.

`func (c childRun) problems(name string, limit time.Duration) []string`. Order and text:
- hung: `HANG:<name>|<limit>`, then a line `killed after <limit>; leftover
  processes: none | <list> (killed) | unverified: <err>`, then
  `--- subprocess output ---` and the output (the goroutine dump).
- not hung, and `leftover` non-empty or a `cleanupErr` other than
  `errNoEnumeration`: `LEAK:<name>|<list>`, meaning processes carrying the
  test's marker were alive after the subprocess exited. They were killed.
- not hung, `!state.Success()`: `<name> failed in its subprocess (<state>):\n<output>`.
- not hung, success, no `--- PASS: <name> (` and no `--- SKIP: <name> (` in
  the output: `<name>: the subprocess ran no such test:\n<output>`. This
  fails closed on a `-test.run` that matched nothing, which would exit 0 with
  "no tests to run".

### 2. `goengines/internal/testmap/runner/watchdog_linux_test.go` (`//go:build linux`, new)

- Injectable readers, the watchdog's own (not the package's
  `readStat`/`getsid`, which are code under test):
  `wdReadEnviron, wdReadStat = func(pid int) ([]byte, error) { os.ReadFile("/proc/<pid>/environ"|"stat") }`.
- `markedProcs(entry string) (live []markedProc, uncertain []uncertainProc, err error)`
  with `markedProc{pid, pgid, sid int; comm string}` and `uncertainProc{pid int; reason string}`.
  It reads `/proc`, and for each numeric entry classifies **before** and
  **after** a marker match separately:
  - `environ` read error:
    - `ENOENT`/`ESRCH` → gone, skip.
    - `EACCES`/`EPERM` → **unrelated and inaccessible**: skip, never kill.
      Ownership cannot be established without the marker, so only another
      uid's process (or a setuid descendant, the documented residual) answers this.
    - any other errno → return `err`. Enumeration is **unverified** and never
      reads as clean.
  - `environ` read, no NUL-split item equal to `entry` → not ours, skip.
    This includes a zombie, whose environ reads empty because the process has
    exited.
  - **marker matched** (known-owned), then `stat`:
    - `ENOENT`/`ESRCH` → exited, skip.
    - **any other read error, or an unparsable line** (no `)`, fewer than 4
      fields, non-numeric pgrp/session) → `uncertain{pid, reason}`. It is
      retained, never dropped.
    - state `Z`/`X` → exited, skip.
    - else → `live` (state, pgrp and session parsed after the last `)`; comm
      between the first `(` and the last `)`).
- `reapMarked(entry string, bound time.Duration) ([]string, error)` loops:
  `markedProcs`. An `err` → return what was seen, plus
  `cleanup_unverified: <err>`. Record every live and uncertain pid seen
  (uncertain as `<pid>:?`). Neither list has members → return seen, `nil`.
  Past `bound` → return seen, plus `cleanup_unverified: still present after
  <bound>: <live pids>; uninspectable: <pid (reason)…>`. Otherwise `SIGKILL`
  each live pgid and pid, and each uncertain **pid only** (its group is
  unknown). It never signals its own pid or its own pgid
  (`syscall.Getpgrp()`), and never a pgid ≤ 1. Then it sleeps 10 ms.
  **An uncertain process leaves the result only by being observed gone**:
  `environ` or `stat` reads `ENOENT`/`ESRCH`, its environ stops carrying the
  marker, or `stat` reads `Z`. It never leaves because a read failed. The
  function returns everything it saw, so on a normal exit a non-empty list is
  the LEAK.
- `TestReapMarkedUncertainty`, an independent fault-injection control (not
  isolated: it starts only its own `sleep 300`s, all `Setsid`, killed and
  reaped in `t.Cleanup`). It uses a fresh marker per subtest, injects through
  `wdReadEnviron`/`wdReadStat` keyed on pid, and uses `reapMarked(entry, 200ms)`:
  - **stat unreadable, persists**: the target carries the marker. Inject
    `stat` → `EACCES`, and keep `environ` reporting the marker (as if alive).
    It must return a non-nil error naming the pid as uninspectable, with the
    pid in `seen`. Never `nil` and empty: that is exactly the false clean the
    old "skip read errors" design would produce, so this subtest is the red
    proof for the fix.
  - **malformed stat, persists**: inject `stat` → `"garbage"`. Same assertion.
  - **stat unreadable, then exits**: inject only `stat` → `EACCES`, with the
    real environ. `reapMarked` kills the pid, the zombie's environ stops
    matching, and the result is `nil` error, `seen` = {target}, and the target
    no longer live. Uncertainty resolves only on an observed exit.
  - **vanished**: inject `stat` → `ENOENT` for a marked live target. Treated
    as exited: `nil`, not in `seen`, not killed (still alive, which pins the
    `ENOENT` contract).
  - **unrelated inaccessible**: `other` really carries the marker. Inject
    `environ` → `EACCES`. Skipped: `nil`, `other` not in `seen` and still alive.
    Handled separately from known-owned uncertainty.
  - **unexpected environ error**: inject `environ` → `EIO` for one pid. It
    must return a `cleanup_unverified` error, never clean.
- `TestIsolationControls`, the watchdog's own negative controls. A guard that
  catches nothing proves nothing (the same idea as
  `TestInvariant5TripwireCatches`). It uses `controlEnv = "AIT_RUNNER_TEST_CONTROL"`
  with value `<mode>|<dir>`. When it is set, the function acts as the
  **fixture** inside the child. Otherwise it runs the subtests below. The
  process-shape ones call
  `runChild(t, "TestIsolationControls", …, childSettings{cpu: runtime.GOMAXPROCS(0)}, controlEnv+"="+mode+"|"+dir)`:
  - **hang** (limit 1 s). The fixture starts `sh -c 'sleep 300 & echo $! > bg.pid; echo $$ > leader.pid; exec sleep 300'`
    with `Setsid` (exactly the runner's escape shape). It waits for both pid
    files and writes `ready` = `shape ok` when the leader's session ≠ its own
    and bg's session = the leader's, checked with its own stat reader.
    Otherwise it writes the mismatch. Then it sleeps one hour. The parent
    asserts: `hung`; elapsed ≤ limit + quitGrace + 2 s; `ready == "shape ok"`;
    the output contains the SIGQUIT dump (`goroutine ` and the fixture
    function's name); both pids are **in `leftover`** and are no longer live;
    and `problems()[0]` starts with `HANG:TestIsolationControls|1s`. The shape
    check is the negative control: those processes were outside the child's
    session, so the session kill alone could not have removed them. The
    marker sweep did.
  - **leak**: the same spawn, then the fixture returns, so the test passes
    with the processes still alive. The parent asserts: not hung,
    `state.Success()`, `leftover` = {leader, bg}, both dead, and a `problems()`
    entry starting `LEAK:TestIsolationControls|`.
  - **fail**: the fixture calls `t.Fatal("control failure")`. The parent
    asserts: not hung, `!Success()`, the output contains `control failure`,
    and a problem `… failed in its subprocess`.
  - **ran nothing**: `runChild(t, "TestNoSuchTestExists", …)`. The parent
    asserts the "ran no such test" problem.
  - **settings: differential against the real `testing` matcher.** Two
    fixture modes share a body that records `t.Name()` of every subtest
    actually executed (`a`, `b`, `b/c`, where `c` is nested in `b`) and
    `runtime.GOMAXPROCS(0)` per pass, appending to files in `dir`:
    - `subtests` runs the body in-process.
    - `guarded` starts with `if !isolated(t, hangLimit) { return }` and then
      runs the same body.
    For each `(run, skip, cpu)` row, the control execs the test binary
    **directly** twice with the same flags: once with mode `subtests` (the
    real `testing` selection = baseline) and once with mode `guarded` (the
    outer process is a real parent: `parentSettings()` reads its live flags
    and `childRunPattern` rewrites them for the child). It asserts both
    recorded sets are equal **and** equal a pinned expectation, so a row that
    selects nothing cannot pass vacuously. Rows:
    | run | skip | cpu | expected ran |
    |---|---|---|---|
    | `^TestIsolationControls$` | `` | 1 | a, b, b/c (single level: all subtests) |
    | `^TestIsolationControls$/b` | `` | 1 | b, b/c (sibling `a` excluded) |
    | `^TestIsolationControls$/b/c` | `` | 1 | b, b/c |
    | `^TestIsolationControls$` | `TestIsolationControls/b/c` | 1 | a, b (`b/c` excluded by skip) |
    | `^TestIsolationControls$/a\|^TestIsolationControls$/b/c` | `` | 1 | a, b, b/c |
    | `^TestNoSuchTestExists$/x\|^TestIsolation(Controls)$/[b]` | `Controls/b/c` | 3 | b |
    | `^TestIsolationControls$/(a\|b)$` | `` | 1,3 | a, b, b/c (each pass) |

    (`\|` in the table is a literal `|`.) **Every row anchors its top level
    to the fixture test**: an empty or unanchored `-test.run` would make each
    direct launch run the whole package (13.8 s, twice per row). The control
    passes `-test.v=true` to every direct launch and **fails if any `=== RUN`
    line names a top-level test other than `TestIsolationControls`**. That is
    the demonstration that the launches exclude unrelated tests. The
    empty-pattern branch (`""` → `^name$`) and unanchored first elements
    (`Isolation.*`) are exercised in the pure `childRunPattern` table below,
    never through a launch. Each direct exec runs under
    `exec.CommandContext` with a 60 s bound, in `t.TempDir()`.
    The recorded GOMAXPROCS per pass must equal the row's cpu list (`[1]`,
    `[3]`, `[1 3]`) in **both** modes. The box default is 24, so neither value
    is the default leaking through. The `1,3` row also proves each pass
    spawns its own child at that pass's value and that `count=1` does not
    multiply passes.
  - **settings: `childRunPattern` table** (pure, no launch): the rows above;
    the **empty pattern** (`""` → `^name$`); unanchored and regex first
    elements (`Isolation.*/[b]`, `Controls`, which matches `TestIsolationControls`
    unanchored); bracket, paren and escape edges (`T/[/]`, `T/(x/y)`,
    `T/a\/b`, an empty sub-element `T/`); a space-rewrite element; and the
    no-alternative-matches error.

### 3. `goengines/internal/testmap/runner/watchdog_other_test.go` (`//go:build unix && !linux`, new)

`var errNoEnumeration = errors.New(...)` (declared in the unix file so
`problems()` can compare with it), plus `reapMarked` returning
`nil, errNoEnumeration`. A hang still fails fast with `HANG:`, and the message
says leftover cleanup is **unverified** rather than claiming "none". This
mirrors `proc_other.go`'s never-claim-what-you-cannot-observe rule. On a
normal exit the sentinel is not a LEAK. darwin gets fail-fast but no leftover
guarantee. Its timing tests already need GNU `timeout`/`sed -i`.

### 4. Guard every process-starting test: one line at the top of each

`if !isolated(t, hangLimit) { return }`. The set is every `Test*` that starts
a process directly or through `Run`/`runAll`/`timedRun`/`Load`/`registry.Scan`/
`registry.Check`/`execRunner`/`sweepSession`/`startSession`/`exec.Command`
(lexical survey, to be re-confirmed per function while editing):
- `timeout_run_test.go`: all 6 `TestTimeout*`.
- `cleanup_linux_test.go`: `TestCleanupSeparateTestGroupOnInvocationTimeout`,
  `TestCleanupAfterNormalExit`, `TestCleanupEveryKillPath`,
  `TestSweepEnumeration`, `TestSweepUninspectableProcesses`.
- `run_test.go`: all 13 (`TestRunPassFail` … `TestRunReportFilesAreSafe`).
- `repo_test.go`: `TestOwnership`, `TestOwnershipRefusals`,
  `TestShadowByNameAndBuiltins`, `TestDescribeOverrideValidated`,
  `TestUnitAttributes`. Re-check `TestConfigRefusals` and
  `TestLoadConfigAbsentAndContract` (classified pure).
- `provenance_test.go`: all 3.
- `list_test.go`: `TestListMalformedThroughScan`.
- **Not guarded** (pure, verified by reading): `TestTimeoutDeadline`,
  `TestGroupingDeterministic`, `TestOutcomeTable`, and the describe, list and
  grouping parsers.

`timedRun`'s 10 s post-hoc bound and `TestRunReportFilesAreSafe`'s in-loop
check stay. They catch "slow but returned", a different failure from a hang.
After editing, cross-check with a grep: every `func Test` without
`isolated(` must be one of the pure ones listed above.

### 5. Step 9 (Post-Implementation)
Current-branch profile (fast): no worktree or branch merge. Commit the code
(`test: … (t1985)`) and the plan separately, then archive via
`aitask_archive.sh 1985` (gate `risk_evaluated` recorded by the orchestrator).

### Post-phase (risk mitigations)

Runs after Verification 1–4 pass, before the Step 8 review.

1. [stress_isolation_suite] Stress the watchdog under load. In one shell, run
   `cd goengines && go test ./internal/testmap/runner/ -count=10 -timeout 30m 2>&1 | tee <scratchpad>/stress.log; echo "rc=${PIPESTATUS[0]}"`.
   Concurrently, in a second background shell, loop `ait engine test` over the
   same period. Require `rc=0`, and zero lines matching `HANG:|LEAK:|FAIL` in
   `stress.log`. Afterwards, `grep -l AIT_RUNNER_TEST_ISOLATE= /proc/*/environ`
   must list nothing. Record the command, the per-run package times and the
   grep result in Final Implementation Notes. If anything flakes, fix the root
   cause (e.g. widen a control bound) and re-run. Do not retry until green.

## Verification

1. `cd goengines && go vet ./... && go test ./internal/testmap/runner/ -count=1 -v`:
   every guarded test PASSes; `TestIsolationControls` passes (hang, leak,
   fail, ran-nothing, the settings differential and the `childRunPattern`
   table); `TestReapMarkedUncertainty` passes all six subtests; there are no
   `HANG:`/`LEAK:` lines. `ait engine test` is green.
   **The concern-2 scenarios through the real test**:
   `go test ./internal/testmap/runner/ -run 'TestSweepUninspectableProcesses/member' -v`
   relays a child that ran **only** `member`.
   `-run TestSweepUninspectableProcesses -skip 'TestSweepUninspectableProcesses/unrelated' -v`
   relays a child without `unrelated`.
2. **Wall time.** Before (measured): package 13.8 s. After: report the
   package and `ait engine test` times. Expected about +1.5–2 s: the 1 s hang
   control; 14 direct launches for the settings differential (7 rows × 2
   modes). Each launch runs **only** `TestIsolationControls`, which the
   control enforces, so each costs a few ms plus one child for `guarded`.
   Then about 33 × (3 ms re-exec + ~7 ms `/proc` scan). If the measured
   increase is materially above this, find which control costs it before
   proceeding.
3. **Coverage pass-through.** `go test -cover ./internal/testmap/runner/`
   before and after. If isolated bodies' coverage is not merged, drop the
   `gocoverdir` forwarding and record that coverage of isolated bodies is not
   collected.
4. **Red proofs.** Mutants go in a scratch copy of `goengines/` under the
   scratchpad, never in the shared tree, and are run with `go test -timeout 30m`.
   After each run, `grep -l AIT_RUNNER_TEST_ISOLATE= /proc/*/environ` must
   list nothing: no marked process survives.
   - M1 `readReport` → `os.ReadFile` (the FIFO blocks): `HANG:TestRunReportFilesAreSafe|20s`
     within ~22 s, and the dump shows the blocked read. **Pre-fix control:**
     the same mutant on a HEAD copy with `-timeout 60s` ends in
     `panic: test timed out`, not a HANG.
   - M2 drop `cmd.WaitDelay = drainDelay`: `TestCleanupAfterNormalExit` HANGs
     (leaked `sleep 300`s hold the pipes), and both sleeps are killed by the
     marker sweep.
   - M3 `sweepSession` never returns and kills nothing (sleeps forever at its
     top): **every** guarded test reports `HANG:` within its bound. Run each
     test as its own binary invocation with an **anchored**
     `-test.run=^<Name>$`, in parallel (`xargs -P`), to keep wall time near
     2 min.
   - M4 the deadline is lost (`WithTimeout` → `WithCancel` in `execRunner`):
     the kill-path tests (`TestTimeoutInvocationMax`, `…BatchBounded`,
     `…NoneSingletons`, `TestKilledRunValidatesRows`, `TestCleanupEveryKillPath`,
     `TestCleanupSeparate…`) HANG at 20 s instead of passing after `sleep 30`.
   - M5 (concern 1): change `markedProcs` back to skipping a matched pid's
     non-`ENOENT` stat error or an unparsable stat. The **stat unreadable,
     persists** and **malformed stat, persists** subtests of
     `TestReapMarkedUncertainty` must fail (`reapMarked` returns `nil` and
     empty), and the other four must still pass.
   - M6 (concern 2): change `childRunPattern` back to `^name$`, and
     separately drop the `-test.cpu` forwarding. The settings-differential
     rows with sub-levels or skips, and the cpu-list assertions, must fail on
     the matching mutant.
   Record each mutant's diff, command and output verbatim in Final
   Implementation Notes. That is closure evidence.

## Risk

### Code-health risk: medium
- The execution model of ~33 tests changes: each body runs in a re-executed child, so a debugger, `-v` output (relayed via `t.Log`) and `-cover` (forwarded `gocoverdir`, unverified) behave differently. Test-only, no production code touched · severity: medium · → mitigation: none (addressed in design: debug recipe in the file comment, coverage pass-through checked in Verification 3)
- A watchdog defect (a false `LEAK:` from a stray marked process such as a detached git maintenance job, a misread "ran no such test", a timing-sensitive control) could make the whole runner suite flaky or red. Covered by `TestIsolationControls`, but flakiness under load is not proven by one green run · severity: low (residual — addressed by inline post-phase stress_isolation_suite) · → mitigation: inline post-phase stress_isolation_suite
- The marker sweep sends SIGKILL by environment match. It is bounded to an exact per-launch token and never signals its own pid or pgid, but it is a new kill path in test code. An inaccessible-environ process is never killed (ownership unprovable) · severity: low · → mitigation: none (guards in design; `unrelated inaccessible` subtest)
- `childRunPattern` ports `testing.splitRegexp`/`rewrite` (Go 1.27). A future Go change to the `-run` grammar could make the child select differently from the parent. The settings differential runs against whatever `testing` builds the suite, so drift fails a test instead of passing silently, and no-match fails closed · severity: low · → mitigation: none (differential control in design)

### Goal-achievement risk: low
- New process-starting tests added later can omit the guard, silently reopening the suite-timeout hang for them. "Every process-starting test" holds only for today's tests · severity: medium · → mitigation: isolation_tripwire
- The no-leftover guarantee is Linux-only. On other unix the HANG still fails fast but the cleanup is reported unverified. Residual: a process that clears its env or execs setuid escapes the marker scan; no fixture does either · severity: low · → mitigation: none (accepted residual, documented in the file comment)
- The wall-time increase (~1.5 s expected, mostly the 1 s hang control) must stay "not material" · severity: low · → mitigation: none (measured in Verification 2)

### Planned mitigations
- timing: post-phase | name: stress_isolation_suite | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — watchdog flakiness under load (false LEAK/HANG) | desc: run the runner package -count=10 under concurrent ait engine test load; require zero HANG/LEAK/FAIL and no surviving marked process
- timing: after | name: isolation_tripwire | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: goal-achievement — future process-starting runner tests omitting the isolated() guard | desc: go/ast tripwire test failing when a runner Test* transitively reaches a process-starting call without starting with `if !isolated(t, hangLimit) { return }`, with its own negative control

## Post-Review Changes

### Change Request 1 (2026-10-14 19:45)
- **Requested by user:** three review findings, each to be verified first.
  (1, blocking) `markedProcs` returned at once on an unexpected environ read
  error, so `reapMarked` returned `cleanup_unverified` before killing a
  readable marked process. (2, blocking) EACCES/EPERM environ reads were
  skipped even for a pid whose marker had matched in an earlier scan, so lost
  access read as a verified cleanup. (3, follow-up) `runChild` reads the whole
  subprocess log into memory before applying `outputCap`.
- **Verified:** all three confirmed in source.
  (1) the early `return` at the default case and the immediate return in `reapMarked`.
  (2) `labels` recorded sightings but was never consulted before the
  empty-scan success return. (3) the `os.ReadFile` of the whole output.
- **Changes made:**
  - `markedProcs` is replaced by `scanMarked`, which returns the matched pids
    plus a list of unreadable-environment failures and never aborts.
  - `reapMarked` now tracks **owned** processes by identity (pid +
    stat `starttime`, field 22) from the scan in which the marker first
    matches. Only an observed exit releases one: stat or `/proc/<pid>` reads
    ENOENT/ESRCH, a zombie, or a changed `starttime` (pid reused; never
    signalled). Lost environ access or a vanished marker no longer releases it.
  - An uninspectable owned pid is killed by pid only when its marker matched
    in the same scan.
  - A round is clean only with no live owned, no uncertain owned, **and no
    unreadable environment**. The error lists both "still present" and "scan incomplete".
  - `parseWdStat` reads `starttime` (requires ≥20 fields).
  - New controls in `TestReapMarkedUncertainty`:
    - "unexpected environ error" now also asserts that the readable marked target was reaped;
    - "environ lost after a match, survives" (error, never clean);
    - "environ lost after a match, then exits" (clean on real exit);
    - "pid reused" (only the first round's kills, none after the starttime changes).
  - `swallowKills` helper.
  - (3) followed its disposition: follow-up task **t1993**
    (`watchdog_bounded_output_read`).
- **Files affected:** `goengines/internal/testmap/runner/watchdog_linux_test.go`.

### Change Request 2 (2026-10-14 22:30)
- **Requested by user:** (blocking) `lostAccess` and the pid-reused control let
  only their first environ read see the real process, and the fixture's
  `start` did not establish that the marker was visible first. The reviewer
  reproduced 4 failures in 200 repetitions; a readiness check fixed them.
- **Verified:** confirmed, and the root cause is wider than the fixture.
  A probe (`exec.Command("sleep").Start()`, then an immediate read of
  `/proc/<pid>/environ`) found the environment **empty (0 bytes, no error) in
  1958 of 2000 trials**. `Start` returns once the child is past execve's switch
  to the new image, before the kernel sets up that image's environment. The
  window is p50 44 µs, p99 116 µs, max 263 µs (unloaded). One full `/proc`
  scan takes about 6.7 ms. The same window lets the **reaper itself** miss a
  marked process caught mid-execve during its final scan (e.g. the child of a
  double-forking parent that has exited) and report a false clean.
  - Not reproduced on this box, though. 3×300 parallel runs of the reviewer's
    command passed both before and after the fix. `/proc` is iterated in
    ascending pid order and new pids are high here, so the scan reaches the
    target about 6 ms after its start, past the window. On a box where pids
    have wrapped, the scan reaches a new low pid at once.
- **Changes made:**
  - `start()` in `TestReapMarkedUncertainty` now waits, through the real
    reader, until the marker is visible (bounded at 5 s and registered after
    the cleanup), so every injection is installed after the precondition holds.
  - `reapMarked` returns clean only after **two consecutive empty scans**,
    `confirmDelay` (2 ms) apart.
  - New control "environ not yet set up": the first environ read is empty, as
    for a process inside execve. The reap must still find and kill the target.
    The red proof is M10: with no confirming scan, it fails.
- **Files affected:** `goengines/internal/testmap/runner/watchdog_linux_test.go`.

## Final Implementation Notes
- **Actual work done:** three new test files in `goengines/internal/testmap/runner/`,
  plus the guard `if !isolated(t, hangLimit) { return }` at the top of the 33
  process-starting tests. No production code changed.
  - `watchdog_unix_test.go`:
    - `isolated` / `runChild` re-exec one top-level test in its own session
      under a 20 s limit; past it, SIGQUIT (goroutine dump), then SIGKILL of
      the group, then `HANG:<test>|<limit>`. A marked process alive after a
      normal exit is a `LEAK:`. A non-zero exit, or a subprocess that ran no
      such test, is reported as a failure.
    - `childSettings`: the child gets the parent's `-run` rewritten by
      `childRunPattern` (a faithful port of `testing.splitRegexp`/`rewrite`,
      top level pinned), `-skip` verbatim, the effective
      `runtime.GOMAXPROCS(0)` as `-cpu`, `count=1`,
      short/failfast/fullpath/parallel, and `gocoverdir`. Profile, trace and
      test-log flags are deliberately not forwarded.
    - `TestChildRunPattern`.
  - `watchdog_linux_test.go`:
    - `scanMarked` + `reapMarked`: env-marker cleanup with identity-based
      ownership (pid + starttime). One scan never aborts on one unreadable
      environment. A clean result needs two consecutive empty scans.
    - `TestIsolationControls`: hang, leak, fail, ran-nothing, and the settings
      differential against the real `testing` matcher.
    - `TestReapMarkedUncertainty`: 11 fault-injection subtests.
  - `watchdog_other_test.go`: non-Linux; a hang fails fast, and cleanup is
    reported unverified.
- **Deviations from plan:**
  - (a) A third seam, `wdKill`. Without it, the "persists" controls' real
    SIGKILL ended the process, so `/proc` stopped listing it and the
    uncertainty resolved by itself.
  - (b) `TestChildRunPattern` is a separate pure test, not a subtest.
  - (c) The hang control's limit was trimmed to 500 ms and the reap bound to
    100 ms, for wall time; the stress run validated both.
  - (d) M5 kills three subtests, not two: "stat unreadable then exits" also
    fails, because with the mutation `seen` is empty.
  - (e) Review rounds (see Post-Review Changes 1 and 2) replaced
    `markedProcs` with `scanMarked`, added identity tracking, the
    non-aborting scan, the confirmation scan and fixture readiness.
  - (f) Review finding 3 (bounded output read) became follow-up **t1993**,
    per its disposition.
  - (g) Wall time is +2.1–2.2 s per package run, against the ~1.5–2 s
    estimate (see below).
- **Issues encountered:**
  - The first stress run's load loop was served `(cached)` (0–1 s per run),
    so it was re-run with `ait engine test -count=1`.
  - The first M10 mutant did not compile (`declared and not used: quiet`).
    It was re-run as `if quiet || true`.
  - `TestBuiltBinary` (cmd package) fails in a `git archive` scratch copy at
    HEAD as well. It needs VCS stamping, so it is an environment artifact;
    green in the real tree, where `ait engine test` passed 30× during stress.
  - The reviewer's 4-in-200 fixture flake did not reproduce locally (3×300
    parallel runs, before and after). `/proc` is iterated in ascending pid
    order and new pids are high here, so the scan reaches a fresh target
    about 6 ms after its start, past the execve window. The mechanism was
    proven by the probe below.
- **Key decisions:**
  - Cleanup by env marker, not by session: `execRunner` Setsids every runner,
    so a session or tree kill misses them and their orphans.
  - The watchdog never calls `sweepSession`/`sessionProcs`/`parseStat`
    (code under test).
  - `hangLimit` 20 s, under the fixtures' `sleep 30`, so a lost deadline
    reads as a hang.
  - Inaccessible environments are never killed (ownership unprovable).
  - Uncertainty about an owned pid leaves the result only on an observed exit.
  - `gocoverdir` is forwarded: coverage stays 88.0%, with identical
    `readReport`/`sweepSession`/`execRunner` numbers versus HEAD.
- **Upstream defects identified:** None
- **Measurements:**
  - Package wall, interleaved runs: HEAD 14.15 s / 14.05 s, final 16.35 s /
    16.14 s (load average ~4.5). The cost breaks down as: controls about
    1.4 s, plus 33 × (re-exec ~3 ms + two `/proc` scans of ~7 ms + 2 ms).
  - Execve environment window (probe below): the marker is missing right
    after `Start` in 1958/2000 trials; it lasts p50 43.8 µs, p99 116.4 µs,
    max 262.7 µs; one `/proc` scan of 764 entries takes 6.65 ms.
- **Residuals (documented in the file comment):**
  - A process that clears its environment *before* its first sighting, or
    execs setuid, escapes the marker scan.
  - Non-Linux: no leftover guarantee.
  - A process held inside execve across both confirming scans (~9 ms apart)
    could be missed.
- **Mitigations:**
  - `stress_isolation_suite` (inline post-phase) ran on the final code: green.
  - `isolation_tripwire` is created at Step 8d.

### Closure evidence (verbatim)

**Red-proof driver** (`<scratchpad>/red_proofs.sh`, verbatim):

````bash
#!/usr/bin/env bash
# t1985 red proofs: each mutant runs in its own scratch copy of goengines/
# (never the shared tree). After every run, no process may still carry an
# isolation marker.
set -u
S=/tmp/claude-1000/-home-ddt-Work-aitasks/767706b9-6b7d-44d7-8f36-b354de4c51df/scratchpad
SRC=$S/mut/goengines     # the working tree's goengines, with the watchdog
HEAD=$S/head/goengines   # git archive HEAD goengines (no watchdog)
OUT=$S/proofs
rm -rf "$OUT"; mkdir -p "$OUT"

# mutate <copy-dir> <file> <python-replacement-pairs...>: exact, asserted
mutate() {
	local dir=$1 file=$2; shift 2
	python3 - "$dir/internal/testmap/runner/$file" "$@" <<'EOF'
import sys
p, pairs = sys.argv[1], sys.argv[2:]
s = open(p).read()
for a, b in zip(pairs[::2], pairs[1::2]):
    a, b = a.encode().decode('unicode_escape'), b.encode().decode('unicode_escape')
    assert s.count(a) == 1, f"mutation anchor not found exactly once in {p}: {a!r}"
    s = s.replace(a, b)
open(p, 'w').write(s)
print("MUTATED", p)
EOF
}
fresh() { rm -rf "$S/m_$1"; mkdir -p "$S/m_$1"; cp -a "${2:-$SRC}" "$S/m_$1/"; echo "$S/m_$1/goengines"; }
markers() {
	local found
	found=$(grep -a -o 'AIT_RUNNER_TEST_ISOLATE=[^[:cntrl:]]*' /proc/[0-9]*/environ 2>/dev/null | sort -u)
	echo "MARKED_SURVIVORS: ${found:-none}"
}
run() { # run <name> <dir> <go test args...>
	local name=$1 dir=$2; shift 2
	local s e rc
	s=$(date +%s)
	(cd "$dir" && go test ./internal/testmap/runner/ -count=1 "$@") > "$OUT/$name.log" 2>&1; rc=$?
	e=$(date +%s)
	{ echo "rc=$rc wall=$((e - s))s"; markers; } >> "$OUT/$name.log"
	echo "== $name: rc=$rc wall=$((e - s))s"
}

READREPORT_A='	f, err := os.OpenFile(path, os.O_RDONLY|syscall.O_NONBLOCK|syscall.O_NOFOLLOW, 0)\n	if errors.Is(err, fs.ErrNotExist) {'
READREPORT_B='	if d, err := os.ReadFile(path); !errors.Is(err, fs.ErrNotExist) {\n		return d, false, err // M1: a plain read blocks on a FIFO\n	}\n	f, err := os.OpenFile(path, os.O_RDONLY|syscall.O_NONBLOCK|syscall.O_NOFOLLOW, 0)\n	if errors.Is(err, fs.ErrNotExist) {'

# M1: readReport back to a plain read (a FIFO blocks the open).
d=$(fresh m1); mutate "$d" report_unix.go "$READREPORT_A" "$READREPORT_B"
run m1 "$d" -run '^TestRunReportFilesAreSafe$' -timeout 30m
# M1 pre-fix control: the same mutant without the watchdog.
d=$(fresh m1_prefix "$HEAD"); mutate "$d" report_unix.go "$READREPORT_A" "$READREPORT_B"
run m1_prefix "$d" -run '^TestRunReportFilesAreSafe$' -timeout 60s

# M2: WaitDelay lost from execRunner.
d=$(fresh m2); mutate "$d" exec_unix.go '	cmd.WaitDelay = drainDelay\n' '	// M2: cmd.WaitDelay = drainDelay\n'
run m2 "$d" -timeout 30m

# M4: the deadline is lost.
d=$(fresh m4); mutate "$d" exec_unix.go '	dctx, cancel := context.WithTimeout(ctx, deadline)\n' '	dctx, cancel := context.WithCancel(ctx) // M4: deadline lost\n'
run m4 "$d" -timeout 30m

# M5: an owned pid's uninspectable or unparsable stat taken as an exit.
d=$(fresh m5)
mutate "$d" watchdog_linux_test.go \
	'				uncertain = append(uncertain, uncertainProc{pid, "stat: " + err.Error(), matched[pid]})\n				continue' '				delete(owned, pid) // M5\n				continue' \
	'			case !ok:\n				uncertain = append(uncertain, uncertainProc{pid, fmt.Sprintf("unparsable stat %.64q", st), matched[pid]})' '			case !ok:\n				delete(owned, pid) // M5'
run m5 "$d" -run '^TestReapMarkedUncertainty$' -v -timeout 10m

# M7: an unreadable environment aborts the round before any kill.
d=$(fresh m7)
mutate "$d" watchdog_linux_test.go '		matched, unreadable := scanMarked(entry)\n' '		matched, unreadable := scanMarked(entry)\n		if len(unreadable) > 0 {\n			return seen(), errors.New("cleanup_unverified: " + unreadable[0]) // M7\n		}\n'
run m7 "$d" -run '^TestReapMarkedUncertainty$' -v -timeout 10m

# M8: ownership only by the current scan's marker match.
d=$(fresh m8)
mutate "$d" watchdog_linux_test.go '		for pid := range matched {\n			if owned[pid] == nil {' '		for pid := range owned {\n			if !matched[pid] {\n				delete(owned, pid) // M8\n			}\n		}\n		for pid := range matched {\n			if owned[pid] == nil {'
run m8 "$d" -run '^TestReapMarkedUncertainty$' -v -timeout 10m

# M9: a different start time under the same pid no longer read as an exit.
d=$(fresh m9)
mutate "$d" watchdog_linux_test.go '			case id.known && p.start != id.start, state == "Z", state == "X":' '			case state == "Z", state == "X": // M9'
run m9 "$d" -run '^TestReapMarkedUncertainty$' -v -timeout 10m

# M10: one empty scan taken as clean (no confirming scan).
d=$(fresh m10)
mutate "$d" watchdog_linux_test.go '			if quiet {\n' '			if quiet || true { // M10\n'
run m10 "$d" -run '^TestReapMarkedUncertainty$' -v -timeout 10m

# M6a: the child's -test.run back to ^name$.
d=$(fresh m6a); mutate "$d" watchdog_unix_test.go '	run, err := childRunPattern(name, s.run)\n' '	run, err := "^"+regexp.QuoteMeta(name)+"$", error(nil) // M6a\n'
run m6a "$d" -run '^(TestIsolationControls|TestChildRunPattern)$' -v -timeout 10m
# M6b: the effective GOMAXPROCS no longer forwarded.
d=$(fresh m6b); mutate "$d" watchdog_unix_test.go '	if s.cpu > 0 {\n' '	if false && s.cpu > 0 { // M6b\n'
run m6b "$d" -run '^TestIsolationControls$' -v -timeout 10m
# M6c: -test.skip no longer forwarded.
d=$(fresh m6c); mutate "$d" watchdog_unix_test.go '	if s.skip != "" {\n' '	if false && s.skip != "" { // M6c\n'
run m6c "$d" -run '^TestIsolationControls$' -v -timeout 10m

# M3: sweepSession never returns and kills nothing — every guarded test,
# each as its own anchored invocation, 12 at a time.
d=$(fresh m3); mutate "$d" exec_unix.go 'func sweepSession(sid int) error {\n' 'func sweepSession(sid int) error {\n	for {\n		time.Sleep(time.Hour) // M3: never returns, kills nothing\n	}\n'
(cd "$d" && go test -c -o "$OUT/m3.test" ./internal/testmap/runner/) || echo "M3 build failed"
names=$(cd "$d/internal/testmap/runner" && awk '/^func Test/{n=$2; sub(/\(.*/,"",n); getline l; if (l ~ /isolated\(t, hangLimit\)/) print n}' *_test.go)
mkdir -p "$OUT/m3"
s=$(date +%s)
printf '%s\n' $names | xargs -P 12 -I{} sh -c 'cd "$1/internal/testmap/runner" && b=$(date +%s); "$2/m3.test" -test.run "^$3\$" -test.count=1 -test.timeout=10m > "$2/m3/$3.log" 2>&1; echo "rc=$? wall=$(( $(date +%s) - b ))s" >> "$2/m3/$3.log"' _ "$d" "$OUT" {}
e=$(date +%s)
{ echo "M3 total wall=$((e - s))s over $(printf '%s\n' $names | wc -l) tests"; markers; } > "$OUT/m3_summary.log"
cat "$OUT/m3_summary.log"
echo ALL_DONE
````

**Driver stdout, final run** (`<scratchpad>/red_proofs3.out`, verbatim):

````
MUTATED /tmp/claude-1000/-home-ddt-Work-aitasks/767706b9-6b7d-44d7-8f36-b354de4c51df/scratchpad/m_m1/goengines/internal/testmap/runner/report_unix.go
== m1: rc=1 wall=20s
MUTATED /tmp/claude-1000/-home-ddt-Work-aitasks/767706b9-6b7d-44d7-8f36-b354de4c51df/scratchpad/m_m1_prefix/goengines/internal/testmap/runner/report_unix.go
== m1_prefix: rc=1 wall=61s
MUTATED /tmp/claude-1000/-home-ddt-Work-aitasks/767706b9-6b7d-44d7-8f36-b354de4c51df/scratchpad/m_m2/goengines/internal/testmap/runner/exec_unix.go
== m2: rc=1 wall=70s
MUTATED /tmp/claude-1000/-home-ddt-Work-aitasks/767706b9-6b7d-44d7-8f36-b354de4c51df/scratchpad/m_m4/goengines/internal/testmap/runner/exec_unix.go
== m4: rc=1 wall=126s
MUTATED /tmp/claude-1000/-home-ddt-Work-aitasks/767706b9-6b7d-44d7-8f36-b354de4c51df/scratchpad/m_m5/goengines/internal/testmap/runner/watchdog_linux_test.go
== m5: rc=1 wall=0s
MUTATED /tmp/claude-1000/-home-ddt-Work-aitasks/767706b9-6b7d-44d7-8f36-b354de4c51df/scratchpad/m_m7/goengines/internal/testmap/runner/watchdog_linux_test.go
== m7: rc=1 wall=1s
MUTATED /tmp/claude-1000/-home-ddt-Work-aitasks/767706b9-6b7d-44d7-8f36-b354de4c51df/scratchpad/m_m8/goengines/internal/testmap/runner/watchdog_linux_test.go
== m8: rc=1 wall=1s
MUTATED /tmp/claude-1000/-home-ddt-Work-aitasks/767706b9-6b7d-44d7-8f36-b354de4c51df/scratchpad/m_m9/goengines/internal/testmap/runner/watchdog_linux_test.go
== m9: rc=1 wall=6s
MUTATED /tmp/claude-1000/-home-ddt-Work-aitasks/767706b9-6b7d-44d7-8f36-b354de4c51df/scratchpad/m_m10/goengines/internal/testmap/runner/watchdog_linux_test.go
== m10: rc=1 wall=0s
MUTATED /tmp/claude-1000/-home-ddt-Work-aitasks/767706b9-6b7d-44d7-8f36-b354de4c51df/scratchpad/m_m6a/goengines/internal/testmap/runner/watchdog_unix_test.go
== m6a: rc=1 wall=2s
MUTATED /tmp/claude-1000/-home-ddt-Work-aitasks/767706b9-6b7d-44d7-8f36-b354de4c51df/scratchpad/m_m6b/goengines/internal/testmap/runner/watchdog_unix_test.go
== m6b: rc=1 wall=1s
MUTATED /tmp/claude-1000/-home-ddt-Work-aitasks/767706b9-6b7d-44d7-8f36-b354de4c51df/scratchpad/m_m6c/goengines/internal/testmap/runner/watchdog_unix_test.go
== m6c: rc=1 wall=1s
MUTATED /tmp/claude-1000/-home-ddt-Work-aitasks/767706b9-6b7d-44d7-8f36-b354de4c51df/scratchpad/m_m3/goengines/internal/testmap/runner/exec_unix.go
M3 total wall=60s over 33 tests
MARKED_SURVIVORS: none
ALL_DONE
````

**M1 readReport → os.ReadFile: result lines extracted from the run log** (`<scratchpad>/sum_m1.txt`, verbatim):

````
--- FAIL: TestRunReportFilesAreSafe (20.04s)
    run_test.go:384: HANG:TestRunReportFilesAreSafe|20s
        killed after 20s; leftover processes: none
MARKED_SURVIVORS: none
````

**M1 pre-fix control (HEAD, no watchdog, -timeout 60s): result lines extracted from the run log** (`<scratchpad>/sum_m1_prefix.txt`, verbatim):

````
panic: test timed out after 1m0s
	running tests:
		TestRunReportFilesAreSafe (1m0s)
rc=1 wall=61s
MARKED_SURVIVORS: none
````

**M2 WaitDelay dropped: result lines extracted from the run log** (`<scratchpad>/sum_m2.txt`, verbatim):

````
--- FAIL: TestCleanupSeparateTestGroupOnInvocationTimeout (20.06s)
    cleanup_linux_test.go:56: HANG:TestCleanupSeparateTestGroupOnInvocationTimeout|20s
        killed after 20s; leftover processes: 3748305:sleep,3748306:sleep (killed)
--- FAIL: TestCleanupAfterNormalExit (20.06s)
    cleanup_linux_test.go:107: HANG:TestCleanupAfterNormalExit|20s
        killed after 20s; leftover processes: 3761247:sleep,3761248:sleep (killed)
--- FAIL: TestCleanupEveryKillPath (20.06s)
    cleanup_linux_test.go:130: HANG:TestCleanupEveryKillPath|20s
        killed after 20s; leftover processes: 3765605:sleep (killed)
MARKED_SURVIVORS: none
````

**M4 deadline lost: result lines extracted from the run log** (`<scratchpad>/sum_m4.txt`, verbatim):

````
--- FAIL: TestCleanupSeparateTestGroupOnInvocationTimeout (20.06s)
    cleanup_linux_test.go:56: HANG:TestCleanupSeparateTestGroupOnInvocationTimeout|20s
        killed after 20s; leftover processes: 3772659:bash,3772662:sleep,3772663:sleep (killed)
--- FAIL: TestCleanupEveryKillPath (20.06s)
    cleanup_linux_test.go:130: HANG:TestCleanupEveryKillPath|20s
        killed after 20s; leftover processes: 3776370:sleep,3776373:sleep (killed)
--- FAIL: TestKilledRunValidatesRows (20.06s)
    run_test.go:116: HANG:TestKilledRunValidatesRows|20s
        killed after 20s; leftover processes: 3780760:sleep (killed)
--- FAIL: TestTimeoutInvocationMax (20.04s)
    timeout_run_test.go:72: HANG:TestTimeoutInvocationMax|20s
        killed after 20s; leftover processes: 3785257:sleep (killed)
--- FAIL: TestTimeoutBatchBounded (20.04s)
    timeout_run_test.go:89: HANG:TestTimeoutBatchBounded|20s
        killed after 20s; leftover processes: 3788625:sleep (killed)
--- FAIL: TestTimeoutNoneSingletons (20.06s)
    timeout_run_test.go:109: HANG:TestTimeoutNoneSingletons|20s
        killed after 20s; leftover processes: 3816602:sleep (killed)
MARKED_SURVIVORS: none
````

**M5 uninspectable stat taken as exit: result lines extracted from the run log** (`<scratchpad>/sum_m5.txt`, verbatim):

````
    watchdog_linux_test.go:617: reap: <nil> (seen []): an uninspectable marked process read as clean
    watchdog_linux_test.go:617: reap: <nil> (seen []): an uninspectable marked process read as clean
    watchdog_linux_test.go:630: reap: <nil>, seen [], alive true
    --- FAIL: TestReapMarkedUncertainty/stat_unreadable_persists (0.02s)
    --- FAIL: TestReapMarkedUncertainty/malformed_stat_persists (0.02s)
    --- FAIL: TestReapMarkedUncertainty/stat_unreadable_then_exits (0.02s)
    --- PASS: TestReapMarkedUncertainty/vanished (0.02s)
    --- PASS: TestReapMarkedUncertainty/unrelated_inaccessible (0.03s)
    --- PASS: TestReapMarkedUncertainty/unexpected_environ_error (0.10s)
    --- PASS: TestReapMarkedUncertainty/environ_lost_after_a_match,_survives (0.10s)
    --- PASS: TestReapMarkedUncertainty/environ_lost_after_a_match,_then_exits (0.03s)
    --- PASS: TestReapMarkedUncertainty/environ_not_yet_set_up (0.04s)
    --- PASS: TestReapMarkedUncertainty/pid_reused (0.03s)
rc=1 wall=0s
MARKED_SURVIVORS: none
````

**M7 unreadable environ aborts the round: result lines extracted from the run log** (`<scratchpad>/sum_m7.txt`, verbatim):

````
    watchdog_linux_test.go:664: reap: cleanup_unverified: pid 3829171: environ: open /proc/3829171/environ: input/output error, seen []: an unreadable environment read as clean
    --- PASS: TestReapMarkedUncertainty/stat_unreadable_persists (0.12s)
    --- PASS: TestReapMarkedUncertainty/malformed_stat_persists (0.11s)
    --- PASS: TestReapMarkedUncertainty/stat_unreadable_then_exits (0.04s)
    --- PASS: TestReapMarkedUncertainty/vanished (0.02s)
    --- PASS: TestReapMarkedUncertainty/unrelated_inaccessible (0.04s)
    --- FAIL: TestReapMarkedUncertainty/unexpected_environ_error (0.01s)
    --- PASS: TestReapMarkedUncertainty/environ_lost_after_a_match,_survives (0.11s)
    --- PASS: TestReapMarkedUncertainty/environ_lost_after_a_match,_then_exits (0.03s)
    --- PASS: TestReapMarkedUncertainty/environ_not_yet_set_up (0.04s)
    --- PASS: TestReapMarkedUncertainty/pid_reused (0.04s)
rc=1 wall=1s
MARKED_SURVIVORS: none
````

**M8 ownership only by the current scan: result lines extracted from the run log** (`<scratchpad>/sum_m8.txt`, verbatim):

````
    watchdog_linux_test.go:691: reap: <nil> (seen [3829542:sleep]): an owned process read as gone once its environment became unreadable
    --- PASS: TestReapMarkedUncertainty/stat_unreadable_persists (0.12s)
    --- PASS: TestReapMarkedUncertainty/malformed_stat_persists (0.10s)
    --- PASS: TestReapMarkedUncertainty/stat_unreadable_then_exits (0.04s)
    --- PASS: TestReapMarkedUncertainty/vanished (0.02s)
    --- PASS: TestReapMarkedUncertainty/unrelated_inaccessible (0.04s)
    --- PASS: TestReapMarkedUncertainty/unexpected_environ_error (0.11s)
    --- FAIL: TestReapMarkedUncertainty/environ_lost_after_a_match,_survives (0.03s)
    --- PASS: TestReapMarkedUncertainty/environ_lost_after_a_match,_then_exits (0.03s)
    --- PASS: TestReapMarkedUncertainty/environ_not_yet_set_up (0.04s)
    --- PASS: TestReapMarkedUncertainty/pid_reused (0.03s)
rc=1 wall=1s
MARKED_SURVIVORS: none
````

**M9 start-time change ignored: result lines extracted from the run log** (`<scratchpad>/sum_m9.txt`, verbatim):

````
    watchdog_linux_test.go:743: reap: cleanup_unverified: still present after 5s: 3829830, seen [3829830:sleep]
    --- PASS: TestReapMarkedUncertainty/stat_unreadable_persists (0.11s)
    --- PASS: TestReapMarkedUncertainty/malformed_stat_persists (0.10s)
    --- PASS: TestReapMarkedUncertainty/stat_unreadable_then_exits (0.03s)
    --- PASS: TestReapMarkedUncertainty/vanished (0.02s)
    --- PASS: TestReapMarkedUncertainty/unrelated_inaccessible (0.03s)
    --- PASS: TestReapMarkedUncertainty/unexpected_environ_error (0.11s)
    --- PASS: TestReapMarkedUncertainty/environ_lost_after_a_match,_survives (0.11s)
    --- PASS: TestReapMarkedUncertainty/environ_lost_after_a_match,_then_exits (0.03s)
    --- PASS: TestReapMarkedUncertainty/environ_not_yet_set_up (0.04s)
    --- FAIL: TestReapMarkedUncertainty/pid_reused (5.01s)
rc=1 wall=6s
MARKED_SURVIVORS: none
````

**M6a child -run back to ^name$: result lines extracted from the run log** (`<scratchpad>/sum_m6a.txt`, verbatim):

````
    watchdog_linux_test.go:517: guarded run="^TestIsolationControls$/b" skip="" cpu=1: ran [TestIsolationControls/a TestIsolationControls/b TestIsolationControls/b/c] procs [1], want [TestIsolationCon
            watchdog_linux_test.go:378: === RUN   TestIsolationControls
                    --- PASS: TestIsolationControls/a (0.00s)
                    --- PASS: TestIsolationControls/b (0.00s)
                        --- PASS: TestIsolationControls/b/c (0.00s)
    watchdog_linux_test.go:517: guarded run="^TestIsolationControls$/b/c" skip="" cpu=1: ran [TestIsolationControls/a TestIsolationControls/b TestIsolationControls/b/c] procs [1], want [TestIsolationC
            watchdog_linux_test.go:378: === RUN   TestIsolationControls
                    --- PASS: TestIsolationControls/a (0.00s)
                    --- PASS: TestIsolationControls/b (0.00s)
                        --- PASS: TestIsolationControls/b/c (0.00s)
    watchdog_linux_test.go:517: guarded run="^TestNoSuchTestExists$/x|^TestIsolation(Controls)$/[b]" skip="Controls/b/c" cpu=3: ran [TestIsolationControls/a TestIsolationControls/b] procs [3], want [T
            watchdog_linux_test.go:378: === RUN   TestIsolationControls
                    --- PASS: TestIsolationControls/a (0.00s)
                    --- PASS: TestIsolationControls/b (0.00s)
    --- PASS: TestIsolationControls/hang (0.54s)
    --- PASS: TestIsolationControls/leak (0.04s)
    --- PASS: TestIsolationControls/fail (0.02s)
    --- PASS: TestIsolationControls/ran_nothing (0.01s)
    --- FAIL: TestIsolationControls/settings (0.17s)
rc=1 wall=2s
MARKED_SURVIVORS: none
````

**M6b GOMAXPROCS not forwarded: result lines extracted from the run log** (`<scratchpad>/sum_m6b.txt`, verbatim):

````
    watchdog_linux_test.go:517: guarded run="^TestIsolationControls$" skip="" cpu=1: ran [TestIsolationControls/a TestIsolationControls/b TestIsolationControls/b/c] procs [24], want [TestIsolationCont
            watchdog_linux_test.go:378: === RUN   TestIsolationControls
                    --- PASS: TestIsolationControls/a (0.00s)
                    --- PASS: TestIsolationControls/b (0.00s)
                        --- PASS: TestIsolationControls/b/c (0.00s)
    watchdog_linux_test.go:517: guarded run="^TestIsolationControls$/b" skip="" cpu=1: ran [TestIsolationControls/b TestIsolationControls/b/c] procs [24], want [TestIsolationControls/b TestIsolationCo
            watchdog_linux_test.go:378: === RUN   TestIsolationControls
                    --- PASS: TestIsolationControls/b (0.00s)
                        --- PASS: TestIsolationControls/b/c (0.00s)
    watchdog_linux_test.go:517: guarded run="^TestIsolationControls$/b/c" skip="" cpu=1: ran [TestIsolationControls/b TestIsolationControls/b/c] procs [24], want [TestIsolationControls/b TestIsolation
            watchdog_linux_test.go:378: === RUN   TestIsolationControls
                    --- PASS: TestIsolationControls/b (0.00s)
                        --- PASS: TestIsolationControls/b/c (0.00s)
    watchdog_linux_test.go:517: guarded run="^TestIsolationControls$" skip="TestIsolationControls/b/c" cpu=1: ran [TestIsolationControls/a TestIsolationControls/b] procs [24], want [TestIsolationContr
            watchdog_linux_test.go:378: === RUN   TestIsolationControls
                    --- PASS: TestIsolationControls/a (0.00s)
                    --- PASS: TestIsolationControls/b (0.00s)
    watchdog_linux_test.go:517: guarded run="^TestIsolationControls$/a|^TestIsolationControls$/b/c" skip="" cpu=1: ran [TestIsolationControls/a TestIsolationControls/b TestIsolationControls/b/c] procs
            watchdog_linux_test.go:378: === RUN   TestIsolationControls
                    --- PASS: TestIsolationControls/a (0.00s)
                    --- PASS: TestIsolationControls/b (0.00s)
                        --- PASS: TestIsolationControls/b/c (0.00s)
    watchdog_linux_test.go:517: guarded run="^TestNoSuchTestExists$/x|^TestIsolation(Controls)$/[b]" skip="Controls/b/c" cpu=3: ran [TestIsolationControls/b] procs [24], want [TestIsolationControls/b]
            watchdog_linux_test.go:378: === RUN   TestIsolationControls
                    --- PASS: TestIsolationControls/b (0.00s)
    watchdog_linux_test.go:517: guarded run="^TestIsolationControls$/(a|b)$" skip="" cpu=1,3: ran [TestIsolationControls/a TestIsolationControls/b TestIsolationControls/b/c TestIsolationControls/a Tes
            watchdog_linux_test.go:378: === RUN   TestIsolationControls
                    --- PASS: TestIsolationControls/a (0.00s)
                    --- PASS: TestIsolationControls/b (0.00s)
                        --- PASS: TestIsolationControls/b/c (0.00s)
            watchdog_linux_test.go:378: === RUN   TestIsolationControls
                    --- PASS: TestIsolationControls/a (0.00s)
                    --- PASS: TestIsolationControls/b (0.00s)
                        --- PASS: TestIsolationControls/b/c (0.00s)
    --- PASS: TestIsolationControls/hang (0.54s)
    --- PASS: TestIsolationControls/leak (0.04s)
    --- PASS: TestIsolationControls/fail (0.02s)
    --- PASS: TestIsolationControls/ran_nothing (0.02s)
    --- FAIL: TestIsolationControls/settings (0.19s)
rc=1 wall=1s
MARKED_SURVIVORS: none
````

**M6c -skip not forwarded: result lines extracted from the run log** (`<scratchpad>/sum_m6c.txt`, verbatim):

````
    watchdog_linux_test.go:517: guarded run="^TestIsolationControls$" skip="TestIsolationControls/b/c" cpu=1: ran [TestIsolationControls/a TestIsolationControls/b TestIsolationControls/b/c] procs [1],
            watchdog_linux_test.go:378: === RUN   TestIsolationControls
                    --- PASS: TestIsolationControls/a (0.00s)
                    --- PASS: TestIsolationControls/b (0.00s)
                        --- PASS: TestIsolationControls/b/c (0.00s)
    watchdog_linux_test.go:517: guarded run="^TestNoSuchTestExists$/x|^TestIsolation(Controls)$/[b]" skip="Controls/b/c" cpu=3: ran [TestIsolationControls/b TestIsolationControls/b/c] procs [3], want 
            watchdog_linux_test.go:378: === RUN   TestIsolationControls
                    --- PASS: TestIsolationControls/b (0.00s)
                        --- PASS: TestIsolationControls/b/c (0.00s)
    --- PASS: TestIsolationControls/hang (0.54s)
    --- PASS: TestIsolationControls/leak (0.04s)
    --- PASS: TestIsolationControls/fail (0.02s)
    --- PASS: TestIsolationControls/ran_nothing (0.01s)
    --- FAIL: TestIsolationControls/settings (0.16s)
rc=1 wall=1s
MARKED_SURVIVORS: none
````

**M10 one empty scan taken as clean (re-run after the compile-error mutant, as `if quiet || true`)**, output:

````
=== RUN   TestReapMarkedUncertainty
=== RUN   TestReapMarkedUncertainty/malformed_stat_persists
=== RUN   TestReapMarkedUncertainty/stat_unreadable_persists
=== RUN   TestReapMarkedUncertainty/stat_unreadable_then_exits
=== RUN   TestReapMarkedUncertainty/vanished
=== RUN   TestReapMarkedUncertainty/unrelated_inaccessible
=== RUN   TestReapMarkedUncertainty/unexpected_environ_error
=== RUN   TestReapMarkedUncertainty/environ_lost_after_a_match,_survives
=== RUN   TestReapMarkedUncertainty/environ_lost_after_a_match,_then_exits
=== RUN   TestReapMarkedUncertainty/environ_not_yet_set_up
    watchdog_linux_test.go:715: reap: <nil>, seen [], alive true: one empty scan read as clean
=== RUN   TestReapMarkedUncertainty/pid_reused
--- FAIL: TestReapMarkedUncertainty (0.57s)
    --- PASS: TestReapMarkedUncertainty/malformed_stat_persists (0.11s)
    --- PASS: TestReapMarkedUncertainty/stat_unreadable_persists (0.11s)
    --- PASS: TestReapMarkedUncertainty/stat_unreadable_then_exits (0.03s)
    --- PASS: TestReapMarkedUncertainty/vanished (0.01s)
    --- PASS: TestReapMarkedUncertainty/unrelated_inaccessible (0.03s)
    --- PASS: TestReapMarkedUncertainty/unexpected_environ_error (0.11s)
    --- PASS: TestReapMarkedUncertainty/environ_lost_after_a_match,_survives (0.12s)
    --- PASS: TestReapMarkedUncertainty/environ_lost_after_a_match,_then_exits (0.03s)
    --- FAIL: TestReapMarkedUncertainty/environ_not_yet_set_up (0.01s)
    --- PASS: TestReapMarkedUncertainty/pid_reused (0.03s)
FAIL
FAIL	github.com/beyondeye/aitasks/goengines/internal/testmap/runner	0.577s
FAIL
rc=1
````

**M3 sweepSession never returns: per-test outcome (33 anchored invocations, 12 parallel)** (`<scratchpad>/sum_m3.txt`, verbatim):

````
M3 total wall=60s over 33 tests
MARKED_SURVIVORS: none
TestChildRowsNeedFull | HANG:TestChildRowsNeedFull|20s | rc=1 wall=20s | leftover processes: none
TestCleanupAfterNormalExit | HANG:TestCleanupAfterNormalExit|20s | rc=1 wall=20s | leftover processes: none
TestCleanupEveryKillPath | HANG:TestCleanupEveryKillPath|20s | rc=1 wall=20s | leftover processes: none
TestCleanupSeparateTestGroupOnInvocationTimeout | never appeared | rc=1 wall=10s | 
TestDescribeOverrideValidated | HANG:TestDescribeOverrideValidated|20s | rc=1 wall=20s | leftover processes: none
TestExecutorSeamAndHandle | HANG:TestExecutorSeamAndHandle|20s | rc=1 wall=20s | leftover processes: none
TestKilledRunValidatesRows | HANG:TestKilledRunValidatesRows|20s | rc=1 wall=20s | leftover processes: none
TestListMalformedThroughScan | HANG:TestListMalformedThroughScan|20s | rc=1 wall=20s | leftover processes: none
TestOwnership | HANG:TestOwnership|20s | rc=1 wall=20s | leftover processes: none
TestOwnershipRefusals | HANG:TestOwnershipRefusals|20s | rc=1 wall=20s | leftover processes: none
TestPostRunHookOrder | HANG:TestPostRunHookOrder|20s | rc=1 wall=20s | leftover processes: none
TestRecordHeadMoved | HANG:TestRecordHeadMoved|20s | rc=1 wall=20s | leftover processes: none
TestRecordMechanismCause | HANG:TestRecordMechanismCause|20s | rc=1 wall=20s | leftover processes: none
TestRecordProvenance | HANG:TestRecordProvenance|20s | rc=1 wall=20s | leftover processes: none
TestRunAllSubsumedAndChildren | HANG:TestRunAllSubsumedAndChildren|20s | rc=1 wall=20s | leftover processes: none
TestRunErrors | HANG:TestRunErrors|20s | rc=1 wall=20s | leftover processes: none
TestRunExitOutcomes | HANG:TestRunExitOutcomes|20s | rc=1 wall=20s | leftover processes: none
TestRunPassFail | HANG:TestRunPassFail|20s | rc=1 wall=20s | leftover processes: none
TestRunReconciliation | HANG:TestRunReconciliation|20s | rc=1 wall=20s | leftover processes: none
TestRunReportFilesAreSafe | HANG:TestRunReportFilesAreSafe|20s | rc=1 wall=20s | leftover processes: none
TestSerialPlanRefusesResources | HANG:TestSerialPlanRefusesResources|20s | rc=1 wall=20s | leftover processes: none
TestShadowByNameAndBuiltins | HANG:TestShadowByNameAndBuiltins|20s | rc=1 wall=20s | leftover processes: none
TestSubsumptionCycleWithPassingRunner | PASS | rc=0 wall=0s | 
TestSubsumptionTerminalSelectsNothing | HANG:TestSubsumptionTerminalSelectsNothing|20s | rc=1 wall=20s | leftover processes: none
TestSweepEnumeration | HANG:TestSweepEnumeration|20s | rc=1 wall=20s | leftover processes: 3833541:sleep (killed)
TestSweepUninspectableProcesses | HANG:TestSweepUninspectableProcesses|20s | rc=1 wall=20s | leftover processes: 3833557:sleep (killed)
TestTimeoutBatchBounded | HANG:TestTimeoutBatchBounded|20s | rc=1 wall=20s | leftover processes: none
TestTimeoutInvocationMax | HANG:TestTimeoutInvocationMax|20s | rc=1 wall=20s | leftover processes: none
TestTimeoutNoneSingletons | HANG:TestTimeoutNoneSingletons|20s | rc=1 wall=20s | leftover processes: none
TestTimeoutNotStartedVsMissing | HANG:TestTimeoutNotStartedVsMissing|20s | rc=1 wall=20s | leftover processes: none
TestTimeoutPerUnitNotEnforced | HANG:TestTimeoutPerUnitNotEnforced|20s | rc=1 wall=20s | leftover processes: none
TestTimeoutPerUnitRunnerEnforced | HANG:TestTimeoutPerUnitRunnerEnforced|20s | rc=1 wall=20s | leftover processes: none
TestUnitAttributes | HANG:TestUnitAttributes|20s | rc=1 wall=20s | leftover processes: none
````

**Stress driver (stress_isolation_suite)** (`<scratchpad>/stress.sh`, verbatim):

````bash
#!/usr/bin/env bash
# t1985 stress_isolation_suite: the runner package ten times while
# `ait engine test` loops alongside; then no marked process may survive.
set -u
S=/tmp/claude-1000/-home-ddt-Work-aitasks/767706b9-6b7d-44d7-8f36-b354de4c51df/scratchpad
cd /home/ddt/Work/aitasks
: > "$S/stress_load.log"
rm -f "$S/stress.done"
(
	i=0
	while [ ! -e "$S/stress.done" ]; do
		i=$((i + 1))
		s=$(date +%s)
		./ait engine test -count=1 > "$S/stress_load_$i.log" 2>&1
		echo "load run $i: rc=$? wall=$(( $(date +%s) - s ))s" >> "$S/stress_load.log"
	done
) &
loader=$!
s=$(date +%s)
(cd goengines && go test ./internal/testmap/runner/ -count=10 -timeout 30m -v) > "$S/stress.log" 2>&1
rc=$?
e=$(date +%s)
touch "$S/stress.done"
wait "$loader"
echo "stress: rc=$rc wall=$((e - s))s"
echo "HANG/LEAK/FAIL lines: $(grep -c -E 'HANG:|LEAK:|^--- FAIL|^\s+--- FAIL|^FAIL' "$S/stress.log")"
echo "top-level PASS lines: $(grep -c '^--- PASS' "$S/stress.log")"
cat "$S/stress_load.log"
found=$(grep -a -o 'AIT_RUNNER_TEST_ISOLATE=[^[:cntrl:]]*' /proc/[0-9]*/environ 2>/dev/null | sort -u)
echo "MARKED_SURVIVORS: ${found:-none}"
rm -f "$S/stress.done"
echo STRESS_DONE
````

**Stress output, final code** (`<scratchpad>/stress4.out`, verbatim):

````
stress: rc=0 wall=163s
HANG/LEAK/FAIL lines: 0
top-level PASS lines: 560
load run 1: rc=0 wall=17s
load run 2: rc=0 wall=16s
load run 3: rc=0 wall=17s
load run 4: rc=0 wall=16s
load run 5: rc=0 wall=16s
load run 6: rc=0 wall=17s
load run 7: rc=0 wall=16s
load run 8: rc=0 wall=17s
load run 9: rc=0 wall=16s
load run 10: rc=0 wall=17s
MARKED_SURVIVORS: none
STRESS_DONE
FINAL_DONE
````

**Reviewer-repro comparison driver** (`<scratchpad>/flake_cmp.sh`, verbatim):

````bash
#!/usr/bin/env bash
# The reviewer's repro, before (prev) and after (mut) the readiness fix: three
# parallel instances x 300 repetitions each, so the start-to-scan race is
# exercised under contention.
S=/tmp/claude-1000/-home-ddt-Work-aitasks/767706b9-6b7d-44d7-8f36-b354de4c51df/scratchpad
for v in prev mut; do
	cd "$S/$v/goengines" && go test -c -o "$S/flake_$v.test" ./internal/testmap/runner/ || exit 1
	cd internal/testmap/runner
	for i in 1 2 3; do
		"$S/flake_$v.test" -test.run '^TestReapMarkedUncertainty$/(environ_lost_after_a_match.*|pid_reused)$' -test.count=300 -test.timeout=10m > "$S/flake_${v}_$i.log" 2>&1 &
	done
	wait
	fails=$(cat "$S"/flake_"$v"_*.log | grep -c -E '^\s+--- FAIL')
	echo "$v: subtest failures over 3x300 runs: $fails"
	cat "$S"/flake_"$v"_*.log | grep -E 'watchdog_linux_test.go:[0-9]+:' | sed -E 's/[0-9]{4,}/N/g' | sort | uniq -c | head -5
done
````

Output of `flake_cmp.sh`:

````
prev: subtest failures over 3x300 runs: 0
mut: subtest failures over 3x300 runs: 0
````

**Execve-window probe 1** (`<scratchpad>/envprobe/probe_test.go`, verbatim):

````go
package envprobe

import (
	"bytes"
	"os"
	"os/exec"
	"strconv"
	"testing"
)

// How often /proc/<pid>/environ lacks the marker right after cmd.Start returns.
func TestEnvironAfterStart(t *testing.T) {
	missed := 0
	const n = 2000
	for i := range n {
		cmd := exec.Command("sleep", "5")
		cmd.Env = append(os.Environ(), "PROBE_MARKER=x")
		if err := cmd.Start(); err != nil {
			t.Fatal(err)
		}
		env, err := os.ReadFile("/proc/" + strconv.Itoa(cmd.Process.Pid) + "/environ")
		if err != nil || !bytes.Contains(env, []byte("PROBE_MARKER=x")) {
			missed++
			if missed <= 3 {
				t.Logf("trial %d: err %v, %d bytes of environ", i, err, len(env))
			}
		}
		_ = cmd.Process.Kill()
		_ = cmd.Wait()
	}
	t.Logf("marker missing right after Start in %d of %d trials", missed, n)
}
````

Output: `probe_test.go:31: marker missing right after Start in 1958 of 2000 trials` (trials 0–2: `err <nil>, 0 bytes of environ`).

**Execve-window probe 2** (`<scratchpad>/envprobe/window_test.go`, verbatim):

````go
package envprobe

import (
	"bytes"
	"os"
	"os/exec"
	"slices"
	"strconv"
	"testing"
	"time"
)

// How long the environment stays unreadable-as-empty after Start, and how
// long one full /proc environ scan takes.
func TestEnvironWindow(t *testing.T) {
	var waits []time.Duration
	for range 500 {
		cmd := exec.Command("sleep", "5")
		cmd.Env = append(os.Environ(), "PROBE_MARKER=x")
		if err := cmd.Start(); err != nil {
			t.Fatal(err)
		}
		s := time.Now()
		for {
			env, _ := os.ReadFile("/proc/" + strconv.Itoa(cmd.Process.Pid) + "/environ")
			if bytes.Contains(env, []byte("PROBE_MARKER=x")) {
				break
			}
		}
		waits = append(waits, time.Since(s))
		_ = cmd.Process.Kill()
		_ = cmd.Wait()
	}
	slices.Sort(waits)
	t.Logf("window: p50 %v p99 %v max %v", waits[len(waits)/2], waits[len(waits)*99/100], waits[len(waits)-1])
	s := time.Now()
	ents, _ := os.ReadDir("/proc")
	for _, e := range ents {
		if _, err := strconv.Atoi(e.Name()); err == nil {
			_, _ = os.ReadFile("/proc/" + e.Name() + "/environ")
		}
	}
	t.Logf("one scan of %d entries: %v", len(ents), time.Since(s))
}
````

Output: `window: p50 43.758µs p99 116.404µs max 262.723µs`; `one scan of 764 entries: 6.654151ms`.
