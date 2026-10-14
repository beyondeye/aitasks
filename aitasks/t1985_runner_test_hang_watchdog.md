---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
followup_kind: review_finding
created_at: 2026-10-14 17:26
updated_at: 2026-10-14 17:26
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
