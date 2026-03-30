---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [tui, tmux]
created_at: 2026-03-30 10:36
updated_at: 2026-03-30 10:36
---

## Enhance TUI Switcher Dialog

Improve the TUI Switcher overlay (`tui_switcher.py`) with three enhancements:

### 1. Arrow Key Wrap-Around

Currently, Textual's standard `ListView` stops at the top/bottom of the list. Add wrap-around behavior so pressing Down on the last selectable item moves to the first selectable item, and pressing Up on the first selectable item moves to the last.

**Files:** `.aitask-scripts/lib/tui_switcher.py` — override key handling in `TuiSwitcherOverlay` or subclass `ListView`.

### 2. Show All Tmux Windows (Grouped by Type)

Currently the switcher only shows the 6 hardcoded `KNOWN_TUIS`. Extend it to discover and display all windows in the current tmux session, grouped by category:

- **TUIs** — existing known TUI windows (board, codebrowser, settings, brainstorm, monitor, diffviewer)
- **Code Agents** — windows running code agents (use classification from `tmux_monitor.py` `PaneCategory.AGENT`)
- **Other** — any other tmux windows not in the above categories

Use `get_tmux_windows()` or `TmuxMonitor.discover_panes()` for discovery. Display group headers in the list. Non-TUI windows should use `tmux select-window` to switch (no launch command needed since they already exist).

### 3. Keyboard Shortcuts for Specific TUIs

Add single-key shortcuts that are context-aware (only active when the switcher overlay is open):

- `b` → Task **B**oard
- `c` → **C**ode Browser
- `s` → **S**ettings
- `r` → b**R**ainstorm

These should immediately switch to the target TUI (launching it if not running), bypassing the need to arrow-navigate and press Enter. Update the hint text at the bottom of the dialog to show available shortcuts.

### Key Files

- `.aitask-scripts/lib/tui_switcher.py` — main switcher widget (233 lines)
- `.aitask-scripts/lib/agent_launch_utils.py` — `get_tmux_windows()` discovery
- `.aitask-scripts/monitor/tmux_monitor.py` — `PaneCategory` classification, `discover_panes()`
- All 5 integrating apps: board (`aitask_board.py`), codebrowser (`codebrowser_app.py`), settings (`settings_app.py`), brainstorm (`brainstorm_app.py`), monitor (`monitor_app.py`)
