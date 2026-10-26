---
Task: t2148_procsup_tests_leak_on_hosted_runner.md
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: fix procsup test leaks on hosted runners (t2148)

## Context

`main`'s required `Go engines check` → `check` job fails in `go test ./...` at
`internal/procsup`. hangguard reports processes carrying the test's marker
still alive after the isolated subprocess exits:
`LEAK:TestHaltStartInterleavings|…:sleep` (3/3 hosted runs) and
`LEAK:TestSupervisorDeathHalts|…:sh` (1/3). Because `go test` fails, nothing
after it in the job gets CI coverage.

## Root cause (reproduced, not hypothesised)

There are two defects, both in the tests' own cleanup of the residual
processes they leave on purpose. Neither is in the detector or in procsup's
production code.

1. **Deterministic, `TestHaltStartInterleavings`: dash forks the last
   command.** On Ubuntu `/bin/sh` is **dash**. `dash -c "sleep 300"` forks
   `sleep` as a child of `sh` and does not exec it. bash, this dev box's
   `/bin/sh`, execs it. So `s1.Pid()` is the `sh`. The supervisor's death
   leaves both `sh` and `sleep` behind, and `killAfter(t, s1.Pid())` (a bare
   `SIGKILL` of one pid) kills only the `sh`. The orphaned `sleep` survives
   every time.
   - Evidence: the test binary built here (`CGO_ENABLED=0 go test -c`) and run
     in `docker run --init ubuntu:24.04` (where `/bin/sh` is dash) gives
     **3/3 LEAK `…:sleep`**. The same container with `/bin/sh` relinked to
     bash **passes**. In the container, `sh -c "sleep 3"` shows `comm=sh`
     with one child.
2. **Racy, `TestSupervisorDeathHalts`: signal without wait, and an unkilled
   residual.** s1's command (`sh -c "setsid sleep 300 & …; wait"`) outlives
   its dead supervisor, and the test never kills it. It exits on its own only
   after cleanup `SIGKILL`s its daemon d1. `killAfter` also does not wait for
   the signalled process to die. hangguard's `reapMarked` scans as soon as the
   subprocess exits, so the still-running `sh` (and the just-signalled
   `sleep`) are reported.
   - Evidence: in the container with `--cpus 1` plus 4 busy loops, `-count=80`
     gives **2/80 LEAK `…:sh,…:sleep`**.

The detector is right: every process it reports really was alive when the test
ended. No grace is added to `reapMarked`, and hangguard is not touched.

## Change: one file, `goengines/internal/procsup/supervise_linux_test.go`

Replace `killAfter` (lines 43-47) with a cleanup that is **scoped by
ownership**, not by a bare number. `SweepSession` is deliberately **not**
reused. Its doc (`session_unix.go`) says it is sound only while the caller
knows the session still has its original members. Several residual numbers
here (`d2`, `sup`) are expected to be dead by cleanup, and a numeric session
match proves nothing about who owns the process.

### Ownership: a per-run environment token

```go
// ownerEnv marks the processes a test starts, so its cleanup can tell its
// own residuals from an unrelated process that reused a pid or session number.
const ownerEnv = "AIT_PROCSUP_TEST_OWNER"

// markOwned gives every process the test starts from here on — supervisors,
// commands, their daemons, all of which inherit this process's environment —
// an entry unique to this run, and returns it as "<ownerEnv>=<value>".
func markOwned(t *testing.T) string
```

`markOwned` builds `<test name>|<pid>.<unixnano>` and calls `t.Setenv`. These
tests are not parallel, and each runs alone in its hangguard subprocess, so the
setenv is scoped to that run. `Start` with a nil `Spec.Env` uses this process's
environment (`procsup.go:106`), and the supervisor strips only the bootstrap
sentinel (`supervisor_linux.go`), so the token reaches every fixture process.
The re-exec'd parent in `TestSuperviseParentDeath` inherits it as well
(`exec.Command` with nil `Env`).

### Cleanup: owned **and** in a documented residual session

```go
// sweepResidualAfter makes sure the residual session sid — a dead
// supervisor's command (started with setsid) or a setsid daemon, left alive on
// purpose — does not outlive the test. At cleanup it kills every process in
// sid that carries owner, then returns once none is alive. It kills every
// member, not only the leader, because /bin/sh may fork its last command
// rather than exec it (dash does), so the leader's pid alone misses the
// process doing the work. And it waits, because the hang guard scans as soon
// as the test's process exits, and a process merely signalled may still be
// running then. A process without owner is never signalled, whatever its
// session or pid, so a reused number is harmless. Owned processes outside the
// residual sessions are left for the hang guard to report.
func sweepResidualAfter(t *testing.T, owner string, sid int)
```

