---
priority: low
effort: medium
depends: []
issue_type: test
status: Ready
labels: [testing, tmux]
created_at: 2026-06-03 23:15
updated_at: 2026-06-03 23:15
---

Surfaced by the t926 periodic macOS compat audit (full test suite run on macOS).
Not macOS-specific — environmental / test-infrastructure.

## Problem

8 tmux / multi-session tests abort with exit 2 and the message:

```
ERROR: <test>.sh refuses to run while other tmux sessions are alive.
Detected sessions on the default socket: aitasks
...
```

They each isolate their own tmux server but additionally **refuse to run if ANY
tmux session exists on the default socket** (a belt-and-suspenders guard added
after historical leaks killed users' main servers). On any developer machine
with a live `tmux` session (very common), these 8 tests cannot run, so the full
suite can never be green locally without first detaching/killing tmux.

## Affected tests (all exit 2, all the same guard)

- `tests/test_kill_agent_pane_smart.sh`
- `tests/test_multi_session_monitor.sh`
- `tests/test_multi_session_primitives.sh`
- `tests/test_tmux_control.sh`
- `tests/test_tmux_control_resilience.sh`
- `tests/test_tmux_exact_session_targeting.sh`
- `tests/test_tmux_run_parity.sh`
- `tests/test_tui_switcher_multi_session.sh`

## Suggested direction

Investigate whether these tests can run safely alongside a user's live tmux by
relying solely on a dedicated isolated socket (`tmux -L <unique_socket>`) for
all server/session operations, so the "other sessions alive on the default
socket" precondition can be dropped (or scoped to only the test's own socket).
The guard exists for a real reason (do NOT simply remove it) — the fix must keep
the user's default-socket server untouched while letting the tests proceed. If
full isolation is proven safe, relax the guard to check only the test's own
socket; otherwise document that these tests require a tmux-free terminal and add
a skip-with-clear-message path so they don't count as hard failures in suite
runs.

## Verification

After the change, the 8 tests run to completion (PASS) from a terminal that has
an unrelated live tmux session, and the user's existing session/panes are
provably untouched.
