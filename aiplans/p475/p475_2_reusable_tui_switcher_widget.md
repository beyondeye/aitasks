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

## Step 9 Reference

Post-implementation: commit, archive, push per task-workflow Step 9.
