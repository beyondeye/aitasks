---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [minimonitor, monitor, frozen_agents]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2049
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-20 12:07
updated_at: 2026-10-20 12:35
---

## Origin

Spawned from t2075 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/monitor_app.py:3804` — `_launch_pick_for_sibling` ignores the `ok` result of `kill_agent_pane_smart`. It clears focus and notifies "Killed <window>" even when the kill failed.
- `.aitask-scripts/monitor/minimonitor_app.py:3370` — the minimonitor sibling-pick kill also ignores the result of `kill_agent_pane_smart` and always clears focus. No failure toast is shown.

(Line numbers are as of the t2075 commit. Re-locate them with `grep -n kill_agent_pane_smart`.)

## Diagnostic context

t2075 fixed the restart path (`MonitorApp._on_restart_confirmed`). There, a failed kill used to be followed by a launch on the SAME task, which put two agents on it. It now warns, refreshes and returns. While auditing every `kill_agent_pane_smart` call site, t2075 found two sibling-pick sites that also discard the result:

```python
# monitor_app.py, _launch_pick_for_sibling (kill happens before the dialog opens)
if state == "live":
    self._monitor.kill_agent_pane_smart(pane_id)
    self._focused_pane_id = None
    self.notify(f"Killed {old_name}", markup=False)
```

```python
# minimonitor_app.py, after the launch
if state == "live":
    self._monitor.kill_agent_pane_smart(kill_pane_id)
    self._focused_pane_id = None
```

The harm is smaller than in the restart path. The outgoing agent's task is a different one, normally finished, so nothing gets duplicated. Still, the monitor reports a kill that never happened, the still-running pane loses focus, and that pane stays alive with no hint to the user. `_on_kill_confirmed` (monitor_app.py ~3690) is the reference shape: on `ok=False` it shows a `"Failed to kill {name}"` error with `markup=False`.

## Suggested fix

At both sites, read `ok, _ = …kill_agent_pane_smart(…)`. On success, keep the current behaviour. On failure, notify `f"Failed to kill {name}"` (`markup=False`) and leave focus alone. For monitor_app, add the toast to `tests/test_monitor_markup_literal_sinks.py` `TOAST_SITES`. Add regressions in `tests/test_monitor_pick_launch_sites.py` (the sibling-path tests; `_Host.kill_ok` already exists from t2075) and in the minimonitor launch tests.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-20T09:35:06Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-20T09:42:29Z status=pass attempt=1 type=human
