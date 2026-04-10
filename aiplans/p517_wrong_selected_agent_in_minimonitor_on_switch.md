---
Task: t517_wrong_selected_agent_in_minimonitor_on_switch.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The minimonitor TUI (`minimonitor_app.py`) detects its own tmux window index once at startup in `on_mount()` and stores it in `self._own_window_index`. This value is used by `_auto_select_own_window()` to highlight the agent card matching the minimonitor's own window — so when you look at the minimonitor, your own agent is pre-selected.

**The problem:** The user has `renumber-windows on` in tmux. When tmux windows are closed, tmux renumbers the remaining windows (e.g., window 2 becomes window 1). But `_own_window_index` is never updated after `on_mount()`, so it becomes stale. `_auto_select_own_window()` then focuses the wrong card — typically the second or third agent, depending on how many windows shifted.

This is triggered via `on_app_focus()` (called when the minimonitor pane regains terminal focus) and as a fallback in `_restore_focus()` (called after each 3-second refresh rebuild).

**Secondary issue:** `_restore_focus` is called via `call_after_refresh` (deferred until after screen repaint). This creates a timing window between the pane list rebuild and focus restoration where `on_app_focus` can fire and apply the stale window index, overriding the user's selection before `_restore_focus` corrects it.

## Plan

### Fix 1: Refresh `_own_window_index` on each data cycle

Add a method to re-query the current window index and call it every refresh.

**File:** `.aitask-scripts/monitor/minimonitor_app.py`

Add method after `_check_auto_close`:

```python
def _update_own_window_info(self) -> None:
    """Re-query own window index (handles tmux renumber-windows)."""
    own_pane = os.environ.get("TMUX_PANE", "")
    if not own_pane:
        return
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "-t", own_pane,
             "#{window_id}\t#{window_index}"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split("\t")
            if len(parts) >= 1:
                self._own_window_id = parts[0]
            if len(parts) >= 2:
                self._own_window_index = parts[1]
    except Exception:
        pass
```

Call it in `_refresh_data` after `capture_all()`:

```python
self._snapshots = self._monitor.capture_all()
self._update_own_window_info()  # <-- NEW
```

### Fix 2: Call `_restore_focus` directly instead of deferred

In `_refresh_data`, change:

```python
self.call_after_refresh(self._restore_focus, saved_pane_id)
```

to:

```python
self._restore_focus(saved_pane_id)
```

Cards are already in the DOM after `_rebuild_pane_list` (Textual's `mount` is synchronous), so `_restore_focus` can find and focus them immediately. This eliminates the timing window where `on_app_focus` could override focus with a stale index.

### Files modified

- `.aitask-scripts/monitor/minimonitor_app.py` — add `_update_own_window_info()`, call it in `_refresh_data`, change deferred `_restore_focus` to direct call

### Verification

1. Start multiple agent windows with minimonitor side panels
2. Close a non-agent window (or any window with a lower index) to trigger tmux renumbering
3. In the minimonitor, navigate to the first agent and press 's'
4. Verify the correct agent window is switched to and the correct card stays highlighted
5. Repeat with different agents to confirm all selections work

## Final Implementation Notes

- **Actual work done:** Added `_update_own_window_info()` method that re-queries the minimonitor's window index from tmux on each 3-second refresh cycle (same `display-message` command already used in `on_mount`). Changed `_restore_focus` from deferred (`call_after_refresh`) to direct call to eliminate the timing window. Both fixes applied exactly as planned.
- **Deviations from plan:** None.
- **Issues encountered:** None — the two changes were straightforward additions.
- **Key decisions:** Chose to update both `_own_window_id` and `_own_window_index` in the refresh method (same tmux command returns both), even though only `_own_window_index` was strictly needed for this bug. This keeps the values consistent.

### Step 9 (Post-Implementation)

Archive task t517 and push.
