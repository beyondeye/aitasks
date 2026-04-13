---
Task: t532_scroll_position_for_multi_agents_in_monitor.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Per-pane scroll position in monitor preview (t532)

## Context

`ait monitor` shows a single content preview area (`#preview-scroll`
ScrollableContainer) that is reused across all monitored agents/panes.
Task t529 (commit `5a56a439`) rendered the full captured scrollback into this
container and added tail-follow semantics so the scroll position is preserved
between refreshes of the *same* pane and snaps to the bottom when the user is
already at the bottom.

The bug (t532): the scroll position is global to the container, not per-pane.
When the user scrolls inside agent A, switches focus to agent B (and possibly
scrolls again), then switches back to A, the scroll position is whatever it
last became under B — A's scroll position is lost. If the user does not scroll
between switches the position appears preserved only by accident, because
`_update_content_preview` checks "was at bottom" and re-pins to the bottom.

The fix is to remember each pane's scroll state and restore it on focus change,
while keeping the existing tail-follow behaviour for refreshes of the same pane.

## Approach

Two changes in this task:

1. **Per-pane scroll memory** (the bug fix).
2. **`t` key — scroll preview to tail and re-enable tail-follow** (the small
   companion feature the user requested while we are touching the scroll path).

### 1. Per-pane scroll memory

Track per-pane scroll state in a dict keyed by `pane_id`, store
`(distance_from_bottom, was_at_bottom)` rather than absolute `scroll_y`. Storing
distance-from-bottom is robust against the captured scrollback growing or
rolling off the top while the pane is unfocused (tmux capture is bounded by
`capture_lines`, default 200, so absolute positions drift as new lines arrive).

When `_update_content_preview` runs:

1. If the focused pane changed since the previous call, snapshot the scroll
   state of the *previous* pane into the dict before swapping content.
2. After updating the preview content, decide the target scroll position for
   the *current* pane:
   - If the pane changed: look up its saved state. If none, default to
     "scroll to bottom" (preserves the existing first-view behaviour).
     If saved state's `was_at_bottom` is true → scroll to end (and tail-follow
     resumes naturally on next refresh). Otherwise compute
     `target_y = max(0, max_scroll_y - distance_from_bottom)` and scroll there.
   - If the pane did not change (refresh of the same pane): keep the existing
     logic — tail-follow when at bottom, otherwise leave `scroll_y` alone so
     it preserves naturally as the new content is appended.
3. Update `_last_preview_pane_id` to the now-displayed pane id.