The cleanup body is a bounded loop (bound `SweepTimeout`, plus a confirming
empty scan, the same execve-window reasoning as `reapMarked`). Each pass:

1. Scan `/proc`. Candidates are processes, other than this one, whose
   `environ` holds `owner` exactly (NUL-separated match, like hangguard's
   `hasEntry`), whose `stat` session is `sid`, and whose state is not Z/X. The
   package's existing `parseStat` (`session_linux.go`) reads the
   session/zombie fields. A vanished process (ENOENT/ESRCH) is skipped.
   EACCES/EPERM means another uid, which cannot be ours, so it is skipped too.
2. For each candidate, kill it **through a process handle**, using only the
   standard library. No syscall numbers are written here: the internal
   tables differ by arch, for example MIPS 4424/4434 and MIPS64 5424/5434.
   ```go
   p, _ := os.FindProcess(pid) // Linux: opens a pidfd; falls back to a bare pid
   defer p.Release()
   err := p.WithHandle(func(uintptr) { // Go 1.26+ (module says go 1.26.0)
   	// The handle pins the process for this callback: re-check ownership now.
   	if ownedIn(pid, owner, sid) {
   		sigErr = p.Signal(syscall.SIGKILL) // handle mode: pidfd_send_signal
   	}
   })
   ```
   - `WithHandle` succeeded → the post-acquisition re-check decided. If the
     pid was recycled before the handle was opened, the re-check reads the
     new process, finds no token, and nothing is signalled. If it was
     recycled after, the handle still names the original, so `Signal`
     reaches only that process (or reports `ErrProcessDone`).
   - `os.ErrNoHandle` → `FindProcess` fell back to a numeric pid (no pidfd:
     kernel < 5.4, seccomp, …), and **no identity guarantee holds**. Do not
     signal: record it ("no process handle for residual pid N") so the loop
     ends in `t.Errorf`, failing closed instead of falling back to
     `kill(pid)`.
   - `os.ErrProcessDone` → it exited between the scan and the open: gone.
   - A `Signal` error other than `ErrProcessDone` is kept and reported if the
     bound passes.
3. Clean means no candidate in a pass, confirmed by a second empty pass
   `confirmDelay`-ish later. Waiting is read-only and identity-free: there
   are no signals, only re-scans.
4. Past the bound: `t.Errorf("residual session %d outlived the test: %v", …)`
   with the pids still present, or the scan errors. It never claims a
   cleanup it did not observe.

### Call sites

- `TestSuperviseParentDeath`: `owner := markOwned(t)` before the parent
  starts. `killAfter(t, daemon)` and `killAfter(t, sup)` become
  `sweepResidualAfter(t, owner, daemon|sup)`. These are safety nets: both are
  asserted dead, and a stale number is now harmless.
- `TestSupervisorDeathHalts`: `markOwned` before `s1`. Add
  `sweepResidualAfter(t, owner, s1.Pid())` right after s1 starts. This is the
  residual that was never killed (defect 2). `d1` and `d2` move to
  `sweepResidualAfter`, and `d2` is a safety net. Update the doc comment: the
  residual is the dead supervisor's command and its daemon.
- `TestHaltStartInterleavings`: `markOwned` before `s1`.
  `killAfter(t, s1.Pid())` becomes `sweepResidualAfter(t, owner, s1.Pid())`,
  which takes the `sh` and its forked `sleep` (defect 1).

### New test (ownership evidence): `TestResidualSweepSparesUnowned`

This test is hangguard-isolated, as the tripwire requires. It starts
`sleep 300` with `Setsid` from `exec.Command`, with an environment that lacks
the token. It then runs the sweep for that session with a token the process
does not carry, and asserts that the process **is still alive** afterwards.
It also starts an owned process in a session, sweeps it, and asserts it is
gone, which covers the positive path in-process. Its own cleanup kills and
`Wait`s its unowned child.

To keep this testable, the cleanup body is a plain function
`sweepOwned(owner string, sid int, bound time.Duration) error`, which
`sweepResidualAfter` wraps in `t.Cleanup`.

Production code, `SweepSession` and hangguard stay unchanged.

