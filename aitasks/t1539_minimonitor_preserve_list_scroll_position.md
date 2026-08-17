---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [minimonitor, tui, scroll]
created_at: 2026-08-17 12:42
updated_at: 2026-08-17 12:42
---

## Symptom

In the minimonitor (`ait monitor --mini` / the 40-column companion pane), when
there are more code-agent cards than fit in the visible list, a vertical
scrollbar appears. If the user scrolls the list down (mouse wheel / scrollbar
drag), the scroll position is **reset to the top on the next status-refresh
tick** (default every 3 s). This makes the list unusable when it overflows: any
agent below the fold snaps back out of view every few seconds.

## Root cause

`MiniMonitorApp._rebuild_pane_list()` (in
`.aitask-scripts/monitor/minimonitor_app.py`) rebuilds the `#mini-pane-list`
`VerticalScroll` from scratch on every refresh:

```python
container = self.query_one("#mini-pane-list", VerticalScroll)
await container.remove_children()
...
await container.mount_all(widgets)
```

`remove_children()` + `mount_all()` drops and recreates all `MiniPaneCard`
children, which resets the scroller's `scroll_y` to 0. Nothing saves or restores
the scroll offset.

The only continuity preserved today is **focus**: `_refresh_data` saves
`_focused_pane_id` and `_restore_focus()` re-`.focus()`es the matching card,
which Textual scrolls back into view. So **keyboard** navigation (up/down)
survives a refresh, but a **mouse-wheel / scrollbar** scroll — which does not
move focus — is discarded every tick. That asymmetry is exactly the reported
symptom.

## Constraint: agents killed between refreshes

Scroll restoration cannot be a naive `scroll_y` save/restore: the set of cards
changes between ticks. A code-agent can be **killed between two refreshes**, and
new ones can appear, so:

- the total content height changes → a saved raw `scroll_y` can exceed the new
  `max_scroll_y` and overshoot;
- the card that occupied a given offset may no longer exist.

The restore must therefore anchor on a **stable identity**, not a raw offset.
`MiniPaneCard` is constructed with `snap.pane.pane_id`
(`MiniPaneCard(snap.pane.pane_id, text_fn(snap))`), which is the natural anchor.

## Suggested approach

Mirror the pattern the **full monitor** already uses for its preview column
(`monitor_app.py` `_record_scroll_for` / `PreviewScrollContainer`, ~lines
878–930), adapted from anchor-by-line-text to anchor-by-`pane_id`:

1. **Before** `remove_children()` in `_rebuild_pane_list()` (or in
   `_refresh_data` around the rebuild, alongside the existing
   `saved_pane_id = self._focused_pane_id` capture), record:
   - whether the list is at bottom (`max_scroll_y <= 0` or
     `scroll_y >= max_scroll_y - 1`), and
   - the `pane_id` of the **topmost visible card** (the card whose region top is
     nearest the current `scroll_y`).
2. **After** `mount_all()`, restore:
   - if it was at bottom → `scroll_end(animate=False)` (keeps a bottom-pinned
     list pinned as agents come and go);
   - else if the anchor `pane_id`'s card still exists → scroll so that card is
     back at the top (`scroll_to`/`scroll_visible` on that card, `animate=False`);
   - else (anchor agent was killed) → fall back to the nearest surviving
     neighbour from the pre-rebuild order, or clamp to `max_scroll_y`, so the
     view stays near where it was instead of jumping to 0.
3. Keep this independent of, and consistent with, the existing focus
   restoration in `_restore_focus()` — the two must not fight (focus scroll vs.
   anchor scroll). Decide a single winner (e.g. anchor scroll is authoritative
   for mouse-driven scroll; focus restore only scrolls when the focused card
   would otherwise be off-screen).

## Notes / references

- This is the minimonitor analogue of the board-list issues already tracked in
  this repo: `t1257_board_auto_refresh_refocus_discards_scroll` and
  `t1261_manual_verification_board_scroll_jump_fix`. Worth reviewing their
  resolutions for a reusable helper before implementing.
- The card row-width work (`t1351_minimonitor_row_width_audit`) touches the same
  rebuild path but is orthogonal.
- Reported against the vendored copy in the `thinking_backend` project; filed
  here in the `aitasks` source repo where `minimonitor_app.py` lives.

## Suggested verification

- With >1 screenful of agents, scroll the list down with the mouse and confirm
  the position holds across several refresh ticks.
- Scroll to the bottom, let an agent above the fold be killed, and confirm the
  view stays pinned to the bottom (no jump to top).
- Scroll to a mid-list agent, kill that exact agent, and confirm the view stays
  near its neighbours rather than snapping to the top.
