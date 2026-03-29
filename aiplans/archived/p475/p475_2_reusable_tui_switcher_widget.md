---
Task: t475_2_reusable_tui_switcher_widget.md
Parent Task: aitasks/t475_monitor_tui.md
Sibling Tasks: aitasks/t475/t475_1_*.md, aitasks/t475/t475_3_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Implementation Plan: Reusable TUI Switcher Widget

## Step 1: Create module file

Create `.aitask-scripts/lib/tui_switcher.py`.

## Step 2: Define KNOWN_TUIS registry

```python
KNOWN_TUIS = [
    ("board", "Task Board"),
    ("codebrowser", "Code Browser"),
    ("brainstorm", "Brainstorm"),
    ("settings", "Settings"),
    ("monitor", "tmux Monitor"),
    ("diffviewer", "Diff Viewer"),
]
```

## Step 3: Implement TuiSwitcherOverlay

A `ModalScreen` that:
- On mount, queries `tmux list-windows -t <session>` to find running TUIs
- Renders a scrollable list of `TuiEntry` widgets (one per KNOWN_TUI)
- Each entry shows: name, status indicator (running/available), description
- Current TUI is marked and non-selectable
- Keybindings: `Up/Down` navigate, `Enter` selects, `Escape`/`j` closes

On selection:
- Running TUI → `tmux select-window -t <session>:<name>`
- Missing TUI → `tmux new-window -t <session> -n <name> 'ait <name>'`
- Dismiss modal after action

CSS: Centered modal, ~40 chars wide, compact list with color-coded entries.

## Step 4: Implement TuiSwitcherMixin

```python
class TuiSwitcherMixin:
    SWITCHER_BINDINGS = [
        Binding("j", "tui_switcher", "Jump to TUI"),
    ]

    def action_tui_switcher(self):
        if not os.environ.get("TMUX"):
            self.notify("TUI switcher requires tmux", severity="warning")
            return
        session = self._resolve_tmux_session()
        self.push_screen(TuiSwitcherOverlay(
            session=session,
            current_tui=getattr(self, "current_tui_name", ""),
        ))

    def _resolve_tmux_session(self):
        # Load from project_config.yaml via load_tmux_defaults()
        ...
```

## Step 5: Verification

- Test overlay open/close with `j`
- Test switch and spawn actions
- Test outside tmux (warning notification)
- Test current TUI highlighting

## Final Implementation Notes

**File created:** `.aitask-scripts/lib/tui_switcher.py`

**Components implemented:**
- `KNOWN_TUIS`: Registry of 6 TUIs with (window_name, display_label, launch_command) tuples
- `TuiSwitcherOverlay(ModalScreen)`: Centered modal with ListView, color-coded status indicators (cyan=current, green=running, dim=available). Binds `Enter` to switch, `j`/`Escape` to close
- `TuiSwitcherMixin`: Adds `j` binding and `action_tui_switcher()`. Checks `$TMUX` env, loads session from `project_config.yaml` via `load_tmux_defaults()`
- `_TuiListItem(ListItem)`: Custom list item with status indicators

**Key decisions:**
- Used `get_tmux_windows()` from `agent_launch_utils.py` (lightweight, same lib directory) rather than the heavier `TmuxMonitor` class
- `j` key confirmed free at App level in all 6 TUI apps. Widget-level conflict in brainstorm DAGDisplay is acceptable (widget bindings take priority when focused)
- Launch command for missing TUIs uses `ait <name>` pattern, matching existing tmux session conventions
- `subprocess.Popen` for tmux commands (non-blocking, matches `agent_command_screen.py` pattern)

**For sibling tasks:** Apps integrate by adding `TuiSwitcherMixin` to class bases, including `*TuiSwitcherMixin.SWITCHER_BINDINGS` in BINDINGS, and setting `self.current_tui_name` in `__init__`