### Post-phase (risk mitigations)
- **hosted_ci_step_triage** (Verification step 5): for each hosted run, list
  per-step conclusions (`gh run view <id> --json jobs`). Step results are
  **diagnostic evidence only**. The acceptance stays **≥3 runs whose whole
  `check` job is green**.
  - If any step fails, the procsup tests included, investigate the root cause
    from the logs before classifying it. A failure caused by this change, or
    another procsup or hangguard defect, is fixed here.
  - Call a failure "unrelated" only with log evidence that it does not
    involve this change. Then record the run id, step and excerpt under
    "Upstream defects identified" (Step 8b offers the follow-up).
  - **A follow-up does not satisfy the acceptance.** While three full green
    jobs are missing, the acceptance stays **unmet**. Do not archive t2148 as
    complete. Stop and ask the user whether to keep the task in flight until
    the blocker lands, or to revise the acceptance explicitly.

## Verification

1. Locally: `gofmt -l`, `go vet ./...`, `go test -count=5 ./internal/procsup/`,
   `go test ./internal/testsupport/hangguard/` (detector controls and
   tripwire), and `./ci/preflight.sh`.
2. In the dash container (`ubuntu:24.04 --init`, static test binary): the full
   procsup package `-count=5` gives 0 LEAK.
3. Stress in the dash container (`--cpus 1`, 4 busy loops):
   `-run 'TestSupervisorDeathHalts|TestHaltStartInterleavings' -count=80`
   gives 0 LEAK (it was 2/80 and 3/3 before).
4. **Negative controls.** Build mutants from an isolated scratch copy of the
   package (a `git worktree` under the scratchpad, or copying the module).
   Never edit and restore the shared tree.
   - mutant A: `TestHaltStartInterleavings` back to a pid-only `SIGKILL` of
     `s1.Pid()` → the dash container reports `LEAK:…:sleep`. The detector
     still catches the original bug.
   - mutant B: drop the `d1` sweep in `TestSupervisorDeathHalts` → the
     deterministic `LEAK:TestSupervisorDeathHalts|…:sleep` (local and
     container). A real leak still fails.
   - mutant C: remove the in-`WithHandle` ownership re-check and the environ
     filter from `sweepOwned` → `TestResidualSweepSparesUnowned` fails. The
     ownership test has teeth.
5. Hosted CI acceptance: ≥3 runs with the **full `check` job green**. This is
   outward-facing, so it waits for confirmation. Push a throwaway branch with
   the fix commit, run `gh workflow run goengines-check.yml --ref <branch>`
   three times, triage per the post-phase above, then delete the branch.

## Risk

### Code-health risk: low
- Test-only change in one file. It adds a small handle-based cleanup helper
  (standard-library `os.Process.WithHandle`, no syscall numbers) and touches
  neither production code nor the detector. Where no handle is available it
  fails closed with an error, never an unscoped kill. A cleanup may now take up to
  `SweepTimeout` on a failing test · severity: low · → mitigation: none
  needed (mutant C and the new test cover the helper)

### Goal-achievement risk: medium
- "≥3 green `check` runs" covers the whole job. Every step after `go test`
  (cross-build, sums loop, structure guard, build.sh/benchci.sh tests, annot
  sync guard, export-integrity tests) has had no hosted coverage since
  procsup landed. One of them may fail, so the job stays red even though
  procsup is fixed. If that happens the acceptance stays unmet, and the user
  decides · severity: medium (residual — triaged and surfaced, never
  redefined, by inline post-phase hosted_ci_step_triage) ·
  → mitigation: inline post-phase hosted_ci_step_triage
- The container reproduces dash, but not the runner's exact kernel or
  scheduling. Another timing-only leak in a procsup test could still appear
  only on hosted runners · severity: low ·
  → mitigation: dash_parity_local_tests

### Planned mitigations
- timing: post-phase | name: hosted_ci_step_triage | type: bug | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: later check-job steps may fail and keep the job red | desc: read hosted runs per step as diagnostics; investigate any failure before classifying; acceptance stays 3 full green check jobs — unmet ⇒ no archive-as-complete, ask the user
- timing: after | name: dash_parity_local_tests | type: test | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: hosted-only shell/timing differences invisible on bash-/bin/sh dev boxes | desc: let the Go suite (or preflight) run under dash locally (docker/bwrap recipe or CI matrix) so fork-vs-exec differences surface before the push

## Step 9

Post-implementation: commit the code (`bug: … (t2148)`) and the plan
separately, then run the hosted CI probe (step 5). Archive via Step 9 of the
task workflow (current-branch mode, no merge) **only if** the full-job
acceptance is met, or the user has explicitly revised it.

## Implementation progress (2026-10-26)

