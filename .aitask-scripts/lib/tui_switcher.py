"""tui_switcher - Reusable TUI switcher widget for quick-switching between aitask TUIs in tmux.

Provides a ModalScreen overlay showing all known TUIs with their running status,
plus any other tmux windows (agents, shells) grouped by type, and a mixin that
any Textual App can use to add the switcher with a single keybinding.

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
    ("settings", "Settings", "ait settings"),
    ("monitor", "tmux Monitor", "ait monitor"),
    ("diffviewer", "Diff Viewer", "ait diffviewer"),
]

# Classification constants (mirrors tmux_monitor.py without importing it)
_AGENT_PREFIXES = ["agent-"]
_TUI_NAMES = {name for name, _, _ in KNOWN_TUIS} | {"git"}
_BRAINSTORM_PREFIX = "brainstorm-"

# Shortcut keys for specific TUIs: (key, tui_name)
_TUI_SHORTCUTS = {
    "board": "b",
    "codebrowser": "c",
    "settings": "s",
}


def _discover_brainstorm_sessions() -> list[str]:
    """Scan .aitask-crews/crew-brainstorm-*/ for existing brainstorm sessions.

    Returns list of task numbers with existing sessions.
    """
    crews_dir = Path(".aitask-crews")
    if not crews_dir.is_dir():
        return []
    prefix = "crew-brainstorm-"
    sessions = []
    for entry in sorted(crews_dir.iterdir()):
        if entry.is_dir() and entry.name.startswith(prefix):
            session_file = entry / "br_session.yaml"
            if session_file.is_file():
                sessions.append(entry.name[len(prefix):])
    return sessions


def _classify_window(name: str) -> str:
    """Classify a tmux window name as 'tui', 'agent', or 'other'."""
    if name in _TUI_NAMES:
        return "tui"
    if name.startswith(_BRAINSTORM_PREFIX):
        return "tui"
    for prefix in _AGENT_PREFIXES:
        if name.startswith(prefix):
            return "agent"
    return "other"


class _WrappingListView(ListView):
    """ListView that wraps cursor around when reaching edges."""

    def action_cursor_down(self) -> None:
        old = self.index
        super().action_cursor_down()
        if self.index == old and old is not None:
            # At bottom — wrap to first selectable item
            for i, child in enumerate(self.children):
                if isinstance(child, ListItem) and not child.disabled:
                    self.index = i
                    return

    def action_cursor_up(self) -> None:
        old = self.index
        super().action_cursor_up()
        if self.index == old and old is not None:
            # At top — wrap to last selectable item
            items = list(self.children)
            for i in range(len(items) - 1, -1, -1):
                if isinstance(items[i], ListItem) and not items[i].disabled:
                    self.index = i
                    return


class _GroupHeader(ListItem):
    """Non-selectable group separator in the switcher list."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self._title = title
        self.disabled = True

    def compose(self):
        yield Static(f"[bold dim]\u2500\u2500 {self._title} \u2500\u2500[/]")


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
            indicator = "[bright_green]\u25cf[/]"
            style = "bright_green"
        else:
            indicator = "[dim]\u25cb[/]"
            style = "dim"
        # Show shortcut hint if this TUI has one
        shortcut = _TUI_SHORTCUTS.get(self.tui_name)
        hint = f" [dim]({shortcut})[/]" if shortcut and not self.is_current else ""
        yield Static(f" {indicator}  [{style}]{self.tui_label}[/]{hint}")


class _WindowListItem(ListItem):
    """A list item representing a non-TUI tmux window."""

    def __init__(self, window_name: str, window_index: str) -> None:
        super().__init__()
        self.window_name = window_name
        self.window_index = window_index

    def compose(self):
        yield Static(f" [bright_green]\u25cf[/]  {self.window_name}")


