"""minimonitor_app - Compact TUI for monitoring tmux agent panes.

Designed to run as a narrow side-column (~40 columns) alongside code agent
windows in tmux. Shows all code agents with idle status. Unlike the full
monitor, it has no preview zone — just a compact agent list with status.

Usage:
    python minimonitor_app.py [--session NAME] [--interval SECS]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# Set up import paths before any local imports
_SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_SCRIPT_DIR / "lib"))
sys.path.insert(0, str(_SCRIPT_DIR / "board"))

from monitor.tmux_monitor import (  # noqa: E402
    PaneCategory,
    PaneSnapshot,
    TmuxMonitor,
    load_monitor_config,
)
from monitor.monitor_shared import (  # noqa: E402
    _TASK_ID_RE, TaskInfoCache, TaskDetailDialog,
)
from tui_switcher import TuiSwitcherMixin  # noqa: E402

from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import VerticalScroll  # noqa: E402
from textual.screen import ModalScreen  # noqa: E402
from textual.widgets import Static  # noqa: E402


# -- Widgets ------------------------------------------------------------------

class MiniPaneCard(Static, can_focus=True):
    """Compact status entry for an agent pane."""

    def __init__(self, pane_id: str, text: str, **kwargs) -> None:
        super().__init__(text, **kwargs)
        self.pane_id = pane_id


# -- Main app -----------------------------------------------------------------

class MiniMonitorApp(TuiSwitcherMixin, App):
    """Compact Textual app for monitoring tmux agent panes."""

    TITLE = "Mini Monitor"

    CSS = """
    #mini-session-bar {
        dock: top;
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }

    #mini-pane-list {
        height: 1fr;
    }

    MiniPaneCard {
        height: auto;
        padding: 0 1;
    }

    MiniPaneCard:focus {
        background: $accent;
        color: $text;
    }

    #mini-key-hints {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("j", "tui_switcher", "Jump TUI", show=False),
        Binding("q", "quit", "Quit", show=False),
        Binding("s", "switch_to", "Switch", show=False),
        Binding("i", "show_task_info", "Task Info", show=False),
        Binding("r", "refresh", "Refresh", show=False),
    ]

    def __init__(
        self,
        session: str,
        project_root: Path,
        refresh_seconds: int = 3,
        capture_lines: int = 30,
        idle_threshold: float = 5.0,
        agent_prefixes: list[str] | None = None,
        tui_names: set[str] | None = None,
    ) -> None:
        super().__init__()
        self.current_tui_name = "minimonitor"
        self._session = session
        self._refresh_seconds = refresh_seconds
        self._capture_lines = capture_lines
        self._idle_threshold = idle_threshold
        self._agent_prefixes = agent_prefixes
        self._tui_names = tui_names
        self._snapshots: dict[str, PaneSnapshot] = {}
        self._focused_pane_id: str | None = None
        self._monitor: TmuxMonitor | None = None
        self._task_cache = TaskInfoCache(project_root)
        self._mount_time: float = 0.0
        self._own_window_id: str | None = None
        self._own_window_index: str | None = None

    def compose(self) -> ComposeResult:
        yield Static(id="mini-session-bar")
        yield VerticalScroll(id="mini-pane-list")
        yield Static(
            "j:jump s/\u2191\u2193:switch i:info q:quit r:refresh",
            id="mini-key-hints",
        )

    def on_mount(self) -> None:
        self._mount_time = time.monotonic()

        if not os.environ.get("TMUX"):
            self.query_one("#mini-session-bar", Static).update(
                "[bold red]Not inside tmux[/]"
            )
            return

        # Detect own window ID and index for auto-close and auto-selection
        own_pane = os.environ.get("TMUX_PANE", "")
        try:
            result = subprocess.run(
                ["tmux", "display-message", "-p", "-t", own_pane,
                 "#{window_id}\t#{window_index}"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split("\t")
                if len(parts) >= 1:
                    self._own_window_id = parts[0]
                if len(parts) >= 2:
                    self._own_window_index = parts[1]
        except Exception:
            pass

        # CRITICAL: Do NOT rename the tmux window — minimonitor runs inside
        # an agent's window, renaming would break agent classification.

        self._start_monitoring()

    def _start_monitoring(self) -> None:
        """Initialize the TmuxMonitor and start refreshing."""
        kwargs: dict = {}
        if self._agent_prefixes is not None:
            kwargs["agent_prefixes"] = self._agent_prefixes
        if self._tui_names is not None:
            kwargs["tui_names"] = self._tui_names

        self._monitor = TmuxMonitor(
            session=self._session,
            capture_lines=self._capture_lines,
            idle_threshold=self._idle_threshold,
            **kwargs,
        )
        self.call_later(self._refresh_data)
        self.set_interval(self._refresh_seconds, self._refresh_data)

    # -- Data refresh ----------------------------------------------------------

    async def _refresh_data(self) -> None:
        if self._monitor is None:
            return

        # Save focus state before rebuild
        saved_pane_id = self._focused_pane_id

        self._snapshots = self._monitor.capture_all()

        # Auto-close check (with 5-second grace period after mount)
        if self._own_window_id and (time.monotonic() - self._mount_time) > 5.0:
            self._check_auto_close()

        self._rebuild_session_bar()
        self._rebuild_pane_list()

        # Defer focus restoration until after Textual processes DOM changes
        self.call_after_refresh(self._restore_focus, saved_pane_id)

    def _check_auto_close(self) -> None:
        """Exit if no other panes remain in our window (besides ourselves)."""
        if self._monitor is None or self._own_window_id is None:
            return
        panes = self._monitor.discover_window_panes(self._own_window_id)
        own_pane = os.environ.get("TMUX_PANE")
        other_panes = [p for p in panes if p.pane_id != own_pane]
        if not other_panes:
            self.exit()

    def _restore_focus(self, pane_id: str | None) -> None:
        """Re-focus the previously focused card after a rebuild."""
        if pane_id is not None:
            for card in self.query("#mini-pane-list MiniPaneCard"):
                if hasattr(card, "pane_id") and card.pane_id == pane_id:
                    card.focus()
                    return
        # Fallback: auto-select the card matching this window's agent
        self._auto_select_own_window()

    def _auto_select_own_window(self) -> None:
        """Focus the card whose agent shares this minimonitor's window."""
        if not self._own_window_index:
            return
        for card in self.query("#mini-pane-list MiniPaneCard"):
            snap = self._snapshots.get(card.pane_id)
            if snap and snap.pane.window_index == self._own_window_index:
                card.focus()
                return

    def on_app_focus(self) -> None:
        """Auto-select own window's agent when this pane regains terminal focus."""
        self._auto_select_own_window()

    def _rebuild_session_bar(self) -> None:
        agents = [
            s for s in self._snapshots.values()
            if s.pane.category == PaneCategory.AGENT
        ]
        total = len(agents)
        idle_count = sum(1 for a in agents if a.is_idle)

        idle_str = f" [yellow]{idle_count} idle[/]" if idle_count > 0 else ""
        bar = self.query_one("#mini-session-bar", Static)
        bar.update(
            f"{self._session}  {total} agent{'s' if total != 1 else ''}{idle_str}"
        )

    def _rebuild_pane_list(self) -> None:
        container = self.query_one("#mini-pane-list", VerticalScroll)
        # Clear existing content
        for widget in list(container.children):
            widget.remove()

        # Only show AGENT panes, sorted by window_index
        agents = [
            s for s in self._snapshots.values()
            if s.pane.category == PaneCategory.AGENT
        ]
        agents.sort(key=lambda s: (s.pane.window_index, s.pane.pane_index))

        for snap in agents:
            if snap.is_idle:
                idle_s = int(snap.idle_seconds)
                dot = "[yellow]\u25cf[/]"
                status = f"[yellow]IDLE {idle_s}s[/]"
            else:
                dot = "[green]\u25cf[/]"
                status = "[green]ok[/]"

            # Build compact card text
            name = snap.pane.window_name
            # Truncate long window names for narrow display
            max_name = 22
            if len(name) > max_name:
                name = name[:max_name - 1] + "\u2026"

            line1 = f"{dot} {name}  {status}"

            # Optional task title line
            task_id = self._task_cache.get_task_id(snap.pane.window_name)
            if task_id:
                info = self._task_cache.get_task_info(task_id)
                if info:
                    title = info.title
                    if len(title) > 30:
                        title = title[:29] + "\u2026"
                    line1 += f"\n  [dim]{title}[/]"

            container.mount(MiniPaneCard(snap.pane.pane_id, line1))

    # -- Key handling ----------------------------------------------------------

    def on_key(self, event) -> None:
        key = event.key

        # Let modal screens handle their own keys
        if isinstance(self.screen, ModalScreen):
            return

        # Up/Down navigate within pane list
        if key == "up":
            self._nav(-1)
            event.stop()
            event.prevent_default()
        elif key == "down":
            self._nav(1)
            event.stop()
            event.prevent_default()

    def _nav(self, direction: int) -> None:
        """Move focus up/down within the pane list."""
        cards = list(self.query("#mini-pane-list MiniPaneCard"))
        if not cards:
            return
        focused = self.focused
        try:
            idx = cards.index(focused)
        except ValueError:
            cards[0].focus()
            return
        new_idx = max(0, min(len(cards) - 1, idx + direction))
        cards[new_idx].focus()

    # -- Focus tracking --------------------------------------------------------

    def on_descendant_focus(self, event) -> None:
        widget = event.widget
        if isinstance(widget, MiniPaneCard):
            self._focused_pane_id = widget.pane_id

    def _get_focused_pane_id(self) -> str | None:
        """Get pane_id from the currently focused widget."""
        focused = self.focused
        if isinstance(focused, MiniPaneCard):
            return focused.pane_id
        return None

    # -- Actions ---------------------------------------------------------------

    def action_switch_to(self) -> None:
        """Switch tmux focus to the focused pane's window (prefer minimonitor pane)."""
        if self._monitor is None:
            return
        pane_id = self._get_focused_pane_id()
        if pane_id is None:
            self.notify("Focus a pane first", severity="warning")
            return
        if self._monitor.switch_to_pane(pane_id, prefer_companion=True):
            snap = self._snapshots.get(pane_id)
            name = f"{snap.pane.window_name}" if snap else pane_id
            self.notify(f"Switched to {name}")
        else:
            self.notify("Failed to switch", severity="error")

    def action_refresh(self) -> None:
        """Force an immediate data refresh."""
        self.call_later(self._refresh_data)
        self.notify("Refreshed")

    def action_show_task_info(self) -> None:
        """Show task detail dialog for the focused agent pane."""
        pane_id = self._get_focused_pane_id()
        if not pane_id:
            self.notify("Focus an agent pane first", severity="warning")
            return
        snap = self._snapshots.get(pane_id)
        if not snap:
            return
        task_id = self._task_cache.get_task_id(snap.pane.window_name)
        if not task_id:
            self.notify("No task ID in window name", severity="warning")
            return
        # Force refresh cache to get latest content
        self._task_cache.invalidate(task_id)
        info = self._task_cache.get_task_info(task_id)
        if not info:
            self.notify(f"Task t{task_id} not found", severity="error")
            return
        self.push_screen(TaskDetailDialog(info))


def _detect_tmux_session() -> str | None:
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
    except Exception:
        pass
    return None


def _load_project_tmux_config(project_root: Path) -> dict:
    """Load tmux section from project_config.yaml."""
    try:
        import yaml
        pc = project_root / "aitasks" / "metadata" / "project_config.yaml"
        if pc.is_file():
            with open(pc) as f:
                data = yaml.safe_load(f) or {}
            return data.get("tmux", {})
    except Exception:
        pass
    return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compact tmux agent monitor TUI")
    parser.add_argument("--session", "-s", default=None, help="tmux session name")
    parser.add_argument("--interval", "-i", type=int, default=None, help="refresh interval in seconds")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    config = load_monitor_config(project_root)
    tmux_config = _load_project_tmux_config(project_root)

    # Resolve session: CLI > current tmux session > config > default
    configured_session = tmux_config.get("default_session", "aitasks")
    if args.session:
        session = args.session
    else:
        session = _detect_tmux_session()
        if session is None:
            session = configured_session

    refresh_seconds = args.interval if args.interval is not None else tmux_config.get("monitor", {}).get("refresh_seconds", 3)

    app = MiniMonitorApp(
        session=session,
        project_root=project_root,
        refresh_seconds=refresh_seconds,
        capture_lines=config.get("capture_lines", 30),
        idle_threshold=config.get("idle_threshold", 5.0),
        agent_prefixes=config.get("agent_prefixes"),
        tui_names=config.get("tui_names"),
    )
    app.run()


if __name__ == "__main__":
    main()
