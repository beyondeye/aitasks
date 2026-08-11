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
import contextlib
import os
import sys
from collections.abc import Callable
from enum import Enum
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
    load_project_tmux_config,
    capture_shadow_text,
    compute_shadow_staleness,
    refresh_shadow_phase_stamp,
    find_shadow_pane_status,
    spawn_shadow,
    _SHADOW_DEEP_RETRY_LINES,
    _SHADOW_TRUNCATED_MSG,
)
from monitor.tmux_control import TmuxControlState  # noqa: E402
from monitor.monitor_shared import (  # noqa: E402
    _ansi_to_rich_text, _TASK_ID_RE, GateSummaryCache, TaskInfo, TaskInfoCache,
    workflow_phase,
    TaskDetailDialog, KillConfirmDialog, NextSiblingDialog, ChooseSiblingModal,
    AgentMarksMixin, ConcernBlockInspectModal, ConcernPickerModal,
    ShadowRejectionsMixin, STATE_STYLE_DONE,
    format_compare_mode_glyph, format_mark_glyph, format_pane_status,
    format_session_divider, format_shadow_glyph, format_state_dot,
    is_task_completed, unparsed_concerns_msg,
)
from monitor.concern_parser import (  # noqa: E402
    _SENTINEL_SAFE_COLS, block_head_truncated, block_region,
    build_clipboard_payload, concern_block_signature, concern_marker_line,
    needs_addressing, parse_concerns, unrecovered_markers,
)
from monitor.desync_summary import get_desync_summary as _get_desync_summary  # noqa: E402
from rich.text import Text  # noqa: E402
from tui_switcher import TuiSwitcherMixin  # noqa: E402
from shortcuts_mixin import ShortcutsMixin  # noqa: E402
from tui_clipboard import copy_to_system_clipboard  # noqa: E402

import subprocess  # noqa: E402
from agent_launch_utils import resolve_dry_run_command, resolve_agent_string, TmuxLaunchConfig, launch_in_tmux, maybe_spawn_minimonitor, mark_monitor_pane, tmux_session_target, unmark_monitor_pane  # noqa: E402
from agent_command_screen import AgentCommandScreen, resolve_skill_profile  # noqa: E402
from tmux_exec import TmuxClient  # noqa: E402

# Gateway client for the Layer-A backend calls below (has-session /
# rename-session target the ait backend session by name, so they must reach
# the dedicated gateway socket — t953). Ambient $TMUX self-probes
# (display-message / rename-window on our own pane) stay raw by design.
_TMUX = TmuxClient()

from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import (  # noqa: E402
    Container, Horizontal, ScrollableContainer, Vertical, VerticalScroll,
)
from textual.screen import ModalScreen  # noqa: E402
from textual.timer import Timer  # noqa: E402
from textual.widgets import Button, Footer, Header, Label, Static  # noqa: E402


def _rename_window_argv(pane: str | None) -> list[str]:
    """Build the ``tmux rename-window monitor`` argv, pinned to *pane*.

    Returns an EMPTY list when *pane* is falsy. Without $TMUX_PANE there is no
    reliable way to identify the monitor's own window, and an untargeted
    ``tmux rename-window`` resolves to the attached client's *active* window —
    which, with automatic-rename off, would permanently mislabel an unrelated
    window (e.g. an agent-explore window or a board) as ``monitor``. Fail safe:
    issue no rename rather than renaming an arbitrary window. See t941 / t1130.
    """
    if not pane:
        return []
    return ["tmux", "rename-window", "-t", pane, "monitor"]


# -- Zone model ---------------------------------------------------------------

class Zone(Enum):
    PANE_LIST = "pane_list"
    PREVIEW = "preview"
    SHADOW = "shadow"


ZONE_ORDER = [Zone.PANE_LIST, Zone.PREVIEW, Zone.SHADOW]

# -- Shadow column (t1216_2) ---------------------------------------------------
#
# How many consecutive FULL refreshes may drop the shadow snapshot before the
# SHADOW zone gives up and falls back to PREVIEW. A snapshot can go absent for
# two indistinguishable reasons — the shadow pane died, or a single capture
# failed (test_monitor_shadow_status.LifecycleTests pins that a transient
# failure legitimately drops the entry with no stale preservation) — so the
# grace window covers both rather than pretending they can be told apart.
# Counted on the 3s tick, so 2 ticks is a wall-clock ~6s.
SHADOW_ABSENT_GRACE_TICKS = 2

# Minimum columns the AGENT preview must keep for the side-by-side split to be
# worth doing. Below this the split is suppressed and only the focused column
# is rendered full-width.
SHADOW_MIN_AGENT_COLS = 40

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

# The abstract-key-name → tmux send-keys map (`_TEXTUAL_TO_TMUX`) and its
# translator moved to monitor_core (t822_7); the applink `forward_key` verb and
# this preview-zone forwarder both resolve keys via monitor_core.translate_key,
# reached here through TmuxMonitor.forward_key.


# -- Widgets ------------------------------------------------------------------

class SessionBar(Static):
    """One-line bar showing session name, pane count, awaiting + idle counts."""
    pass


class PaneCard(Static, can_focus=True):
    """Status entry for a pane in the agents/other section."""

    def __init__(self, pane_id: str, text: str, **kwargs) -> None:
        super().__init__(text, **kwargs)
        self.pane_id = pane_id


class PreviewPanel(Static, can_focus=True):
    """Focusable content preview panel — forwards keystrokes to tmux when active."""
    pass


class PreviewRow(Horizontal):
    """Horizontal row holding the agent + shadow preview columns.

    Owns the trigger for the narrow-split decision (t1216_2). The App-level
    `on_resize` fires BEFORE this row has been re-laid-out, so a fit check
    driven from there measures a stale `content_region` (verified: on a
    120→70 resize the App handler still sees a 120-column row). Reacting to
    the row's OWN Resize event is what makes the measurement authoritative.
    """

    on_row_resize: Callable[[], None] | None = None

    def on_resize(self, event) -> None:
        if self.on_row_resize is not None:
            self.on_row_resize()


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
            # Gateway-routed with an explicit exact-match target (t953): with
            # the dedicated `-L ait` socket in the argv, implicit
            # current-session resolution would rely on $TMUX_PANE existing on
            # the ait server — false when the monitor runs inside a legacy
            # default-socket session. The gateway swallows exceptions into
            # rc != 0, so branch on rc instead of try/except.
            rc, _ = _TMUX.run(
                ["rename-session", "-t", tmux_session_target(self._current),
                 self._expected],
            )
            if rc == 0:
                self.dismiss(True)
            else:
                self.app.notify("Failed to rename session", severity="error")
                self.dismiss(False)
        else:
            self.dismiss(False)

    def action_dismiss_dialog(self) -> None:
        self.dismiss(False)


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

