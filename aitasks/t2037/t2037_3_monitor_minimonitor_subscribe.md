---
priority: medium
effort: medium
depends: [t2037_2]
issue_type: feature
status: Ready
labels: [monitor, minimonitor, performance]
anchor: 2034
created_at: 2026-10-16 08:11
updated_at: 2026-10-16 08:11
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
