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
from monitor.monitor_core import (  # noqa: E402,F401
    PaneCategory,
    PaneSnapshot,
    _TASK_ID_RE,
    GateSummaryCache,
    TaskInfo,
    TaskInfoCache,
)

from typing import TYPE_CHECKING

from textual.binding import Binding  # noqa: E402
from textual.containers import Container, VerticalScroll  # noqa: E402
from textual.screen import ModalScreen  # noqa: E402
from textual.widgets import (  # noqa: E402
    Button, Checkbox, Input, Label, Markdown, Static,
)
from textual.app import ComposeResult  # noqa: E402
from rich.text import Text  # noqa: E402
from rich.markup import escape  # noqa: E402

try:
    from monitor.concern_parser import needs_addressing
except ImportError:  # imported flat (tests may put MONITOR_DIR on sys.path)
    from concern_parser import needs_addressing  # noqa: E402

if TYPE_CHECKING:  # annotations only (PEP 563 via `from __future__`); no runtime cost
    from monitor.concern_parser import Concern


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


def _state_color(snap: PaneSnapshot, completed: bool = False) -> str:
    """The single definition of the state→color mapping (t1133, t1322):
    PROMPT (awaiting_input) > COMPLETED > IDLE > active, as bold magenta /
    bold dodger_blue1 / yellow / green. Shared by the status badge, the agent
    dot, and the shadow glyph.

    ``completed`` is an explicit opt-in parameter and is never inferred here:
    it is a property of the pane's *task*, which a ``PaneSnapshot`` does not
    carry, and a shadow pane has no task of its own — inferring it would make
    :func:`format_shadow_glyph` colour shadows by their followed agent's task
    state. A completed agent parked on a final prompt still reads PROMPT, which
    is actionable now.
    """
    if getattr(snap, "awaiting_input", False):
        return "bold magenta"
    if completed:
        return "bold dodger_blue1"
    if snap.is_idle:
        return "yellow"
    return "green"


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
    belongs to no state in the ladder (magenta / dodger_blue1 / yellow / green),
    which is exactly what makes it legible as *user intent* rather than status.
    """
    if marked:
        return f"[bold white]{MARK_GLYPH}[/]"
    return f"[dim]{MARK_EMPTY_GLYPH}[/]"


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

    async def action_toggle_mark(self) -> None:
        """Toggle the prioritized mark on the selected agent."""
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
        return f"[bold magenta]PROMPT {int(snap.idle_seconds)}s[/]"
    if completed:
        return f"[bold dodger_blue1]DONE {int(snap.idle_seconds)}s[/]"
    if snap.is_idle:
        return f"[yellow]IDLE {int(snap.idle_seconds)}s[/]"
    return "[green]Active[/]"


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

    Dismisses ``(True, kill_followed_agent)`` on confirm, ``None`` on cancel.
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

    /* Narrow variant (minimonitor companion pane, ~40 cols): two buttons plus
       a checkbox cannot share a row, so stack them — and drop the `tall`
       borders, which cost two rows per control in a pane that has none to
       spare. */
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
        if event.button.id != "btn-pick-ok":
            self.dismiss(None)
            return
        kill = False
        if self._kill_target_label is not None:
            kill = self.query_one("#pick-kill", Checkbox).value
        self.dismiss((True, kill))

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


# Priority → rich-markup badge for a concern row. Colors mirror the broader
# high=red / medium=yellow / low=dim convention used across the monitor TUIs.
_CONCERN_BADGE = {
    "high": "[bold red]HIGH[/]",
    "medium": "[bold yellow]MED[/]",
    "low": "[dim]LOW[/]",
}


#: Columns line 1 of a narrow row spends before the region: mark, spaces, the
#: widest badge (`HIGH`), and the separating space.
_NARROW_PREFIX_COLS = 8


class _ConcernRow(Static):
    """A focusable, toggleable concern row inside ConcernPickerModal.

    Holds one ``Concern``, its ``original_index`` in the modal's input list, and a
    ``selected`` flag. The checkbox glyph follows the t1004 convention (☑/☐, never
    a dot; marked = bold yellow). Navigation mirrors ``_SiblingRow``; ``space``
    toggles the selection (``enter`` confirm is handled at the modal level).

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
        self._selected = False
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
    def selected(self) -> bool:
        return self._selected

    def toggle(self) -> None:
        self.set_selected(not self._selected)

    def set_selected(self, value: bool) -> None:
        if self._selected != value:
            self._selected = value
            self.refresh()

    def _region_label(self, budget: int) -> str:
        """The region, ellipsized to ``budget`` columns, or a visible placeholder."""
        region = self._concern.region
        if not region:
            return "[dim italic](no region)[/]"
        if budget >= 4 and len(region) > budget:
            region = region[: budget - 1] + "…"
        return f"[dim]{escape(region)}[/]"

    def render(self) -> str:
        mark = "[bold yellow]☑[/]" if self._selected else "☐"
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
            self.toggle()
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


