---
Task: t513_minimonitor_autoswitch_on_up_down.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

Bug t513: The minimonitor TUI auto-switches tmux windows when navigating between agents with up/down arrow keys. The intended behavior is that arrow keys only change the list selection; only the explicit "s" shortcut should switch tmux windows.

## Root Cause

In `_nav()` (line 314-329 of `.aitask-scripts/monitor/minimonitor_app.py`), after moving focus to a new card, lines 327-329 immediately call `self._monitor.switch_to_pane()` — triggering a tmux window switch on every arrow key press.

## Fix

**File:** `.aitask-scripts/monitor/minimonitor_app.py`

1. Remove the `switch_to_pane` call (lines 327-329) from `_nav()` method
2. Update docstring to reflect navigation-only behavior

The `action_switch_to()` method (bound to "s" key) already correctly handles explicit window switching — no changes needed.

## Verification

1. Run minimonitor TUI
2. Press up/down arrows — selection should move in the list without switching tmux windows
3. Press "s" — should switch to the selected agent's tmux window

## Final Implementation Notes
- **Actual work done:** Removed the `switch_to_pane()` call from `_nav()` in minimonitor_app.py (3 lines deleted) and updated the method docstring. The existing `action_switch_to()` bound to "s" key already handled explicit switching correctly.
- **Deviations from plan:** None — fix was exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Simple removal rather than adding a flag/toggle, since the `action_switch_to()` method already provides the explicit switch pathway.
