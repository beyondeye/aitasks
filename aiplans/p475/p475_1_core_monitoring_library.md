---
Task: t475_1_core_monitoring_library.md
Parent Task: aitasks/t475_monitor_tui.md
Sibling Tasks: aitasks/t475/t475_2_*.md, aitasks/t475/t475_3_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Implementation Plan: Core Monitoring Library

## Step 1: Create module structure

Create `.aitask-scripts/monitor/__init__.py` (empty) and `.aitask-scripts/monitor/tmux_monitor.py`.

## Step 2: Define data classes

In `tmux_monitor.py`:

```python
from __future__ import annotations
import os, subprocess, time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

class PaneCategory(Enum):
    AGENT = "agent"
    TUI = "tui"
    OTHER = "other"

DEFAULT_AGENT_PREFIXES = ["agent-"]
DEFAULT_TUI_NAMES = {"board", "codebrowser", "settings", "brainstorm", "monitor", "diffviewer"}

@dataclass
class TmuxPaneInfo:
    window_index: str
    window_name: str
    pane_index: str
    pane_id: str
    pane_pid: int
    current_command: str
    width: int
    height: int
    category: PaneCategory

@dataclass
class PaneSnapshot:
    pane: TmuxPaneInfo
    content: str
    timestamp: float
    idle_seconds: float
    is_idle: bool
```

## Step 3: Implement TmuxMonitor class

Constructor accepts `session`, `capture_lines`, `idle_threshold`, `exclude_pane`, `agent_prefixes`, `tui_names`. Store internal state for idle tracking: `_last_content: dict[str, str]`, `_last_change_time: dict[str, float]`.

### Methods:

**`classify_pane(window_name)`**: Check `agent_prefixes` (startswith), then `tui_names` (exact match), else OTHER.

**`discover_panes()`**: Run `tmux list-panes -s -t <session> -F` with tab-delimited format string: `#{window_index}\t#{window_name}\t#{pane_index}\t#{pane_id}\t#{pane_pid}\t#{pane_current_command}\t#{pane_width}x#{pane_height}`. Parse each line, call `classify_pane`, filter out `exclude_pane`.

**`capture_pane(pane_id)`**: Run `tmux capture-pane -p -t <pane_id> -S -<capture_lines>`. Compare content vs `_last_content[pane_id]`. Update idle tracking. Return `PaneSnapshot`.

**`capture_all()`**: Call `discover_panes()`, then `capture_pane()` for each. Return `dict[pane_id, PaneSnapshot]`. Clean up stale entries in `_last_content` for panes that no longer exist.

**`send_enter(pane_id)`**: Run `tmux send-keys -t <pane_id> Enter`. Return success bool.

**`switch_to_pane(pane_id)`**: Run `tmux select-window -t <session>:<window>` then `tmux select-pane -t <pane_id>`. Need to map pane_id to window_index from last discovery.

**`spawn_tui(tui_name)`**: Run `tmux new-window -t <session> -n <tui_name> 'ait <tui_name>'`. Return success bool.

**`get_running_tuis()`**: From last discovery, return set of window_names that are in `tui_names`.

**`get_missing_tuis()`**: Return `tui_names - get_running_tuis()`.

## Step 4: Config loading

Add `load_monitor_config(project_root)` function that reads `project_config.yaml` and extracts `tmux.monitor` section with defaults.

## Step 5: Update existing agent window names

Change these window names to use `agent-` prefix:
- `.aitask-scripts/board/aitask_board.py`: Find `default_window_name=f"pick-{num}"` → `f"agent-pick-{num}"`, `"create-task"` → `"agent-create"`
- `.aitask-scripts/codebrowser/codebrowser_app.py`: Find `f"explain-{...}"` → `f"agent-explain-{...}"`
- `.aitask-scripts/codebrowser/history_screen.py`: Find `f"qa-{task_id}"` → `f"agent-qa-{task_id}"`
- `.aitask-scripts/lib/agent_command_screen.py`: Find default `"aitask"` → `"agent-task"`

## Step 6: Verification

- Test with actual tmux session
- Verify pane discovery, categorization, idle detection, send_enter, switch_to_pane

## Final Implementation Notes

- **Actual work done:** Created `.aitask-scripts/monitor/` package with `tmux_monitor.py` containing `PaneCategory` enum, `TmuxPaneInfo`/`PaneSnapshot` dataclasses, `TmuxMonitor` class with all planned methods, and `load_monitor_config()`. Renamed agent window names in 4 files to use `agent-` prefix. Added `tmux.monitor` config section to `project_config.yaml`.
- **Deviations from plan:** `create-task` and `aitask` fallback window names were NOT renamed (per user feedback — they don't spawn code agents). The task description had listed them for renaming.
- **Issues encountered:** No tmux server running in test environment — verified graceful degradation (empty results, no errors). Classification, config loading, and self-exclusion all tested successfully.
- **Key decisions:** `exclude_pane` defaults to `$TMUX_PANE` env var if not explicitly provided. Idle detection only tracks AGENT panes (TUI/OTHER always report `is_idle=False`). Stale pane entries are cleaned on each `capture_all()` cycle.
- **Notes for sibling tasks:** The `TmuxMonitor` class is ready for import. Use `from monitor.tmux_monitor import TmuxMonitor, load_monitor_config` (with `.aitask-scripts` on sys.path). The `_pane_cache` dict is populated by `discover_panes()` and used by `switch_to_pane()` — always call `discover_panes()` or `capture_all()` before switching. Config loading follows the same pattern as `load_tmux_defaults()` in `agent_launch_utils.py`. The `agent-` prefix convention is now established — future agent windows should use this prefix for automatic categorization.

## Step 9 Reference

Post-implementation: commit, archive, push per task-workflow Step 9.
