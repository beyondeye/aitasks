---
Task: t548_scroll_position_lost_when_switching_between_agents_in_ait_mo.md
Base branch: main
plan_verified: []
---

# Fix per-pane scroll reset in ait monitor preview (t548)

## Context

`ait monitor` (Textual TUI) keeps a per-pane vertical scroll memory so each
agent preview pane remembers where the user scrolled. Commit e1fd8bb5 (t532)
introduced `_preview_scroll_state: dict[pane_id, (distance, was_at_bottom)]`,
populated only at pane-switch time from a live read of `scroll.scroll_y` and
`scroll.max_scroll_y`.

The bug (t548): when the user arrows up/down between agents, the preview
jumps to tail instead of restoring the remembered position.

## Root cause

`scroll.scroll_y` / `scroll.max_scroll_y` read at save time are unreliable:

- `_update_content_preview` runs every 3 s (`_refresh_data` → same-pane path),
  calls `preview.update(content)`, which triggers a Textual re-layout
  (`Static.update` → `refresh(layout=True)` → `_size_updated` →
  `_scroll_update` → `scroll_y = validate_scroll_y(scroll_y)`).
- When the new virtual_size is smaller than before (a line count dip from
  Rich wrapping, ANSI re-render, width change, etc.), `scroll_y` is clamped
  to the new `max_scroll_y`.
- The same-pane branch (`monitor_app.py:827-835`) then observes
  `scroll_y >= max_scroll_y - 1`, fires `scroll_end` and the view snaps to
  tail.
- On the next arrow keypress, `_update_content_preview:771-780` saves the
  now-clamped values → `_preview_scroll_state[pane] = (0.0, True)`. Returning
  to that pane later restores as "was_at_bottom" → `scroll_end` → tail.

The current design reads widget state at switch time, but widget state
already reflects side-effects of prior refreshes. The fix is to record user
intent at the moment the user scrolls, not at the moment we're about to
discard it.

## Fix

Track scroll intent via Textual event hooks on the scroll container itself,
so `_preview_scroll_state` is updated whenever the user actually scrolls.
Three input channels exist and must all be covered:

- **Mouse wheel** over the preview → `MouseScrollUp` / `MouseScrollDown`
  events dispatched to the scrollable container.
- **Scrollbar track click** (page up/down) → the `ScrollBar` child widget
  posts `ScrollUp` / `ScrollDown` messages to the container, which handle
  them via `_on_scroll_up` / `_on_scroll_down`.
- **Scrollbar thumb drag / jump click** → the scrollbar posts `ScrollTo`
  messages with the target `y`, handled by `_on_scroll_to`.

Arrow/PgUp/PgDn keys are NOT a channel here: in PREVIEW zone they are
forwarded to tmux, in PANE_LIST zone they're consumed by zone navigation.

### Changes in `.aitask-scripts/monitor/monitor_app.py`

1. **New subclass `PreviewScrollContainer(ScrollableContainer)`** (near the
   top of the file, alongside `PreviewPanel`):

   ```python
   class PreviewScrollContainer(ScrollableContainer):
       """ScrollableContainer that reports user-driven scroll changes
       (mouse wheel, scrollbar track click, scrollbar drag)."""

       on_user_scroll: Callable[[], None] | None = None

       def _on_mouse_scroll_up(self, event) -> None:
           super()._on_mouse_scroll_up(event)
           self._notify_user_scroll()

       def _on_mouse_scroll_down(self, event) -> None:
           super()._on_mouse_scroll_down(event)
           self._notify_user_scroll()

       def _on_scroll_up(self, event) -> None:
           super()._on_scroll_up(event)
           self._notify_user_scroll()

       def _on_scroll_down(self, event) -> None:
           super()._on_scroll_down(event)
           self._notify_user_scroll()

       def _on_scroll_to(self, message) -> None:
           super()._on_scroll_to(message)
           self._notify_user_scroll()

       def _notify_user_scroll(self) -> None:
           if self.on_user_scroll is not None:
               self.on_user_scroll()
   ```

   Rationale: Textual's built-in `_on_mouse_scroll_*` / `_on_scroll_*` /
   `_on_scroll_to` handlers (in `textual.widget.Widget`) do the actual
   scrolling via `scroll_page_up/down`, `scroll_to`, etc. We hook
   **after** `super()` so `scroll_y` has already advanced to the user's
   chosen position before we read it. We override the private `_on_*`
   methods (not public `on_*`) because that guarantees we run in the same
   synchronous call chain as the built-in handler — no dispatch races.

