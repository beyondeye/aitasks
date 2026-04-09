---
priority: medium
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [aitask_monitor, aitask_monitormini]
created_at: 2026-04-09 09:06
updated_at: 2026-04-09 09:06
---

## Context

Task t496 (Mini Monitor TUI) requires shared widgets that currently live inside `monitor_app.py`. Before creating the mini monitor, extract reusable components into a new `monitor_shared.py` module. This is a prerequisite for t496_2 (core minimonitor) since both the full and mini monitor need these widgets.

## Key Files to Modify

- `.aitask-scripts/monitor/monitor_shared.py` — **NEW** shared module
- `.aitask-scripts/monitor/monitor_app.py` — extract code out, replace with imports
- `.aitask-scripts/monitor/tmux_monitor.py` — add `"minimonitor"` to `DEFAULT_TUI_NAMES`, add `discover_window_panes()` method

## What to Extract from `monitor_app.py` → `monitor_shared.py`

1. Constants: `_DARK_BG_ANSI`, `_ANSI_RESET_RE`, `_ANSI_DEFAULT_BG_RE` (lines ~50-53)
2. Function: `_ansi_to_rich_text()` (lines ~55-74)
3. Constant: `_TASK_ID_RE` regex (line ~147)
4. Dataclass: `TaskInfo` (lines ~151-162)
5. Class: `TaskInfoCache` (lines ~164-266) — task file resolution and caching
6. Class: `TaskDetailDialog(ModalScreen)` (lines ~269-337) — read-only task/plan viewer
7. Class: `KillConfirmDialog(ModalScreen)` (lines ~407-490) — kill confirmation with preview

## Implementation Plan

### 1. Create `monitor_shared.py`

Path: `.aitask-scripts/monitor/monitor_shared.py`

Required imports and path setup (same pattern as `monitor_app.py`):
```python
"""monitor_shared - Shared widgets and utilities for monitor TUIs."""
from __future__ import annotations

import os, re, sys
from dataclasses import dataclass
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_SCRIPT_DIR / "lib"))
sys.path.insert(0, str(_SCRIPT_DIR / "board"))

from task_yaml import parse_frontmatter  # noqa: E402
# Textual imports as needed for TaskDetailDialog, KillConfirmDialog
```

Move the 7 items listed above into this file. Maintain exact same logic and CSS.

### 2. Update `monitor_app.py`

Replace extracted code with imports:
```python
from monitor.monitor_shared import (
    _ansi_to_rich_text, _TASK_ID_RE, TaskInfo, TaskInfoCache,
    TaskDetailDialog, KillConfirmDialog,
)
```

Keep in `monitor_app.py`: `Zone`, `ZONE_ORDER`, `PREVIEW_SIZES`, `_TEXTUAL_TO_TMUX`, `SessionBar`, `PaneCard`, `PreviewPane`, `SessionRenameDialog`, `MonitorApp`, `_detect_tmux_session`, `_load_project_tmux_config`, `main()`.

### 3. Update `tmux_monitor.py`

**3a.** Add `"minimonitor"` to `DEFAULT_TUI_NAMES` on line 30:
```python
DEFAULT_TUI_NAMES = {"board", "codebrowser", "settings", "brainstorm", "monitor", "minimonitor", "diffviewer"}
```

**3b.** Add method to `TmuxMonitor` class after `discover_panes()` (~line 128):
```python
def discover_window_panes(self, window_id: str) -> list[TmuxPaneInfo]:
    """Discover panes in a specific window (not session-wide).
    Uses 'tmux list-panes -t window_id' (no -s flag).
    """
```
Same format string and parsing as `discover_panes()` but:
- Target: `["tmux", "list-panes", "-t", window_id, "-F", fmt]` (no `-s`)
- No `exclude_pane` filtering (caller handles that)
- Does NOT update `_pane_cache` (read-only check)

## Verification Steps

1. `python -c "from monitor.monitor_shared import TaskInfoCache, TaskDetailDialog, KillConfirmDialog"` — imports work
2. `ait monitor` — full monitor still works (regression check)
3. Run from the `.aitask-scripts/` directory: `python -c "from monitor.tmux_monitor import TmuxMonitor; m = TmuxMonitor('test'); print(hasattr(m, 'discover_window_panes'))"` — prints True
