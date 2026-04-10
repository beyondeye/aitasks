---
Task: t518_autoswitch_to_agent_that_need_attention.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

## Context

The monitor TUI (`ait monitor`) shows tmux panes running code agents. When monitoring many agents simultaneously, the user must manually select each agent to preview its output. This task adds an "auto-switch" toggle that automatically cycles the preview to the idle agent that has been waiting longest when the currently focused agent is actively running.

## Plan

All changes in a single file: `.aitask-scripts/monitor/monitor_app.py`

### 1. Add `_auto_switch` instance variable

In `__init__`, add:
```python
self._auto_switch: bool = False
```

### 2. Add keybinding `a` for toggle

In `BINDINGS` list, add:
```python
Binding("a", "toggle_auto_switch", "Auto"),
```

### 3. Add `action_toggle_auto_switch` method

```python
def action_toggle_auto_switch(self) -> None:
    self._auto_switch = not self._auto_switch
    if self._auto_switch:
        self.notify("Auto-switch ON: preview follows idle agents needing attention")
    else:
        self.notify("Auto-switch OFF: manual selection only")
    self._rebuild_session_bar()
    self._rebuild_pane_list()
```

### 4. Update `_rebuild_session_bar` to show `[AUTO]` indicator

Add `auto_tag` between pane count and Tab hint.

### 5. Update `_rebuild_pane_list` to show `⟳ AUTO` in agents header

When auto-switch is enabled, the "CODE AGENTS (N)" section header shows `CODE AGENTS (N) ⟳ AUTO` in bold yellow.

### 6. Add auto-switch call in `_refresh_data`

After `self._snapshots = self._monitor.capture_all()`, before UI rebuild:
- Only when enabled AND in PANE_LIST zone
- Calls `_maybe_auto_switch()` and updates `saved_pane_id` if switched

### 7. Add `_maybe_auto_switch` helper method

- If no focused pane or not an AGENT → return False
- If focused agent IS idle → return False (it needs attention, keep it)
- Find all AGENT panes where `is_idle == True`
- Sort by `idle_seconds` descending (most idle first)
- Set `_focused_pane_id` to the most-idle agent
- Return True

## Final Implementation Notes

- **Actual work done:** Added auto-switch toggle feature with `a` keybinding, `_maybe_auto_switch()` logic in the 3-second refresh cycle, `[AUTO]` indicator in session bar, and `⟳ AUTO` indicator in pane list header. Descriptive notification messages on toggle.
- **Deviations from plan:** Added `⟳ AUTO` label to the "CODE AGENTS" section header in the pane list for more visible indication (user feedback). Made notification messages more descriptive ("preview follows idle agents needing attention"). Added `_rebuild_pane_list()` call in the toggle action so the header updates immediately.
- **Issues encountered:** Initial implementation had insufficient visual indication of the auto-switch state. User feedback led to adding the pane list header indicator and more descriptive notification text.
- **Key decisions:** Used the `⟳` (clockwise arrow) Unicode character for the auto-switch indicator to visually convey "cycling". Toggle is session-only (not persisted). Auto-switch only fires on the 3-second refresh cadence to avoid jitter.
