---
priority: medium
effort: medium
depends: [t475_4]
issue_type: feature
status: Ready
labels: [aitask_monitor, tui]
created_at: 2026-03-29 10:41
updated_at: 2026-03-29 10:41
---

## Board TUI Integration

Add monitor-specific features to the board TUI: command palette entry to launch monitor, keybinding, and tmux status indicators on task cards.

### Context

This integrates the tmux Monitor (t475_3) into the board TUI. Users can launch the monitor from the board and see which tasks have active tmux panes.

### Key Files to Modify

- `.aitask-scripts/board/aitask_board.py` — `KanbanApp`, `KanbanCommandProvider`, `TaskCard`

### Key Files to Reference

- `.aitask-scripts/monitor/tmux_monitor.py` — core library (t475_1), specifically `discover_panes()`
- `.aitask-scripts/monitor/monitor_app.py` — monitor app (t475_3)
- `.aitask-scripts/lib/agent_launch_utils.py` — `launch_in_tmux()`, `is_tmux_available()`

### Implementation Plan

#### 1. Command Palette Entry

Add to `KanbanCommandProvider.discover()` and `search()` (~line 2484):

```python
Hit(score, "Open tmux Monitor", self.action_launch_monitor,
    help="Launch the tmux pane monitor in a new window")
```

Implement `action_launch_monitor()` in `KanbanApp`:
- If inside tmux: spawn `ait monitor` in a new tmux window using `launch_in_tmux()`
- If not in tmux: launch in a new terminal using `find_terminal()` + subprocess
- Show notification: "Launched tmux Monitor"

#### 2. Keybinding

Add `M` keybinding to `KanbanApp.BINDINGS`:
```python
Binding("M", "launch_monitor", "Monitor", show=True),
```

The `M` key (uppercase, requires shift) is unused in the board and distinctive enough to avoid accidental triggers.

#### 3. Status Indicator on Task Cards

During `refresh_board()` (or on a lighter refresh), if tmux is available:
- Call `TmuxMonitor.discover_panes()` with the configured session (lightweight, no content capture)
- Build a map: task_number → pane_id for agent windows matching `agent-pick-<num>` pattern
- In `TaskCard` rendering, if the task number has an active pane, append a `[tmux]` badge

**Performance note:** `discover_panes()` only runs `tmux list-panes` (single subprocess call, fast). Content capture is NOT done. This runs on board refresh (default: every 5 minutes), not on every render.

### Verification

- Open board, press `M` — verify monitor launches
- Open command palette, search "monitor" — verify entry appears
- Pick a task in tmux, then check board — verify `[tmux]` badge on the task card
- Test without tmux installed — verify no errors (badges silently hidden)
