---
Task: t1854_6_m3_2c_supervised_execution.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md, aitasks/t1854/t1854_5_*.md, aitasks/t1854/t1854_7_*.md, aitasks/t1854/t1854_8_*.md, aitasks/t1854/t1854_9_*.md, aitasks/t1854/t1854_10_*.md, aitasks/t1854/t1854_11_*.md, aitasks/t1854/t1854_12_*.md, aitasks/t1854/t1854_13_*.md, aitasks/t1854/t1854_14_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-25 06:35
---

# Plan: t1854_6 — M3.2c Supervised execution foundation (dedicated supervisor)

## Context

No production runner may be enabled before process supervision is complete.
This task delivers three things:

- **G8:** containment that a descendant cannot leave by changing its process
  group or session.
- **G8a:** per-invocation cleanup ownership that survives a builtin crash.
- **The scaffold:** the `ait-testmap runner <name>` verb and the builtin
  scaffold, with **no production adapter registered**.

Every adapter (t1854_8–t1854_13) and the scheduler (t1854_3) build on it.

**Design decision (user, 2026-10-24):** a **dedicated supervisor process** per
contained process start. It replaces the first plan's engine-wide subreaper
tree, which three review rounds kept extending, and **cgroup hardening is
deferred** to a follow-up task. The task body
(`aitasks/t1854/t1854_6_m3_2c_supervised_execution.md`) stays authoritative for
G1–G10, except for the criteria this plan revises (listed under *Acceptance
criteria revised*, applied to the body in Step 1).

Automation-first: no path makes a human action a precondition.

## The design in one paragraph

Every contained process start goes through `ait-testmap __supervise`, a re-exec
of the engine binary that runs no test code. This covers the engine starting a
runner's `describe` / `list` / `run`, and a builtin starting a tool. The
supervisor sets `PR_SET_CHILD_SUBREAPER` on **itself only**, starts the command
in a new session, and owns exactly its own subtree: every orphan below it,
`setsid()` callers included, reparents to it. Cleanup kills its **direct
children** by pid. Each is its own unreaped child, so the pid cannot have been
reused. It then reaps with `wait4(-1)`, which is safe because every child it
has is a member, and repeats, since orphans become direct children. It stops
only when `wait4` returns **ECHILD**: a kernel proof that the subtree is empty,
because any live descendant implies a live direct child. Membership is exact
per supervisor by construction, so concurrent invocations on any Linux host
cannot touch each other's processes.

## Step 0 — Reality check (recorded 2026-10-23, main `bcdeff693`)

M3.1's exec/sweep code, t1854_2's contract and t1854_7's guard were read as
landed. The three inbox notes (t1854_2, t1854_5, t1854_7) were acknowledged
and are consumed below as advisory input.

| # | task body says / assumed | repository has | decision |
|---|---|---|---|
| 1 | hang guard is `isolated(t, hangLimit)`, unexported, runner-only | `hangguard.Isolated(t, limit)` in `internal/testsupport/hangguard`; opt-in is one `tripwirePackages` entry; runner keeps its `isolated` wrapper (t1854_5 note) | `procsup` and `builtin` each get a `tripwirePackages` entry with `localStarters`; runner's `sweepSession` starter moves to procsup's entry |
| 2 | scaffold writes `cases.jsonl` "per t1854_2" | `runner.ValidateCases`, `runner.CasesFile`; row `{"unit","case","status","duration_ms","message"?}`; env `AIT_TESTMAP_REPORT_DIR` / `AIT_TESTMAP_ACCOUNTING`; Manifest has `accounting`, `report_dir`, `units[].cases` (t1854_2 note) | the results writer emits exactly that shape and reuses the exported names |
| 3 | "fresh-report reader" helper | `runner.FreshReport(d ReportDir, path)` needs a `ReportDir` whose identity is unexported and built only by `NewReportDir` (engine side) | named extension of t1854_2's `report_unix.go`: `runner.OpenReportDir(path)`. It requires a real, empty directory, records its identity, and takes `Start` from its mtime at open. The builtin calls it at startup, before any tool runs |
| 4 | builtin runs as `SelfExe runner <b> describe\|list\|run --manifest <abs>` | confirmed (`repo.go` `Runner.command`); `describe`/`list` take no `--manifest`; env adds `AIT_TESTMAP_ROOT/RUNNER/COMMAND/ACTIVE` (+ `RUN_ID`, `REPORT_DIR`, `ACCOUNTING`) | the CLI shape is `runner <name> describe`, `runner <name> list`, `runner <name> run --manifest <p>` |
| 5 | engine sweeps the runner's session; `setsid()` escapes | `execRunner` → `sweepSession(pid)`; `sessionProcs` in `proc_linux.go` / `proc_darwin.go` / `proc_other.go`; `readStat` is also used by `recursion_linux.go` | the session code moves to `procsup` (`SweepSession`, `SessionProcs`) and is used only on darwin's legacy (unsupervised) path. On Linux no path signals by session number (see the Engine side). runner keeps its own `readStat` for the recursion view. M3.1's cleanup tests stay in runner, unchanged and green |
| 6 | recursion backstop walks the ppid chain (t1854_7 note) | an orphaned or `setsid`+double-forked descendant reparents away and escapes it today | orphans now reparent to the supervisor, whose parent is the engine, so the chain reaches the outer engine. A new recursion case, `wrap=orphan` (setsid double fork under `env -i`), is refused |
| 7 | executor gets context; `AIT_TESTMAP_ACTIVE` is in every adapter env (t1854_7 note) | confirmed | the supervisor passes the command's env verbatim; the scaffold passes `os.Environ()` through, so the marker survives |
| 8 | cgroup v2 leaf and `AIT_TESTMAP_REQUIRE_*` knob for a cgroup boundary | — | **out of scope** (user, 2026-10-24); hardening becomes a spawned follow-up task. The 2026-10-23 decision to add `AIT_TESTMAP_REQUIRE_CGROUP` is withdrawn with it. REQUIRE_REAL_TOOLS is untouched |
| 9 | t1854_3 consumes `Boundary.Overlappable()` | an executor receives invocations **before** they start | the executor-facing query is `runner.Overlappable() bool`: true on Linux, false where containment is unavailable (darwin). `Run` enforces it (below). A note goes to t1854_3 |
| 10 | CI coverage | `goengines-check.yml`: ubuntu-latest, `go test ./...`, preflight first | the supervisor needs only `prctl` and `/proc`, both available on CI. **Every test, the parallel overlap test included, runs in CI**; no host-only coverage |
| 11 | module deps | stdlib + `x/sync`, `doublestar`, `yaml.v3` | stdlib only: `syscall.RawSyscall(SYS_PRCTL, 36 /*PR_SET_CHILD_SUBREAPER*/, 1, …)`, `syscall.Wait4`, `os.Pipe`, `exec.Cmd.ExtraFiles` |
| 12 | engine binary entry for the supervisor | `cmd/ait-testmap/main.go` → `dispatch(verbs…)`; `TestVerbTableMatchesProposal` pins the verb table to the proposal | `__supervise` is dispatched in `run()` **before** the verb table, so the table and its test are unchanged. It is documented in README as internal |

