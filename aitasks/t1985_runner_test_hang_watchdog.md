---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: test
status: Implementing
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: review_finding
implemented_with: claudecode/opus5_5
created_at: 2026-10-14 17:26
updated_at: 2026-10-14 19:09
---

## Context

Review finding from t1854_1 (M3.1, runner contract), dispositioned as a
follow-up by the reviewer. The runner package's timing tests assert a bound
only **after** the run returns:

- `timedRun` in `goengines/internal/testmap/runner/timeout_run_test.go`;
- the in-loop check in `TestRunReportFilesAreSafe` (`run_test.go`).

Both call `Run` synchronously. A regression that makes `Run` hang (a
reintroduced blocking report read, a sweep that never terminates, a
`WaitDelay` lost from `execRunner`) never reaches either assertion. The test
then waits for the suite-level `go test -timeout` (10 min by default). That
is what the t1854_1 red proof showed: reverting `readReport` to a plain
`os.ReadFile` failed only as a 60 s test timeout.

## Goal

Every runner test that exercises a deadline, kill or report-read path fails
within its own bound, quickly and with a clear message, when `Run` hangs,
and leaves no process behind.

- Prefer an **isolated test subprocess**. The test re-execs the test binary
  (`os.Args[0] -test.run=<name>` with an env marker) under its own deadline,
  in its own session, so the parent can SIGKILL the whole session on expiry
  and report `HANG:<test>|<limit>`.
- A goroutine-plus-timer watchdog alone is not enough: the blocked `Run` and
  the runner processes it started would leak into the rest of the suite.
- Cover at least `TestTimeout*`, `TestCleanup*`, `TestKilledRunValidatesRows`
  and `TestRunReportFilesAreSafe`.

## Verification

- A red proof per watchdog: with a hang reintroduced (for example
  `readReport` back to `os.ReadFile` with a FIFO), the guarded test fails
  within its bound, not the suite timeout, and no `sleep` process from the
  fixture survives. Check `/proc` or `pgrep -s` for the subprocess session.
- `ait engine test` stays green, and the suite's wall time does not grow
  materially.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1854_1** id=2026-10-14T15:47:31Z.d9630f36c6a45effa173bdab from=t1854_1 at=2026-10-14T15:47:31Z base=7f1d0614a333c14f0130789c8a22e2233e6d9db0 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_1 (M3.1, archived; runner package landed in 3d1a2b628). This relays a scope decision the user made on 2026-10-14 in the t1854_1 session. The decision is quoted, not verified by you: confirm it with the user if it conflicts with your plan.
> | 
> | **The decision:** t1985's watchdog must be **reusable by M3.2 (t1854_2)**, and t1854_2 is being made to depend on t1985.
> | 
> | **Why:** M3.2's builtin runners (bash-file, pytest, go-test, gradle-class, suite, device) live in `goengines/internal/testmap/runner/builtin/`. The M3.1 contract requires each builtin to prove its timeout enforcement and process cleanup with its own tests. Those are exactly the tests that need your hang/leak guard. But a helper defined in package `runner`'s `_test.go` files cannot be imported from another package's tests.
> | 
> | **What this asks of the design:**
> | - Ship the isolated-subprocess watchdog as a small importable **non-test** package, for example `goengines/internal/testmap/runnertest`. The name is a suggestion, not a requirement.
> |   - Its API is testing-only: it takes `*testing.T` / `testing.TB`.
> |   - It uses a linux build tag where it needs `/proc`.
> |   - It covers the pieces your plan calls `runChild` / `isolated` / `problems` / `reapMarked` / `markedProcs`.
> | - Have `runner`'s own guarded tests consume it, so it is exercised from day one.
> | - Keep the negative controls (hang / leak / fail / no-such-test) against the package itself.
> | - Keep test-only code out of the production binary. An `internal/` package imported only by `_test.go` files is never linked into `ait-testmap`.
> | 
> | **Moment-relative, may already be stale:** as of this message, your plan draft (`glowing-beaming-treehouse.md`) places these helpers in `runner/*_test.go` files.
> | 
> | Advisory input only; your own planning, gates and review decide.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-14T16:09:50Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-15T05:53:48Z status=pass attempt=1 type=human
