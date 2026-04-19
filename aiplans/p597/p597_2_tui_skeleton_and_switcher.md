---
Task: t597_2_tui_skeleton_and_switcher.md
Parent Task: aitasks/t597_ait_stats_tui.md
Sibling Tasks: aitasks/t597/t597_1_*.md, aitasks/t597/t597_3_*.md, aitasks/t597/t597_4_*.md, aitasks/t597/t597_5_*.md, aitasks/t597/t597_6_*.md
Archived Sibling Plans: aiplans/archived/p597/p597_*_*.md
Worktree: (no worktree — current branch)
Branch: main
Base branch: main
---

# Plan: t597_2 — TUI skeleton + dispatcher + switcher integration

## Context

Builds the empty-but-functional shell of the stats TUI: Textual app with sidebar + content area, `ait stats-tui` dispatcher entry, bash wrapper, and registration in the tmux TUI switcher. Panes (t597_3) and the config modal (t597_4) plug into this skeleton.

User decisions baked in:
- Layout: single active pane + sidebar
- Sidebar navigation: ↑/↓ arrows (no `n` binding)
- Refresh: manual via `r`
- Switcher: standard `j` via `TuiSwitcherMixin`

## Implementation Plan

### 1. Bash wrapper `.aitask-scripts/aitask_stats_tui.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH:-}"
exec python3 "$SCRIPT_DIR/stats/stats_app.py" "$@"
```

(Mirror the existing `aitask_board.sh` / `aitask_codebrowser.sh` style — copy whichever is closer.)

### 2. `ait` dispatcher

Add a `stats-tui)` case routing to `.aitask-scripts/aitask_stats_tui.sh "$@"`. Place near the existing `board)` / `codebrowser)` / `monitor)` cases.

### 3. TUI switcher registration

In `.aitask-scripts/lib/tui_switcher.py`:

- Append to `KNOWN_TUIS`: `("stats", "Statistics", "ait stats-tui")`
- In `_TUI_SHORTCUTS` (line ~86), pick a free letter — `t` is most natural for "stats". Verify no clash by reading the dict; if `t` taken, try `S` or `y`.

### 4. Textual app `.aitask-scripts/stats/stats_app.py`

Skeleton:

```python
#!/usr/bin/env python3
"""ait stats TUI."""
import sys
from pathlib import Path

# When launched directly (not via ait stats-tui), wrapper sets PYTHONPATH; safety:
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Container
from textual.widgets import Header, Footer, ListView, ListItem, Label, Static

from lib.tui_switcher import TuiSwitcherMixin
from stats.stats_data import collect_stats, StatsData

# Stub pane list (real one comes in t597_3 / t597_4)
STUB_PANES = [
    ("overview.summary", "Summary"),
    ("overview.daily", "Daily"),
    ("overview.weekday", "Weekday"),
]


class StatsApp(TuiSwitcherMixin, App):
    CSS_PATH = None
    TITLE = "ait stats"

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("r", "refresh", "Refresh"),
        Binding("c", "config", "Config"),
        Binding("q", "quit", "Quit"),
        *TuiSwitcherMixin.SWITCHER_BINDINGS,
    ]

    def __init__(self) -> None:
        super().__init__()
        self.current_tui_name = "stats"
        self.stats_data: StatsData | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield ListView(
                *[ListItem(Label(title), id=pid.replace(".", "_"))
                  for pid, title in STUB_PANES],
                id="sidebar",
            )
            yield Container(id="content")
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()
        self._show_pane(STUB_PANES[0][0])
        self.query_one("#sidebar", ListView).focus()

    def _load_data(self) -> None:
        from datetime import date
        self.stats_data = collect_stats(date.today(), 0)

    def _show_pane(self, pane_id: str) -> None:
        content = self.query_one("#content", Container)
        content.remove_children()
        # Stub renderer (t597_3 replaces this with PANE_DEFS[pane_id].render(...))
        title = next((t for pid, t in STUB_PANES if pid == pane_id), pane_id)
        content.mount(Static(f"[bold]{title}[/bold]\n\n(pane not yet implemented)"))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item is not None and event.item.id is not None:
            self._show_pane(event.item.id.replace("_", ".", 1))

    def action_refresh(self) -> None:
        self._load_data()
        self.notify("Refreshed", timeout=1)

    def action_config(self) -> None:
        self.notify("Config modal coming in t597_4", timeout=2)


if __name__ == "__main__":
    StatsApp().run()
```

### 5. CSS for sidebar/content split

Add `CSS = "..."` inline (or a small `.tcss` file) — sidebar fixed width (e.g., 28), content `1fr`.

### 6. Priority binding caveat (memory)

Per `feedback_textual_priority_bindings`: when t597_4 adds a modal that defines its own `c` / arrow bindings, the `App.action_*` here may swallow keys. Pre-emptively scope guards inside actions to `self.screen.query_one(...)` and raise `textual.actions.SkipAction` when the active screen is a modal. Add a comment in `action_config` to remind the next implementer.

## Verification

```bash
ait stats-tui                       # opens; sidebar visible; arrow keys swap stub content; r notifies; q quits
ait board                           # press j → switcher overlay lists "Statistics" with shortcut t
shellcheck .aitask-scripts/aitask_stats_tui.sh
python3 -c "from textual import __version__; print(__version__)"   # confirm Textual present
```

## Out of Scope

- Real pane widgets (t597_3 — sidebar populated from a hardcoded stub here).
- Config modal logic (t597_4 — `c` is a stub).
- Removing `--plot` (t597_5).
