"""minimonitor_app - Compact TUI for monitoring tmux agent panes.

Designed to run as a narrow side-column (~40 columns) alongside code agent
windows in tmux. Shows all code agents with idle status. Unlike the full
monitor, it has no preview zone — just a compact agent list with status.

Usage:
    python minimonitor_app.py [--session NAME] [--interval SECS]
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import re
import subprocess
import sys
import textwrap
import time
from typing import NamedTuple
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
    find_shadow_pane_info_async,
    capture_shadow_text,
    capture_raw_tail,
    compute_shadow_staleness,
    compute_block_age_staleness,
    combine_staleness,
    refresh_shadow_phase_stamp,
    spawn_shadow,
    _SHADOW_DEEP_RETRY_LINES,
    _SHADOW_TRUNCATED_MSG,
)
from monitor import review_loop  # noqa: E402  (auto-recheck decision core, t1159_2)
from monitor.tmux_control import TmuxControlState  # noqa: E402
from monitor.monitor_shared import (  # noqa: E402
    _TASK_ID_RE, GateSummaryCache, TaskInfoCache, TaskDetailDialog,
    workflow_phase,
    KillConfirmDialog, NextSiblingDialog, ChooseSiblingModal,
    AgentMarksMixin, ColumnPickerModal, NewColumnTitleModal,
    ConcernBlockInspectModal, ConcernPickerModal, TaskNumberInputModal,
    TaskPickConfirmDialog, ShadowRejectionsMixin, STATE_STYLE_DONE,
    format_compare_mode_glyph, format_mark_glyph, format_pane_status,
    format_section_header, format_session_divider, format_shadow_glyph,
    format_state_dot, is_task_completed,
    format_shadow_stale_banner, format_staleness_detail,
    uncertified_round_block_msg, unparsed_concerns_msg,
)
from monitor.concern_parser import (  # noqa: E402
    block_head_truncated, block_region, build_clipboard_payload,
    contains_block_evidence,
    has_concern_block, has_invalid_round_header, is_metadata_only_block,
    needs_addressing,
    parse_block_meta, parse_concerns, unrecovered_markers,
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
    mark_monitor_pane,
    tmux_session_target,
    tmux_window_target,
    unmark_monitor_pane,
)
from agent_command_screen import AgentCommandScreen, resolve_skill_profile  # noqa: E402
import gate_ledger  # noqa: E402  (narrow gate-summary shed; same import path as monitor_core)

from rich.cells import cell_len, set_cell_size  # noqa: E402
from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import VerticalScroll  # noqa: E402
from textual.screen import ModalScreen  # noqa: E402
from textual.timer import Timer  # noqa: E402
from textual.widgets import Static  # noqa: E402


class ReadRecency(NamedTuple):
    """Read-recency verdict paired with the stamp that produced it (t1493).

    ``_update_shadow_freshness`` used to render the banner itself and kept
    ``analyzed_at`` local. The banner now lives in a separate every-tick step,
    which cannot say "analyzed Ns ago" — nor tell which signal drove a stale
    verdict — from the boolean alone. Binding the two into one value makes them
    unable to desync, which two loose attributes could not guarantee.
    """

    stale: bool | None
    analyzed_at: float | None


#: Read recency before anything has been resolved. Module-level so the property
#: default and the no-shadow reset are literally the same value.
_UNKNOWN_RECENCY = ReadRecency(None, None)


# Consecutive *verified* empty-window observations required before the companion
# closes itself (t1446). Any observation that is not a verified self-sighting —
# a tmux failure, an incompletely parsed listing, or a window that still holds
# another pane — resets the streak to 0, so the count only ever measures
# back-to-back positive evidence. At the default 3 s refresh this costs ~3 s of
# extra pane lifetime and buys immunity to a single-tick glitch. There is
# deliberately NO opposite budget: repeated failures never close the pane.
AUTO_CLOSE_CONFIRMATIONS = 2


# -- Row width budget ---------------------------------------------------------
#
# The one place this pane's column arithmetic lives (t1479):
#
#     target_width (default 40, `mm_cfg["width"]`)
#       − 2   MiniPaneCard `padding: 0 1`      ⇒ usable row      = _row_budget()
#       − 2   the "  " indent every detail row under the name line carries
#       = 36  at the default width             ⇒ detail content  = _detail_budget()
#
# Budgets are denominated in terminal **cells**, not code points — `cell_len`,
# never `len` — because a double-width character costs two columns.
_ROW_PADDING = 2      # MiniPaneCard `padding: 0 1`
_DETAIL_INDENT = 2    # the "  " prefix on the title / gate-phase rows
_MIN_PHASE_CELLS = 4  # below this a clipped phase carries no information


def _row_budget(target_width: int) -> int:
    """Cells available to a card's first (name/status) row.

    Not consumed by the gate-phase row below — it is here so **row 1's** owner
    (t1351, the row-width audit that replaces the `len()`-based name/command
    caps with cell-aware truncation) can adopt this arithmetic rather than
    restate it. The two tasks share this pane's budget; this module is where it
    is stated once.
    """
    return max(0, target_width - _ROW_PADDING)


def _detail_budget(target_width: int) -> int:
    """Cells available to a card's indented detail row (title, gate+phase).

    **Real geometry, clamped only at zero.** ``tmux.minimonitor.width`` is
    user-configurable and nothing validates a minimum, so a floor here (an
    earlier draft clamped to 8) would hand callers more cells than the pane
    has and the row would wrap — the one outcome this budget exists to
    prevent. Consumers are built for a tight budget: ``_clip`` answers 0 and 1
    without overshooting, and ``format_gate_phase_row`` sheds down to the bare
    ``<n>/<total>`` ratio. A pane too narrow to say anything renders nothing,
    which is honest; rejecting an absurd configured width belongs at the config
    seam, not here.
    """
    return max(0, target_width - _ROW_PADDING - _DETAIL_INDENT)


def _clip(text: str, budget: int) -> str:
    """Cell-aware terminator. ``Static`` *wraps* rather than clips, so anything
    that could exceed its budget must be cut here or it silently costs a whole
    extra row — the exact cost this card is trying to save.

    The return is ALWAYS ≤ ``budget`` cells, degenerate budgets included: the
    ellipsis itself costs a cell, so budgets 0 and 1 are answered before it is
    appended rather than overshooting by one.
    """
    if budget <= 0:
        return ""
    if cell_len(text) <= budget:
        return text
    if budget == 1:
        return "…"
    return set_cell_size(text, budget - 1).rstrip() + "…"


def format_gate_phase_row(phase: str, gates: str, budget: int) -> str:
    """The gate summary and the advisory workflow phase on ONE line (t1479).

    ``<PHASE><⏸> · <gate summary>`` — phase first (the coarser signal), counts
    second, and **no ``phase:`` / ``gates:`` labels**: they cost ~13 cells and
    say nothing that ``IMPLEMENT`` and ``3/4 pass`` do not already say in
    context. The full monitor merges the same two signals onto its status row;
    this is the narrow-column equivalent, and it is what turns a gated task's
    card from four rows into three.

    Either half may be empty (an ungated task has no summary, an unresolvable
    phase renders as ``""``) — then the other is rendered alone, and ``""``
    when both are.

    **Shed order when the join exceeds ``budget``** — the gate counts are the
    last thing to give way, because a failed or stale gate is precisely what
    must stay visible:

    1. abbreviate the gate tail (``1/4 pass, 1 pending, 1 failed`` →
       ``1/4 1p 1f``, :func:`gate_ledger.abbreviate_gate_summary`);
    2. clip the **phase** — it is coarse and re-derivable, the counts are not;
    3. drop the phase entirely once it would clip below
       :data:`_MIN_PHASE_CELLS`, where it carries no information anyway;
    4. terminal backstop — clip the abbreviated summary, reachable only if it
       alone exceeds the budget.

    At the default 40-column pane (36-cell budget) the worst realistic case,
    ``unknown (rec off) · 0/4 1p 1f 1s``, is 32 cells: rungs 2-4 exist so the
    failure mode is stated rather than emergent.
    """
    if not phase and not gates:
        return ""
    if not gates:
        return _clip(phase, budget)
    short = gate_ledger.abbreviate_gate_summary(gates)
    if not phase:
        for candidate in (gates, short):
            if cell_len(candidate) <= budget:
                return candidate
        return _clip(short, budget)
    for candidate in (gates, short):                    # 1. abbreviate the tail
        line = f"{phase} · {candidate}"
        if cell_len(line) <= budget:
            return line
    room = budget - cell_len(f" · {short}")             # 2. the phase gives way
    if room >= _MIN_PHASE_CELLS:
        return f"{_clip(phase, room)} · {short}"
    if cell_len(short) <= budget:                       # 3. drop the phase
        return short
    return _clip(short, budget)                         # 4. terminal backstop


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

# Headless board-column seam (t1377_1), shelled out to rather than imported: it
# owns the task-file write, and `monitor/` keeps its no-in-process-mutation
# stance. Timeout mirrors `_MARKS_CMD_TIMEOUT` — the wrapper takes no lock of its
# own, so this only has to bound a wedged child.
_BOARD_COLUMN_SH = _SCRIPT_DIR / "aitask_board_column.sh"
_BOARD_COLUMN_CMD_TIMEOUT = 20.0


# -- Main app -----------------------------------------------------------------

# The complete key surface of the app. Minimonitor renders no Footer — its
# 40-column companion layout surfaces EVERY binding here instead (the
# tui_conventions.md "surface the hint in the pane's own text" exception).
# Module-level so tests can pin hints/BINDINGS parity executably: a binding
# added without a hint line fails the audit test, keeping the convention's
# all-operations requirement true by construction (t1159_2 review round 7).
KEY_HINTS_TEXT = (
    "i:info  q:quit  tab:agent\n"
    "I:info (followed agent)\n"
    "s/\u2191\u2193:switch  enter:send\n"
    "d:detect (\u2248 strip, = raw)\n"
    "j:tui switcher  m:full monitor\n"
    "k:kill  n:next  e/E:shadow\n"
    "c:concerns  p:pick task\n"
    "L:auto-recheck loop\n"
    "M:multi-session  ?:edit keys\n"
    "space:mark ★ (followed agent)"
)


class MiniMonitorApp(
    AgentMarksMixin, ShadowRejectionsMixin, TuiSwitcherMixin, ShortcutsMixin, App
):
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

    /* Auto-recheck loop status (t1159_2). $warning, deliberately distinct
       from the $error stale banner above; empty text ⇒ 0 rows. */
    #mini-loop-status {
        dock: top;
        height: auto;
        background: $warning;
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

    /* No `color:` — the divider's style is single-sourced in
       monitor_shared.format_session_divider (t1449). */
    .mini-session-divider {
        height: 1;
        padding: 0 1;
    }

    /* Section header inside the pane list (currently only "other"). No `color:`
       or `text-style:` — both are single-sourced in
       monitor_shared.format_section_header (t1449), which is what keeps this
       rule and the session divider above deliberately different colours. */
    .mini-section-header {
        height: 1;
        padding: 0 1;
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
        Binding("space", "toggle_mark", "Mark followed agent", show=False),
        # show=False like every minimonitor binding: this app renders no
        # Footer — its 40-column companion layout surfaces every binding in
        # the #mini-key-hints Static instead (the tui_conventions.md
        # "surface the hint in the pane's own text" exception, justified in
        # p1159_2; the hints/bindings parity is test-pinned).
        Binding("L", "toggle_review_loop", "Auto-recheck loop", show=False),
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
        mark_pane: bool = False,
    ) -> None:
        super().__init__()
        self.current_tui_name = "minimonitor"
        # Only the production launcher (main()) passes mark_pane=True. Gating it
        # keeps a Textual run_test() mount — which inherits the running agent's
        # $TMUX_PANE — from stamping @aitask_monitor_kind on a live pane, the
        # same hazard the monitor's rename_window flag exists for (t1240/t1451).
        self._mark_pane = mark_pane
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
        # Back-to-back verified-empty observations (t1446) — see
        # AUTO_CLOSE_CONFIRMATIONS and _check_auto_close.
        self._empty_window_streak: int = 0
        self._own_window_id: str | None = None
        self._own_window_index: str | None = None
        self._own_window_name: str | None = None
        # The followed-agent docked panel is built once (static identity, no
        # per-cycle status refresh) — see _maybe_build_own_agent_panel.
        self._own_panel_built: bool = False
        # The docked card widget and the identity string frozen at build time,
        # so the per-tick repaint (t1383/t1420, _refresh_own_live_state) never needs a
        # snapshot it may no longer have.
        self._own_card: Static | None = None
        self._own_identity_text: str = ""
        # Tri-state, deliberately: True/False are the two mark glyphs, None means
        # "nothing markable here" (never an agent, or renamed off the `agent-`
        # prefix after the panel was built) and renders NO glyph. It is both the
        # current state and the repaint's change-detector, so the
        # agent → renamed transition is an ordinary state change rather than a
        # case the repaint has to special-case.
        self._own_mark_state: bool | None = None
        # Rendered phase line currently painted on the docked panel (t1420).
        self._own_phase_state: str = ""
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
        # Shadow-feedback READ RECENCY (t1104), verdict + the stamp that
        # produced it, written as one tuple (t1493). Tri-state verdict: None =
        # unknown (never resolved, or a transient capture/hash failure — do NOT
        # clear a prior warning on such a failure), False = current, True =
        # stale. The timestamp is carried because the banner reports "analyzed
        # Ns ago" from a step that no longer computes the verdict itself; a
        # loose second attribute could desync from it.
        self._shadow_read_recency: ReadRecency = ReadRecency(None, None)
        # COMBINED verdict (read recency joined with block age) — what every
        # user-facing surface reads. Kept separate from the read-recency
        # verdict above so each keeps one meaning and one provenance.
        self._shadow_stale_combined: bool | None = None
        # Throttle the staleness compare to every OTHER refresh tick (~6s at the
        # 3s default) to halve the extra pane reads; the concern auto-offer still
        # runs every tick. Odd counter ⇒ checks on the first tick a shadow is
        # present (responsive) then every second one.
        self._shadow_freshness_tick: int = 0
        # Auto-recheck loop (t1159_2): pure decision core + its display/input
        # state. The banner text seam mirrors _shadow_stale_banner_text.
        self._review_loop = review_loop.ReviewLoopController()
        self._loop_banner_text: str = ""
        # Work-classifier baseline: (content, awaiting_input_kind, pane_id,
        # history_size) of the last successful followed snapshot. PRESERVED
        # across indeterminate ticks (capture failed, agent still discovered)
        # so a response produced during the gap still classifies as work;
        # reset only on verified departure, pane replacement, or re-arm.
        self._loop_baseline: (
            tuple[str, str, str, int | None, tuple[int, int]] | None) = None
        # Raw shadow-tail hash ring for the readiness stability conjunct.
        self._loop_shadow_hash: int | None = None
        self._loop_shadow_hash_streak: int = 0
        # Monotonic stamp of the last serviced evidence tick. Overlapping
        # refreshes (t1111_4) invoke the service concurrently; without this
        # guard each invocation would advance the debounce streak and the
        # hash-stability ring, collapsing the "N consecutive refreshes"
        # guarantees into wall-clock-free counters (review round 2).
        self._loop_last_service_at: float | None = None
        # Sticky "a False verdict was recorded since the last committed
        # service tick" (review round 4). The recency cache updates on its
        # own cadence (throttle + overlapping refreshes), so the ONLY False
        # between two committed ticks can be observed by a throttled service
        # and then overwritten by True before the next committed one — a
        # FIRED controller would never see its re-arm edge. The writer sets
        # this; the next committed tick delivers False once and clears it.
        self._loop_stale_false_pending: bool = False
        # Prioritized-agent marks (t1326): cached reader + purge scheduling.
        self._init_agent_marks()

    def compose(self) -> ComposeResult:
        yield Static(id="mini-session-bar")
        # Live staleness warning for shadow feedback (t1104); empty ⇒ 0 rows.
        yield Static("", id="mini-shadow-stale")
        # Auto-recheck loop status (t1159_2); empty ⇒ 0 rows.
        yield Static("", id="mini-loop-status")
        yield VerticalScroll(id="mini-own-agent")
        yield VerticalScroll(id="mini-pane-list")
        yield Static(KEY_HINTS_TEXT, id="mini-key-hints")

    def on_mount(self) -> None:
        self._mount_time = time.monotonic()

        if not os.environ.get("TMUX"):
            self.query_one("#mini-session-bar", Static).update(
                "[bold red]Not inside tmux[/]"
            )
            return

        # Stamp our own pane so the single-instance guards can see us (t1451).
        # The spawner never does this — see mark_monitor_pane's docstring.
        if self._mark_pane:
            with contextlib.suppress(Exception):
                mark_monitor_pane("minimonitor")

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
        # Clear our pane marker on the normal-exit path. An abnormal exit is
        # covered by monitor_marker_state, which classifies a marker whose pid
        # is gone as stale so the guards ignore and self-heal it (t1451).
        if getattr(self, "_mark_pane", False):
            with contextlib.suppress(Exception):
                unmark_monitor_pane()
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
        # The one live element of that otherwise-static panel (t1383). Must run
        # after `_set_session_root_map` and `_refresh_marks` above, which
        # `_is_marked` reads, and after the build so there is a card to update.
        self._refresh_own_live_state()
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
        """Exit only on a POSITIVELY OBSERVED empty window (t1446).

        An observation the process could not actually make — a tmux timeout or
        transport failure, a listing that did not parse completely, a listing
        that does not even contain our own pane — is not evidence the window is
        empty. Those paths never exit and reset the confirmation streak, so only
        back-to-back positive sightings of solitude can close the companion.

        The original code read `discover_window_panes()` returning `[]` as "no
        other panes remain" and quit. On 2026-08-06 a machine-wide stall pushed
        the 5 s tmux timeout over the edge in every minimonitor at once and they
        all quit within the same second, abandoning the agents they were
        watching.
        """
        if self._monitor is None or self._own_window_id is None:
            return
        observed, panes = self._monitor.discover_window_panes(self._own_window_id)
        own_pane = os.environ.get("TMUX_PANE")
        if not observed or not own_pane:
            # tmux failed, or the listing dropped a record (a truncated sibling
            # row looks exactly like solitude), or we cannot identify our own
            # pane at all — nothing was verified.
            self._empty_window_streak = 0
            return
        pane_ids = {p.pane_id for p in panes}
        if own_pane not in pane_ids:
            # A complete listing that does not mention us is not a self-sighting.
            self._empty_window_streak = 0
            return
        if pane_ids - {own_pane}:
            self._empty_window_streak = 0  # other panes remain
            return
        self._empty_window_streak += 1
        if self._empty_window_streak >= AUTO_CLOSE_CONFIRMATIONS:
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

    def _find_own_window_snapshot(self) -> PaneSnapshot | None:
        """The pane this minimonitor sits beside, agent or not (t1382).

        The **identity / presentation** seam, deliberately NOT the action seam.
        ``_find_own_agent_snapshot`` stays strictly AGENT-scoped so ``k`` / ``n``
        / ``e`` / ``E`` / ``I`` keep refusing in a window renamed off the
        ``agent-`` prefix — that rename is how a user takes a window out of the
        agent rotation, and honouring it is the point. But the docked panel and
        the "don't list the followed pane twice" exclusion are about *which pane
        we are next to*, not about whether it is an agent, so they resolve here.

        Prefers the AGENT match, so a window holding both an agent and a stray
        shell still resolves to the agent; otherwise falls back to the
        lowest-``pane_index`` pane of the same window and session, which is
        deterministic across ticks. The fallback cannot pick a helper: shadow and
        companion panes never reach ``_snapshots``, and this minimonitor's own
        pane is dropped by ``TmuxMonitor.exclude_pane``.
        """
        agent = self._find_own_agent_snapshot()
        if agent is not None:
            return agent
        if not self._own_window_index:
            return None
        candidates = [
            snap for snap in self._snapshots.values()
            if snap.pane.window_index == self._own_window_index
            and snap.pane.session_name in ("", self._session)
        ]
        if not candidates:
            return None
        # Numeric where possible: pane_index is a string, so a plain min() would
        # order "10" before "2".
        return min(
            candidates,
            key=lambda s: (
                int(s.pane.pane_index) if s.pane.pane_index.isdigit() else 1 << 30,
                s.pane.pane_index,
            ),
        )

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
        done_str = f" [{STATE_STYLE_DONE}]{done_count}d[/]" if done_count > 0 else ""
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
                # Gate summary + advisory phase share ONE row (t1479): they
                # describe one thing between them, and two rows of a four-row
                # card is too much of this pane to spend on it. Either half may
                # be empty (ungated task / unresolvable phase); the row is
                # omitted only when both are.
                merged = format_gate_phase_row(
                    workflow_phase.render_phase_narrow(
                        self._phase_for_snap(snap, info)),
                    self._gate_cache.summary_for(info) or "",
                    _detail_budget(self._target_width),
                )
                if merged:
                    line1 += f"\n  [dim]{merged}[/]"
        return line1

    def _phase_for_snap(self, snap: PaneSnapshot, info) -> "workflow_phase.PhaseSignal":
        """Advisory phase for one pane: cached ledger half + this tick's live
        observation. Never gates anything — see aidocs/framework/shadow_agent.md."""
        return self._gate_cache.phase_for(
            info,
            screen_text=snap.content,
            awaiting_input=snap.awaiting_input,
            awaiting_input_kind=snap.awaiting_input_kind,
            agent=workflow_phase.agent_key_from_command(snap.pane.current_command),
        )

    def _other_card_text(self, snap: PaneSnapshot) -> str:
        """One-line card for an uncategorized (``PaneCategory.OTHER``) pane.

        The narrow analogue of ``MonitorApp._format_other_card_text``: no mark,
        state dot, shadow glyph, compare-mode glyph, status, task title or gate
        line — none of those mean anything for a pane that is not an agent, and
        the row has no columns to spare for them.

        Column budget, against the ~38 usable columns of this pane (the 40-wide
        ``target_width`` minus ``MiniPaneCard``'s ``padding: 0 1``):

            2  leading blanks (aligns under the agent rows' always-on mark glyph)
          + 1  ``○``
          + 1  space
          + 20 window name (same cap as ``_agent_card_text``)
          + 2  spaces
          + 10 current command
          = 36

        The window name is what gives way first, exactly as on the agent row.

        **The budget above assumes single-cell characters.** The caps are applied
        with ``len()``, which counts code points, so a name of 20 double-width
        characters occupies 40 cells and the row overflows (measured: 36 code
        points, 64 cells) and Rich clips it. This is inherited from
        ``_agent_card_text``, which caps its name the same way — so the fix is
        cell-width-aware truncation (``rich.cells.cell_len`` /
        ``set_cell_size``) applied to **both** rows, and it belongs with the
        row-width audit in t1351 rather than to this row alone.
        """
        name = snap.pane.window_name
        max_name = 20
        if len(name) > max_name:
            name = name[:max_name - 1] + "…"
        cmd = snap.pane.current_command
        max_cmd = 10
        if len(cmd) > max_cmd:
            cmd = cmd[:max_cmd - 1] + "…"
        return f"  [dim]○[/] {name}  [dim]{cmd}[/]"

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

    def _own_card_text(self, marked: bool | None, phase: str = "") -> str:
        """Docked-panel card text: the frozen identity line, the mark glyph, and
        the advisory workflow phase.

        The mark and the phase are the ONLY things this panel refreshes (t1383,
        t1420). That is a **narrowed** static-panel contract (t944 / t1133 /
        t1322), not an abandoned one: what stays excluded is live *agent status*
        — the state dot, the compare-mode and shadow glyphs, the COMPLETED
        badge. A mark is a durable **user annotation**, not status:
        ``format_mark_glyph``'s docstring already places it outside the
        live-state cluster, and it can change without the agent changing at all
        (set from ``ait monitor`` or another repo, or expired by TTL).

        The phase is admitted deliberately (t1420): this panel *is* the followed
        agent, and the shadow companion spawned from it picks its review mode
        from the phase — showing it only on the general list rows, which exclude
        the followed agent by construction, would put it everywhere except the
        one place it is for. It is advisory: it never gates a key, a spawn, or
        anything the user can ask the shadow.

        **Phase only — deliberately no gate summary (t1479).** When the list
        rows merged their gate counts onto the phase line, this panel did NOT
        follow: a gate summary is a second live signal, and admitting it would
        widen the narrowed contract above rather than keep it narrow. What it
        did adopt is the *rendering*: ``render_phase_narrow`` (label-free), so
        the phase reads the same on both surfaces of this 40-column pane instead
        of carrying a ``phase: `` label the rows next to it dropped.

        ``marked is None`` ⇒ there is nothing markable here (the window was
        never an agent, or was renamed off the ``agent-`` prefix after the panel
        was built) ⇒ **no glyph**, matching ``_other_card_text``. The glyph is
        present exactly when ``space`` would act, which is what keeps a
        read-only ☆ from appearing on a pane whose ``space`` refuses.

        **Width.** The glyph costs 2 columns on the name line, against ~38
        usable in the default 40-column pane; unlike the list rows, the docked
        panel does not truncate the name. Measured at 40 columns: names up to
        36 characters are unaffected, and real agent windows are far shorter
        (``agent-pick-1383``, ``agent-explore-2`` — 11-17 chars). Above 36 the
        name folds and the glyph is left on a line of its own. A non-breaking
        separator does NOT avoid that (Rich splits on ``\\s``, which matches
        U+00A0), and truncating here would drop the tail of the identity this
        panel exists to show — so the fold is accepted. Row-width tuning for
        this pane belongs to t1351.
        """
        line = (self._own_identity_text if marked is None
                else f"{format_mark_glyph(marked)} {self._own_identity_text}")
        if phase:
            line += f"\n  [dim]{phase}[/]"
        return line

    def _refresh_own_live_state(self) -> None:
        """Repaint the docked panel's ★/☆ and advisory phase when either changes.

        One set lookup per tick when nothing changed, and a single
        ``Static.update`` when something did. Four sources converge on this one
        code path: a local ``space``, a mark set from ``ait monitor`` or another
        repo, TTL expiry, and the followed window being **renamed out of the
        agent category** — which drops the state to ``None`` and removes the
        glyph, rather than stranding the last-rendered ★ on a pane that
        ``space`` now refuses.

        Only the glyph tracks reality: the identity text stays frozen through a
        rename, per ``_maybe_build_own_agent_panel``'s one-shot contract.
        """
        if self._own_card is None:
            return
        snap = self._find_own_agent_snapshot()
        marked = self._is_marked(snap) if snap is not None else None
        phase = self._own_phase_text(snap)
        # Tri-state compare: False (unmarked agent) and None (nothing markable)
        # are distinct, so the transition between them repaints. The phase is
        # compared as its RENDERED string, so a provenance change that does not
        # alter what the user sees costs no repaint.
        if marked == self._own_mark_state and phase == self._own_phase_state:
            return
        self._own_mark_state = marked
        self._own_phase_state = phase
        self._own_card.update(self._own_card_text(marked, phase))

    def _own_phase_text(self, snap) -> str:
        """Rendered advisory phase for the followed agent, or ``""``.

        Narrow (label-free) form, matching the list rows of the same pane — see
        ``_own_card_text`` for why this panel takes the phase and not the gate
        summary that now shares that line on the rows.

        Fails soft: any resolution problem yields no phase line rather than a
        stale or fabricated one, because this panel must never be broken by an
        advisory signal.
        """
        if snap is None:
            return ""
        task_id = self._task_cache.get_task_id_for_pane(snap.pane)
        if not task_id:
            return ""
        info = self._task_cache.get_task_info(task_id, snap.pane.session_name)
        if info is None:
            return ""
        return workflow_phase.render_phase_narrow(self._phase_for_snap(snap, info))

    async def _maybe_build_own_agent_panel(self) -> None:
        """Populate the docked panel for the agent this minimonitor follows —
        ONCE. The followed agent is fixed for the minimonitor's lifetime, so its
        identity panel is static: it is not rebuilt on each refresh cycle and
        carries no live status badge (per the followed-agent UX).

        Retries each cycle only until the own-window snapshot first resolves
        (tmux window-index detection can lag the first data refresh).

        Resolves through ``_find_own_window_snapshot`` (t1382), so a minimonitor
        started in a window renamed off the ``agent-`` prefix builds its panel at
        all — previously the AGENT-only lookup returned ``None`` on every cycle
        and the panel was never built. The header then reads "this window"
        instead of "this agent", so the uncategorized state is legible rather
        than looking like a missing agent. A window renamed *after* the panel
        built keeps the old header and name: the panel is one-shot by design and
        is not re-read. The prioritized-mark glyph is the sole exception — it is
        repainted per tick by ``_refresh_own_live_state`` (t1383, t1420).
        """
        if self._own_panel_built:
            return
        own_snap = self._find_own_window_snapshot()
        if own_snap is None:
            return  # not resolved yet — try again next cycle
        is_agent = own_snap.pane.category == PaneCategory.AGENT
        label = "this agent" if is_agent else "this window"
        # Freeze the identity here; only the mark glyph tracks reality after.
        self._own_identity_text = self._own_agent_identity_text(own_snap)
        self._own_mark_state = self._is_marked(own_snap) if is_agent else None
        self._own_phase_state = self._own_phase_text(own_snap)
        card = Static(
            self._own_card_text(self._own_mark_state, self._own_phase_state),
            classes="mini-own-card"
        )
        panel = self.query_one("#mini-own-agent", VerticalScroll)
        await panel.remove_children()
        await panel.mount_all([
            Static(f"[dim]── {label} ──[/]", classes="mini-own-header"),
            card,
        ])
        self._own_card = card
        self._own_panel_built = True

    async def _rebuild_pane_list(self) -> None:
        container = self.query_one("#mini-pane-list", VerticalScroll)
        # Clear existing content and wait for the prune to complete before
        # mounting new cards — otherwise focus restoration can race removal.
        await container.remove_children()

        # Two sections, mirroring MonitorApp._rebuild_pane_list: AGENT panes
        # first, then uncategorized (OTHER) ones under their own header (t1382).
        # Without the second section a window renamed off the `agent-` prefix
        # vanished from minimonitor entirely. PaneCategory.TUI is rendered by
        # neither, same as in the full monitor.
        #
        # Both sections exclude the followed pane \u2014 it lives in the docked
        # #mini-own-agent panel \u2014 and both resolve it through
        # `_find_own_window_snapshot`, so a renamed own window is excluded from
        # the OTHER section rather than being shown twice.
        #
        # Sort by (session_name, window_index, pane_index) so session grouping is
        # stable across refreshes; single-session mode degrades to the legacy
        # (window_index, pane_index) order because every snapshot shares the same
        # session.
        own_snap = self._find_own_window_snapshot()
        own_pane_id = own_snap.pane.pane_id if own_snap else None
        agents: list[PaneSnapshot] = []
        others: list[PaneSnapshot] = []
        for s in self._snapshots.values():
            if s.pane.pane_id == own_pane_id:
                continue
            if s.pane.category == PaneCategory.AGENT:
                agents.append(s)
            elif s.pane.category == PaneCategory.OTHER:
                others.append(s)

        sort_key = (
            lambda s: (s.pane.session_name, s.pane.window_index, s.pane.pane_index)
        )
        agents.sort(key=sort_key)
        others.sort(key=sort_key)

        multi_mode = bool(self._monitor and self._monitor.multi_session)
        widgets: list = []

        def append_group(snaps: list[PaneSnapshot], text_fn) -> None:
            """Mount one section's cards, with a session divider per group.

            Shared by both sections rather than copied: the divider rule (multi
            mode only, emitted when the session changes) has to stay identical
            for the two, and each section restarts its own grouping.
            """
            current_session: str | None = None
            for snap in snaps:
                if multi_mode and snap.pane.session_name != current_session:
                    current_session = snap.pane.session_name
                    label = current_session or "?"
                    widgets.append(Static(
                        format_session_divider(label),
                        classes="mini-session-divider",
                    ))
                widgets.append(MiniPaneCard(snap.pane.pane_id, text_fn(snap)))

        append_group(agents, self._agent_card_text)
        if others:
            # Only the OTHER section is headed. The agent section deliberately
            # has none \u2014 minimonitor never had one, and the session bar already
            # carries the agent count.
            widgets.append(Static(
                format_section_header(f"other ({len(others)})"),
                classes="mini-section-header",
            ))
            append_group(others, self._other_card_text)

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

        Prefers the resolved followed-pane snapshot (pane-id exact) so that a
        shadow or other helper pane sharing the window is never mistaken for the
        agent (t986). Falls back to the first non-minimonitor pane in the window
        when no snapshot is available. Notifies and returns None on
        failure (not in tmux, tmux error, no sibling). Shared by the Tab focus
        handler and the Enter send handler.

        Resolves through ``_find_own_window_snapshot`` (t1382), not the
        AGENT-only lookup: in a window renamed off the ``agent-`` prefix the
        strict resolver returns ``None`` and control fell through to the raw
        ``list-panes`` fallback, whose "first pane that is not me" rule can
        select the **shadow** pane — the exact hazard this docstring warns about.
        The snapshot path excludes shadows by construction.
        """
        own_snap = self._find_own_window_snapshot()
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
        suggested_id, suggested_title, suggested_kind = result
        parent_id = self._task_cache.get_parent_id(task_id) or task_id

        pane_id = snap.pane.pane_id
        self.push_screen(
            NextSiblingDialog(
                task_id, current_title, current_status,
                suggested_id, suggested_title, parent_id,
                narrow=True,
                suggested_followup_kind=suggested_kind,
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
                result, target_id, target_root, pane_id, sess
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
        result: tuple[str, object] | None,
        target_id: str,
        target_root: Path,
        pane_id: str | None,
        sess: str,
    ) -> None:
        if not result:
            return
        action, payload = result
        if action == "column":
            # The seam is a subprocess and this is a synchronous push_screen
            # callback, so the work has to move onto a worker.
            self.run_worker(
                self._open_column_picker(target_id, target_root, sess),
                exclusive=False,
                exit_on_error=False,
                group="board-column",
            )
            return
        kill = payload
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

    async def _run_board_column_cmd(self, args: list[str]) -> tuple[int, str]:
        """Run the headless board-column seam off the event loop.

        Mirrors :meth:`AgentMarksMixin._run_marks_cmd`, including its contract:
        **total — never raises, always terminates.** It is reached from a
        keypress handler, so an unhandled ``OSError`` from a missing wrapper
        would propagate out of the pick flow, and a child that never exits would
        wedge the worker forever. Both are normalised to ``(rc, "ERROR:…")`` and
        callers treat the result as data. Tests override this method.
        """
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                str(_BOARD_COLUMN_SH), *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await asyncio.wait_for(
                proc.communicate(), timeout=_BOARD_COLUMN_CMD_TIMEOUT
            )
        except asyncio.TimeoutError:
            # Kill the child, then reap it so it cannot become a zombie.
            try:
                proc.kill()
                await proc.wait()
            except Exception:  # noqa: BLE001 - already exited / unkillable
                pass
            return 1, (
                f"ERROR:board column command timed out after "
                f"{_BOARD_COLUMN_CMD_TIMEOUT}s"
            )
        except OSError as exc:
            return 1, f"ERROR:cannot run {_BOARD_COLUMN_SH.name}: {exc}"
        return proc.returncode or 0, out.decode("utf-8", "replace").strip()

    @staticmethod
    def _parse_column_lines(out: str) -> list[tuple[str, str, str]]:
        """`COLUMN:<id>|<colour>|<title>` lines → `(id, colour, title)`.

        Split on the first two separators only: the title is emitted last
        precisely because a configured title may legitimately contain ``|``.
        """
        columns: list[tuple[str, str, str]] = []
        for line in out.splitlines():
            if not line.startswith("COLUMN:"):
                continue
            parts = line[len("COLUMN:"):].split("|", 2)
            if len(parts) != 3:
                continue
            columns.append((parts[0], parts[1], parts[2]))
        return columns

    async def _open_column_picker(
        self, target_id: str, target_root: Path, sess: str
    ) -> None:
        """Read the board's columns and the task's current one, then pick.

        ``target_root`` rather than ``self._project_root``: in multi-session
        mode the followed pane may belong to a different project entirely.
        ``--task-dir`` is deliberately left at its default — a foreign project's
        layout is not discoverable from here.
        """
        root = str(target_root)
        rc, out = await self._run_board_column_cmd(
            ["list-columns", "--root", root, "--include-unordered"]
        )
        first = out.splitlines()[0] if out else ""
        if rc:
            self.notify(
                f"Board columns unavailable: {first or f'exit {rc}'}",
                severity="warning", markup=False,
            )
            return
        columns = self._parse_column_lines(out)
        if not columns:
            self.notify("No board columns configured", severity="warning")
            return

        rc, out = await self._run_board_column_cmd(
            ["current-column", "--root", root, "--task", target_id]
        )
        first = out.splitlines()[0] if out else ""
        if rc:
            # Defensive: the dialog already omits the button for a child id, so
            # `not_a_parent_task` should be unreachable from the UI. Surface the
            # stable reason token rather than prose either way.
            self.notify(
                f"Cannot move t{target_id}: {first or f'exit {rc}'}",
                severity="warning", markup=False,
            )
            return
        current = first[len("CURRENT:"):].rsplit("|", 1)[-1] if first else ""

        titles = {col_id: title for col_id, _c, title in columns}
        self.push_screen(
            ColumnPickerModal(target_id, columns, current=current, narrow=True,
                              allow_new=True),
            callback=lambda result: self._on_column_chosen(
                result, target_id, target_root, sess, current, titles
            ),
        )

    def _on_column_chosen(
        self,
        result: tuple[str, str | None] | None,
        target_id: str,
        target_root: Path,
        sess: str,
        current: str,
        titles: dict[str, str],
    ) -> None:
        # `result` is the picker's tagged tuple (t1377_3). Branch on the TAG,
        # never on truthiness: both ("existing", id) and ("new", None) are truthy,
        # so a truthiness test would send the create action down the move path.
        if not result:
            return
        action, col_id = result
        if action == "new":
            self.push_screen(
                NewColumnTitleModal(narrow=True),
                callback=lambda title: self._on_new_column_title(
                    title, target_id, target_root, sess
                ),
            )
            return
        title = titles.get(col_id, col_id)
        if col_id == current:
            # `markup=False`: Textual parses a notification's message as markup
            # by default, and the title is user-authored config. A column named
            # `Backlog [/]` raises MarkupError; `a[b]c` is silently swallowed to
            # `ac`. The picker escapes its own renderables, but a toast is a
            # separate sink and needed its own fix (t1377_2).
            self.notify(f"t{target_id} is already in {title}", markup=False)
            return
        self.run_worker(
            self._apply_column_move(target_id, target_root, sess, col_id, title),
            exclusive=False,
            exit_on_error=False,
            group="board-column",
        )

    def _on_new_column_title(
        self, title: str | None, target_id: str, target_root: Path, sess: str,
    ) -> None:
        """Callback for NewColumnTitleModal (t1377_3).

        A blank title cannot normally arrive — the modal rejects it in place and
        stays mounted — but the guard is kept so a programmatic dismissal cannot
        reach the seam with nothing to create.
        """
        if not title or not title.strip():
            return
        self.run_worker(
            self._create_and_move(target_id, target_root, sess, title.strip()),
            exclusive=False,
            exit_on_error=False,
            group="board-column",
        )

    async def _create_and_move(
        self, target_id: str, target_root: Path, sess: str, title: str,
    ) -> None:
        """Create a board column, then move the task into it in one gesture.

        The colour is deliberately not passed: the seam auto-assigns the next
        unused palette entry, which is what keeps this a single title prompt in a
        pane too small for a swatch palette.
        """
        rc, out = await self._run_board_column_cmd(
            ["create", "--root", str(target_root), "--title", title]
        )
        first = out.splitlines()[0] if out else ""
        if rc or not first.startswith("CREATED:"):
            self.notify(
                f"Create failed: {first or f'exit {rc}'}",
                severity="warning", markup=False,
            )
            return
        # Title LAST, so split on the first two separators only.
        parts = first[len("CREATED:"):].split("|", 2)
        if len(parts) != 3:
            self.notify(f"Create failed: malformed response {first}",
                        severity="warning", markup=False)
            return
        col_id, _color, new_title = parts
        moved = await self._apply_column_move(
            target_id, target_root, sess, col_id, new_title)
        if not moved:
            # The column exists even though the task did not move — say so, or
            # the user re-runs and creates a duplicate.
            self.notify(f"Column {new_title} was created but t{target_id} "
                        f"was not moved into it",
                        severity="warning", markup=False)

    async def _apply_column_move(
        self, target_id: str, target_root: Path, sess: str,
        col_id: str, title: str,
    ) -> bool:
        rc, out = await self._run_board_column_cmd(
            ["move", "--root", str(target_root),
             "--task", target_id, "--column", col_id]
        )
        first = out.splitlines()[0] if out else ""
        if rc or not first.startswith("MOVED:"):
            self.notify(
                f"Move failed: {first or f'exit {rc}'}",
                severity="warning", markup=False,
            )
            return False
        # `TaskInfoCache` would reject the stale entry on its (st_mtime_ns,
        # st_size) identity gate anyway, but a same-size edit inside the same
        # second is real, and every explicit gesture in this flow invalidates.
        self._task_cache.invalidate(target_id, sess)
        self.notify(f"Moved t{target_id} → {title}", markup=False)
        return True

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
            # Stamped before spawn_shadow returns, so a shadow that reads
            # `--phase` before the first refresh tick still sees the checkpoint
            # it was launched for (t1420).
            phase_signal=self._phase_signal_for_pane(snap),
        )

    def _phase_signal_for_pane(self, snap: PaneSnapshot):
        """Advisory phase for a pane, or ``None`` when it cannot be resolved.

        ``None`` is a legitimate answer that simply leaves the pane option
        unwritten — the per-tick re-stamp fills it in shortly after.
        """
        try:
            task_id = self._task_cache.get_task_id_for_pane(snap.pane)
            if not task_id:
                return None
            info = self._task_cache.get_task_info(task_id, snap.pane.session_name)
            if info is None:
                return None
            return self._phase_for_snap(snap, info)
        except Exception:
            return None

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

    def _restamp_shadow_phase(self, shadow_pane: str, snap: PaneSnapshot) -> None:
        """Push the followed agent's current advisory phase onto its shadow.

        Resolves the task the same way every display site does
        (``get_task_id_for_pane``), so t1389's move to stamped pane options stays
        a drop-in. A pane with no resolvable task, or any failure at all, simply
        leaves the previous stamp standing.
        """
        with contextlib.suppress(Exception):
            task_id = self._task_cache.get_task_id_for_pane(snap.pane)
            if not task_id:
                return
            info = self._task_cache.get_task_info(task_id, snap.pane.session_name)
            if info is None:
                return
            refresh_shadow_phase_stamp(
                self._monitor, shadow_pane, self._phase_for_snap(snap, info))

    @property
    def _shadow_feedback_stale(self) -> bool | None:
        """Read-recency verdict — the tri-state, without its timestamp (t1104).

        Read-only since t1493: the verdict and the ``analyzed_at`` that produced
        it are written together as :class:`ReadRecency`, so there is exactly one
        writable source and they cannot desync. Kept under the original name
        because it is the established read surface (tests, and t1159_2's planned
        review loop). Writers assign ``_shadow_read_recency``.
        """
        return getattr(self, "_shadow_read_recency", _UNKNOWN_RECENCY).stale

    def _shadow_freshness_eps(self) -> float:
        """Epsilon absorbing the monitor's up-to-one-tick detection lag.

        One definition, shared by the read-recency compare and the block-age
        compare — they answer questions about the same clock and must not
        disagree about how much jitter is tolerable.
        """
        return max(2.0, float(getattr(self, "_refresh_seconds", 3)))

    async def _update_shadow_freshness(
        self, shadow_pane: str, followed_pane: str
    ) -> None:
        """Refresh the shadow's READ-RECENCY verdict (t1104).

        The comparison itself is :func:`monitor_core.compute_shadow_staleness`
        (shared with the full monitor, t1216_1). The tri-state it returns is
        what makes the display failure-safe: ``None`` means "could not tell" —
        an unreadable / malformed stamp, or a followed pane not observed yet —
        and must leave the recorded verdict exactly as it was. Only an explicit
        ``True``/``False`` is recorded.

        **Banner writes are deliberately not here** (t1493). This method is
        throttled to every other tick because it costs a tmux ``get_pane_option``;
        the banner must also reflect *block age*, which is free to compute from
        the capture the auto-offer already takes every tick. So the banner is
        owned by :meth:`_refresh_shadow_stale_banner`, and this method's only job
        is to keep ``_shadow_read_recency`` current.
        """
        stale, analyzed_at = await compute_shadow_staleness(
            self._monitor, shadow_pane, followed_pane, self._shadow_freshness_eps()
        )
        if stale is None:
            return  # indeterminate — preserve prior state
        self._shadow_read_recency = ReadRecency(stale, analyzed_at)
        if stale is False:
            # Review-loop edge accumulator (t1159_2, review round 4): a False
            # recorded here may be overwritten before the loop's next
            # committed evidence tick; latch it so the edge is never lost.
            self._loop_stale_false_pending = True

    def _refresh_shadow_stale_banner(
        self, capture_text: str, followed_pane: str
    ) -> None:
        """Combine read recency with block age and repaint the banner (t1493).

        Runs on **every** tick, unlike the throttled read-recency compare, and
        costs no tmux traffic: ``capture_text`` is the capture the auto-offer
        already took, and ``get_last_change_wall`` is an in-process dict lookup.

        This is the surface that owns the *became-stale* transition. The
        auto-offer toast cannot: it returns early on an unchanged block (the
        round-qualified dedup), which is precisely the shape of the defect —
        the shadow re-reads, emits nothing, and the same block sits there
        ageing. A toast is a "new concerns arrived" announcement and re-firing
        it every tick would be wrong; a live banner is the right home.
        """
        recency = getattr(self, "_shadow_read_recency", _UNKNOWN_RECENCY)
        # Cost gate, mirroring the one inside `compute_shadow_staleness`: with
        # no block on the pane there is no age to compare, so do not query the
        # followed pane's last-change at all.
        last_change = None
        monitor = self._monitor
        if (contains_block_evidence(capture_text) and monitor is not None
                and hasattr(monitor, "get_last_change_wall")):
            with contextlib.suppress(Exception):
                last_change = monitor.get_last_change_wall(followed_pane)
        age = compute_block_age_staleness(
            capture_text, last_change, self._shadow_freshness_eps()
        )
        self._record_combined_staleness(
            combine_staleness(recency.stale, age),
            format_shadow_stale_banner(
                recency.stale, age, parse_block_meta(capture_text),
                recency.analyzed_at, time.time(),
            ),
        )

    def _record_combined_staleness(
        self, combined: bool | None, banner_text: str
    ) -> None:
        """Persist the combined verdict + banner under the preserve rule (t1493).

        The rule is *"never clear a standing **warning**"* — and a warning is
        specifically a recorded ``True``. Preserving a prior ``False`` as well
        would be wrong in the one direction that matters: a pane that had no
        block (verdict ``False``, correctly) and then grows a pre-round-header
        block moves to ``None``, and swallowing that transition would present
        an unverifiable block as current — precisely the defect this signal
        exists to remove. ``None`` over ``False`` is an escalation, not a
        clear, so it is always recorded.

        One method rather than the condition inlined at each site: the tick
        path and the picker path must apply the identical rule, and two copies
        of a three-way condition is how they would diverge.
        """
        if combined is None and getattr(self, "_shadow_stale_combined", None) is True:
            return  # would clear a standing warning — preserve it
        self._shadow_stale_combined = combined
        self._set_shadow_stale_banner(banner_text)

    # -- Auto-recheck loop (t1159_2) --------------------------------------

    def _set_loop_banner(self, text: str) -> None:
        """Update the loop status line; no-op if unmounted.

        Records the last-set text on ``_loop_banner_text`` (DOM-free test
        seam, mirroring ``_shadow_stale_banner_text``) and best-effort updates
        the ``#mini-loop-status`` Static.
        """
        self._loop_banner_text = text
        with contextlib.suppress(Exception):
            self.query_one("#mini-loop-status", Static).update(text)

    def _derive_agent_presence(self, snap: PaneSnapshot | None) -> bool | None:
        """Tri-state followed-agent presence from discovery-level liveness.

        Committed snapshots DROP panes whose content capture failed, so a
        missing snapshot alone is not departure (the discovery-facts seam
        exists precisely for this — see monitor_core `_record_discovery_facts`).
        True = snapshot present; False = the session was enumerated and the
        agent window is verifiably gone; None = capture failed while the
        agent is still discovered, or discovery itself is indeterminate.
        """
        if snap is not None:
            return True
        monitor = self._monitor
        window_name = self._own_window_name
        if monitor is None or not window_name:
            return None
        with contextlib.suppress(Exception):
            if (self._session, window_name) in monitor.last_discovered_agents():
                return None  # pane exists, its capture failed this cycle
            if self._session in monitor.last_enumerated_sessions():
                return False  # verified: enumerated, and the agent is gone
        return None

    def _loop_auto_disarm(self, reason: str) -> None:
        """Visible auto-disarm: banner off, baseline/ring cleared, one toast."""
        self._review_loop.disarm()
        self._loop_baseline = None
        self._loop_shadow_hash = None
        self._loop_shadow_hash_streak = 0
        self._set_loop_banner("")
        self.notify(f"Auto-recheck loop disarmed: {reason}", severity="warning")

    async def action_toggle_review_loop(self) -> None:
        """Arm/disarm the shadow auto-recheck loop (t1159_2).

        Arming refuses visibly on capability gaps on BOTH sides: the followed
        agent needs live prompt tiers (the trigger), the shadow agent needs a
        readiness detector (the delivery). Both are agent-capability gates —
        never phase gates (advisory-only contract).
        """
        ctrl = self._review_loop
        if ctrl.armed:
            ctrl.disarm()
            self._set_loop_banner("")
            self.notify("Auto-recheck loop disarmed")
            return
        snap = self._find_own_agent_snapshot()
        if snap is None or not snap.pane.pane_id:
            self.notify("Auto-recheck unavailable: no followed agent pane",
                        severity="warning")
            return
        followed_key = workflow_phase.agent_key_from_command(
            snap.pane.current_command)
        if not workflow_phase.live_tiers_available(followed_key):
            self.notify(
                f"Auto-recheck unavailable for "
                f"'{snap.pane.current_command or 'unknown'}' — no prompt "
                "detection yet (t1467)",
                severity="warning")
            return
        ok, shadow_pane, shadow_command = await find_shadow_pane_info_async(
            self._monitor, snap.pane.pane_id)
        if not ok:
            self.notify(
                "Auto-recheck unavailable: could not query the shadow pane — "
                "try again", severity="warning")
            return
        if not shadow_pane:
            self.notify(
                "Auto-recheck unavailable: no shadow pane — press 'e' to "
                "launch one", severity="warning")
            return
        shadow_key = workflow_phase.agent_key_from_command(shadow_command)
        if shadow_key not in review_loop.SHADOW_READY_DETECTORS:
            self.notify(
                f"Auto-recheck unavailable: shadow agent "
                f"'{shadow_command or 'unknown'}' has no readiness detection "
                "yet", severity="warning")
            return
        # Arm. pending_work covers an episode already pending at arm time via
        # the explicit user action; a fresh arm keeps the work latch closed so
        # an arm-time selection-only redraw cannot fire (review hardening 6).
        ctrl.arm(pending_work=(self._shadow_feedback_stale is True))
        self._loop_stale_false_pending = False  # pre-arm state, not ours
        # Seed the classifier baseline from the arm-time snapshot (review
        # hardening 9): a sub-tick response right after arming must still
        # classify as work on the first tick.
        self._loop_baseline = (snap.content, snap.awaiting_input_kind,
                              snap.pane.pane_id, snap.pane.history_size,
                              (snap.pane.width, snap.pane.height))
        self._loop_shadow_hash = None
        self._loop_shadow_hash_streak = 0
        self._loop_last_service_at = None
        self._set_loop_banner("⟳ auto-recheck ARMED")
        self.notify("Auto-recheck loop armed — press 'L' again to disarm")

    async def _service_review_loop(
        self, snap: PaneSnapshot | None, shadow_ok: bool,
        shadow_pane: str | None, shadow_command: str,
        tick_text: str | None,
    ) -> None:
        """Per-tick loop service, called from ALL THREE branches of
        `_maybe_offer_concerns` so absence is observed, not inferred.

        ``shadow_ok`` False means the lookup itself failed (or was not made
        this tick) — the loop pauses; only ``(True, None)`` is a verified
        shadow absence (review hardening 2).
        """
        ctrl = self._review_loop
        if not ctrl.armed:
            return

        # Serialize the evidence ticks (review round 2): overlapping
        # refreshes invoke this service concurrently, and each invocation
        # would otherwise count as its own debounce/hash-stability tick.
        # One committed evidence tick per half refresh period, minimum 1s.
        # MUST run before any evidence mutation (review round 3): a throttled
        # invocation that classified and advanced the baseline would consume
        # a work observation without ever delivering it to the controller —
        # the next committed tick would then see "no change" and the episode
        # would be permanently lost. A skipped invocation touches nothing.
        now_mono = time.monotonic()
        min_interval = max(
            1.0, 0.5 * float(getattr(self, "_refresh_seconds", 3)))
        if (self._loop_last_service_at is not None
                and now_mono - self._loop_last_service_at < min_interval):
            return
        self._loop_last_service_at = now_mono

        agent_presence = self._derive_agent_presence(snap)

        # Baseline maintenance + work classification (hardenings 6/8/9).
        # Only here, on a committed evidence tick — arm() seeds the baseline,
        # so no upkeep is needed while disarmed.
        work_signal = review_loop.UNKNOWN
        if snap is not None:
            base = self._loop_baseline
            if base is not None and base[2] != snap.pane.pane_id:
                base = None  # followed pane identity replaced
            if base is not None:
                work_signal = review_loop.classify_followed_change(
                    base[0], base[1], snap.content, snap.awaiting_input_kind,
                    snap.awaiting_input,
                    workflow_phase.agent_key_from_command(
                        snap.pane.current_command),
                    base[3], snap.pane.history_size,
                    base[4], (snap.pane.width, snap.pane.height),
                )
            self._loop_baseline = (snap.content, snap.awaiting_input_kind,
                                   snap.pane.pane_id, snap.pane.history_size,
                                   (snap.pane.width, snap.pane.height))
        elif agent_presence is False:
            self._loop_baseline = None
        # agent_presence None: baseline PRESERVED (hardening 8) — a response
        # produced during a capture-failure gap still classifies as work.

        # Mid-loop shadow-agent re-resolution (capability, not phase).
        shadow_key = ""
        if shadow_ok and shadow_pane:
            shadow_key = workflow_phase.agent_key_from_command(shadow_command)
            if shadow_key not in review_loop.SHADOW_READY_DETECTORS:
                self._loop_auto_disarm(
                    f"shadow agent '{shadow_command or 'unknown'}' has no "
                    "readiness detection")
                return

        # Shadow readiness over a raw tail + hash ring (only while armed —
        # this is the loop's one extra tmux read per tick). Snapshot the
        # lifecycle generation first: a disarm/re-arm during the await below
        # starts a NEW lifecycle, and this invocation's evidence (classified
        # against the OLD baseline) must never be injected into it (review
        # round 7).
        lifecycle_gen = ctrl.generation
        shadow_ready: bool | None = None
        raw_tail: str | None = None
        if shadow_ok and shadow_pane:
            raw_tail = await capture_raw_tail(self._monitor, shadow_pane)
            if ctrl.generation != lifecycle_gen:
                return  # superseded lifecycle — abandon, mutate nothing
            if raw_tail is None:
                self._loop_shadow_hash = None
                self._loop_shadow_hash_streak = 0
            else:
                tail_hash = hash(raw_tail)
                if tail_hash == self._loop_shadow_hash:
                    self._loop_shadow_hash_streak += 1
                else:
                    self._loop_shadow_hash_streak = 0
                self._loop_shadow_hash = tail_hash
            hash_stable = (raw_tail is not None
                           and self._loop_shadow_hash_streak >= 1)
            shadow_ready = review_loop.shadow_prompt_ready(
                raw_tail, shadow_key, hash_stable)

        # Unmounted apps (unit tests) have an empty screen stack; treat that
        # as "no modal" rather than crashing the service.
        try:
            modal_open = isinstance(self.screen, ModalScreen)
        except Exception:
            modal_open = False
        # Deliver a False the recency writer recorded between committed
        # ticks (review round 4): the controller must observe every recorded
        # transition or a FIRED state can wedge. Consumed exactly once, on a
        # committed tick only — throttled invocations returned above.
        # ORDERED delivery (review round 5): the latched False is OLDER than
        # this tick's evidence. When the current verdict has moved on (True /
        # None), replay the False in its own controller tick FIRST — with no
        # work signal, since that older instant carried none — so a WORK
        # classified this tick is not consumed by an artificial same-instant
        # True→False edge (the shadow never read that newer output).
        # Consume the latched edge ONLY when the controller will actually
        # process observations this tick (review round 6): an indeterminate
        # presence returns at the controller's presence guard before any
        # observation runs, and discarding the flag there would lose the
        # only False — FIRED would wedge after recovery. Verified absence
        # auto-disarms before observations too, and a dead loop's flag is
        # re-seeded at the next arm, so True/True is the consumption gate.
        can_consume = (agent_presence is True
                       and bool(shadow_ok and shadow_pane))
        stale_input = self._shadow_feedback_stale
        if self._loop_stale_false_pending and can_consume:
            self._loop_stale_false_pending = False
            if stale_input is False:
                pass  # the current tick itself delivers the False
            else:
                replay = ctrl.tick(
                    agent_present=agent_presence,
                    shadow_present=(None if not shadow_ok
                                    else bool(shadow_pane)),
                    awaiting_input=None,
                    stale=False,
                    work_signal=review_loop.UNKNOWN,
                    shadow_ready=None,
                    modal_open=modal_open,
                    now=now_mono,
                )
                if replay == review_loop.ACTION_AUTO_DISARM:
                    self._loop_baseline = None
                    self._loop_shadow_hash = None
                    self._loop_shadow_hash_streak = 0
                    self._set_loop_banner("")
                    self.notify(
                        "Auto-recheck loop disarmed: followed agent or "
                        "shadow pane is gone", severity="warning")
                    return
        action = ctrl.tick(
            agent_present=agent_presence,
            shadow_present=(None if not shadow_ok else bool(shadow_pane)),
            awaiting_input=(snap.awaiting_input if snap is not None else None),
            stale=stale_input,
            work_signal=work_signal,
            shadow_ready=shadow_ready,
            modal_open=modal_open,
            now=time.monotonic(),
        )

        if action == review_loop.ACTION_AUTO_DISARM:
            self._loop_baseline = None
            self._loop_shadow_hash = None
            self._loop_shadow_hash_streak = 0
            self._set_loop_banner("")
            self.notify("Auto-recheck loop disarmed: followed agent or "
                        "shadow pane is gone", severity="warning")
            return

        if action == review_loop.ACTION_FIRE:
            token = ctrl.delivery_token
            outcome, detail = await self._fire_shadow_recheck(
                shadow_pane, snap, shadow_key, raw_tail, tick_text, token)
            if outcome == "sent":
                ctrl.confirm_fire(token, time.monotonic())
            elif outcome == "not_ready":
                ctrl.abort_fire(token)
            else:  # transport failure — never leave the loop armed (hardening 1)
                self._loop_auto_disarm(detail)
                return

        # Banner reflects the post-decision state every tick.
        if ctrl.state == review_loop.FIRED:
            self._set_loop_banner(
                f"⟳ recheck #{ctrl.rounds_fired} sent — waiting for shadow")
        elif ctrl.state == review_loop.DELIVERING:
            self._set_loop_banner("⟳ auto-recheck: delivering…")
        elif ctrl.holding_for_shadow:
            self._set_loop_banner("⟳ waiting for shadow to settle")
        else:
            self._set_loop_banner("⟳ auto-recheck ARMED")

    async def _fire_shadow_recheck(
        self, shadow_pane: str, snap: PaneSnapshot | None, shadow_key: str,
        tick_raw_tail: str | None, tick_text: str | None, token,
    ) -> tuple[str, str]:
        """Verified two-step delivery into the SHADOW pane.

        Returns ``('sent' | 'not_ready' | 'failed', detail)``. Receives no
        followed pane id — structurally incapable of writing the followed
        pane (safety contract item 1). Enter is NEVER sent after a failed
        prompt write (it would submit foreign composer text or answer a
        dialog); readiness is revalidated on a fresh capture immediately
        before sending, with the delivery token re-checked after the await
        (review hardenings 1+4).
        """
        ctrl = self._review_loop
        fresh = await capture_raw_tail(self._monitor, shadow_pane)
        if not ctrl.delivery_valid(token):
            return "not_ready", "delivery superseded"
        # The fresh capture must be ready AND match the tail the decision was
        # made on — a shadow that changed between tick and delivery is not
        # the shadow we validated.
        hash_stable = (fresh is not None and tick_raw_tail is not None
                       and fresh == tick_raw_tail)
        if review_loop.shadow_prompt_ready(fresh, shadow_key,
                                           hash_stable) is not True:
            return "not_ready", "shadow not settled at delivery time"
        meta = parse_block_meta(tick_text) if tick_text else None
        expected_round = (meta.round + 1) if meta else None
        phase = None
        if snap is not None:
            with contextlib.suppress(Exception):
                task_id = self._task_cache.get_task_id_for_pane(snap.pane)
                if task_id:
                    info = self._task_cache.get_task_info(
                        task_id, snap.pane.session_name)
                    if info is not None:
                        phase = self._phase_for_snap(snap, info).phase
        prompt = review_loop.compose_recheck_prompt(phase, expected_round)
        monitor = self._monitor
        if monitor is None:
            return "failed", "no tmux monitor"
        if not monitor.send_keys(shadow_pane, prompt, literal=True):
            return ("failed",
                    "could not write the recheck prompt to the shadow pane")
        if not monitor.send_keys(shadow_pane, "Enter"):
            return ("failed",
                    "recheck text left in the shadow composer — submit or "
                    "clear it there manually")
        return "sent", prompt

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
            lost = unrecovered_markers(text)
            if lost:
                self.notify(unparsed_concerns_msg(len(lost)), severity="warning")
                # No picker means no banner to hang the `u` affordance off, so
                # open the raw view directly — the user pressed `c` deliberately
                # and this is the only thing left to show them (t1293).
                self.push_screen(
                    ConcernBlockInspectModal(lost, block_region(text) or "")
                )
            elif is_metadata_only_block(text):
                # A CERTIFIED metadata-only block is the shadow's record of a
                # clean round (t1159_1) — name the round instead of the
                # generic line. Strict on purpose: an unclosed header-only
                # stream may be about to emit items, and header+dropped-prose
                # is malformed output — neither is a clean round.
                meta = parse_block_meta(text)
                self.notify(
                    f"Clean review (round {meta.round}) — no concerns"
                )
            elif ((meta := parse_block_meta(text)) is not None
                    or has_invalid_round_header(text)):
                # A round header without certification: dropped non-item
                # content, a still-streaming header-only block, or a
                # Round:-shaped header that fails the grammar (meta None,
                # but the producer TRIED to emit metadata). "No concerns"
                # would hide emitted output — warn and show the raw block,
                # like the lost-markers case above.
                self.notify(
                    uncertified_round_block_msg(meta.round if meta else None),
                    severity="warning",
                )
                self.push_screen(
                    ConcernBlockInspectModal([], block_region(text) or "")
                )
            else:
                self.notify("No concerns detected on the shadow pane")
            return
        # Recomputed here, from THIS action's capture — never the tick cache
        # (t1493). The cached verdict describes the tick's capture; by now the
        # pane may carry a newer round, and `text` may have been replaced by the
        # deeper re-capture above. Labelling round 2's concerns with round 1's
        # freshness is the same snapshot incoherence the `block_meta=` wiring
        # below exists to prevent, so both must come from one capture. The user
        # pressed `c` deliberately, which is the same reasoning that already
        # pays for that deeper re-capture.
        eps = self._shadow_freshness_eps()
        read_stale, analyzed_at = await compute_shadow_staleness(
            self._monitor, shadow_pane, snap.pane.pane_id, eps
        )
        last_change = None
        if self._monitor is not None and hasattr(
            self._monitor, "get_last_change_wall"
        ):
            with contextlib.suppress(Exception):
                last_change = self._monitor.get_last_change_wall(snap.pane.pane_id)
        age = compute_block_age_staleness(text, last_change, eps)
        stale = combine_staleness(read_stale, age)
        block_meta = parse_block_meta(text)
        # Write-back, one rule per value. Read recency preserves on ITS own
        # indeterminate; the combined verdict goes through the shared
        # preserve rule (a standing True is never cleared, everything else is
        # recorded). A combined True driven by block age alone is a positive
        # finding and must be established even when read recency is None.
        if read_stale is not None:
            self._shadow_read_recency = ReadRecency(read_stale, analyzed_at)
        self._record_combined_staleness(
            stale,
            format_shadow_stale_banner(
                read_stale, age, block_meta, analyzed_at, time.time()
            ),
        )
        # Resolved and stashed here: the dismissal callback receives only the
        # result, so the followed pane — the sole source of a task id — is out
        # of reach by then (t1427_2).
        self._concern_pick_task_id = self._task_cache.get_task_id_for_pane(snap.pane)
        entries = await self._fetch_rejected_entries(self._concern_pick_task_id)
        self.push_screen(
            ConcernPickerModal(
                concerns,
                narrow=True,
                stale=stale,
                unrecovered=unrecovered_markers(text),
                raw_block=block_region(text) or "",
                rejected_entries=entries,
                store_unavailable=not self._concern_pick_task_id,
                block_meta=block_meta,
                stale_detail=format_staleness_detail(age, block_meta),
            ),
            callback=self._on_concerns_picked,
        )

    def _on_concerns_picked(self, result) -> None:
        """Modal callback: forward and/or persist the user's dispositions.

        ``result`` is a ``ConcernPickResult`` on confirm, or ``None`` on
        cancel — in which case nothing is written (no side effect before an
        explicit confirm). The body is shared with the full monitor via
        ``ShadowRejectionsMixin``; this app holds no pick guard to release.
        """
        self.apply_concern_pick_result(
            result, getattr(self, "_concern_pick_task_id", None)
        )

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
            # Review-loop service runs on EVERY branch (t1159_2): absence is
            # observed, never inferred. shadow_ok=False = "not looked" — the
            # loop pauses rather than reading it as a verified shadow absence.
            await self._service_review_loop(None, False, None, "", None)
            return
        shadow_ok, shadow_pane, shadow_command = await find_shadow_pane_info_async(
            self._monitor, snap.pane.pane_id)
        if not shadow_pane:
            # No shadow (offer path keeps the pre-t1159_2 fail-open collapse:
            # a failed lookup and a verified absence both land here — nothing
            # to show either way): nothing can be stale — clear any standing
            # warning. The loop service DOES discriminate via shadow_ok.
            self._shadow_read_recency = _UNKNOWN_RECENCY
            self._shadow_stale_combined = None
            self._set_shadow_stale_banner("")
            await self._service_review_loop(snap, shadow_ok, None, "", None)
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
        # Re-stamp the advisory phase on the same pass (t1420). Every tick, not
        # throttled with the freshness check: the shadow re-reads it on every
        # refetch, and a frozen hint is the one failure mode the pane-option
        # channel exists to avoid. Best-effort inside; never raises here.
        self._restamp_shadow_phase(shadow_pane, snap)
        text = await capture_shadow_text(shadow_pane)
        # Review-loop service, main path (t1159_2): before the text-None
        # return so a failed cleaned capture still services the tick.
        await self._service_review_loop(
            snap, shadow_ok, shadow_pane, shadow_command, text)
        if text is None:
            return
        # Combine read recency with block age and repaint, EVERY tick and before
        # any early return below: a pane whose block never changes is exactly
        # the case that must still go stale, and a pane with no block at all
        # must keep behaving as it did before block age existed (t1493).
        self._refresh_shadow_stale_banner(text, snap.pane.pane_id)
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
        # Round-qualified dedup (t1159_1): a repeat round re-raising the same
        # concerns is NEWS (the shadow re-reviewed and stands by them), so the
        # round header lifts the payload dedup. No header ⇒ the key is the bare
        # payload, byte-identical to the pre-header behavior.
        meta = parse_block_meta(text)
        dedup_key = (
            f"round={meta.round}@{meta.reviewed_at}\n{payload}" if meta
            else payload
        )
        if self._last_concern_block_payload.get(shadow_pane) == dedup_key:
            return
        self._last_concern_block_payload[shadow_pane] = dedup_key
        round_suffix = f" (round {meta.round})" if meta else ""
        # The COMBINED verdict, tri-state (t1493). This toast fires only when a
        # NEW block is announced — the dedup return above is deliberate — so it
        # reports the freshness of the block it is announcing. The
        # became-stale-later transition belongs to the live banner, which is the
        # only surface that re-renders on an unchanged block.
        combined = getattr(self, "_shadow_stale_combined", None)
        if combined is True:
            stale_suffix = " (⚠ STALE — agent moved on)"
        elif combined is None:
            stale_suffix = " (⚠ freshness unknown)"
        else:
            stale_suffix = ""
        # Name the disposition split up front (t1274) so the toast already says
        # how much of the block is actually asking for action.
        actionable = sum(1 for c in concerns if needs_addressing(c))
        info = len(concerns) - actionable
        info_suffix = f" (+{info} informational)" if info else ""
        self.notify(
            f"Shadow raised {actionable} concern(s){info_suffix} — press 'c' to pick"
            + round_suffix + stale_suffix,
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
        # The pane list has held non-agent cards since t1382, so "focused card ⇒
        # agent" is no longer an invariant. Idle detection only runs for AGENT
        # panes (`_apply_bookkeeping`), so an override set here for anything else
        # would be written and never read.
        snap = self._snapshots.get(pane_id)
        if snap is not None and snap.pane.category != PaneCategory.AGENT:
            self.notify(
                "Idle detection applies to agent panes only", severity="warning"
            )
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
        # Since t1382 the list can hold non-agent cards. Without this the call
        # would degrade incidentally to "No task ID in window name", which reads
        # like a broken agent rather than a pane that has no task by nature.
        if snap.pane.category != PaneCategory.AGENT:
            self.notify("Not an agent pane", severity="warning")
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

    async def action_toggle_mark(self) -> None:
        """Toggle the prioritized mark on the agent this minimonitor follows.

        Overrides ``AgentMarksMixin.action_toggle_mark``, which resolves through
        live focus. Deliberately NOT the focused list card, and deliberately not
        a *second* key beside the inherited one (t1383): a minimonitor is a
        companion pane bound to exactly one agent, so ``space`` here means "the
        agent I am watching" — one key, one target, whatever the list
        highlights. The full monitor keeps the inherited focus-resolved action;
        it follows nothing, so focus is its only target and it stays the way to
        mark any *other* agent.

        List rows still render ★/☆ so marks set from ``ait monitor`` or another
        repo remain visible here; they are simply read-only.

        Same resolution as ``action_kill_own_agent`` / ``action_pick_next_for_own``
        / ``action_show_own_task_info``, including the AGENT-only refusal in a
        window renamed off the ``agent-`` prefix.
        """
        snap = self._find_own_agent_snapshot()
        if snap is None:
            self.notify("No followed agent in this window", severity="warning")
            return
        await self._toggle_mark_for(snap)

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
        mark_pane=True,   # production launcher only — see MiniMonitorApp.__init__
    )
    app.run()


if __name__ == "__main__":
    main()
