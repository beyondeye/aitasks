"""monitor_app - TUI for monitoring tmux panes running code agents.

Shows all tmux panes categorized as agents, TUIs, or other. Maintains an
attention queue for idle agent panes (likely awaiting user input) and allows
confirming (sending Enter), deferring, or switching to those panes.

Usage:
    python monitor_app.py [--session NAME] [--interval SECS] [--lines N]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Set up import paths before any local imports
_SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_SCRIPT_DIR / "lib"))

from monitor.tmux_monitor import (  # noqa: E402
    PaneCategory,
    PaneSnapshot,
    TmuxMonitor,
    load_monitor_config,
)
from tui_switcher import TuiSwitcherMixin  # noqa: E402

import subprocess  # noqa: E402

from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Container, VerticalScroll  # noqa: E402
from textual.screen import ModalScreen  # noqa: E402
from textual.widgets import Button, Footer, Header, Label, Static  # noqa: E402


class SessionBar(Static):
    """One-line bar showing session name, pane count, idle count."""
    pass


class AttentionCard(Static, can_focus=True):
    """Card for an idle agent pane in the attention queue."""

    def __init__(self, pane_id: str, text: str, **kwargs) -> None:
        super().__init__(text, **kwargs)
        self.pane_id = pane_id


class PaneCard(Static, can_focus=True):
    """Status entry for a pane in the agents/other section."""

    def __init__(self, pane_id: str, text: str, **kwargs) -> None:
        super().__init__(text, **kwargs)
        self.pane_id = pane_id


class SessionRenameDialog(ModalScreen):
    """Dialog offering to rename the current tmux session."""

    DEFAULT_CSS = """
    SessionRenameDialog {
        align: center middle;
    }
    #rename-dialog {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $warning;
        padding: 1 2;
    }
    #rename-message {
        margin: 0 0 1 0;
    }
    #rename-buttons {
        width: 100%;
        height: auto;
        layout: horizontal;
    }
    #rename-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_dialog", "Close", show=False),
    ]

    def __init__(self, current: str, expected: str) -> None:
        super().__init__()
        self._current = current
        self._expected = expected

    def compose(self) -> ComposeResult:
        with Container(id="rename-dialog"):
            yield Label(
                f"[bold yellow]Session name mismatch[/]\n\n"
                f"Current session: [bold]{self._current}[/]\n"
                f"Expected session: [bold]{self._expected}[/]\n\n"
                f"Rename session to [bold]{self._expected}[/]?",
                id="rename-message",
            )
            with Container(id="rename-buttons"):
                yield Button("Rename", variant="warning", id="btn-rename")
                yield Button("Continue anyway", variant="default", id="btn-continue")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-rename":
            try:
                subprocess.run(
                    ["tmux", "rename-session", self._expected],
                    capture_output=True, timeout=5,
                )
                self.dismiss(True)
            except Exception:
                self.app.notify("Failed to rename session", severity="error")
                self.dismiss(False)
        else:
            self.dismiss(False)

    def action_dismiss_dialog(self) -> None:
        self.dismiss(False)


