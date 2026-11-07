---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [monitor, minimonitor, performance]
gates: [risk_evaluated]
anchor: 2034
followup_kind: risk_mitigation
created_at: 2026-11-07 19:15
updated_at: 2026-11-07 19:15
---

## Origin

Risk-mitigation ("after") follow-up for t2037_3, created at Step 8d after implementation landed.

## Risk addressed

Up to one server tick of extra staleness in server mode.

From t2037_3's plan (`## Risk` / Goal-achievement): "In server mode the timer reads the subscription, so a card can be up to one server tick staler than with an in-process scan. Render on push would close this, but it is out of scope."

## Goal

Make `ait monitor` and `ait minimonitor` re-render when the subscription changes, instead of only on their own interval timer.

- `MonitorClient.add_update_listener(cb)` already calls `cb(Applied)` after every applied snapshot/delta (`Applied.changed` names the changed panes), and `add_mode_listener` reports mode switches (`.aitask-scripts/monitor/status_client.py`).
- Drive a read-only refresh (`_refresh_data(scan=False)`) from the listener, coalesced and dispatched with `run_worker` — never on the App message pump (`call_later` / `call_next` / `set_timer` all run there; see t2037_3's archived plan and `aidocs/framework/monitor_status_protocol.md` "Consumers: monitor and minimonitor").
- Decide whether the interval timer can then be lengthened or skipped while subscribed (it also drives marks, auto-close and maintenance, so it cannot simply stop).
- The minimonitor already diffs rendered card text (t2183), so a push-driven render of unchanged cards is cheap; measure the per-client CPU before/after with t2034_1's scripts (re-run in t2037_3's Final Implementation Notes).
