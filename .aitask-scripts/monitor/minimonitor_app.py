"""minimonitor_app - Compact TUI for monitoring tmux agent panes.

Designed to run as a narrow side-column (~40 columns) alongside code agent
windows in tmux. Shows all code agents with idle status. Unlike the full
monitor, it has no preview zone — just a compact agent list with status.

Usage:
    python minimonitor_app.py [--session NAME] [--interval SECS]
"""
from __future__ import annotations

import argparse
import contextlib
import os
import re
import subprocess
import sys
import textwrap
import time
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
    # Shared shadow seam (t1216_1) — one implementation, shared with the full
    # monitor, which imports it the same way (`monitor_app.py`).
    find_shadow_pane,
    find_shadow_pane_async,
    capture_shadow_text,
    compute_shadow_staleness,
    spawn_shadow,
    _SHADOW_DEEP_RETRY_LINES,
    _SHADOW_TRUNCATED_MSG,
)
from monitor.tmux_control import TmuxControlState  # noqa: E402
from monitor.monitor_shared import (  # noqa: E402
    _TASK_ID_RE, GateSummaryCache, TaskInfoCache, TaskDetailDialog,
    KillConfirmDialog, NextSiblingDialog, ChooseSiblingModal,
    AgentMarksMixin,
    ConcernPickerModal, TaskNumberInputModal, TaskPickConfirmDialog,
    format_compare_mode_glyph, format_mark_glyph, format_pane_status,
    format_shadow_glyph, format_stale_duration, format_state_dot,
    is_task_completed, unparsed_concerns_msg,
)
from monitor.concern_parser import (  # noqa: E402
    block_head_truncated, build_clipboard_payload, has_concern_block,
    needs_addressing, parse_concerns, unrecovered_markers,
)
from monitor.desync_summary import get_desync_summary as _get_desync_summary  # noqa: E402
from tui_switcher import TuiSwitcherMixin  # noqa: E402
from shortcuts_mixin import ShortcutsMixin  # noqa: E402
from tui_clipboard import copy_to_system_clipboard  # noqa: E402
from agent_launch_utils import (  # noqa: E402
    resolve_dry_run_command,
    resolve_agent_string,
    TmuxLaunchConfig,
    launch_in_tmux,
    maybe_spawn_minimonitor,
    tmux_session_target,
    tmux_window_target,
)
from agent_command_screen import AgentCommandScreen, resolve_skill_profile  # noqa: E402

from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import VerticalScroll  # noqa: E402
from textual.screen import ModalScreen  # noqa: E402
from textual.timer import Timer  # noqa: E402
from textual.widgets import Static  # noqa: E402


# -- Widgets ------------------------------------------------------------------

class MiniPaneCard(Static, can_focus=True):
    """Compact status entry for an agent pane."""

    def __init__(self, pane_id: str, text: str, **kwargs) -> None:
        super().__init__(text, **kwargs)
        self.pane_id = pane_id


# Accepted shapes for a hand-typed task number (t1310): a parent id, or one
# child level — the same shape `_TASK_ID_RE` extracts from agent window names.
# Applied BEFORE any lookup, because the id is interpolated into a glob pattern
# downstream and passed to the pick command.
_PICK_TASK_ID_RE = re.compile(r"\d+(?:_\d+)?")


# -- Main app -----------------------------------------------------------------

