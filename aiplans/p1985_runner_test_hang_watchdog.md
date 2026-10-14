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
