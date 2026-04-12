---
Task: t523_minimonitor_loosing_agent_focus.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Fix minimonitor selection reset on refresh (t523)

## Context

In `ait minimonitor`, the user's selected agent card in the list loses its
highlight every ~3 seconds (matching the data refresh cycle). After the reset,
pressing up/down starts from the first card again — confirming that
`self.focused` is no longer a `MiniPaneCard` (hits the `ValueError` branch in
`_nav`). The issue reproduces for both the user's own-window agent card and any
other card, so it is not a foreign-selection override from
`_auto_select_own_window` alone.

Root cause is in `_refresh_data` / `_rebuild_pane_list` in
`.aitask-scripts/monitor/minimonitor_app.py`. The rebuild does:

```python
for widget in list(container.children):
    widget.remove()            # returns AwaitRemove, not awaited
...
container.mount(MiniPaneCard(...))   # returns AwaitMount, not awaited
```

Then `_refresh_data` calls `self._restore_focus(saved_pane_id)` *directly*,
assuming the new cards are queryable. Verified against Textual 8.1.1 source:

- `Widget.remove()` schedules async `_prune` tasks gathered on `__await__`.
- `Widget.mount()` returns an `AwaitMount` that blocks on `_mounted_event`.
- `Widget.focus()` is itself deferred via `self.app.call_later(set_focus, self)`.

So when `_restore_focus` runs immediately after the unawaited rebuild, the new
`MiniPaneCard`s are not yet fully mounted and `card.focus()` does not stick.
The fallback `_auto_select_own_window()` has the same query-timing problem, so
nothing ends up focused.

This regression was introduced by t517 which changed `_refresh_data` from
`self.call_after_refresh(self._restore_focus, ...)` to a direct call (see
`aiplans/archived/p517_wrong_selected_agent_in_minimonitor_on_switch.md`). The
separate t517 fix (`_update_own_window_info()` each refresh) is still correct
and must be preserved. The full monitor's `_refresh_data`
(`.aitask-scripts/monitor/monitor_app.py:470-473`) still uses
`call_after_refresh` with an explicit comment: "Immediate restore fails because
removed widgets haven't been fully detached yet."

Intended outcome: the user's selection in the minimonitor is preserved across
refresh cycles and across tmux terminal focus-in events.

## Plan

All changes in `.aitask-scripts/monitor/minimonitor_app.py`.

### 1. Make `_rebuild_pane_list` async and await DOM mutations

Change signature to `async def _rebuild_pane_list(self) -> None`. Replace the
manual `for widget in list(container.children): widget.remove()` with a single
`await container.remove_children()`, and collect new cards into a list that is
mounted via a single `await container.mount_all(cards)`:

```python
async def _rebuild_pane_list(self) -> None:
    container = self.query_one("#mini-pane-list", VerticalScroll)
    await container.remove_children()

    agents = [
        s for s in self._snapshots.values()
        if s.pane.category == PaneCategory.AGENT
    ]
    agents.sort(key=lambda s: (s.pane.window_index, s.pane.pane_index))

    cards: list[MiniPaneCard] = []
    for snap in agents:
        # ... existing card text construction unchanged ...
        cards.append(MiniPaneCard(snap.pane.pane_id, line1))

    if cards:
        await container.mount_all(cards)
```

Both `remove_children()` and `mount_all()` return awaitables in Textual 8.1.1;
awaiting them guarantees `_mounted_event` has fired and prune has completed, so
the next statement sees a stable DOM.

### 2. Await the rebuild in `_refresh_data`

```python
self._rebuild_session_bar()
await self._rebuild_pane_list()
self._restore_focus(saved_pane_id)
```

This keeps `_restore_focus` as a direct (non-deferred) call, which was the
t517 win — but now it runs *after* the DOM is actually stable.

### 3. Guard `on_app_focus` against overriding an existing selection

```python
def on_app_focus(self) -> None:
    """Auto-select own window's agent when this pane regains terminal focus."""
    if isinstance(self.focused, MiniPaneCard):
        return  # user has a valid selection, don't override it
    self._auto_select_own_window()
```

Preserves the t517 intent (auto-select when the minimonitor pane regains focus
and nothing is yet selected) without stomping a user's current selection.
Textual's `AppFocus` event fires when the minimonitor pane gains terminal
focus in tmux, so this guard is load-bearing regardless of the refresh fix.

### 4. Belt-and-braces: update `_focused_pane_id` inside `_restore_focus`

Because `Widget.focus()` is itself deferred (queues a `set_focus` message),
`on_descendant_focus` may not run before the next refresh cycle saves
`self._focused_pane_id`. Set it directly after calling `focus()` to close that
race:

