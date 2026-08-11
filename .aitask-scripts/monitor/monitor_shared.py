"""monitor_shared - Shared widgets and utilities for monitor TUIs.

Provides reusable components used by both the full monitor (monitor_app.py)
and the mini monitor. Extracted to avoid code duplication.
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import tempfile
import time
from pathlib import Path

# Set up import paths before any local imports
_SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_SCRIPT_DIR / "lib"))

import agent_marks  # noqa: E402

# `PaneSnapshot` + the task-context symbols moved to monitor_core (t822_6);
# re-exported here so `from monitor.monitor_shared import TaskInfo, …` keeps
# working for monitor_app / minimonitor_app / tests.
# The advisory phase seam (t1420) — re-exported so both TUIs reach it the same
# way they reach the caches, without each re-deriving lib/ on sys.path.
from monitor.monitor_core import workflow_phase  # noqa: E402,F401

from monitor.monitor_core import (  # noqa: E402,F401
    PaneCategory,
    PaneSnapshot,
    _TASK_ID_RE,
    GateSummaryCache,
    TaskInfo,
    TaskInfoCache,
)

from typing import TYPE_CHECKING, NamedTuple, Sequence

from textual.binding import Binding  # noqa: E402
from textual.containers import Container, VerticalScroll  # noqa: E402
from textual.screen import ModalScreen  # noqa: E402
from textual.widgets import (  # noqa: E402
    Button, Checkbox, Input, Label, Markdown, Static,
)
from textual.app import ComposeResult  # noqa: E402
from rich.text import Text  # noqa: E402
from rich.markup import escape  # noqa: E402
# Both names live in `rich.color` — `rich.errors` does NOT export ColorParseError,
# and this import sits at module scope, so getting it wrong takes down every
# monitor TUI at startup rather than just the column picker (t1377_2).
from rich.color import Color, ColorParseError  # noqa: E402

try:
    from monitor.concern_parser import (
        build_clipboard_payload, concern_marker_line, needs_addressing,
    )
except ImportError:  # imported flat (tests may put MONITOR_DIR on sys.path)
    from concern_parser import (  # noqa: E402
        build_clipboard_payload, concern_marker_line, needs_addressing,
    )

from tui_clipboard import copy_to_system_clipboard  # noqa: E402

if TYPE_CHECKING:  # annotations only (PEP 563 via `from __future__`); no runtime cost
    from monitor.concern_parser import BlockMeta, Concern


# Dark background for terminal preview — hard-coded because we're rendering
# actual tmux terminal content (always dark) regardless of the TUI theme.
_DARK_BG_ANSI = "\033[48;2;26;26;26m"
_ANSI_RESET_RE = re.compile(r'\033\[0?m')
_ANSI_DEFAULT_BG_RE = re.compile(r'\033\[49m')


# Idle-detection compare-mode pseudo-icons used in agent cards across both
# the full monitor and the minimonitor. Single column wide so the compact
# minimonitor layout stays compact.
COMPARE_MODE_ICONS = {
    "stripped": "≈",   # ≈ — fuzzy / ANSI-stripped equality (default)
    "raw": "=",             # = — strict byte-equal
}


def format_compare_mode_glyph(mode: str, is_override: bool) -> str:
    glyph = COMPARE_MODE_ICONS.get(mode, "?")
    color = "yellow" if is_override else "dim"
    return f"[{color}]{glyph}[/]"


def is_task_completed(info) -> bool:
    """True when a pane's resolved task is finished (t1322).

    Accepts a ``TaskInfo`` or ``None``. Both signals are checked because
    ``aitask_archive.sh`` sets ``status: Done`` *before* it moves the file into
    ``aitasks/archived/``, so a monitor tick can land between the two and see
    either one alone.
    """
    if info is None:
        return False
    if str(getattr(info, "status", "")).strip() == "Done":
        return True
    abs_path = str(getattr(info, "task_file_abs", "") or "")
    return "/archived/" in abs_path.replace(os.sep, "/")


# Agent-state markup styles. Named here (t1453) because the DONE style was
# previously duplicated as a literal across five call sites in three files,
# which is how one wrong colour name spread unnoticed through both monitors.
# The two `── … ──` rule styles live further down (SESSION_DIVIDER_STYLE,
# SECTION_HEADER_STYLE); all five must stay mutually distinct.
STATE_STYLE_PROMPT = "bold magenta"

#: COMPLETED/DONE. Spelled as a **hex literal, not a colour name**: these markup
#: spans are parsed by Textual, whose palette is CSS colour names — it does NOT
#: know Rich's xterm names, and an unknown name fails *silently* rather than
#: raising. `[bold dodger_blue1]` parsed fine and then painted default
#: foreground with the `bold` dropped, so DONE never once rendered blue, and no
#: span-level assertion could see it (the span keeps the unresolved string).
#: Only a composited-screen check catches that — see
#: tests/test_markup_colour_contract.py. #1e90ff is CSS `dodgerblue`, the shade
#: the old name intended; plain CSS `blue` is #000080, far too dark on the
#: #1a1a1a card.
STATE_STYLE_DONE = "bold #1e90ff"

STATE_STYLE_IDLE = "yellow"
STATE_STYLE_ACTIVE = "green"


def _state_color(snap: PaneSnapshot, completed: bool = False) -> str:
    """The single definition of the state→color mapping (t1133, t1322):
    PROMPT (awaiting_input) > COMPLETED > IDLE > active, as
    :data:`STATE_STYLE_PROMPT` / :data:`STATE_STYLE_DONE` /
    :data:`STATE_STYLE_IDLE` / :data:`STATE_STYLE_ACTIVE`. Shared by the status
    badge, the agent dot, and the shadow glyph.

    ``completed`` is an explicit opt-in parameter and is never inferred here:
    it is a property of the pane's *task*, which a ``PaneSnapshot`` does not
    carry, and a shadow pane has no task of its own — inferring it would make
    :func:`format_shadow_glyph` colour shadows by their followed agent's task
    state. A completed agent parked on a final prompt still reads PROMPT, which
    is actionable now.
    """
    if getattr(snap, "awaiting_input", False):
        return STATE_STYLE_PROMPT
    if completed:
        return STATE_STYLE_DONE
    if snap.is_idle:
        return STATE_STYLE_IDLE
    return STATE_STYLE_ACTIVE


def format_state_dot(snap: PaneSnapshot, completed: bool = False) -> str:
    """The agent row's own status dot ``●``, colored by state (t1133 — was
    previously duplicated inline in monitor_app / minimonitor_app)."""
    return f"[{_state_color(snap, completed)}]●[/]"


# Shadow-status glyph (t1133): a deliberately different shape from the agent's
# own ● so the pair "agent state + its shadow's state" reads at a glance.
SHADOW_GLYPH = "◆"  # ◆
SHADOW_CONCERN_GLYPH = "!"  # appended to ◆ when the shadow has fresh concerns


def format_shadow_glyph(
    shadow_snap: PaneSnapshot | None, *, has_concerns: bool = False
) -> str:
    """Colored ``◆`` for a bound shadow's state, or ``""`` when the agent has
    no live shadow — callers render nothing (no placeholder), keeping
    non-shadowed rows byte-identical to the pre-t1133 output.

    No ``completed`` parameter: a shadow is an advisory companion with no task
    of its own, so it can never be COMPLETED and must never be rendered in the
    completed colour (t1322). Pinned by a test.

    ``has_concerns`` (t1216_3) appends :data:`SHADOW_CONCERN_GLYPH` for an agent
    whose shadow has emitted a concern block the user has not been offered yet.
    Keyword-only and defaulting to ``False`` so every existing call site is
    unchanged, and applied INSIDE the ``None`` guard so a non-shadowed row stays
    byte-identical whatever the flag says. It shares the state colour rather
    than adding a span: one marker, one style run.
    """
    if shadow_snap is None:
        return ""
    body = SHADOW_GLYPH + (SHADOW_CONCERN_GLYPH if has_concerns else "")
    return f"[{_state_color(shadow_snap)}]{body}[/]"


# Prioritized-agent mark (t1326): the user's own durable annotation, shaped
# distinctly from ● (live state) and ◆ (shadow state) so the row still reads at
# a glance. ☑/☐ was rejected — it already means "selected for this action" in
# ConcernPickerModal further down this module.
MARK_GLYPH = "★"        # prioritized
MARK_EMPTY_GLYPH = "☆"  # not prioritized


def format_mark_glyph(marked: bool) -> str:
    """Always-on ``★``/``☆`` pair for the user's prioritized-agent mark.

    Unlike :func:`format_shadow_glyph`, this NEVER returns ``""`` — the pair is
    always-on by explicit decision (the t1004 convention, cf. the board's and
    brainstorm's ☑/☐), so an unmarked agent reads as *deliberately unmarked*
    rather than as a row that forgot to render one. That costs two columns on
    every row, which is paid for in the minimonitor by a shorter name budget.

    **Bold white, deliberately NOT the repo-wide marked=bold-yellow convention**
    (``brainstorm/widgets.py``, ``_ConcernRow.render`` below). Those marks live
    in pickers, where nothing else on the row is coloured by state. This one
    sits two columns from the agent's ``●``, and :func:`_state_color` paints
    that dot **yellow for IDLE** — so a yellow ★ beside a yellow ● would read as
    one state cluster and invite "is that agent idle, or is it flagged?". White
    belongs to no state in the ladder (magenta / blue / yellow / green),
    which is exactly what makes it legible as *user intent* rather than status.
    """
    if marked:
        return f"[bold white]{MARK_GLYPH}[/]"
    return f"[dim]{MARK_EMPTY_GLYPH}[/]"


# Repo/session divider (t1449): in multi-session mode each tmux session is one
# repo/project, so this rule is the repo boundary in the agent list.
#
# Bold cyan, deliberately NOT `dim`: `dim` is what the task-title line under
# every agent card uses, so a dim divider read as one more task title and the
# repo grouping vanished. Cyan also belongs to no state in the ladder
# (magenta / blue / yellow / green) and is not the ★ mark's white,
# which is what makes it legible as *structure* rather than status.
SESSION_DIVIDER_STYLE = "bold cyan"


def format_session_divider(label: str) -> str:
    """The ``── <session> ──`` repo-boundary rule, styled once for both TUIs.

    Callers own their own leading indent (the full monitor indents by two
    columns; minimonitor pads via CSS) but never the style — that is the point
    of this seam.
    """
    return f"[{SESSION_DIVIDER_STYLE}]── {label} ──[/]"


# Pane-list section header (t1449): the `── other (N) ──` rule that heads the
# uncategorized section. Same glyph shape as the repo divider above, so it needs
# its own colour or the two read as one kind of boundary — but a DIFFERENT one,
# because cyan has to keep meaning "repo boundary" and nothing else.
#
# A light violet, free in both agent lists: it is not #1e90ff (DONE) and
# sits far enough from magenta (PROMPT) to stay separable. Bold lives here
# rather than in CSS so the whole style is one string.
#
# Spelled as a **hex literal, not a colour name**: these markup spans are parsed
# by Textual, whose palette is CSS colour names — it does NOT know Rich's xterm
# names. `[bold medium_purple1]` parses without error and then silently paints
# default-foreground, which no span-level assertion can see (the span keeps the
# unresolved string). Only a composited-screen check catches it; there is one in
# tests/test_monitor_session_divider.py for exactly this reason.
SECTION_HEADER_STYLE = "bold #af87ff"


def format_section_header(label: str) -> str:
    """The ``── other (N) ──`` section rule, styled once.

    Deliberately NOT :data:`SESSION_DIVIDER_STYLE`: a section boundary and a
    repo boundary are different things, and the shared ``── … ──`` shape is
    exactly why they must not share a colour.
    """
    return f"[{SECTION_HEADER_STYLE}]── {label} ──[/]"


#: The locked writer. Readers go straight to the JSON (see AgentMarksMixin).
_MARKS_SH = _SCRIPT_DIR / "aitask_agent_marks.sh"

#: Seconds between materializing purges. The render path filters expired and
#: dead marks every tick for free; this only bounds the file's growth, so it
#: does not need to be frequent.
_MARKS_PURGE_INTERVAL = 600.0

#: Hard ceiling on a single wrapper invocation. Above the wrapper's own lock
#: timeouts (2s toggle / 10s purge) so a contended-but-healthy writer reports
#: LOCK_BUSY itself rather than being killed mid-write.
_MARKS_CMD_TIMEOUT = 20.0

#: The shadow concern-rejection store's single writer/reader (t1427_1).
_REJECTED_SH = _SCRIPT_DIR / "aitask_shadow_rejected.sh"

#: Same rule as :data:`_MARKS_CMD_TIMEOUT`: above the helper's own mutation lock
#: timeout (10s) so a contended-but-healthy writer gets to report LOCK_BUSY
#: itself instead of being killed mid-write and blamed for a timeout.
_REJECTED_CMD_TIMEOUT = 20.0


class AgentMarksMixin:
    """Prioritized-agent marks for a monitor TUI (t1326).

    Mixed into both ``MonitorApp`` and ``MiniMonitorApp``. Requires from the
    host app: ``_monitor``, ``_snapshots``, ``_get_focused_pane_id()``,
    ``notify()``, ``call_later()`` and ``_refresh_data()``.

    Reads are lock-free and direct; the single writer is ``_MARKS_SH``, which
    holds the ``registry_lock.sh`` mutex.
    """

    def _init_agent_marks(self) -> None:
        """Call from ``__init__``."""
        self._marks_view = agent_marks.MarksView()
        # 0.0 ⇒ the first refresh tick after mount materializes a purge.
        self._marks_purge_due_at: float = 0.0
        self._marks_purge_inflight: bool = False
        # Per-tick session→root map, refreshed once per tick by the host app
        # (see `_set_session_root_map`). Starts empty so a keypress-driven
        # rebuild that runs outside `_refresh_data` reuses the last tick's map
        # rather than triggering a fan-out on a keystroke — the same contract
        # `_completed_pane_ids` uses.
        self._session_root_map: dict = {}

    def _set_session_root_map(self, mapping: dict) -> None:
        """Publish this tick's session→project-root map.

        Called once per refresh from each app's `_refresh_data`, which already
        fetches the mapping for `TaskInfoCache.update_session_mapping` — the
        full monitor via the **async** variant. Marks reuse that one value
        instead of re-querying.

        This is not merely a micro-optimisation: `_strict_root_for_snap` runs
        once per row per tick, and calling the SYNC
        `get_session_to_project_mapping()` from there put a potential blocking
        tmux round-trip on the render path (free on a cache hit, but a
        `list-sessions` plus a `list-panes` per session on a miss).
        `tests/test_monitor_refresh_no_sync_tmux.py` exists to trip exactly
        that regression.
        """
        self._session_root_map = mapping or {}

    # -- identity ----------------------------------------------------------

    def _strict_root_for_snap(self, snap: PaneSnapshot) -> str | None:
        """Canonical project root owning this pane's session, or ``None``.

        **Strict on purpose** — unlike ``_root_for_snap``, it never falls back
        to ``self._project_root``. That fallback is right for "which repo do I
        read task data from", but catastrophic for mark identity: it would file
        another repo's agent under *this* repo's root, so a mark set here would
        surface on an identically-named window elsewhere. Callers treat ``None``
        as "not markable" and, for the purge, as a visibility gap.
        """
        return self._root_for_session(getattr(snap.pane, "session_name", ""))

    def _is_marked(self, snap: PaneSnapshot) -> bool:
        """Render-time lookup. Cheap: the view is a cached key set."""
        root = self._strict_root_for_snap(snap)
        if root is None:
            return False
        return self._marks_view.is_marked(root, snap.pane.window_name)

    # -- read path ---------------------------------------------------------

    def _refresh_marks(self) -> None:
        """Re-read the store if it changed. Call once per refresh tick.

        Costs one ``os.stat`` in the steady state, which is what makes a mark
        set in another repo appear here within a single tick.
        """
        try:
            self._marks_view.refresh()
        except Exception:  # noqa: BLE001 - advisory data must never break a tick
            pass

    # -- write path --------------------------------------------------------

    async def _run_marks_cmd(self, args: list[str]) -> tuple[int, str]:
        """Run the locked writer off the event loop. The injectable seam.

        Deliberately NOT ``TmuxMonitor._run_offloaded``: that seam's contract is
        "pure compute over plain data" (invariant A), which spawning a process
        violates. Tests override this method.

        **Total by contract — never raises, always terminates.** Callers treat
        the result as data, so every failure is normalised to
        ``(rc, "ERROR:…")``:

        - A missing or non-executable wrapper raises ``OSError`` from
          ``create_subprocess_exec``. Unhandled, that would propagate out of
          ``action_toggle_mark`` on a keypress.
        - A child that never exits would hang ``communicate()`` forever, and the
          purge scheduler's ``finally`` — which clears ``_marks_purge_inflight``
          — would never run, wedging maintenance for the life of the process.
          That is precisely the guarantee its docstring makes, so the timeout is
          what makes the claim true rather than aspirational.

        The wrapper's own lock timeouts are 2s (toggle) and 10s (purge), so
        :data:`_MARKS_CMD_TIMEOUT` sits above both: a slow-but-working writer
        must be allowed to finish and report ``LOCK_BUSY`` itself.
        """
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                str(_MARKS_SH), *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await asyncio.wait_for(
                proc.communicate(), timeout=_MARKS_CMD_TIMEOUT
            )
        except asyncio.TimeoutError:
            # Kill the child, then reap it so it cannot become a zombie.
            try:
                proc.kill()
                await proc.wait()
            except Exception:  # noqa: BLE001 - already exited / unkillable
                pass
            return 1, f"ERROR:marks command timed out after {_MARKS_CMD_TIMEOUT}s"
        except OSError as exc:
            return 1, f"ERROR:cannot run {_MARKS_SH.name}: {exc}"
        return proc.returncode or 0, out.decode("utf-8", "replace").strip()

    async def _toggle_mark_for(self, snap: PaneSnapshot) -> None:
        """Toggle the prioritized mark on ``snap``. The shared write path.

        Target resolution belongs to the caller: the full monitor resolves
        through live focus (:meth:`action_toggle_mark`); the minimonitor
        resolves through the agent it follows
        (``MiniMonitorApp.action_toggle_mark``, t1383). Both reach this one
        sink, so the guards and the four outcome branches are written once.
        """
        # Both TUIs render non-agent panes as focusable cards (monitor's OTHER
        # section, and minimonitor's since t1382), so "the focused card is an
        # agent" is no longer an invariant either app can assume. A mark is keyed
        # by window name and only ever consumed by the agent lists, so marking a
        # shell / lazygit / renamed window would write an entry nothing reads.
        # Guarded here, in the shared sink, rather than in each app.
        if snap.pane.category != PaneCategory.AGENT:
            self.notify("Marks apply to agent panes only", severity="warning")
            return

        root = self._strict_root_for_snap(snap)
        if root is None:
            self.notify(
                "Cannot resolve this agent's project — not marking",
                severity="warning",
            )
            return

        window = snap.pane.window_name
        rc, out = await self._run_marks_cmd(["toggle", root, window])
        first = out.splitlines()[0] if out else ""

        if first.startswith("MARKED:"):
            self.notify(f"Prioritized {window}", timeout=3)
        elif first.startswith("UNMARKED:"):
            self.notify(f"Unmarked {window}", timeout=3)
        elif first == "LOCK_BUSY" or rc == 3:
            self.notify("Marks file busy — try again", severity="warning")
            return
        else:
            self.notify(f"Mark failed: {first or f'exit {rc}'}", severity="error")
            return

        # The write may land inside the same coarse mtime tick as the last read,
        # so force the re-read rather than trusting the stat stamp.
        self._marks_view.invalidate()
        self._refresh_marks()
        self.call_later(self._refresh_data)

    async def action_toggle_mark(self) -> None:
        """Toggle the prioritized mark on the *focused* agent card.

        The minimonitor overrides this to target the agent it follows instead
        (t1383) — it is a companion pane bound to exactly one agent, so focus
        is the wrong target there. The full monitor follows nothing, so focus
        is its only target, and it stays the way to mark any *other* agent.
        """
        # Live focus, NOT the cached `_focused_pane_id`: the toggle must act on
        # what is selected *now*, and the cached field survives focus moving off
        # the card entirely (it is only updated by `on_descendant_focus`, which
        # never fires for a non-card widget). Acting on it would toggle a mark
        # the user is no longer pointing at. Returns silently — "nothing
        # selected" is not an error worth a toast.
        #
        # This deliberately diverges from `_current_shadow_pane_id`
        # (monitor_app.py), which documents preferring the *cached* field
        # because it must survive focus being in a preview zone. Opposite needs,
        # opposite choice.
        #
        # NOTE: modal safety does NOT rest on this guard. Textual does not
        # dispatch App-level BINDINGS while a ModalScreen is active, so `space`
        # never reaches this action from inside a dialog — verified by a
        # negative control in tests/test_monitor_modal_space_dispatch.py, which
        # pins that behaviour so a future Textual change or a key-forwarding
        # modal cannot silently reintroduce the hazard.
        pane_id = self._get_focused_pane_id()
        if not pane_id:
            return
        snap = self._snapshots.get(pane_id)
        if snap is None:
            return
        await self._toggle_mark_for(snap)

    # -- purge -------------------------------------------------------------

    def _collect_marks_observation(self) -> tuple[dict[str, set[str]], set[str], bool]:
        """Snapshot what this tick can prove about liveness.

        Returns ``(observed_windows_by_root, sweepable_roots, complete)``.

        Both inputs come from **discovery**, via
        ``TmuxMonitor.last_enumerated_sessions()`` and
        ``last_discovered_agents()`` — never from ``_snapshots``.

        That distinction is the whole correctness of the sweep.
        ``commit_snapshots`` drops any pane whose *content capture* failed
        (``if result is None: continue``), so ``_snapshots`` is "panes we
        successfully read", not "panes that exist". Deriving the agent set from
        it would make a transient capture failure indistinguishable from a
        departed agent: the agent's siblings would keep its root sweepable while
        it was itself missing, and the purge would delete a live mark. Discovery
        output has no such hole — the pane is listed whether or not its content
        could be read.

        Both facts are published by ``commit_snapshots`` on its winning-generation
        branch, so they and the snapshots are always the same generation.
        """
        monitor = self._monitor
        sessions = getattr(monitor, "last_enumerated_sessions", None)
        agents = getattr(monitor, "last_discovered_agents", None)
        if sessions is None or agents is None:
            # A monitor that cannot report discovery facts (e.g. a test double)
            # gives no basis for concluding anything departed. Fail closed.
            return {}, set(), False

        observed: dict[str, set[str]] = {}
        sweepable: set[str] = set()
        complete = True

        for session in sessions():
            root = self._root_for_session(session)
            if root is None:
                # An enumerated session we cannot attribute to a project. Not a
                # gap in agent visibility — it simply is not sweepable.
                continue
            sweepable.add(root)
            observed.setdefault(root, set())

        for session, window in agents():
            root = self._root_for_session(session)
            if root is None:
                # A discovered agent we cannot attribute. Its window would be
                # missing from observed[root] while that root may still be
                # sweepable, so its live mark could be deleted. Suppress the
                # whole sweep for this tick — a visibility gap must never cause
                # a deletion.
                complete = False
                continue
            observed.setdefault(root, set()).add(window)

        return observed, sweepable, complete

    def _root_for_session(self, session: str) -> str | None:
        """Canonical project root for a session name, or ``None``."""
        if not session:
            return None
        root = self._session_root_map.get(session)
        if root is None:
            return None
        return agent_marks.mark_key(root, "")[0]

    def _write_observation_file(
        self, observed: dict[str, set[str]], sweepable: set[str], complete: bool
    ) -> str:
        fd, path = tempfile.mkstemp(prefix="ait-marks-obs-", suffix=".tsv")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            if not complete:
                fh.write("INCOMPLETE\n")
            for root in sorted(sweepable):
                fh.write(f"ROOT\t{root}\n")
            for root in sorted(observed):
                for window in sorted(observed[root]):
                    fh.write(f"WINDOW\t{root}\t{window}\n")
        return path

    async def _maybe_purge_marks(self) -> None:
        """Materialize expiry + the liveness sweep, at most every 10 minutes.

        The render path already filters expired marks every tick, so this exists
        only to bound the store's growth. Scheduling is explicit rather than
        implicit: an in-flight run is never stacked, and the flag is cleared in a
        ``finally`` so a crashed or hung wrapper cannot wedge the scheduler.
        """
        if self._marks_purge_inflight:
            return
        now = time.monotonic()
        if now < self._marks_purge_due_at:
            return

        # Snapshot the observation BEFORE the await and pass it explicitly. The
        # purge must act on the state it was scheduled with, not on whatever
        # ambient state exists when the subprocess returns.
        observed, sweepable, complete = self._collect_marks_observation()
        self._marks_purge_inflight = True
        path = None
        try:
            path = self._write_observation_file(observed, sweepable, complete)
            await self._run_marks_cmd(["purge", "--observed", path])
        except Exception:  # noqa: BLE001 - maintenance must never break a tick
            pass
        finally:
            self._marks_purge_inflight = False
            self._marks_purge_due_at = time.monotonic() + _MARKS_PURGE_INTERVAL
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass


class ShadowRejectionsMixin:
    """The concern-rejection store seam for a monitor TUI (t1427_2).

    Mixed into both ``MonitorApp`` and ``MiniMonitorApp``. One shared seam
    rather than two open-coded subprocess blocks, so the timeout, the
    never-raises contract and the exit-code vocabulary are defined once.

    A sibling of :class:`AgentMarksMixin` rather than part of it: both wrap a
    locked bash writer with the same shape, but they own unrelated state and
    conflating them would put rejection logic behind a marks-shaped name.
    """

    async def _run_rejected_cmd(
        self, args: list[str], stdin_text: str = ""
    ) -> tuple[int, str]:
        """Run ``aitask_shadow_rejected.sh`` off the event loop. The test seam.

        Modeled on :meth:`AgentMarksMixin._run_marks_cmd` and keeping its
        contract: **total — never raises, always terminates.** It is reached
        from a keypress handler and from a modal dismissal callback, so an
        unhandled ``OSError`` would propagate out of the pick flow, and a child
        that never exits would wedge the worker for the life of the process.
        Both are normalised to ``(1, "ERROR:…")`` and callers treat the result
        as data. Tests override this method — no bash runs in the suites.

        Unlike the marks seam this one writes **stdin**: ``add`` takes its
        marker lines there rather than as argv, so a body containing shell
        metacharacters or newlines never has to survive an argument list.
        """
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                str(_REJECTED_SH), *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await asyncio.wait_for(
                proc.communicate(stdin_text.encode("utf-8")),
                timeout=_REJECTED_CMD_TIMEOUT,
            )
        except asyncio.TimeoutError:
            # Kill the child, then reap it so it cannot become a zombie.
            try:
                proc.kill()
                await proc.wait()
            except Exception:  # noqa: BLE001 - already exited / unkillable
                pass
            return 1, (
                f"ERROR:rejection store command timed out after "
                f"{_REJECTED_CMD_TIMEOUT}s"
            )
        except OSError as exc:
            return 1, f"ERROR:cannot run {_REJECTED_SH.name}: {exc}"
        return proc.returncode or 0, out.decode("utf-8", "replace").strip()

    async def _fetch_rejected_entries(
        self, task_id: str | None
    ) -> list[RejectedEntry]:
        """Pre-fetch the task's rejection store for the picker.

        Returns ``[]`` for every non-success outcome — a store that cannot be
        read is presented as "nothing rejected yet", which is the safe direction
        (the shadow keeps raising concerns rather than appearing to suppress
        them). Callers pass ``store_unavailable`` separately for the case that
        genuinely needs to be visible: no task id at all.
        """
        if not task_id:
            return []
        rc, out = await self._run_rejected_cmd(["list", task_id, "--machine"])
        if rc != 0:
            return []
        return parse_rejected_machine_lines(out)

    def apply_concern_pick_result(self, result, task_id: str | None) -> None:
        """Act on a :class:`ConcernPickResult` — the shared callback body.

        Identical in both apps, so it lives here rather than being written
        twice. The caller has already released whatever re-entrancy guard it
        holds; this is purely the "do what the user asked" half.

        Forwarding is synchronous (a clipboard write); persistence is not — it
        is a subprocess, and this runs inside a synchronous ``push_screen``
        dismissal callback, so the work moves onto a worker.
        """
        # `is None`, never `if not result`: an all-empty result is a legitimate
        # "confirmed nothing" and must not be mistaken for a cancellation.
        if result is None:
            return

        if result.forwarded:
            # copy_to_system_clipboard, never app.copy_to_clipboard: a bare
            # OSC 52 from a non-visible tmux window never reaches the system
            # clipboard. tests/test_tui_clipboard_seam.sh enforces this.
            copy_to_system_clipboard(self, build_clipboard_payload(result.forwarded))
            self.notify("Concerns copied to clipboard.")

        if not result.rejected and not result.unrejected:
            return

        if not task_id:
            # A VISIBLE refusal, never a silent drop: the user marked rejections
            # and they are not being stored, which they can only find out here.
            self.notify(
                "Rejections not persisted — no task id for this pane",
                severity="warning",
            )
            return

        self.run_worker(
            self._persist_concern_dispositions(result, task_id),
            exclusive=False,
            exit_on_error=False,
            group="shadow-rejections",
        )

    async def _persist_concern_dispositions(self, result, task_id: str) -> None:
        """Write the confirmed rejections / un-rejections. Worker body.

        Sequential rather than concurrent: both subcommands take the same
        per-task mutex, so issuing them together would just make one of them
        report ``LOCK_BUSY`` against ourselves.
        """
        if result.rejected:
            stdin_text = "".join(
                concern_marker_line(c) + "\n" for c in result.rejected
            )
            rc, out = await self._run_rejected_cmd(
                ["add", task_id, "--producer", "picker"], stdin_text
            )
            message, severity = self.rejection_outcome_message(rc, out)
            if message:
                self.notify(message, severity=severity)
            else:
                n = len(result.rejected)
                self.notify(f"{n} concern(s) rejected — suppressed next round")

        if result.unrejected:
            rc, out = await self._run_rejected_cmd(
                ["remove", task_id, *result.unrejected]
            )
            message, severity = self.rejection_outcome_message(rc, out)
            if message:
                self.notify(message, severity=severity)
            else:
                self.notify(f"{len(result.unrejected)} concern(s) un-rejected")

    def rejection_outcome_message(self, rc: int, out: str) -> tuple[str, str]:
        """Map a helper result to ``(message, severity)``.

        The three failure codes are kept **distinct** deliberately (t1427_1):
        ``3`` is transient contention and retrying is reasonable, ``4`` means
        the store is structurally unusable and will not fix itself, and ``2``
        means this code passed something wrong. Collapsing them into one
        "rejection failed" would turn a permanent misconfiguration into an
        endless retry, which is exactly the failure t1427_1 recorded.
        """
        first = out.splitlines()[0] if out else ""
        if rc == 3 or first == "LOCK_BUSY":
            return ("Rejection store busy — try again", "warning")
        if rc == 4:
            return (
                f"Rejection store unusable — not retrying ({first or 'exit 4'})",
                "error",
            )
        if rc == 2:
            return (f"Rejection store rejected the request: {first}", "error")
        if rc != 0:
            return (f"Rejection store failed: {first or f'exit {rc}'}", "error")
        return ("", "")


def unparsed_concerns_msg(count: int) -> str:
    """Warning for a block whose marker lines yielded no concern (t1274).

    Its own message rather than the bland "no concerns": the shadow *did* emit a
    block, so silence (or a false all-clear) is the failure being fixed.

    Shared (t1216_3) so minimonitor and the full monitor report an unparseable
    block identically; it is also what makes that outcome *definitive* enough
    for the monitor to clear its concern badge.
    """
    return (
        f"Shadow emitted a concern block but {count} line(s) could not be "
        "parsed — none are forwardable"
    )


def uncertified_round_block_msg(round_number: "int | None") -> str:
    """Warning for a round-headed block that is not a certified clean round.

    Covers the shapes `is_metadata_only_block` refuses while the block still
    carries (or attempts) a round header (t1159_1): a complete block whose
    non-item content the scanner silently dropped (nothing parsed, nothing in
    `unrecovered_markers`), a still-streaming header-only block, and — with
    ``round_number=None`` — a block whose ``Round:`` line fails the grammar
    (`has_invalid_round_header`), where no round can be reported. Reporting
    any of them as "no concerns" would hide output the shadow did emit — same
    failure class as :func:`unparsed_concerns_msg`.

    Shared so both TUIs report the shapes identically.
    """
    if round_number is None:
        return (
            "Concern block has an invalid round header and no parseable "
            "concerns — showing the raw block"
        )
    return (
        f"Concern block (round {round_number}) has no parseable concerns and "
        "is not a clean-round record — showing the raw block"
    )


def format_stale_duration(seconds: float) -> str:
    """Compact human duration for the shadow-staleness banner (t1104).

    Pure. Shared so every surface that reports "analyzed N ago" reads
    identically (t1216_1).
    """
    s = int(max(0.0, seconds))
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def format_pane_status(snap: PaneSnapshot, completed: bool = False) -> str:
    """Render a pane's status badge with awaiting_input > completed > is_idle >
    active priority (t1322). See :func:`_state_color` for why ``completed`` is
    an explicit parameter rather than something derived from ``snap``."""
    if getattr(snap, "awaiting_input", False):
        return f"[{STATE_STYLE_PROMPT}]PROMPT {int(snap.idle_seconds)}s[/]"
    if completed:
        return f"[{STATE_STYLE_DONE}]DONE {int(snap.idle_seconds)}s[/]"
    if snap.is_idle:
        return f"[{STATE_STYLE_IDLE}]IDLE {int(snap.idle_seconds)}s[/]"
    return f"[{STATE_STYLE_ACTIVE}]Active[/]"


def _ansi_to_rich_text(ansi_str: str) -> Text:
    """Convert ANSI text to Rich Text with a forced dark background.

    Pre-processes the raw ANSI to inject a dark background (#1a1a1a) at the
    start and after every SGR reset, so areas that would otherwise show the
    terminal's default background render correctly in the TUI preview.
    """
    # Set dark bg at start of every line
    lines = ansi_str.split("\n")
    patched = []
    for line in lines:
        # Inject dark bg at start
        line = _DARK_BG_ANSI + line
        # After every reset (\033[0m or \033[m), re-apply dark bg
        line = _ANSI_RESET_RE.sub(lambda m: m.group(0) + _DARK_BG_ANSI, line)
        # Replace default-bg-only (\033[49m) with our dark bg
        line = _ANSI_DEFAULT_BG_RE.sub(_DARK_BG_ANSI, line)
        patched.append(line)
    text = Text.from_ansi("\n".join(patched))
    return text


class TaskDetailDialog(ModalScreen):
    """Read-only dialog showing task content and optional plan."""

    BINDINGS = [
        Binding("escape", "dismiss_dialog", "Close", show=False),
        Binding("q", "dismiss_dialog", "Close", show=False),
        Binding("p", "toggle_plan", "Plan/Task", show=True),
    ]

    DEFAULT_CSS = """
    TaskDetailDialog { align: center middle; }
    #task-detail-dialog {
        width: 90%;
        height: 85%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #task-detail-header { text-style: bold; margin: 0 0 1 0; }
    #task-detail-meta { margin: 0 0 1 0; color: $text-muted; }
    #task-detail-scroll { height: 1fr; }
    #task-detail-footer { dock: bottom; height: 1; color: $text-muted; }
    """

    def __init__(self, info: TaskInfo) -> None:
        super().__init__()
        self._info = info
        self._showing_plan = False

    def _detail_widgets(self) -> ComposeResult:
        """The header / meta / body triple, without the dialog container or the
        footer. Subclasses (``TaskPickConfirmDialog``, t1310) reuse it so
        ``action_toggle_plan`` — which queries ``#task-detail-header`` and
        ``#task-detail-scroll`` — is inherited verbatim.
        """
        info = self._info
        yield Static(
            f"[bold]t{info.task_id}: {info.title}[/]",
            id="task-detail-header",
        )
        yield Static(
            f"Priority: {info.priority}  Effort: {info.effort}  "
            f"Type: {info.issue_type}  Status: {info.status}",
            id="task-detail-meta",
        )
        yield VerticalScroll(
            Markdown(info.body or "*No content*"),
            id="task-detail-scroll",
        )

    def compose(self) -> ComposeResult:
        with Container(id="task-detail-dialog"):
            yield from self._detail_widgets()
            plan_hint = (
                "  [dim]p: switch plan/task[/]" if self._info.plan_content else ""
            )
            yield Static(
                f"[dim]q/Esc: close[/]{plan_hint}",
                id="task-detail-footer",
            )

    def action_dismiss_dialog(self) -> None:
        self.dismiss()

    def action_toggle_plan(self) -> None:
        if not self._info.plan_content:
            self.app.notify("No plan file found", severity="warning")
            return
        self._showing_plan = not self._showing_plan
        content = self._info.plan_content if self._showing_plan else self._info.body
        label = "Plan" if self._showing_plan else "Task"

        scroll = self.query_one("#task-detail-scroll", VerticalScroll)
        for child in list(scroll.children):
            child.remove()
        scroll.mount(Markdown(content or "*No content*"))

        header = self.query_one("#task-detail-header", Static)
        header.update(f"[bold]t{self._info.task_id}: {self._info.title}[/] [{label}]")


class TaskNumberInputModal(ModalScreen):
    """Prompt for a task number to pick (t1310).

    The first TUI surface in this repo that takes a *typed* task id rather than
    offering a list — the end-of-run "created t1234 / pick t1235 next" case the
    minimonitor's ``p`` serves. Dismisses the raw string (validation and
    normalization belong to the caller, which owns the downstream lookup) or
    ``None`` on cancel.
    """

    BINDINGS = [Binding("escape", "dismiss_dialog", "Close", show=False)]

    DEFAULT_CSS = """
    TaskNumberInputModal { align: center middle; }
    #task-num-dialog {
        width: 60%;
        min-width: 28;
        height: auto;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #task-num-header { text-style: bold; color: $accent; margin: 0 0 1 0; }
    #task-num-input { margin: 0 0 1 0; }
    #task-num-help { color: $text-muted; margin: 0 0 1 0; }
    #task-num-buttons { width: 100%; height: auto; layout: horizontal; }
    #task-num-buttons Button { margin: 0 1; }

    /* Narrow variant (minimonitor companion pane, ~40 cols): widen the dialog
       and stack the buttons, matching NextSiblingDialog.narrow. */
    TaskNumberInputModal.narrow #task-num-dialog { width: 90%; min-width: 30; }
    TaskNumberInputModal.narrow #task-num-buttons { layout: vertical; height: auto; }
    TaskNumberInputModal.narrow #task-num-buttons Button {
        width: 1fr;
        margin: 0 0 1 0;
    }
    """

    def __init__(self, narrow: bool = False) -> None:
        super().__init__()
        self._narrow = narrow

    def compose(self) -> ComposeResult:
        if self._narrow:
            self.add_class("narrow")
        with Container(id="task-num-dialog"):
            yield Static("[bold]Pick Task by Number[/]", id="task-num-header")
            yield Input(placeholder="e.g. 1310 or 1310_2", id="task-num-input")
            yield Static(
                "[dim]\\[Enter/OK] continue  \\[Esc] cancel[/]",
                id="task-num-help",
            )
            with Container(id="task-num-buttons"):
                yield Button("OK", variant="primary", id="btn-num-ok")
                yield Button("Cancel", variant="default", id="btn-num-cancel")

    def on_mount(self) -> None:
        self.query_one("#task-num-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-num-ok":
            self.dismiss(self.query_one("#task-num-input", Input).value)
        else:
            self.dismiss(None)

    def action_dismiss_dialog(self) -> None:
        self.dismiss(None)


class TaskPickConfirmDialog(TaskDetailDialog):
    """Task detail plus a launch confirmation and an opt-in kill (t1310).

    A *subclass* rather than a flag on ``TaskDetailDialog`` so the read-only
    ``i`` / ``I`` surface stays unchanged by construction: the base keeps its
    exact bindings, CSS, auto-focus, compose order and ``None`` dismissal, and
    its two call sites are untouched. Textual type selectors match base classes,
    so the base's ``#task-detail-dialog`` rules still apply here and only the
    confirm row and the ``.narrow`` variant live below.

    Dismisses ``("pick", kill_followed_agent)`` on confirm, ``("column", None)``
    when the user chooses to move the task to a board column, and ``None`` on
    cancel (t1377_2). The first element used to be a bare ``True``; it is a tag
    now because a two-way boolean cannot carry a third action.

    The column action is offered only for a **parent** task id: board columns
    hold parent cards, and the headless seam refuses a child id outright with
    ``not_a_parent_task``, so an affordance there would be a dead end.
    """

    DEFAULT_CSS = """
    /* Leave room for the confirm row on a short pane; the body scroll gives up
       space first but never disappears entirely. */
    TaskPickConfirmDialog #task-detail-dialog { height: 90%; }
    TaskPickConfirmDialog #task-detail-scroll { min-height: 1; }
    /* Docked, not in normal flow: the minimonitor pane is as short as the tmux
       window, and a flow-laid confirm row silently overflows *below* the dialog
       at ~20 rows — the buttons then render off-screen entirely. Docking makes
       "the controls are inside the dialog" structural: the body scroll is what
       gives up space, down to a single row. */
    TaskPickConfirmDialog #pick-confirm-row {
        dock: bottom;
        width: 100%;
        height: auto;
        margin: 1 0 0 0;
    }
    TaskPickConfirmDialog #task-detail-footer { dock: bottom; }
    #pick-eligibility { color: $warning; text-style: bold; margin: 0 0 1 0; }
    #pick-running { color: $warning; margin: 0 0 1 0; }
    #pick-kill-detail { color: $text-muted; text-style: bold; margin: 0 0 1 0; }
    #pick-buttons { width: 100%; height: auto; layout: horizontal; }
    #pick-buttons Button { margin: 0 1; }

    /* Narrow variant (minimonitor companion pane, ~40 cols): the buttons plus a
       checkbox cannot share a row, so stack them — and drop the `tall`
       borders, which cost two rows per control in a pane that has none to
       spare. With the t1377_2 column button the stack is three rows tall, which
       is why `#pick-confirm-row { dock: bottom }` above is load-bearing: the
       body scroll gives up the space, not the controls. */
    TaskPickConfirmDialog.narrow #task-detail-dialog { width: 90%; min-width: 30; }
    TaskPickConfirmDialog.narrow #pick-buttons { layout: vertical; height: auto; }
    TaskPickConfirmDialog.narrow #pick-buttons Button {
        width: 1fr;
        height: 1;
        border: none;
        margin: 0 0 1 0;
    }
    TaskPickConfirmDialog.narrow #pick-kill {
        width: 1fr;
        height: 1;
        border: none;
    }
    """

    def __init__(
        self,
        info: TaskInfo,
        *,
        kill_target_label: str | None = None,
        already_running: str | None = None,
        blocking: list[str] | None = None,
        narrow: bool = False,
    ) -> None:
        super().__init__(info)
        self._kill_target_label = kill_target_label
        self._already_running = already_running
        self._blocking = list(blocking or [])
        self._narrow = narrow

    @property
    def has_eligibility_warning(self) -> bool:
        """True when the target is not cleanly pickable — drives the OK label."""
        return self._info.status != "Ready" or bool(self._blocking)

    @property
    def offers_column_action(self) -> bool:
        """True when this task can be moved to a board column (t1377_2).

        Only parent tasks are board cards: the board loads children into a
        separate ``child_task_datas`` map and never renders them in a column, and
        ``aitask_board_column.sh`` refuses a child id with ``not_a_parent_task``.
        Offering the button for ``1377_2`` would therefore be a dead affordance,
        so it is omitted instead. Same parent/child test as
        ``NextSiblingDialog.compose``.
        """
        return "_" not in self._info.task_id

    def _kill_detail_text(self, kill: bool) -> str:
        """State of the kill checkbox, in words.

        Textual's ``Checkbox`` draws the same ``X`` slider glyph whether or not
        it is ticked — only the colour differs. That is too weak a signal for a
        control that closes down a running agent, especially in a ~40-column
        pane, so the state is restated here in text.
        """
        verb = "KILLS" if kill else "keeps"
        return f"{verb} {self._kill_target_label}"

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id != "pick-kill":
            return
        self.query_one("#pick-kill-detail", Static).update(
            self._kill_detail_text(event.value)
        )

    def _eligibility_lines(self) -> list[str]:
        lines: list[str] = []
        if self._info.status != "Ready":
            status = self._info.status or "(no status)"
            lines.append(f"⚠ t{self._info.task_id} is {status} — not Ready to pick")
        if self._blocking:
            blockers = " ".join(f"t{b}" for b in self._blocking)
            lines.append(f"⛔ blocked by {blockers}")
        return lines

    def compose(self) -> ComposeResult:
        if self._narrow:
            self.add_class("narrow")
        with Container(id="task-detail-dialog"):
            yield from self._detail_widgets()
            with Container(id="pick-confirm-row"):
                eligibility = self._eligibility_lines()
                if eligibility:
                    yield Static("\n".join(eligibility), id="pick-eligibility")
                if self._already_running:
                    yield Static(self._already_running, id="pick-running")
                if self._kill_target_label is not None:
                    # Short label on purpose: ToggleButton is `text-wrap: nowrap;
                    # text-overflow: ellipsis`, so a long one is silently clipped
                    # *inside* the dialog — invisible to a region-fit test. The
                    # detail goes in its own wrapping Static below.
                    yield Checkbox("kill followed agent", value=False, id="pick-kill")
                    yield Static(
                        self._kill_detail_text(False), id="pick-kill-detail"
                    )
                with Container(id="pick-buttons"):
                    if self.has_eligibility_warning:
                        yield Button(
                            "Launch anyway", variant="warning", id="btn-pick-ok"
                        )
                    else:
                        yield Button("OK", variant="primary", id="btn-pick-ok")
                    if self.offers_column_action:
                        # No trailing "…": no Button in this framework uses one,
                        # and the narrow pane charges a column for it.
                        yield Button(
                            "Move to column", variant="default",
                            id="btn-pick-column",
                        )
                    yield Button("Cancel", variant="default", id="btn-pick-cancel")
            plan_hint = (
                "  [dim]p: switch plan/task[/]" if self._info.plan_content else ""
            )
            yield Static(
                f"[dim]q/Esc: cancel[/]{plan_hint}",
                id="task-detail-footer",
            )

    def on_mount(self) -> None:
        # Confirm-mode only. The base's default AUTO_FOCUS lands on the
        # focusable body scroll, which is right for i/I (arrows scroll the
        # body) and must not change; here the primary action should be armed.
        self.query_one("#btn-pick-ok", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # Branch on the id explicitly. The earlier `!= "btn-pick-ok" -> cancel`
        # shortcut would silently swallow any button added later — including
        # `btn-pick-column`, which would then read as a cancel.
        if event.button.id == "btn-pick-ok":
            kill = False
            if self._kill_target_label is not None:
                kill = self.query_one("#pick-kill", Checkbox).value
            self.dismiss(("pick", kill))
            return
        if event.button.id == "btn-pick-column":
            self.dismiss(("column", None))
            return
        self.dismiss(None)

    def action_dismiss_dialog(self) -> None:
        # Inherited q / Esc must mean cancel, never a truthy result.
        self.dismiss(None)


class KillConfirmDialog(ModalScreen):
    """Confirmation dialog before killing a tmux pane."""

    BINDINGS = [
        Binding("escape", "dismiss_dialog", "Close", show=False),
    ]

    DEFAULT_CSS = """
    KillConfirmDialog { align: center middle; }
    #kill-dialog {
        width: 80%;
        min-width: 28;
        height: auto;
        max-height: 85%;
        background: $surface;
        border: thick $error;
        padding: 1 2;
    }
    #kill-header { text-style: bold; color: $error; margin: 0 0 1 0; }
    #kill-details { margin: 0 0 1 0; }
    #kill-preview-label { text-style: bold; color: $text-muted; margin: 1 0 0 0; }
    #kill-preview { max-height: 17; margin: 0 0 1 0; background: #1a1a1a; color: #d4d4d4; padding: 0 1; }
    #kill-buttons { width: 100%; height: 3; layout: horizontal; align: center middle; }
    #kill-buttons Button { width: auto; min-width: 10; margin: 0; }
    """

    def __init__(
        self,
        snap: PaneSnapshot,
        task_info: TaskInfo | None,
        show_preview: bool = True,
    ) -> None:
        super().__init__()
        self._snap = snap
        self._task_info = task_info
        self._show_preview = show_preview

    def compose(self) -> ComposeResult:
        snap = self._snap
        pane = snap.pane

        status = format_pane_status(snap)

        with Container(id="kill-dialog"):
            yield Static(
                "[bold red]Kill Agent Confirmation[/]",
                id="kill-header",
            )

            detail_parts = [
                f"Window:   [bold]{pane.window_index}:{pane.window_name}[/] (pane {pane.pane_index})",
            ]
            if self._task_info:
                info = self._task_info
                detail_parts.append(
                    f"Task:     [bold]t{info.task_id}[/]: {info.title}"
                )
                detail_parts.append(
                    f"          Priority: {info.priority}  Status: {info.status}"
                )
            detail_parts.append(f"Status:   {status}")
            detail_parts.append(f"Process:  {pane.current_command} (PID {pane.pane_pid})")

            yield Static("\n".join(detail_parts), id="kill-details")

            if self._show_preview:
                lines = snap.content.rstrip().splitlines()
                preview_lines = lines[-15:] if len(lines) > 15 else lines
                if preview_lines:
                    preview_content = _ansi_to_rich_text("\n".join(preview_lines))
                else:
                    preview_content = "(empty)"

                yield Static("[bold]Window Content Preview:[/]", id="kill-preview-label")
                yield Static(preview_content, id="kill-preview")

            with Container(id="kill-buttons"):
                yield Button("Kill", variant="error", id="btn-kill")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-kill":
            self.dismiss(True)
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

    /* Narrow variant (minimonitor companion pane, ~40 cols): three buttons
       cannot fit horizontally, so widen the dialog and stack them vertically. */
    NextSiblingDialog.narrow #next-sib-dialog { width: 90%; min-width: 30; }
    NextSiblingDialog.narrow #next-sib-buttons { layout: vertical; height: auto; }
    NextSiblingDialog.narrow #next-sib-buttons Button { width: 1fr; margin: 0 0 1 0; }
    """

    def __init__(
        self,
        current_task_id: str,
        current_title: str,
        current_status: str,
        suggested_id: str,
        suggested_title: str,
        parent_id: str,
        narrow: bool = False,
    ) -> None:
        super().__init__()
        self._current_task_id = current_task_id
        self._current_title = current_title
        self._current_status = current_status
        self._suggested_id = suggested_id
        self._suggested_title = suggested_title
        self._parent_id = parent_id
        self._narrow = narrow

    def compose(self) -> ComposeResult:
        if self._narrow:
            self.add_class("narrow")
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
                yield Button("Choose sibling", variant="primary", id="btn-choose-sibling")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-pick-suggested":
            self.dismiss(("pick", self._suggested_id))
        elif event.button.id == "btn-choose-sibling":
            self.dismiss(("choose", self._parent_id))
        else:
            self.dismiss(None)

    def action_dismiss_dialog(self) -> None:
        self.dismiss(None)


