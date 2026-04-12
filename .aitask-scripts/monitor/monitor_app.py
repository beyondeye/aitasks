"""monitor_app - TUI for monitoring tmux panes running code agents.

Shows all tmux panes categorized as agents, TUIs, or other. Uses a zone-based
navigation model: Tab cycles between 2 panels (session list, preview), Up/Down
navigates within the session list panel, and the preview panel forwards all
keystrokes directly to the tmux session being previewed.

Usage:
    python monitor_app.py [--session NAME] [--interval SECS] [--lines N]
"""
from __future__ import annotations

import argparse
import os
import sys
from enum import Enum
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
    _ansi_to_rich_text, _TASK_ID_RE, TaskInfo, TaskInfoCache,
    TaskDetailDialog, KillConfirmDialog,
)
from tui_switcher import TuiSwitcherMixin  # noqa: E402

import subprocess  # noqa: E402
from agent_launch_utils import resolve_dry_run_command, TmuxLaunchConfig, launch_in_tmux, maybe_spawn_minimonitor  # noqa: E402

from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Container, ScrollableContainer, VerticalScroll  # noqa: E402
from textual.screen import ModalScreen  # noqa: E402
from textual.timer import Timer  # noqa: E402
from textual.widgets import Button, Footer, Header, Label, Static  # noqa: E402



# -- Zone model ---------------------------------------------------------------

class Zone(Enum):
    PANE_LIST = "pane_list"
    PREVIEW = "preview"


ZONE_ORDER = [Zone.PANE_LIST, Zone.PREVIEW]

# Preview panel size presets: (section_max_height, preview_max_height, label)
PREVIEW_SIZES = [
    (12, 10, "S"),
    (24, 22, "M"),
    (40, 38, "L"),
]
PREVIEW_DEFAULT_SIZE = 1  # Medium

# Textual key name → tmux send-keys argument (for special keys)
_TEXTUAL_TO_TMUX = {
    "enter": "Enter",
    "escape": "Escape",
    "backspace": "BSpace",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "space": "Space",
    "delete": "DC",
    "home": "Home",
    "end": "End",
    "pageup": "PPage",
    "pagedown": "NPage",
    "insert": "IC",
    "f1": "F1",
    "f2": "F2",
    "f3": "F3",
    "f4": "F4",
    "f5": "F5",
    "f6": "F6",
    "f7": "F7",
    "f8": "F8",
    "f9": "F9",
    "f10": "F10",
    "f11": "F11",
    "f12": "F12",
}


# -- Widgets ------------------------------------------------------------------

class SessionBar(Static):
    """One-line bar showing session name, pane count, idle count."""
    pass


class PaneCard(Static, can_focus=True):
    """Status entry for a pane in the agents/other section."""

    def __init__(self, pane_id: str, text: str, **kwargs) -> None:
        super().__init__(text, **kwargs)
        self.pane_id = pane_id


class PreviewPanel(Static, can_focus=True):
    """Focusable content preview panel — forwards keystrokes to tmux when active."""
    pass


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


