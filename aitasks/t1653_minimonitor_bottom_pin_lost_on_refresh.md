---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [minimonitor, tui, scroll, textual]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-08-31 18:32
updated_at: 2026-08-31 22:48
---

## Symptom (user report)

In `ait minimonitor`, when the code-agent list overflows and a vertical
scrollbar appears, dragging the scrollbar to the **end of the list** does not
survive the per-tick refresh: the view jumps back up. The position is not always
lost outright — the restore itself is wrong. **The distance jumped is not
constant: it is larger on a longer list.**

## Root cause — measured, not inferred

Reproduced live: the real `MiniMonitorApp` booted in an isolated tmux server
(`-L`), 60 `agent-*` windows, `_capture_list_scroll` / `_restore_list_scroll`
instrumented, driven with synthesised SGR mouse gestures (a real scrollbar thumb
drag: button press, motion, release). Trace after dragging to the end of the
trough:

```
71.03  y=74.37 max=88 vh=135  CAPTURE at_bottom=False anchor=%41 delta=0.371
71.10  y=63.37 max=67 vh=114   restore  GAP=3.63
72.10  y=70.37 max=73 vh=120   restore  GAP=2.63
73.08  y=74.37 max=88 vh=135   restore  GAP=13.63
```

The view oscillates and never returns to the bottom, for 15+ consecutive ticks.

Three linked facts, each measured:

1. **The rebuild zeroes the offset on EVERY tick.** Every `restore_in` sample
   read `scroll_y == 0`. `_restore_list_scroll` is therefore the *only* thing
   holding the position, once per second — any inaccuracy in it is a visible
   jump, continuously.

2. **A thumb drag cannot reliably reach the bottom, and its error scales with
   list length.** Textual maps thumb travel at
   `virtual_size / window_size` **content** rows per **screen** row
   (`textual/scrollbar.py:384-392`) — 2.87 in the fixture. A drag ending one
   screen row short of the trough end therefore lands ~3 content rows short of
   `max_scroll_y`, and that quantum grows linearly with the content height.
   This is exactly the reporter's "more if the list is longer".

3. **`at_bottom` is a one-row window, so that shortfall reads as
   not-at-bottom.** `_capture_list_scroll` records
   `at_bottom = max_y <= 0 or scroll_y >= max_y - 1`
   (`minimonitor_app.py:1587`). Off by more than one row, the bottom-pin branch
   never fires; the anchor branch takes over and **faithfully freezes the wrong
   position forever**. Card-height churn (task/gate/concern rows coming and
   going) then clamps `scroll_y` down on every content shrink via
   `validate_scroll_y`, and nothing restores it on the regrow — the oscillation
   above.

The underlying design flaw is that "the user is pinned to the bottom" is
captured as a **one-shot boolean snapshot taken before the rebuild** and applied
**once after it**, from geometry that is stale by construction. The bottom
branch also has no range gate at all — the comment at `minimonitor_app.py:404-409`
concedes the `target > max_scroll_y` retry is "vacuously false" when the target
*is* `max_scroll_y` — and it opts out of Textual's own deferral by passing
`immediate=True` to `scroll_end`, the very deferral Textual documents
(`widget.py:3051-3056`) as being there to obtain a settled `max_scroll_y`.

## Fix direction

Replace the hand-rolled bottom pin with Textual's first-class anchor:
`MiniPaneList.anchor()` / `release_anchor()`. The compositor recomputes
`new_scroll_y` from `total_region.bottom - container_height` inside the **arrange
pass** (`textual/_compositor.py:609` and `:693`), i.e. at the one moment the new
geometry is final. That removes the snapshot, the one-row threshold, the retry
budget and the `immediate=True` race in a single stroke. `release_anchor()`
already fires on any user scroll (`_scroll_to(release_anchor=True)`) and
`_check_anchor` re-arms when the user returns to the bottom — the same semantics
`at_bottom` is imitating.

Keep the existing anchor-id + delta path for genuine mid-list positions; it is
correct and its tests pass. Only the `at_bottom` branch changes.

Note `MiniPaneList` overrides `scroll_to_region` and `_scroll_to`. Check the
interaction: the compositor writes the anchored offset through `set_reactive`,
bypassing both overrides — verify that is the wanted behaviour under
`_list_scroll_lock` rather than assuming it.

