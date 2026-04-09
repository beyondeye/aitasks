---
Task: t496_1_extract_monitor_shared.md
Parent Task: aitasks/t496_minimonitor.md
Sibling Tasks: aitasks/t496/t496_2_core_minimonitor_tui.md, aitasks/t496/t496_3_autospawn_integration.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Extract Shared Monitor Components (t496_1)

## Overview

Extract reusable widgets from `monitor_app.py` into `monitor_shared.py` and add `discover_window_panes()` to `tmux_monitor.py`. This enables both the full monitor and the upcoming mini monitor to share code.

## Steps

### 1. Create `.aitask-scripts/monitor/monitor_shared.py`

Create the new file with the following extracted from `monitor_app.py`:

**Constants and functions:**
- `_DARK_BG_ANSI`, `_ANSI_RESET_RE`, `_ANSI_DEFAULT_BG_RE`
- `_ansi_to_rich_text(ansi_str: str) -> Text`
- `_TASK_ID_RE` regex

**Dataclass:**
- `TaskInfo` (task_id, task_file, title, priority, effort, issue_type, status, body, plan_content)

**Classes:**
- `TaskInfoCache` — task file resolution, frontmatter parsing, plan lookup, caching
- `TaskDetailDialog(ModalScreen)` — read-only task/plan viewer with `p` key toggle
- `KillConfirmDialog(ModalScreen)` — kill confirmation with ANSI preview

Path setup (top of file):
```python
_SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_SCRIPT_DIR / "lib"))
sys.path.insert(0, str(_SCRIPT_DIR / "board"))
```

Imports needed: `re`, `sys`, `os`, `dataclass`, `Path`, `parse_frontmatter` from `task_yaml`, Textual widgets (App, ComposeResult, Binding, Container, VerticalScroll, ScrollableContainer, ModalScreen, Button, Label, Markdown, Static), `Text` and `Style` from rich.

### 2. Update `monitor_app.py`

Remove the extracted code and replace with:
```python
from monitor.monitor_shared import (
    _ansi_to_rich_text, _TASK_ID_RE, TaskInfo, TaskInfoCache,
    TaskDetailDialog, KillConfirmDialog,
)
```

Keep: `Zone`, `ZONE_ORDER`, `PREVIEW_SIZES`, `_TEXTUAL_TO_TMUX`, `SessionBar`, `PaneCard`, `PreviewPane`, `SessionRenameDialog`, `MonitorApp`, helper functions, `main()`.

### 3. Update `tmux_monitor.py`

**3a.** Update `DEFAULT_TUI_NAMES` (line 30):
```python
DEFAULT_TUI_NAMES = {"board", "codebrowser", "settings", "brainstorm", "monitor", "minimonitor", "diffviewer"}
```

**3b.** Add `discover_window_panes()` method after `discover_panes()`:
- Uses `tmux list-panes -t {window_id} -F {fmt}` (no `-s`)
- Same parsing as `discover_panes()` but no `exclude_pane` filtering and no `_pane_cache` update
- Returns `list[TmuxPaneInfo]`

## Verification

1. `python -c "from monitor.monitor_shared import TaskInfoCache, TaskDetailDialog, KillConfirmDialog; print('OK')"`
2. `ait monitor` — full monitor still works identically
3. `python -c "from monitor.tmux_monitor import TmuxMonitor; m = TmuxMonitor('x'); print(hasattr(m, 'discover_window_panes'))"`

## Final Implementation Notes
- **Actual work done:** Extracted 7 items (3 constants, 1 function, 1 dataclass, 3 classes) from `monitor_app.py` into new `monitor_shared.py`. Added `"minimonitor"` to `DEFAULT_TUI_NAMES` and `discover_window_panes()` method to `tmux_monitor.py`. Cleaned up unused imports in `monitor_app.py` (`re`, `dataclass`, `parse_frontmatter`, `Markdown`, `Text`, `Style`).
- **Deviations from plan:** None — plan was accurate. Verified against post-t501 codebase (PreviewPane→PreviewPanel rename had no impact on extracted items).
- **Issues encountered:** None.
- **Key decisions:** `monitor_shared.py` imports `PaneSnapshot` from `tmux_monitor` (needed by `KillConfirmDialog`). `_ansi_to_rich_text` is imported back into `monitor_app.py` since it's used by both `KillConfirmDialog` (extracted) and `MonitorApp._update_content_preview` (stays).
- **Notes for sibling tasks:** The `monitor_shared.py` module provides `_ansi_to_rich_text`, `_TASK_ID_RE`, `TaskInfo`, `TaskInfoCache`, `TaskDetailDialog`, `KillConfirmDialog` — all importable from `monitor.monitor_shared`. The mini monitor (t496_2) should import shared widgets from there. `discover_window_panes(window_id)` is available on `TmuxMonitor` for window-scoped pane discovery without `-s` flag.

## Step 9: Post-Implementation
Archive task, push changes, collect feedback.