class MonitorApp(TuiSwitcherMixin, App):
    """Textual app for monitoring tmux panes running code agents."""

    TITLE = "tmux Monitor"

    CSS = """
    #session-bar {
        dock: top;
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }

    #attention-section {
        height: auto;
        max-height: 12;
        border-bottom: solid $primary-darken-2;
    }

    #attention-header {
        padding: 0 1;
        text-style: bold;
        color: $warning;
    }

    AttentionCard {
        height: auto;
        padding: 0 1;
        margin: 0 0;
    }

    AttentionCard:focus {
        background: $accent;
        color: $text;
    }

    #no-attention {
        padding: 0 1;
        color: $text-muted;
    }

    #pane-list {
        height: 1fr;
    }

    .section-header {
        padding: 0 1;
        text-style: bold;
        color: $text-muted;
    }

    PaneCard {
        height: auto;
        padding: 0 1;
    }

    PaneCard:focus {
        background: $accent;
        color: $text;
    }

    #content-section {
        height: auto;
        max-height: 12;
        min-height: 3;
        border-top: solid $primary-darken-2;
    }

    #content-header {
        padding: 0 1;
        text-style: bold;
        color: $text-muted;
    }

    #content-preview {
        padding: 0 1;
        height: auto;
        max-height: 10;
    }
    """

    BINDINGS = [
        Binding("j", "tui_switcher", "Jump TUI"),
        Binding("q", "quit", "Quit"),
        Binding("enter", "confirm", "Confirm"),
        Binding("c", "confirm", "Confirm", show=False),
        Binding("d", "decide_later", "Later"),
        Binding("s", "switch_to", "Switch"),
        Binding("r", "refresh", "Refresh"),
        Binding("f5", "refresh", "Refresh", show=False),
    ]

    def __init__(
        self,
        session: str,
        refresh_seconds: int = 3,
        capture_lines: int = 30,
        idle_threshold: float = 5.0,
        agent_prefixes: list[str] | None = None,
        tui_names: set[str] | None = None,
        expected_session: str | None = None,
    ) -> None:
        super().__init__()
        self.current_tui_name = "monitor"
        self._session = session
        self._expected_session = expected_session
        self._refresh_seconds = refresh_seconds
        self._capture_lines = capture_lines
        self._idle_threshold = idle_threshold
        self._agent_prefixes = agent_prefixes
        self._tui_names = tui_names
        self.attention_queue: list[str] = []
        self._snapshots: dict[str, PaneSnapshot] = {}
        self._focused_pane_id: str | None = None
        self._monitor: TmuxMonitor | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield SessionBar(id="session-bar")
        yield VerticalScroll(
            Static("[bold yellow]NEEDS ATTENTION[/]", id="attention-header"),
            Static("[dim]No idle agents[/]", id="no-attention"),
            id="attention-section",
        )
        yield VerticalScroll(id="pane-list")
        yield VerticalScroll(
            Static("[bold]Content Preview[/]", id="content-header"),
            Static("", id="content-preview"),
            id="content-section",
        )
        yield Footer()

    def on_mount(self) -> None:
        if not os.environ.get("TMUX"):
            self.sub_title = "Not running inside tmux"
            self.query_one("#session-bar", SessionBar).update(
                "[bold red]Warning:[/] Not inside tmux — monitoring requires an active tmux session"
            )
            return

        # Rename the tmux window so the TUI switcher can find us
        try:
            subprocess.run(
                ["tmux", "rename-window", "monitor"],
                capture_output=True, timeout=5,
            )
        except Exception:
            pass

        # Check if session name matches expected config
        if self._expected_session and self._session != self._expected_session:
            # Check if a session with the expected name already exists
            try:
                result = subprocess.run(
                    ["tmux", "has-session", "-t", self._expected_session],
                    capture_output=True, timeout=5,
                )
                if result.returncode == 0:
                    # Expected session exists elsewhere — just warn
                    self.notify(
                        f"Session '{self._session}' differs from configured "
                        f"'{self._expected_session}' (which already exists)",
                        severity="warning",
                        timeout=8,
                    )
                else:
                    # Offer to rename
                    self.push_screen(
                        SessionRenameDialog(self._session, self._expected_session),
                        callback=self._on_session_rename,
                    )
                    return  # _start_monitoring called from callback
            except Exception:
                pass

        self._start_monitoring()

    def _on_session_rename(self, renamed: bool | None) -> None:
        """Callback after session rename dialog."""
        if renamed:
            self._session = self._expected_session  # type: ignore[assignment]
            self.notify(f"Session renamed to '{self._session}'")
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

    async def _refresh_data(self) -> None:
        if self._monitor is None:
            return

        self._snapshots = self._monitor.capture_all()
        self._update_attention_queue()
        self._rebuild_session_bar()
        self._rebuild_attention_section()
        self._rebuild_pane_list()
        self._update_content_preview()

    def _update_attention_queue(self) -> None:
        idle_pane_ids = {
            pid for pid, snap in self._snapshots.items()
            if snap.is_idle and snap.pane.category == PaneCategory.AGENT
        }

        # Remove panes that are no longer idle
        self.attention_queue = [pid for pid in self.attention_queue if pid in idle_pane_ids]

        # Add new idle panes at the end
        for pid in idle_pane_ids:
            if pid not in self.attention_queue:
                self.attention_queue.append(pid)

    def _rebuild_session_bar(self) -> None:
        total = len(self._snapshots)
        idle = len(self.attention_queue)
        bar = self.query_one("#session-bar", SessionBar)
        bar.update(
            f"tmux Monitor — session: {self._session} "
            f"({total} pane{'s' if total != 1 else ''}, {idle} idle)"
        )

    def _rebuild_attention_section(self) -> None:
        container = self.query_one("#attention-section", VerticalScroll)
        # Remove old cards
        for card in list(container.query(AttentionCard)):
            card.remove()

        no_attn = container.query_one("#no-attention", Static)

        if not self.attention_queue:
            no_attn.display = True
            return

        no_attn.display = False
        for pid in self.attention_queue:
            snap = self._snapshots.get(pid)
            if snap is None:
                continue
            # Get last non-empty line of content
            lines = [l for l in snap.content.rstrip().splitlines() if l.strip()]
            last_line = lines[-1].strip() if lines else "(empty)"
            if len(last_line) > 70:
                last_line = last_line[:67] + "..."

            idle_s = int(snap.idle_seconds)
            text = (
                f"[bold yellow]![/] "
                f"{snap.pane.window_index}:{snap.pane.window_name} "
                f"(pane {snap.pane.pane_index}) — "
                f"[yellow]idle {idle_s}s[/]  "
                f"[dim]{last_line}[/]"
            )
            container.mount(AttentionCard(pid, text))

    def _rebuild_pane_list(self) -> None:
        container = self.query_one("#pane-list", VerticalScroll)
        # Clear existing content
        for widget in list(container.children):
            widget.remove()

        agents: list[PaneSnapshot] = []
        others: list[PaneSnapshot] = []
        for snap in self._snapshots.values():
            if snap.pane.category == PaneCategory.AGENT:
                agents.append(snap)
            elif snap.pane.category == PaneCategory.OTHER:
                others.append(snap)

        # Sort by window_index
        agents.sort(key=lambda s: (s.pane.window_index, s.pane.pane_index))
        others.sort(key=lambda s: (s.pane.window_index, s.pane.pane_index))

        if agents:
            container.mount(Static(f"[bold]CODE AGENTS ({len(agents)})[/]", classes="section-header"))
            for snap in agents:
                if snap.is_idle:
                    idle_s = int(snap.idle_seconds)
                    dot = "[yellow]\u25cf[/]"
                    status = f"[yellow]IDLE {idle_s}s[/]"
                else:
                    dot = "[green]\u25cf[/]"
                    status = "[green]Active[/]"
                text = (
                    f" {dot} {snap.pane.window_index}:{snap.pane.window_name} "
                    f"({snap.pane.pane_index})  {status}"
                )
                container.mount(PaneCard(snap.pane.pane_id, text))

        if others:
            container.mount(Static(f"[bold]OTHER ({len(others)})[/]", classes="section-header"))
            for snap in others:
                text = (
                    f" [dim]\u25cb[/] {snap.pane.window_index}:{snap.pane.window_name} "
                    f"({snap.pane.pane_index})  [dim]{snap.pane.current_command}[/]"
                )
                container.mount(PaneCard(snap.pane.pane_id, text))

    def _update_content_preview(self) -> None:
        preview = self.query_one("#content-preview", Static)
        header = self.query_one("#content-header", Static)

        if self._focused_pane_id and self._focused_pane_id in self._snapshots:
            snap = self._snapshots[self._focused_pane_id]
            header.update(
                f"[bold]Content Preview[/] "
                f"({snap.pane.window_index}:{snap.pane.window_name})"
            )
            # Show last N lines, strip trailing whitespace
            lines = snap.content.rstrip().splitlines()
            display_lines = lines[-15:] if len(lines) > 15 else lines
            preview.update("\n".join(display_lines) if display_lines else "[dim](empty)[/]")
        else:
            header.update("[bold]Content Preview[/]")
            preview.update("[dim]Focus an agent or pane to see its output[/]")

    def on_descendant_focus(self, event) -> None:
        widget = event.widget
        if isinstance(widget, AttentionCard):
            self._focused_pane_id = widget.pane_id
            self._update_content_preview()
        elif isinstance(widget, PaneCard):
            self._focused_pane_id = widget.pane_id
            self._update_content_preview()

    def _get_focused_pane_id(self) -> str | None:
        """Get pane_id from the currently focused widget."""
        focused = self.focused
        if isinstance(focused, AttentionCard):
            return focused.pane_id
        elif isinstance(focused, PaneCard):
            return focused.pane_id
        return None

    def action_confirm(self) -> None:
        """Send Enter to the focused idle agent pane."""
        if self._monitor is None:
            return
        pane_id = self._get_focused_pane_id()
        if pane_id is None:
            self.notify("Focus an agent pane first", severity="warning")
            return
        if pane_id not in self.attention_queue:
            self.notify("Pane is not in the attention queue", severity="warning")
            return
        if self._monitor.send_enter(pane_id):
            self.attention_queue = [p for p in self.attention_queue if p != pane_id]
            snap = self._snapshots.get(pane_id)
            name = f"{snap.pane.window_name}" if snap else pane_id
            self.notify(f"Sent Enter to {name}")
            self.call_later(self._refresh_data)
        else:
            self.notify("Failed to send Enter", severity="error")

    def action_decide_later(self) -> None:
        """Move the focused pane to the end of the attention queue."""
        pane_id = self._get_focused_pane_id()
        if pane_id is None or pane_id not in self.attention_queue:
            self.notify("Focus an attention card first", severity="warning")
            return
        self.attention_queue = [p for p in self.attention_queue if p != pane_id]
        self.attention_queue.append(pane_id)
        self._rebuild_attention_section()
        snap = self._snapshots.get(pane_id)
        name = f"{snap.pane.window_name}" if snap else pane_id
        self.notify(f"Moved {name} to end of queue")

    def action_switch_to(self) -> None:
        """Switch tmux focus to the focused pane."""
        if self._monitor is None:
            return
        pane_id = self._get_focused_pane_id()
        if pane_id is None:
            self.notify("Focus a pane first", severity="warning")
            return
        if self._monitor.switch_to_pane(pane_id):
            snap = self._snapshots.get(pane_id)
            name = f"{snap.pane.window_name}" if snap else pane_id
            self.notify(f"Switched to {name}")
        else:
            self.notify("Failed to switch", severity="error")

    def action_refresh(self) -> None:
        """Force an immediate data refresh."""
        self.call_later(self._refresh_data)
        self.notify("Refreshed")


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
    parser = argparse.ArgumentParser(description="tmux pane monitor TUI")
    parser.add_argument("--session", "-s", default=None, help="tmux session name")
    parser.add_argument("--interval", "-i", type=int, default=None, help="refresh interval in seconds")
    parser.add_argument("--lines", "-n", type=int, default=None, help="lines to capture per pane")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    config = load_monitor_config(project_root)
    tmux_config = _load_project_tmux_config(project_root)

    # The configured session name (used for mismatch check)
    configured_session = tmux_config.get("default_session", "aitasks")

    # Resolve session: CLI > current tmux session > config > default
    if args.session:
        session = args.session
        expected_session = None  # explicit CLI choice, no mismatch check
    else:
        session = _detect_tmux_session()
        if session is not None:
            # Auto-detected; check against config
            expected_session = configured_session if session != configured_session else None
        else:
            session = configured_session
            expected_session = None

    refresh_seconds = args.interval if args.interval is not None else tmux_config.get("monitor", {}).get("refresh_seconds", 3)
    capture_lines = args.lines if args.lines is not None else config.get("capture_lines", 30)

    app = MonitorApp(
        session=session,
        refresh_seconds=refresh_seconds,
        capture_lines=capture_lines,
        idle_threshold=config.get("idle_threshold", 5.0),
        agent_prefixes=config.get("agent_prefixes"),
        tui_names=config.get("tui_names"),
        expected_session=expected_session,
    )
    app.run()


if __name__ == "__main__":
    main()
