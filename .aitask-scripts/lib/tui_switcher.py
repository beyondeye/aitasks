"""tui_switcher - Reusable TUI switcher widget for quick-switching between aitask TUIs in tmux.

Provides a ModalScreen overlay showing all known TUIs with their running status,
and a mixin that any Textual App can use to add the switcher with a single keybinding.

Usage:
    from tui_switcher import TuiSwitcherMixin

    class MyApp(TuiSwitcherMixin, App):
        BINDINGS = [
            *TuiSwitcherMixin.SWITCHER_BINDINGS,
            Binding("q", "quit", "Quit"),
            # ... other bindings
        ]

        def __init__(self):
            super().__init__()
            self.current_tui_name = "board"  # name of this TUI
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView, Static

# Add lib dir to path for agent_launch_utils import
_LIB_DIR = str(Path(__file__).resolve().parent)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from agent_launch_utils import get_tmux_windows, load_tmux_defaults  # noqa: E402


def _detect_current_session() -> str | None:
    """Auto-detect the current tmux session name, or None if not inside tmux."""
    if not os.environ.get("TMUX"):
        return None
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#S"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


# Registry of known TUIs: (window_name, display_label, launch_command)
# window_name must match what tmux uses (the -n flag when creating the window)
KNOWN_TUIS = [
    ("board", "Task Board", "ait board"),
    ("codebrowser", "Code Browser", "ait codebrowser"),
    ("brainstorm", "Brainstorm", "ait brainstorm"),
    ("settings", "Settings", "ait settings"),
    ("monitor", "tmux Monitor", "ait monitor"),
    ("diffviewer", "Diff Viewer", "ait diffviewer"),
]


class _TuiListItem(ListItem):
    """A list item representing a TUI entry in the switcher."""

    def __init__(self, name: str, label: str, running: bool, is_current: bool) -> None:
        super().__init__()
        self.tui_name = name
        self.tui_label = label
        self.running = running
        self.is_current = is_current

    def compose(self):
        if self.is_current:
            indicator = "[bold cyan]\u25b6[/]"
            style = "bold cyan"
        elif self.running:
            indicator = "[green]\u25cf[/]"
            style = "green"
        else:
            indicator = "[dim]\u25cb[/]"
            style = "dim"
        yield Static(f" {indicator}  [{style}]{self.tui_label}[/]")


class TuiSwitcherOverlay(ModalScreen):
    """Modal overlay listing known TUIs with status and quick-switch capability."""

    DEFAULT_CSS = """
    TuiSwitcherOverlay {
        align: center middle;
    }
    #switcher_dialog {
        width: 44;
        height: auto;
        max-height: 22;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #switcher_title {
        text-align: center;
        text-style: bold;
        padding: 0 0 1 0;
        width: 100%;
    }
    #switcher_list {
        height: auto;
        max-height: 14;
    }
    #switcher_hint {
        text-align: center;
        padding: 1 0 0 0;
        color: $text-muted;
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_overlay", "Close", show=False),
        Binding("j", "dismiss_overlay", "Close", show=False),
        Binding("enter", "select_tui", "Switch", show=False),
    ]

    def __init__(self, session: str, current_tui: str = "") -> None:
        super().__init__()
        self._session = session
        self._current_tui = current_tui

    def compose(self):
        with Container(id="switcher_dialog"):
            yield Label("TUI Switcher", id="switcher_title")
            yield ListView(id="switcher_list")
            yield Label("[dim]Enter[/dim] switch  [dim]j/Esc[/dim] close", id="switcher_hint")

    def on_mount(self) -> None:
        running_windows = get_tmux_windows(self._session)
        running_names = {name for _, name in running_windows}

        list_view = self.query_one("#switcher_list", ListView)
        first_selectable_idx = None
        for idx, (name, label, _cmd) in enumerate(KNOWN_TUIS):
            is_current = name == self._current_tui
            running = name in running_names
            item = _TuiListItem(name, label, running, is_current)
            if is_current:
                item.disabled = True
            elif first_selectable_idx is None:
                first_selectable_idx = idx
            list_view.append(item)
        if first_selectable_idx is not None:
            list_view.index = first_selectable_idx

    def action_dismiss_overlay(self) -> None:
        self.dismiss(None)

    def action_select_tui(self) -> None:
        list_view = self.query_one("#switcher_list", ListView)
        if list_view.highlighted_child is None:
            return
        item = list_view.highlighted_child
        if not isinstance(item, _TuiListItem) or item.is_current:
            return
        self._switch_to(item.tui_name, item.running)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if not isinstance(item, _TuiListItem) or item.is_current:
            return
        self._switch_to(item.tui_name, item.running)

    def _switch_to(self, name: str, running: bool) -> None:
        try:
            if running:
                subprocess.Popen(
                    ["tmux", "select-window", "-t", f"{self._session}:{name}"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            else:
                cmd = self._get_launch_command(name)
                # Trailing colon ensures tmux interprets target as session, not window
                subprocess.Popen(
                    ["tmux", "new-window", "-t", f"{self._session}:", "-n", name, cmd],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
        except (FileNotFoundError, OSError):
            self.app.notify(f"Failed to switch to {name}", severity="error")
            return
        self.dismiss(name)

    @staticmethod
    def _get_launch_command(name: str) -> str:
        for tui_name, _, cmd in KNOWN_TUIS:
            if tui_name == name:
                return cmd
        return f"ait {name}"


class TuiSwitcherMixin:
    """Mixin for Textual Apps to add TUI switcher support.

    Usage:
        class MyApp(TuiSwitcherMixin, App):
            BINDINGS = [
                *TuiSwitcherMixin.SWITCHER_BINDINGS,
                ...
            ]
            def __init__(self):
                super().__init__()
                self.current_tui_name = "board"
    """

    SWITCHER_BINDINGS = [
        Binding("j", "tui_switcher", "Jump TUI", show=False),
    ]

    def action_tui_switcher(self) -> None:
        if not os.environ.get("TMUX"):
            self.notify("TUI switcher requires tmux", severity="warning")
            return
        # Prefer auto-detecting current tmux session, fall back to config
        session = _detect_current_session()
        if session is None:
            defaults = load_tmux_defaults(Path.cwd())
            session = defaults.get("default_session", "aitasks")
        current = getattr(self, "current_tui_name", "")
        self.push_screen(TuiSwitcherOverlay(session=session, current_tui=current))
