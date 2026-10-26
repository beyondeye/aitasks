---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tmux, test_infrastructure]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [2147]
assigned_to: dario-e@beyond-eye.com
anchor: 1689
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-26 08:04
updated_at: 2026-10-26 11:38
---

## Origin

Spawned from t1689 during Step 8b review.

## Upstream defect

- `tests/test_tmux_pane_for_pid.sh:48 — macOS: -L ait_panepid_<pid> under the isolated TMUX_TMPDIR in $TMPDIR exceeds the AF_UNIX sun_path limit ("File name too long"); the test fails before any assertion (same on unmodified HEAD)`
- `tests/test_lock_anchor_tmux_live.sh:156 — same macOS socket-path-length failure for -L ait_anchorlive_<pid>; "could not start a test pane" (same on unmodified HEAD)`
- `tests/test_bounded_run.py:58 — _read_pid's 5s readiness bound flakes under load (TestCrewGitTimeout.test_git_cmd_timeout_reports_124 failed once in a full run; passes in isolation)`

## Diagnostic context

While verifying t1689 on macOS (Darwin 24.6), the two live tmux tests failed before their first assertion. With stderr left visible, tmux reports
`error connecting to /private/var/folders/<hash>/<hash>/T/ait_isolated_tmux_501/tmux-501/ait_panepid_<pid> (File name too long)`.
`require_isolated_tmux` (tests/lib/tmux_isolation.sh) points TMUX_TMPDIR at `${TMPDIR}/ait_isolated_tmux_<uid>`, and macOS's $TMPDIR is ~53 bytes. Add tmux's `tmux-<uid>/` and a long `-L` name, and the socket path passes the ~104-byte `sun_path` limit (the t1729 class, which `tests/test_tmux_exec.py::_short_socket_tmpdir` already works around with a short `/tmp` dir). Both tests fail identically on a detached worktree at the pre-t1689 HEAD, so they predate t1689. A shorter probe socket name in the same dir succeeds, so the length is the cause.

Separately, one full `tests/run_all_python_tests.sh` run failed only in `test_bounded_run.TestCrewGitTimeout.test_git_cmd_timeout_reports_124`: "fixture never wrote …/child.pid", raised by `_read_pid`'s 5-second readiness deadline. Other test processes were running on the machine at the time. The module passed 5/5 in isolation, and a clean full re-run passed.

## Suggested fix

- Socket path: give these tests a short fixture `TMUX_TMPDIR` (as `_short_socket_tmpdir` / `tests/test_tmux_spawn_path_live.sh` do with `mktemp -d /tmp/...`) and/or shorter `-L` names. Consider making `require_isolated_tmux` itself prefer a short base dir on macOS, so every adopting test benefits.
- bounded_run: raise or scale `_read_pid`'s readiness bound (it is a readiness wait, so a generous ceiling costs nothing when the fixture is quick).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-26T07:50:36Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-26T09:35:01Z status=pass attempt=1 type=human
