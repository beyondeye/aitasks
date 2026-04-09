---
Task: t511_improved_mini_monitor_agent_switch.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

When pressing "s" in the minimonitor TUI to switch to another agent's tmux window, focus currently goes to the agent pane. This breaks the navigation flow — the user loses the minimonitor UI and can't immediately switch to another agent. The fix: focus the minimonitor companion pane in the target window instead, auto-select the current window's agent in the list, and make arrow keys navigate + switch simultaneously.

## Changes

### 1. `tmux_monitor.py` — Add companion pane lookup + modify `switch_to_pane`

**Add `find_companion_pane_id(window_index)` method** (~line 301, after `switch_to_pane`):
- Runs `tmux list-panes -t SESSION:WINDOW_INDEX -F "#{pane_id}\t#{pane_pid}"`
- For each pane, calls `_is_companion_process(pid)`
- Returns the first companion pane_id found, or None

**Modify `switch_to_pane()`** (line 284):
- Add `prefer_companion: bool = False` parameter
- After `select-window`, if `prefer_companion=True`, call `find_companion_pane_id(window_index)`
- If found, `select-pane` targets the companion pane; otherwise falls back to the original agent pane

### 2. `minimonitor_app.py` — Auto-select own window's agent

**Add `_own_window_index` detection** in `on_mount()` (line 143):
- After the existing `#{window_id}` detection, also query `#{window_index}` for the own pane
- Store as `self._own_window_index`

**Add `_auto_select_own_window()` method**:
- Iterates cards in `#mini-pane-list`, finds the one whose agent's `window_index` matches `_own_window_index` (looked up via `_snapshots`)
- Focuses that card

**Modify `_restore_focus()`** (line 208):
- After trying to restore by saved `pane_id`, if no match found OR pane_id was None, fall back to `_auto_select_own_window()`

**Add `on_app_focus()` handler**:
- Calls `_auto_select_own_window()` when the terminal pane regains focus (fires when tmux switches focus to this pane, requires `focus-events on` in tmux)

### 3. `minimonitor_app.py` — "s" key focuses companion pane

**Modify `action_switch_to()`** (line 323):
- Change `self._monitor.switch_to_pane(pane_id)` to `self._monitor.switch_to_pane(pane_id, prefer_companion=True)`

### 4. `minimonitor_app.py` — Arrow keys navigate + switch

**Modify `_nav()`** (line 293):
- After focusing the new card, get its `pane_id`
- Call `self._monitor.switch_to_pane(pane_id, prefer_companion=True)` to switch the tmux window and focus the target's minimonitor

**Update key hints** (line 130):
- Change to indicate arrow keys also switch

## Files Modified

- `.aitask-scripts/monitor/tmux_monitor.py` — new method + modified `switch_to_pane`
- `.aitask-scripts/monitor/minimonitor_app.py` — auto-select, arrow switching, companion focus

## Verification

1. Open tmux with multiple agent windows (each with minimonitor companion panes)
2. Focus a minimonitor pane
3. Press "s" → should switch to the focused agent's window and focus the minimonitor pane there (not the agent pane)
4. The target minimonitor should auto-select its own window's agent in the list
5. Press Down/Up → should navigate the list AND switch to the corresponding agent's window, focusing the minimonitor
6. Press "i" on a different agent → should show task info (verify existing functionality still works)
7. Test with an agent window that has NO minimonitor companion → should fall back to focusing the agent pane

## Final Implementation Notes
- **Actual work done:** Implemented all 4 planned changes as designed. No deviations from plan.
- **Deviations from plan:** None — the plan was followed exactly.
- **Issues encountered:** None. Both files had clean syntax after changes.
- **Key decisions:** Used `_snapshots` lookup (by pane_id → window_index) for auto-selection instead of storing window_index on MiniPaneCard, keeping the card widget simple. Combined `window_id` and `window_index` detection into a single `tmux display-message` call for efficiency. Arrow key switching only triggers when the selection actually changes (`new_idx != idx`).

## Step 9 (Post-Implementation)
Cleanup, archival, and merge steps per the shared workflow.
