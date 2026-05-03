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
from collections.abc import Callable
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
    TaskDetailDialog, KillConfirmDialog, format_compare_mode_glyph,
)
from monitor.desync_summary import get_desync_summary as _get_desync_summary  # noqa: E402
from tui_switcher import TuiSwitcherMixin  # noqa: E402

import subprocess  # noqa: E402
from agent_launch_utils import resolve_dry_run_command, resolve_agent_string, TmuxLaunchConfig, launch_in_tmux, maybe_spawn_minimonitor, tmux_session_target  # noqa: E402
from agent_command_screen import AgentCommandScreen  # noqa: E402

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
#
# Numeric heights are applied as-is. String heights of the form "agents:N"
# mean: size the pane-list to fit N agent cards and give the rest of the
# terminal to the preview section (resolved at apply time).
PREVIEW_AGENT_CARD_LINES = 2     # worst-case lines per PaneCard (status row + task title row)
PREVIEW_LAYOUT_FIXED_LINES = 5   # header + session-bar + footer (3) + pane-list top/bottom border (2)
PREVIEW_MIN_SECTION_H = 4        # minimum section height so preview is never fully hidden
PREVIEW_MIN_PREVIEW_H = 2        # minimum inner scroll height

PREVIEW_SIZES = [
    (12, 10, "S"),
    (24, 22, "M"),
    (40, 38, "L"),
    ("agents:9", "agents:9", "XL_9"),
    ("agents:6", "agents:6", "XL_6"),
    ("agents:3", "agents:3", "XL_3"),
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


class PreviewScrollContainer(ScrollableContainer):
    """ScrollableContainer that reports user-driven scroll changes.

    Hooks the private `_on_*` handlers to run after Textual's built-in
    handlers. The notify is scheduled via `call_after_refresh` because
    Textual commits `scroll_y` updates on the next refresh frame — reading
    `self.scroll_y` synchronously after `super()._on_*` returns the
    pre-scroll value.
    """

    on_user_scroll: Callable[[], None] | None = None
    # Set synchronously inside each _on_* handler; cleared by
    # _record_preview_scroll after the deferred state update commits.
    # Read by _update_content_preview to skip content updates + scroll
    # restoration on the same frame as a user scroll event, avoiding a
    # race where the refresh tick would undo the user's scroll.
    user_is_scrolling: bool = False

    def _on_mouse_scroll_up(self, event) -> None:
        self.user_is_scrolling = True
        super()._on_mouse_scroll_up(event)
        self._schedule_notify()

    def _on_mouse_scroll_down(self, event) -> None:
        self.user_is_scrolling = True
        super()._on_mouse_scroll_down(event)
        self._schedule_notify()

    def _on_scroll_up(self, event) -> None:
        self.user_is_scrolling = True
        super()._on_scroll_up(event)
        self._schedule_notify()

    def _on_scroll_down(self, event) -> None:
        self.user_is_scrolling = True
        super()._on_scroll_down(event)
        self._schedule_notify()

    def _on_scroll_to(self, message) -> None:
        self.user_is_scrolling = True
        super()._on_scroll_to(message)
        self._schedule_notify()

    def _schedule_notify(self) -> None:
        if self.on_user_scroll is not None:
            self.call_after_refresh(self.on_user_scroll)


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


class RestartConfirmDialog(ModalScreen):
    """Confirmation dialog for restarting the task in the focused agent pane."""

    BINDINGS = [Binding("escape", "dismiss_dialog", "Close", show=False)]

    DEFAULT_CSS = """
    RestartConfirmDialog { align: center middle; }
    #restart-dialog { width: 70%; height: auto; background: $surface; border: thick $warning; padding: 1 2; }
    #restart-header { text-style: bold; color: $warning; margin: 0 0 1 0; }
    #restart-details { margin: 0 0 1 0; }
    #restart-buttons { width: 100%; height: auto; layout: horizontal; }
    #restart-buttons Button { margin: 0 1; }
    """

    def __init__(
        self,
        task_id: str,
        title: str,
        status: str,
        idle_seconds: float,
    ) -> None:
        super().__init__()
        self._task_id = task_id
        self._title = title
        self._status = status
        self._idle_seconds = idle_seconds

    def compose(self) -> ComposeResult:
        with Container(id="restart-dialog"):
            yield Static("[bold yellow]Restart Task[/]", id="restart-header")
            lines = [
                f"Current:   [bold]t{self._task_id}[/]: {self._title}  (Status: {self._status})",
                f"Terminal:  idle for {int(self._idle_seconds)}s",
            ]
            if self._status != "Ready":
                lines.append(
                    f"\n[yellow]⚠ Task status is '{self._status}' (not Ready) — "
                    f"pick workflow may behave unexpectedly[/]"
                )
            lines.append(
                "\n[dim]The current pane will be killed after you confirm the spawn dialog.[/]"
            )
            yield Static("\n".join(lines), id="restart-details")
            with Container(id="restart-buttons"):
                yield Button("Restart", variant="warning", id="btn-restart")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-restart")

    def action_dismiss_dialog(self) -> None:
        self.dismiss(False)


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

    PaneCard.selected {
        background: $accent 30%;
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
        scrollbar-gutter: stable;
    }

    PreviewPanel {
        height: auto;
        background: #1a1a1a;
        color: #d4d4d4;
    }

    PreviewPanel:focus {
        background: #1a1a1a;
    }
    """

    BINDINGS = [
        Binding("tab", "switch_zone", "← Back (Tab)", show=True),
        Binding("j", "tui_switcher", "TUI switcher"),
        Binding("q", "quit", "Quit"),
        Binding("s", "switch_to", "Switch"),
        Binding("i", "show_task_info", "Task Info"),
        Binding("r", "refresh", "Refresh"),
        Binding("f5", "refresh", "Refresh", show=False),
        Binding("z", "cycle_preview_size", "Zoom"),
        Binding("t", "scroll_preview_tail", "Tail"),
        Binding("k", "kill_pane", "Kill"),
        Binding("n", "pick_next_sibling", "Next Sibling"),
        Binding("R", "restart_task", "Restart"),
        Binding("enter", "send_enter", "Send ↵", show=True),
        Binding("A", "toggle_auto_switch", "Auto"),
        Binding("M", "toggle_multi_session", "Multi", show=False),
        Binding("L", "open_log", "Log"),
        Binding("d", "cycle_compare_mode", "Detect"),
    ]

    def __init__(
        self,
        session: str,
        project_root: Path,
        refresh_seconds: int = 3,
        capture_lines: int = 200,
        idle_threshold: float = 5.0,
        agent_prefixes: list[str] | None = None,
        tui_names: set[str] | None = None,
        expected_session: str | None = None,
        multi_session: bool = True,
        compare_mode_default: str = "stripped",
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
        self._multi_session = multi_session
        self._compare_mode_default = compare_mode_default
        self._snapshots: dict[str, PaneSnapshot] = {}
        self._focused_pane_id: str | None = None
        # Per-pane scroll memory: pane_id → (was_at_bottom, anchor_text).
        # `anchor_text` is the text of the topmost visible line at the moment
        # the user scrolled; on each refresh we locate it in the new content
        # and re-scroll so the same line stays at the top of the viewport,
        # which is stable against tmux's rolling capture window.
        self._preview_scroll_state: dict[str, tuple[bool, str | None]] = {}
        self._last_preview_pane_id: str | None = None
        # Lines last passed to preview.update() for the focused pane. Used by
        # _record_preview_scroll to resolve int(scroll_y) to anchor_text without
        # mixing rendered-view coordinates with live-snapshot coordinates.
        self._preview_rendered_lines: list[str] = []
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
            PreviewScrollContainer(
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

        # Rename the tmux window so the TUI switcher can find us. This runs
        # before `_start_monitoring()` constructs `self._monitor`, so it must
        # use raw subprocess rather than `self._monitor.tmux_run`.
        try:
            subprocess.run(
                ["tmux", "rename-window", "monitor"],
                capture_output=True, timeout=5,
            )
        except Exception:
            pass

        # Check if session name matches expected config. In multi-session
        # mode the attached session name is effectively "whichever aitasks
        # session you happen to be in"; the rename prompt is noise there.
        if (
            not self._multi_session
            and self._expected_session
            and self._session != self._expected_session
        ):
            # Check if a session with the expected name already exists.
            # Pre-monitor-init: no `self._monitor` yet, so subprocess is
            # the only available path here too.
            try:
                result = subprocess.run(
                    ["tmux", "has-session", "-t",
                     tmux_session_target(self._expected_session)],
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
            multi_session=self._multi_session,
            compare_mode_default=self._compare_mode_default,
            **kwargs,
        )

        async def _connect_control_client() -> None:
            try:
                ok = await self._monitor.start_control_client()
                if not ok:
                    self.log("tmux control mode unavailable; using subprocess fallback")
            except Exception as exc:
                self.log(f"tmux control mode init failed: {exc!r}")

        self.run_worker(
            _connect_control_client(),
            exclusive=False,
            exit_on_error=False,
            group="tmux-control-init",
        )

        try:
            scroll = self.query_one("#preview-scroll", PreviewScrollContainer)
            scroll.on_user_scroll = self._record_preview_scroll
        except Exception:
            pass
        self.call_later(self._refresh_data)
        self.set_interval(self._refresh_seconds, self._refresh_data)

    async def on_unmount(self) -> None:
        if getattr(self, "_monitor", None) is not None:
            try:
                await self._monitor.close_control_client()
            except Exception:
                pass

    @staticmethod
    def _locate_anchor(
        lines: list[str], anchor_text: str | None
    ) -> int | None:
        """Find `anchor_text` in `lines`; returns the first match or None.

        Disambiguation is not needed in practice for the monitor preview:
        duplicates tend to be consecutive (blank lines) and `lines.index`
        picks the topmost, which is what we want for a top-of-viewport
        anchor under a rolling buffer.
        """
        if anchor_text is None:
            return None
        try:
            return lines.index(anchor_text)
        except ValueError:
            return None

    def _record_preview_scroll(self) -> None:
        """Record user scroll intent for the focused pane.

        Called (via PreviewScrollContainer.call_after_refresh) once the user's
        mouse wheel / scrollbar drag / page click has committed scroll_y.
        Anchors by the text of the topmost visible line in the currently
        rendered content — stable against tmux's rolling capture.
        """
        if self._focused_pane_id is None:
            return
        try:
            scroll = self.query_one("#preview-scroll", PreviewScrollContainer)
        except Exception:
            return
        max_y = scroll.max_scroll_y
        scroll_y = scroll.scroll_y
        at_bottom = max_y <= 0 or scroll_y >= max_y - 1
        anchor_text: str | None = None
        if not at_bottom:
            idx = int(scroll_y)
            if 0 <= idx < len(self._preview_rendered_lines):
                anchor_text = self._preview_rendered_lines[idx]

        prev = self._preview_scroll_state.get(self._focused_pane_id)
        was_detached = prev is not None and not prev[0]

        self._preview_scroll_state[self._focused_pane_id] = (at_bottom, anchor_text)
        scroll.user_is_scrolling = False

        # Re-attach → pull a fresh snapshot so tail-follow resumes on latest output.
        if was_detached and at_bottom:
            self.call_later(self._fast_preview_refresh)

    # -- Cross-session project-root resolution ---------------------------------

    def _root_for_snap(self, snap: PaneSnapshot) -> Path:
        """Project root that owns the given pane's tmux session.

        Falls back to ``self._project_root`` when the pane has no session_name
        (legacy single-session paths) or its session is not in the discovered
        aitasks-sessions list.
        """
        sess = snap.pane.session_name
        if sess and self._monitor is not None:
            mapping = self._monitor.get_session_to_project_mapping()
            if sess in mapping:
                return mapping[sess]
        return self._project_root

    # -- Data refresh ----------------------------------------------------------

    async def _refresh_data(self) -> None:
        if self._monitor is None:
            return

        # Save focus state before rebuild
        saved_pane_id = self._focused_pane_id
        saved_zone = self._active_zone

        self._snapshots = await self._monitor.capture_all_async()
        # Refresh the per-session project-root mapping so cross-session task
        # data resolves from the right project. Cheap — piggybacks on the
        # TmuxMonitor sessions cache TTL.
        self._task_cache.update_session_mapping(
            self._monitor.get_session_to_project_mapping()
        )

        # Drop saved scroll state for panes that no longer exist.
        stale = [
            pid for pid in self._preview_scroll_state
            if pid not in self._snapshots
        ]
        for pid in stale:
            del self._preview_scroll_state[pid]
        if (
            self._last_preview_pane_id is not None
            and self._last_preview_pane_id not in self._snapshots
        ):
            self._last_preview_pane_id = None

        # Focus request from minimonitor (via tmux session env var). Explicit
        # requests take priority over auto-switch heuristics. If the target
        # pane isn't yet in the snapshot (startup race), leave the env var
        # in place so the next refresh can retry.
        target_name = self._consume_focus_request()
        if target_name:
            for pid, snap in self._snapshots.items():
                if (
                    snap.pane.category == PaneCategory.AGENT
                    and snap.pane.window_name == target_name
                ):
                    self._focused_pane_id = pid
                    saved_pane_id = pid
                    saved_zone = Zone.PANE_LIST
                    self._active_zone = Zone.PANE_LIST
                    self._clear_focus_request()
                    break

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
        snap = await self._monitor.capture_pane_async(self._focused_pane_id)
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

    def _consume_focus_request(self) -> str | None:
        """Read the `AITASK_MONITOR_FOCUS_WINDOW` tmux session env var.

        Returns the target window name if set, or None. Does NOT clear the
        variable — use `_clear_focus_request()` after a successful match so
        that a startup race (target pane not yet in snapshot) can be retried
        on the next refresh tick.
        """
        if self._monitor is None:
            return None
        rc, stdout = self._monitor.tmux_run([
            "show-environment", "-t", tmux_session_target(self._session),
            "AITASK_MONITOR_FOCUS_WINDOW",
        ])
        if rc != 0:
            return None
        line = stdout.strip()
        if not line or "=" not in line:
            return None
        # tmux emits "-VAR" for unset markers; those have no "=".
        _, _, value = line.partition("=")
        value = value.strip()
        return value or None

    def _clear_focus_request(self) -> None:
        """Unset the tmux session focus-request env var."""
        if self._monitor is None:
            return
        self._monitor.tmux_run([
            "set-environment", "-t", tmux_session_target(self._session),
            "-u", "AITASK_MONITOR_FOCUS_WINDOW",
        ])

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
            self._update_content_preview()
            return
        # If the user already navigated to a valid PaneCard during this
        # refresh cycle, respect their selection instead of reverting to the
        # saved id. Fixes the "arrow-keypress lost on refresh" race (t545).
        focused = self.focused
        if (
            isinstance(focused, PaneCard)
            and focused.pane_id in self._snapshots
        ):
            self._focused_pane_id = focused.pane_id
        elif pane_id is not None:
            for card in self.query("#pane-list PaneCard"):
                if hasattr(card, "pane_id") and card.pane_id == pane_id:
                    card.focus()
                    # Widget.focus() is deferred; on_descendant_focus may not
                    # fire before the next refresh tick, leaving saved_pane_id
                    # stale. Set _focused_pane_id directly so the next tick sees
                    # the real state.
                    self._focused_pane_id = card.pane_id
                    break
        # Sync preview with the final focus state. The _update_content_preview
        # call in _refresh_data (line 683) may have rendered with a stale
        # _focused_pane_id if DOM events during _rebuild_pane_list shifted
        # focus. This second call corrects the preview. On the fast path it's
        # cheap (same_pane check short-circuits). Fixes t576.
        self._update_content_preview()
        # Re-apply the .selected class to the freshly-mounted card whose
        # pane_id matches _focused_pane_id (cards were destroyed by the
        # rebuild). Required so the preview-zone indicator survives ticks.
        self._update_selected_card_indicator()

    def _rebuild_session_bar(self) -> None:
        total = len(self._snapshots)
        bar = self.query_one("#session-bar", SessionBar)
        auto_tag = "  [bold yellow][AUTO][/]" if self._auto_switch else ""
        try:
            desync = _get_desync_summary(Path.cwd(), compact=False)
        except Exception:
            desync = ""
        if self._monitor is not None and self._monitor.multi_session:
            sessions = {
                s.pane.session_name for s in self._snapshots.values()
                if s.pane.session_name
            }
            attached = self._read_attached_session() or self._session
            session_word = "session" if len(sessions) == 1 else "sessions"
            pane_word = "pane" if total == 1 else "panes"
            bar.update(
                f"tmux Monitor — {len(sessions)} {session_word} "
                f"· {total} {pane_word} · multi "
                f"(attached: {attached})"
                f"{auto_tag}"
                f"{desync}"
                f"  [dim]Tab: switch panel[/]"
            )
        else:
            bar.update(
                f"tmux Monitor — session: {self._session} "
                f"({total} pane{'s' if total != 1 else ''})"
                f"{auto_tag}"
                f"{desync}"
                f"  [dim]Tab: switch panel[/]"
            )

    def _read_attached_session(self) -> str | None:
        """Return the currently-attached tmux session name, or None on failure."""
        if self._monitor is None:
            return None
        rc, stdout = self._monitor.tmux_run(["display-message", "-p", "#S"])
        if rc != 0:
            return None
        return stdout.strip() or None

    def _format_agent_card_text(self, snap: PaneSnapshot) -> str:
        if snap.is_idle:
            idle_s = int(snap.idle_seconds)
            dot = "[yellow]\u25cf[/]"
            status = f"[yellow]IDLE {idle_s}s[/]"
        else:
            dot = "[green]\u25cf[/]"
            status = "[green]Active[/]"
        if self._monitor is not None:
            mode = self._monitor.get_compare_mode(snap.pane.pane_id)
            is_override = self._monitor.is_compare_mode_overridden(snap.pane.pane_id)
        else:
            mode = "stripped"
            is_override = False
        glyph = format_compare_mode_glyph(mode, is_override)
        text = (
            f" {dot} {glyph} {snap.pane.window_index}:{snap.pane.window_name} "
            f"({snap.pane.pane_index})  {status}"
        )
        task_id = self._task_cache.get_task_id(snap.pane.window_name)
        if task_id:
            info = self._task_cache.get_task_info(task_id, snap.pane.session_name)
            if info:
                text += f"\n     [dim italic]t{task_id}: {info.title}[/]"
        return text

    def _format_other_card_text(self, snap: PaneSnapshot) -> str:
        return (
            f" [dim]\u25cb[/] {snap.pane.window_index}:{snap.pane.window_name} "
            f"({snap.pane.pane_index})  [dim]{snap.pane.current_command}[/]"
        )

    def _rebuild_pane_list(self) -> None:
        container = self.query_one("#pane-list", VerticalScroll)
        multi_mode = bool(self._monitor and self._monitor.multi_session)

        agents: list[PaneSnapshot] = []
        others: list[PaneSnapshot] = []
        for snap in self._snapshots.values():
            if snap.pane.category == PaneCategory.AGENT:
                agents.append(snap)
            elif snap.pane.category == PaneCategory.OTHER:
                others.append(snap)

        # Sort by (session_name, window_index, pane_index) so the unified
        # multi-session list is stable across refreshes. Single-session mode
        # produces identical session_name for every snapshot, so the sort key
        # degrades to the legacy (window_index, pane_index) order.
        agents.sort(
            key=lambda s: (s.pane.session_name, s.pane.window_index, s.pane.pane_index)
        )
        others.sort(
            key=lambda s: (s.pane.session_name, s.pane.window_index, s.pane.pane_index)
        )

        # Fast path: same pane set and order → update text in place, no DOM
        # churn. This keeps the focused PaneCard alive across ticks so arrow
        # keypresses that arrive during a refresh still resolve against a
        # stable card list. Fixes t545 (arrow-keypress lost on refresh race).
        desired_ids = (
            [s.pane.pane_id for s in agents]
            + [s.pane.pane_id for s in others]
        )
        current_cards = [
            w for w in container.children if isinstance(w, PaneCard)
        ]
        current_ids = [c.pane_id for c in current_cards]
        if desired_ids and desired_ids == current_ids:
            # Header counts are unchanged (set is identical), but the
            # agents-section header's AUTO tag can flip via
            # action_toggle_auto_switch(). Update the agents header text in
            # place so the "⟳ AUTO" indicator stays in sync.
            headers = [
                w for w in container.children
                if isinstance(w, Static) and not isinstance(w, PaneCard)
            ]
            if agents and headers:
                auto_label = (
                    "  [bold yellow]⟳ AUTO[/]" if self._auto_switch else ""
                )
                headers[0].update(
                    f"[bold]CODE AGENTS ({len(agents)})[/]{auto_label}"
                )
            by_id = {c.pane_id: c for c in current_cards}
            for snap in agents:
                by_id[snap.pane.pane_id].update(
                    self._format_agent_card_text(snap)
                )
            for snap in others:
                by_id[snap.pane.pane_id].update(
                    self._format_other_card_text(snap)
                )
            return

        # Slow path (structural change): full rebuild. Arrow loss in this
        # window is tolerable because the pane set actually changed.
        for widget in list(container.children):
            widget.remove()

        def mount_with_session_dividers(snaps, card_fn):
            """Mount PaneCards with a session divider before each new group.

            In multi mode, emits a subtle `── sess_name ──` divider before the
            first card of each session so users can see at a glance which
            agents belong to which session, while still keeping the unified
            single-list ordering.
            """
            current_session = None
            for snap in snaps:
                sess = snap.pane.session_name
                if multi_mode and sess != current_session:
                    current_session = sess
                    label = sess or "?"
                    container.mount(Static(
                        f"  [dim]── {label} ──[/]",
                        classes="session-divider",
                    ))
                container.mount(PaneCard(snap.pane.pane_id, card_fn(snap)))

        if agents:
            auto_label = "  [bold yellow]⟳ AUTO[/]" if self._auto_switch else ""
            container.mount(Static(
                f"[bold]CODE AGENTS ({len(agents)})[/]{auto_label}",
                classes="section-header",
            ))
            mount_with_session_dividers(agents, self._format_agent_card_text)

        if others:
            container.mount(Static(
                f"[bold]OTHER ({len(others)})[/]",
                classes="section-header",
            ))
            mount_with_session_dividers(others, self._format_other_card_text)

    def _update_content_preview(self) -> None:
        try:
            preview = self.query_one("#content-preview", PreviewPanel)
            header = self.query_one("#content-header", Static)
            scroll = self.query_one("#preview-scroll", PreviewScrollContainer)
        except Exception:
            return

        if not (self._focused_pane_id and self._focused_pane_id in self._snapshots):
            header.update("[bold]Content Preview[/]")
            preview.styles.min_width = 0
            preview.update("[dim]Focus an agent or pane to see its output[/]")
            self._preview_rendered_lines = []
            self._last_preview_pane_id = self._focused_pane_id
            return

        snap = self._snapshots[self._focused_pane_id]
        saved = self._preview_scroll_state.get(self._focused_pane_id)
        is_paused = saved is not None and not saved[0]
        same_pane = (self._focused_pane_id == self._last_preview_pane_id)

        # -- Header (always refreshed so PAUSED/LIVE badge stays current) --
        pane_label = f"({snap.pane.window_index}:{snap.pane.window_name})"
        task_id = self._task_cache.get_task_id(snap.pane.window_name)
        if task_id:
            info = self._task_cache.get_task_info(task_id, snap.pane.session_name)
            if info:
                if self._active_zone == Zone.PREVIEW:
                    pane_label += f" [bold]t{task_id}: {info.title}[/]"
                else:
                    pane_label += f" [dim italic]t{task_id}: {info.title}[/]"

        if is_paused:
            tag = " [bold yellow]PAUSED[/]"
        elif self._active_zone == Zone.PREVIEW:
            tag = " [bold green]LIVE[/]"
        else:
            tag = ""

        if self._active_zone == Zone.PREVIEW:
            header.update(f"[bold white]Content Preview[/] {pane_label}{tag}")
        else:
            header.update(f"[bold]Content Preview[/] {pane_label}{tag}")

        # -- Frozen branch: skip content + scroll updates entirely --
        # Same pane as last tick AND (user detached OR user scroll in flight):
        # do not call preview.update() (no layout recompute, no scroll clamp)
        # and do not call scroll_end/scroll_to (no fighting the user).
        if same_pane and (is_paused or scroll.user_is_scrolling):
            self._last_preview_pane_id = self._focused_pane_id
            return

        # -- Active branch: render fresh content and restore scroll --
        lines = snap.content.rstrip().splitlines()
        if lines:
            content = _ansi_to_rich_text("\n".join(lines))
            preview.styles.min_width = snap.pane.width
            preview.update(content)
            self._preview_rendered_lines = lines

            if saved is None or saved[0]:
                # Tail follow (first view of this pane or at-bottom).
                self.call_after_refresh(
                    lambda: scroll.scroll_end(animate=False)
                )
            else:
                anchor_text = saved[1]
                target_idx = self._locate_anchor(lines, anchor_text)
                if target_idx is None:
                    # Anchor rolled off the capture buffer — snap to tail so
                    # we don't get stuck on a stale position on pane-return.
                    self.call_after_refresh(
                        lambda: scroll.scroll_end(animate=False)
                    )
                else:
                    target_f = float(target_idx)

                    def _restore(t=target_f):
                        scroll.scroll_to(y=t, animate=False)
                    self.call_after_refresh(_restore)
        else:
            preview.styles.min_width = 0
            preview.update("[dim](empty)[/]")
            self._preview_rendered_lines = []

        self._last_preview_pane_id = self._focused_pane_id

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
        # Keep the previewed PaneCard visually marked even when focus is on
        # the preview pane.
        self._update_selected_card_indicator()

    def _update_selected_card_indicator(self) -> None:
        """Mark the PaneCard matching _focused_pane_id with the 'selected' class.

        Provides a persistent visual hint of which agent's preview is shown,
        even when keyboard focus has moved to the PreviewPanel.
        """
        for card in self.query("#pane-list PaneCard"):
            card.set_class(card.pane_id == self._focused_pane_id, "selected")

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
        """Cycle the preview pane through S/M/L/XL_N sizes."""
        self._preview_size_idx = (self._preview_size_idx + 1) % len(PREVIEW_SIZES)
        self._apply_preview_size()

    def _apply_preview_size(self) -> None:
        """Apply the current preview size index to the preview widgets."""
        section_h, preview_h, label = PREVIEW_SIZES[self._preview_size_idx]

        if isinstance(section_h, str) and section_h.startswith("agents:"):
            # Dynamic mode: size the pane-list to fit N agent cards; the
            # preview section gets whatever vertical space remains.
            # self.size may be (0, 0) before the first layout pass.
            n_agents = int(section_h.split(":", 1)[1])
            screen_h = self.size.height or 40
            reserve = PREVIEW_LAYOUT_FIXED_LINES + n_agents * PREVIEW_AGENT_CARD_LINES
            section_h = max(PREVIEW_MIN_SECTION_H, screen_h - reserve)
            preview_h = max(PREVIEW_MIN_PREVIEW_H, section_h - 2)

        try:
            section = self.query_one("#content-section")
            scroll = self.query_one("#preview-scroll", ScrollableContainer)
        except Exception:
            return

        # Cap the section and scroll container heights only. The inner
        # PreviewPanel (Static) must remain free to grow to its content
        # height so the ScrollableContainer has overflow to scroll over.
        section.styles.max_height = section_h
        scroll.styles.max_height = preview_h
        self.notify(f"Preview size: {label}")
        # Immediately repopulate the (possibly larger) preview without
        # waiting for the next 3s refresh cycle.
        self._update_content_preview()

    def action_scroll_preview_tail(self) -> None:
        """Jump preview to the bottom and re-engage tail-follow."""
        try:
            scroll = self.query_one("#preview-scroll", PreviewScrollContainer)
        except Exception:
            return
        scroll.scroll_end(animate=False)
        if self._focused_pane_id is not None:
            self._preview_scroll_state[self._focused_pane_id] = (True, None)
            # Pull fresh content so tail-follow resumes on the latest output.
            self.call_later(self._fast_preview_refresh)
        self.notify("Tail follow")

    def on_resize(self, event) -> None:
        """Recompute dynamic sizing specs (agents:N) when the terminal is resized."""
        section_spec, _, _ = PREVIEW_SIZES[self._preview_size_idx]
        if isinstance(section_spec, str) and section_spec.startswith("agents:"):
            self._apply_preview_size()

    def action_toggle_auto_switch(self) -> None:
        """Toggle auto-switch mode on/off."""
        self._auto_switch = not self._auto_switch
        if self._auto_switch:
            self.notify("Auto-switch ON: preview follows idle agents needing attention")
        else:
            self.notify("Auto-switch OFF: manual selection only")
        self._rebuild_session_bar()
        self._rebuild_pane_list()

    def action_toggle_multi_session(self) -> None:
        """Flip the multi-session view ON/OFF in memory.

        Persists only for the lifetime of this `MonitorApp` instance — no
        config write (TUI auto-commit restriction). Invalidates the session
        cache so the first post-toggle refresh re-discovers immediately.
        """
        if self._monitor is None:
            return
        self._monitor.multi_session = not self._monitor.multi_session
        self._monitor.invalidate_sessions_cache()
        self._multi_session = self._monitor.multi_session
        state = "ON" if self._monitor.multi_session else "OFF"
        self.notify(f"Multi-session {state}", timeout=3)
        self.call_later(self._refresh_data)

    def action_cycle_compare_mode(self) -> None:
        """Cycle the focused pane's idle-detection compare mode."""
        if self._monitor is None:
            return
        pane_id = self._get_focused_pane_id()
        if not pane_id:
            self.notify("Focus an agent pane first", severity="warning")
            return
        new_mode, is_default = self._monitor.cycle_compare_mode(pane_id)
        suffix = " (default)" if is_default else " (override)"
        self.notify(f"Idle detect mode: {new_mode}{suffix}", timeout=3)
        self.call_later(self._refresh_data)

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
        sess = snap.pane.session_name
        self._task_cache.invalidate(task_id, sess)
        info = self._task_cache.get_task_info(task_id, sess)
        if not info:
            self.notify(f"Task t{task_id} not found", severity="error")
            return
        self.push_screen(TaskDetailDialog(info))

    def action_open_log(self) -> None:
        """Open the ANSI-aware log viewer for the focused agent pane."""
        pane_id = self._get_focused_pane_id()
        if not pane_id:
            self.notify("Focus an agent pane first", severity="warning")
            return
        snap = self._snapshots.get(pane_id)
        if not snap:
            return
        window_name = snap.pane.window_name
        if not window_name.startswith("agent-"):
            self.notify("Not an agent pane", severity="warning")
            return
        agent_name = window_name[len("agent-"):]
        if agent_name.startswith("pick-"):
            self.notify("Pick launcher panes have no agent log")
            return
        root = self._root_for_snap(snap)
        crews_root = root / ".aitask-crews"
        log_path = None
        if crews_root.exists():
            for crew_dir in sorted(crews_root.glob("crew-*")):
                candidate = crew_dir / f"{agent_name}_log.txt"
                if candidate.exists():
                    log_path = candidate
                    break
        if log_path is None:
            self.notify(
                f"No log file found for {agent_name}",
                severity="warning",
            )
            return
        try:
            subprocess.Popen(
                ["./ait", "crew", "logview", "--path", str(log_path)],
                cwd=str(root),
            )
            self.notify(f"Opening log for {agent_name}")
        except OSError as exc:
            self.notify(f"Failed to launch log viewer: {exc}", severity="error")

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
            task_info = self._task_cache.get_task_info(task_id, snap.pane.session_name)
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
        ok, _ = self._monitor.kill_agent_pane_smart(pane_id)
        if ok:
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
        sess = snap.pane.session_name
        self._task_cache.invalidate(task_id, sess)
        current_info = self._task_cache.get_task_info(task_id, sess)
        # If task file not found, it was likely archived (Done) — still allow sibling pick
        current_title = current_info.title if current_info else f"(archived t{task_id})"
        current_status = current_info.status if current_info else "Done"

        result = self._task_cache.find_next_sibling(task_id, sess)
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
        sess = snap.pane.session_name
        current_info = self._task_cache.get_task_info(task_id, sess)

        # Resolve pick command in the project that owns the focused pane's
        # session — siblings live in that same project.
        target_root = self._root_for_snap(snap)
        full_cmd = resolve_dry_run_command(target_root, "pick", target_id)
        if not full_cmd:
            self.notify(f"Failed to resolve pick command for t{target_id}", severity="error")
            return

        # Kill current pane if task is Done, archived (info is None), or a
        # parent task whose implementation has moved to its children.
        is_parent_with_children = "_" not in task_id
        if is_parent_with_children or not current_info or current_info.status == "Done":
            old_name = snap.pane.window_name
            self._monitor.kill_agent_pane_smart(pane_id)
            self._focused_pane_id = None
            self.notify(f"Killed {old_name}")

        prompt_str = f"/aitask-pick {target_id}"
        window_name = f"agent-pick-{target_id}"
        agent_string = resolve_agent_string(target_root, "pick")
        screen = AgentCommandScreen(
            f"Pick Task t{target_id}", full_cmd, prompt_str,
            default_window_name=window_name,
            project_root=target_root,
            operation="pick",
            operation_args=[target_id],
            default_agent_string=agent_string,
        )

        def on_pick_result(pick_result):
            if isinstance(pick_result, TmuxLaunchConfig):
                _, err = launch_in_tmux(screen.full_command, pick_result)
                if err:
                    self.notify(f"Launch failed: {err}", severity="error")
                    return
                if pick_result.new_window:
                    maybe_spawn_minimonitor(pick_result.session, pick_result.window)
                self.notify(f"Launched agent for t{target_id}")
            self.call_later(self._refresh_data)

        self.push_screen(screen, on_pick_result)

    def action_restart_task(self) -> None:
        """Kill the focused idle agent pane and re-run pick for the same task."""
        if self._monitor is None:
            return
        pane_id = self._get_focused_pane_id()
        if not pane_id:
            self.notify("Focus an agent pane first", severity="warning")
            return
        snap = self._snapshots.get(pane_id)
        if not snap:
            return
        if not snap.is_idle:
            self.notify(
                "Restart only available when the terminal is idle",
                severity="warning",
            )
            return
        task_id = self._task_cache.get_task_id(snap.pane.window_name)
        if not task_id:
            self.notify("No task ID in window name", severity="warning")
            return
        sess = snap.pane.session_name
        self._task_cache.invalidate(task_id, sess)
        info = self._task_cache.get_task_info(task_id, sess)
        title = info.title if info else f"(archived t{task_id})"
        status = info.status if info else "Done"

        self.push_screen(
            RestartConfirmDialog(task_id, title, status, snap.idle_seconds),
            callback=lambda ok: self._on_restart_confirmed(ok, pane_id, task_id),
        )

    def _on_restart_confirmed(
        self, confirmed: bool | None, pane_id: str, task_id: str
    ) -> None:
        if not confirmed:
            return
        if self._monitor is None:
            return
        snap = self._snapshots.get(pane_id)
        if not snap:
            self.notify("Focused pane no longer exists", severity="warning")
            return

        target_root = self._root_for_snap(snap)
        full_cmd = resolve_dry_run_command(target_root, "pick", task_id)
        if not full_cmd:
            self.notify(
                f"Failed to resolve pick command for t{task_id}",
                severity="error",
            )
            return

        prompt_str = f"/aitask-pick {task_id}"
        window_name = f"agent-pick-{task_id}"
        agent_string = resolve_agent_string(target_root, "pick")
        screen = AgentCommandScreen(
            f"Pick Task t{task_id}", full_cmd, prompt_str,
            default_window_name=window_name,
            project_root=target_root,
            operation="pick",
            operation_args=[task_id],
            default_agent_string=agent_string,
        )

        old_window_name = snap.pane.window_name

        def on_pick_result(pick_result):
            if isinstance(pick_result, TmuxLaunchConfig):
                # Tear down the old agent before launching. In the common
                # single-agent-per-window case, kill_agent_pane_smart kills
                # the whole window (matching the behaviour added in t556) so
                # the new `agent-pick-<id>` window does not collide with a
                # stale one of the same name. In the rare multi-agent-split
                # case, only the restarted pane dies and siblings survive;
                # maybe_spawn_minimonitor's last-match window lookup keeps
                # the new companion attached to the correct window even if
                # two windows share a name transiently.
                if self._monitor:
                    ok, _ = self._monitor.kill_agent_pane_smart(pane_id)
                    if ok:
                        if self._focused_pane_id == pane_id:
                            self._focused_pane_id = None
                        self.notify(f"Killed {old_window_name}")
                _, err = launch_in_tmux(screen.full_command, pick_result)
                if err:
                    self.notify(f"Launch failed: {err}", severity="error")
                    return
                if pick_result.new_window:
                    maybe_spawn_minimonitor(pick_result.session, pick_result.window)
                self.notify(f"Restarted agent for t{task_id}")
            self.call_later(self._refresh_data)

        self.push_screen(screen, on_pick_result)


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
    capture_lines = args.lines if args.lines is not None else config.get("capture_lines", 200)

    app = MonitorApp(
        session=session,
        project_root=project_root,
        refresh_seconds=refresh_seconds,
        capture_lines=capture_lines,
        idle_threshold=config.get("idle_threshold", 5.0),
        agent_prefixes=config.get("agent_prefixes"),
        tui_names=config.get("tui_names"),
        expected_session=expected_session,
        compare_mode_default=config.get("compare_mode_default", "stripped"),
    )
    app.run()


if __name__ == "__main__":
    main()
