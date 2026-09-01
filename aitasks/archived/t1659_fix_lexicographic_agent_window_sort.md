---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [minimonitor, tui, monitor]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1653
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-01 09:37
updated_at: 2026-09-01 12:05
completed_at: 2026-09-01 12:05
---

## Origin

Spawned from t1653 during Step 8b review. It is not a cause of that bug — it was
found while tracing minimonitor's scroll behaviour in a live 40-agent fixture,
and the wrong ordering is plainly visible in the capture.

## Upstream defect

`monitor/monitor_core.py:866 — PaneSnapshot.window_index is a str, so both
MiniMonitorApp._rebuild_pane_list and MonitorApp._rebuild_pane_list sort agents
lexicographically (1, 10, 11, …, 2, 20) instead of numerically.`

## Diagnostic context

Both TUIs sort with the same key shape:

```python
sort_key = lambda s: (s.pane.session_name, s.pane.window_index, s.pane.pane_index)
```

`window_index` (and `pane_index`) come off the tmux gateway as strings, so the
comparison is lexicographic. Observed in the t1653 live fixture capture as
`agent-pick-9, -10, -11, …, -14, -1, -2, …` — an agent list that jumps back to
low numbers part-way down.

t1653 deliberately did NOT fix this: it changes visible agent ordering in **two**
TUIs (`monitor/minimonitor_app.py:_rebuild_pane_list` and
`monitor/monitor_app.py:_rebuild_pane_list`), which is a different blast radius
from a scroll fix and needs its own tests. Check both call sites before changing
either — they share the key shape and must not diverge.

## Suggested fix

Sort on a numeric key while keeping the string field for display, e.g. a helper
that returns `(session_name, int_or_inf(window_index), int_or_inf(pane_index))`
and tolerates a non-numeric index rather than raising. A tmux window index is
normally an integer, but nothing in the snapshot type guarantees it, so the
comparison must stay total.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-01T08:15:56Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-01T08:32:52Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-01T09:05:14Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:149ef74a76aee3a1

> **✅ gate:risk_evaluated** run=2026-09-01T09:05:14Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1659/risk_evaluated_2026-09-01T09:05:14Z-risk_evaluated-a1.log`