class MiniMonitorApp(AgentMarksMixin, TuiSwitcherMixin, ShortcutsMixin, App):
    """Compact Textual app for monitoring tmux agent panes."""

    _shortcuts_scope = "minimonitor"

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

    #mini-shadow-stale {
        dock: top;
        height: auto;
        background: $error;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }

    #mini-own-agent {
        dock: top;
        height: auto;
        background: $boost;
        border-bottom: solid $primary;
        padding: 0;
    }

    .mini-own-header {
        height: 1;
        padding: 0 1;
        color: $text-muted;
        text-style: bold;
    }

    .mini-own-card {
        height: auto;
        padding: 0 1;
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

    .mini-session-divider {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }

    #mini-key-hints {
        dock: bottom;
        height: auto;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    """

    BINDINGS = [
        *ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS,
        Binding("tab", "focus_sibling_pane", "Focus agent", show=False),
        Binding("enter", "send_enter_to_sibling", "Send Enter", show=False),
        Binding("k", "kill_own_agent", "Kill", show=False),
        Binding("n", "pick_next_for_own", "Next", show=False),
        Binding("p", "pick_task_by_number", "Pick task", show=False),
        Binding("e", "launch_shadow", "Shadow", show=False),
        Binding("E", "launch_shadow_pick", "Shadow (pick agent)", show=False),
        Binding("c", "pick_concerns", "Concerns", show=False),
        Binding("j", "tui_switcher", "TUI switcher", show=False),
        Binding("q", "quit", "Quit", show=False),
        Binding("s", "switch_to", "Switch", show=False),
        Binding("i", "show_task_info", "Task Info", show=False),
        Binding("I", "show_own_task_info", "Task Info (followed)", show=False),
        Binding("m", "switch_to_monitor", "Full Monitor", show=False),
        Binding("M", "toggle_multi_session", "Multi", show=False),
        Binding("d", "cycle_compare_mode", "Detect", show=False),
        Binding("space", "toggle_mark", "Mark", show=False),
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
        compare_mode_default: str = "stripped",
        target_width: int = 40,
    ) -> None:
        super().__init__()
        self.current_tui_name = "minimonitor"
        self._session = session
        self._refresh_seconds = refresh_seconds
        self._capture_lines = capture_lines
        self._idle_threshold = idle_threshold
        self._agent_prefixes = agent_prefixes
        self._tui_names = tui_names
        self._compare_mode_default = compare_mode_default
        # Configured width of this companion side-column. tmux rescales panes
        # proportionally on a window resize (incl. detach->reattach), so the
        # pane spawned at this width drifts wider; on_resize re-pins it.
        self._target_width = target_width
        self._snapshots: dict[str, PaneSnapshot] = {}
        self._focused_pane_id: str | None = None
        self._monitor: TmuxMonitor | None = None
        self._refresh_timer: Timer | None = None
        self._project_root = project_root
        self._task_cache = TaskInfoCache(project_root)
        self._gate_cache = GateSummaryCache()
        # Pane ids whose task is finished, recomputed once per refresh tick
        # (t1322) so the card badge and the session bar's `d` counter agree
        # within a tick. See MonitorApp._compute_completed_panes.
        self._completed_pane_ids: frozenset[str] = frozenset()
        self._mount_time: float = 0.0
        self._own_window_id: str | None = None
        self._own_window_index: str | None = None
        self._own_window_name: str | None = None
        # The followed-agent docked panel is built once (static identity, no
        # per-cycle status refresh) — see _maybe_build_own_agent_panel.
        self._own_panel_built: bool = False
        # Auto-offer de-dup (t1037_4): last forwarded concern payload per shadow
        # pane id, so a re-detected *unchanged* block does not re-fire the hint.
        self._last_concern_block_payload: dict[str, str] = {}
        # Shadow panes already warned that their concern block was clipped at the
        # head by the capture window (t1187). Warn once per episode, not every
        # tick; cleared for a pane as soon as a complete block is seen on it.
        self._truncation_warned: set[str] = set()
        # Shadow panes already warned that their complete concern block parsed to
        # nothing because every marker was malformed (t1274). Same once-per-
        # episode policy as `_truncation_warned`, and cleared the same way.
        self._unparsed_warned: set[str] = set()
        # Shadow-feedback freshness (t1104). Tri-state: None = unknown (never
        # resolved, or a transient capture/hash failure — do NOT clear a prior
        # warning on such a failure), False = current, True = stale.
        self._shadow_feedback_stale: bool | None = None
        # Throttle the staleness compare to every OTHER refresh tick (~6s at the
        # 3s default) to halve the extra pane reads; the concern auto-offer still
        # runs every tick. Odd counter ⇒ checks on the first tick a shadow is
        # present (responsive) then every second one.
        self._shadow_freshness_tick: int = 0
        # Prioritized-agent marks (t1326): cached reader + purge scheduling.
        self._init_agent_marks()

    def compose(self) -> ComposeResult:
        yield Static(id="mini-session-bar")
        # Live staleness warning for shadow feedback (t1104); empty ⇒ 0 rows.
        yield Static("", id="mini-shadow-stale")
        yield VerticalScroll(id="mini-own-agent")
        yield VerticalScroll(id="mini-pane-list")
        yield Static(
            "i:info  q:quit  tab:agent\n"
            "I:info (followed agent)\n"
            "s/\u2191\u2193:switch  enter:send\n"
            "d:detect (\u2248 strip, = raw)\n"
            "j:tui switcher  m:full monitor\n"
            "k:kill  n:next  e/E:shadow\n"
            "c:concerns  p:pick task\n"
            "space:mark (★ prioritized)",
            id="mini-key-hints",
        )

    def on_mount(self) -> None:
        self._mount_time = time.monotonic()

        if not os.environ.get("TMUX"):
            self.query_one("#mini-session-bar", Static).update(
                "[bold red]Not inside tmux[/]"
            )
            return

        # Detect own window ID, index, and name for auto-close, auto-selection,
        # and the "switch to full monitor" handoff.
        own_pane = os.environ.get("TMUX_PANE", "")
        try:
            result = subprocess.run(
                ["tmux", "display-message", "-p", "-t", own_pane,
                 "#{window_id}\t#{window_index}\t#{window_name}"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split("\t")
                if len(parts) >= 1:
                    self._own_window_id = parts[0]
                if len(parts) >= 2:
                    self._own_window_index = parts[1]
                if len(parts) >= 3:
                    self._own_window_name = parts[2]
        except Exception:
            pass

        # CRITICAL: Do NOT rename the tmux window — minimonitor runs inside
        # an agent's window, renaming would break agent classification.

        self._start_monitoring()

    def on_resize(self, event) -> None:
        """Re-pin the companion pane to its configured width on any resize."""
        self._maybe_pin_width()

    def _maybe_pin_width(self) -> None:
        """Clamp this minimonitor's companion pane back to its target width.

        tmux stores window layout as proportions, so on a window resize (live,
        or detach -> resize terminal -> reattach) it rescales every pane to the
        same fraction of the new width — a pane spawned at ``target_width``
        columns drifts wider. Re-pin it whenever we exceed the target.

        Self-terminating: after the resize the pane width equals the target, so
        the follow-up Resize event returns early. If the window is too narrow
        for the target, tmux clamps ``-x`` to what fits and the width stays at
        or below the target, so it does not loop either.
        """
        if self._monitor is None:
            return
        own_pane = os.environ.get("TMUX_PANE")
        if not own_pane:
            return
        if self.size.width <= self._target_width:
            return
        self._monitor.resize_pane(own_pane, x=self._target_width)

    def _teardown_prior_monitoring(self) -> None:
        """Cancel the prior refresh timer and close the prior monitor's
        control client, if any. Mirrors `MonitorApp._teardown_prior_monitoring`.

        Minimonitor does not currently re-enter `_start_monitoring()` (no
        session-rename flow), but the helper is cheap and protects against
        future re-entry paths.
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

    async def on_unmount(self) -> None:
        if getattr(self, "_monitor", None) is not None:
            try:
                await self._monitor.close_control_client()
            except Exception:
                pass

    # -- Data refresh ----------------------------------------------------------

    async def _refresh_data(self) -> None:
        if self._monitor is None:
            return

        # Save focus state before rebuild
        saved_pane_id = self._focused_pane_id

        # capture_all_async returns None when a newer overlapping refresh
        # superseded this one (t1111_4). Skip the stale cycle — a newer refresh
        # owns the rebuild — rather than overwriting visible snapshots with stale
        # pane content.
        snaps = await self._monitor.capture_all_async()
        if snaps is None:
            return
        self._snapshots = snaps
        # Refresh per-session project-root mapping so cross-session task data
        # resolves from the right project (free — uses TmuxMonitor's cached
        # session list).
        session_roots = self._monitor.get_session_to_project_mapping()
        self._task_cache.update_session_mapping(session_roots)
        # Prioritized marks (t1326) reuse this tick's mapping rather than
        # re-querying per row — see AgentMarksMixin._set_session_root_map.
        self._set_session_root_map(session_roots)
        # Drop last cycle's gate summaries so a live-growing ledger re-derives
        # this refresh (mirrors the board's per-refresh gate cache).
        self._gate_cache.clear()
        # Prioritized marks (t1326): mtime-gated, so this is one os.stat when
        # nothing changed. Must run before the pane list renders, and is what
        # makes a mark set in another repo appear here within one tick.
        self._refresh_marks()
        # Completed-pane set for THIS tick (t1322) — after the session
        # mapping refresh (which may clear the task cache), before the bar
        # and the pane list read it.
        self._completed_pane_ids = self._compute_completed_panes()

        # Keep window index fresh (handles tmux renumber-windows)
        self._update_own_window_info()

        # Auto-close check (with 5-second grace period after mount)
        if self._own_window_id and (time.monotonic() - self._mount_time) > 5.0:
            self._check_auto_close()

        self._rebuild_session_bar()
        # Build the followed-agent panel once (static identity — it does not
        # refresh with the general list), then rebuild the list (which excludes
        # the followed agent). Await both so remove_children/mount_all complete
        # before focus restoration — Textual's remove/mount/focus are deferred,
        # so a direct call into _restore_focus would race the DOM updates.
        await self._maybe_build_own_agent_panel()
        await self._rebuild_pane_list()

        self._restore_focus(saved_pane_id)

        # Proactive concern auto-offer (t1037_4): hint once per *new* complete
        # concern block on the followed agent's shadow pane. Best-effort and
        # event-loop safe — any failure silently skips this tick.
        await self._maybe_offer_concerns()

        # Materialize mark expiry / the liveness sweep at most every 10 min
        # (t1326). Last, so a slow writer can never delay the visible refresh.
        await self._maybe_purge_marks()

    def _check_auto_close(self) -> None:
        """Exit if no other panes remain in our window (besides ourselves)."""
        if self._monitor is None or self._own_window_id is None:
            return
        panes = self._monitor.discover_window_panes(self._own_window_id)
        own_pane = os.environ.get("TMUX_PANE")
        other_panes = [p for p in panes if p.pane_id != own_pane]
        if not other_panes:
            self.exit()

    def _update_own_window_info(self) -> None:
        """Re-query own window index/name (handles tmux renumber-windows and
        window renames)."""
        own_pane = os.environ.get("TMUX_PANE", "")
        if not own_pane or self._monitor is None:
            return
        rc, stdout = self._monitor.tmux_run(
            ["display-message", "-p", "-t", own_pane,
             "#{window_id}\t#{window_index}\t#{window_name}"],
            timeout=2,
        )
        if rc != 0 or not stdout.strip():
            return
        parts = stdout.strip().split("\t")
        if len(parts) >= 1:
            self._own_window_id = parts[0]
        if len(parts) >= 2:
            self._own_window_index = parts[1]
        if len(parts) >= 3:
            self._own_window_name = parts[2]

    def _find_own_agent_snapshot(self) -> PaneSnapshot | None:
        """Return the snapshot of the AGENT pane sharing this minimonitor's
        tmux window (the agent it follows), or None if not detected.

        Matches on window_index scoped to the own session — the same match
        used to auto-select the followed agent. Multi-session: two sessions
        could both have a pane at the same window_index, so the session scope
        prevents resolving a cross-session agent. Empty session_name is
        preserved to cover legacy snapshot paths.
        """
        if not self._own_window_index:
            return None
        for snap in self._snapshots.values():
            if (
                snap.pane.category == PaneCategory.AGENT
                and snap.pane.window_index == self._own_window_index
                and snap.pane.session_name in ("", self._session)
            ):
                return snap
        return None

    def _root_for_snap(self, snap: PaneSnapshot) -> Path:
        """Project root that owns the given pane's tmux session, falling back to
        this minimonitor's project root. Mirrors MonitorApp._root_for_snap."""
        sess = snap.pane.session_name
        if sess and self._monitor is not None:
            mapping = self._monitor.get_session_to_project_mapping()
            if sess in mapping:
                return mapping[sess]
        return self._project_root

    def _restore_focus(self, pane_id: str | None) -> None:
        """Re-focus the previously focused card after a rebuild."""
        if pane_id is not None:
            for card in self.query("#mini-pane-list MiniPaneCard"):
                if hasattr(card, "pane_id") and card.pane_id == pane_id:
                    card.focus()
                    # Widget.focus() is deferred, so on_descendant_focus may
                    # not fire before the next refresh cycle. Set directly to
                    # avoid a stale saved_pane_id on the next tick.
                    self._focused_pane_id = card.pane_id
                    return
        # Fallback: select the first general-list agent (the followed agent
        # lives in its own static docked panel and is not focusable).
        self._auto_select_own_window()

    def _auto_select_own_window(self) -> None:
        """Focus the first general-list agent card, if any.

        The followed agent is shown in the static, non-focusable docked panel
        (``#mini-own-agent``), so there is nothing to auto-select there.
        """
        list_cards = list(self.query("#mini-pane-list MiniPaneCard"))
        if list_cards:
            list_cards[0].focus()

    def on_app_focus(self) -> None:
        """Auto-select own window's agent when this pane regains terminal focus.

        Always re-selects the card matching this window's agent so that after
        an "s" switch the target minimonitor highlights the correct agent.
        """
        self._auto_select_own_window()

    def _rebuild_session_bar(self) -> None:
        agents = [
            s for s in self._snapshots.values()
            if s.pane.category == PaneCategory.AGENT
        ]
        total = len(agents)
        # Same three-way partition as the full monitor (t1322): each agent lands
        # in at most one bucket, on the PROMPT > COMPLETED > IDLE ladder the
        # badges use. The bar is narrow, so `done` renders as a compact `Nd`.
        awaiting_count = sum(1 for a in agents if getattr(a, "awaiting_input", False))
        done_count = sum(1 for a in agents
                         if a.pane.pane_id in self._completed_pane_ids
                         and not getattr(a, "awaiting_input", False))
        idle_count = sum(1 for a in agents
                         if a.is_idle and not getattr(a, "awaiting_input", False)
                         and a.pane.pane_id not in self._completed_pane_ids)

        awaiting_str = f" [bold magenta]{awaiting_count} awaiting[/]" if awaiting_count > 0 else ""
        done_str = f" [bold dodger_blue1]{done_count}d[/]" if done_count > 0 else ""
        idle_str = f" [yellow]{idle_count} idle[/]" if idle_count > 0 else ""
        try:
            desync = _get_desync_summary(Path.cwd(), compact=True)
        except Exception:
            desync = ""
        # Surface the control-channel state only when not steady-state.
        # Compact form fits the narrow minimonitor bar.
        state_badge = ""
        if self._monitor is not None:
            s = self._monitor.control_state()
            if s == TmuxControlState.RECONNECTING:
                state_badge = " [yellow]rc:retry[/]"
            elif s == TmuxControlState.FALLBACK:
                state_badge = " [red]rc:fb[/]"
        bar = self.query_one("#mini-session-bar", Static)

        if self._monitor is not None and self._monitor.multi_session:
            # Count unique sessions currently represented in the snapshot so
            # the bar tracks what's on screen, not the discovery cache.
            sessions = {
                s.pane.session_name for s in agents if s.pane.session_name
            }
            n = len(sessions) if sessions else 1
            bar.update(f"multi: {n}s · {total}a{awaiting_str}{done_str}{idle_str}{desync}{state_badge}")
        else:
            bar.update(
                f"{self._session}  {total} agent{'s' if total != 1 else ''}{awaiting_str}{done_str}{idle_str}{desync}{state_badge}"
            )

    def _compute_completed_panes(self) -> frozenset[str]:
        """Pane ids whose task is finished, for THIS refresh tick (t1322).

        Mirrors :meth:`MonitorApp._compute_completed_panes` — one pass per tick
        so the card badge and the session-bar counter cannot disagree, and the
        only site paying the per-pane ``os.stat`` freshness check.
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

    def _agent_card_text(self, snap: PaneSnapshot) -> str:
        """Build the compact card text (status line + optional task title) for
        a general-list agent row (``_rebuild_pane_list`` is the only caller).

        NOT used by the docked followed-agent panel — that renders via
        ``_own_agent_identity_text`` and is static by design: no live status
        dot, no compare-mode glyph, and no shadow-status glyph (t1133).
        """
        # Per-tick set is the SOLE source of the completed flag (t1322) — the
        # `info` lookup below supplies the title and gate summary but must never
        # re-derive completion, or the badge could disagree with the session bar
        # for a tick. See MonitorApp._format_agent_card_text.
        completed = snap.pane.pane_id in self._completed_pane_ids
        dot = format_state_dot(snap, completed)
        status = format_pane_status(snap, completed)


        glyph = "?"
        shadow = ""
        if self._monitor is not None:
            mode = self._monitor.get_compare_mode(snap.pane.pane_id)
            is_override = self._monitor.is_compare_mode_overridden(snap.pane.pane_id)
            glyph = format_compare_mode_glyph(mode, is_override)
            # Shadow-status glyph (t1133): second colored glyph right after
            # the agent's own dot when a shadow is bound; "" keeps
            # non-shadowed rows unchanged.
            shadow = format_shadow_glyph(
                self._monitor.get_shadow_snapshot(snap.pane.pane_id)
            )

        # Truncate long window names for narrow display. 20, not 22: the
        # prioritized-mark pair (t1326) is always-on and costs two columns on
        # every row, and this pane lays out at ~38 usable columns — already
        # short of the worst-case row (● ◆! ≈ <name>  PROMPT 123s). The name's
        # tail is context; the mark is signal, so the tail is what gives way.
        name = snap.pane.window_name
        max_name = 20
        if len(name) > max_name:
            name = name[:max_name - 1] + "…"

        # Leftmost: a durable user annotation, deliberately outside the live
        # state cluster (dot / shadow / compare-mode), and first to survive
        # truncation.
        mark = format_mark_glyph(self._is_marked(snap))
        shadow_part = f" {shadow}" if shadow else ""
        line1 = f"{mark} {dot}{shadow_part} {glyph} {name}  {status}"

        # Optional task title line
        task_id = self._task_cache.get_task_id_for_pane(snap.pane)
        if task_id:
            info = self._task_cache.get_task_info(task_id, snap.pane.session_name)
            if info:
                title = info.title
                if len(title) > 30:
                    title = title[:29] + "…"
                line1 += f"\n  [dim]{title}[/]"
                # General pane list only — the docked followed-agent panel
                # (_own_agent_identity_text) is intentionally static and is left
                # untouched. Shown only for tasks that have a gate ledger.
                gates = self._gate_cache.summary_for(info)
                if gates:
                    line1 += f"\n  [dim]gates: {gates}[/]"
        return line1

    def _own_agent_identity_text(self, snap: PaneSnapshot) -> str:
        """Static identity line for the followed agent: window name + optional
        task title. Deliberately omits live status (idle/prompt/active) and the
        idle-detection glyph — the docked panel is built once and is not a
        refreshing status card like the general-list entries.

        **This includes COMPLETED (t1322), by explicit decision.** The followed
        agent's own task finishing is not surfaced here; the panel stays static.
        Use `ait monitor`, or the general list, to see a completed badge. Left
        this way so the omission reads as a choice, not an oversight.
        """
        name = snap.pane.window_name
        line = f"[bold]{name}[/]"
        task_id = self._task_cache.get_task_id_for_pane(snap.pane)
        if task_id:
            info = self._task_cache.get_task_info(task_id, snap.pane.session_name)
            if info:
                # Wrap the task description over up to two lines, sized to the
                # companion column (minus its padding + the 2-space indent).
                wrap_width = max(20, self._target_width - 4)
                wrapped = textwrap.wrap(info.title, wrap_width)[:2]
                if len(wrapped) == 2 and len(info.title) > sum(
                    len(w) for w in wrapped
                ) + 1:
                    wrapped[1] = wrapped[1][: max(1, wrap_width - 1)] + "…"
                for wline in wrapped:
                    line += f"\n  [dim]{wline}[/]"
        return line

    async def _maybe_build_own_agent_panel(self) -> None:
        """Populate the docked panel for the agent this minimonitor follows —
        ONCE. The followed agent is fixed for the minimonitor's lifetime, so its
        identity panel is static: it is not rebuilt on each refresh cycle and
        carries no live status badge (per the followed-agent UX).

        Retries each cycle only until the own-agent snapshot first resolves
        (tmux window-index detection can lag the first data refresh).
        """
        if self._own_panel_built:
            return
        own_snap = self._find_own_agent_snapshot()
        if own_snap is None:
            return  # not resolved yet — try again next cycle
        panel = self.query_one("#mini-own-agent", VerticalScroll)
        await panel.remove_children()
        await panel.mount_all([
            Static("[dim]── this agent ──[/]", classes="mini-own-header"),
            Static(self._own_agent_identity_text(own_snap), classes="mini-own-card"),
        ])
        self._own_panel_built = True

    async def _rebuild_pane_list(self) -> None:
        container = self.query_one("#mini-pane-list", VerticalScroll)
        # Clear existing content and wait for the prune to complete before
        # mounting new cards — otherwise focus restoration can race removal.
        await container.remove_children()

        # Show AGENT panes EXCEPT the followed agent (it lives in the docked
        # #mini-own-agent panel). Sort by (session_name, window_index,
        # pane_index) so session grouping is stable across refreshes;
        # single-session mode degrades to the legacy (window_index,
        # pane_index) order because every snapshot shares the same session.
        own_snap = self._find_own_agent_snapshot()
        own_pane_id = own_snap.pane.pane_id if own_snap else None
        agents = [
            s for s in self._snapshots.values()
            if s.pane.category == PaneCategory.AGENT
            and s.pane.pane_id != own_pane_id
        ]
        agents.sort(
            key=lambda s: (s.pane.session_name, s.pane.window_index, s.pane.pane_index)
        )

        multi_mode = bool(self._monitor and self._monitor.multi_session)
        widgets: list = []
        current_session: str | None = None

        for snap in agents:
            if multi_mode and snap.pane.session_name != current_session:
                current_session = snap.pane.session_name
                label = current_session or "?"
                widgets.append(Static(
                    f"[dim]\u2500\u2500 {label} \u2500\u2500[/]",
                    classes="mini-session-divider",
                ))

            widgets.append(
                MiniPaneCard(snap.pane.pane_id, self._agent_card_text(snap))
            )

        if widgets:
            await container.mount_all(widgets)

    # -- Key handling ----------------------------------------------------------

    def on_key(self, event) -> None:
        key = event.key

        # Let modal screens handle their own keys
        if isinstance(self.screen, ModalScreen):
            return

        if key == "tab":
            self._focus_sibling_pane()
            event.stop()
            event.prevent_default()
            return

        if key == "enter":
            self._send_enter_to_sibling()
            event.stop()
            event.prevent_default()
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
        """Move focus up/down within the general pane list."""
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

    def _find_sibling_pane_id(self) -> str | None:
        """Return the pane_id of the agent this minimonitor follows.

        Prefers the resolved followed-agent snapshot (pane-id exact) so that a
        shadow or other helper pane sharing the window is never mistaken for the
        agent (t986). Falls back to the first non-minimonitor pane in the window
        when no agent snapshot is available. Notifies and returns None on
        failure (not in tmux, tmux error, no sibling). Shared by the Tab focus
        handler and the Enter send handler.
        """
        own_snap = self._find_own_agent_snapshot()
        if own_snap is not None:
            return own_snap.pane.pane_id
        own_pane = os.environ.get("TMUX_PANE", "")
        if not own_pane or not self._own_window_id or self._monitor is None:
            self.notify("Not inside tmux", severity="warning")
            return None
        rc, stdout = self._monitor.tmux_run([
            "list-panes", "-t", self._own_window_id, "-F", "#{pane_id}",
        ])
        if rc != 0:
            self.notify("tmux list-panes failed", severity="error")
            return None
        other_panes = [
            line.strip() for line in stdout.strip().splitlines()
            if line.strip() and line.strip() != own_pane
        ]
        if not other_panes:
            self.notify("No other pane in this window", severity="warning")
            return None
        return other_panes[0]

    def _focus_sibling_pane(self) -> None:
        """Move tmux focus to the sibling pane in the minimonitor's window."""
        sibling = self._find_sibling_pane_id()
        if sibling is None or self._monitor is None:
            return
        rc, _ = self._monitor.tmux_run(["select-pane", "-t", sibling])
        if rc != 0:
            self.notify("select-pane failed", severity="error")

    def _send_enter_to_sibling(self) -> None:
        """Send an Enter keystroke to the sibling pane in our tmux window."""
        if self._monitor is None:
            self.notify("Monitor not ready", severity="warning")
            return
        sibling = self._find_sibling_pane_id()
        if sibling is None:
            return
        if not self._monitor.send_keys(sibling, "Enter"):
            self.notify("send-keys failed", severity="error")

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

    def _switcher_selected_session(self) -> str | None:
        """Pre-select the followed agent's session in the TUI switcher.

        The minimonitor follows one specific agent — the one sharing its tmux
        window, shown in the static, unselectable docked panel
        (``#mini-own-agent``). The switcher should open with *that* agent's
        project as the default, not whichever general-list card happens to be
        focused: the focused card cycles as the user navigates and is an agent
        the user is only glancing at, so keying the default project off it gave
        an unpredictable initial selection (t947). Returns ``None`` (attached
        session) when no followed agent is detected. ``_find_own_agent_snapshot``
        already filters on ``PaneCategory.AGENT``, so no category check is needed.
        """
        snap = self._find_own_agent_snapshot()
        if snap is None:
            return None
        return snap.pane.session_name or None

    def _switcher_narrow(self) -> bool:
        """Minimonitor lives in a narrow tmux pane — its switcher dialogs use
        the small-pane layout, matching the pick / sibling / concern dialogs
        that already pass ``narrow=True``."""
        return True

    # -- Actions ---------------------------------------------------------------

    def action_focus_sibling_pane(self) -> None:
        """No-op — Tab is handled in on_key. Exists for Binding registration."""

    def action_send_enter_to_sibling(self) -> None:
        """No-op — Enter is handled in on_key. Exists for Binding registration."""

    # -- Followed-agent kill / next (own agent only) ---------------------------

    def action_kill_own_agent(self) -> None:
        """Kill the agent this minimonitor follows (its own-window agent).

        Scoped to the followed agent regardless of which general-list card is
        focused. Because the minimonitor is a companion pane in that agent's
        window, killing the last non-companion pane collapses the whole window
        — which also tears down this minimonitor.
        """
        if self._monitor is None:
            self.notify("Monitor not ready", severity="warning")
            return
        snap = self._find_own_agent_snapshot()
        if snap is None:
            self.notify("No followed agent in this window", severity="warning")
            return
        task_info = None
        task_id = self._task_cache.get_task_id_for_pane(snap.pane)
        if task_id:
            task_info = self._task_cache.get_task_info(task_id, snap.pane.session_name)
        pane_id = snap.pane.pane_id
        self.push_screen(
            KillConfirmDialog(snap, task_info, show_preview=False),
            callback=lambda ok: self._on_own_kill_confirmed(ok, pane_id),
        )

    def _on_own_kill_confirmed(self, confirmed: bool | None, pane_id: str) -> None:
        if not confirmed or self._monitor is None:
            return
        snap = self._snapshots.get(pane_id)
        name = snap.pane.window_name if snap else pane_id
        ok, killed_window = self._monitor.kill_agent_pane_smart(pane_id)
        if ok:
            self._focused_pane_id = None
            # If the window collapsed, this minimonitor pane is being torn down
            # with it — the notify/refresh may never render. Otherwise drop the
            # killed card on the next refresh.
            if not killed_window:
                self.notify(f"Killed {name}")
                self.call_later(self._refresh_data)
        else:
            self.notify(f"Failed to kill {name}", severity="error")

    def action_pick_next_for_own(self) -> None:
        """Find and launch the next sibling task for the followed agent.

        Scoped to the followed agent (own-window), mirroring the full monitor's
        ``action_pick_next_sibling`` but resolving the target from the docked
        agent rather than the focused list card.
        """
        if self._monitor is None:
            self.notify("Monitor not ready", severity="warning")
            return
        snap = self._find_own_agent_snapshot()
        if snap is None:
            self.notify("No followed agent in this window", severity="warning")
            return
        task_id = self._task_cache.get_task_id_for_pane(snap.pane)
        if not task_id:
            self.notify("No task ID in window name", severity="warning")
            return
        sess = snap.pane.session_name
        self._task_cache.invalidate(task_id, sess)
        current_info = self._task_cache.get_task_info(task_id, sess)
        # If the task file is gone it was likely archived (Done) — still allow.
        current_title = current_info.title if current_info else f"(archived t{task_id})"
        current_status = current_info.status if current_info else "Done"

        result = self._task_cache.find_next_sibling(task_id, sess)
        if not result:
            self.notify("No ready siblings or children found", severity="warning")
            return
        suggested_id, suggested_title = result
        parent_id = self._task_cache.get_parent_id(task_id) or task_id

        pane_id = snap.pane.pane_id
        self.push_screen(
            NextSiblingDialog(
                task_id, current_title, current_status,
                suggested_id, suggested_title, parent_id,
                narrow=True,
            ),
            callback=lambda r: self._on_own_next_result(r, pane_id, task_id, sess),
        )

    def _on_own_next_result(
        self, result: tuple[str, str] | None, pane_id: str, task_id: str, sess: str
    ) -> None:
        if result is None:
            return
        action, payload = result
        if action == "pick":
            self._launch_pick_for_own(payload, pane_id, task_id, sess)
            return
        # action == "choose": payload is parent_id; open the sibling picker.
        siblings = self._task_cache.find_ready_siblings(task_id, sess)
        if not siblings:
            self.notify("No Ready siblings to choose from", severity="warning")
            return

        def _on_picked(sib_id: str | None) -> None:
            if sib_id:
                self._launch_pick_for_own(sib_id, pane_id, task_id, sess)

        self.push_screen(
            ChooseSiblingModal(payload, siblings, narrow=True), callback=_on_picked
        )

    def _launch_pick_for_own(
        self, target_id: str, pane_id: str, task_id: str, sess: str
    ) -> None:
        """Launch ``/aitask-pick <target_id>`` for the followed agent's session.

        Unlike the full monitor (which kills the current pane *before* launching
        because it lives in a separate window), the minimonitor shares the
        followed agent's window — killing it would tear down this minimonitor.
        So launch the next agent FIRST, then kill the current window per the
        same heuristic (parent-split-into-children / archived / Done).
        """
        if self._monitor is None:
            return
        snap = self._snapshots.get(pane_id)
        if snap is None:
            self.notify("Followed agent no longer exists", severity="warning")
            return
        # Read the status BEFORE the dialog opens: a task completing while
        # AgentCommandScreen is up must not flip the kill decision.
        current_info = self._task_cache.get_task_info(task_id, sess)
        is_parent_with_children = "_" not in task_id
        should_kill = (
            is_parent_with_children
            or not current_info
            or current_info.status == "Done"
        )
        self._launch_pick(
            target_id,
            self._root_for_snap(snap),
            pane_id if should_kill else None,
        )

    def _launch_pick(
        self, target_id: str, target_root: Path, kill_pane_id: str | None
    ) -> None:
        """Open the launch dialog for ``/aitask-pick <target_id>`` and run it.

        Shared by ``n`` (:meth:`_launch_pick_for_own`, which derives
        ``kill_pane_id`` from the followed task's status) and ``p``
        (:meth:`action_pick_task_by_number`, where the user ticks a checkbox) —
        one implementation so the two keys cannot drift.

        ``kill_pane_id`` is killed only **after** a successful launch. That
        order is load-bearing: unlike the full monitor, the minimonitor shares
        the followed agent's window, so killing first would tear this app down
        before the next agent exists.
        """
        if self._monitor is None:
            return
        full_cmd = resolve_dry_run_command(target_root, "pick", target_id)
        if not full_cmd:
            self.notify(
                f"Failed to resolve pick command for t{target_id}", severity="error"
            )
            return

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
            narrow=True,
        )

        def on_pick_result(pick_result):
            if isinstance(pick_result, TmuxLaunchConfig):
                # 1. Launch the incoming agent FIRST (new window) so it survives
                #    even if killing the current window tears down this app.
                _, err = launch_in_tmux(screen.full_command, pick_result)
                if err:
                    self.notify(f"Launch failed: {err}", severity="error")
                    return
                if pick_result.new_window:
                    maybe_spawn_minimonitor(pick_result.session, pick_result.window)
                self.notify(f"Launched agent for t{target_id}")
                # 2. Only now kill the outgoing agent, if the caller asked.
                if kill_pane_id and self._monitor is not None:
                    self._monitor.kill_agent_pane_smart(kill_pane_id)
                    self._focused_pane_id = None
            self.call_later(self._refresh_data)

        self.push_screen(screen, on_pick_result)

    def action_pick_task_by_number(self) -> None:
        """Pick any task by typing its number, then launch it (t1310).

        The end-of-run case ``n`` cannot serve: an agent reports the follow-up
        tasks it created, or the one to pick next, as bare numbers — and ``n``
        only ever resolves the followed pane's next *Ready sibling*. Two
        dialogs: a number prompt, then the task's details with an opt-in
        "kill followed agent" checkbox. The launch and the kill both go through
        the same :meth:`_launch_pick` ``n`` uses.
        """
        if self._monitor is None:
            # Guard at the ENTRY, not at launch: _launch_pick's own
            # `self._monitor is None` return is silent, so without this the
            # user would complete both dialogs and see nothing happen.
            self.notify("Monitor not ready", severity="warning")
            return
        snap = self._find_own_agent_snapshot()
        target_root = self._root_for_snap(snap) if snap else self._project_root
        sess = snap.pane.session_name if snap else self._session

        self.push_screen(
            TaskNumberInputModal(narrow=True),
            callback=lambda raw: self._on_pick_number_entered(
                raw, snap, target_root, sess
            ),
        )

    def _on_pick_number_entered(
        self, raw: str | None, snap: PaneSnapshot | None, target_root: Path, sess: str
    ) -> None:
        """Validate the typed id, resolve it, and open the confirm dialog."""
        if not raw:
            return  # cancelled
        target_id = raw.strip().lstrip("t")
        if not _PICK_TASK_ID_RE.fullmatch(target_id):
            # Validate BEFORE resolving: TaskInfoCache._resolve interpolates the
            # id into a `Path.glob` pattern, so a metacharacter ("12*") would
            # match an unrelated task file and the dialog would describe a
            # different task than the one `/aitask-pick <raw>` launches.
            self.notify(f"Not a task number: {raw.strip()!r}", severity="warning")
            return

        self._task_cache.invalidate(target_id, sess)
        info = self._task_cache.get_task_info(target_id, sess)
        if info is None:
            self.notify(f"Task t{target_id} not found", severity="warning")
            return
        blocking = self._task_cache.blocking_dependencies(info, sess)
        already = self._find_running_agent_line(target_id, sess)

        kill_label = None
        if snap is not None:
            own_id = self._task_cache.get_task_id_for_pane(snap.pane)
            own_info = None
            if own_id:
                # Refresh for the same reason blocking_dependencies does: this
                # status is what the user reads before ticking a box that closes
                # the agent down, and a stale "Done" would actively encourage
                # killing an agent that is still working.
                self._task_cache.invalidate(own_id, sess)
                own_info = self._task_cache.get_task_info(own_id, sess)
            own_status = own_info.status if own_info else "unknown"
            kill_label = (
                f"t{own_id or '?'} · {own_status} · {snap.pane.window_name}"
            )
        pane_id = snap.pane.pane_id if snap is not None else None

        self.push_screen(
            TaskPickConfirmDialog(
                info,
                kill_target_label=kill_label,
                already_running=already,
                blocking=blocking,
                narrow=True,
            ),
            callback=lambda result: self._on_pick_confirmed(
                result, target_id, target_root, pane_id
            ),
        )

    def _find_running_agent_line(self, target_id: str, sess: str) -> str | None:
        """Warning text when an agent for ``target_id`` is already running.

        Scoped to ``sess``: task ids come from the window name alone, so in
        multi-session mode an unscoped scan would match an unrelated ``t<id>``
        in another project. One tmux session maps to exactly one project root,
        so the session scope IS the project scope — the same rule
        :meth:`_find_own_agent_snapshot` uses.
        """
        for snap in self._snapshots.values():
            if snap.pane.category != PaneCategory.AGENT:
                continue
            if snap.pane.session_name not in ("", sess):
                continue
            if self._task_cache.get_task_id_for_pane(snap.pane) != target_id:
                continue
            return (
                f"⚠ t{target_id} is already running in this session, "
                f"window {snap.pane.window_index}:{snap.pane.window_name}"
            )
        return None

    def _on_pick_confirmed(
        self,
        result: tuple[bool, bool] | None,
        target_id: str,
        target_root: Path,
        pane_id: str | None,
    ) -> None:
        if not result:
            return
        _ok, kill = result
        kill_pane_id = None
        if kill and pane_id:
            if pane_id in self._snapshots:
                kill_pane_id = pane_id
            else:
                self.notify(
                    "Followed agent no longer exists — launching without kill",
                    severity="warning",
                )
        self._launch_pick(target_id, target_root, kill_pane_id)

    def action_launch_shadow(self) -> None:
        """Spawn the shadow companion agent for the followed coding agent.

        Builds ``/aitask-shadow <followed_pane_id> [<task_id>]`` and launches
        the ``shadow`` codeagent — by default a new pane in the followed
        agent's window, or a separate window when ``tmux.shadow_same_window``
        is false. The launcher passes only the pane id; the shadow skill
        captures the followed pane on demand. After spawn it stamps
        ``@aitask_shadow_target`` on the new pane (the t986_1 classifier that
        keeps the shadow out of agent lists and binds its lifecycle) and wires
        the followed agent's ``pane-died`` cleanup hook so the shadow dies with
        its agent.
        """
        if self._monitor is None:
            return
        snap = self._find_own_agent_snapshot()
        if snap is None:
            self.notify("No followed agent to shadow", severity="warning")
            return
        followed_pane = snap.pane.pane_id
        if not followed_pane:
            self.notify("Followed agent pane id unavailable", severity="warning")
            return
        # One shadow per followed agent (the @aitask_shadow_target option is the
        # lifecycle binding). Refuse a duplicate so the concern picker's reverse
        # lookup stays unambiguous by construction (t1037_4). Sync lookup — this
        # action is sync and already issues sync tmux_run calls.
        if find_shadow_pane(self._monitor, followed_pane):
            self.notify(
                "A shadow is already running for this agent", severity="warning"
            )
            return
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

        Same as ``action_launch_shadow`` (duplicate guard, specialized
        same-window split placement, ``@aitask_shadow_target`` stamp + cleanup
        hook) but opens the narrow ``AgentCommandScreen`` first so the user can
        confirm / change the code agent and model before the shadow starts —
        the ``E`` (shift-e) analogue of the switcher's t1148 ``X`` explore-pick
        shortcut. Cancelling the dialog launches nothing.

        The dialog's own returned placement is intentionally discarded: the
        shadow's split-target-the-followed-AGENT-pane geometry is richer than
        the dialog's tmux tab can express, so placement stays handler-controlled
        in ``_spawn_shadow`` and only the (possibly agent-overridden)
        ``full_command`` is consumed.
        """
        if self._monitor is None:
            return
        snap = self._find_own_agent_snapshot()
        if snap is None:
            self.notify("No followed agent to shadow", severity="warning")
            return
        followed_pane = snap.pane.pane_id
        if not followed_pane:
            self.notify("Followed agent pane id unavailable", severity="warning")
            return
        # Duplicate guard runs BEFORE opening the dialog (don't pop a picker just
        # to fail). Same sync reverse-lookup as action_launch_shadow.
        if find_shadow_pane(self._monitor, followed_pane):
            self.notify(
                "A shadow is already running for this agent", severity="warning"
            )
            return
        task_id = self._task_cache.get_task_id_for_pane(snap.pane)
        target_root = self._root_for_snap(snap)
        args = [followed_pane] + ([task_id] if task_id else [])
        full_cmd = resolve_dry_run_command(target_root, "shadow", *args)
        if not full_cmd:
            self.notify("Failed to resolve shadow command", severity="error")
            return
        agent_string = resolve_agent_string(target_root, "shadow")
        screen = AgentCommandScreen(
            "Shadow (pick agent)",
            full_cmd,
            "/aitask-shadow " + " ".join(args),
            project_root=target_root,
            operation="shadow",
            operation_args=args,
            default_agent_string=agent_string,
            narrow=True,
        )

        def on_shadow_result(result):
            # Confirm returns a TmuxLaunchConfig; its placement is discarded (see
            # docstring). Use screen.full_command (post-override), not the
            # captured full_cmd. None (cancel) / "run" launch nothing, mirroring
            # _launch_pick_for_own.
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

        Shared by the fire-and-forget ``e`` shortcut (``action_launch_shadow``)
        and the pick-agent ``E`` shortcut (``action_launch_shadow_pick``).
        ``full_cmd`` is the already-resolved shadow command (with any agent /
        model override baked in).

        Kept as a per-app method deliberately — it is **not** a pass-through
        seam. The two safety-critical decisions below (which pane the cleanup
        hook despawns, and whether the launch may steal the client's window)
        differ between the two apps, and inlining them at the two call sites in
        each app would replicate them four times instead of twice (t1216_4).
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
            # This minimonitor IS the followed agent's companion and shares its
            # window, so the cleanup hook must despawn US once the agent's window
            # holds no real agent — not the shadow, which job 1 already kills via
            # its @aitask_shadow_target marker.
            companion_pane=os.environ.get("TMUX_PANE") or None,
            # This client is already on the followed agent's window, so selecting
            # it is a no-op — keep the historical argv.
            select_window=True,
            notify=self.notify,
            schedule_refresh=lambda: self.call_later(self._refresh_data),
        )

    # -- Shadow concern picker (t1037_4) ---------------------------------------

    def _set_shadow_stale_banner(self, text: str) -> None:
        """Update the live staleness warning line; no-op if unmounted (t1104).

        Records the last-set text on ``_shadow_stale_banner_text`` (a test seam so
        the warning is assertable without a mounted DOM) and best-effort updates
        the ``#mini-shadow-stale`` Static — suppressed if the widget is not
        mounted (e.g. unit tests), matching the panel's best-effort UX.
        """
        self._shadow_stale_banner_text = text
        with contextlib.suppress(Exception):
            self.query_one("#mini-shadow-stale", Static).update(text)

    async def _update_shadow_freshness(
        self, shadow_pane: str, followed_pane: str
    ) -> None:
        """Mark the shadow's feedback stale if the followed agent moved on (t1104).

        The comparison itself is :func:`monitor_core.compute_shadow_staleness`
        (shared with the full monitor, t1216_1); this method owns only the
        minimonitor-specific banner policy. The tri-state it returns is what
        makes the display failure-safe: ``None`` means "could not tell" — an
        unreadable / malformed stamp, or a followed pane not observed yet — and
        must leave a standing warning exactly as it was. Only an explicit
        ``False`` clears the banner.
        """
        # Epsilon absorbs monitor's up-to-one-tick detection lag so a change the
        # shadow already saw (just noticed a beat later) is not mis-read as new.
        eps = max(2.0, float(getattr(self, "_refresh_seconds", 3)))
        stale, analyzed_at = await compute_shadow_staleness(
            self._monitor, shadow_pane, followed_pane, eps
        )
        if stale is None:
            return  # indeterminate — preserve prior state
        if stale:
            age = format_stale_duration(time.time() - analyzed_at)
            self._shadow_feedback_stale = True
            self._set_shadow_stale_banner(
                f"[bold]⚠ shadow feedback is stale — agent moved on "
                f"(analyzed {age} ago)[/]"
            )
        else:
            self._shadow_feedback_stale = False
            self._set_shadow_stale_banner("")

    async def action_pick_concerns(self) -> None:
        """Forward the shadow agent's concerns to the followed agent (via clipboard).

        Captures the bound shadow pane, parses its concern block, opens the picker
        modal, and on confirm copies the selected concerns (with a preamble) to the
        clipboard. The hotkey path uses the forgiving ``parse_concerns`` — the user
        deliberately asked to look now; the refresh-tick auto-offer uses the strict
        ``has_concern_block`` trigger instead (see :meth:`_maybe_offer_concerns`).
        """
        snap = self._find_own_agent_snapshot()
        if snap is None:
            self.notify("No followed agent in this window", severity="warning")
            return
        shadow_pane = await find_shadow_pane_async(self._monitor, snap.pane.pane_id)
        if not shadow_pane:
            self.notify(
                "No shadow agent running — press 'e' to launch one",
                severity="warning",
            )
            return
        text = await capture_shadow_text(shadow_pane)
        if text is None:
            self.notify("Could not read the shadow pane", severity="warning")
            return
        concerns = parse_concerns(text)
        if not concerns and block_head_truncated(text):
            # The block is there but the window started inside it. This is the
            # explicit user action, so pay for ONE much deeper re-capture rather
            # than reporting a false "no concerns" (t1187).
            deeper = await capture_shadow_text(
                shadow_pane, lines=_SHADOW_DEEP_RETRY_LINES
            )
            if deeper is not None:
                text = deeper
                concerns = parse_concerns(text)
            if not concerns:
                self.notify(_SHADOW_TRUNCATED_MSG, severity="warning")
                return
        if not concerns:
            # A block whose markers are ALL malformed parses to nothing, so the
            # bland "no concerns" message would be a lie — the shadow did emit a
            # block, none of it survived. Say that instead (t1274).
            lost = len(unrecovered_markers(text))
            if lost:
                self.notify(unparsed_concerns_msg(lost), severity="warning")
            else:
                self.notify("No concerns detected on the shadow pane")
            return
        # Warn on the actionable surface if the shadow's feedback is known-stale
        # (computed on the refresh tick — reuse it, no second live-sig spend).
        stale = bool(getattr(self, "_shadow_feedback_stale", None))
        self.push_screen(
            ConcernPickerModal(
                concerns,
                narrow=True,
                stale=stale,
                unrecovered=len(unrecovered_markers(text)),
            ),
            callback=self._on_concerns_picked,
        )

    def _on_concerns_picked(self, selected: list | None) -> None:
        """Modal callback: copy the selected concerns to the clipboard.

        ``selected`` is the chosen ``list[Concern]`` on confirm (or the full list
        on copy-all), or ``None``/empty on cancel — in which case nothing is
        written (no side effect before an explicit confirm).
        """
        if not selected:
            return
        payload = build_clipboard_payload(selected)
        copy_to_system_clipboard(self, payload)
        self.notify("Concerns copied to clipboard.")

    async def _maybe_offer_concerns(self) -> None:
        """Proactively hint when a fresh, complete concern block appears on the shadow.

        Strict trigger: ``has_concern_block`` (requires a *closing* fence + >=1
        concern) so a still-streaming, unclosed block does not fire mid-stream.
        De-duped per shadow pane on the *parsed* payload — not the raw capture —
        so unrelated pane churn around an unchanged block does not re-hint.
        Best-effort and event-loop safe: any capture/query failure silently skips
        the tick without touching the de-dup state.

        NOTE: if continuous detection proves noisy in live use, the documented
        fallback is to drop this and rely on the 'c' hotkey alone (verified by the
        t1037_5 manual-verification sibling).
        """
        snap = self._find_own_agent_snapshot()
        if snap is None or not snap.pane.pane_id:
            return
        shadow_pane = await find_shadow_pane_async(self._monitor, snap.pane.pane_id)
        if not shadow_pane:
            # No shadow: nothing can be stale — clear any standing warning.
            self._shadow_feedback_stale = None
            self._set_shadow_stale_banner("")
            return
        # Freshness (t1104) — independent of whether a concern block is present,
        # so the warning tracks staleness even when the block is unchanged.
        # Throttled to every other tick (halves the extra pane reads); a skipped
        # tick simply leaves the last computed state on screen. Cost-gated +
        # failure-safe inside.
        self._shadow_freshness_tick = getattr(
            self, "_shadow_freshness_tick", 0
        ) + 1
        if self._shadow_freshness_tick % 2 == 1:
            await self._update_shadow_freshness(shadow_pane, snap.pane.pane_id)
        text = await capture_shadow_text(shadow_pane)
        if text is None:
            return
        if not has_concern_block(text):
            # A block whose opening fence fell outside the window looks exactly
            # like "no concerns" to the strict predicate. Say so once per pane
            # instead of staying silent (t1187) — the user can then deepen the
            # window or press 'c', which retries deeper on its own.
            if block_head_truncated(text):
                if shadow_pane not in self._truncation_warned:
                    self._truncation_warned.add(shadow_pane)
                    self.notify(_SHADOW_TRUNCATED_MSG, severity="warning")
                return
            # A complete block whose markers are ALL malformed yields no concern,
            # so the strict predicate reads it as "nothing here" — the same class
            # of silent false negative as the truncation case, and equally worth
            # one warning per pane (t1274).
            lost = unrecovered_markers(text)
            if lost and shadow_pane not in self._unparsed_warned:
                self._unparsed_warned.add(shadow_pane)
                self.notify(unparsed_concerns_msg(len(lost)), severity="warning")
            return
        # A complete block arrived: re-arm the warnings for this pane.
        self._truncation_warned.discard(shadow_pane)
        self._unparsed_warned.discard(shadow_pane)
        concerns = parse_concerns(text)
        if not concerns:
            return
        payload = build_clipboard_payload(concerns)
        if self._last_concern_block_payload.get(shadow_pane) == payload:
            return
        self._last_concern_block_payload[shadow_pane] = payload
        stale_suffix = (
            " (⚠ STALE — agent moved on)"
            if getattr(self, "_shadow_feedback_stale", None) else ""
        )
        # Name the disposition split up front (t1274) so the toast already says
        # how much of the block is actually asking for action.
        actionable = sum(1 for c in concerns if needs_addressing(c))
        info = len(concerns) - actionable
        info_suffix = f" (+{info} informational)" if info else ""
        self.notify(
            f"Shadow raised {actionable} concern(s){info_suffix} — press 'c' to pick"
            + stale_suffix,
            severity="information",
        )

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

    def action_cycle_compare_mode(self) -> None:
        """Cycle the focused pane's idle-detection compare mode."""
        if self._monitor is None:
            self.notify("Monitor not ready", severity="warning")
            return
        pane_id = self._focused_pane_id
        if not pane_id:
            self.notify("Focus an agent pane first", severity="warning")
            return
        new_mode, is_default = self._monitor.cycle_compare_mode(pane_id)
        suffix = " (default)" if is_default else " (override)"
        self.notify(f"Idle detect: {new_mode}{suffix}", timeout=3)
        self.call_later(self._refresh_data)

    def action_toggle_multi_session(self) -> None:
        """Flip the multi-session view ON/OFF in memory.

        Mirrors MonitorApp.action_toggle_multi_session: in-memory only (no
        config write), invalidates the session cache so the first
        post-toggle refresh re-discovers, and schedules a refresh to repaint.
        """
        if self._monitor is None:
            return
        self._monitor.multi_session = not self._monitor.multi_session
        self._monitor.invalidate_sessions_cache()
        state = "ON" if self._monitor.multi_session else "OFF"
        self.notify(f"Multi-session {state}", timeout=3)
        self.call_later(self._refresh_data)

    def _show_task_info_for(self, snap: PaneSnapshot) -> None:
        """Open the task detail dialog for ``snap``'s pane, refreshing the cache.

        Shared by ``i`` (focused list card) and ``I`` (followed agent) — same
        dialog, two different target resolutions.
        """
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

    def action_show_task_info(self) -> None:
        """Show task detail dialog for the focused agent pane."""
        pane_id = self._get_focused_pane_id()
        if not pane_id:
            self.notify("Focus an agent pane first", severity="warning")
            return
        snap = self._snapshots.get(pane_id)
        if not snap:
            return
        self._show_task_info_for(snap)

    def action_show_own_task_info(self) -> None:
        """Show task detail dialog for the agent this minimonitor follows.

        The followed agent lives in the static, non-focusable #mini-own-agent
        panel and is excluded from the selectable list, so the focus-scoped
        ``i`` can never reach it — and since ``_auto_select_own_window`` always
        focuses a list card when one exists, a "nothing focused" fallback on
        ``i`` would be dead code whenever another agent is running (t1282).
        Hence its own key, scoped to the followed agent regardless of which
        list card is focused — the same resolution as ``action_kill_own_agent``
        / ``action_pick_next_for_own``.
        """
        snap = self._find_own_agent_snapshot()
        if snap is None:
            self.notify("No followed agent in this window", severity="warning")
            return
        self._show_task_info_for(snap)

    def action_switch_to_monitor(self) -> None:
        """Switch to the full monitor window with the companion agent focused.

        Writes the companion agent's window name to the tmux session
        environment so the full monitor can auto-focus the matching card on
        its next refresh, then selects (or creates) the monitor window.
        """
        if not os.environ.get("TMUX"):
            self.notify("Not inside tmux", severity="warning")
            return
        if not self._own_window_name:
            self.notify("Own window not detected yet", severity="warning")
            return

        if self._monitor is None:
            self.notify("Monitor not ready", severity="warning")
            return

        # Record the focus request on the tmux session so monitor_app can
        # pick it up on its next refresh.
        rc, _ = self._monitor.tmux_run([
            "set-environment", "-t", tmux_session_target(self._session),
            "AITASK_MONITOR_FOCUS_WINDOW", self._own_window_name,
        ])
        if rc != 0:
            self.notify("tmux set-environment failed", severity="error")
            return

        # Does the monitor window already exist in the session?
        rc, stdout = self._monitor.tmux_run([
            "list-windows", "-t", tmux_session_target(self._session),
            "-F", "#{window_name}",
        ])
        if rc != 0:
            self.notify("tmux list-windows failed", severity="error")
            return
        monitor_running = "monitor" in stdout.strip().splitlines()

        if monitor_running:
            rc, _ = self._monitor.tmux_run([
                "select-window", "-t",
                tmux_window_target(self._session, "monitor"),
            ])
            if rc != 0:
                self.notify("select-window failed", severity="error")
        else:
            # Trailing colon forces tmux to treat the target as a session.
            rc, _ = self._monitor.tmux_run([
                "new-window", "-t", tmux_window_target(self._session, ""),
                "-n", "monitor", "ait monitor",
            ])
            if rc != 0:
                self.notify("new-window failed", severity="error")


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
    parser = argparse.ArgumentParser(description="Compact tmux agent monitor TUI")
    parser.add_argument("--session", "-s", default=None, help="tmux session name")
    parser.add_argument("--interval", "-i", type=int, default=None, help="refresh interval in seconds")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    config = load_monitor_config(project_root)
    tmux_config = load_project_tmux_config(project_root)

    # Resolve session: CLI > current tmux session > config > default
    configured_session = tmux_config.get("default_session", "aitasks")
    if args.session:
        session = args.session
    else:
        session = _detect_tmux_session()
        if session is None:
            session = configured_session

    refresh_seconds = args.interval if args.interval is not None else tmux_config.get("monitor", {}).get("refresh_seconds", 3)

    # Same config key the spawner reads (agent_launch_utils.maybe_spawn_minimonitor);
    # the app re-pins its pane to this width on resize.
    mm_cfg = tmux_config.get("minimonitor", {})
    target_width = int(mm_cfg["width"]) if isinstance(mm_cfg, dict) and "width" in mm_cfg else 40

    app = MiniMonitorApp(
        session=session,
        project_root=project_root,
        refresh_seconds=refresh_seconds,
        capture_lines=config.get("capture_lines", 30),
        idle_threshold=config.get("idle_threshold", 5.0),
        agent_prefixes=config.get("agent_prefixes"),
        tui_names=config.get("tui_names"),
        compare_mode_default=config.get("compare_mode_default", "stripped"),
        target_width=target_width,
    )
    app.run()


if __name__ == "__main__":
    main()
