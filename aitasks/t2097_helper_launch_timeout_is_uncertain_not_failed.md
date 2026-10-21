---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitormini, tmux]
gates: [risk_evaluated]
anchor: 2073
followup_kind: upstream_defect
created_at: 2026-10-21 14:40
updated_at: 2026-10-21 14:40
---

## Origin

Spawned from t2087 during plan review (the shadow spawn's launch-returned identity).

## Upstream defect

- `.aitask-scripts/lib/tmux_exec.py:254` — `TmuxClient.run` catches
  `subprocess.TimeoutExpired` together with `FileNotFoundError` / `OSError` and
  answers `(-1, "")` for all three.
- `.aitask-scripts/lib/agent_launch_utils.py` — `launch_split_pane` and
  `launch_window_pane` (and `launch_in_tmux`) turn any `rc != 0` into an ordinary
  `error` string ("tmux split-window failed (rc=-1)").
- `.aitask-scripts/monitor/monitor_core.py` — `spawn_shadow` and
  `spawn_scratchpad` return immediately on that `error`: no refresh, no
  recovery.

## Why it matters

A timeout does not prove tmux failed to create the pane. The server can create
it and only the reply is lost. The spawn then reports "launch failed" and does
nothing more, while a live, UNSTAMPED helper pane (shadow or scratchpad) may
exist. That pane lists as an agent, evades the duplicate guard, and is never
reached by the cleanup hook. This is the same unknown ≠ gone failure class that
t2073_4 and t2087 closed for the post-launch lookup, one boundary earlier.

## Suggested fix

- Distinguish an **uncertain** launch outcome (timeout) from a **definite**
  failure at the launcher boundary. For example, route the launch through the
  gateway's `run_result` (`TmuxResult` carries a status), or return a dedicated
  timeout signal from the identity launchers.
- On an uncertain outcome, both spawns should say so in the user-facing message
  (not "launch failed"), call `schedule_refresh()`, and advise checking the
  agent's window for a stray pane.
- **Do not blindly retry the launch.** A retry after a lost reply opens a second
  helper.
- Optionally attempt nothing further: without a pid there is nothing to recover
  by, so reporting is the honest outcome.
- Pin it with a timeout regression for both spawns (gateway answering a timeout
  on the launch), plus a control showing that a definite failure (non-zero tmux
  exit) keeps today's no-refresh error.
