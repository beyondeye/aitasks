---
Task: t475_5_board_tui_integration.md
Parent Task: aitasks/t475_monitor_tui.md
Sibling Tasks: aitasks/t475/t475_1_*.md, aitasks/t475/t475_3_*.md
Archived Sibling Plans: aiplans/archived/p475/p475_*_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Implementation Plan: Board TUI Integration

## Step 1: Command Palette Entry

In `.aitask-scripts/board/aitask_board.py`, add to `KanbanCommandProvider`:

```python
# In discover():
yield DiscoveryHit(...)  # existing entries
yield Hit(score, "Open tmux Monitor", self.action_launch_monitor,
          help="Launch tmux pane monitor in a new window")

# In search():
# Add matching logic for "monitor" search term
```

## Step 2: Launch Monitor Action

```python
def action_launch_monitor(self):
    if is_tmux_available() and os.environ.get("TMUX"):
        launch_in_tmux("ait monitor", TmuxLaunchConfig(
            session=self.manager.tmux_session,
            window="monitor",
            new_session=False,
            new_window=True,
        ))
    else:
        terminal = find_terminal()
        if terminal:
            subprocess.Popen([terminal, "-e", "ait", "monitor"])
    self.notify("Launched tmux Monitor")
```

## Step 3: Keybinding

Add to BINDINGS:
```python
Binding("M", "launch_monitor", "Monitor"),
```

## Step 4: Status Indicator on Task Cards

In `refresh_board()` or a dedicated method:
1. If `is_tmux_available()` and configured session exists:
   - Import `TmuxMonitor` from monitor module
   - Call `discover_panes()` (lightweight, no content capture)
   - Build map: extract task numbers from `agent-pick-<num>` window names
2. In `TaskCard` rendering, check if task number has an active pane
3. Append `[tmux]` badge to the card label

Performance: only on board refresh (default 5min), single subprocess call.

## Verification

- Press `M` in board → monitor launches in new tmux window
- Command palette "monitor" → same
- Pick a task in tmux, then board shows `[tmux]` badge
- Without tmux: `M` launches in terminal or shows error gracefully

## Step 9 Reference

Commit, archive, push per task-workflow Step 9.
