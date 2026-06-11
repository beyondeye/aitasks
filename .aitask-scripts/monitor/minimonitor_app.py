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
from monitor.tmux_control import TmuxControlState  # noqa: E402
from monitor.monitor_shared import (  # noqa: E402
    _TASK_ID_RE, TaskInfoCache, TaskDetailDialog, KillConfirmDialog,
    NextSiblingDialog, ChooseSiblingModal, format_compare_mode_glyph,
    format_pane_status,
)
from monitor.desync_summary import get_desync_summary as _get_desync_summary  # noqa: E402
from tui_switcher import TuiSwitcherMixin  # noqa: E402
from shortcuts_mixin import ShortcutsMixin  # noqa: E402
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


# -- Main app -----------------------------------------------------------------

class MiniMonitorApp(TuiSwitcherMixin, ShortcutsMixin, App):
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
        Binding("j", "tui_switcher", "TUI switcher", show=False),
        Binding("q", "quit", "Quit", show=False),
        Binding("s", "switch_to", "Switch", show=False),
        Binding("i", "show_task_info", "Task Info", show=False),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("m", "switch_to_monitor", "Full Monitor", show=False),
        Binding("M", "toggle_multi_session", "Multi", show=False),
        Binding("d", "cycle_compare_mode", "Detect", show=False),
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
        self._mount_time: float = 0.0
        self._own_window_id: str | None = None
        self._own_window_index: str | None = None
        self._own_window_name: str | None = None
        # The followed-agent docked panel is built once (static identity, no
        # per-cycle status refresh) — see _maybe_build_own_agent_panel.
        self._own_panel_built: bool = False

    def compose(self) -> ComposeResult:
        yield Static(id="mini-session-bar")
        yield VerticalScroll(id="mini-own-agent")
        yield VerticalScroll(id="mini-pane-list")
        yield Static(
            "tab:agent  s/\u2191\u2193:switch  i:info\n"
            "k:kill  n:next  enter:send\n"
            "j:jump  r:refresh  q:quit\n"
            "m:full monitor  d:detect (\u2248 strip, = raw)",
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

        self._snapshots = await self._monitor.capture_all_async()
        # Refresh per-session project-root mapping so cross-session task data
        # resolves from the right project (free — uses TmuxMonitor's cached
        # session list).
        self._task_cache.update_session_mapping(
            self._monitor.get_session_to_project_mapping()
        )

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
        awaiting_count = sum(1 for a in agents if getattr(a, "awaiting_input", False))
        idle_count = sum(1 for a in agents
                         if a.is_idle and not getattr(a, "awaiting_input", False))

        awaiting_str = f" [bold magenta]{awaiting_count} awaiting[/]" if awaiting_count > 0 else ""
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
            bar.update(f"multi: {n}s · {total}a{awaiting_str}{idle_str}{desync}{state_badge}")
        else:
            bar.update(
                f"{self._session}  {total} agent{'s' if total != 1 else ''}{awaiting_str}{idle_str}{desync}{state_badge}"
            )

    def _agent_card_text(self, snap: PaneSnapshot) -> str:
        """Build the compact card text (status line + optional task title) for
        an agent snapshot.

        Shared by the docked followed-agent panel (``_rebuild_own_agent_panel``)
        and the general pane list (``_rebuild_pane_list``).
        """
        if getattr(snap, "awaiting_input", False):
            dot = "[bold magenta]●[/]"
        elif snap.is_idle:
            dot = "[yellow]●[/]"
        else:
            dot = "[green]●[/]"
        status = format_pane_status(snap)

        glyph = "?"
        if self._monitor is not None:
            mode = self._monitor.get_compare_mode(snap.pane.pane_id)
            is_override = self._monitor.is_compare_mode_overridden(snap.pane.pane_id)
            glyph = format_compare_mode_glyph(mode, is_override)

        # Truncate long window names for narrow display
        name = snap.pane.window_name
        max_name = 22
        if len(name) > max_name:
            name = name[:max_name - 1] + "…"

        line1 = f"{dot} {glyph} {name}  {status}"

        # Optional task title line
        task_id = self._task_cache.get_task_id(snap.pane.window_name)
        if task_id:
            info = self._task_cache.get_task_info(task_id, snap.pane.session_name)
            if info:
                title = info.title
                if len(title) > 30:
                    title = title[:29] + "…"
                line1 += f"\n  [dim]{title}[/]"
        return line1

    def _own_agent_identity_text(self, snap: PaneSnapshot) -> str:
        """Static identity line for the followed agent: window name + optional
        task title. Deliberately omits live status (idle/prompt/active) and the
        idle-detection glyph — the docked panel is built once and is not a
        refreshing status card like the general-list entries.
        """
        name = snap.pane.window_name
        line = f"[bold]{name}[/]"
        task_id = self._task_cache.get_task_id(snap.pane.window_name)
        if task_id:
            info = self._task_cache.get_task_info(task_id, snap.pane.session_name)
            if info:
                title = info.title
                if len(title) > 30:
                    title = title[:29] + "…"
                line += f"\n  [dim]{title}[/]"
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
        """Return the pane_id of the first non-minimonitor pane in our window.

        Notifies and returns None on failure (not in tmux, tmux error, no
        sibling). Shared by the Tab focus handler and the Enter send handler.
        """
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
        task_id = self._task_cache.get_task_id(snap.pane.window_name)
        if task_id:
            task_info = self._task_cache.get_task_info(task_id, snap.pane.session_name)
        pane_id = snap.pane.pane_id
        self.push_screen(
            KillConfirmDialog(snap, task_info),
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
        task_id = self._task_cache.get_task_id(snap.pane.window_name)
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

        self.push_screen(ChooseSiblingModal(payload, siblings), callback=_on_picked)

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
        current_info = self._task_cache.get_task_info(task_id, sess)

        target_root = self._root_for_snap(snap)
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
        )

        def on_pick_result(pick_result):
            if isinstance(pick_result, TmuxLaunchConfig):
                # 1. Launch the next sibling FIRST (new window) so it survives
                #    even if killing the current window tears down this app.
                _, err = launch_in_tmux(screen.full_command, pick_result)
                if err:
                    self.notify(f"Launch failed: {err}", severity="error")
                    return
                if pick_result.new_window:
                    maybe_spawn_minimonitor(pick_result.session, pick_result.window)
                self.notify(f"Launched agent for t{target_id}")
                # 2. Kill the current window per the full-monitor heuristic.
                is_parent_with_children = "_" not in task_id
                if (
                    is_parent_with_children
                    or not current_info
                    or current_info.status == "Done"
                ):
                    self._monitor.kill_agent_pane_smart(pane_id)
                    self._focused_pane_id = None
            self.call_later(self._refresh_data)

        self.push_screen(screen, on_pick_result)

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

    def action_refresh(self) -> None:
        """Force an immediate data refresh."""
        self.call_later(self._refresh_data)
        self.notify("Refreshed")

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