Scroll restoration must happen via `call_after_refresh` so the new content has
been laid out and `max_scroll_y` reflects the new content height. Use
`scroll.scroll_to(y=target, animate=False)` (Textual's canonical setter) for
the non-bottom case, mirroring the existing `scroll.scroll_end(animate=False)`
call.

Stale entries in the per-pane dict are cleaned up in `_refresh_data` after the
fresh `capture_all()` snapshot, by dropping any pane_id no longer present in
`self._snapshots`. This keeps the dict bounded to currently-live panes.

Horizontal scroll (`scroll_x`) is intentionally out of scope — the user only
reported the vertical case and the existing code already only manages vertical
position.

### 2. `t` key — jump to tail / resume tail-follow

After scrolling back to read older output, the user needs a quick way to
return to the live tail (and resume tail-follow on subsequent refreshes,
since tail-follow is gated on "is the user currently at the bottom?").

Add a new binding `Binding("t", "scroll_preview_tail", "Tail")` to the app's
`BINDINGS` list and an action method `action_scroll_preview_tail` that:

- looks up `#preview-scroll`, calls `scroll.scroll_end(animate=False)`
- updates the per-pane saved state for the focused pane to
  `(distance=0.0, was_at_bottom=True)` so future pane-switches restore the
  tail position
- shows a brief notification ("Tail follow")

Tail-follow on the *next* refresh re-engages naturally: `_update_content_preview`
reads `scroll_y` and pins to the bottom whenever the user is already at the
bottom, which we just made true.

The key `t` is unused (current bindings: tab, j, q, s, i, r, f5, z, b, k, n,
enter, a; plus `escape` in dialogs) and is mnemonic for "tail".

## Files to modify

- `.aitask-scripts/monitor/monitor_app.py`
  - `__init__` (~line 366): add two instance fields:
    - `self._preview_scroll_state: dict[str, tuple[float, bool]] = {}`
      (pane_id → (distance_from_bottom, was_at_bottom))
    - `self._last_preview_pane_id: str | None = None`
  - `_refresh_data` (~line 462): after `self._snapshots = self._monitor.capture_all()`,
    prune `self._preview_scroll_state` to drop pane_ids no longer in
    `self._snapshots`. Also clear `self._last_preview_pane_id` if it points to a
    pane that has gone away.
  - `_update_content_preview` (~line 610): rewrite the body of the
    `if lines:` branch to (a) detect pane change vs same-pane refresh,
    (b) snapshot the previous pane's state before swapping content,
    (c) compute the target scroll position for the new pane,
    (d) schedule `scroll_end` *or* `scroll_to(y=target)` via
    `call_after_refresh`. Also update `self._last_preview_pane_id` at the
    end of the method (in both the focused and unfocused branches —
    setting it to `None` when nothing is displayed so the next focus is
    treated as a pane change).
  - `BINDINGS` list (~line 330): add `Binding("t", "scroll_preview_tail", "Tail")`.
  - new method `action_scroll_preview_tail` (place near
    `action_toggle_scrollbar`, ~line 891): scroll the preview to end and
    update the per-pane saved state for the focused pane so a future
    pane-switch restores tail position.

## Verification

Manual TUI test inside an existing tmux session that has at least two
agent panes (so the monitor displays two preview targets):

1. `./ait monitor` from inside the tmux session.
2. Focus agent A in the pane list. Use the mouse wheel or keyboard to scroll
   the preview a few lines up from the bottom. Note the visible content.
3. Focus agent B. Scroll to a different position (e.g. all the way to top).
4. Focus agent A again. The preview should restore to roughly the same
   distance-from-bottom you left it at, *not* the top of agent B.
5. Focus agent B again. It should restore to the top.
6. Verify tail-follow still works: focus agent A, scroll to the bottom,
   wait a tick — the live updates should keep the view pinned to the bottom.
7. Verify zoom toggle (`z`) still preserves the per-pane state.
8. Kill one of the agent panes via tmux; `_refresh_data` should remove the
   stale entry without crashing.
9. With agent A focused and scrolled up, press `t`. The preview should jump
   to the bottom and `Tail follow` should appear in the notification area.
   Wait a tick — live updates should keep pinning to the bottom. Switch to
   agent B then back to agent A: A should still be at the bottom.
10. Verify the new `Tail` binding shows up in the footer key hints.

There are no automated tests for the Textual monitor app, so manual TUI
verification is the only path. After implementation, run `python3 -m py_compile
.aitask-scripts/monitor/monitor_app.py` as a syntax sanity check.

## Step 9 reminder

After review, follow task-workflow Step 9 (commit, push, archive via
`./.aitask-scripts/aitask_archive.sh 532`).

## Final Implementation Notes

- **Actual work done:** Implemented the plan as written in
  `.aitask-scripts/monitor/monitor_app.py`. Added `_preview_scroll_state` and
  `_last_preview_pane_id` instance fields; rewrote `_update_content_preview`
  to detect pane change vs same-pane refresh, snapshot the previous pane's
  scroll state before swapping content, and restore the saved
  distance-from-bottom on switch back. Added stale-entry cleanup in
  `_refresh_data` after `capture_all()`. Added `Binding("t",
  "scroll_preview_tail", "Tail")` and a new `action_scroll_preview_tail`
  method that calls `scroll_end(animate=False)` and pre-populates the saved
  state with `(0.0, True)` for the focused pane.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:**
  - Stored `(distance_from_bottom, was_at_bottom)` rather than absolute
    `scroll_y` so per-pane restoration survives the captured scrollback
    growing/rolling while a pane is unfocused.
  - Restoration scheduled via `call_after_refresh` so the new content has
    been laid out and `max_scroll_y` reflects the new content height before
    we compute `target = max_scroll_y - distance`.
  - Default for first-view of a pane stays at "scroll to bottom" (matches
    pre-fix behaviour).
  - Reset `_last_preview_pane_id = None` when the displayed pane disappears
    or when the unfocused-state branch runs, so the next pane focus is
    treated as a pane change.
- **Verification done:** `python3 -m py_compile
  .aitask-scripts/monitor/monitor_app.py` passes. Manual TUI verification
  is the primary path (per the plan's verification section).

