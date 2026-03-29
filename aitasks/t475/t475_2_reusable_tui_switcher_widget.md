---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask_monitor, tui]
created_at: 2026-03-29 10:38
updated_at: 2026-03-29 10:38
---

## Reusable TUI Switcher Widget

Shared Textual widget for quick-switching between TUI windows in tmux, usable by any TUI app via the `j` keybinding.

### Context

This is a cross-cutting feature for the tmux Monitor TUI (parent t475). The TUI Switcher is a modal overlay + mixin class that can be added to ANY Textual TUI app. When `j` is pressed, it shows all aitask TUIs; running ones can be switched to, missing ones can be spawned. The `j` key is confirmed free across ALL existing TUIs.

### Key Files to Create

- `.aitask-scripts/lib/tui_switcher.py` — shared widget module

### Key Files to Reference

- `.aitask-scripts/lib/agent_launch_utils.py` — `load_tmux_defaults()`, `get_tmux_windows()`, `is_tmux_available()`
- `.aitask-scripts/lib/agent_command_screen.py` — existing ModalScreen pattern for tmux interactions
- `.aitask-scripts/board/aitask_board.py` — example of App class structure and BINDINGS

### Implementation Plan

#### 1. TuiSwitcherOverlay (ModalScreen)

```python
class TuiSwitcherOverlay(ModalScreen):
    """Quick-switch overlay listing all aitask TUIs.
    Running TUIs show [switch], missing ones show [spawn].
    Selecting an entry switches to or spawns the TUI window."""

    BINDINGS = [
        Binding("escape", "cancel", "Close"),
        Binding("j", "cancel", "Close"),  # toggle off with same key
    ]
```

**Layout:**
- List of TUI entries (board, codebrowser, brainstorm, settings, monitor, diffviewer)
- Each entry shows: TUI name, status (running/not running), action hint
- Current TUI is highlighted and marked (can't switch to self)
- Compact modal, centered

**Navigation:**
- `Up/Down` — navigate TUI list
- `Enter` — select (switch or spawn)
- `Escape` or `j` — close overlay

**Logic on selection:**
- If TUI is running: `tmux select-window -t <session>:<window_name>` → dismiss
- If TUI is not running: `tmux new-window -t <session> -n <name> 'ait <name>'` → dismiss

Uses `get_tmux_windows()` from `agent_launch_utils.py` to check which TUIs are running.

#### 2. TuiSwitcherMixin

```python
class TuiSwitcherMixin:
    """Mixin class to add TUI switcher support to any Textual App.

    Usage:
        class MyApp(App, TuiSwitcherMixin):
            BINDINGS = [
                *TuiSwitcherMixin.SWITCHER_BINDINGS,
                # ... app-specific bindings
            ]
            def __init__(self):
                super().__init__()
                self.current_tui_name = "board"  # set per-app
    """
    SWITCHER_BINDINGS = [
        Binding("j", "tui_switcher", "Jump to TUI"),
    ]

    def action_tui_switcher(self):
        if not os.environ.get("TMUX"):
            self.notify("TUI switcher requires tmux", severity="warning")
            return
        self.push_screen(TuiSwitcherOverlay(
            session=self._get_tmux_session(),
            current_tui=getattr(self, "current_tui_name", ""),
        ))
```

The mixin reads the tmux session name from `project_config.yaml` via `load_tmux_defaults()`.

#### 3. Known TUI registry

```python
KNOWN_TUIS = [
    ("board", "Task board"),
    ("codebrowser", "Code browser"),
    ("brainstorm", "Brainstorm"),
    ("settings", "Settings"),
    ("monitor", "tmux Monitor"),
    ("diffviewer", "Diff viewer"),
]
```

Each entry maps a window name to a display label. The spawn command is `ait <name>`.

#### 4. Widget CSS

Compact centered modal with scrollable list, color-coded status (green for running, gray for available).

### Verification

- Test overlay opens with `j`, closes with `j` or `Escape`
- Test switch-to for running TUI windows
- Test spawn for missing TUIs
- Test warning shown when not inside tmux ($TMUX not set)
- Test current TUI is not switchable-to (highlighted differently)
