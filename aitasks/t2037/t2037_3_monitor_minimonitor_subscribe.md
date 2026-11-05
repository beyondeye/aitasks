---
priority: medium
effort: medium
depends: [t2037_2]
issue_type: feature
status: Implementing
labels: [monitor, minimonitor, performance]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2034
created_at: 2026-10-16 08:11
updated_at: 2026-11-06 00:21
---

Switch `ait monitor` and `ait minimonitor` to the client (parent: Python
monitor status server task).

## Do

- Replace the in-process `TmuxMonitor` construction at
  `monitor/monitor_app.py:856` and `monitor/minimonitor_app.py:1592` with
  `MonitorClient` (keeping its fallback).
- Keep client-side: the minimonitor review loop's raw-tail captures of the
  followed pane and its shadow (`monitor/review_loop.py`), every action
  (send-keys, kill, pick, shadow spawn), the switcher.
- Apply t2034_2's semantics for parked agents and compare-mode overrides.

## Verification

- Existing monitor/minimonitor tests pass in both modes (server and fallback).
- Live: with N minimonitors, one capture pass per tick (count `capture-pane`
  calls before and after); idle seconds agree across clients.
- Re-run t2034_1's measurement and record the difference.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2183** id=2026-11-04T20:09:14Z.518d4636c5eb9849ba8afc32 from=t2183 from_verified=yes at=2026-11-04T20:09:14Z base=4c51b9150c91b416fd3c809ed593b88f765a3ddf base_branch=main dirty=yes host=omg16
>
> | t2183 landed in 4c51b9150 (minimonitor_app.py) — advisory context for switching the minimonitor to MonitorClient:
> | 
> | - The minimonitor now diffs the RENDERED card text against what each card shows (`Static.content`), so it is independent of where snapshots come from. Protocol deltas need no extra plumbing for render savings; a card's text also depends on marks, task cache, gate ledger, compare mode, the completed set and the width, which deltas cannot carry anyway.
> | - `_refresh_data`'s list block changed: `_build_list_entries()` → `_plan_in_place_list_update()` → nothing / `_apply_list_updates` / `_rebuild_pane_list(entries)`. The top-of-tick `saved_pane_id` is gone (focus is read at restore time). If you touch the capture half of `_refresh_data`, keep the list block after the snapshot assignment.
> | - Measured (one host, synthetic agents): per-instance CPU at N=12 0.49 % of a core active / 0.79 % idle after t2183; the producer (~0.37 % of a core at N=12) is now the largest bucket — that is the part your migration removes per client.

> **✉ note:t2037_2** id=2026-11-05T22:06:07Z.a07bd73c9ff71ed79f810a47 from=t2037_2 from_verified=yes at=2026-11-05T22:06:07Z base=3594c2798b2cd68979b056d1492ac0f65f6e561b base_branch=main dirty=yes host=omg16
>
> | Advisory from t2037_2 (MonitorClient landed in 3594c2798; details in its archived plan's "Notes for sibling tasks"). Wiring the swap needs, as of that commit:
> | 
> | - Build the local TmuxMonitor exactly as today and wrap it: MonitorClient(local, kind="monitor"|"minimonitor", own_pane=..., session=..., project_root=...). start_control_client()/close_control_client() are the client's start/close, so the existing mount/unmount calls drive it.
> | - PINS: in server mode the server computes the skip set from pins, and set_parked_agents only reaches the local instance. AgentMarksMixin._publish_parked_agents must also call self._monitor.set_capture_pins(self._capture_pins()) when present, or a minimonitor never pins its followed parked agent.
> | - capture_all_async / capture_all_classified_async only READ the subscription; keypress refresh sites should await self._monitor.request_refresh().
> | - Compare mode: the sync cycle_compare_mode returns a prediction in server mode; switch call sites to await cycle_compare_mode_async().
> | - Fallback-mode leg of the both-modes tests: AITASKS_MONITOR_SERVER=0 or enabled=False.
> | - In server mode the server applies each session's project_config.yaml, not an app's CLI overrides (--interval, capture lines).
> | - tests/test_monitor_client_surface.py fails if an app starts using a monitor attribute the client neither serves nor allowlists (GATEWAY_NAMES).
> | - Optional: render on push via add_update_listener (Applied.changed) / add_mode_listener.

> **👁 note:read** id=2026-11-05T22:20:38Z.5d4de543ba547b4980a55e0e by=t2037_3 at=2026-11-05T22:20:38Z mode=explicit ids=2026-11-04T20:09:14Z.518d4636c5eb9849ba8afc32,2026-11-05T22:06:07Z.a07bd73c9ff71ed79f810a47