class NextSiblingDialog(ModalScreen):
    """Dialog for picking next sibling task."""

    BINDINGS = [Binding("escape", "dismiss_dialog", "Close", show=False)]

    DEFAULT_CSS = """
    NextSiblingDialog { align: center middle; }
    #next-sib-dialog { width: 70%; height: auto; background: $surface; border: thick $warning; padding: 1 2; }
    #next-sib-header { text-style: bold; color: $warning; margin: 0 0 1 0; }
    #next-sib-details { margin: 0 0 1 0; }
    #next-sib-buttons { width: 100%; height: auto; layout: horizontal; }
    #next-sib-buttons Button { margin: 0 1; }
    """

    def __init__(
        self,
        current_task_id: str,
        current_title: str,
        current_status: str,
        suggested_id: str,
        suggested_title: str,
        parent_id: str,
    ) -> None:
        super().__init__()
        self._current_task_id = current_task_id
        self._current_title = current_title
        self._current_status = current_status
        self._suggested_id = suggested_id
        self._suggested_title = suggested_title
        self._parent_id = parent_id

    def compose(self) -> ComposeResult:
        is_parent_with_children = "_" not in self._current_task_id
        will_kill = self._current_status == "Done" or is_parent_with_children
        with Container(id="next-sib-dialog"):
            yield Static("[bold yellow]Pick Next Sibling[/]", id="next-sib-header")
            lines = [
                f"Current:   [bold]t{self._current_task_id}[/]: {self._current_title}  (Status: {self._current_status})",
                f"Suggested: [bold]t{self._suggested_id}[/]: {self._suggested_title}",
            ]
            if will_kill:
                if is_parent_with_children:
                    lines.append("\n[yellow]Parent agent pane will be killed (parent is split into children)[/]")
                else:
                    lines.append("\n[yellow]Current agent pane will be killed (task is Done)[/]")
            yield Static("\n".join(lines), id="next-sib-details")
            with Container(id="next-sib-buttons"):
                yield Button(f"Pick t{self._suggested_id}", variant="warning", id="btn-pick-suggested")
                yield Button("Choose child", variant="primary", id="btn-choose-child")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-pick-suggested":
            self.dismiss(("pick", self._suggested_id))
        elif event.button.id == "btn-choose-child":
            self.dismiss(("choose", self._parent_id))
        else:
            self.dismiss(None)

    def action_dismiss_dialog(self) -> None:
        self.dismiss(None)