2. **Wire the callback in `compose`** (`monitor_app.py:384-396`): replace
   `ScrollableContainer(...)` with `PreviewScrollContainer(...)`.

3. **Register the callback once the widget is mounted** — add in
   `_start_monitoring` or at the top of `_refresh_data` (guarded so it only
   runs once):

   ```python
   scroll = self.query_one("#preview-scroll", PreviewScrollContainer)
   scroll.on_user_scroll = self._record_preview_scroll
   ```

4. **New helper `_record_preview_scroll`** on `MonitorApp`:

   ```python
   def _record_preview_scroll(self) -> None:
       if self._focused_pane_id is None:
           return
       try:
           scroll = self.query_one("#preview-scroll", PreviewScrollContainer)
       except Exception:
           return
       max_y = scroll.max_scroll_y
       scroll_y = scroll.scroll_y
       at_bottom = max_y <= 0 or scroll_y >= max_y - 1
       distance = max(0.0, max_y - scroll_y)
       self._preview_scroll_state[self._focused_pane_id] = (distance, at_bottom)
   ```

5. **Rewrite `_update_content_preview`** (`monitor_app.py:758-844`):

   - **Drop** the save block at lines 771-780 entirely. State now comes from
     `_record_preview_scroll`, which is always current.
   - **Same-pane branch** (lines 827-835) becomes: consult
     `_preview_scroll_state.get(focused_pane_id)` and restore it (tail if
     `was_at_bottom` or missing; `scroll_to(max - distance)` otherwise). This
     undoes any post-`preview.update` clamping on every refresh tick.
   - **Pane-changed branch** (lines 809-826) is unchanged in shape: same
     dict lookup, same `scroll_end` / `scroll_to` calls.

6. **Keep the tail action intact** (`action_scroll_preview_tail`,
   lines 1077-1086): it already writes `(0.0, True)` into
   `_preview_scroll_state`, which remains the correct representation of
   "tail-follow engaged."

7. **Stale-entry cleanup** (lines 479-490) stays unchanged — dropping state
   for panes that disappeared is still correct.

### Secondary nice-to-have (optional, only if trivial)

The same-pane restore path will now fire `call_after_refresh(scroll_to)`
every 3 s even when nothing changed. That is intentional — it re-asserts
the user's intent against any clamping — but we should not animate, and we
already pass `animate=False`. No extra work needed.

## Critical files

- `.aitask-scripts/monitor/monitor_app.py` — all edits (one file).

## Verification

Tested interactively in a real tmux session with ≥2 agent panes.

1. Start a tmux session with at least two agent windows
   (`agent-foo`, `agent-bar`) that each produce ≥200 lines of output so the
   scrollback is saturated.
2. Launch `ait monitor` in a third window.
3. **Scenario A — remember scroll on return:**
   - Arrow to `agent-foo`. Mouse-wheel up ~10 lines.
   - Arrow to `agent-bar`. Expect: starts at tail (first visit).
   - Arrow back to `agent-foo`. **Expect:** same scroll offset as step a, NOT
     tail. (Current bug: snaps to tail.)
4. **Scenario B — tail-follow still works:**
   - Focus `agent-foo`, press `t` (tail). Scroll should snap to bottom.
   - Wait for the 3 s refresh to append more output. Expect: the view keeps
     tailing (stays at bottom).
   - Arrow to `agent-bar` and back. Expect: still at tail.
5. **Scenario C — tail-follow disengages on scroll up:**
   - From tail, mouse-wheel up a few lines.
   - Wait 3 s for refresh. Expect: view does NOT snap back to bottom; the
     same lines stay visible.
   - Repeat using the **scrollbar thumb drag** instead of mouse wheel —
     expect the drag position to stick across refreshes and pane switches.
   - Repeat by **clicking above/below the scrollbar thumb** (page
     scroll) — expect the new position to stick.
6. **Scenario D — across the 3 s refresh while scrolled up:**
   - Scroll up in `agent-foo`. Wait through two 3 s refresh ticks without
     touching anything. Expect: scroll position stays put (does NOT drift to
     tail).
7. **Scenario E — zoom cycle:** Press `z` to cycle preview sizes while
   scrolled up. Expect: scroll position is preserved proportionally (tied to
   `max - distance` anchoring).
8. **Syntax/import check:** `python3 -c "import ast;
   ast.parse(open('.aitask-scripts/monitor/monitor_app.py').read())"`.

No unit tests exist for the monitor TUI (it is interactive and Textual-based),
so validation is exclusively manual through the scenarios above.

## Step 9 reference

After implementation, follow task-workflow Step 9 (commit, archive via
`./.aitask-scripts/aitask_archive.sh 548`, merge).