Owned-file re-confirmation. Every touched file is in this task's list or is a
named extension of its owner's file:

- `report_unix.go` (t1854_2) gains `OpenReportDir`;
- `hangguard/tripwire_test.go` (t1854_5) gains entries;
- `recursion_test.go` (t1854_7) gains the backend parameterization and the
  orphan case;
- `cmd/ait-testmap/main.go` gains the `__supervise` pre-dispatch.

No gitx or deps file is touched.

## Acceptance criteria revised (applied to the task body in Step 1)

| criterion (task body) | revised to |
|---|---|
| G8 "subreaper on the supervising process … `/proc` parent-pid tree" | the subreaper is the **dedicated supervisor** (`__supervise`). Emptiness is proven by `wait4` ECHILD; `/proc` is used only to target kills. A survivor past the bound is `cleanup_incomplete`; an unreadable `/proc` is `cleanup_unverified` |
| G8 cgroup v2 leaf, `CONTAINMENT:subreaper\|cgroup` | cgroup deferred to the follow-up `supervisor_cgroup_hardening`. The record reports `containment: supervisor\|none` |
| G8a boundary "cgroup leaf when delegated, else tree"; `Overlappable()` only for cgroup; `PARALLEL_REFUSED:containment` without cgroup | the boundary is the **per-invocation supervisor**, and the record reports `boundary: supervisor\|none`. `runner.Overlappable()` is true on Linux. `PARALLEL_REFUSED:containment` remains only where containment is unavailable (darwin) |
| G8a "membership the kernel keeps even after every process between it and the engine has died" | membership survives the death of **every process that runs test code**: runner, builtin, tool, and any descendant. **The supervisor's own death is a stated residual**: its remaining processes may be left behind. It is detected, recorded as `cleanup_unverified`, and halts all further work (below) |
| real-process overlap test "runs on a host with a delegated cgroup; otherwise asserts the serial refusal"; `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1` / `REQUIRE_CGROUP` declaration | the overlap test runs **on every Linux host, CI included**; no knob |
| "M3.1's session sweep stays as a second pass" | the sweep moves to procsup and its tests stay green, as the **darwin legacy path only**. On Linux the engine never signals by session number: after a clean supervision the session id is no longer owned, and after a supervision failure its original ownership is unverified. The mechanism failure and the halt carry the failure instead |
| invariant "under every enabled backend" | unchanged in form: parameterized over `procsup.Backends()`, which today is `[supervisor]`; any later backend (cgroup hardening, PID namespace) must join it |

The parent's G8/G8a text (`aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md`)
is edited the same way in Step 1. Every sibling body carries a copy of the
G-table, so each receiving sibling gets a note (Step 11) rather than an edit.

## Design

### `__supervise` (`goengines/internal/procsup/supervisor_linux.go`)

**Invocation.** `ait-testmap __supervise --grace <dur> --bound <dur> --
<path> <args…>`, with the command's cwd and env inherited from the
supervisor's own `exec.Cmd`.

**File descriptors:**
- fd 0, 1 and 2 are passed straight through to the command, so the
  supervisor never copies output;
- fd 3 is the **control pipe** (parent → supervisor);
- fd 4 is the **status pipe** (supervisor → parent).

**Sequence:**
1. `prctl(PR_SET_CHILD_SUBREAPER, 1)`. On failure, write status
   `{"error":"subreaper:<errno>"}` and exit 3. The command never starts.
2. Start the command with `Setsid`, so it leads its own session and process
   group. The supervisor itself starts nothing else, ever. Immediately
   **write the handshake line** `{"pid":<command pid>}` on fd 4.
   - The client sets the sentinel env `AIT_PROCSUP_SUPERVISOR=1` on the
     supervisor process.
     - The genuine supervisor (`SuperviseMain`) removes it, both from its own
       environment and from the command's, **before** starting the command.
       So no legitimate process below a supervisor ever carries it.
     - **Bootstrap guard:** `Start` and `Run` refuse **before any launch** when
       the sentinel is present in the calling process's environment, with
       `*DispatchError` (`supervisor_dispatch_missing`). A process that still
       carries it is by construction a supervisor launch that was never
       dispatched, typically a test binary that omitted
       `procsup.MaybeSupervise()`. So it can never start another supervisor:
       the recursion is cut at depth one, independent of the missing call.
   - The client also requires the handshake line within `HandshakeTimeout`
     (5 s), else it SIGKILLs the supervisor process:
     `SupervisorDied: missing handshake`. This bounds how long the misdispatched
     process runs. The guard above ensures it launches nothing meanwhile.
