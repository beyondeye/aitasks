---
Task: t577_wrong_agent_in_minimonitor_agent_list_selected_on_window_swi.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Fix minimonitor auto-selection on window switch (t577)

## Context

The minimonitor TUI has an "s" shortcut that switches tmux focus to the selected agent's window, preferring the companion minimonitor pane. After the switch, the minimonitor in the target window should auto-select the agent running in that window. This doesn't work because the `on_app_focus()` handler has a guard that prevents auto-selection when any card is already focused.

## Root Cause

In `minimonitor_app.py:275-281`:

```python
def on_app_focus(self) -> None:
    if isinstance(self.focused, MiniPaneCard):
        return  # BUG: skips auto-select when a card is already focused
    self._auto_select_own_window()
```

When the "s" switch lands on window B's minimonitor, `on_app_focus()` fires but returns early because minimonitor B already has a previously focused card. The `_auto_select_own_window()` method (which correctly selects the own window's agent) never runs.

## Fix

**File:** `.aitask-scripts/monitor/minimonitor_app.py`

Remove the guard in `on_app_focus()` so `_auto_select_own_window()` always runs when the app gains terminal focus:

```python
def on_app_focus(self) -> None:
    """Auto-select own window's agent when this pane regains terminal focus."""
    self._auto_select_own_window()
```

**Why this is safe:** The minimonitor's primary UX contract is "show the agent in MY window as selected." When terminal focus arrives (from window switch, tab-back, or any other source), re-selecting the own window's agent is correct. The `_restore_focus()` method (called during refresh cycles) separately preserves user navigation within the list between refreshes — that's unaffected.

## Verification

1. Open multiple agent windows (each with a companion minimonitor)
2. In minimonitor, navigate with arrows to select a different agent
3. Press "s" to switch to that agent's window
4. Verify the minimonitor in the target window now highlights the agent running in that window
5. Press "tab" to go to the agent pane, then "tab" back — verify the minimonitor still shows own agent

## Final Implementation Notes
- **Actual work done:** Removed the `isinstance(self.focused, MiniPaneCard)` guard in `on_app_focus()` so that `_auto_select_own_window()` always runs when the minimonitor regains terminal focus. This is a 3-line removal, no new code added.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Chose to always auto-select on focus rather than a targeted signaling mechanism (e.g., tmux env var from the "s" action). The simpler approach is correct because the minimonitor's purpose is to reflect the agent in its own window, and `_restore_focus()` (the refresh-cycle path) separately preserves navigation between refreshes.
