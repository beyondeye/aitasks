---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitor]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-14 12:32
updated_at: 2026-04-14 12:38
---

In `ait monitor` the arrow-key navigation in the agent list is responsive in general (fixed by t544 — tmux captures now run via asyncio), but a residual race remains: if the user presses up/down arrow at exactly the moment a refresh tick fires, the keystroke appears lost — as if the arrow was never pressed. The selection does not move.

## Likely root cause

After t544, `_refresh_data()` still does these synchronous DOM mutations at `.aitask-scripts/monitor/monitor_app.py`:

1. `_rebuild_pane_list()` (`monitor_app.py:636`) — clears all `PaneCard` widgets with `widget.remove()` and mounts new ones with `container.mount()`. This is NOT awaited; the monitor's version is still synchronous (unlike `minimonitor_app.py` which uses `await container.mount_all(...)`).
2. `call_after_refresh(self._restore_focus, saved_pane_id, saved_zone)` (`monitor_app.py:522`) — deferred focus restoration.

Hypothesis: when a user presses an arrow right as the refresh tick fires, the sequence is:
- Arrow key event is posted into Textual's queue.
- Refresh tick runs, captures tmux async (fast), then synchronously tears down all `PaneCard` widgets.
- The currently-focused `PaneCard` (target of the key event) gets removed mid-dispatch, so `_nav_within_zone()` queries the empty DOM or the new cards and the keypress effectively resolves against a destroyed widget.
- `_restore_focus()` fires afterwards and restores focus to the *old* selection index — clobbering the user's attempted navigation.

## Investigation to do

- Reproduce deterministically (e.g., add a test mode that fires arrow keypresses synthetically at refresh-tick boundaries).
- Instrument `on_key` / `_nav_within_zone` to log whether keypresses arrive during an active `_refresh_data` coroutine.
- Check whether `call_after_refresh(self._restore_focus, ...)` is overwriting a user's in-flight selection change.
- Compare with `minimonitor_app.py`, which awaits DOM operations (`await container.remove_children()` / `await container.mount_all()`). Does it exhibit the same bug, or does the `await` happen to serialize it away?

## Candidate fixes (pick after investigation)

1. **Make `_rebuild_pane_list()` async** like minimonitor's version, and `await` it from `_refresh_data()`. Keyboard events dispatched between the old and new DOM would then wait for mount to complete.
2. **Diff-based rebuild:** instead of removing and remounting all cards every tick, reconcile by pane_id — only add new cards, remove gone ones, and update existing cards in place. This removes the "focused widget disappears mid-dispatch" window entirely.
3. **Restore-focus guard:** in `_restore_focus`, don't overwrite the current focus if it is already on a valid `PaneCard` — respect any navigation the user performed while the refresh was in flight.
4. **Key queue during refresh:** set a flag while `_refresh_data` is running; if an arrow key event arrives with the flag set, queue it and replay after `_restore_focus` completes.

## Acceptance criteria

- Holding down `↓` through multiple refresh boundaries produces no "stuck" frame — every press advances the selection.
- No regression in auto-switch or focus-request behavior.

Reference: fixed in t544 — `aiplans/archived/p544_monitor_refresh_vs_user_arrows.md` (async tmux refactor). This is the follow-up for the residual DOM-rebuild race.
