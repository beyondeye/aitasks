---
priority: medium
effort: medium
depends: []
issue_type: performance
status: Implementing
labels: [monitor, minimonitor, performance]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2034
created_at: 2026-11-03 17:02
updated_at: 2026-11-04 16:53
---

## Context

t2034_1 measured monitor and minimonitor CPU on 2026-11-03 (omg16; tables,
method and scripts in the archived plan
`aiplans/archived/p2034/p2034_1_measure_monitor_scan_cost.md`). The largest
cost the shared monitor status server (t2034 / t2037) does **not** remove is
minimonitor rendering:

- About 80 % of a live minimonitor's GIL-held CPU is Textual: render ≈55 %,
  dispatch ≈25 %. Scanning (the producer) is ≈14 %.
- Per-instance CPU grows with the number of agents N. These are steady-state
  figures on an isolated tmux server: N=1 0.22 %, N=4 ≈0.7 %, N=12 ≈1.3 %,
  and live N=38 3.85 % median. The producer accounts for only ≈0.02–0.03 % of
  a core per agent; the rest of the growth is rendering.
- Live: 38 minimonitors × ≈3.1 % of Textual ≈ **1.2 cores**, which is more
  than the tmux-server load the status server removes.

Each refresh tick (3 s, `MiniMonitorApp._refresh_data`) rebuilds the whole
pane list (`MiniMonitorApp._rebuild_pane_list`,
`.aitask-scripts/monitor/minimonitor_app.py`). The top stacks are
`_agent_card_text` → markup → `Content`, `Compositor._render_chops`,
`StylesCache.render_line` and `Widget.render_lines`. Every card is
re-rendered whether or not its content changed.

## Goal

Cut minimonitor per-tick render CPU so it scales with *changed* agents rather
than *all* agents, without breaking scroll/focus preservation:
- `_capture_list_scroll` / `_restore_list_scroll`;
- the bottom-pin and width-pin live tests
  (`tests/test_minimonitor_bottom_pin_live.py`,
  `tests/test_minimonitor_width_pin_live.py`).

## Do

- Profile first, using the t2034_1 method:
  - py-spy **with `--gil`** (the default mode on CPython 3.14 counts blocked
    waits as active);
  - a companion layout, because a solitary minimonitor auto-closes;
  - `AITASKS_TMUX_SOCKET` set explicitly to an isolated server.

  Confirm which part of the rebuild dominates: card text and markup building,
  widget remount, or layout and compositor.
- Design an incremental update: diff card state per tick, update only changed
  cards in place, and skip the rebuild when nothing changed. Keep one code path
  for the full rebuild when the card *set* changes (agents added or removed).
- Consider what the t2037 subscription protocol can provide (per-pane deltas)
  so the client knows what changed without re-diffing. Coordinate rather than
  duplicate, since t2037 is the status server.
- Re-measure with the same harness at N = 1, 4, 12 and report the before and
  after tables.

## Verification

- The existing minimonitor tests stay green, including the live pin tests in
  the serial carve-out.
- Before/after CPU tables are recorded in the plan at the same N, with py-spy
  coverage reported.