class _SiblingRow(Static):
    """A focusable sibling row inside ChooseSiblingModal."""

    can_focus = True

    DEFAULT_CSS = """
    _SiblingRow {
        height: 1;
        padding: 0 1;
    }
    _SiblingRow:focus {
        background: $accent 30%;
    }
    """

    def __init__(self, sib_id: str, title: str, blocking_ids: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self._sib_id = sib_id
        self._title = title
        self._blocking_ids = blocking_ids

    @property
    def sib_id(self) -> str:
        return self._sib_id

    def render(self) -> str:
        base = f"  [bold #7aa2f7]t{self._sib_id}[/]  {self._title}"
        if self._blocking_ids:
            blockers = " ".join(f"t{b}" for b in self._blocking_ids)
            base += f"  [bold red]⛔ blocked by {blockers}[/]"
        return base

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.screen.dismiss(self._sib_id)
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            self._focus_neighbor(1)
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            self._focus_neighbor(-1)
            event.prevent_default()
            event.stop()

    def _focus_neighbor(self, delta: int) -> None:
        parent = self.parent
        if parent is None:
            return
        rows = [w for w in parent.children if isinstance(w, _SiblingRow)]
        try:
            idx = rows.index(self)
        except ValueError:
            return
        new_idx = max(0, min(len(rows) - 1, idx + delta))
        if new_idx != idx:
            rows[new_idx].focus()
            rows[new_idx].scroll_visible()


class ChooseSiblingModal(ModalScreen):
    """Modal dialog letting the user pick a Ready sibling task by name."""

    BINDINGS = [Binding("escape", "dismiss_dialog", "Close", show=False)]

    DEFAULT_CSS = """
    ChooseSiblingModal { align: center middle; }
    #choose-sib-dialog {
        width: 70%;
        max-height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #choose-sib-header { text-style: bold; color: $accent; margin: 0 0 1 0; }
    #choose-sib-context { color: $text-muted; margin: 0 0 1 0; }
    #choose-sib-list { height: 1fr; min-height: 3; margin: 0 0 1 0; }
    #choose-sib-help { color: $text-muted; margin: 0 0 1 0; }
    #choose-sib-buttons { width: 100%; height: auto; layout: horizontal; }
    #choose-sib-buttons Button { margin: 0 1; }

    /* Narrow variant (minimonitor companion pane, ~40 cols): widen the dialog
       so the header, sibling rows, and OK/Cancel render fully. The two short
       buttons still fit horizontally within the widened pane. */
    ChooseSiblingModal.narrow #choose-sib-dialog { width: 90%; min-width: 30; }
    """

    def __init__(
        self,
        parent_id: str,
        siblings: list[tuple[str, str, list[str]]],
        narrow: bool = False,
    ) -> None:
        super().__init__()
        self._parent_id = parent_id
        self._siblings = siblings
        self._narrow = narrow

    def compose(self) -> ComposeResult:
        if self._narrow:
            self.add_class("narrow")
        with Container(id="choose-sib-dialog"):
            yield Static("[bold]Choose Sibling[/]", id="choose-sib-header")
            yield Static(
                f"Parent: [bold]t{self._parent_id}[/]  ·  {len(self._siblings)} Ready sibling(s)",
                id="choose-sib-context",
            )
            with VerticalScroll(id="choose-sib-list"):
                for sib_id, title, blocking_ids in self._siblings:
                    yield _SiblingRow(sib_id, title, blocking_ids)
            yield Static(
                "[dim]\\[↑/↓] navigate  \\[Enter/OK] select  \\[Esc] cancel[/]",
                id="choose-sib-help",
            )
            with Container(id="choose-sib-buttons"):
                yield Button("OK", variant="primary", id="btn-ok")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_mount(self) -> None:
        rows = list(self.query(_SiblingRow))
        if rows:
            rows[0].focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-ok":
            focused = self.focused
            if isinstance(focused, _SiblingRow):
                self.dismiss(focused.sib_id)
                return
            rows = list(self.query(_SiblingRow))
            if rows:
                self.dismiss(rows[0].sib_id)
            else:
                self.dismiss(None)
        else:
            self.dismiss(None)

    def action_dismiss_dialog(self) -> None:
        self.dismiss(None)


def _safe_column_color(raw: str) -> str:
    """A board-column colour that is safe to use as a rich-markup tag.

    Column colours come from a hand-editable ``board_config.json``, so the value
    is arbitrary text landing in a markup *tag*. Textual's current renderer
    tolerates an unknown style name (the text simply renders unstyled), so this
    is **defence in depth, not crash-prevention** — but ``Style.parse`` does
    raise ``StyleSyntaxError`` on the same input, so any path that resolves the
    style eagerly would fail, and relying on the renderer's tolerance would be
    relying on an implementation detail.

    Note the seam's own ``unordered`` default, ``gray``, is **not** a valid rich
    colour (rich has ``grey0``…``grey100``, no bare ``gray``/``grey``), so this
    fires on a stock value and that row draws an unstyled swatch.

    Only :class:`ColorParseError` is caught — the fallback is purely cosmetic so
    it cannot fail open into wrong behaviour, and a broader except would hide
    real bugs.
    """
    if not raw:
        return ""
    try:
        Color.parse(raw)
    except ColorParseError:
        return ""
    return raw


class _ColumnRow(Static):
    """A focusable board-column row inside ColumnPickerModal (t1377_2)."""

    can_focus = True

    DEFAULT_CSS = """
    _ColumnRow {
        height: 1;
        padding: 0 1;
    }
    _ColumnRow:focus {
        background: $accent 30%;
    }
    """

    def __init__(self, col_id: str, title: str, color: str = "",
                 current: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self._col_id = col_id
        self._title = title
        self._color = _safe_column_color(color)
        self._current = current

    @property
    def col_id(self) -> str:
        return self._col_id

    def pick_result(self):
        """This row's dismissal payload (t1377_3).

        The **one** place that knows the picker's result shape for a real
        column; `_NewColumnRow` overrides it for the create action. Both the
        Enter key and the OK button route through here, so the tagged tuple is
        defined once rather than at each dismissal site.
        """
        return ("existing", self._col_id)

    def render(self) -> str:
        # `title` and `col_id` are user-authored config reaching a markup
        # string, so both are escaped. Verified, not theoretical: an unescaped
        # `[/]` raises MarkupError and takes the modal down, and an unescaped
        # `[b]` is silently swallowed — `a[b]c` renders as `ac`, corrupting the
        # title with no signal at all. The colour is a *tag*, not text, so
        # escaping is not the tool for it — it is validated in the constructor.
        mark = "●" if self._current else " "
        swatch = f"[{self._color}]██[/]" if self._color else "██"
        return (f" {mark} {swatch} {escape(self._title)} "
                f"[dim]({escape(self._col_id)})[/]")

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.screen.dismiss(self.pick_result())
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            self._focus_neighbor(1)
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            self._focus_neighbor(-1)
            event.prevent_default()
            event.stop()

    def _focus_neighbor(self, delta: int) -> None:
        parent = self.parent
        if parent is None:
            return
        rows = [w for w in parent.children if isinstance(w, _ColumnRow)]
        try:
            idx = rows.index(self)
        except ValueError:
            return
        new_idx = max(0, min(len(rows) - 1, idx + delta))
        if new_idx != idx:
            rows[new_idx].focus()
            rows[new_idx].scroll_visible()


class _NewColumnRow(_ColumnRow):
    """The trailing "create a new column" row of ColumnPickerModal (t1377_3).

    A **subclass** rather than a sentinel `col_id` string: a sentinel would flow
    into the caller's `titles` lookup and could reach the seam as a real column
    id, whereas the tagged result makes the create action structurally distinct.
    Subclassing (rather than a sibling widget) is what keeps `_focus_neighbor`'s
    ``isinstance(w, _ColumnRow)`` scan and the modal's focus loop working
    unchanged.

    It carries no id and no colour, so it renders no swatch — there is nothing
    user-authored in this row to escape.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("", "", "", current=False, **kwargs)

    def pick_result(self):
        return ("new", None)

    def render(self) -> str:
        return "   [bold]＋ New column…[/]"


class ColumnPickerModal(ModalScreen):
    """Pick the board column to move a task into (t1377_2).

    ``columns`` is ``(col_id, colour, title)`` in board order — the shape
    ``aitask_board_column.sh list-columns`` emits, including the synthetic
    ``unordered`` entry. ``current`` is the task's present column, marked in the
    list so the user can see where it sits before moving it.

    ``allow_new`` appends a trailing "＋ New column…" row (t1377_3). It defaults
    to off so the constructor stays usable by a caller that only wants to move.

    Dismisses a **tagged tuple** (t1377_3):

    ==========================  ====================================
    ``("existing", col_id)``    move to an already-configured column
    ``("new", None)``           the user chose to create one
    ``None``                    cancel
    ==========================  ====================================

    The tag exists because both actions would otherwise be a bare string, and a
    sentinel id could reach the headless seam as a real column. Note both tuples
    are **truthy**: a consumer must branch on the tag, not on truthiness.
    """

    BINDINGS = [Binding("escape", "dismiss_dialog", "Close", show=False)]

    DEFAULT_CSS = """
    ColumnPickerModal { align: center middle; }
    #column-pick-dialog {
        width: 70%;
        max-height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #column-pick-header { text-style: bold; color: $accent; margin: 0 0 1 0; }
    #column-pick-context { color: $text-muted; margin: 0 0 1 0; }
    #column-pick-list { height: 1fr; min-height: 3; margin: 0 0 1 0; }
    #column-pick-help { color: $text-muted; margin: 0 0 1 0; }
    #column-pick-buttons { width: 100%; height: auto; layout: horizontal; }
    #column-pick-buttons Button { margin: 0 1; }

    /* Small-pane variant (minimonitor companion pane, ~40 cols and as SHORT as
       the tmux window): widen the dialog so rows render fully, then reclaim the
       vertical budget. This dialog carries more chrome than the sibling picker
       — header, context, list, help AND buttons — so at ~16 rows the borders
       cost real space: drop them and let the list collapse to a single
       scrolling row, the same levers the pick-confirm dialog pulls.
       `min-width: 0` is load-bearing: Textual's Button defaults to
       `min-width: 16`, so two of them plus margins overflow a 32-cell content
       box and Cancel renders outside the dialog. */
    ColumnPickerModal.narrow #column-pick-dialog { width: 90%; min-width: 30; }
    ColumnPickerModal.narrow #column-pick-list { min-height: 1; }
    /* At 40x16 the content box is 8 rows and the chrome wants 9, so the
       blank-line margins are what has to give — not the list, which is the
       only part carrying information. */
    ColumnPickerModal.narrow #column-pick-header { margin: 0; }
    ColumnPickerModal.narrow #column-pick-help { margin: 0; }
    ColumnPickerModal.narrow #column-pick-buttons Button {
        width: 1fr;
        min-width: 0;
        height: 1;
        border: none;
    }
    """

    def __init__(
        self,
        task_id: str,
        columns: list[tuple[str, str, str]],
        current: str | None = None,
        narrow: bool = False,
        allow_new: bool = False,
    ) -> None:
        super().__init__()
        self._task_id = task_id
        self._columns = columns
        self._current = current
        self._narrow = narrow
        self._allow_new = allow_new

    def _current_title(self) -> str:
        for col_id, _color, title in self._columns:
            if col_id == self._current:
                return title
        return self._current or "unknown"

    def compose(self) -> ComposeResult:
        if self._narrow:
            self.add_class("narrow")
        with Container(id="column-pick-dialog"):
            yield Static("[bold]Move to Column[/]", id="column-pick-header")
            # The current column's title is user-authored config too.
            yield Static(
                f"Task: [bold]t{escape(self._task_id)}[/]  ·  "
                f"now in: {escape(self._current_title())}",
                id="column-pick-context",
            )
            with VerticalScroll(id="column-pick-list"):
                for col_id, color, title in self._columns:
                    yield _ColumnRow(col_id, title, color,
                                     current=col_id == self._current)
                if self._allow_new:
                    yield _NewColumnRow()
            yield Static(
                "[dim]\\[↑/↓] navigate  \\[Enter/OK] select  \\[Esc] cancel[/]",
                id="column-pick-help",
            )
            with Container(id="column-pick-buttons"):
                yield Button("OK", variant="primary", id="btn-col-ok")
                yield Button("Cancel", variant="default", id="btn-col-cancel")

    def on_mount(self) -> None:
        rows = list(self.query(_ColumnRow))
        if not rows:
            return
        for row in rows:
            if row.col_id == self._current:
                row.focus()
                return
        rows[0].focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-col-ok":
            focused = self.focused
            if isinstance(focused, _ColumnRow):
                self.dismiss(focused.pick_result())
                return
            rows = list(self.query(_ColumnRow))
            if rows:
                self.dismiss(rows[0].pick_result())
            else:
                self.dismiss(None)
        else:
            self.dismiss(None)

    def action_dismiss_dialog(self) -> None:
        self.dismiss(None)


class NewColumnTitleModal(ModalScreen):
    """Prompt for the title of a board column to create (t1377_3).

    Shape copied from :class:`TaskNumberInputModal` — one input, OK/Cancel, a
    ``.narrow`` variant for the ~40-column companion pane. Dismisses the raw
    title string, or ``None`` on cancel; the id and colour are derived by the
    headless seam, so this asks for the one thing only a human can supply.

    **A blank title is rejected in place** — warn and stay mounted, mirroring
    the board's ``ColumnEditScreen.save``. Dismissing an empty string would push
    the refusal down to the seam and close the dialog the user has to reopen.
    """

    BINDINGS = [Binding("escape", "dismiss_dialog", "Close", show=False)]

    DEFAULT_CSS = """
    NewColumnTitleModal { align: center middle; }
    #new-col-dialog {
        width: 60%;
        min-width: 28;
        height: auto;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #new-col-header { text-style: bold; color: $accent; margin: 0 0 1 0; }
    #new-col-input { margin: 0 0 1 0; }
    #new-col-help { color: $text-muted; margin: 0 0 1 0; }
    #new-col-buttons { width: 100%; height: auto; layout: horizontal; }
    #new-col-buttons Button { margin: 0 1; }

    /* Small-pane variant for the ~40-column companion pane. `min-width: 0` is
       load-bearing: Textual's Button defaults to `min-width: 16`, so two of them
       plus margins overflow a 32-cell content box and Cancel renders outside the
       dialog. Buttons stack, as in TaskNumberInputModal.
       Keep the small-pane keyword out of THIS comment: the CSS-stripping helper
       in tests/test_minimonitor_pick_by_number.py drops any line containing it
       and then eats lines through the next `}`, so a mention here would orphan
       this comment's opener and take a real rule with it. */
    NewColumnTitleModal.narrow #new-col-dialog { width: 90%; min-width: 30; }
    NewColumnTitleModal.narrow #new-col-buttons { layout: vertical; height: auto; }
    NewColumnTitleModal.narrow #new-col-buttons Button {
        width: 1fr;
        min-width: 0;
        height: 1;
        border: none;
        margin: 0 0 1 0;
    }
    """

    def __init__(self, narrow: bool = False) -> None:
        super().__init__()
        self._narrow = narrow

    def compose(self) -> ComposeResult:
        if self._narrow:
            self.add_class("narrow")
        with Container(id="new-col-dialog"):
            yield Static("[bold]New Board Column[/]", id="new-col-header")
            yield Input(placeholder="e.g. Spikes", id="new-col-input")
            yield Static(
                "[dim]\\[Enter/OK] create  \\[Esc] cancel[/]",
                id="new-col-help",
            )
            with Container(id="new-col-buttons"):
                yield Button("Create", variant="primary", id="btn-new-col-ok")
                yield Button("Cancel", variant="default", id="btn-new-col-cancel")

    def on_mount(self) -> None:
        self.query_one("#new-col-input", Input).focus()

    def _submit(self) -> None:
        """The single guard both Enter and the Create button route through."""
        title = self.query_one("#new-col-input", Input).value.strip()
        if not title:
            self.app.notify("Title is required", severity="warning")
            return  # stay mounted — never dismiss on a blank title
        self.dismiss(title)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-new-col-ok":
            self._submit()
        else:
            self.dismiss(None)

    def action_dismiss_dialog(self) -> None:
        self.dismiss(None)


# Priority → rich-markup badge for a concern row. Colors mirror the broader
# high=red / medium=yellow / low=dim convention used across the monitor TUIs.
_CONCERN_BADGE = {
    "high": "[bold red]HIGH[/]",
    "medium": "[bold yellow]MED[/]",
    "low": "[dim]LOW[/]",
}


class RejectedEntry(NamedTuple):
    """One row of the per-task rejection store, as pre-fetched by the caller.

    Mirrors a single ``REJECTED:r<id>|<ts>|<producer>|<marker line>`` line from
    ``aitask_shadow_rejected.sh list --machine``. The marker line comes **last**
    on the wire precisely because it contains ``|``, so the parse is a 3-way
    split — see :func:`parse_rejected_machine_lines`.
    """

    id: str            # store entry id, `r`-prefixed exactly as the helper emits
    ts: str            # ISO-8601 rejection timestamp
    producer: str      # which shadow producer raised it, or "unknown"
    marker_line: str   # the canonical `- [priority | region] body` line


class ConcernPickResult(NamedTuple):
    """What :class:`ConcernPickerModal` dismisses with on confirm (t1427_2).

    Three independent output channels, because rejection needed a second one and
    overloading the old ``list[Concern]`` return would have made "forward these"
    and "reject these" indistinguishable.

    **All-empty is a valid result** — the user confirmed without marking
    anything. Cancellation is signalled by ``None`` instead, so a consumer must
    test ``result is None`` and never ``if not result``.
    """

    forwarded: list["Concern"]
    rejected: list["Concern"]
    unrejected: tuple[str, ...]   # store entry ids to un-reject, e.g. ("r1", "r3")


def parse_rejected_machine_lines(out: str) -> list[RejectedEntry]:
    """Parse ``list --machine`` output into entries.

    ``NO_REJECTIONS`` (a missing store *or* one drained of entries) and any
    unrecognised line yield nothing. Branch on that sentinel, never on the exit
    status: the helper exits 0 for **every** resolution outcome.

    ``split("|", 3)`` — bounded at 3 — is what keeps a body containing ``|``
    intact, since the marker line is the last field.
    """
    entries: list[RejectedEntry] = []
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("REJECTED:"):
            continue
        parts = line[len("REJECTED:"):].split("|", 3)
        if len(parts) != 4:
            continue
        entries.append(RejectedEntry(*parts))
    return entries


#: Disposition → row mark (t1427_2). Every glyph is **single-width**, which is
#: what keeps :data:`_NARROW_PREFIX_COLS` valid: the narrow layout budgets the
#: prefix in columns, so a double-width mark would silently eat a column of
#: region text at exactly the widths that already have none to spare.
_CONCERN_MARKS = {
    "none": "☐",
    "forward": "[bold yellow]☑[/]",
    "rejected": "[red]✗[/]",
}


#: Columns line 1 of a narrow row spends before the region: mark, spaces, the
#: widest badge (`HIGH`), and the separating space.
_NARROW_PREFIX_COLS = 8


class _ConcernRow(Static):
    """A focusable, tri-state concern row inside ConcernPickerModal.

    Holds one ``Concern``, its ``original_index`` in the modal's input list, and a
    **mutually exclusive** disposition in ``{"none", "forward", "rejected"}``
    (t1427_2). The checkbox glyph follows the t1004 convention (☑/☐, never a dot;
    marked = bold yellow); rejection adds a red ``✗``. Navigation mirrors
    ``_SiblingRow``; ``space`` toggles *forward* and ``r`` toggles *rejected* —
    setting either clears the other, so a concern can never be forwarded and
    rejected at once (``enter`` confirm is handled at the modal level).

    The three marks are all **single-width**, so :data:`_NARROW_PREFIX_COLS`
    still describes the narrow layout's prefix budget.

    **Two layouts (t1274).** The wide variant is one line,
    ``☐ BADGE region body``. The narrow variant — the minimonitor companion pane,
    where the laid-out row gets ~28 columns — is **two** lines, region on the
    first and body on the second. One line does not fit there: Rich's fold drops
    an overflowing segment whole rather than truncating it, so a region past ~19
    characters erased the region *and* the body and the row rendered as a bare
    priority badge. A 21-char region like ``authoring-conv.md:103`` is both real
    and fully compliant with the producer's ≤30-char rule, which is why this was
    hit routinely.
    """

    can_focus = True

    DEFAULT_CSS = """
    _ConcernRow {
        height: 1;
        padding: 0 1;
    }
    _ConcernRow.two-line {
        height: 2;
    }
    /* Informational: the shadow is NOT asking for action — recede, don't hide. */
    _ConcernRow.informational {
        color: $text-muted;
    }
    /* Rejected (t1427_2): dim, which together with the red ✗ mark reads as
       struck through without depending on terminal strikethrough support.
       Same colour as .informational on purpose — a rejected informational row
       is simply dim, and the mark is what distinguishes the two states. */
    _ConcernRow.rejected {
        color: $text-muted;
    }
    _ConcernRow:focus {
        background: $accent 30%;
    }
    /* Focused + hovered stays a shade of the focus accent — never gray hover. */
    _ConcernRow:focus:hover {
        background: $accent 40%;
    }
    """

    def __init__(
        self,
        concern: "Concern",
        *,
        narrow: bool = False,
        original_index: int = 0,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._concern = concern
        self._narrow = narrow
        self._original_index = original_index
        self._state = "none"
        if narrow:
            self.add_class("two-line")
        if not needs_addressing(concern):
            self.add_class("informational")

    @property
    def concern(self) -> "Concern":
        return self._concern

    @property
    def original_index(self) -> int:
        """Position in the modal's input list — the stable selection identity.

        Partitioning reorders the DOM, and ``Concern`` is a ``NamedTuple``: two
        equal concerns are indistinguishable by value, so the original order can
        only be restored positionally.
        """
        return self._original_index

    @property
    def state(self) -> str:
        """One of ``"none"`` / ``"forward"`` / ``"rejected"``."""
        return self._state

    @property
    def selected(self) -> bool:
        """True only in the ``forward`` state — the "will be forwarded" read."""
        return self._state == "forward"

    @property
    def rejected(self) -> bool:
        return self._state == "rejected"

    def set_state(self, value: str) -> None:
        """Set the disposition; repaint and re-class only on a real change.

        The ``rejected`` CSS class tracks the state here rather than at each
        call site, so the glyph and the dimming can never disagree.
        """
        if self._state == value:
            return
        self._state = value
        self.set_class(value == "rejected", "rejected")
        self.refresh()

    def toggle_forward(self) -> None:
        """``space``: forward ⇄ none. Clears a rejection by construction."""
        self.set_state("none" if self._state == "forward" else "forward")

    def toggle_reject(self) -> None:
        """``r``: rejected ⇄ none. Clears a forward selection by construction."""
        self.set_state("none" if self._state == "rejected" else "rejected")

    def _region_label(self, budget: int) -> str:
        """The region, ellipsized to ``budget`` columns, or a visible placeholder."""
        region = self._concern.region
        if not region:
            return "[dim italic](no region)[/]"
        if budget >= 4 and len(region) > budget:
            region = region[: budget - 1] + "…"
        return f"[dim]{escape(region)}[/]"

    def render(self) -> str:
        mark = _CONCERN_MARKS[self._state]
        badge = _CONCERN_BADGE.get(self._concern.priority, "[dim]LOW[/]")
        # display_body(), never .body — the Disposition:/Verified: trailer is
        # metadata for the receiving agent, not for this row. (The clipboard path
        # is the mirror rule: always .body, so the trailer is forwarded intact.)
        # Frozen with a DISPLAY role in
        # tests/test_concern_body_display_contract.py (t1294).
        body = escape(self._concern.display_body())
        if self._narrow:
            budget = max(6, (self.size.width or 28) - _NARROW_PREFIX_COLS)
            return f"{mark}  {badge} {self._region_label(budget)}\n   {body}"
        return f"{mark}  {badge} {self._region_label(40)}  {body}"

    def on_key(self, event) -> None:
        if event.key == "space":
            self.toggle_forward()
            event.prevent_default()
            event.stop()
        elif event.key == "r":
            self.toggle_reject()
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            self._focus_neighbor(1)
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            self._focus_neighbor(-1)
            event.prevent_default()
            event.stop()

    def _focus_neighbor(self, delta: int) -> None:
        parent = self.parent
        if parent is None:
            return
        rows = [w for w in parent.children if isinstance(w, _ConcernRow)]
        try:
            idx = rows.index(self)
        except ValueError:
            return
        new_idx = max(0, min(len(rows) - 1, idx + delta))
        if new_idx != idx:
            rows[new_idx].focus()
            rows[new_idx].scroll_visible()


#: Section headers for the disposition partition, in presentation order.
_CONCERN_SECTIONS = ("Needs addressing", "Informational")


#: The ``.narrow`` dialog's declared ``min-width``, and therefore the width at or
#: below which its chrome can no longer fit (t1293). **Derived, not chosen:** a
#: dialog whose minimum is N cells exactly fills an N-cell screen and overflows
#: anything narrower — at 24 the composited rows lose their right border and are
#: cut mid-word (``HIGH authoring-co``, ``[Spac``). The bound is inclusive
#: because the second defect bites at N too: ``max-height: 80%`` plus a help line
#: that wraps to five rows pushes the OK/Cancel labels off-screen. Pinned to the
#: stylesheet by ``test_tier_threshold_is_derived_from_the_declared_min_width``,
#: so retuning the CSS moves the tier with it.
#:
#: **Not a terminal tier.** This is a *component minimum width* in the sense of
#: ``aidocs/framework/tui_conventions.md`` — a property of this dialog, which is
#: why it lives here rather than in ``lib/tui_layout.py``. Do not route it
#: through ``terminal_tier`` / ``is_narrow_terminal``: those bound the NARROW
#: tier at 80 columns, so they answer True for every width this modal
#: distinguishes (24, 30, 40) and cannot express the decision at all. Rule 3 of
#: that document forbids reusing a tier constant as a component floor.
_PICKER_NARROW_MIN_WIDTH = 30

#: Narrowest width the picker is *tested* at, and the floor the docs quote.
#: Matches ``concern_parser._SENTINEL_SAFE_COLS`` — below it the block's own
#: fences wrap in the shadow pane and there is nothing parseable to show anyway.
_PICKER_MIN_COLS = 24

_CONCERN_HELP_FULL = (
    "[dim]\\[↑/↓] navigate  \\[Space] forward  \\[r] reject  "
    "\\[R] rejected list  \\[u] unparsed  \\[Enter/OK] confirm  \\[Esc] cancel[/]"
)

#: Same keys, ~50 columns instead of ~100 — at the xnarrow tier the full line
#: wraps to five rows and evicts the buttons. Dropping the removed `a`/`A` bulk
#: keys (t1427_2) is what buys the room for `r` / `R` at 24 columns.
_CONCERN_HELP_COMPACT = (
    "[dim]↑↓ move · spc fwd · r rej · R list · u raw · ↵ ok · esc[/]"
)


def format_block_meta(meta: "BlockMeta | None") -> str:
    """Display suffix for a concern block's round header, ``""`` when absent.

    Pure and **total over garbage**: ``reviewed_at`` is verbatim producer text
    that the parser never validates, so this must render *something* for any
    input rather than raise. The time is shortened to its clock part when the
    ISO shape is recognizable (``…T14:03:27Z`` → ``14:03:27Z``) and truncated
    otherwise. Returns **plain text** — the caller owns escaping at whatever
    markup boundary consumes it.
    """
    if meta is None:
        return ""
    when = meta.reviewed_at
    if "T" in when:
        when = when.rsplit("T", 1)[1]
    when = when[:12]
    return f"  ·  round {meta.round}" + (f", {when}" if when else "")


class ConcernBlockInspectModal(ModalScreen):
    """Raw view of a concern block that did not fully parse (t1293).

    t1274 made the loss *visible* (``⚠ N line(s) … could not be parsed``); this
    shows **what** was lost, so the user can tell an over-bound split marker from
    a producer typo and file a real bug against the shadow procedure.

    Two entry points: ``u`` from :class:`ConcernPickerModal`, and — when the
    block parsed to *nothing*, so there is no picker to show a banner beside —
    pushed directly by the caller's ``c`` handler.

    Everything is rendered with ``markup=False``. A concern marker is literally
    ``- [high | region]``; interpreted as Rich markup the bracket is eaten, i.e.
    the inspect view would corrupt the very text it exists to show.
    """

    BINDINGS = [
        Binding("escape", "dismiss_dialog", "Close", show=False),
        Binding("q", "dismiss_dialog", "Close", show=False),
    ]

    DEFAULT_CSS = """
    ConcernBlockInspectModal { align: center middle; }
    #concern-inspect-dialog {
        width: 90%;
        height: 85%;
        background: $surface;
        border: thick $warning;
        padding: 0 1;
    }
    #concern-inspect-header { text-style: bold; color: $warning; }
    #concern-inspect-lines { color: $text; height: auto; max-height: 40%; }
    #concern-inspect-raw-label { color: $text-muted; }
    #concern-inspect-scroll { height: 1fr; }
    #concern-inspect-footer { dock: bottom; height: 1; color: $text-muted; }
    """

    def __init__(self, unrecovered: Sequence[str], raw_block: str = "") -> None:
        super().__init__()
        self._unrecovered = list(unrecovered)
        self._raw_block = raw_block

    def compose(self) -> ComposeResult:
        with Container(id="concern-inspect-dialog"):
            yield Static(
                f"Unparsed concern lines ({len(self._unrecovered)})",
                id="concern-inspect-header",
            )
            with VerticalScroll(id="concern-inspect-lines"):
                for line in self._unrecovered:
                    yield Static(line, markup=False)
            yield Static("─ raw block ─", id="concern-inspect-raw-label")
            with VerticalScroll(id="concern-inspect-scroll"):
                yield Static(
                    self._raw_block.strip() or "(block region unavailable)",
                    markup=False,
                )
            yield Static("q/Esc: close", id="concern-inspect-footer")

    def action_dismiss_dialog(self) -> None:
        self.dismiss()


class _RejectedRow(Static):
    """A focusable, toggleable row of :class:`RejectedStoreModal` (t1427_2).

    ``space`` marks the entry for **un-rejection**; the mark follows the same
    t1004 convention as ``_ConcernRow`` (☑/☐, marked = bold yellow). Navigation
    mirrors ``_ConcernRow._focus_neighbor``.

    Rendered with ``markup=False`` semantics: the marker line is escaped before
    it reaches the markup renderer, because a marker literally reads
    ``- [high | region]`` and Rich would eat the bracket — corrupting the very
    text this view exists to show (the same rule
    :class:`ConcernBlockInspectModal` states).
    """

    can_focus = True

    DEFAULT_CSS = """
    _RejectedRow {
        height: auto;
        padding: 0 1;
    }
    _RejectedRow:focus {
        background: $accent 30%;
    }
    _RejectedRow:focus:hover {
        background: $accent 40%;
    }
    /* Marked for un-rejection: it is coming back, so stop dimming it. */
    _RejectedRow.unrejecting {
        color: $text;
    }
    """

    def __init__(self, entry: RejectedEntry, **kwargs) -> None:
        super().__init__(**kwargs)
        self._entry = entry
        self._marked = False

    @property
    def entry(self) -> RejectedEntry:
        return self._entry

    @property
    def marked(self) -> bool:
        return self._marked

    def toggle(self) -> None:
        self._marked = not self._marked
        self.set_class(self._marked, "unrejecting")
        self.refresh()

    def render(self) -> str:
        mark = "[bold yellow]☑[/]" if self._marked else "☐"
        meta = escape(f"{self._entry.id} · {self._entry.producer}")
        return f"{mark}  [dim]{meta}[/]\n   {escape(self._entry.marker_line)}"

    def on_key(self, event) -> None:
        if event.key == "space":
            self.toggle()
            event.prevent_default()
            event.stop()
        elif event.key in ("down", "up"):
            self._focus_neighbor(1 if event.key == "down" else -1)
            event.prevent_default()
            event.stop()

    def _focus_neighbor(self, delta: int) -> None:
        parent = self.parent
        if parent is None:
            return
        rows = [w for w in parent.children if isinstance(w, _RejectedRow)]
        try:
            idx = rows.index(self)
        except ValueError:
            return
        new_idx = max(0, min(len(rows) - 1, idx + delta))
        if new_idx != idx:
            rows[new_idx].focus()
            rows[new_idx].scroll_visible()


class RejectedStoreModal(ModalScreen):
    """The task's persisted rejections, with a per-row un-reject toggle (t1427_2).

    Rejection is otherwise irreversible, and a single mis-press would blind the
    shadow to that concern for the rest of the task — so this view is the
    required undo path (t1427 requirement 5). It is **TUI-only** by decision;
    there is no user-facing CLI for un-rejecting.

    Pure UI, exactly like the picker that pushes it: it neither reads nor writes
    the store. Entries arrive pre-fetched, and the ids it dismisses with travel
    back through the picker's result for the caller to act on.

    Dismisses a ``tuple[str, ...]`` of entry ids to un-reject — empty on
    ``escape``, which is therefore indistinguishable from "confirmed nothing".
    That is deliberate: both mean "change nothing", so no caller needs to tell
    them apart.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
        Binding("q", "cancel", "Close", show=False),
        Binding("enter", "confirm", "Un-reject marked"),
    ]

    DEFAULT_CSS = """
    RejectedStoreModal { align: center middle; }
    #rejected-dialog {
        width: 90%;
        height: 85%;
        background: $surface;
        border: thick $accent;
        padding: 0 1;
    }
    #rejected-header { text-style: bold; color: $accent; }
    #rejected-list { height: 1fr; }
    #rejected-footer { dock: bottom; height: 1; color: $text-muted; }
    """

    def __init__(self, entries: Sequence[RejectedEntry]) -> None:
        super().__init__()
        self._entries = list(entries)

    def compose(self) -> ComposeResult:
        with Container(id="rejected-dialog"):
            yield Static(
                f"Rejected concerns ({len(self._entries)})", id="rejected-header"
            )
            with VerticalScroll(id="rejected-list"):
                for entry in self._entries:
                    yield _RejectedRow(entry)
            yield Static(
                "[dim]\\[Space] un-reject  \\[Enter] apply  \\[q/Esc] cancel[/]",
                id="rejected-footer",
            )

    def on_mount(self) -> None:
        rows = list(self.query(_RejectedRow))
        if rows:
            rows[0].focus()

    def _marked_ids(self) -> tuple[str, ...]:
        return tuple(
            row.entry.id for row in self.query(_RejectedRow) if row.marked
        )

    def action_confirm(self) -> None:
        self.dismiss(self._marked_ids())

    def action_cancel(self) -> None:
        self.dismiss(())


