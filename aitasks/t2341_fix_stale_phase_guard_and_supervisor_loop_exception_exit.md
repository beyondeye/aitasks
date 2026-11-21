---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tmux, monitor]
gates: [risk_evaluated]
anchor: 2051
followup_kind: upstream_defect
created_at: 2026-11-21 20:21
updated_at: 2026-11-21 20:21
---

## Origin

Spawned from t2051 during Step 8b review.

## Upstream defect

- `tests/test_workflow_phase_standalone.sh:155-157 — Guard 3 expects 2 matches of 'agent_key_from_command(shadow_command)' in minimonitor_app.py; the committed file has 0, so the test fails at HEAD`
- `.aitask-scripts/monitor/monitor_core.py:_supervisor_loop — any exception other than CancelledError raised by a reconnect's start() ends the supervisor task silently and leaves the backend in RECONNECTING forever`

## Diagnostic context

Both were found while running the regression sweep for t2051 (control clients moved to the `_ait_control` helper session). Neither is caused by that change.

1. `bash tests/test_workflow_phase_standalone.sh` fails "Guard 3: two documented shadow-side sites" (expected 2, actual 0). The guard counts a literal call in `.aitask-scripts/monitor/minimonitor_app.py`. t2051 did not touch that file, and `git show HEAD:.aitask-scripts/monitor/minimonitor_app.py | grep -c 'agent_key_from_command(shadow_command)'` was 0 before the t2051 commit. The last commit to that file was t2309. Either the two shadow-side call sites were removed or reshaped (then the guard and its comment are stale), or they should still exist.

2. During t2051 a new probe inside `TmuxControlClient.start()` raised `AttributeError`. `TmuxControlBackend._supervisor_loop` catches only `asyncio.CancelledError`, so the supervisor task ended, nothing logged it, and the backend stayed in `RECONNECTING` with no further reconnect attempts and no transition to `FALLBACK`. The t2051 probe was made unable to raise, but the loop itself still has this failure mode for any future exception in `start()`.

## Suggested fix

1. Check what t2309 did to the two shadow-side sites, then either restore the expected call shape or update the guard's pattern, count and comment to the current code.
2. In `_supervisor_loop`, treat an unexpected exception from a reconnect attempt as a failed attempt (count it, keep the backoff), so the loop still ends in `FALLBACK`; add a test that injects a raising `start()`.