class ConcernPickerModal(ModalScreen):
    """Modal letting the user pick which shadow concerns to forward.

    Lives here (rather than in minimonitor) because the full monitor is due to
    push it too — see t1216_3; today minimonitor is the only caller. It carries
    its own ``DEFAULT_CSS`` per the TUI conventions for multi-App modals.

    **Disposition partition (t1274).** Concerns the shadow marked
    ``informational`` — real, but explicitly *not* a request for action — are
    grouped under their own header and dimmed, and ``a`` (select all) skips them.
    A block whose concerns all fall in one partition shows no headers at all, so
    plan-review blocks (whose producers have no disposition concept) look exactly
    as they did before.

    **Dismiss contract (consumed by t1037_4):** dismisses with the **selected**
    ``list[Concern]`` on confirm (OK / Enter) or with the full list on "copy ALL"
    (``A``); dismisses with ``None`` on Esc / Cancel. The modal stays pure-UI: it
    does NOT build the clipboard payload or touch the clipboard — the caller's
    action handler runs ``concern_parser.build_clipboard_payload`` +
    ``tui_clipboard.copy_to_system_clipboard``. This keeps it unit-testable
    without a clipboard backend.
    """

    BINDINGS = [
        Binding("escape", "dismiss_dialog", "Close", show=False),
        Binding("enter", "confirm", "OK"),
        Binding("a", "toggle_all", "Select all/none"),
        Binding("A", "copy_all", "Copy ALL"),
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
    ConcernPickerModal.narrow #concern-dialog { width: 90%; min-width: 30; }
    """

    def __init__(
        self, concerns: list["Concern"], narrow: bool = False,
        stale: bool = False, unrecovered: int = 0,
    ) -> None:
        super().__init__()
        self._concerns = list(concerns)
        self._narrow = narrow
        self._stale = stale
        self._unrecovered = unrecovered

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
        partitions = self._partitions()
        if len(partitions) < 2:
            return f"{len(self._concerns)} concern(s)  ·  select to forward"
        counts = {title: len(group) for title, group in partitions}
        return (
            f"{counts['Needs addressing']} to address  ·  "
            f"{counts['Informational']} informational  ·  select to forward"
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
                    f"⚠ {self._unrecovered} line(s) in this block "
                    "could not be parsed",
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
            yield Static(
                "[dim]\\[↑/↓] navigate  \\[Space] toggle  \\[a] all actionable  "
                "\\[A] copy all  \\[Enter/OK] confirm  \\[Esc] cancel[/]",
                id="concern-help",
            )
            with Container(id="concern-buttons"):
                yield Button("OK", variant="primary", id="btn-ok")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_mount(self) -> None:
        rows = list(self.query(_ConcernRow))
        if rows:
            rows[0].focus()

    def _rows(self) -> list[_ConcernRow]:
        return list(self.query(_ConcernRow))

    def _selected_concerns(self) -> list["Concern"]:
        """Selected concerns in **original input order**.

        Sorted by ``original_index``, never by DOM position and never matched by
        value: partitioning reorders the DOM, and two equal ``Concern`` tuples
        are indistinguishable, so ticking one of a duplicate pair would otherwise
        forward the wrong one — or both.
        """
        selected = [row for row in self._rows() if row.selected]
        return [row.concern for row in sorted(selected, key=lambda r: r.original_index)]

    def action_toggle_all(self) -> None:
        rows = self._rows()
        # Informational concerns are not requests for action, so bulk-select
        # covers only the actionable ones. `A` (copy ALL) remains the escape
        # hatch that takes literally everything.
        actionable = [row for row in rows if needs_addressing(row.concern)]
        target_rows = actionable or rows
        # If every target row is already selected, a second press clears them.
        target = not (
            bool(target_rows) and all(row.selected for row in target_rows)
        )
        for row in target_rows:
            row.set_selected(target)

    def action_confirm(self) -> None:
        self.dismiss(self._selected_concerns())

    def action_copy_all(self) -> None:
        # Fast path: forward every concern in one keystroke (preamble is attached
        # downstream by build_clipboard_payload).
        self.dismiss(list(self._concerns))

    def action_dismiss_dialog(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-ok":
            self.dismiss(self._selected_concerns())
        else:
            self.dismiss(None)
