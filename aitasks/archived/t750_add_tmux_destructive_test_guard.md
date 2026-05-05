---
priority: high
effort: low
depends: []
issue_type: test
status: Done
labels: [testing, tmux, crash_recovery]
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-05 09:39
updated_at: 2026-05-05 09:50
completed_at: 2026-05-05 09:50
---

Add a pre-flight guard to all 8 destructive tmux tests that aborts with a clear error message when run from inside an existing tmux session or while other user tmux sessions are alive on the default socket.

## Background

The destructive tmux tests create and tear down their own tmux server via `TMUX_TMPDIR=$(mktemp -d)` + `tmux kill-server` cleanup, intended to keep their state isolated from the user's main tmux server. In practice, leak paths in `kill-server` cleanup, pane-id collisions, and control-client teardown have historically cascaded into the surrounding user tmux server, killing every pane inside it — including long-running TUIs (codebrowser, brainstorm, monitor), shells, editors, and background agents — with possible data loss.

This is the exact risk class flagged in `feedback_tmux_stress_tasks_outside_tmux.md` (memory): "for tasks whose tests destructively manipulate tmux (kill -KILL clients, kill-session, kill-server), surface the risk and recommend running implementation from a shell outside the user's aitasks tmux."

## Scope

- New shared helper: `tests/lib/require_no_tmux.sh` exposing `require_no_tmux()` that aborts (`exit 2`) with actionable recovery instructions on either condition.
- Wire the helper into 8 destructive tmux tests:
  - `tests/test_kill_agent_pane_smart.sh`
  - `tests/test_multi_session_monitor.sh`
  - `tests/test_multi_session_primitives.sh`
  - `tests/test_tmux_control.sh`
  - `tests/test_tmux_control_resilience.sh`
  - `tests/test_tmux_exact_session_targeting.sh`
  - `tests/test_tmux_run_parity.sh`
  - `tests/test_tui_switcher_multi_session.sh`

## Guard semantics

1. `[[ -n "${TMUX:-}" ]]` — refuse to run inside a tmux pane.
2. `tmux list-sessions` returns 0 — refuse to run while any user tmux server is reachable on the default socket. Names the offending sessions.
3. Insertion point: after the test's tmux/Python availability `SKIP` checks, before any `mktemp`/`new-session` operation.

## Outcome

A user attempting to run any of the 8 tests from inside their `aitasks` tmux session (or with any tmux session alive) gets a clear, actionable message and exit code 2. They are explicitly told to run from a fresh terminal outside tmux, and to `tmux kill-server` only after saving any in-progress work.