# -- Main app -----------------------------------------------------------------

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

    #pane-list {
        height: 1fr;
        border: solid $primary-darken-2;
    }

    #pane-list.zone-active {
        border: solid $accent;
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
        max-height: 24;
        min-height: 3;
        border-bottom: solid $primary-darken-2;
    }

    #content-section.zone-active {
        border-bottom: solid $warning;
    }

    #content-header {
        dock: bottom;
        padding: 0 1;
        text-style: bold;
        color: $text-muted;
    }

    #preview-scroll {
        height: 1fr;
        max-height: 22;
    }

    PreviewPanel {
        height: auto;
        max-height: 22;
        background: #1a1a1a;
        color: #d4d4d4;
    }

    PreviewPanel:focus {
        background: #1a1a1a;
    }
    """

    BINDINGS = [
        Binding("tab", "switch_zone", "← Back (Tab)", show=True),
        Binding("j", "tui_switcher", "Jump TUI"),
        Binding("q", "quit", "Quit"),
        Binding("s", "switch_to", "Switch"),
        Binding("i", "show_task_info", "Task Info"),
        Binding("r", "refresh", "Refresh"),
        Binding("f5", "refresh", "Refresh", show=False),
        Binding("z", "cycle_preview_size", "Zoom"),
        Binding("k", "kill_pane", "Kill"),
        Binding("n", "pick_next_sibling", "Next Sibling"),
        Binding("enter", "send_enter", "Send ↵", show=True),
        Binding("a", "toggle_auto_switch", "Auto"),
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
        self._project_root = project_root
        self._snapshots: dict[str, PaneSnapshot] = {}
        self._focused_pane_id: str | None = None
        self._monitor: TmuxMonitor | None = None
        self._active_zone: Zone = Zone.PANE_LIST
        self._preview_timer: Timer | None = None
        self._delayed_refresh_timer: Timer | None = None
        self._preview_size_idx: int = PREVIEW_DEFAULT_SIZE
        self._task_cache = TaskInfoCache(project_root)
        self._auto_switch: bool = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield SessionBar(id="session-bar")
        yield VerticalScroll(id="pane-list")
        yield Container(
            ScrollableContainer(
                PreviewPanel("", id="content-preview"),
                id="preview-scroll",
            ),
            Static("[bold]Content Preview[/]", id="content-header"),
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

    # -- Data refresh ----------------------------------------------------------

    async def _refresh_data(self) -> None:
        if self._monitor is None:
            return

        # Save focus state before rebuild
        saved_pane_id = self._focused_pane_id
        saved_zone = self._active_zone

        self._snapshots = self._monitor.capture_all()

        # Auto-switch: if enabled and in pane list, move to most-idle agent
        if self._auto_switch and saved_zone == Zone.PANE_LIST:
            if self._maybe_auto_switch():
                saved_pane_id = self._focused_pane_id

        self._rebuild_session_bar()
        self._rebuild_pane_list()
        self._update_content_preview()

        # Defer focus restoration until after Textual processes the DOM changes
        # from remove()/mount(). Immediate restore fails because removed widgets
        # haven't been fully detached yet.
        self.call_after_refresh(self._restore_focus, saved_pane_id, saved_zone)

    async def _fast_preview_refresh(self) -> None:
        """Lightweight refresh — only re-capture the focused pane for preview."""
        if self._monitor is None or self._focused_pane_id is None:
            return
        snap = self._monitor.capture_pane(self._focused_pane_id)
        if snap is not None:
            self._snapshots[self._focused_pane_id] = snap
            self._update_content_preview()

    def _schedule_delayed_refresh(self, delay: float = 0.3) -> None:
        """Schedule a one-shot preview refresh after *delay* seconds.

        Cancels any pending delayed refresh to avoid stacking.
        """
        if self._delayed_refresh_timer is not None:
            self._delayed_refresh_timer.stop()
        self._delayed_refresh_timer = self.set_timer(
            delay, self._fire_delayed_refresh
        )

    async def _fire_delayed_refresh(self) -> None:
        """Fire the delayed refresh and clear the timer reference."""
        self._delayed_refresh_timer = None
        await self._fast_preview_refresh()

    def _maybe_auto_switch(self) -> bool:
        """Switch focus to the most-idle agent if the current agent is active.

        Returns True if focus was switched, False otherwise.
        """
        if self._focused_pane_id is None:
            return False
        current_snap = self._snapshots.get(self._focused_pane_id)
        if current_snap is None or current_snap.pane.category != PaneCategory.AGENT:
            return False
        # If focused agent is idle, keep it — it needs attention
        if current_snap.is_idle:
            return False
        # Find idle agents, sorted by most idle first
        idle_agents = [
            snap for snap in self._snapshots.values()
            if snap.pane.category == PaneCategory.AGENT and snap.is_idle
        ]
        if not idle_agents:
            return False
        idle_agents.sort(key=lambda s: s.idle_seconds, reverse=True)
        self._focused_pane_id = idle_agents[0].pane.pane_id
        return True

    def _restore_focus(self, pane_id: str | None, zone: Zone) -> None:
        """Re-focus the previously focused widget after a rebuild."""
        if zone == Zone.PREVIEW:
            try:
                self.query_one("#content-preview", PreviewPanel).focus()
            except Exception:
                pass
            return
        if pane_id is None:
            return
        for card in self.query("#pane-list PaneCard"):
            if hasattr(card, "pane_id") and card.pane_id == pane_id:
                card.focus()
                return

    def _rebuild_session_bar(self) -> None:
        total = len(self._snapshots)
        bar = self.query_one("#session-bar", SessionBar)
        auto_tag = "  [bold yellow][AUTO][/]" if self._auto_switch else ""
        bar.update(
            f"tmux Monitor — session: {self._session} "
            f"({total} pane{'s' if total != 1 else ''})"
            f"{auto_tag}"
            f"  [dim]Tab: switch panel[/]"
        )

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
            auto_label = "  [bold yellow]⟳ AUTO[/]" if self._auto_switch else ""
            container.mount(Static(f"[bold]CODE AGENTS ({len(agents)})[/]{auto_label}", classes="section-header"))
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
                task_id = self._task_cache.get_task_id(snap.pane.window_name)
                if task_id:
                    info = self._task_cache.get_task_info(task_id)
                    if info:
                        text += f"\n     [dim italic]t{task_id}: {info.title}[/]"
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
        try:
            preview = self.query_one("#content-preview", PreviewPanel)
            header = self.query_one("#content-header", Static)
        except Exception:
            return

        if self._focused_pane_id and self._focused_pane_id in self._snapshots:
            snap = self._snapshots[self._focused_pane_id]
            pane_label = f"({snap.pane.window_index}:{snap.pane.window_name})"
            task_id = self._task_cache.get_task_id(snap.pane.window_name)
            if task_id:
                info = self._task_cache.get_task_info(task_id)
                if info:
                    if self._active_zone == Zone.PREVIEW:
                        pane_label += f" [bold]t{task_id}: {info.title}[/]"
                    else:
                        pane_label += f" [dim italic]t{task_id}: {info.title}[/]"
            if self._active_zone == Zone.PREVIEW:
                header.update(
                    f"[bold white]Content Preview[/] {pane_label} [bold green]LIVE[/]"
                )
            else:
                header.update(f"[bold]Content Preview[/] {pane_label}")
            # Show last N lines, strip trailing whitespace
            lines = snap.content.rstrip().splitlines()
            # Show lines proportional to the current preview size
            _, max_h, _ = PREVIEW_SIZES[self._preview_size_idx]
            show_n = max_h - 1  # leave 1 line for footer
            display_lines = lines[-show_n:] if len(lines) > show_n else lines
            if display_lines:
                content = _ansi_to_rich_text("\n".join(display_lines))
                preview.styles.min_width = snap.pane.width
                preview.update(content)
            else:
                preview.styles.min_width = 0
                preview.update("[dim](empty)[/]")
        else:
            header.update("[bold]Content Preview[/]")
            preview.styles.min_width = 0
            preview.update("[dim]Focus an agent or pane to see its output[/]")

    # -- Zone navigation -------------------------------------------------------

    def _switch_zone(self, direction: int = 1) -> None:
        """Cycle active zone forward or backward."""
        idx = ZONE_ORDER.index(self._active_zone)
        new_idx = (idx + direction) % len(ZONE_ORDER)
        self._active_zone = ZONE_ORDER[new_idx]
        self._focus_first_in_zone()
        self._manage_preview_timer()
        self._update_zone_indicators()

    def _focus_first_in_zone(self) -> None:
        """Focus the first focusable widget in the active zone."""
        if self._active_zone == Zone.PANE_LIST:
            cards = list(self.query("#pane-list PaneCard"))
            if not cards:
                return
            # Restore previously focused card if possible
            if self._focused_pane_id:
                for card in cards:
                    if card.pane_id == self._focused_pane_id:
                        card.focus()
                        return
            # Fall back to first card
            cards[0].focus()
        elif self._active_zone == Zone.PREVIEW:
            try:
                self.query_one("#content-preview", PreviewPanel).focus()
            except Exception:
                pass

    def _update_zone_indicators(self) -> None:
        """Update visual indicators showing which zone is active."""
        try:
            for section_id, zone in [
                ("#pane-list", Zone.PANE_LIST),
                ("#content-section", Zone.PREVIEW),
            ]:
                widget = self.query_one(section_id)
                widget.set_class(self._active_zone == zone, "zone-active")
        except Exception:
            return
        # Refresh the preview header (LIVE indicator)
        self._update_content_preview()
        # Update footer to show/hide bindings based on active zone
        self.refresh_bindings()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Show/hide footer bindings based on active zone."""
        if self._active_zone == Zone.PREVIEW:
            return action == "switch_zone"
        return action != "switch_zone"

    def action_switch_zone(self) -> None:
        """No-op — Tab is handled in on_key. Exists for Footer display only."""

    def action_send_enter(self) -> None:
        """No-op — Enter is handled in on_key. Exists for Footer display only."""

    def _manage_preview_timer(self) -> None:
        """Start/stop the fast preview timer based on active zone."""
        if self._active_zone == Zone.PREVIEW and self._preview_timer is None:
            self._preview_timer = self.set_interval(0.3, self._fast_preview_refresh)
        elif self._active_zone != Zone.PREVIEW and self._preview_timer is not None:
            self._preview_timer.stop()
            self._preview_timer = None

    def _nav_within_zone(self, direction: int) -> None:
        """Move focus up/down within the current zone's cards."""
        if self._active_zone == Zone.PANE_LIST:
            cards = list(self.query("#pane-list PaneCard"))
        else:
            return  # No card navigation in preview zone

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

    # -- Key handling ----------------------------------------------------------

    def on_key(self, event) -> None:
        key = event.key

        # Let modal screens (e.g. TuiSwitcherOverlay) handle their own keys
        if isinstance(self.screen, ModalScreen):
            return

        # Tab/Shift+Tab always cycle zones (in all zones including preview)
        if key == "tab":
            self._switch_zone(1)
            event.stop()
            event.prevent_default()
            return
        if key == "shift+tab":
            self._switch_zone(-1)
            event.stop()
            event.prevent_default()
            return

        # In pane-list zone: Enter sends Enter to the focused agent's tmux pane
        if key == "enter" and self._active_zone == Zone.PANE_LIST:
            if self._focused_pane_id and self._monitor:
                self._monitor.send_keys(self._focused_pane_id, "Enter")
                self._schedule_delayed_refresh()
            event.stop()
            event.prevent_default()
            return

        # In preview zone: forward everything to tmux
        if self._active_zone == Zone.PREVIEW:
            if self._focused_pane_id and self._monitor:
                self._forward_key_to_tmux(event)
            event.stop()
            event.prevent_default()
            return

        # In non-preview zones: Up/Down navigate within zone
        if key == "up":
            self._nav_within_zone(-1)
            event.stop()
            event.prevent_default()
        elif key == "down":
            self._nav_within_zone(1)
            event.stop()
            event.prevent_default()

    def _forward_key_to_tmux(self, event) -> None:
        """Map a Textual key event to tmux send-keys and forward it."""
        key = event.key
        pane_id = self._focused_pane_id

        # Check special key mapping
        if key in _TEXTUAL_TO_TMUX:
            self._monitor.send_keys(pane_id, _TEXTUAL_TO_TMUX[key])
            self.call_later(self._fast_preview_refresh)
            return

        # Ctrl+key → C-key in tmux
        if key.startswith("ctrl+"):
            char = key[5:]
            self._monitor.send_keys(pane_id, f"C-{char}")
            self.call_later(self._fast_preview_refresh)
            return

        # Regular character
        if event.character and len(event.character) == 1:
            self._monitor.send_keys(pane_id, event.character, literal=True)
            self.call_later(self._fast_preview_refresh)

    # -- Focus tracking --------------------------------------------------------

    def on_descendant_focus(self, event) -> None:
        widget = event.widget
        if isinstance(widget, PaneCard):
            self._active_zone = Zone.PANE_LIST
            self._focused_pane_id = widget.pane_id
            self._update_content_preview()
            self._manage_preview_timer()
            self._update_zone_indicators()
        elif isinstance(widget, PreviewPanel):
            self._active_zone = Zone.PREVIEW
            self._manage_preview_timer()
            self._update_zone_indicators()

    def _get_focused_pane_id(self) -> str | None:
        """Get pane_id from the currently focused widget."""
        focused = self.focused
        if isinstance(focused, PaneCard):
            return focused.pane_id
        return None

    # -- Actions ---------------------------------------------------------------

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

    def action_cycle_preview_size(self) -> None:
        """Cycle the preview pane through S/M/L sizes."""
        self._preview_size_idx = (self._preview_size_idx + 1) % len(PREVIEW_SIZES)
        section_h, preview_h, label = PREVIEW_SIZES[self._preview_size_idx]
        section = self.query_one("#content-section")
        scroll = self.query_one("#preview-scroll", ScrollableContainer)
        preview = self.query_one("#content-preview", PreviewPanel)
        section.styles.max_height = section_h
        scroll.styles.max_height = preview_h
        preview.styles.max_height = preview_h
        self.notify(f"Preview size: {label}")

    def action_toggle_auto_switch(self) -> None:
        """Toggle auto-switch mode on/off."""
        self._auto_switch = not self._auto_switch
        if self._auto_switch:
            self.notify("Auto-switch ON: preview follows idle agents needing attention")
        else:
            self.notify("Auto-switch OFF: manual selection only")
        self._rebuild_session_bar()
        self._rebuild_pane_list()

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

    def action_kill_pane(self) -> None:
        """Show kill confirmation dialog for the focused pane."""
        if self._monitor is None:
            return
        pane_id = self._get_focused_pane_id()
        if not pane_id:
            self.notify("Focus a pane first", severity="warning")
            return
        snap = self._snapshots.get(pane_id)
        if not snap:
            return
        task_info = None
        task_id = self._task_cache.get_task_id(snap.pane.window_name)
        if task_id:
            task_info = self._task_cache.get_task_info(task_id)
        self.push_screen(
            KillConfirmDialog(snap, task_info),
            callback=self._on_kill_confirmed,
        )

    def _on_kill_confirmed(self, confirmed: bool | None) -> None:
        """Callback after kill confirmation dialog."""
        if not confirmed:
            return
        pane_id = self._focused_pane_id
        if pane_id is None or self._monitor is None:
            return
        snap = self._snapshots.get(pane_id)
        name = snap.pane.window_name if snap else pane_id
        if self._monitor.kill_pane(pane_id):
            self._focused_pane_id = None
            self.notify(f"Killed {name}")
            self.call_later(self._refresh_data)
        else:
            self.notify(f"Failed to kill {name}", severity="error")

    def action_pick_next_sibling(self) -> None:
        """Find and launch next sibling task for the focused agent pane."""
        if self._monitor is None:
            return
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
        self._task_cache.invalidate(task_id)
        current_info = self._task_cache.get_task_info(task_id)
        # If task file not found, it was likely archived (Done) — still allow sibling pick
        current_title = current_info.title if current_info else f"(archived t{task_id})"
        current_status = current_info.status if current_info else "Done"

        result = self._task_cache.find_next_sibling(task_id)
        if not result:
            self.notify("No ready siblings or children found", severity="warning")
            return
        suggested_id, suggested_title = result
        parent_id = self._task_cache.get_parent_id(task_id) or task_id

        self.push_screen(
            NextSiblingDialog(
                task_id, current_title, current_status,
                suggested_id, suggested_title, parent_id,
            ),
            callback=self._on_next_sibling_result,
        )

    def _on_next_sibling_result(self, result: tuple[str, str] | None) -> None:
        """Callback after next-sibling dialog."""
        if result is None:
            return
        action, target_id = result

        pane_id = self._focused_pane_id
        if pane_id is None or self._monitor is None:
            return
        snap = self._snapshots.get(pane_id)
        if not snap:
            return
        task_id = self._task_cache.get_task_id(snap.pane.window_name)
        if not task_id:
            return
        current_info = self._task_cache.get_task_info(task_id)

        # Resolve pick command: specific child or parent for selection
        full_cmd = resolve_dry_run_command(self._project_root, "pick", target_id)
        if not full_cmd:
            self.notify(f"Failed to resolve pick command for t{target_id}", severity="error")
            return

        # Kill current pane if task is Done, archived (info is None), or a
        # parent task whose implementation has moved to its children.
        is_parent_with_children = "_" not in task_id
        if is_parent_with_children or not current_info or current_info.status == "Done":
            old_name = snap.pane.window_name
            self._monitor.kill_pane(pane_id)
            self._focused_pane_id = None
            self.notify(f"Killed {old_name}")

        # Launch new agent in tmux
        window_name = f"agent-pick-{target_id}"
        config = TmuxLaunchConfig(
            session=self._session,
            window=window_name,
            new_session=False,
            new_window=True,
        )
        _, err = launch_in_tmux(full_cmd, config)
        if err:
            self.notify(f"Launch failed: {err}", severity="error")
            return
        maybe_spawn_minimonitor(self._session, window_name)
        self.notify(f"Launched agent for t{target_id}")
        self.call_later(self._refresh_data)


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
        project_root=project_root,
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