## Acceptance criteria

1. With a list long enough to overflow, dragging the scrollbar thumb to the end
   of the trough leaves the list at the bottom, and it **stays** at the bottom
   across at least 10 consecutive refresh ticks, with card heights churning.
   Assert on `max_scroll_y - scroll_y == 0`, not on a rendered frame.
2. The same holds after the list grows and shrinks (agents appearing and
   disappearing) without any user gesture.
3. A user scroll away from the bottom is still honoured and is NOT re-pinned on
   the next tick (the existing `UserGestureSupersedesTests` contract).
4. Mid-list anchoring is unchanged: the existing
   `tests/test_minimonitor_scroll_preservation.py` cases still pass.
5. The repro is executable. See the testing note below — a headless-only test
   is NOT sufficient evidence for this bug and must not be the only coverage.

## Testing note — the headless suite cannot reproduce this

Measured, and it constrains the plan: driving the real `_refresh_data()` through
`_RefreshHost` under `App.run_test` produced **zero** shortfall at N =
6/12/24/48/96 cards, with single-line cards, with wrapping `height: auto` cards,
and with the list growing between ticks. `run_test` settles layout synchronously,
so the restore always ran at `attempt=0` against final geometry.

Consequence: **`list_layout_pending` returned True zero times across every
headless AND live run.** The 8-attempt retry ladder
(`_SCROLL_RESTORE_MAX_ATTEMPTS`) and both readiness gates are unexercised. Decide
deliberately whether the anchor-based fix lets them be deleted, and say so — do
not leave them in place unexamined.

The acceptance test therefore needs a **live tmux fixture**. This is known to
work and t1539 used it: Textual has SGR mouse tracking on, so
`tmux send-keys -t <pane> -l $'\e[<65;<col>;<row>M'` is a real wheel event and a
press/motion/release triple is a real scrollbar drag, on a detached server. Honour
the fixture rules in `aidocs/framework/tui_conventions.md` and the live-fixture
gotchas: minimonitor auto-closes if it is alone in its window (split it beside
another pane), and a TUI on a throwaway `-L` socket still queries the shared
socket unless `AITASKS_TMUX_SOCKET=<socket>` is exported into the pane's own
command. Route all tmux through the gateway (`lib/tmux_exec.py` /
`lib/tmux_exec.sh`) — `tests/test_no_raw_tmux.sh` enforces it.

## Side findings from the same exploration

Both were confirmed while tracing the above. Handle them here or split them out,
but record the decision either way.

- **The agent list sorts lexicographically.** `PaneSnapshot.window_index` is a
  `str` (`monitor_core.py:866`), and `_rebuild_pane_list` sorts on
  `(session_name, window_index, pane_index)`, so windows order as
  1, 10, 11, …, 19, 2, 20 …. Visible in the fixture capture as
  `agent-pick-9, -10, …, -14, -1, -2, …`. `MonitorApp._rebuild_pane_list` shares
  the key shape — check both before changing either.
- **`_capture_list_scroll` and `list_layout_pending` sample only
  `MiniPaneCard`s**, but the container also mounts session dividers and the
  `other (N)` section header. Harmless for the anchor (the delta absorbs a
  preceding divider, deliberately, and may be negative — observed `delta=-1.0`),
  but the readiness predicate is judging a subset of the content.

## Key references

- `.aitask-scripts/monitor/minimonitor_app.py` — `pick_scroll_anchor` (:339),
  `resolve_anchor_target` (:366), `list_layout_pending` (:395),
  `MiniPaneList` (:426), scroll-state class attrs (:587),
  refresh wiring (:1303), `_capture_list_scroll` (:1552),
  `_restore_list_scroll` (:1598), `_abandon_scroll_restore` (:1663),
  `_rebuild_pane_list` (:2167)
- `tests/test_minimonitor_scroll_preservation.py` — the t1539 suite and its
  three documented negative controls
- Textual 8.2.7: `widget.py` `anchor` (:800), `release_anchor` (:814),
  `_check_anchor` (:822), `max_scroll_y` (:1989), `scroll_end` (:3012);
  `_compositor.py` anchor re-application (:609, :693);
  `scrollbar.py` thumb-drag mapping (:384-392)

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-31T19:48:43Z status=pass attempt=1 type=human