class MonitorApp(
    AgentMarksMixin, ShadowRejectionsMixin, TuiSwitcherMixin, ShortcutsMixin, App
):
    """Textual app for monitoring tmux panes running code agents."""

    _shortcuts_scope = "monitor"

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

    #preview-row {
        height: 1fr;
    }

    #agent-col {
        width: 1fr;
    }

    #shadow-col {
        width: auto;
        display: none;
        border-left: solid $primary-darken-2;
    }

    #shadow-col.zone-active {
        border-left: solid $warning;
    }

    #shadow-scroll {
        height: 1fr;
        max-height: 22;
        scrollbar-gutter: stable;
    }

    #shadow-header {
        dock: bottom;
        padding: 0 1;
        text-style: bold;
        color: $text-muted;
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
        *ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS,
        Binding("tab", "switch_zone", "← Back (Tab)", show=True),
        Binding("j", "tui_switcher", "TUI switcher"),
        Binding("q", "quit", "Quit"),
        Binding("s", "switch_to", "Switch"),
        Binding("i", "show_task_info", "Task Info"),
        Binding("r", "refresh", "Refresh"),
        # Hidden on purpose: an alias of `r`, which is already footer-visible with
        # the same label and action. Showing both would duplicate a footer entry
        # rather than surface an operation.
        Binding("f5", "refresh", "Refresh", show=False),
        Binding("z", "cycle_preview_size", "Zoom"),
        Binding("t", "scroll_preview_tail", "Tail"),
        Binding("k", "kill_pane", "Kill"),
        Binding("n", "pick_next_sibling", "Next Sibling"),
        Binding("R", "restart_task", "Restart"),
        Binding("enter", "send_enter", "Send ↵", show=True),
        Binding("A", "toggle_auto_switch", "Auto"),
        Binding("M", "toggle_multi_session", "Multi"),
        Binding("L", "open_log", "Log"),
        Binding("d", "cycle_compare_mode", "Detect"),
        Binding("c", "pick_concerns", "Concerns"),
        Binding("e", "launch_shadow", "Shadow"),
        Binding("E", "launch_shadow_pick", "Shadow (pick)"),
        Binding("space", "toggle_mark", "Mark"),
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
        rename_window: bool = False,
        mark_pane: bool = False,
    ) -> None:
        super().__init__()
        self.current_tui_name = "monitor"
        # Only the production launcher (main()) passes rename_window=True.
        # Test mounts keep the default False so on_mount can never rename a
        # window on the live tmux server — a test run inside an agent's pane
        # inherits that pane's $TMUX_PANE and would relabel the agent's own
        # window as "monitor" (t1240).
        self._rename_window = rename_window
        # Same production-launcher gate, for the @aitask_monitor_kind pane
        # marker the single-instance guards read (t1451): a run_test() mount
        # inherits the agent's $TMUX_PANE and must not stamp a live pane.
        self._mark_pane = mark_pane
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
        # Monotonic token bumped for every scheduled preview render (t1111_5).
        # Guards the offloaded _ansi_to_rich_text render against out-of-order /
        # superseded resolution: an apply (and its deferred scroll restore) only
        # touches the preview if its token is still current AND focus has not moved.
        self._preview_render_gen: int = 0
        # -- Shadow column mirrors of the four fields above (t1216_2). Kept
        # separate rather than shared so a slow shadow render can never
        # supersede an agent render (and vice versa); the two run in different
        # worker groups for the same reason. _shadow_scroll_state is keyed by
        # the SHADOW pane id, not the followed agent's.
        self._shadow_scroll_state: dict[str, tuple[bool, str | None]] = {}
        self._last_shadow_pane_id: str | None = None
        self._shadow_rendered_lines: list[str] = []
        self._shadow_render_gen: int = 0
        # Consecutive FULL refreshes for which the selected agent's shadow
        # snapshot was absent. See SHADOW_ABSENT_GRACE_TICKS.
        self._shadow_absent_ticks: int = 0
        # Whether the shadow column is currently shown (a shadow is known AND
        # the side-by-side split fits — Step 4 narrow fallback).
        self._shadow_split_ok: bool = False
        # Last observed shadow pane width. Used to keep the column sized (and
        # visible) while the zone HOLDS a momentarily-absent snapshot during
        # the grace window, when no snapshot is available to measure.
        self._last_shadow_width: int | None = None
        # The agent whose shadow the SHADOW zone is currently bound to. Set on
        # entry, used to tell "the selection moved" from "the snapshot blipped".
        self._shadow_zone_agent_id: str | None = None
        # Which preview column `t` (tail) targets. `t` is only pressable from
        # PANE_LIST — check_action disables every non-switch_zone binding while
        # a preview zone is focused — so this tracks the LAST-focused preview
        # column rather than the active zone.
        self._active_preview_zone: Zone = Zone.PREVIEW
        # -- Shadow concern state (t1216_3). Keyed by the FOLLOWED agent's pane
        # id, not the shadow's: the monitor's identity for a row is the agent,
        # and a marker must survive a shadow respawn so an identical block is
        # not re-offered.
        #
        # Every agent's shadow snapshot resolved on the current full tick, so
        # the concern scan reuses the one lookup _reconcile_shadow_state already
        # does instead of re-walking get_shadow_snapshot.
        self._tick_shadow_snaps: dict[str, PaneSnapshot] = {}
        # This tick's raw-capture signature per agent. Absent => no complete
        # block => no badge. Rebuilt every tick (see _scan_concern_signatures).
        self._concern_sig_latest: dict[str, str] = {}
        # Signatures already offered (the picker was pushed, or the block was
        # authoritatively shown to hold nothing forwardable) and signatures
        # already checked with a -J capture. Each value is a frozenset holding
        # BOTH the raw trigger digest and the -J captured one — the two capture
        # paths hash the same block differently whenever it wraps mid-word, so a
        # single stored string would never match again.
        self._concern_sig_offered: dict[str, frozenset[str]] = {}
        self._concern_sig_examined: dict[str, frozenset[str]] = {}
        # Throttle for the sub-_SENTINEL_SAFE_COLS probe (every other tick).
        self._concern_tick: int = 0
        # One offer pass at a time. A busy latch rather than an exclusive worker:
        # cancelling would orphan capture_shadow_text's subprocess, which is
        # killed only on its own timeout.
        self._offer_busy: bool = False
        # Held from the `c` keypress until the picker is dismissed, so a second
        # `c` over the open modal cannot stack another one.
        self._concern_pick_busy: bool = False
        # Task id of the agent the open picker belongs to, captured at pick time
        # for the dismissal callback (t1427_2). None = unresolvable.
        self._concern_pick_task_id: str | None = None
        self._pane_cards: dict[str, PaneCard] = {}
        self._selected_card_pane_id: str | None = None
        self._monitor: TmuxMonitor | None = None
        self._active_zone: Zone = Zone.PANE_LIST
        self._preview_timer: Timer | None = None
        self._delayed_refresh_timer: Timer | None = None
        self._refresh_timer: Timer | None = None
        self._preview_size_idx: int = PREVIEW_DEFAULT_SIZE
        self._task_cache = TaskInfoCache(project_root)
        self._gate_cache = GateSummaryCache()
        self._auto_switch: bool = False
        # Pane ids whose task is finished, recomputed once per refresh tick
        # (t1322). Read by the card badge, the session bar's `done` counter and
        # the auto-switch filter, so all three agree within a tick. Starts empty
        # so keypress-driven rebuilds that run outside _refresh_data (e.g.
        # action_toggle_auto_switch) reuse the last tick's set rather than
        # triggering an N-stat fan-out on a keystroke.
        self._completed_pane_ids: frozenset[str] = frozenset()
        # Prioritized-agent marks (t1326): cached reader + purge scheduling.
        self._init_agent_marks()

    def compose(self) -> ComposeResult:
        yield Header()
        yield SessionBar(id="session-bar")
        yield VerticalScroll(id="pane-list")
        # Two columns inside the preview section: the agent preview (left,
        # elastic) and the shadow preview (right, sized to the real shadow
        # pane's width so its content renders unwrapped). #shadow-col is
        # display:none until a shadow is bound AND the split fits (t1216_2).
        # The agent column keeps every id the rest of the app queries by
        # (#preview-scroll, #content-preview, #content-header); #content-header
        # docks to whatever its parent is, so moving it inside #agent-col
        # re-docks it there with no CSS change.
        yield Container(
            PreviewRow(
                Vertical(
                    PreviewScrollContainer(
                        PreviewPanel("", id="content-preview"),
                        id="preview-scroll",
                    ),
                    Static("[bold]Content Preview[/]", id="content-header"),
                    id="agent-col",
                ),
                Vertical(
                    PreviewScrollContainer(
                        PreviewPanel("", id="shadow-preview"),
                        id="shadow-scroll",
                    ),
                    Static("[bold]Shadow[/]", id="shadow-header"),
                    id="shadow-col",
                ),
                id="preview-row",
            ),
            id="content-section",
        )
        yield Footer()

    def on_mount(self) -> None:
        # Pure-DOM widget wiring first: it has no tmux dependency, so it must
        # not sit behind the not-inside-tmux early return below (which would
        # also make it unreachable from any test that scrubs $TMUX).
        self._wire_preview_hooks()

        if not os.environ.get("TMUX"):
            self.sub_title = "Not running inside tmux"
            self.query_one("#session-bar", SessionBar).update(
                "[bold red]Warning:[/] Not inside tmux — monitoring requires an active tmux session"
            )
            return

        # Rename the tmux window so the TUI switcher can find us. This runs
        # before `_start_monitoring()` constructs `self._monitor`, so it must
        # use raw subprocess rather than `self._monitor.tmux_run`. Gated on
        # the constructor's rename_window flag (production launcher only) so
        # test mounts never rename a live window (t1240).
        if self._rename_window:
            try:
                rename_argv = _rename_window_argv(os.environ.get("TMUX_PANE"))
                if rename_argv:
                    subprocess.run(rename_argv, capture_output=True, timeout=5)
            except Exception:
                pass

        # Stamp our own pane so the single-instance guards can see us (t1451).
        # The spawner never does this — see mark_monitor_pane's docstring.
        if self._mark_pane:
            with contextlib.suppress(Exception):
                mark_monitor_pane("monitor")

        # Check if session name matches expected config. In multi-session
        # mode the attached session name is effectively "whichever aitasks
        # session you happen to be in"; the rename prompt is noise there.
        if (
            not self._multi_session
            and self._expected_session
            and self._session != self._expected_session
        ):
            # Check if a session with the expected name already exists.
            # Pre-monitor-init: no `self._monitor` yet, so the module-level
            # gateway client is the path here (Layer-A backend query, t953).
            try:
                rc, _ = _TMUX.run(
                    ["has-session", "-t",
                     tmux_session_target(self._expected_session)],
                )
                if rc == 0:
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

    def _teardown_prior_monitoring(self) -> None:
        """Cancel the prior refresh timer and close the prior monitor's
        control client, if any.

        Called at the top of `_start_monitoring()` so re-entry paths
        (e.g., the `SessionRenameDialog` callback) do not leak a refresh
        timer, a `tmux -C attach` subprocess, or a `tmux-control-loop`
        bg thread. Without this guard, a session-rename re-entry doubles
        the polling cadence and silently spawns a second control client
        that lives until the process exits.
        """
        if self._refresh_timer is not None:
            with contextlib.suppress(Exception):
                self._refresh_timer.stop()
            self._refresh_timer = None
        prev = self._monitor
        if prev is not None:
            self._monitor = None

            async def _close_prev() -> None:
                with contextlib.suppress(Exception):
                    await prev.close_control_client()

            self.run_worker(
                _close_prev(),
                exclusive=False,
                exit_on_error=False,
                group="tmux-control-teardown",
            )

    def _start_monitoring(self) -> None:
        """Initialize the TmuxMonitor and start refreshing."""
        self._teardown_prior_monitoring()

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

        self.call_later(self._refresh_data)
        self._refresh_timer = self.set_interval(
            self._refresh_seconds, self._refresh_data
        )

    def _wire_preview_hooks(self) -> None:
        """Attach the preview columns' scroll + resize callbacks.

        Pure DOM wiring — no tmux — so it runs unconditionally at mount.
        """
        try:
            scroll = self.query_one("#preview-scroll", PreviewScrollContainer)
            scroll.on_user_scroll = self._record_preview_scroll
        except Exception:
            pass
        try:
            shadow_scroll = self.query_one("#shadow-scroll", PreviewScrollContainer)
            shadow_scroll.on_user_scroll = self._record_shadow_scroll
        except Exception:
            pass
        try:
            row = self.query_one("#preview-row", PreviewRow)
            row.on_row_resize = self._schedule_shadow_fit_check
        except Exception:
            pass
        self._schedule_shadow_fit_check()

    async def on_unmount(self) -> None:
        # Clear our pane marker on the normal-exit path; an abnormal exit is
        # covered by monitor_marker_state's stale classification (t1451).
        if getattr(self, "_mark_pane", False):
            with contextlib.suppress(Exception):
                unmark_monitor_pane()
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
        """Record user scroll intent for the AGENT preview column."""
        self._record_scroll_for(Zone.PREVIEW)

    def _record_shadow_scroll(self) -> None:
        """Record user scroll intent for the SHADOW preview column (t1216_2)."""
        self._record_scroll_for(Zone.SHADOW)

    def _record_scroll_for(self, zone: Zone) -> None:
        """Record user scroll intent for one preview column.

        Called (via PreviewScrollContainer.call_after_refresh) once the user's
        mouse wheel / scrollbar drag / page click has committed scroll_y.
        Anchors by the text of the topmost visible line in the currently
        rendered content — stable against tmux's rolling capture.

        Parameterised over the column rather than duplicated (t1216_2): the two
        differ only in which scroller, state map, rendered-lines list and fast
        refresh they act on. Note the key differs in kind — the agent column is
        keyed by the FOLLOWED pane id, the shadow column by the SHADOW pane id.
        """
        if zone == Zone.SHADOW:
            key = self._current_shadow_pane_id()
            scroll_id = "#shadow-scroll"
            state = self._shadow_scroll_state
            rendered = self._shadow_rendered_lines
            refresh = self._fast_shadow_refresh
        else:
            key = self._focused_pane_id
            scroll_id = "#preview-scroll"
            state = self._preview_scroll_state
            rendered = self._preview_rendered_lines
            refresh = self._fast_preview_refresh

        if key is None:
            return
        try:
            scroll = self.query_one(scroll_id, PreviewScrollContainer)
        except Exception:
            return
        max_y = scroll.max_scroll_y
        scroll_y = scroll.scroll_y
        at_bottom = max_y <= 0 or scroll_y >= max_y - 1
        anchor_text: str | None = None
        if not at_bottom:
            idx = int(scroll_y)
            if 0 <= idx < len(rendered):
                anchor_text = rendered[idx]

        prev = state.get(key)
        was_detached = prev is not None and not prev[0]

        state[key] = (at_bottom, anchor_text)
        scroll.user_is_scrolling = False

        # Re-attach → pull a fresh snapshot so tail-follow resumes on latest output.
        if was_detached and at_bottom:
            self.call_later(refresh)

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

        # Two-phase capture (t1111_4): offload the strip/prompt-regex CPU work,
        # then commit under the monitor-owned generation guard. If a newer refresh
        # reserved a later generation while we were off-loop, discard this cycle —
        # skip the DOM rebuild entirely (the newer cycle owns it) and never write
        # stale content into _last_content / _snapshots.
        gen, classified = await self._monitor.capture_all_classified_async()
        if self._monitor.capture_generation != gen:
            return
        snaps = self._monitor.commit_snapshots(gen, classified)
        if snaps is None:
            return
        self._snapshots = snaps
        # Refresh the per-session project-root mapping so cross-session task
        # data resolves from the right project. Cheap — piggybacks on the
        # TmuxMonitor sessions cache TTL.
        session_roots = await self._monitor.get_session_to_project_mapping_async()
        self._task_cache.update_session_mapping(session_roots)
        # Prioritized marks (t1326): publish the SAME mapping to the mark code
        # (the async value — the render path must never make a sync tmux call;
        # see test_monitor_refresh_no_sync_tmux.py), then re-read the store.
        # The re-read is mtime-gated, so it is one os.stat when nothing changed,
        # and it is what makes a mark set in another repo appear within a tick.
        self._set_session_root_map(session_roots)
        self._refresh_marks()
        # Completed-pane set for THIS tick (t1322). Must run after
        # update_session_mapping (which may clear the task cache) and before
        # _maybe_auto_switch below, which filters on it.
        self._completed_pane_ids = self._compute_completed_panes()
        # NOTE: no per-tick gate-cache clear here — GateSummaryCache now
        # invalidates by task-file mtime/size, so a live-growing ledger
        # re-derives on the tick its file changes without re-reading unchanged
        # ledgers from disk every 3s.

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
        target_name = await self._consume_focus_request()
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
                    await self._clear_focus_request()
                    break

        # Auto-switch: if enabled and in pane list, move to most-idle agent
        if self._auto_switch and saved_zone == Zone.PANE_LIST:
            if self._maybe_auto_switch():
                saved_pane_id = self._focused_pane_id

        attached_session = None
        if self._monitor.multi_session:
            attached_session = await self._read_attached_session()
        self._rebuild_session_bar(attached_session)
        # Shadow reconciliation MUST run before the _restore_focus scheduling
        # below: it can change the active zone (grace fallback / selection
        # moved), and `saved_zone` was captured at the top of this method,
        # before that could happen. Handing the stale value to the deferred
        # restore would re-focus the shadow column and undo the fallback that
        # just fired (t1216_2).
        saved_zone = self._reconcile_shadow_state()
        # Cheap, synchronous and I/O-free: must run BEFORE the rebuild below so
        # the badge each card renders reflects this tick (t1216_3). The costly
        # half (authoritative capture + toast) is dispatched as a worker at the
        # end of this method instead, off the refresh cadence.
        self._scan_concern_signatures()

        pane_list_rebuilt = self._rebuild_pane_list()
        self._update_content_preview()
        self._update_shadow_preview()

        # Defer focus restoration until after Textual processes the DOM changes
        # from remove()/mount(). Immediate restore fails because removed widgets
        # haven't been fully detached yet.
        self.call_after_refresh(
            self._restore_focus, saved_pane_id, saved_zone, pane_list_rebuilt
        )

        # Concern verification + toast (t1216_3). A worker, so a stalled capture
        # cannot stretch the refresh interval — Textual awaits the timer callback
        # before scheduling the next one. Deliberately NOT exclusive=True:
        # cancelling would orphan capture_shadow_text's subprocess, which is
        # killed only on its own timeout. Re-entrancy is handled by _offer_busy,
        # so a slow pass is not restarted rather than killed mid-flight.
        self.run_worker(
            self._offer_concerns(), group="concerns", exit_on_error=False
        )

        # Materialize mark expiry / the liveness sweep at most every 10 min
        # (t1326). Last, so a slow writer can never delay the visible refresh.
        await self._maybe_purge_marks()

    async def _offer_concerns(self) -> None:
        """Toast the SELECTED agent once per verified block.

        Cost: at most ONE ``-J`` capture per (selected agent, newly-seen
        signature), plus the narrow-pane probe every other tick when a
        sub-sentinel-width shadow shows nothing. Never per tick in the steady
        state, and never scaling with N — the badge, which does scale, is free.

        The block is verified before toasting because ``concern_block_signature``
        requires a complete *fence* but not a parsed concern: an all-malformed
        block (the case t1274 exists for) would otherwise announce "Shadow raised
        concerns" and then report nothing forwardable on `c`.
        """
        if self._monitor is None or self._offer_busy:
            return
        self._offer_busy = True
        try:
            self._concern_tick += 1
            pane_id = self._focused_pane_id
            shadow_snap = (
                self._tick_shadow_snaps.get(pane_id) if pane_id else None
            )
            if shadow_snap is None:
                return
            seen = self._seen_concern_sigs(pane_id)
            sig = self._concern_sig_latest.get(pane_id)  # the TRIGGER — snapshot
            if sig is None:
                # Nothing detected. Only a sub-sentinel-width pane can HIDE a
                # block from the cheap detector (_SENTINEL_SAFE_COLS = 24: the
                # fences are 21 and 18 chars), so anything wider genuinely has
                # none and needs no subprocess.
                if shadow_snap.pane.width >= _SENTINEL_SAFE_COLS:
                    return
                if self._concern_tick % 2 == 0:
                    return  # probe every other tick
            elif sig in seen:
                return  # already picked, or already checked

            shadow_pane = shadow_snap.pane.pane_id
            text = await capture_shadow_text(shadow_pane)
            if text is None:
                return  # learned nothing; retry next tick
            captured_sig = concern_block_signature(text)
            if captured_sig is None:
                return  # no complete block in the -J window
            if sig is None:
                # Narrow-pane path: the probe is where the badge's signature
                # comes from, since the raw capture cannot see the fences.
                self._concern_sig_latest[pane_id] = captured_sig
            # Re-read AFTER the await: a concurrent `c` (its guard is independent
            # of _offer_busy) may have offered this block while we were suspended.
            if captured_sig in self._seen_concern_sigs(pane_id):
                return
            # Trigger passed EXPLICITLY from the snapshot above — re-reading it
            # here could store a NEWER block's signature and lose it.
            self._mark_concern_sig(
                self._concern_sig_examined, pane_id, sig, captured_sig
            )
            verified = frozenset(
                s for s in (sig, captured_sig) if s is not None
            )
            concerns = parse_concerns(text)
            if not concerns:
                # Malformed or empty block: no misleading toast. The badge
                # stands, and `c` gives the user the precise reason.
                return
            eps = max(2.0, float(getattr(self, "_refresh_seconds", 3)))
            stale, _ = await compute_shadow_staleness(
                self._monitor, shadow_pane, pane_id, eps
            )
            # Re-check AFTER the awaits: the toast is an unsolicited interruption
            # and must describe what is on screen NOW. The signature stays marked
            # examined (the check really did run) and the badge is untouched, so
            # nothing is lost when the popup is skipped.
            if self._focused_pane_id != pane_id:
                return
            still = self._monitor.get_shadow_snapshot(pane_id)
            if still is None or still.pane.pane_id != shadow_pane:
                return  # shadow died or was rebound while we captured
            # ...and the SAME pane may have moved on to a different block while
            # we were suspended. Identity is not freshness: toasting "raised N
            # concern(s)" for the block we verified would then disagree with both
            # the badge (which tracks the newer one) and the picker a keypress
            # later. Skip it — the newer block is not in `_examined`, so the next
            # pass verifies and announces it on its own terms.
            if self._concern_sig_latest.get(pane_id) not in verified:
                return
            actionable = sum(1 for c in concerns if needs_addressing(c))
            info = len(concerns) - actionable
            info_suffix = f" (+{info} informational)" if info else ""
            stale_suffix = " (⚠ STALE — agent moved on)" if stale else ""
            self.notify(
                f"Shadow raised {actionable} concern(s){info_suffix} — "
                f"press 'c' to pick" + stale_suffix
            )
        finally:
            self._offer_busy = False

    async def _fast_preview_refresh(self) -> None:
        """Lightweight refresh — only re-capture the focused pane for preview.

        Uses the same two-phase/generation discipline as the full refresh
        (t1111_4): the classify work is offloaded, and the focused pane id is
        **pinned before the await** so a focus change during the offload can't
        commit pane A's snapshot while the preview UI is updated for pane B.
        """
        if self._monitor is None:
            return
        pane_id = self._focused_pane_id
        if pane_id is None:
            return
        gen, pane, content, result = \
            await self._monitor.capture_pane_classified_async(pane_id)
        if pane is None:
            return
        if self._monitor.capture_generation != gen:
            return  # superseded by a newer capture → discard
        snap = self._monitor.commit_snapshot(gen, pane, content, result)
        if snap is None:
            return
        self._snapshots[pane_id] = snap  # write under the PINNED id
        if pane_id == self._focused_pane_id:  # focus-identity guard
            self._update_content_preview()

    async def _fast_shadow_refresh(self) -> None:
        """Lightweight refresh — only re-capture the selected agent's shadow.

        `refresh_shadow_snapshot` returns None for four distinct reasons (key
        absent — it never CREATES one; capture failed; stale write seq; shadow
        rebound to a different pane) and all four mean the same thing: **no
        update this tick**, never "shadow gone". The 3s full refresh owns
        deletion, and the SHADOW_ABSENT_GRACE_TICKS counter is driven from
        _refresh_data, not from here — so this must not hide or clear anything
        (t1216_1 rule 5).

        The followed pane id is pinned before the await, mirroring
        _fast_preview_refresh's focus-identity guard.
        """
        if self._monitor is None:
            return
        pane_id = self._focused_pane_id
        if pane_id is None:
            return
        snap = await self._monitor.refresh_shadow_snapshot(pane_id)
        if snap is None:
            return  # no update this tick
        if pane_id == self._focused_pane_id:  # focus-identity guard
            self._update_shadow_preview()

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

    async def _consume_focus_request(self) -> str | None:
        """Read the `AITASK_MONITOR_FOCUS_WINDOW` tmux session env var.

        Returns the target window name if set, or None. Does NOT clear the
        variable — use `_clear_focus_request()` after a successful match so
        that a startup race (target pane not yet in snapshot) can be retried
        on the next refresh tick.
        """
        if self._monitor is None:
            return None
        rc, stdout = await self._monitor.tmux_run_async([
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

    async def _clear_focus_request(self) -> None:
        """Unset the tmux session focus-request env var."""
        if self._monitor is None:
            return
        await self._monitor.tmux_run_async([
            "set-environment", "-t", tmux_session_target(self._session),
            "-u", "AITASK_MONITOR_FOCUS_WINDOW",
        ])

    def _agents_header_text(self, n_agents: int) -> str:
        """The CODE AGENTS section header, including the status legend.

        Built in one place because both the fast in-place path and the slow
        rebuild path in :meth:`_rebuild_pane_list` render this line; duplicating
        it once more would make the legend and the AUTO tag drift apart.
        """
        auto_label = "  [bold yellow]⟳ AUTO[/]" if self._auto_switch else ""
        legend = (
            "  [dim]([/][green]●[/][dim] active [/]"
            "[bold magenta]●[/][dim] prompt [/]"
            "[yellow]●[/][dim] idle [/]"
            f"[{STATE_STYLE_DONE}]●[/][dim] done)[/]"
        )
        return f"[bold]CODE AGENTS ({n_agents})[/]{auto_label}{legend}"

    def _compute_completed_panes(self) -> frozenset[str]:
        """Pane ids whose task is finished, for THIS refresh tick (t1322).

        One place, one pass: the card badge, the session bar's `done` counter
        and the auto-switch filter must agree within a tick, and only a single
        precomputed set guarantees that. This is also the only site that pays
        the per-pane ``os.stat`` freshness check — every later ``get_task_info``
        on the same tick hits a warm entry.
        """
        done: set[str] = set()
        for pane_id, snap in self._snapshots.items():
            if snap.pane.category != PaneCategory.AGENT:
                continue
            task_id = self._task_cache.get_task_id_for_pane(snap.pane)
            if not task_id:
                continue
            if is_task_completed(
                self._task_cache.get_task_info(task_id, snap.pane.session_name)
            ):
                done.add(pane_id)
        return frozenset(done)

    def _maybe_auto_switch(self) -> bool:
        """Switch focus to a pane that needs attention if the current is active.

        Priority: awaiting_input > is_idle. Awaiting panes are surfaced first
        because they are blocked on user input — no idle-threshold wait
        required.

        Completed panes (t1322) are excluded from every branch. A finished agent
        is idle forever and, sorted by ``idle_seconds`` descending, would
        otherwise permanently capture focus — parking the monitor on a done
        agent and never surfacing a live one that needs input.

        Returns True if focus was switched, False otherwise.
        """
        if self._focused_pane_id is None:
            return False
        current_snap = self._snapshots.get(self._focused_pane_id)
        if current_snap is None or current_snap.pane.category != PaneCategory.AGENT:
            return False
        # If focused agent already needs attention, keep it — unless it is
        # merely *completed*-idle, which needs no attention at all.
        if (
            getattr(current_snap, "awaiting_input", False)
            or (
                current_snap.is_idle
                and self._focused_pane_id not in self._completed_pane_ids
            )
        ):
            return False
        # Prefer awaiting-input panes over idle ones — they need attention
        # more urgently (blocked on a prompt).
        awaiting = [
            snap for snap in self._snapshots.values()
            if snap.pane.category == PaneCategory.AGENT
            and getattr(snap, "awaiting_input", False)
        ]
        if awaiting:
            awaiting.sort(key=lambda s: s.idle_seconds, reverse=True)
            self._focused_pane_id = awaiting[0].pane.pane_id
            return True
        # Find idle agents, sorted by most idle first
        idle_agents = [
            snap for snap in self._snapshots.values()
            if snap.pane.category == PaneCategory.AGENT and snap.is_idle
            and snap.pane.pane_id not in self._completed_pane_ids
        ]
        if not idle_agents:
            return False
        idle_agents.sort(key=lambda s: s.idle_seconds, reverse=True)
        self._focused_pane_id = idle_agents[0].pane.pane_id
        return True

    def _restore_focus(
        self, pane_id: str | None, zone: Zone, pane_list_rebuilt: bool = True
    ) -> None:
        """Re-focus the previously focused widget after a rebuild."""
        if zone == Zone.PREVIEW:
            try:
                self.query_one("#content-preview", PreviewPanel).focus()
            except Exception:
                pass
            self._update_content_preview()
            self._update_shadow_preview()
            if pane_list_rebuilt:
                self._update_selected_card_indicator(full=True)
            return
        # Without this branch SHADOW would fall through to the PaneCard path
        # below, whose card.focus() fires on_descendant_focus → Zone.PANE_LIST —
        # ejecting the user from the shadow column on EVERY 3s refresh and
        # silently ending shadow key targeting (t1216_2).
        if zone == Zone.SHADOW:
            # Re-validate: this restore was QUEUED before the deferred
            # visibility check ran, so the column may have been hidden (or the
            # shadow may have vanished) in between. Re-focusing it then would
            # resurrect a zone that was just left — and, because focusing the
            # column re-enters it, would reset the absent-grace counter on
            # every tick so the grace window could never expire.
            # Validate on the COLUMN being shown, not on a snapshot existing:
            # during the grace hold the snapshot is absent but the column is
            # still up rendering the placeholder, and focus must stay there.
            if self._shadow_split_ok:
                try:
                    self.query_one("#shadow-preview", PreviewPanel).focus()
                except Exception:
                    pass
            else:
                self._active_zone = Zone.PREVIEW
                self._active_preview_zone = Zone.PREVIEW
                try:
                    self.query_one("#content-preview", PreviewPanel).focus()
                except Exception:
                    pass
            self._update_content_preview()
            self._update_shadow_preview()
            if pane_list_rebuilt:
                self._update_selected_card_indicator(full=True)
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
            card = self._pane_cards.get(pane_id)
            if card is not None:
                card.focus()
                # Widget.focus() is deferred; on_descendant_focus may not
                # fire before the next refresh tick, leaving saved_pane_id
                # stale. Set _focused_pane_id directly so the next tick sees
                # the real state.
                self._focused_pane_id = card.pane_id
        # Sync preview with the final focus state. The _update_content_preview
        # call in _refresh_data (line 683) may have rendered with a stale
        # _focused_pane_id if DOM events during _rebuild_pane_list shifted
        # focus. This second call corrects the preview. On the fast path it's
        # cheap (same_pane check short-circuits). Fixes t576.
        self._update_content_preview()
        # Same for the shadow column: _focused_pane_id may have changed just
        # above, and the shadow shown is derived from it.
        self._update_shadow_preview()
        # Re-apply the .selected class to the freshly-mounted card whose
        # pane_id matches _focused_pane_id (cards were destroyed by the
        # rebuild). Required so the preview-zone indicator survives ticks.
        if pane_list_rebuilt:
            self._update_selected_card_indicator(full=True)

    def _switcher_selected_session(self) -> str | None:
        """Pre-select the focused agent pane's session in the TUI switcher.

        When the focused row is a code-agent card belonging to a non-attached
        tmux session, the switcher opens with that session already selected
        — saving the user a Left/Right cycle (t836). Non-agent rows fall
        through to the default attached-session behavior.
        """
        pid = self._focused_pane_id
        if not pid:
            return None
        snap = self._snapshots.get(pid)
        if snap is None or snap.pane.category != PaneCategory.AGENT:
            return None
        return snap.pane.session_name or None

    def _rebuild_session_bar(self, attached_session: str | None = None) -> None:
        total = len(self._snapshots)
        agents = [
            s for s in self._snapshots.values()
            if s.pane.category == PaneCategory.AGENT
        ]
        # The three counters partition the agents exactly as the badges do, on
        # the same PROMPT > COMPLETED > IDLE ladder (t1322), so every agent
        # lands in at most one bucket and the bar can never disagree with the
        # rows above it. Subtracting completed from idle alone would not be
        # enough: a completed agent parked on its final feedback prompt is both
        # awaiting and completed, and would be counted twice while its badge
        # read PROMPT.
        awaiting_count = sum(1 for a in agents if getattr(a, "awaiting_input", False))
        done_count = sum(1 for a in agents
                         if a.pane.pane_id in self._completed_pane_ids
                         and not getattr(a, "awaiting_input", False))
        idle_count = sum(1 for a in agents
                         if a.is_idle and not getattr(a, "awaiting_input", False)
                         and a.pane.pane_id not in self._completed_pane_ids)
        awaiting_str = f"  [bold magenta]{awaiting_count} awaiting[/]" if awaiting_count > 0 else ""
        done_str = f"  [{STATE_STYLE_DONE}]{done_count} done[/]" if done_count > 0 else ""
        idle_str = f"  [yellow]{idle_count} idle[/]" if idle_count > 0 else ""
        bar = self.query_one("#session-bar", SessionBar)
        auto_tag = "  [bold yellow][AUTO][/]" if self._auto_switch else ""
        try:
            desync = _get_desync_summary(Path.cwd(), compact=False)
        except Exception:
            desync = ""
        # Surface the control-channel state only when it is *not* the
        # steady-state CONNECTED — keep the bar quiet during normal use.
        state_badge = ""
        if self._monitor is not None:
            s = self._monitor.control_state()
            if s == TmuxControlState.RECONNECTING:
                state_badge = "  [yellow]control: reconnecting[/]"
            elif s == TmuxControlState.FALLBACK:
                state_badge = "  [red]control: fallback[/]"
        if self._monitor is not None and self._monitor.multi_session:
            sessions = {
                s.pane.session_name for s in self._snapshots.values()
                if s.pane.session_name
            }
            attached = attached_session or self._session
            session_word = "session" if len(sessions) == 1 else "sessions"
            pane_word = "pane" if total == 1 else "panes"
            bar.update(
                f"tmux Monitor — {len(sessions)} {session_word} "
                f"· {total} {pane_word} · multi "
                f"(attached: {attached})"
                f"{awaiting_str}"
                f"{done_str}"
                f"{idle_str}"
                f"{auto_tag}"
                f"{desync}"
                f"{state_badge}"
                f"  [dim]Tab: switch panel[/]"
            )
        else:
            bar.update(
                f"tmux Monitor — session: {self._session} "
                f"({total} pane{'s' if total != 1 else ''})"
                f"{awaiting_str}"
                f"{done_str}"
                f"{idle_str}"
                f"{auto_tag}"
                f"{desync}"
                f"{state_badge}"
                f"  [dim]Tab: switch panel[/]"
            )

    async def _read_attached_session(self) -> str | None:
        """Return the currently-attached tmux session name, or None on failure."""
        if self._monitor is None:
            return None
        rc, stdout = await self._monitor.tmux_run_async(["display-message", "-p", "#S"])
        if rc != 0:
            return None
        return stdout.strip() or None

    def _format_agent_card_text(self, snap: PaneSnapshot) -> str:
        # Membership in the per-tick set is the SOLE source of the completed
        # flag (t1322). The `info` lookup further down may supply the title and
        # gate summary, but must never re-derive completion: an archive landing
        # between _compute_completed_panes and this call would flip the identity
        # gate and leave the badge disagreeing with the session bar and the
        # auto-switch decision for a tick.
        completed = snap.pane.pane_id in self._completed_pane_ids
        dot = format_state_dot(snap, completed)
        status = format_pane_status(snap, completed)
        if self._monitor is not None:
            mode = self._monitor.get_compare_mode(snap.pane.pane_id)
            is_override = self._monitor.is_compare_mode_overridden(snap.pane.pane_id)
            shadow_snap = self._monitor.get_shadow_snapshot(snap.pane.pane_id)
        else:
            mode = "stripped"
            is_override = False
            shadow_snap = None
        glyph = format_compare_mode_glyph(mode, is_override)
        # Shadow-status glyph (t1133): second colored glyph right after the
        # agent's own dot when a shadow agent is bound to this pane; empty
        # string (no placeholder) keeps non-shadowed rows unchanged.
        #
        # The concern marker (t1216_3) rides on the same glyph. It is derived
        # here for EVERY agent — that is what makes the N-agent case work: each
        # shadow with an un-offered block is marked at zero tmux cost, while the
        # toast fires only for the selected one.
        shadow = format_shadow_glyph(
            shadow_snap, has_concerns=self._has_fresh_concerns(snap.pane.pane_id)
        )
        shadow_part = f" {shadow}" if shadow else ""
        # Leftmost: the prioritized mark (t1326) is a durable user annotation,
        # deliberately outside the live state cluster. Always-on ★/☆ pair, so
        # rows never shift when one is toggled.
        mark = format_mark_glyph(self._is_marked(snap))
        text = (
            f" {mark} {dot}{shadow_part} {glyph} "
            f"{snap.pane.window_index}:{snap.pane.window_name} "
            f"({snap.pane.pane_index})  {status}"
        )
        task_id = self._task_cache.get_task_id_for_pane(snap.pane)
        if task_id:
            info = self._task_cache.get_task_info(task_id, snap.pane.session_name)
            if info:
                # Gate summary sits at the END of the status row (row 1), after
                # the status, rather than on its own line — keeps the card
                # compact in the full monitor. (Minimonitor keeps it on a
                # separate line; its rows are too narrow to append here.)
                gates = self._gate_cache.summary_for(info)
                if gates:
                    text += f"  [dim]gates: {gates}[/]"
                # Advisory workflow phase (t1420) — a hint beside the gate
                # counts, never a gate on anything. Composed per tick because
                # its live half tracks the pane, not the file.
                signal = self._gate_cache.phase_for(
                    info,
                    screen_text=snap.content,
                    awaiting_input=snap.awaiting_input,
                    awaiting_input_kind=snap.awaiting_input_kind,
                    agent=workflow_phase.agent_key_from_command(
                        snap.pane.current_command),
                )
                phase = workflow_phase.render_phase(signal)
                if phase:
                    text += f"  [dim]{phase}[/]"
                # Re-stamp the bound shadow from the SAME signal. The full
                # monitor spawns shadows too, so without this its shadows would
                # keep their launch-time value forever (t1420). Best-effort:
                # `refresh_shadow_phase_stamp` swallows every failure, so an
                # advisory hint can never disturb the card render.
                if shadow_snap is not None and self._monitor is not None:
                    refresh_shadow_phase_stamp(
                        self._monitor, shadow_snap.pane.pane_id, signal)
                text += f"\n     [dim italic]t{task_id}: {info.title}[/]"
        return text

    def _format_other_card_text(self, snap: PaneSnapshot) -> str:
        return (
            f" [dim]\u25cb[/] {snap.pane.window_index}:{snap.pane.window_name} "
            f"({snap.pane.pane_index})  [dim]{snap.pane.current_command}[/]"
        )

    def _rebuild_pane_list(self) -> bool:
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
                headers[0].update(self._agents_header_text(len(agents)))
            by_id = {c.pane_id: c for c in current_cards}
            self._pane_cards = by_id
            for snap in agents:
                by_id[snap.pane.pane_id].update(
                    self._format_agent_card_text(snap)
                )
            for snap in others:
                by_id[snap.pane.pane_id].update(
                    self._format_other_card_text(snap)
                )
            return False

        # Slow path (structural change): full rebuild. Arrow loss in this
        # window is tolerable because the pane set actually changed.
        self._pane_cards = {}
        self._selected_card_pane_id = None
        for widget in list(container.children):
            widget.remove()

        def mount_with_session_dividers(snaps, card_fn):
            """Mount PaneCards with a session divider before each new group.

            In multi mode, emits a `── sess_name ──` divider before the first
            card of each session so users can see at a glance which agents
            belong to which session, while still keeping the unified
            single-list ordering. The style comes from
            `monitor_shared.format_session_divider`; only the two-column indent
            belongs to this call site.
            """
            current_session = None
            for snap in snaps:
                sess = snap.pane.session_name
                if multi_mode and sess != current_session:
                    current_session = sess
                    label = sess or "?"
                    container.mount(Static(
                        f"  {format_session_divider(label)}",
                        classes="session-divider",
                    ))
                card = PaneCard(snap.pane.pane_id, card_fn(snap))
                container.mount(card)
                self._pane_cards[card.pane_id] = card

        if agents:
            container.mount(Static(
                self._agents_header_text(len(agents)),
                classes="section-header",
            ))
            mount_with_session_dividers(agents, self._format_agent_card_text)

        if others:
            container.mount(Static(
                f"[bold]OTHER ({len(others)})[/]",
                classes="section-header",
            ))
            mount_with_session_dividers(others, self._format_other_card_text)
        return True

    def _update_content_preview(self) -> None:
        try:
            preview = self.query_one("#content-preview", PreviewPanel)
            header = self.query_one("#content-header", Static)
            scroll = self.query_one("#preview-scroll", PreviewScrollContainer)
        except Exception:
            return

        # Any (re)entry supersedes an in-flight offloaded render (t1111_5): bump
        # the render token UP FRONT so a pending _apply_preview_render scheduled by
        # an earlier call can no longer apply — whether this call renders fresh
        # content, clears to (empty)/prompt, or intentionally freezes the current
        # view. Branches that decide "do not render" must still invalidate a stale
        # render (e.g. an empty/no-focus/frozen re-entry must not be overwritten by
        # a slow render for the same pane that was scheduled a moment earlier), so
        # the bump lives here rather than only at schedule time. The render branch
        # reuses `my_gen` instead of bumping again.
        self._preview_render_gen += 1
        my_gen = self._preview_render_gen

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
        task_id = self._task_cache.get_task_id_for_pane(snap.pane)
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

        # -- Active branch: offload the render, apply + restore scroll on the loop --
        # Only _ansi_to_rich_text (Text.from_ansi + per-line regex) is CPU-heavy and
        # pure, so it is offloaded (t1111_5). Everything cheap/stateful stays here on
        # the loop: min_width, the rendered-lines bookkeeping (drives scroll-anchor
        # save), and _last_preview_pane_id (drives same_pane) are set synchronously
        # from the snapshot — not from the render — so their semantics stay correct
        # immediately. preview.update(text) + scroll restore are deferred into the
        # worker (see _apply_preview_render).
        lines = snap.content.rstrip().splitlines()
        if lines:
            preview.styles.min_width = snap.pane.width
            self._preview_rendered_lines = lines
            # my_gen was reserved at the top of this method (every entry bumps it).
            pane_id = self._focused_pane_id
            if not same_pane:
                # Pane actually switched: clear pane-A's stale body NOW so the
                # already-updated header for pane B never sits above pane A's
                # content while the offloaded render is in flight. Same-pane
                # re-renders (0.3s fast-preview tick) skip this to avoid flicker.
                preview.update("[dim]…[/]")
            self.run_worker(
                self._apply_preview_render(
                    pane_id, "\n".join(lines), my_gen, saved, lines
                ),
                exclusive=True, group="preview", exit_on_error=False,
            )
        else:
            preview.styles.min_width = 0
            preview.update("[dim](empty)[/]")
            self._preview_rendered_lines = []

        self._last_preview_pane_id = self._focused_pane_id

    async def _apply_preview_render(self, pane_id, joined, my_gen, saved, lines) -> None:
        """Offloaded preview render + guarded application (t1111_5).

        Runs the pure, CPU-heavy `_ansi_to_rich_text` off the UI thread via the
        TmuxMonitor `_run_offloaded` seam (established in t1111_4), then applies
        `preview.update` + scroll restore back on the loop — but only if this
        render is still the current one (`_preview_render_gen`) AND focus has not
        moved to another pane. A late / superseded render never overwrites the
        preview; a stale scroll restore never lands on another pane's shared
        scroll container.
        """
        if self._monitor is None:
            return
        # Superseded while still queued (rapid arrow-nav): don't even launch the
        # thread. `run_worker(exclusive=True)` cancels the coroutine, but the
        # asyncio.to_thread work is not cancellable — this check is what avoids
        # a doomed render; the generation guard below is what enforces correctness.
        if my_gen != self._preview_render_gen:
            return
        try:
            text = await self._monitor._run_offloaded(
                lambda: _ansi_to_rich_text(joined)
            )
        except Exception:
            # Fail closed: a raising from_ansi degrades to raw text, never crashes
            # the loop.
            text = Text(joined)

        # Back on the loop after the await:
        if my_gen != self._preview_render_gen:
            return  # superseded by a newer render → discard
        if pane_id != self._focused_pane_id:
            return  # focus moved during the offload → don't write B's preview
        try:
            preview = self.query_one("#content-preview", PreviewPanel)
            scroll = self.query_one("#preview-scroll", PreviewScrollContainer)
        except Exception:
            return

        preview.update(text)

        # Scroll restore AFTER preview.update. The deferred call_after_refresh
        # callbacks fire on a later refresh cycle, by which point focus may have
        # moved again and `scroll` is a SHARED container — so each re-checks the
        # generation + focused pane at execution time before touching scroll.
        def _guarded(action, g=my_gen, p=pane_id):
            if g == self._preview_render_gen and p == self._focused_pane_id:
                action()

        if saved is None or saved[0]:
            # Tail follow (first view of this pane or at-bottom).
            self.call_after_refresh(
                lambda: _guarded(lambda: scroll.scroll_end(animate=False))
            )
        else:
            anchor_text = saved[1]
            target_idx = self._locate_anchor(lines, anchor_text)
            if target_idx is None:
                # Anchor rolled off the capture buffer — snap to tail so we don't
                # get stuck on a stale position on pane-return.
                self.call_after_refresh(
                    lambda: _guarded(lambda: scroll.scroll_end(animate=False))
                )
            else:
                target_f = float(target_idx)
                self.call_after_refresh(
                    lambda t=target_f: _guarded(
                        lambda: scroll.scroll_to(y=t, animate=False)
                    )
                )

    # -- Shadow column rendering (t1216_2) -------------------------------------

    def _update_shadow_preview(self) -> None:
        """Render the SHADOW column for the selected agent's bound shadow.

        Mirrors _update_content_preview but with its OWN render generation and
        worker group: sharing either would let the two columns cancel or clobber
        each other's renders.
        """
        try:
            preview = self.query_one("#shadow-preview", PreviewPanel)
            header = self.query_one("#shadow-header", Static)
            scroll = self.query_one("#shadow-scroll", PreviewScrollContainer)
        except Exception:
            return

        # Bump UP FRONT on EVERY entry — including the absent / frozen / empty
        # branches — so a slow in-flight render can never clobber a newer state
        # (same discipline as _update_content_preview, t1111_5).
        self._shadow_render_gen += 1
        my_gen = self._shadow_render_gen

        snap = None
        if self._focused_pane_id and self._monitor is not None:
            snap = self._monitor.get_shadow_snapshot(self._focused_pane_id)

        if snap is None:
            # The zone may still be HELD here during the grace window (see
            # _reconcile_shadow_state), so show a placeholder rather than
            # anything that could be mistaken for live shadow output.
            header.update("[bold]Shadow[/]")
            preview.styles.min_width = 0
            preview.update("[dim](shadow unavailable)[/]")
            self._shadow_rendered_lines = []
            self._last_shadow_pane_id = None
            return

        shadow_pane_id = snap.pane.pane_id
        saved = self._shadow_scroll_state.get(shadow_pane_id)
        is_paused = saved is not None and not saved[0]
        same_pane = (shadow_pane_id == self._last_shadow_pane_id)

        label = f"({shadow_pane_id} ← {self._focused_pane_id})"
        if is_paused:
            tag = " [bold yellow]PAUSED[/]"
        elif self._active_zone == Zone.SHADOW:
            tag = " [bold green]LIVE[/]"
        else:
            tag = ""
        if self._active_zone == Zone.SHADOW:
            header.update(f"[bold white]Shadow[/] {label}{tag}")
        else:
            header.update(f"[bold]Shadow[/] {label}{tag}")

        # Frozen branch: same shadow pane AND (user detached OR scroll in flight).
        if same_pane and (is_paused or scroll.user_is_scrolling):
            self._last_shadow_pane_id = shadow_pane_id
            return

        lines = snap.content.rstrip().splitlines()
        if lines:
            # Size the panel to the REAL shadow pane width so its content
            # renders unwrapped (mirrors the agent preview).
            preview.styles.min_width = snap.pane.width
            self._shadow_rendered_lines = lines
            if not same_pane:
                preview.update("[dim]…[/]")
            self.run_worker(
                self._apply_shadow_render(
                    shadow_pane_id, "\n".join(lines), my_gen, saved, lines
                ),
                exclusive=True, group="shadow-preview", exit_on_error=False,
            )
        else:
            preview.styles.min_width = 0
            preview.update("[dim](empty)[/]")
            self._shadow_rendered_lines = []

        self._last_shadow_pane_id = shadow_pane_id

    async def _apply_shadow_render(
        self, shadow_pane_id, joined, my_gen, saved, lines
    ) -> None:
        """Offloaded shadow render + guarded application.

        Mirrors _apply_preview_render, but the identity guard compares against
        the CURRENT shadow pane (the selection may have moved to another agent,
        or the shadow may have been rebound) rather than the focused agent.
        """
        if self._monitor is None:
            return
        if my_gen != self._shadow_render_gen:
            return
        try:
            text = await self._monitor._run_offloaded(
                lambda: _ansi_to_rich_text(joined)
            )
        except Exception:
            text = Text(joined)

        if my_gen != self._shadow_render_gen:
            return  # superseded by a newer render → discard
        if shadow_pane_id != self._current_shadow_pane_id():
            return  # selection moved / shadow rebound during the offload
        try:
            preview = self.query_one("#shadow-preview", PreviewPanel)
            scroll = self.query_one("#shadow-scroll", PreviewScrollContainer)
        except Exception:
            return

        preview.update(text)

        def _guarded(action, g=my_gen, p=shadow_pane_id):
            if g == self._shadow_render_gen and p == self._current_shadow_pane_id():
                action()

        if saved is None or saved[0]:
            self.call_after_refresh(
                lambda: _guarded(lambda: scroll.scroll_end(animate=False))
            )
        else:
            target_idx = self._locate_anchor(lines, saved[1])
            if target_idx is None:
                self.call_after_refresh(
                    lambda: _guarded(lambda: scroll.scroll_end(animate=False))
                )
            else:
                target_f = float(target_idx)
                self.call_after_refresh(
                    lambda t=target_f: _guarded(
                        lambda: scroll.scroll_to(y=t, animate=False)
                    )
                )

    # -- Zone navigation -------------------------------------------------------

    # -- Shadow concern helpers (t1216_3) --------------------------------------

    @staticmethod
    def _mark_concern_sig(
        store: dict[str, frozenset[str]],
        pane_id: str,
        trigger_sig: str | None,
        captured_sig: str,
    ) -> None:
        """Record BOTH the raw trigger signature and the -J captured one.

        They are digests of the same block taken through different capture paths
        (the tick's ``-p -e`` vs the picker's ``-J``), and
        ``concern_block_signature``'s documented mid-word-wrap residual makes
        them differ systematically whenever the block wraps mid-word. Storing
        only one leaves the next tick's raw signature unmatched — which
        re-captures every tick for ``_concern_sig_examined``, and never clears
        the badge for ``_concern_sig_offered``. Bounded at two entries: a new
        block replaces the pair.

        ``trigger_sig`` is a PARAMETER, never read from ``_concern_sig_latest``
        here: callers snapshot it BEFORE their capture await, and the 3s tick can
        replace it with a NEWER block's signature meanwhile. Reading it at write
        time would mark that newer block as already examined/offered and lose it
        silently. Static for the same reason — there is no instance state to
        reach for.
        """
        store[pane_id] = frozenset(
            s for s in (trigger_sig, captured_sig) if s is not None
        )

    def _seen_concern_sigs(self, followed_pane_id: str) -> frozenset[str]:
        """Signatures already picked OR already authoritatively checked."""
        return self._concern_sig_offered.get(
            followed_pane_id, frozenset()
        ) | self._concern_sig_examined.get(followed_pane_id, frozenset())

    def _scan_concern_signatures(self) -> None:
        """Refresh the per-agent concern signatures from data the tick already has.

        Zero tmux traffic: ``shadow_snap.content`` came from the same async
        gather that captured the agents. This is a TRIGGER, never a parse — the
        picker re-captures with ``-J`` (concern_parser's third strictness tier).
        """
        prev = self._concern_sig_latest
        latest: dict[str, str] = {}
        for followed, snap in self._tick_shadow_snaps.items():
            sig = concern_block_signature(snap.content)
            if sig is None and snap.pane.width < _SENTINEL_SAFE_COLS:
                # Below _SENTINEL_SAFE_COLS the fences themselves can wrap, so
                # "no signature" is uninformative, not evidence of absence. Carry
                # forward whatever the Step-5 probe last established — rebuilding
                # wholesale here would clear the probe's value every tick and
                # make a narrow-pane badge flicker on and off. For a WIDE pane
                # absence IS evidence, so it drops (the "scrolls out" case).
                sig = prev.get(followed)
            if sig is not None:
                latest[followed] = sig
        self._concern_sig_latest = latest
        # Evict ONLY when the agent itself is gone: a shadow that died and one
        # whose capture blipped are indistinguishable here, and evicting on that
        # would re-offer an identical block when the shadow respawns.
        #
        # Iterate the UNION of both maps: an agent whose block verified to
        # nothing forwardable has an `_examined` entry and NO `_offered` one
        # (the offer pass returns before marking it offered), so a loop over
        # `_concern_sig_offered` alone would never visit it and its entry would
        # outlive the agent for the rest of the session.
        for pid in set(self._concern_sig_offered) | set(self._concern_sig_examined):
            if pid not in self._snapshots:
                self._concern_sig_offered.pop(pid, None)
                self._concern_sig_examined.pop(pid, None)

    def _has_fresh_concerns(self, followed_pane_id: str) -> bool:
        """True when this agent's shadow has a block the user has not been
        offered — the card badge. Derived every render, never a latched flag."""
        sig = self._concern_sig_latest.get(followed_pane_id)
        if sig is None:
            return False
        # Membership, not equality: the on-screen digest and the stored -J one
        # are the same block through different capture paths (see
        # _mark_concern_sig), so `!=` would leave the badge stuck on forever
        # after a successful pick.
        return sig not in self._concern_sig_offered.get(
            followed_pane_id, frozenset()
        )

    # -- Shadow column helpers (t1216_2) ---------------------------------------

    def _current_shadow_pane_id(self) -> str | None:
        """Shadow pane bound to the SELECTED agent, or None.

        Resolves from ``self._focused_pane_id`` — never ``_get_focused_pane_id()``,
        which reads ``self.focused`` and returns None whenever focus is off a
        PaneCard, i.e. always while a preview zone is active.

        Answers *"is there a shadow to **read**"* (preview, key forwarding,
        concern picker) from the cached snapshots, where lagging a tick is the
        intended cheapness. It does **not** answer *"may I **create** one"*: the
        cache cannot report a shadow it has not observed yet, so the launch guards
        use the live ``find_shadow_pane_status`` lookup instead (t1216_4).
        """
        if not self._focused_pane_id or self._monitor is None:
            return None
        snap = self._monitor.get_shadow_snapshot(self._focused_pane_id)
        return None if snap is None else snap.pane.pane_id

    def _shadow_visibility_width(self) -> int | None:
        """Width the shadow column should occupy, or None to hide it.

        **Single source of truth** for every caller of
        `_apply_shadow_visibility` — the 3s reconcile and the resize-driven fit
        check. Deriving this in two places is a live bug: while the SHADOW zone
        HOLDS a momentarily-absent snapshot, a caller that resolved `None`
        instead of the last known width would hide the column and trigger
        `_leave_shadow_zone`, collapsing the grace window to whenever the user
        happens to resize the terminal.
        """
        snap = None
        if self._focused_pane_id and self._monitor is not None:
            snap = self._monitor.get_shadow_snapshot(self._focused_pane_id)
        if snap is not None:
            self._last_shadow_width = snap.pane.width
            return snap.pane.width
        if self._active_zone == Zone.SHADOW:
            return self._last_shadow_width  # holding: keep the column up
        return None

    def _shadow_split_fits(self, shadow_width: int) -> bool:
        """Whether the side-by-side split leaves the agent column usable.

        Decided on the mounted row's usable content width, NOT self.size.width:
        the screen width ignores #content-section's border, the stable
        scrollbar gutters and padding, and at the boundary that error is
        several columns. content_region is only meaningful post-layout, so
        every caller schedules this via call_after_refresh.
        """
        try:
            row = self.query_one("#preview-row")
        except Exception:
            return False  # not mounted yet — no split
        avail = row.content_region.width
        return (avail - (shadow_width + 1)) >= SHADOW_MIN_AGENT_COLS

    def _apply_shadow_visibility(self, shadow_width: int | None) -> None:
        """Show/size or hide #shadow-col. Runs post-layout (call_after_refresh).

        `shadow_width` is None when no shadow is bound. Also resets the tail
        target when the column is not usable, so `t` can never aim at a hidden
        column.
        """
        try:
            col = self.query_one("#shadow-col")
            preview = self.query_one("#shadow-preview", PreviewPanel)
        except Exception:
            return
        fits = shadow_width is not None and self._shadow_split_fits(shadow_width)
        self._shadow_split_ok = fits
        if fits:
            # +1 for the stable scrollbar gutter.
            col.styles.width = shadow_width + 1
            preview.styles.min_width = shadow_width
            col.display = True
        else:
            col.display = False
            if self._active_preview_zone == Zone.SHADOW:
                self._active_preview_zone = Zone.PREVIEW
            if self._active_zone == Zone.SHADOW:
                self._leave_shadow_zone("Shadow column hidden — too narrow")

    def _reconcile_shadow_state(self) -> Zone:
        """Full-refresh owner of shadow visibility, the grace counter and the
        SHADOW-zone exit. Returns the (possibly changed) active zone.

        The 0.3s tick only runs while SHADOW is FOCUSED, but the column is
        visible whenever a shadow is bound — so the 3s refresh has to own all of
        this or the column goes stale (or keeps showing the previous agent's
        shadow) whenever focus sits in the pane list.

        Two causes of an absent snapshot are indistinguishable here — the shadow
        pane died, or a single capture failed — so the grace window covers both.
        A selection change is different: it IS unambiguous (we never had a
        snapshot for the newly selected agent), so it exits immediately.

        Returns the zone so _refresh_data can rebind its `saved_zone` local
        before handing it to the deferred _restore_focus — otherwise the restore
        would re-focus the shadow column and UNDO the fallback just applied.
        """
        snap = None
        if self._focused_pane_id and self._monitor is not None:
            snap = self._monitor.get_shadow_snapshot(self._focused_pane_id)

        if self._active_zone == Zone.SHADOW:
            moved = (
                self._shadow_zone_agent_id is not None
                and self._focused_pane_id != self._shadow_zone_agent_id
            )
            if moved and snap is None:
                # Unambiguous: we never had a snapshot for the newly selected
                # agent, so this is not a blip. Leave at once rather than
                # sitting on a placeholder for the whole grace window.
                self._leave_shadow_zone("Agent has no shadow — back to the preview")
            elif moved:
                # Follow the selection onto the new agent's shadow.
                self._shadow_zone_agent_id = self._focused_pane_id
                self._shadow_absent_ticks = 0
            elif snap is not None:
                self._shadow_absent_ticks = 0
            else:
                self._shadow_absent_ticks += 1
                if self._shadow_absent_ticks >= SHADOW_ABSENT_GRACE_TICKS:
                    self._leave_shadow_zone(
                        "Shadow gone — back to the agent preview"
                    )
        else:
            self._shadow_absent_ticks = 0

        # Visibility/width must be measured post-layout. Derived by the shared
        # helper (never inline) so this path and the resize-driven fit check
        # cannot disagree about the hold case.
        self._schedule_shadow_fit_check()

        # Drop scroll state for shadow panes that no longer exist. The same walk
        # publishes _tick_shadow_snaps: this is the ONE place per tick that
        # resolves every agent's shadow, and the concern scan consumes it rather
        # than repeating the lookup (t1216_3).
        live_shadow_ids = set()
        tick_shadows: dict[str, PaneSnapshot] = {}
        if self._monitor is not None:
            for followed in list(self._snapshots):
                s = self._monitor.get_shadow_snapshot(followed)
                if s is not None:
                    live_shadow_ids.add(s.pane.pane_id)
                    tick_shadows[followed] = s
        self._tick_shadow_snaps = tick_shadows
        for pid in [p for p in self._shadow_scroll_state if p not in live_shadow_ids]:
            del self._shadow_scroll_state[pid]
        if (
            self._last_shadow_pane_id is not None
            and self._last_shadow_pane_id not in live_shadow_ids
        ):
            self._last_shadow_pane_id = None

        return self._active_zone

    def _zone_available(self, zone: Zone) -> bool:
        """Whether `zone` can currently be entered.

        Only SHADOW is conditional — it needs a bound shadow for the selected
        agent AND the split to fit — so Tab behaves exactly as before for
        agents with no shadow.
        """
        if zone != Zone.SHADOW:
            return True
        return self._current_shadow_pane_id() is not None and self._shadow_split_ok

    def _enter_shadow_zone(self) -> None:
        """Bind the SHADOW zone to the currently selected agent.

        Idempotent for the SAME agent. This matters: _restore_focus re-focuses
        #shadow-preview on every full refresh, which fires on_descendant_focus
        and lands here — resetting the absent-grace counter unconditionally
        would mean it could NEVER reach SHADOW_ABSENT_GRACE_TICKS and the zone
        would hold a dead shadow forever.
        """
        if self._shadow_zone_agent_id != self._focused_pane_id:
            self._shadow_zone_agent_id = self._focused_pane_id
            self._shadow_absent_ticks = 0
        self._active_preview_zone = Zone.SHADOW

    def _leave_shadow_zone(self, reason: str | None = None) -> None:
        """Fall back from SHADOW to PREVIEW and reset the tail target."""
        self._active_zone = Zone.PREVIEW
        self._active_preview_zone = Zone.PREVIEW
        self._shadow_absent_ticks = 0
        self._shadow_zone_agent_id = None
        self._focus_first_in_zone()
        self._manage_preview_timer()
        if reason:
            self.notify(reason)

    def _switch_zone(self, direction: int = 1) -> None:
        """Cycle active zone forward or backward, skipping unavailable zones."""
        idx = ZONE_ORDER.index(self._active_zone)
        # Loop rather than single-step so a skip can never land on an invalid
        # zone (PANE_LIST is always available, so this always terminates).
        for _ in range(len(ZONE_ORDER)):
            idx = (idx + direction) % len(ZONE_ORDER)
            if self._zone_available(ZONE_ORDER[idx]):
                break
        self._active_zone = ZONE_ORDER[idx]
        if self._active_zone == Zone.SHADOW:
            self._enter_shadow_zone()
        elif self._active_zone == Zone.PREVIEW:
            self._active_preview_zone = Zone.PREVIEW
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
        elif self._active_zone == Zone.SHADOW:
            try:
                self.query_one("#shadow-preview", PreviewPanel).focus()
            except Exception:
                pass

    def _update_zone_indicators(self) -> None:
        """Update visual indicators showing which zone is active."""
        try:
            for section_id, zone in [
                ("#pane-list", Zone.PANE_LIST),
                ("#content-section", Zone.PREVIEW),
                ("#shadow-col", Zone.SHADOW),
            ]:
                widget = self.query_one(section_id)
                widget.set_class(self._active_zone == zone, "zone-active")
        except Exception:
            return
        # Refresh the preview headers (LIVE indicator) for both columns.
        self._update_content_preview()
        self._update_shadow_preview()
        # Update footer to show/hide bindings based on active zone.
        # refresh_bindings() is what actually relabels the Footer — check_action
        # alone never does.
        self.refresh_bindings()
        # Keep the previewed PaneCard visually marked even when focus is on
        # the preview pane.
        self._update_selected_card_indicator()

    def _update_selected_card_indicator(self, full: bool = False) -> None:
        """Mark the PaneCard matching _focused_pane_id with the 'selected' class.

        Provides a persistent visual hint of which agent's preview is shown,
        even when keyboard focus has moved to the PreviewPanel.
        """
        focused_id = self._focused_pane_id
        if full:
            for card in self._pane_cards.values():
                card.set_class(card.pane_id == focused_id, "selected")
            self._selected_card_pane_id = (
                focused_id if focused_id in self._pane_cards else None
            )
            return

        old_id = self._selected_card_pane_id
        if old_id != focused_id:
            old_card = self._pane_cards.get(old_id) if old_id is not None else None
            if old_card is not None:
                old_card.set_class(False, "selected")

        new_card = self._pane_cards.get(focused_id) if focused_id is not None else None
        if new_card is not None:
            new_card.set_class(True, "selected")
            self._selected_card_pane_id = focused_id
        else:
            self._selected_card_pane_id = None

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Show/hide footer bindings based on active zone."""
        if self._active_zone in (Zone.PREVIEW, Zone.SHADOW):
            return action == "switch_zone"
        return action != "switch_zone"

    def action_switch_zone(self) -> None:
        """No-op — Tab is handled in on_key. Exists for Footer display only."""

    def action_send_enter(self) -> None:
        """No-op — Enter is handled in on_key. Exists for Footer display only."""

    async def _fast_zone_refresh(self) -> None:
        """Dispatch the 0.3s tick to the column the ACTIVE zone owns.

        set_interval binds its callback once, so widening _manage_preview_timer's
        `is None` guard to admit SHADOW would leave a PREVIEW→SHADOW transition
        taking neither branch — the live timer would keep refreshing the agent
        column forever. Dispatching here reads the zone at call time instead, so
        a zone change needs no timer churn and there is no stop/recreate window
        (t1216_2).
        """
        if self._active_zone == Zone.SHADOW:
            await self._fast_shadow_refresh()
        elif self._active_zone == Zone.PREVIEW:
            await self._fast_preview_refresh()

    def _manage_preview_timer(self) -> None:
        """Start/stop the fast preview timer based on active zone."""
        active = self._active_zone in (Zone.PREVIEW, Zone.SHADOW)
        if active and self._preview_timer is None:
            self._preview_timer = self.set_interval(0.3, self._fast_zone_refresh)
        elif not active and self._preview_timer is not None:
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

        # In the shadow zone: forward everything to the SHADOW pane. This must
        # sit above the PREVIEW catch-all below. event.stop() is unconditional,
        # so when the shadow is absent the key is SWALLOWED rather than falling
        # through to the agent pane — typing a user's shadow input into a
        # working agent would be a real hazard (t1216_2).
        if self._active_zone == Zone.SHADOW:
            shadow_pane = self._current_shadow_pane_id()
            if shadow_pane and self._monitor:
                self._forward_key_to_tmux(event, target_pane_id=shadow_pane)
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

    def _forward_key_to_tmux(self, event, target_pane_id: str | None = None) -> None:
        """Map a Textual key event to tmux send-keys and forward it.

        Key translation lives in ``monitor_core.translate_key`` (shared with the
        applink ``forward_key`` verb, t822_7); this method only forwards the
        key and wires the desktop fast refresh.

        ``target_pane_id`` overrides the default (the focused agent pane) for
        the SHADOW zone. The SCHEDULED refresh must match the target, or typing
        into the shadow would re-capture the agent column instead (t1216_2).
        """
        target = target_pane_id or self._focused_pane_id
        if self._monitor.forward_key(target, event.key, event.character):
            self.call_later(
                self._fast_shadow_refresh if target_pane_id
                else self._fast_preview_refresh
            )

    # -- Focus tracking --------------------------------------------------------

    def on_descendant_focus(self, event) -> None:
        widget = event.widget
        # NOTE: none of these branches clears _shadow_zone_agent_id. Focus
        # events fire incidentally during a pane-list rebuild, and unbinding
        # here would make the next _enter_shadow_zone look like a fresh entry
        # and reset the absent-grace counter every tick (t1216_2). The binding
        # is owned by _enter_shadow_zone / _leave_shadow_zone only.
        if isinstance(widget, PaneCard):
            self._active_zone = Zone.PANE_LIST
            self._focused_pane_id = widget.pane_id
            self._manage_preview_timer()
            self._update_zone_indicators()
        elif isinstance(widget, PreviewPanel):
            # BOTH preview columns are PreviewPanel instances, so the zone must
            # be disambiguated by widget id — an isinstance-only branch would
            # silently route shadow focus to Zone.PREVIEW (t1216_2).
            if widget.id == "shadow-preview":
                self._active_zone = Zone.SHADOW
                self._enter_shadow_zone()
            else:
                self._active_zone = Zone.PREVIEW
                self._active_preview_zone = Zone.PREVIEW
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
        # Keep the shadow column's height in step with the agent column.
        try:
            self.query_one(
                "#shadow-scroll", ScrollableContainer
            ).styles.max_height = preview_h
        except Exception:
            pass
        self.notify(f"Preview size: {label}")
        # Immediately repopulate the (possibly larger) preview without
        # waiting for the next 3s refresh cycle.
        self._update_content_preview()
        self._update_shadow_preview()
        self._schedule_shadow_fit_check()

    def _schedule_shadow_fit_check(self) -> None:
        """Re-decide the side-by-side split after the next layout pass.

        content_region is meaningless before layout, so every fit decision is
        deferred via call_after_refresh.
        """
        self.call_after_refresh(
            self._apply_shadow_visibility, self._shadow_visibility_width()
        )

    def action_scroll_preview_tail(self) -> None:
        """Jump the LAST-FOCUSED preview column to its tail and re-engage follow.

        `t` is only ever pressable from PANE_LIST — check_action disables every
        non-switch_zone binding while a preview zone is focused — so "the active
        column" means the last-focused one, tracked in _active_preview_zone
        (t1216_2). The two columns key their scroll state differently: the agent
        column by the followed pane id, the shadow column by the shadow pane id.
        """
        if self._active_preview_zone == Zone.SHADOW:
            scroll_id, state = "#shadow-scroll", self._shadow_scroll_state
            key = self._current_shadow_pane_id()
            refresh = self._fast_shadow_refresh
        else:
            scroll_id, state = "#preview-scroll", self._preview_scroll_state
            key = self._focused_pane_id
            refresh = self._fast_preview_refresh
        try:
            scroll = self.query_one(scroll_id, PreviewScrollContainer)
        except Exception:
            return
        scroll.scroll_end(animate=False)
        if key is not None:
            state[key] = (True, None)
            # Pull fresh content so tail-follow resumes on the latest output.
            self.call_later(refresh)
        self.notify("Tail follow")

    def on_resize(self, event) -> None:
        """Recompute dynamic sizing specs (agents:N) when the terminal is resized."""
        section_spec, _, _ = PREVIEW_SIZES[self._preview_size_idx]
        if isinstance(section_spec, str) and section_spec.startswith("agents:"):
            self._apply_preview_size()
        # NOTE: the shadow split is deliberately NOT re-decided here. This
        # handler runs before #preview-row has been re-laid-out, so it would
        # measure a stale content_region (a 120→70 resize still reports 120).
        # PreviewRow.on_row_resize drives the fit check instead — the row's own
        # Resize event is the one that carries a settled width (t1216_2).

    def action_toggle_auto_switch(self) -> None:
        """Toggle auto-switch mode on/off."""
        self._auto_switch = not self._auto_switch
        if self._auto_switch:
            self.notify("Auto-switch ON: preview follows idle agents needing attention")
        else:
            self.notify("Auto-switch OFF: manual selection only")
        self._rebuild_session_bar()
        if self._rebuild_pane_list():
            self._update_selected_card_indicator(full=True)

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

    # -- Shadow spawn (t1216_4) ------------------------------------------------

    def _resolve_shadow_target(self) -> tuple[PaneSnapshot, str] | None:
        """Validate the selected pane as a shadow target, or notify and return None.

        Shared prologue of ``e`` / ``E``. Resolves from ``self._focused_pane_id``
        — never ``_get_focused_pane_id()``, which reads ``self.focused`` and
        returns None whenever focus is off a PaneCard.
        """
        pane_id = self._focused_pane_id
        if not pane_id or pane_id not in self._snapshots:
            self.notify("Focus an agent pane first", severity="warning")
            return None
        snap = self._snapshots[pane_id]
        # Monitor-only guard: `_rebuild_pane_list` renders PaneCategory.OTHER
        # panes as focusable PaneCards, so the selection can be a shell or a
        # lazygit pane. minimonitor never needed this — it resolves its target
        # via `_find_own_agent_snapshot`, which already filters on category.
        if snap.pane.category != PaneCategory.AGENT:
            self.notify("Shadow only applies to agent panes", severity="warning")
            return None
        followed_pane = snap.pane.pane_id
        if not followed_pane:
            self.notify("Agent pane id unavailable", severity="warning")
            return None
        # One shadow per followed agent (the @aitask_shadow_target option is the
        # lifecycle binding). Live lookup, not the snapshot cache: the cache can
        # only report a shadow it has already observed, so it cannot answer
        # "may I create one". Fail closed — an unverifiable state must not spawn.
        ok, existing = find_shadow_pane_status(self._monitor, followed_pane)
        if not ok:
            self.notify(
                "Could not verify whether a shadow is already running",
                severity="warning",
            )
            return None
        if existing:
            self.notify(
                "A shadow is already running for this agent", severity="warning"
            )
            return None
        return snap, followed_pane

    def action_launch_shadow(self) -> None:
        """Spawn the shadow companion agent for the SELECTED coding agent.

        Builds ``/aitask-shadow <followed_pane_id> [<task_id>]`` and launches the
        ``shadow`` codeagent — by default a new pane in the followed agent's
        window, or a separate window when ``tmux.shadow_same_window`` is false.
        The launcher passes only the pane id; the shadow skill captures the
        followed pane on demand. After spawn it stamps ``@aitask_shadow_target``
        on the new pane (the t986_1 classifier that keeps the shadow out of agent
        lists and binds its lifecycle) and wires the followed agent's
        ``pane-died`` cleanup hook so the shadow dies with its agent.

        Sync by design: the duplicate guard's single ``list-panes`` round-trip is
        far cheaper than the spawn that follows, and this is a user action, not
        the refresh path that `test_monitor_refresh_no_sync_tmux` constrains.
        """
        if self._monitor is None:
            return
        target = self._resolve_shadow_target()
        if target is None:
            return
        snap, followed_pane = target
        task_id = self._task_cache.get_task_id_for_pane(snap.pane)
        target_root = self._root_for_snap(snap)
        args = [followed_pane] + ([task_id] if task_id else [])
        full_cmd = resolve_dry_run_command(target_root, "shadow", *args)
        if not full_cmd:
            self.notify("Failed to resolve shadow command", severity="error")
            return
        self._spawn_shadow(full_cmd, followed_pane, task_id, target_root, snap)

    def action_launch_shadow_pick(self) -> None:
        """Open the agent/model picker, then spawn the shadow with the choice.

        Same as ``action_launch_shadow`` (duplicate guard, specialized same-window
        split placement, ``@aitask_shadow_target`` stamp + cleanup hook) but opens
        the ``AgentCommandScreen`` first so the user can confirm / change the code
        agent and model before the shadow starts. Cancelling launches nothing.

        The dialog's own returned placement is intentionally discarded: the
        shadow's split-target-the-followed-AGENT-pane geometry is richer than the
        dialog's tmux tab can express, so placement stays handler-controlled in
        ``_spawn_shadow`` and only the (possibly agent-overridden)
        ``full_command`` is consumed.
        """
        if self._monitor is None:
            return
        target = self._resolve_shadow_target()
        if target is None:
            return
        snap, followed_pane = target
        task_id = self._task_cache.get_task_id_for_pane(snap.pane)
        target_root = self._root_for_snap(snap)
        args = [followed_pane] + ([task_id] if task_id else [])
        full_cmd = resolve_dry_run_command(target_root, "shadow", *args)
        if not full_cmd:
            self.notify("Failed to resolve shadow command", severity="error")
            return
        screen = AgentCommandScreen(
            "Shadow (pick agent)",
            full_cmd,
            "/aitask-shadow " + " ".join(args),
            project_root=target_root,
            operation="shadow",
            operation_args=args,
            default_agent_string=resolve_agent_string(target_root, "shadow"),
        )

        def on_shadow_result(result):
            # Confirm returns a TmuxLaunchConfig; its placement is discarded (see
            # docstring). Use screen.full_command (post-override), not the
            # captured full_cmd. None (cancel) / "run" launch nothing.
            if isinstance(result, TmuxLaunchConfig):
                self._spawn_shadow(
                    screen.full_command, followed_pane, task_id, target_root, snap
                )

        self.push_screen(screen, on_shadow_result)

    def _spawn_shadow(
        self,
        full_cmd: str,
        followed_pane: str,
        task_id: str | None,
        target_root: Path,
        snap: PaneSnapshot,
    ) -> str | None:
        """Apply **this app's** shadow-spawn policy, then delegate the mechanics.

        Kept as a per-app method deliberately — it is **not** a pass-through
        seam. The two safety-critical decisions below differ between the monitor
        and the minimonitor, and inlining them at both call sites in each app
        would replicate them four times instead of twice (t1216_4).
        """
        if self._monitor is None:
            return None
        return spawn_shadow(
            self._monitor,
            full_cmd=full_cmd,
            followed_pane=followed_pane,
            followed_window=snap.pane.window_name,
            session=snap.pane.session_name or self._session,
            task_id=task_id,
            target_root=target_root,
            # The monitor is NOT the agent's companion and normally lives in
            # another window — passing our own TMUX_PANE here would make
            # aitask_companion_cleanup.sh kill the monitor when the agent's
            # window runs out of real agents. None binds the hook to the new
            # shadow pane instead.
            companion_pane=None,
            # Stealing the client's window would defeat the shadow preview column
            # this monitor exists to show.
            select_window=False,
            notify=self.notify,
            schedule_refresh=lambda: self.call_later(self._refresh_data),
            # Stamped before spawn_shadow returns, so a shadow that reads
            # `--phase` before the first refresh tick still sees the checkpoint
            # it was launched for (t1420).
            phase_signal=self._phase_signal_for_pane(snap),
        )

    def _phase_signal_for_pane(self, snap: PaneSnapshot):
        """Advisory phase for a pane, or ``None`` when it cannot be resolved.

        ``None`` simply leaves the pane option unwritten; the per-tick re-stamp
        in ``_format_agent_card_text`` fills it in shortly after.
        """
        try:
            task_id = self._task_cache.get_task_id_for_pane(snap.pane)
            if not task_id:
                return None
            info = self._task_cache.get_task_info(task_id, snap.pane.session_name)
            if info is None:
                return None
            return self._gate_cache.phase_for(
                info,
                screen_text=snap.content,
                awaiting_input=snap.awaiting_input,
                awaiting_input_kind=snap.awaiting_input_kind,
                agent=workflow_phase.agent_key_from_command(
                    snap.pane.current_command),
            )
        except Exception:
            return None

    async def action_pick_concerns(self) -> None:
        """Forward the selected agent's shadow concerns via the clipboard (t1216_3).

        Captures the bound shadow pane, parses its concern block, opens the
        shared picker modal, and on confirm copies the selected concerns (with a
        preamble) to the clipboard. The hotkey path uses the forgiving
        ``parse_concerns`` — the user deliberately asked to look now; the refresh
        tick uses the cheap ``concern_block_signature`` trigger instead.

        ``check_action`` disables every non-``switch_zone`` binding while a
        preview zone is focused, so this is only ever reachable from PANE_LIST —
        in PREVIEW / SHADOW the keystroke is forwarded to tmux, which is correct.
        """
        if self._concern_pick_busy:
            return
        pane_id = self._focused_pane_id
        if not pane_id or pane_id not in self._snapshots:
            self.notify("Focus an agent pane first", severity="warning")
            return
        shadow_pane = self._current_shadow_pane_id()
        if not shadow_pane:
            self.notify(
                "No shadow agent bound to this agent — press 'e' to launch one",
                severity="warning",
            )
            return
        self._concern_pick_busy = True
        modal_owns_guard = False
        # Resolved HERE, not in the callback: Textual invokes the dismissal
        # callback with the result and nothing else, so the pane — the only
        # thing a task id can be derived from — is out of reach by then.
        # Pinned for the same reason pane_id is: `c` acts on the agent that was
        # selected when it was pressed.
        self._concern_pick_task_id = self._task_cache.get_task_id_for_pane(
            self._snapshots[pane_id].pane
        )
        # Snapshot the trigger BEFORE any await: the 3s tick can replace it with
        # a newer block's signature while we capture, and marking THAT signature
        # offered would clear its badge without ever presenting it.
        trigger_sig = self._concern_sig_latest.get(pane_id)
        try:
            text = await capture_shadow_text(shadow_pane)
            if text is None:
                self.notify("Could not read the shadow pane", severity="warning")
                return  # indeterminate — leave the marker untouched
            concerns = parse_concerns(text)
            if not concerns and block_head_truncated(text):
                # The block is there but the window started inside it. This is
                # the explicit user action, so pay for ONE much deeper re-capture
                # rather than reporting a false "no concerns" (t1187).
                deeper = await capture_shadow_text(
                    shadow_pane, lines=_SHADOW_DEEP_RETRY_LINES
                )
                if deeper is not None:
                    text = deeper
                    concerns = parse_concerns(text)
                if not concerns:
                    self.notify(_SHADOW_TRUNCATED_MSG, severity="warning")
                    return  # indeterminate — marker untouched
            if not concerns:
                lost = unrecovered_markers(text)
                if lost:
                    self.notify(
                        unparsed_concerns_msg(len(lost)), severity="warning"
                    )
                else:
                    self.notify("No concerns detected on the shadow pane")
                # Definitive ONLY when the capture does contain a complete block:
                # the user has just been told precisely what is in it and it will
                # never become parseable, so clear the badge. With no complete
                # block here we learned nothing about the badged one — leave it.
                done_sig = concern_block_signature(text)
                if done_sig is not None:
                    self._mark_concern_sig(
                        self._concern_sig_offered, pane_id, trigger_sig, done_sig
                    )
                if lost:
                    # No picker means no banner to hang the `u` affordance off,
                    # so open the raw view directly (t1293). It owns the pick
                    # guard until dismissed, exactly like the picker does —
                    # otherwise a second `c` would stack inspect modals.
                    self.push_screen(
                        ConcernBlockInspectModal(lost, block_region(text) or ""),
                        callback=self._on_inspect_closed,
                    )
                    modal_owns_guard = True
                return
            eps = max(2.0, float(getattr(self, "_refresh_seconds", 3)))
            stale, _ = await compute_shadow_staleness(
                self._monitor, shadow_pane, pane_id, eps
            )
            # pane_id stays PINNED across these awaits, unlike the toast path: `c`
            # is an explicit action against the agent selected when it was
            # pressed, so its modal and marker belong to that agent even if the
            # selection drifts mid-capture.
            self._mark_concern_sig(
                self._concern_sig_offered, pane_id, trigger_sig,
                concern_block_signature(text),
            )
            task_id = self._concern_pick_task_id
            entries = await self._fetch_rejected_entries(task_id)
            self.push_screen(
                ConcernPickerModal(
                    concerns,
                    narrow=False,  # the monitor is full-width, unlike minimonitor
                    stale=bool(stale),
                    unrecovered=unrecovered_markers(text),
                    raw_block=block_region(text) or "",
                    rejected_entries=entries,
                    store_unavailable=not task_id,
                ),
                callback=self._on_concerns_picked,
            )
            modal_owns_guard = True  # released by the callback, not here
        finally:
            if not modal_owns_guard:
                self._concern_pick_busy = False

    def _on_concerns_picked(self, result) -> None:
        """Modal callback: forward and/or persist the user's dispositions.

        Also releases the pick guard. Textual invokes this on every dismissal
        (including ``None`` on Esc), and holding the guard until then is what
        stops a second `c` over the open picker stacking another one.

        ``result`` is a ``ConcernPickResult`` on confirm, or ``None`` on
        cancel — in which case nothing is written (no side effect before an
        explicit confirm). The shared body lives on ``ShadowRejectionsMixin``;
        only the guard release is monitor-specific.
        """
        self._concern_pick_busy = False
        self.apply_concern_pick_result(result, self._concern_pick_task_id)

    def _on_inspect_closed(self, _result) -> None:
        """Release the pick guard when the raw-block view closes (t1293).

        The all-malformed path pushes :class:`ConcernBlockInspectModal` instead
        of the picker, so it needs its own release — without it the guard would
        stay held and every later `c` would be silently swallowed.
        """
        self._concern_pick_busy = False

    def action_show_task_info(self) -> None:
        """Show task detail dialog for the focused agent pane."""
        pane_id = self._get_focused_pane_id()
        if not pane_id:
            self.notify("Focus an agent pane first", severity="warning")
            return
        snap = self._snapshots.get(pane_id)
        if not snap:
            return
        task_id = self._task_cache.get_task_id_for_pane(snap.pane)
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
                start_new_session=True,  # outlive the monitor TUI (esp. outside tmux)
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
        task_id = self._task_cache.get_task_id_for_pane(snap.pane)
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
        task_id = self._task_cache.get_task_id_for_pane(snap.pane)
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
        action, payload = result
        if action == "pick":
            self._launch_pick_for_sibling(payload)
            return
        # action == "choose": payload is parent_id; open the sibling picker.
        pane_id = self._focused_pane_id
        if pane_id is None or self._monitor is None:
            return
        snap = self._snapshots.get(pane_id)
        if not snap:
            return
        task_id = self._task_cache.get_task_id_for_pane(snap.pane)
        if not task_id:
            return
        sess = snap.pane.session_name
        siblings = self._task_cache.find_ready_siblings(task_id, sess)
        if not siblings:
            self.notify("No Ready siblings to choose from", severity="warning")
            return

        def _on_picked(sib_id: str | None) -> None:
            if sib_id:
                self._launch_pick_for_sibling(sib_id)

        self.push_screen(ChooseSiblingModal(payload, siblings), callback=_on_picked)

    def _launch_pick_for_sibling(self, target_id: str) -> None:
        """Launch `/aitask-pick <target_id>` for the focused pane's session.

        Kills the current pane first if the current task is a parent split
        into children, was archived, or is Done — matching the heuristic
        used by the immediate "Pick t<N>" path.
        """
        pane_id = self._focused_pane_id
        if pane_id is None or self._monitor is None:
            return
        snap = self._snapshots.get(pane_id)
        if not snap:
            return
        task_id = self._task_cache.get_task_id_for_pane(snap.pane)
        if not task_id:
            return
        sess = snap.pane.session_name
        current_info = self._task_cache.get_task_info(task_id, sess)

        target_root = self._root_for_snap(snap)
        full_cmd = resolve_dry_run_command(target_root, "pick", target_id)
        if not full_cmd:
            self.notify(f"Failed to resolve pick command for t{target_id}", severity="error")
            return

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
            skill_name="pick",
            default_profile=resolve_skill_profile("pick", target_root),
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
        task_id = self._task_cache.get_task_id_for_pane(snap.pane)
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
            skill_name="pick",
            default_profile=resolve_skill_profile("pick", target_root),
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


def main() -> None:
    parser = argparse.ArgumentParser(description="tmux pane monitor TUI")
    parser.add_argument("--session", "-s", default=None, help="tmux session name")
    parser.add_argument("--interval", "-i", type=int, default=None, help="refresh interval in seconds")
    parser.add_argument("--lines", "-n", type=int, default=None, help="lines to capture per pane")
    parser.add_argument(
        "--headless-for-applink", action="store_true",
        help="Run the applink bridge headless (no TUI), serving only the mobile "
             "listener. See 'ait monitor --headless-for-applink --help' for options.",
    )
    args = parser.parse_args()

    # The launcher (aitask_monitor.sh) intercepts --headless-for-applink before
    # exec and routes to applink/headless.py, so this branch only fires on a
    # direct `python monitor_app.py --headless-for-applink` that bypassed the
    # launcher's dep-probe and routing. Fail clearly instead of opening the TUI.
    if args.headless_for_applink:
        print(
            "Run the applink headless bridge via the launcher: "
            "ait monitor --headless-for-applink",
            file=sys.stderr,
        )
        raise SystemExit(2)

    project_root = Path(__file__).resolve().parents[2]
    config = load_monitor_config(project_root)
    tmux_config = load_project_tmux_config(project_root)

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
        rename_window=True,
        mark_pane=True,   # production launcher only — see MonitorApp.__init__
    )
    app.run()


if __name__ == "__main__":
    main()