3. Wait, in one loop, for the command's exit (`wait4` on its pid) or for a
   control event:
   - a `c` byte (cancel), or
   - EOF on the control pipe, meaning the parent died or closed it. EOF is
     handled like cancel, so **an engine's death makes every supervisor clean
     up**.
4. **On cancel:** SIGTERM the command's process group, but only while the
   command is unreaped, so the pgid cannot have been reused. The group lies
   inside the command's own session, whose members are all descendants. Then
   wait up to `--grace` for the exit.
5. **Cleanup, on every path:**
   - Enumerate the supervisor's direct children: `/proc/<pid>/stat` with
     `ppid == self`. Each is an unreaped child, so its pid is pinned.
   - SIGKILL each one, then reap with `wait4(-1, WNOHANG)` until no zombie
     remains.
   - Repeat until `wait4(-1, WNOHANG)` returns `ECHILD`, which means clean, or
     `--bound` expires, which means `cleanup_incomplete:<pids still children>`.
   - An unreadable `/proc` cannot target a kill. It still waits for ECHILD
     within the bound; past the bound it is `cleanup_unverified:<reason>`.
   - No group signal is used in cleanup, and no pid outside its own children
     is ever signalled.
6. Write one status line on fd 4 and exit 0:
   `{"exit":<n>,"signal":"<name>"|"","start_error":"…"|"","cleanup":"ok"|"cleanup_incomplete:…"|"cleanup_unverified:…"}`.

### Client and supervision API (`procsup`, `goengines/internal/procsup/`)

**Files:**
- `procsup.go`: shared types and docs;
- `supervisor_linux.go`: the supervisor's main loop;
- `client_unix.go`: starting and talking to a supervisor;
- `session_linux.go` / `session_darwin.go` / `session_other.go`: moved from
  `runner/proc_*.go`;
- `unavailable_other.go`: darwin and other unix.

**`Start(ctx, Spec) (*Proc, error)` and `(*Proc).Wait() Result`.** The
engine's runner path uses them:
- `Spec{Path, Args, Env, Dir, Stdout, Stderr io.Writer or *os.File, Grace, Bound}`;
- the client starts `SupervisorExe` (default `os.Executable`) with the
  control and status pipes as `ExtraFiles`;
- `Proc.Cancel()` writes the cancel byte;
- `Wait` returns:
  - `Result{Exit, Signal, StartErr, Cleanup error, SupervisorDied bool, Detail}`;
  - `SupervisorDied` when the supervisor exited by signal, exited non-zero
    without a status line, or wrote a malformed status (strict JSON, unknown
    fields refused).
- **Supervisor unresponsive:** the client allows `Grace + Bound + 2s` after a
  cancel. Past that it SIGKILLs the supervisor itself, which then counts as
  `SupervisorDied`.

**`Run(ctx, RunSpec) RunResult`.** The builtin's tool path, with timeout
semantics:
- `RunSpec` adds `Timeout`, a `Stdout`/`Stderr` **file path**, and
  `OutputMax`;
- output is copied through a capped file writer. Past the cap it is truncated,
  `Truncated` is set and draining continues. A `WaitDelay` bounds leaked
  holders;
- timeout or `ctx` cancel → `Cancel()`, which means SIGTERM, then the grace,
  then the containment kill and the ECHILD proof;
- `RunResult{Exit, Signal, TimedOut, Cancelled, Truncated, StartErr, Cleanup, SupervisorDied, Containment}`.

**Halt on supervisor death or failed cleanup (the user-requested rule).**
- **Trigger:** a `Wait` that finds `SupervisorDied`, or a status whose
  `cleanup` is not `ok`, **halts** the process's procsup.
- **Admission and registration are one critical section (review finding,
  2026-10-25).** One mutex, `admitMu`, guards three things together: the
  halted flag, the first detail and the live registry. No atomic flag is read
  outside it.
  - **`Start`**:
    1. *Admit*: under `admitMu`, if halted → refuse with `*HaltedError`. Else
       insert a **reservation** (the `Proc`, state `starting`) into the
       registry.
    2. Release the lock and *launch* the supervisor; the control pipe exists
       from launch.
    3. *Activate*: under `admitMu` again, mark the `Proc` launched. If its
       `cancelRequested` was set meanwhile, write the cancel byte now, under
       the lock.
    4. A launch failure removes the reservation under the lock.
  - **Halt**: under `admitMu`, set halted and the detail, and set
    `cancelRequested` on **every** registry entry, reservations included.
    Still under the lock, write the cancel byte to every entry that is already
    launched. Entries still starting get theirs at their own step 3.
  - **`Wait`** removes its `Proc` under `admitMu` once the supervisor's exit
    is read.
  - **Consequence:** a `Start` that overlaps a halt is in exactly one of two
    cases. It checks after the halt, so it is refused and launches nothing.
    Or it reserved before the halt, so the halt's snapshot includes it and it
    is cancelled no later than its activation. There is no third interleaving.
  - The supervisor handles a cancel byte that arrives before or right after it
    starts its command. Pending control input is read after the start, so the
    command is cancelled, never left running.
  - Test seams for the deterministic test below (each guarded by
    `testing.Testing()`): `BeforeAdmitForTesting` (before step 1) and
    `BeforeLaunchForTesting` (between steps 1 and 2), both blocking hooks.
