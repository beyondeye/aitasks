---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
followup_kind: upstream_defect
created_at: 2026-10-25 09:00
updated_at: 2026-10-25 09:00
---

## Origin

Spawned from t1854_6 (M3.2c supervised execution) during Step 8b review.

## Upstream defect

- `goengines/internal/testmap/runner/exec_unix.go:execUnsupervised` — the darwin (unsupervised) path sweeps the runner's session after `cmd.Run` has reaped the runner, so the session number can in principle have been reused by an unrelated session (pre-existing M3.1 behaviour, kept unchanged by t1854_6 and documented as a residual of the unsupervised path).

## Diagnostic context

t1854_6 moved Linux execution onto a dedicated per-start supervisor (`internal/procsup`). Two review findings there established that a session-number sweep is sound only while the session is known to still have its original members:

- After the runner has been reaped, nothing pins the session id.
- If every member is gone, the number can be reallocated, and the sweep's `sid == S` then identifies whichever session holds the number now.

On Linux the engine therefore never signals by session number. The darwin path (`procsup.Available()` fails; no `PR_SET_CHILD_SUBREAPER`) still runs M3.1's `execUnsupervised`: `exec.CommandContext` + `Setsid` + `cmd.Run()` (which reaps the runner), then `sweepSession(cmd.Process.Pid, SweepTimeout)`. `procsup.SweepSession` documents the precondition.

Production builtin adapters refuse on darwin (`CONTAINMENT_UNAVAILABLE`), so this affects only project script runners there. darwin is compiled and vetted only (no CI execution).

## Suggested fix

Keep the session pinned until the sweep is done: start the runner without letting os/exec reap it (e.g. `os.StartProcess` + a sweep loop that runs while the leader is still an unreaped zombie, then `wait4` the leader last), or sweep only members that are confirmed descendants. Pin it with a darwin-only test, plus a code-level assertion on Linux CI that the sweep runs before the reap.