- [x] `supervise_linux_test.go`: `killAfter` removed; `markOwned` / `sweepResidualAfter` /
  `sweepOwned` / `ownedIn` / `ownedProc` / `killOwned` added (stdlib `os.FindProcess` +
  `Process.WithHandle`, ownership re-checked inside the handle callback, `ErrNoHandle` → no
  signal, reported); call sites updated in TestSuperviseParentDeath, TestSupervisorDeathHalts
  (+ new sweep of `s1.Pid()`), TestHaltStartInterleavings; new `TestResidualSweepSparesUnowned`.
- [x] Verification 1: gofmt clean, `go vet ./...` ok, procsup `-count=3` ok locally, hangguard ok,
  `ci/preflight.sh` ok.
- [x] Verification 2: dash container (`ubuntu:24.04 --init`), full procsup `-count=5`: PASS, 0 LEAK.
- [x] Verification 3: dash container `--cpus 1` + 4 busy loops, the four affected tests `-count=80`:
  PASS, 0 LEAK (pre-fix: 2/80 and 3/3).
- [x] Verification 4 (mutants built from scratch copies of the module):
  A pid-only kill → `LEAK:TestHaltStartInterleavings|…:sleep` 3/3 (dash);
  B no d1 sweep → `LEAK:TestSupervisorDeathHalts|…:sleep` 3/3 local and 3/3 dash;
  C ownership checks removed → `TestResidualSweepSparesUnowned` fails
  ("a sweep of the unowned session killed: unowned true").
- [ ] Verification 5 / post-phase hosted_ci_step_triage: pending (needs a pushed probe branch).

## Post-Review Changes

### Change Request 1 (2026-10-26 14:05)
- **Requested by user:** (1) `ownedProc` failed the whole scan on an unreadable stat of an
  *unrelated* process (an EACCES on pid 1 made a sweep of an empty session fail) — place such a
  process by getsid like `SessionProcs`, keeping an error only for an unverifiable member of the
  target session; (2) mutant C removed both ownership filters, so nothing proved the in-handle
  re-check alone — add a focused `killOwned` check.
- **Changes made:** `ownedProc` now falls back to `getsid` on an unreadable stat: another session →
  skipped; gone → skipped; member of `sid` or unknown session → error (never killed, never clean).
  `TestResidualSweepSparesUnowned` now calls `killOwned` directly on an unowned pid and on an owned
  pid of another session, and asserts neither is signalled. New isolated
  `TestResidualSweepUninspectable` (reusing `injectStat` / `startSession`): an uninspectable
  unrelated process does not fail the sweep; an uninspectable member makes it fail and is not killed.
- **Re-verified on the final code:** local vet/gofmt/procsup ×3/hangguard/preflight ok; dash
  container full procsup ×5 PASS; dash stress ×80 PASS (0 LEAK); mutants rebuilt from scratch copies
  of the final code: A → `LEAK:TestHaltStartInterleavings|…:sleep` 3/3, B →
  `LEAK:TestSupervisorDeathHalts|…:sleep` 3/3, D (in-handle re-check removed only) →
  "killOwned signalled the unowned process", E (getsid fallback reverted) → "an uninspectable
  process of another session failed the sweep … permission denied".
- **Files affected:** `goengines/internal/procsup/supervise_linux_test.go`

## Final Implementation Notes
- **Actual work done:** Root-caused both hosted-only leaks (dash forks the last command of
  `sh -c`, so a pid-only kill of the dead supervisor's command leaves its `sleep`; and the cleanup
  never killed s1's `sh` and never waited for signalled processes before hangguard's scan). Replaced
  `killAfter` with an ownership-scoped, waiting sweep of each documented residual session
  (`markOwned` env token + session filter + pidfd kill via `os.Process.WithHandle` with an in-handle
  ownership re-check; `ErrNoHandle` fails closed). Added `TestResidualSweepSparesUnowned` and
  `TestResidualSweepUninspectable`. Test-only; production code and hangguard untouched.
- **Deviations from plan:** Two review rounds before implementation replaced the first design
  (`SweepSession` by bare session number) with the ownership-scoped design, and raw pidfd syscall
  numbers with the stdlib handle API. Post-review: getsid fallback for unreadable stats, and a
  direct `killOwned` check (Change Request 1).
- **Issues encountered:** Not reproducible on the dev box because `/bin/sh` is bash there; reproduced
  deterministically in `docker run --init ubuntu:24.04` with a static `go test -c` binary, and the race
  under `--cpus 1` + busy loops.
- **Key decisions:** Fix the tests, not the detector: everything hangguard reported really was alive.
  Ownership by a per-run env token rather than session numbers (no stale-number kills); sweep only
  documented residual sessions so hangguard still reports any other leak.
- **Upstream defects identified:** None