- **What it records:** the halted flag, plus the first triggering detail kept
  verbatim. Then:
  1. **Further work stops.** Every later `Start`/`Run` returns
     `*HaltedError` (`halted:<first detail>`) **without starting a process**.
     There is no recovery: the halt lasts for the life of the process. The
     engine is one process per verb, so the next `ait-testmap` invocation
     starts fresh.
  2. **Other active supervisors are cancelled.** procsup keeps a registry of
     live `Proc`s. On halt it calls `Cancel()` on every one except the
     trigger, and each cleans up its own subtree and reports normally. Their
     results carry `Halted: true`, so their invocations are recorded as
     `halted`, not as their own failure. Waiting for them stays the job of
     their own `Wait` callers.
- **Residual, stated in README and in the record's detail:** when the
  supervisor itself dies, the processes still in its subtree reparent to
  their nearest subreaper ancestor (systemd user manager, init or other) and
  **may be left running**.
  - The engine makes **no** fallback kill: once the supervisor is gone,
    nothing proves that the runner's session still exists, so no signal by
    session or group number is authorized.
  - It never claims that cleanup succeeded. It records the failure and halts.
  - A dead tool supervisor *inside a builtin* is not this residual: its
    orphans reparent to the invocation's supervisor (the nearest subreaper)
    and die with the invocation.
  - Only the outermost supervisor's death leaks.
- `Backends() []string` is `["supervisor"]` on Linux and `[]` elsewhere.
  `Available() error` is nil on Linux and `*UnavailableError` elsewhere,
  rendered `CONTAINMENT_UNAVAILABLE:<GOOS>`.
- **Test hooks** (each panics unless `testing.Testing()` is true, so a
  production binary cannot reach them):
  - `SetUnavailableForTesting()` drives the forced `CONTAINMENT_UNAVAILABLE`
    test;
  - `OnStartForTesting(func(supervisorPid, commandPid int))` lets a test kill
    a specific supervisor.

  Test binaries dispatch the supervisor with one line in `TestMain`:
  `procsup.MaybeSupervise()`, which handles `os.Args[1] == "__supervise"` and
  exits.

### Engine side (runner, named extensions of M3.1)

