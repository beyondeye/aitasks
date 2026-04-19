---
Task: t597_2_tui_skeleton_and_switcher.md
Parent Task: aitasks/t597_ait_stats_tui.md
Sibling Tasks: aitasks/t597/t597_1_*.md, aitasks/t597/t597_3_*.md, aitasks/t597/t597_4_*.md, aitasks/t597/t597_5_*.md, aitasks/t597/t597_6_*.md
Archived Sibling Plans: aiplans/archived/p597/p597_*_*.md
Worktree: (no worktree — current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7 @ 2026-04-19 18:31
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

## Final Implementation Notes

- **Actual work done:**
  - `.aitask-scripts/aitask_stats_tui.sh` (34 lines, executable): mirrors `aitask_board.sh` with venv-preferred Python, terminal-capability warning, and required-deps check (`textual`, `plotext`). Sets `PYTHONPATH="$SCRIPT_DIR:..."` so `from stats.stats_data import …` and `from lib.tui_switcher import …` both resolve.
  - `ait` dispatcher: added `stats-tui)` case routing to the new wrapper, placed adjacent to the existing `stats)` entry so the related commands sit together.
  - `.aitask-scripts/lib/tui_switcher.py`: appended `("stats", "Statistics", "ait stats-tui")` to `KNOWN_TUIS` (between `settings` and `diffviewer`) and added `"stats": "t"` to `_TUI_SHORTCUTS`. `t` was free.
  - `.aitask-scripts/stats/stats_app.py` (173 lines): Textual `App` subclass `StatsApp(TuiSwitcherMixin, App)`. Layout: `Header` + `Horizontal(ListView#sidebar, Container#content)` + `Footer`. CSS gives the sidebar a fixed 28-cell width with a vertical accent border; content fills the remainder. Bindings: `r` refresh, `c` config (stub, notifies "coming in t597_4"), `q` quit, plus `*TuiSwitcherMixin.SWITCHER_BINDINGS` for `j`. Sidebar auto-focused at startup so `↑`/`↓` work immediately without a manual focus step. `on_list_view_selected` swaps the content container. Stub panes display `total_tasks` / `tasks_7d` / `tasks_30d` from `StatsData` so the skeleton shows live numbers, not just placeholder text.

- **Deviations from plan:**
  - Plan sketch used `Binding("up"/"down", "cursor_up"/"cursor_down", ...)` at the App level; in practice Textual's `ListView` already handles arrow-key navigation when focused, so the explicit bindings would be redundant. Removed them and instead focus the sidebar on mount — same UX, less surface area for binding conflicts when t597_4's modal lands.
  - Two small id helpers (`_pane_id_to_widget_id` / `_widget_id_to_pane_id`) wrap a `pane_<replaced>` prefix: Textual widget ids cannot contain `.`, but pane ids are dotted (`overview.summary`). Encapsulating the conversion in two helpers keeps the round-trip in one place so t597_3 doesn't reinvent it.
  - Wrapper: SC1091 from shellcheck on the `source lib/terminal_compat.sh` line — informational only (file exists; shellcheck just doesn't follow it without `-x`). Mirrored the `aitask_board.sh` style verbatim to stay consistent with how every other TUI wrapper is written.

- **Issues encountered:**
  - First parallel verification batch was cancelled because the dispatcher smoke test (`./ait stats-tui --help`) launched the actual TUI in the foreground (Textual ignores `--help` because the app's `BINDINGS`/argparse don't define one, and just runs). Re-ran the verifications individually and killed the background process.

- **Key decisions:**
  - Sidebar width 28 (not e.g. 25 or 32): wide enough for "Weekday distribution" without wrap, narrow enough that the content area dominates.
  - Stub renderer reads `StatsData` instead of showing static placeholder text. Cheap, validates the data wire-up, and gives the user something to see when smoke-testing the skeleton.
  - Did not subclass `Screen` separately — current scope fits in the App with one `compose()`. t597_4's config modal will push a `ModalScreen`; if that grows complex, extracting the main view to a `MainScreen` class is easy.

- **Notes for sibling tasks:**
  - **t597_3 (panes):** replace `_show_pane()` with `PANE_DEFS[pane_id].render(self.stats_data, content)`. Keep the `_pane_id_to_widget_id` / `_widget_id_to_pane_id` helpers — they're still needed because Textual ids can't contain `.`. The `active_layout` attribute is already a `list[tuple[str, str]]` of `(pane_id, label)` tuples; t597_4 keeps that shape but populates from config. To wire `PANE_DEFS` into the sidebar labels, the layout becomes `list[str]` of pane ids, and the label comes from `PANE_DEFS[pid].title`.
  - **t597_4 (config modal):** the stub `action_config()` notifies "Config modal coming in t597_4" — replace with `self.push_screen(ConfigModal(self.config), self._on_config_done)`. The priority-binding caveat (memory `feedback_textual_priority_bindings`) is documented as a comment block above `action_refresh` for the implementer to reference.
  - **t597_5 (--plot removal):** does not interact with this skeleton. The wrapper's deps check lists `plotext` because the panes (t597_3) need it.
