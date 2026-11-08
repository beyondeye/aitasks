---
priority: medium
effort: medium
depends: [t2037_3]
issue_type: feature
status: Implementing
labels: [applink, monitor]
assigned_to: dario-e@beyond-eye.com
anchor: 2034
created_at: 2026-10-16 08:11
updated_at: 2026-11-08 22:58
---

Switch applink to the client (parent: Python monitor status server task).

applink builds its own `TmuxMonitor` (`applink/server.py:190`), and
`PushScheduler` (`applink/pusher.py:69`) polls `capture_all_async`. It also uses
that instance as an action and content gateway. Calls found in
`applink/router.py` / `pusher.py`: `send_keys`, `forward_key`, `send_enter`,
`kill_window`, `kill_agent_pane_smart`, `spawn_tui`, `switch_to_pane`,
`capture_pane`, `capture_pane_content_async`, `capture_cursor_async`,
`cycle_compare_mode`, `get_pane`.

## Do

- Status (`pane_status` pushes and the router's `not_idle` restart gate) comes
  from the subscription.
- Decide per call which ones stay on a local gateway instance (actions, cursor
  capture, history scrollback) and which go through the server (`capture{}`).
- The mobile wire protocol (`aidocs/applink/protocol.md`) stays unchanged.

## Verification

Existing applink tests pass; a live check that a paired client still receives
`pane_status` updates and can send keys, with only the server capturing for
status.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2037_3** id=2026-11-07T17:20:54Z.d3b948f3a61203778155b9af from=t2037_3 from_verified=yes at=2026-11-07T17:20:54Z base=bc5505493c2518ba9f25c665a05060eaf3029e5c base_branch=main dirty=yes host=omg16
>
> | Advisory from t2037_3 (monitor + minimonitor now subscribe through MonitorClient; code commit bc5505493). Details are in its archived plan's "Notes for sibling tasks" and "Post-Review Changes". As of that commit:
> | 
> | - Construction: monitor_shared.build_monitor_client(local, kind=..., own_pane=..., session=..., project_root=..., pins=..., enabled=None|False). monitor_shared imports Textual; applink may prefer MonitorClient directly with the same arguments.
> | - Before a requested scan, call flush_pins() between set_capture_pins(...) and request_refresh(). set_capture_pins only spawns its set_pins send, so the refresh could otherwise reach the server first and scan under the old pins. flush_pins is bounded and never raises.
> | - These calls wait for the server: capture_pane_classified_async, refresh_shadow_snapshot, request_refresh, capture, set_content, flush_pins, and cycle/set_compare_mode_async. Never await one on a serialized dispatch path, such as applink's request loop if one connection's requests are handled in order. Four review rounds on t2037_3 found exactly this class of bug in the TUIs (call_later, set_timer → call_next, and a mode decision made at scheduling time).
> | - Choose the route by object type, never by client.mode. A client in fallback can reconnect before a queued callback runs.
> | - capture_all_* only reads the subscription. Scans happen per server tick, plus explicit request_refresh.
> | - The server applies each project's project_config.yaml. A per-instance override needs enabled=False.
> | - Measured (one host, one moment): with N=12 agents and K=4 clients, tmux-server CPU is 0.67 % shared vs 2.2 % in-process, and the status server costs about 0.35 %.

> **👁 note:read** id=2026-11-08T20:57:27Z.e388d902948ce1cfc8109407 by=t2037_4 at=2026-11-08T20:57:27Z mode=explicit ids=2026-11-07T17:20:54Z.d3b948f3a61203778155b9af