```python
def _restore_focus(self, pane_id: str | None) -> None:
    if pane_id is not None:
        for card in self.query("#mini-pane-list MiniPaneCard"):
            if hasattr(card, "pane_id") and card.pane_id == pane_id:
                card.focus()
                self._focused_pane_id = card.pane_id
                return
    # Fallback: auto-select the card matching this window's agent
    self._auto_select_own_window()
```

Keep the existing fallback behavior unchanged — if `pane_id` is `None` (initial
state) or the saved pane has disappeared from the snapshot, fall through to
`_auto_select_own_window()` so the own-window card is picked up.

## Files modified

- `.aitask-scripts/monitor/minimonitor_app.py`
  - `_refresh_data` — await the rebuild
  - `_rebuild_pane_list` — convert to async, use `remove_children()` + `mount_all()`
  - `_restore_focus` — set `_focused_pane_id` directly on match
  - `on_app_focus` — early return when a `MiniPaneCard` is already focused

No changes to `aitask_minimonitor.sh`, the dispatcher, or project config.

## Verification

Manual (requires a live tmux session with multiple code agent panes, since
minimonitor discovers panes via `TmuxMonitor.capture_all()`):

1. Start a tmux session and launch 2+ code agent panes (e.g., via `ait board`
   pick action), each with a companion minimonitor pane.
2. In one minimonitor, press `↓` to select a non-own-window agent card.
3. Wait >3 seconds through a full refresh cycle.
   - **Expected:** the selected card stays highlighted; no visual reset.
4. Press `↓` again.
   - **Expected:** focus moves to the next card in order, NOT back to the
     first card (confirms `self.focused` is still a `MiniPaneCard`).
5. Select the own-window agent card and wait >3 seconds.
   - **Expected:** selection persists.
6. Switch tmux focus to another pane and then back to the minimonitor pane
   (triggers `AppFocus` → `on_app_focus`).
   - **Expected:** if a card was already selected, it stays selected; if no
     card was selected, the own-window card is auto-picked.
7. Close an agent window whose card was selected.
   - **Expected:** after the next refresh, the vanished pane is gone and the
     own-window fallback selects the own-window card (no crash, no stuck focus).
8. Re-verify t517's original scenario: renumber tmux windows (close a low-index
   window), then press `s` on a card — the correct agent window is switched to
   (confirms `_update_own_window_info` is still running each refresh).

No automated tests exist for the Textual TUI layer; the existing test suite
(`tests/test_*.sh`) is shell-only and does not cover `minimonitor_app.py`.
Sanity check the module imports at minimum: `python -c "import sys;
sys.path.insert(0, '.aitask-scripts'); from monitor import minimonitor_app"`.

## Final Implementation Notes

- **Actual work done:** All four fixes applied to
  `.aitask-scripts/monitor/minimonitor_app.py` exactly as planned.
  1. `_rebuild_pane_list` converted to `async`; `widget.remove()` loop replaced
     with a single `await container.remove_children()`; card mounting batched
     into a list and mounted via a single `await container.mount_all(cards)`.
  2. `_refresh_data` now `await`s the rebuild before calling `_restore_focus`.
  3. `_restore_focus` writes `self._focused_pane_id = card.pane_id` directly
     after a successful `card.focus()` match, closing the `Widget.focus()`
     deferral race.
  4. `on_app_focus` now short-circuits when `isinstance(self.focused,
     MiniPaneCard)` — the user's selection is no longer stomped when the pane
     regains terminal focus.
- **Deviations from plan:** None.
- **Issues encountered:** None. Verified Textual internals (`Widget.remove`
  returns `AwaitRemove`, `Widget.mount` returns `AwaitMount`, `Widget.focus`
  uses `call_later(set_focus, self)`) against Textual 8.1.1 source before
  implementing. Import sanity check (`python -c "...from monitor import
  minimonitor_app"`) passes and both `_rebuild_pane_list` / `_refresh_data`
  are confirmed as coroutine functions.
- **Key decisions:** Went with the awaited `remove_children()` +
  `mount_all()` approach instead of copying the full monitor's
  `call_after_refresh` pattern. The awaited approach is more explicit, avoids
  a second focus-deferral hop, and still preserves the t517 win of running
  `_restore_focus` as a direct (non-deferred) call — just *after* the DOM is
  actually stable. The t517 fix `_update_own_window_info()` each refresh is
  untouched.

## Step 9 (Post-Implementation)

Commit the single-file change with `bug: Fix minimonitor selection reset on
refresh (t523)`, run `./ait git` for the plan file commit, then follow the
standard archive + push flow in the task-workflow Step 9.
