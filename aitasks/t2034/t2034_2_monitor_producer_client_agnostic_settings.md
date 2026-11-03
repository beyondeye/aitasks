---
priority: medium
effort: medium
depends: [t2034_1]
issue_type: refactor
status: Implementing
labels: [monitor, minimonitor]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2034
implemented_with: claudecode/opus5_5
created_at: 2026-10-16 08:01
updated_at: 2026-11-03 18:19
---

Make the `TmuxMonitor` producer client-agnostic, so one shared instance can
serve many TUIs (see the parent task). Four per-instance settings sit inside the
producer today:

| Setting | Where | Proposed semantics |
|---|---|---|
| `exclude_pane` (defaults to `$TMUX_PANE`) | `TmuxMonitor.__init__`, `monitor/monitor_core.py:1954` | the client filters its own pane out |
| multi-session toggle `M` | `action_toggle_multi_session` (`monitor_app.py:3105`, `minimonitor_app.py:5346`) | the producer always scans every session; the client filters |
| parked agents (capture skipped) | `set_parked_agents`, `monitor_core.py:2089` | **open**: skip only when every subscriber parks the agent, or make parking global (marks live app-side today) |
| compare-mode override | `action_cycle_compare_mode` (`monitor_app.py:3121`, `minimonitor_app.py:5322`) | **open**: one shared per-pane setting (behaviour change: one client's override changes every client's idle verdict), or a per-client idle clock for overridden panes |

## Do

- Settle the two open rows with the user during planning and record them in the
  protocol doc (child 3).
- Refactor in-process first, before any server exists: the producer runs
  without an exclude or session filter, clients filter, and parking and compare
  mode follow the decided semantics. A single monitor or minimonitor must behave
  exactly as before.
- Tests pinning each row, including the existing rule that the parked set is
  published *before* the capture (see the `set_parked_agents` docstring).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-03T16:19:28Z status=pass attempt=1 type=human