- **`exec_unix.go`:** `execRunner(ctx, c, deadline)` starts the runner
  through `procsup.Start` on Linux.
  - stdout and stderr are pipes into the existing `capWriter`s: the stdout cap
    still kills on overflow, by calling `Cancel`.
  - The engine deadline, an output overflow and ctx cancellation each call
    `Proc.Cancel()`, with grace 0. That keeps M3.1's immediate-kill semantics.
  - **On Linux the engine never signals by session number, on any path.**
    - **After a verified clean result** (`cleanup: ok`, from the ECHILD
      proof), the supervisor has reaped every descendant, the runner
      included. The number that was the runner's session id is no longer
      pinned and may already belong to an unrelated session.
    - **On the failure paths** (`SupervisorDied`, `cleanup_incomplete`,
      `cleanup_unverified`), nothing establishes that the original session
      still exists:
      - a supervisor can reap everything and then die before writing its
        status;
      - an inspection can fail after the last member is gone.

      In both cases the number can be released and reused before any
      enumeration begins. `sid == S` would then identify whatever session
      holds that number now, not the runner's. The original ownership is
      unverified, so no signal is authorized.
    - **What the failure paths keep:** the mechanism failure
      (`cleanup_unverified:supervisor_died:…` or the supervisor's own
      verdict) and the **halt**.
    - **What they give up:** best-effort cleanup. The supervisor-death
      residual already documents that processes may be left behind.
  - **`SweepSession` stays as the legacy utility where it is independently
    required: darwin**, where there is no supervisor. There the engine still
    runs the runner directly, with `Setsid` and M3.1's sweep, unchanged
    (including that path's pre-existing post-reap window, noted in README).
    Its unit tests (`TestSweepEnumeration`, `TestSweepUninspectableProcesses`)
    move to procsup and stay green.
  - `sweepSession` is a package-level var in runner (`=
    procsup.SweepSession`), used only by the darwin path, so a test can
    prove that the Linux path never calls it.
  - The first error goes to `res.Sweep` as a `*CleanupError`. `SupervisorDied`
    → `cleanup_unverified:supervisor_died:<detail>`; `Halted` →
    `res.Halted = true`.
  - On darwin (`Available()` fails), `execRunner` runs the runner directly as
    today, with `Setsid` and the session sweep, containment `none`.
  - The comment's `setsid()` residual is rewritten: on Linux it is closed by
    the supervisor.
- **`proc_*.go`:** the session code moves to procsup. `proc_linux.go` keeps
  `readStat`/`gone`/`parseStat` for `recursion_linux.go` and the tests.
- **`invoke.go`:**
  - `procsup` refusal before start (`*HaltedError`) → `fail("halted:"+…)`:
    mechanism, every unit `not_started`, nothing started.
  - `Record` gains `Containment` (`supervisor|none`) and `Boundary`
    (`supervisor|none`) as JSON fields.
  - **A halted execution is an interruption that is not a timeout (review
    finding, 2026-10-25).** `execResult.Halted`, together with
    `Interrupted() = Killed || Halted`, is threaded through every place that
    today special-cases an engine kill:
    - **`ValidateRows` / `ValidateCases`:** their `killed` argument becomes
      `res.Interrupted()`. A runner cancelled by a halt can leave an
      unterminated final line, which is ignored as truncated exactly as after
      a kill. Every complete line is still judged.
    - **`caseEvidence`:** its kill branch now applies when
      `res.Interrupted()`. The early `!ran && !res.Killed` return no longer
      fires for a halt. For a halted invocation that means:
      - attributable invalid evidence (any reason but `incomplete`:
        `duplicate_case`, `unexpected_case`, `malformed_case`,
        `rejected_report`) makes the unit `error` with its reasons recorded as
        protocol errors;
      - a unit whose cases are all terminally reported (`Terminal`) keeps its
        derived status and counters;
      - every other unit, partial or untouched, is left unreported for
        attribution.
    - **`decide`** gains `case end.Halted:`, placed before `end.Killed`
      because mechanism outranks timeout. It sets cause `mechanism` with
      detail `halted:<origin detail>` and leaves synthesis to the new
      `AttributeHalt(expected, started, reported)`, never to `AttributeKill`.
      An unreported unit becomes `missing`, carrying `Started` from its start
      row; it is never `timeout` or `batch_timeout`, because the engine did
      not time it out.
    - **`Record.TimedOut`** stays empty for a halt, and `Record.Killed` stays
      false.
  - A queued invocation refused before start (`*HaltedError`) → mechanism
    `halted:<origin>`, every unit `not_started`, as already planned.
- **`repo.go` `Runner.call`** (describe/list) uses the same `execRunner`. A
  halt or supervisor death is
  `RUNNER_PROTOCOL:<runner>|<verb>|halted:…` / `…|cleanup_unverified:…`.
- **`plan.go` / `run.go`:**
  - Export `Overlappable() bool`, which is `procsup.Available() == nil`.
  - When it is false (darwin), `Run` wraps the `InvokeFunc` in a per-run
    mutex. A contended invoke records `ParallelRefused = "containment"` and
    waits.
  - `RunReport.ParallelRefused string`. `cmd/ait-testmap/run.go` prints
    `PARALLEL_REFUSED:containment` before `RUN_ACCOUNTING` when it is set.
- **`cmd/ait-testmap/main.go`:** `run()` sends `args[0] == "__supervise"` to
  `procsup.SuperviseMain(args[1:])` before the verb table.

### Builtin scaffold: `goengines/internal/testmap/runner/builtin` (new)

- `Adapter{Name string; TestOnly bool; Describe func(*Env) ([]byte, error); List func(ctx, *Env, io.Writer) error; Run func(ctx, *Env, *runner.Manifest, *Results) int}`.
  - `Register(a)` panics on a duplicate and calls `runner.RegisterBuiltin`.
  - `TestOnly` is never registered by a production binary. A test asserts
    cmd's registry is empty.
- `Main(args []string, stdout, stderr io.Writer) int`:
  - `<name> describe|list|run --manifest <p>`.
  - An unknown name → `UNKNOWN_BUILTIN:<name>` and 64; a bad usage → 64.
  - `procsup.Available()` failing and `!TestOnly` → `CONTAINMENT_UNAVAILABLE:<platform>`
    on stderr, exit 3. A test-only adapter runs uncontained there, marked
    `Containment: none`.
- `Env` carries:
  - `Root`, `Runner`, `Command` (`AIT_TESTMAP_COMMAND`), `Accounting`,
    `RunID`;
  - `ReportDir` (via `OpenReportDir`) and `Entry` (`runners.yaml` lookup by
    name via `runner.LoadConfig`);
  - `Supervise(ctx, RunSpec) procsup.RunResult`, which is `procsup.Run`;
  - `DiscoveryBound() = runner.ListTimeout*9/10`, for native discovery.
- Helpers:
  - `ReadManifest(path)`: strict decode.
  - `Results`: `Start` and `Row` write `results.jsonl`; `Case` writes
    `cases.jsonl` in t1854_2's exact shape.
  - `Fresh(path)`: wraps `runner.FreshReport`.
  - `SplitCommand(s)` splits on whitespace. It refuses `$`, backtick, `;`,
    `|`, `&`, `<`, `>`, `\n`, `\r`, plus quotes and backslash (unsupported
    quoting, so it fails closed), and an empty command. Tools run through
    exec, never a shell.
- **`cmd/ait-testmap/builtin.go`:** `runRunner` dispatches to `builtin.Main`;
  its exits are `{0,1,2,3,64,75}`. `verbs.go` replaces `stub("runner")` with
  `{Name: "runner", Run: runRunner, Exits: runnerExits}`. `main_test.go`:
  `runner` leaves the stub list, and `TestRunnerVerb` covers usage,
  `UNKNOWN_BUILTIN:pytest` → 64, and an empty production registry.

## Implementation steps

0. **Host probe** (Step 0's "prove the subreaper behaviour", still before any
   code). A standalone Go program in the scratchpad must prove four things on
   this host and in an `env -i` shell:
   - (a) with the flag set, a `setsid` double-forked grandchild reparents to
     the probe;
   - (b) without it, the grandchild reparents elsewhere (the negative
     control);
   - (c) the kill-direct-children → reap → repeat loop ends in ECHILD, with
     the grandchild dead;
   - (d) a SIGKILLed middle process's children become the probe's direct
     children.

   The outputs are recorded verbatim in Final Implementation Notes.
1. **Task body and parent edits.**
   - Apply *Acceptance criteria revised* to the task body.
   - Edit the parent's G8/G8a rows, and record the withdrawn
     `AIT_TESTMAP_REQUIRE_CGROUP` decision.
   - Commit both via `aitask_task_commit.sh` with explicit paths.
2. **Move the session code.** Move `sweepSession`/`sessionProcs` and their
   tests (`TestSweepEnumeration`, `TestSweepUninspectableProcesses`,
   `injectStat`) into procsup. runner's callers use `procsup.SweepSession`.
   Everything is green before going on.
3. **procsup supervisor, client, halt and `Run`, with the procsup tripwire
   entry.** The entry is
   `{dir: "internal/procsup", name: "procsup", localStarters: ["Start", "Run", "SweepSession", "SuperviseMain"]}`,
   and `sweepSession` is removed from runner's entry. Tests use real
   processes; each starts with `hangguard.Isolated`, and helpers come from
   the test binary's `TestMain`. This preserves the task's list:
   - **timeout**: SIGTERM then kill;
   - **cancellation**: ctx;
   - **a child that ignores SIGTERM**: killed after the grace;
   - **a grandchild in its own process group**;
   - **a double-forked orphan**;
   - **a `setsid()` child, and a double-fork `setsid()` daemon**;
   - **a zombie**: a child leaves an unreaped grandchild and exits. The
     supervisor reaps it, reports `ok`, and does not hang;
   - **output past the cap**: truncated, flagged, bounded;
   - **the ECHILD proof**: a descendant that outlives the command keeps the
     supervisor from reporting `ok` until it is dead;
   - **the parent's death**: a helper process acting as the parent starts a
     supervisor, then is SIGKILLed. The supervisor sees EOF on the control
     pipe and cleans up its subtree, so the daemon is dead within the bound;
   - **supervisor death** (the residual and the halt):
     - two supervisors S1 and S2 are active, each holding a `setsid` daemon,
       and S1 is SIGKILLed via `OnStartForTesting`;
     - S1's `Wait` reports `SupervisorDied`, and the halt is set with S1's
       detail;
     - S2 is cancelled: its daemon is dead, its result is `Halted: true` and
       its cleanup is `ok`;
     - a later `Start` returns `*HaltedError`, and the helper's marker file
       proves nothing started;
     - S1's daemon is **asserted still alive**, documenting the residual.
       Teardown kills it explicitly;
   - **a malformed or missing status line** is `SupervisorDied`;
   - **halt/start interleavings, deterministic:**
     - Two `Start`s are paused at the two seams: P1 in
       `BeforeLaunchForTesting` (already reserved) and P2 in
       `BeforeAdmitForTesting` (not yet admitted).
     - Supervisor S1 is then SIGKILLed and its `Wait` sets the halt. The test
       waits until the halt is observable before releasing both.
     - **Expected:**
       - P1 launches, receives the cancel at activation, and returns `Halted`
         with its command dead (`cleanup: ok`);
       - P2 returns `*HaltedError`, and the launch log proves it never
         launched;
     - Mutants:
       - (l) halt snapshots only launched entries, not reservations → P1's
         command survives → red;
       - (m) admission reads the flag outside `admitMu` and registers after
         launch → red;
   - **omitted dispatch, bounded and non-recursive:**
     - procsup's own `TestMain` skips `MaybeSupervise()` when
       `AIT_TEST_OMIT_DISPATCH=1`; this is test code only.
     - An isolated test sets `HandshakeTimeout` to 1 s and calls `Start` with
       that env, so the child test binary runs its suite instead of
       supervising.
     - Every `Start` in any process appends one line to the file named by
       `AIT_TEST_LAUNCH_LOG` **just before it launches**, and the guard's
       refusal happens before that point.
     - Expected:
       - `Wait` returns `SupervisorDied: missing handshake` within 1 s plus a
         margin (asserted under 4 s);
       - the launch log holds **exactly one** line, the outer launch;
       - the hangguard reap finds no marked leftovers;
       - a direct unit check confirms `Start` with the sentinel in the env
         returns `*DispatchError` and launches nothing;
   - **bootstrap sentinel scrubbed:** the supervised command's environment
     (dumped by a helper) does not contain `AIT_PROCSUP_SUPERVISOR`, so a
     legitimate nested supervisor launch from a supervised builtin is never
     refused;
   - **the forced `CONTAINMENT_UNAVAILABLE` refusal.**
4. **Runner engine side.** `execRunner` through `procsup.Start`; the Record
   fields; `EndState.Halted` in `decide`; `Overlappable()`; the darwin-mode
   wrapper and `ParallelRefused`, plus the cmd `run.go` line. Add
   `procsup.MaybeSupervise()` to runner's `TestMain`. The existing
   `cleanup_linux_test.go` stays green unchanged. Add:
   - a script runner that leaves a `setsid` double-forked daemon: the daemon
     is dead when `Run` returns;
   - **halt inside a run**:
     - two invocations under the serial executor; invocation 1's supervisor
       is SIGKILLed via the hook;
     - invocation 1 records `mechanism`/`cleanup_unverified:supervisor_died:…`;
     - invocation 2 starts no process (marker absent), records
       `mechanism`/`halted:<invocation 1's detail>`, and its units are
       `not_started`;
     - the run exits 3;
   - **halt with a concurrent invocation**: through a parallel test
     executor, invocation B is cancelled when A's supervisor dies. B is
     recorded `halted`, its daemon is dead, and no B unit is `pass` unless it
     was terminal before the cancel;
   - **halted cases reconciliation (engine path):**
     - Invocation C runs a cases-accounting script runner: one invocation,
       four units, `timeouts: per_unit`, so start rows exist. Before C blocks
       on a go-file, it writes evidence for each unit:
       - U1 **complete**: a start row and every expected case row;
       - U2 **partial**: a start row and one of two expected case rows;
       - U3 **untouched**: nothing;
       - U4 **attributable error**: a start row, a duplicate case row and a
         truncated final line.
     - A parallel test executor runs a second invocation D, whose supervisor
       is SIGKILLed via the hook, triggering the halt and cancelling C.
     - **Expected for C:**
       - cause `mechanism`, detail `halted:<D's detail>`;
       - U1 keeps its derived `pass`, counters intact;
       - U2 is `missing` with `Started` true, never `timeout`;
       - U3 is `missing` (no start row), never `timeout` or `not_started`;
       - U4 is `error` with `duplicate_case` recorded as a protocol error, its
         truncated line ignored;
       - `TimedOut` is empty.
     - Mutants:
       - (n) `caseEvidence` keeps its `!res.Killed` early return → U1 becomes
         `missing` → red;
       - (o) `decide` attributes a halt through `AttributeKill` → U2 becomes
         `timeout` → red;
   - **the `ParallelRefused` wrapper**, with `Overlappable` forced false via a
     test hook: concurrent invokes serialize and the report carries
     `ParallelRefused`;
   - **no session signalling on Linux, on any path:** runner's `sweepSession`
     var is swapped for a recorder, and the recorder has **zero** calls in
     each of these cases:
     - (1) a clean invocation;
     - (2) a run whose supervisor is SIGKILLed mid-run (via the hook);
     - (3) **failure after completed cleanup:** the supervisor reaches ECHILD
       and then dies **before** writing its status. This is driven by a
       `SetDieAfterCleanupForTesting()` hook that TestMain enables in the
       supervising test binary from an env var; it is guarded by
       `testing.Testing()`.

     Case (3) also asserts:
     - the record is `mechanism`/`cleanup_unverified:supervisor_died:…`, and
       the halt is set;
     - an unrelated `setsid` process the test started before the run is still
       alive afterwards. Combined with the zero-call recorder, an unverified
       result cannot authorize signalling another session.
5. **`report_unix.go` `OpenReportDir`**, with tests: it refuses a
   non-directory, a link and a non-empty directory; a file written after open
   is fresh, a back-dated one is stale.
6. **The builtin scaffold, the cmd `runner` verb and the `__supervise`
   pre-dispatch, with `main_test.go`.**
   - The test binary's `TestMain` calls `procsup.MaybeSupervise()` and
     dispatches `runner <name> …` to `builtin.Main`, with
     `runner.SelfExe = os.Executable`.
   - `AIT_TEST_PROCSUP_UNAVAILABLE=1` is read **in TestMain only**.
   - The test-only adapter `echo` covers:
     - describe/list/run end to end through `runner.Run` (pass rows,
       `cases.jsonl` reconciled);
     - SplitCommand refusals, one per metacharacter;
     - `UNKNOWN_BUILTIN`;
     - the forced `CONTAINMENT_UNAVAILABLE` (a production-mode adapter →
       exit 3, mechanism).
   - **Builtin crash (engine path):** the builtin is SIGKILLed mid-unit while
     its supervised tool holds a `setsid` descendant. Nothing is left when
     `Run` returns: the tool supervisor's orphans reparent to the invocation
     supervisor and die with it.
   - **Real-process overlap (runs in CI):**
     - A and B run in parallel through a test executor;
     - A's builtin is SIGKILLed while it holds a `setsid` double-forked
       daemon;
     - B blocks on a go-file until A's daemon is confirmed dead, then checks
       that its own helper is still alive and reports pass;
     - expected: A's daemon is dead and A has a cause; B passes with no cause,
       and every one of B's processes survives until B exits.

   Add the builtin tripwire entry.
7. **Recursion invariant** (named extension of t1854_7's test). Add one
   isolated top-level test per entry of `procsup.Backends()`
   (`TestRecursionBackendSupervisor`), running every `recursionCases()` entry
   through `checkRecursion`. A coverage test asserts that the per-backend
   table equals `procsup.Backends()`. Add the `wrap=orphan` case (a `setsid`
   double fork plus `env -i`, refused via `ancestor:`).
8. **Red proofs.** Each is an isolated mutant, run, then restored
   byte-identical (checked with `git diff --stat` and a checksum):
   - (a) the supervisor skips `PR_SET_CHILD_SUBREAPER` → the `setsid`/daemon
     tests, the builtin-crash test and the orphan recursion case go red;
   - (b) cleanup stops once the command exits instead of at ECHILD → the
     ECHILD-proof test goes red;
   - (c) A's cleanup kills every engine descendant (the "engine-wide tree"
     mutant) → the overlap test's "B unaffected" goes red;
   - (d) halt does not cancel the other active supervisors → the
     supervisor-death test's S2 assertions go red;
   - (e) the halt flag is ignored by `Start` → "nothing started after halt"
     goes red, both in procsup and in the run;
   - (f) the supervisor ignores control-pipe EOF → the parent-death test goes
     red;
   - (g) one SplitCommand metacharacter is removed → its case goes red;
   - (h) a production adapter runs uncontained → the CONTAINMENT_UNAVAILABLE
     test goes red;
   - (i) the darwin-mode wrapper is removed → the ParallelRefused test goes
     red;
   - (j) the bootstrap guard is removed from `Start` → the omitted-dispatch
     test's launch log exceeds one line and goes red;
   - (k) `execRunner` restores a sweep after a supervision failure → case (3)
     of the no-session-signalling test goes red;
   - (l)–(m), the halt/start interleavings, and (n)–(o), the halted cases
     reconciliation, are as named in Steps 3 and 4.
9. **README Interfaces rows and text:**
   - `procsup` (`Start`/`Run`/`Available`/`Backends`), `__supervise` (fds,
     status line, internal), the halt rule, and the **supervisor-death
     residual**;
   - `runner.Overlappable` / `PARALLEL_REFUSED:containment` (darwin only),
     `runner <name>` / `UNKNOWN_BUILTIN`, and the `CONTAINMENT_UNAVAILABLE`
     support restriction;
   - the M3.1 residual text, and the G8/G8a evidence-contract rows.
10. **Checks:** `gofmt`, `go vet ./...`, `GOOS=darwin go vet ./...`,
    `./ci/preflight.sh`, `ait engine test`, and `ait engine cross` (the
    darwin build compiles).
11. **Notes:**
    - to **t1854_3**: `runner.Overlappable()` is true on Linux, so `errgroup`
      parallelism is safe there. `PARALLEL_REFUSED` is darwin-only. A halt
      cancels in-flight invocations and refuses queued ones (mechanism). The
      executor must pass its ctx through;
    - to **t1854_8–t1854_13**:
      - the G8/G8a revision;
      - the scaffold API (`builtin.Register`/`Adapter`/`Env`, `Supervise` →
        `procsup.Run`, `SplitCommand`, `DiscoveryBound`, `OpenReportDir`);
      - the required one-line `procsup.MaybeSupervise()` in any test binary
        that supervises;
      - the tripwire entry;
      - that each adapter records what it reads (t2081/t2082).

## Verification

- Every task acceptance criterion, as revised above, maps to a step:
  - timeout, cancellation, SIGTERM-ignore, own-group grandchild, orphan,
    `setsid` child and daemon, zombie, and output cap (Step 3);
  - builtin crash (Step 6) and the overlap test (Step 6, in CI);
  - the recursion invariant and the orphan case (Step 7);
  - CONTAINMENT_UNAVAILABLE (Steps 3 and 6);
  - supervisor death and the halt (Steps 3 and 4).
- `ait engine test` green; preflight green; darwin vet and cross build green.
- Red proofs (a)–(i) are recorded in Final Implementation Notes.

## Risk

### Code-health risk: medium
- Every contained start gains a process hop: a new internal `__supervise` entry and an fd protocol (control and status pipes) between engine and supervisor. A protocol bug can turn every runner start into a mechanism failure. Mitigated by:
  - a strict status decode;
  - the malformed and missing-status tests;
  - the move of the session sweep landing green on its own first (Step 2).

  · severity: medium · → mitigation: none (designed in; Steps 2–3)
- The engine's runner start path (`execRunner`, used by describe/list/run) changes for every runner on Linux. M3.1's `cleanup_linux_test.go` stays unchanged as the characterization. · severity: medium · → mitigation: none
- A test binary that supervises must call `procsup.MaybeSupervise()` in `TestMain`. Forgetting it makes the supervisor re-exec run the whole test suite. This is bounded in two ways (review finding, 2026-10-25):
  - **No recursion:** `Start`/`Run` refuse before any launch while the bootstrap sentinel is in the caller's env, and the genuine supervisor scrubs the sentinel before starting its command.
  - **Bounded time:** a missing handshake within `HandshakeTimeout` → the client SIGKILLs the misdispatched process.

  Pinned by the omitted-dispatch test and mutant (j). · severity: low · → mitigation: none (designed in)
- A session-number sweep after supervision could kill an unrelated session that reused the runner's session id, whether after a clean reap or after a failure whose original session is already gone (review findings, 2026-10-25). On Linux the engine therefore never signals by session number. The cost is best-effort cleanup after a supervisor failure, which the residual already documents. Pinned by the no-session-signalling test, including failure-after-completed-cleanup, and mutant (k). · severity: low · → mitigation: none (designed in)

- The halt adds cross-supervisor state. Without one critical section around admission and registration, a `Start` that overlaps a halt could escape both refusal and cancellation (review finding, 2026-10-25). It is designed as admit/reserve → launch → activate under `admitMu`, and the halt cancels reservations too. Pinned by the deterministic paused-Start test and mutants (l)–(m). · severity: medium · → mitigation: none (designed in)
- Introducing a non-timeout interruption touches M3.1/t1854_2's evidence path (`ValidateRows`/`ValidateCases` truncation tolerance, `caseEvidence`, `decide`). Treating a halt as neither a normal exit nor a kill would silently drop completed case evidence (review finding, 2026-10-25). `Interrupted()` is threaded through every kill special case, and `AttributeHalt` is separate from `AttributeKill`. Pinned by the four-unit halted cases test and mutants (n)–(o). · severity: medium · → mitigation: none (designed in)

### Goal-achievement risk: medium
- G8a is narrowed: membership survives every test-code process's death, but not the supervisor's own. A same-uid test can kill the supervisor, and its subtree may then be left running. This is detected, recorded `cleanup_unverified` and halts all work, but it is not prevented. Accepted by the user (2026-10-24) as a stated residual; the hardening is deferred. · severity: medium · → mitigation: supervisor_cgroup_hardening
- Revising acceptance criteria that siblings copy (the G-table in t1854_8–13, t1854_3's parallel assumption) could leave them planning against the old G8a. Step 1 edits the parent, and Step 11 sends notes to every affected sibling. · severity: low · → mitigation: none (Step 11)

### Planned mitigations
- timing: after | name: supervisor_cgroup_hardening | type: enhancement | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: supervisor death can leave its subtree running | desc: Place each supervisor in a delegated cgroup v2 leaf where one exists, so the kernel keeps membership after the supervisor's own death; add it to procsup.Backends() and the recursion invariant; CI delegation and an AIT_TESTMAP_REQUIRE_CGROUP-style knob are decided there

Dispositions carried over from the first design: `ci_cgroup_delegation_coverage`
is replaced by `supervisor_cgroup_hardening`, following the user's 2026-10-24
"defer cgroup hardening". `procsup_pidfd_kill` is dropped: the supervisor
signals only its own unreaped children, so the pid-reuse window it closed no
longer exists.

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival on the
current branch, no merge).
