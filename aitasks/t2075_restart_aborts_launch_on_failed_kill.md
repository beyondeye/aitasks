---
priority: medium
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
created_at: 2026-10-20 10:27
updated_at: 2026-10-20 11:15
---

## Origin

Spawned from t2065 during Step 8 review.

## Upstream defect

- `.aitask-scripts/monitor/monitor_app.py:3930-3935` — `_on_restart_confirmed` still calls `launch_in_tmux` (and reports "Restarted agent for t<id>") when `kill_agent_pane_smart` returns `ok=False`. A failed kill leaves the original agent alive while a replacement starts on the same task.

(Line numbers as of the t2065 commit; re-locate by function name: the `on_pick_result` closure inside `MonitorApp._on_restart_confirmed`.)

## Diagnostic context

t2065 added a kill-time frozen re-check in front of the restart's kill. It neither kills nor launches unless `_kill_target_state` proves the pane live. The *live* path still ignores the kill's own result:

```python
ok, _ = self._monitor.kill_agent_pane_smart(pane_id)
if ok:
    ...
    self.notify(f"Killed {old_window_name}", markup=False)
_, err = launch_in_tmux(screen.full_command, pick_result)   # runs even when ok is False
```

This pre-dates t2065: the committed baseline before t2065 has the same shape. A plan reviewer reproduced it through the real callback with kill and launch stubbed.

## Suggested fix

On `ok=False`, notify a warning naming the window (`markup=False`; add the toast to `tests/test_monitor_markup_literal_sinks.py` `TOAST_SITES`), call `self.call_later(self._refresh_data)` and return without launching. Add a regression in `tests/test_monitor_pick_launch_sites.py::RestartPickTests`: with a kill that fails, the log has no `("launch", …)` entry and no "Restarted agent" notify.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-20T08:15:30Z status=pass attempt=1 type=human