class ConcernPickerModal(ModalScreen):
    """Modal letting the user forward or reject shadow concerns.

    Lives here (rather than in minimonitor) because the full monitor is due to
    push it too — see t1216_3; today minimonitor is the only caller. It carries
    its own ``DEFAULT_CSS`` per the TUI conventions for multi-App modals.

    **Disposition partition (t1274).** Concerns the shadow marked
    ``informational`` — real, but explicitly *not* a request for action — are
    grouped under their own header and dimmed. A block whose concerns all fall in
    one partition shows no headers at all, so plan-review blocks (whose producers
    have no disposition concept) look exactly as they did before.

    **Per-row actions only (t1427_2).** ``space`` forwards, ``r`` rejects, and
    the two are mutually exclusive on each row. The former ``a`` (select all
    actionable) and ``A`` (copy ALL) bulk keys were **removed outright**, not
    re-scoped: a bulk key that swept a row into "forward" would silently
    overwrite a rejection the user had just made, and rejection is persistent
    state rather than a one-shot selection.

    **Two independent size knobs (t1293) — neither is derived from the other.**
    ``narrow`` is the *caller's* hint and owns only the two-line ``_ConcernRow``
    layout. The ``xnarrow`` class is derived from the modal's own **measured**
    width (:data:`_PICKER_NARROW_MIN_WIDTH`) and owns only the dialog chrome, so a
    full-width monitor running in a 24-column terminal gets it too.

    **Dismiss contract (t1427_2; supersedes the t1037_4 list contract):**
    dismisses with a :class:`ConcernPickResult` on confirm (OK / Enter) and with
    ``None`` on Esc / Cancel. ``None`` is the ONLY cancel signal — a result whose
    three fields are all empty is a legitimate "confirmed nothing", so consumers
    MUST branch on ``is None`` and never on truthiness.

    The modal stays pure-UI: it does NOT build the clipboard payload, touch the
    clipboard, or write the rejection store — the caller's action handler runs
    ``concern_parser.build_clipboard_payload`` +
    ``tui_clipboard.copy_to_system_clipboard`` and the
    ``aitask_shadow_rejected.sh`` seam. This keeps it unit-testable without a
    clipboard backend or a filesystem. ``rejected_entries`` is likewise
    pre-fetched by the caller and passed in.
    """

    BINDINGS = [
        Binding("escape", "dismiss_dialog", "Close", show=False),
        Binding("enter", "confirm", "OK"),
        Binding("R", "show_rejected", "Rejected list"),
        # `u` for "unparsed". Deliberately not `i` — both apps bind that to Task
        # Info. `_ConcernRow.on_key` stops only space/up/down, so this bubbles.
        Binding("u", "inspect_unrecovered", "Unparsed", show=False),
    ]

    DEFAULT_CSS = """
    ConcernPickerModal { align: center middle; }
    #concern-dialog {
        width: 70%;
        max-height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #concern-header { text-style: bold; color: $accent; margin: 0 0 1 0; }
    #concern-stale { color: $error; text-style: bold; margin: 0 0 1 0; }
    #concern-unrecovered { color: $warning; text-style: bold; margin: 0 0 1 0; }
    #concern-context { color: $text-muted; margin: 0 0 1 0; }
    .concern-section { text-style: bold; color: $accent; height: 1; }
    #concern-list { height: 1fr; min-height: 3; margin: 0 0 1 0; }
    #concern-help { color: $text-muted; margin: 0 0 1 0; }
    #concern-buttons { width: 100%; height: auto; layout: horizontal; }
    #concern-buttons Button { margin: 0 1; }

    /* Narrow variant (minimonitor companion pane, ~40 cols): widen the dialog
       so the header, concern rows, and OK/Cancel render fully. */
    /* `min-width` here is the CANONICAL value _PICKER_NARROW_MIN_WIDTH mirrors;
       a drift guard in tests/test_concern_picker_modal.py keeps the two equal,
       so retuning this number moves the tier boundary with it. */
    ConcernPickerModal.narrow #concern-dialog { width: 90%; min-width: 30; }

    /* Extra-narrow tier (t1293), applied from the modal's MEASURED width at or
       below _PICKER_NARROW_MIN_WIDTH. The `min-width` above is exactly what
       makes the dialog overflow a 24-column screen — clipping the right border
       away and cutting every row mid-word — so it is cleared here, not reduced.
       `border: thick` is deliberately KEPT: an intact border on every dialog row
       is what the layout tests assert against to prove nothing is clipped. */
    ConcernPickerModal.xnarrow #concern-dialog {
        width: 100%;
        min-width: 0;
        max-height: 100%;
        padding: 0 1;
    }
    /* No OK/Cancel at this tier. Measured: side by side under ~34 columns the
       second label renders as "Can"; stacked they cost 6 rows and at 24x20 they
       evict the help line — the only place `r` / `R` / `u` are named. They are
       fully redundant with Enter/Esc, which the compact help does name, so the
       buttons are the right thing to drop. Nothing is ever half-drawn. */
    ConcernPickerModal.xnarrow #concern-buttons { display: none; }
    ConcernPickerModal.xnarrow #concern-buttons Button { width: 100%; margin: 0; }
    """

    def __init__(
        self, concerns: list["Concern"], narrow: bool = False,
        stale: bool = False, unrecovered: Sequence[str] = (),
        raw_block: str = "",
        *,
        rejected_entries: Sequence[RejectedEntry] = (),
        store_unavailable: bool = False,
        block_meta: "BlockMeta | None" = None,
    ) -> None:
        super().__init__()
        self._concerns = list(concerns)
        self._narrow = narrow
        self._stale = stale
        # The LINES, not a count (t1293): a count derived from the list with
        # `len()` cannot disagree with what the inspect view shows, whereas a
        # separate int parameter alongside a list parameter could.
        self._unrecovered = list(unrecovered)
        self._raw_block = raw_block
        # Pre-fetched by the caller at open time and never refreshed: the
        # session's view of the store is deliberately frozen (t1427 descoped
        # cross-session staleness handling). Safe to act on despite that,
        # because t1427_1 made entry ids stable and never reused.
        self._rejected_entries = list(rejected_entries)
        # No task id for this pane ⇒ the store cannot be located at all. Kept
        # distinct from "store is empty" so `R` can say which is true.
        self._store_unavailable = store_unavailable
        # Round metadata from the block header (t1159_1) — display-only.
        self._block_meta = block_meta
        self._unreject_ids: list[str] = []

    def _partitions(self) -> list[tuple[str, list[tuple[int, "Concern"]]]]:
        """``[(section_title, [(original_index, concern), …]), …]``, non-empty only.

        Input order is preserved inside each partition, and the original index
        travels with every concern so selection can be restored positionally.
        """
        actionable: list[tuple[int, "Concern"]] = []
        informational: list[tuple[int, "Concern"]] = []
        for index, concern in enumerate(self._concerns):
            target = actionable if needs_addressing(concern) else informational
            target.append((index, concern))
        pairs = zip(_CONCERN_SECTIONS, (actionable, informational))
        return [(title, group) for title, group in pairs if group]

    def _context_line(self) -> str:
        # `reviewed_at` is verbatim untrusted producer text on a markup-enabled
        # Static — an unescaped `[/]` raises MarkupError and takes the modal
        # down (same hazard class as the board-column title at _swatch_markup).
        meta_suffix = escape(format_block_meta(self._block_meta))
        partitions = self._partitions()
        if len(partitions) < 2:
            return (
                f"{len(self._concerns)} concern(s)  ·  forward or reject"
                + meta_suffix
            )
        counts = {title: len(group) for title, group in partitions}
        return (
            f"{counts['Needs addressing']} to address  ·  "
            f"{counts['Informational']} informational  ·  forward or reject"
            + meta_suffix
        )

    def compose(self) -> ComposeResult:
        if self._narrow:
            self.add_class("narrow")
        partitions = self._partitions()
        with Container(id="concern-dialog"):
            yield Static("[bold]Concerns[/]", id="concern-header")
            # Staleness warning (t1104): the followed agent has moved on since
            # the shadow produced these concerns.
            if self._stale:
                yield Static(
                    "⚠ These concerns may be stale — the agent has moved on",
                    id="concern-stale",
                )
            # Lossy-parse warning (t1274): the block held marker-looking lines
            # that yielded no concern, so this list is short of what the shadow
            # emitted. Visible degradation beats a silently truncated list.
            if self._unrecovered:
                yield Static(
                    # `\\[u]` — an unescaped `[u]` is Rich's underline tag and
                    # renders as nothing at all.
                    f"⚠ {len(self._unrecovered)} line(s) in this block "
                    "could not be parsed — \\[u] inspect",
                    id="concern-unrecovered",
                )
            yield Static(self._context_line(), id="concern-context")
            with VerticalScroll(id="concern-list"):
                # Headers only when both partitions exist — a single-partition
                # block (every plan-review block) looks exactly as it did before.
                show_headers = len(partitions) > 1
                for title, group in partitions:
                    if show_headers:
                        yield Static(f"─ {title} ─", classes="concern-section")
                    for index, concern in group:
                        yield _ConcernRow(
                            concern, narrow=self._narrow, original_index=index
                        )
            # Swapped for the compact variant by _apply_width_tier() once the
            # modal knows its measured width.
            yield Static(_CONCERN_HELP_FULL, id="concern-help")
            with Container(id="concern-buttons"):
                yield Button("OK", variant="primary", id="btn-ok")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_mount(self) -> None:
        self._apply_width_tier()
        rows = list(self.query(_ConcernRow))
        if rows:
            rows[0].focus()

    def on_resize(self) -> None:
        self._apply_width_tier()

    def _apply_width_tier(self) -> None:
        """Pick the dialog chrome from the modal's MEASURED width (t1293).

        Keyed on ``self.size.width`` — never on ``self._narrow``, which is the
        caller's row-layout hint and says nothing about the real terminal. Textual
        has no media queries, so this is the substitute; ``on_resize`` keeps it
        live. ``_ConcernRow.render`` already derives its region budget from live
        width, so the rows follow with no change here.

        The threshold is this dialog's own declared minimum, not a shared
        terminal tier — see :data:`_PICKER_NARROW_MIN_WIDTH` for why
        ``tui_layout.is_narrow_terminal`` cannot express this decision.
        """
        xnarrow = self.size.width <= _PICKER_NARROW_MIN_WIDTH
        self.set_class(xnarrow, "xnarrow")
        help_widgets = list(self.query("#concern-help"))
        if help_widgets:
            help_widgets[0].update(
                _CONCERN_HELP_COMPACT if xnarrow else _CONCERN_HELP_FULL
            )

    def action_inspect_unrecovered(self) -> None:
        """Show the marker lines this block lost, over the still-open picker.

        Pushed on the App (the first modal-over-modal in the monitor package;
        the repo precedent is ``brainstorm/modals.py``'s ``NodeDetailModal``).
        The picker is NOT dismissed, so closing the inspect view returns to an
        intact selection.
        """
        if not self._unrecovered:
            self.app.notify("Nothing unparsed in this block")
            return
        self.app.push_screen(
            ConcernBlockInspectModal(self._unrecovered, self._raw_block)
        )

    def _rows(self) -> list[_ConcernRow]:
        return list(self.query(_ConcernRow))

    def _concerns_in_state(self, state: str) -> list["Concern"]:
        """Concerns whose row is in ``state``, in **original input order**.

        Sorted by ``original_index``, never by DOM position and never matched by
        value: partitioning reorders the DOM, and two equal ``Concern`` tuples
        are indistinguishable, so ticking one of a duplicate pair would otherwise
        forward — or reject — the wrong one, or both.
        """
        rows = [row for row in self._rows() if row.state == state]
        return [row.concern for row in sorted(rows, key=lambda r: r.original_index)]

    def _result(self) -> ConcernPickResult:
        return ConcernPickResult(
            forwarded=self._concerns_in_state("forward"),
            rejected=self._concerns_in_state("rejected"),
            unrejected=tuple(self._unreject_ids),
        )

    def action_show_rejected(self) -> None:
        """Open the persisted rejection list, over the still-open picker.

        Same modal-over-modal shape as :meth:`action_inspect_unrecovered` — the
        picker is NOT dismissed, so returning lands on an intact selection.

        The two empty cases are reported **differently on purpose**: "no task id"
        means the store could not even be located and any rejection made here
        will be refused, which the user needs to know *before* confirming; "no
        rejected concerns" means the store was read and is genuinely empty.
        """
        if self._store_unavailable:
            self.app.notify(
                "No task id for this pane — rejection store unavailable",
                severity="warning",
            )
            return
        if not self._rejected_entries:
            self.app.notify("No previously rejected concerns for this task")
            return
        self.app.push_screen(
            RejectedStoreModal(self._rejected_entries),
            callback=self._on_rejected_view_closed,
        )

    def _on_rejected_view_closed(self, ids) -> None:
        """Accumulate the ids the rejected-store view marked for un-rejection.

        Accumulates rather than replaces: the view can be opened more than once
        before confirming, and a second visit must not discard the first visit's
        choices. De-duped, order preserved.
        """
        for entry_id in ids or ():
            if entry_id not in self._unreject_ids:
                self._unreject_ids.append(entry_id)

    def action_confirm(self) -> None:
        self.dismiss(self._result())

    def action_dismiss_dialog(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-ok":
            self.dismiss(self._result())
        else:
            self.dismiss(None)
