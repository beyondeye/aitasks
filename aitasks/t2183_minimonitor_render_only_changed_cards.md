---
priority: medium
effort: medium
depends: []
issue_type: performance
status: Implementing
labels: [monitor, minimonitor, performance]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2201** id=2026-11-04T15:02:01Z.24c6b90cd39091510b90ba35 from=t2201 at=2026-11-04T15:02:01Z base=c0a6bbd4015d48cca47bfd7b1deba187cfb4c66f base_branch=main dirty=yes host=omg16
>
> | Advisory context from exploring t2201 (minimonitor click selection reverted by refresh), 2026-11-04:
> | 
> | - MiniMonitorApp._refresh_data snapshots saved_pane_id at the TOP of the tick and restores it after the full teardown/rebuild via a deferred card.focus(); a click during the tick's awaits is reverted. t2201 owns the fix (read the user's current intent at restore time, synchronous set_focus) plus a regression test that clicks while capture_all_async is suspended.
> | - Whatever incremental update t2183 designs must keep that test green: an in-place card update must never re-focus a stale pane id over a click, and the "card set changed" full-rebuild path still needs the t2201 behaviour.
> | - Load evidence measured live that day (one host, one moment, not a benchmark): 46 minimonitors + 5 monitors = 50 control-mode clients on one tmux -L ait server, 111 panes / 5 sessions; tmux server at 40-73% of a core; display-message RTT 3-119 ms; a shell-loop capture-pane sweep of all 111 panes 0.9-4.4 s. Your Context cites 38 minimonitors from t2034_1; the count has grown.

> **👁 note:read** id=2026-11-04T16:28:54Z.8e19865888b3f8106ab27e28 by=t2183 at=2026-11-04T16:28:54Z mode=explicit ids=2026-11-04T15:02:01Z.24c6b90cd39091510b90ba35

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-04T16:35:37Z status=pass attempt=1 type=human
