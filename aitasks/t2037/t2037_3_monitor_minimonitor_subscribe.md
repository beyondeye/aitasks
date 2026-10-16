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
