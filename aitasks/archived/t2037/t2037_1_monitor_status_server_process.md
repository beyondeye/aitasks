---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: high
depends: [t2034_3]
issue_type: feature
status: Done
labels: [monitor, tmux]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2034
implemented_with: claudecode/opus5_5
created_at: 2026-10-16 08:11
updated_at: 2026-11-05 08:28
completed_at: 2026-11-05 08:28
---

The status server process and its lifecycle (parent: Python monitor status
server task). It owns one `TmuxMonitor` producer and serves the t2034_3
protocol.

## Do

- One server per (tmux socket, framework `VERSION`): the socket path is keyed on
  the tmux socket (`AITASKS_TMUX_SOCKET` or the default) and `VERSION`, under
  `$XDG_RUNTIME_DIR/aitasks/` (fallback `~/.aitask/run/`), directory mode 0700.
- An `ensure` entry point: an exclusive file lock (no double start), then start
  the server detached (`setsid`) if none is answering.
- Exit after a grace period with no subscribers, or when the control client
  sees `%exit`. Detect and replace a stale socket left by a crashed server.
- Apply each session's own project `tmux.monitor` config (`load_monitor_config`
  through the session→project map), not one project's config for every
  session.
- tmux calls only through the gateways (`lib/tmux_exec.py`;
  `tests/test_no_raw_tmux.sh` enforces).

## Verification

Tests: single start under concurrent `ensure`, idle exit, stale-socket
recovery, per-version isolation, per-session config, delta ordering by `gen`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-04T16:47:29Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-05T06:21:56Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-05T06:28:28Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:e284f57f04951d1a

> **✅ gate:risk_evaluated** run=2026-11-05T06:28:28Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2037_1/risk_evaluated_2026-11-05T06:28:28Z-risk_evaluated-a1.log`