class TuiSwitcherOverlay(ModalScreen):
    """Modal overlay listing known TUIs with status and quick-switch capability."""

    DEFAULT_CSS = """
    TuiSwitcherOverlay {
        align: center middle;
    }
    #switcher_dialog {
        width: 44;
        height: auto;
        max-height: 30;
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
        max-height: 22;
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
        Binding("b", "shortcut_board", "Board", show=False),
        Binding("c", "shortcut_codebrowser", "Code Browser", show=False),
        Binding("s", "shortcut_settings", "Settings", show=False),
        Binding("r", "shortcut_brainstorm", "Brainstorm", show=False),
        Binding("x", "shortcut_explore", "Explore", show=False),
    ]

    def __init__(self, session: str, current_tui: str = "") -> None:
        super().__init__()
        self._session = session
        self._current_tui = current_tui
        self._running_names: set[str] = set()

    def compose(self):
        with Container(id="switcher_dialog"):
            yield Label("TUI Switcher", id="switcher_title")
            yield _WrappingListView(id="switcher_list")
            yield Label(
                "[dim]b[/]oard  [dim]c[/]ode  [dim]s[/]ettings  b[dim]r[/]ainstorm  e[dim]x[/]plore\n"
                "[dim]Enter[/] switch  [dim]j/Esc[/] close",
                id="switcher_hint",
            )

    def on_mount(self) -> None:
        running_windows = get_tmux_windows(self._session)
        self._running_names = {name for _, name in running_windows}
        running_by_name = {name: idx for idx, name in running_windows}

        list_view = self.query_one("#switcher_list", _WrappingListView)
        item_idx = 0
        first_selectable_idx = None

        # --- TUI Group ---
        list_view.append(_GroupHeader("TUIs"))
        item_idx += 1

        for name, label, _cmd in KNOWN_TUIS:
            is_current = name == self._current_tui
            running = name in self._running_names
            item = _TuiListItem(name, label, running, is_current)
            if is_current:
                item.disabled = True
            elif first_selectable_idx is None:
                first_selectable_idx = item_idx
            list_view.append(item)
            item_idx += 1

        # --- Dynamic brainstorm session entries ---
        brainstorm_sessions = _discover_brainstorm_sessions()
        all_brainstorm_nums = set(brainstorm_sessions)
        for name in self._running_names:
            if name.startswith(_BRAINSTORM_PREFIX):
                all_brainstorm_nums.add(name[len(_BRAINSTORM_PREFIX):])
        for task_num in sorted(all_brainstorm_nums):
            win_name = f"{_BRAINSTORM_PREFIX}{task_num}"
            label = f"Brainstorm (t{task_num})"
            running = win_name in self._running_names
            is_current = win_name == self._current_tui
            item = _TuiListItem(win_name, label, running, is_current)
            if is_current:
                item.disabled = True
            elif first_selectable_idx is None:
                first_selectable_idx = item_idx
            list_view.append(item)
            item_idx += 1

        # --- Classify non-TUI windows ---
        agents = []
        others = []
        for win_idx, win_name in running_windows:
            if win_name in _TUI_NAMES:
                continue
            cat = _classify_window(win_name)
            if cat == "agent":
                agents.append((win_idx, win_name))
            else:
                others.append((win_idx, win_name))

        # --- Agent Group ---
        if agents:
            list_view.append(_GroupHeader("Code Agents"))
            item_idx += 1
            for win_idx, win_name in agents:
                if first_selectable_idx is None:
                    first_selectable_idx = item_idx
                list_view.append(_WindowListItem(win_name, win_idx))
                item_idx += 1

        # --- Other Group ---
        if others:
            list_view.append(_GroupHeader("Other"))
            item_idx += 1
            for win_idx, win_name in others:
                if first_selectable_idx is None:
                    first_selectable_idx = item_idx
                list_view.append(_WindowListItem(win_name, win_idx))
                item_idx += 1

        if first_selectable_idx is not None:
            list_view.index = first_selectable_idx

    def action_dismiss_overlay(self) -> None:
        self.dismiss(None)

    def action_select_tui(self) -> None:
        list_view = self.query_one("#switcher_list", _WrappingListView)
        if list_view.highlighted_child is None:
            return
        item = list_view.highlighted_child
        if isinstance(item, _TuiListItem):
            if item.is_current:
                return
            self._switch_to(item.tui_name, item.running)
        elif isinstance(item, _WindowListItem):
            self._switch_to(item.window_name, True, item.window_index)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, _TuiListItem):
            if item.is_current:
                return
            self._switch_to(item.tui_name, item.running)
        elif isinstance(item, _WindowListItem):
            self._switch_to(item.window_name, True, item.window_index)

    def _shortcut_switch(self, target_name: str) -> None:
        """Switch directly to a specific TUI by name, launching if not running."""
        if target_name == self._current_tui:
            return
        self._switch_to(target_name, target_name in self._running_names)

    def action_shortcut_board(self) -> None:
        self._shortcut_switch("board")

    def action_shortcut_codebrowser(self) -> None:
        self._shortcut_switch("codebrowser")

    def action_shortcut_settings(self) -> None:
        self._shortcut_switch("settings")

    def action_shortcut_brainstorm(self) -> None:
        """Switch to first running brainstorm window, or notify if none running."""
        for name in sorted(self._running_names):
            if name.startswith(_BRAINSTORM_PREFIX):
                if name == self._current_tui:
                    return
                self._switch_to(name, True)
                return
        self.app.notify("No brainstorm session running", severity="warning")

    def action_shortcut_explore(self) -> None:
        """Launch a new explore agent session (always new window)."""
        n = 1
        while f"agent-explore-{n}" in self._running_names:
            n += 1
        window_name = f"agent-explore-{n}"
        try:
            subprocess.Popen(
                ["tmux", "new-window", "-t", f"{self._session}:",
                 "-n", window_name, "ait codeagent invoke explore"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            from agent_launch_utils import maybe_spawn_minimonitor
            maybe_spawn_minimonitor(self._session, window_name)
        except (FileNotFoundError, OSError):
            self.app.notify("Failed to launch explore", severity="error")
            return
        self.dismiss(window_name)

    def _switch_to(self, name: str, running: bool, window_index: str | None = None) -> None:
        try:
            if running:
                target = f"{self._session}:{window_index}" if window_index else f"{self._session}:{name}"
                subprocess.Popen(
                    ["tmux", "select-window", "-t", target],
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
        if name.startswith(_BRAINSTORM_PREFIX):
            task_num = name[len(_BRAINSTORM_PREFIX):]
            return f"ait brainstorm {task_num}"
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
