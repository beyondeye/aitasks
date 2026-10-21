"""The By-Trail view's App half: state, workers, keys and launch (t1794_5).

``TrailScreenMixin`` carries everything an App needs to host the By-Trail
screen — the session state (``_init_trail_state``), the render and selection
flow, the drift / reload / artifact-version-watch workers, the trail actions
and the ``/aitask-trail`` launch — moved verbatim out of ``KanbanApp``. The
pure projection, cards and modals it renders with live in
``board_trail_view.py``.

A host mixes it in ahead of ``App`` and provides the surface ``TrailHost``
documents; ``tests/test_trail_screen_host_protocol.py`` asserts every host
does. Two things are deliberately host policy rather than shared code:

* ``_trail_task_target()`` — which task ``T`` launches ``/aitask-trail`` for
  (C10). ``action_trail_task`` here only launches what the host returns.
* the optional board-only capabilities in ``TRAIL_ACTION_CAPABILITIES``. A
  host without them keeps the ``M`` / ``S`` bindings declared (one override
  owner) but ``_has_trail_capability`` stops both actions from running.

``run_dialog_command`` lives here too (parent plan "Scope decisions"): every
AgentCommandScreen "run" branch — the board's pick / create / brainstorm /
work-report launches as well as the trail launch — dispatches through it, and
the host's ``_after_dialog_command(refocus_filename)`` hook owns the refresh
and its ``_suspend_sync_guard(what)`` decides whether a suspended run may start.

**Patch targets.** The trail launch, drift, discovery and dialog-dispatch
names (``discover_trails``, ``_trail_versions``, ``load_trail_blob``,
``run_trail_drift``, ``resolve_dry_run_command``, ``AgentCommandScreen``,
``launch_in_tmux``, ``find_terminal`` …) and the linked-trail scan and jump
names (``scan_linked_trails``, ``current_tmux_session``,
``live_project_session``, ``bootstrap_project_session``,
``trails_supports_focus``, ``is_aitasks_project``, ``session_owned_by``,
``launch_or_focus_trails``, ``switch_client_to``,
``prepare_linked_trail_jump``, ``finish_linked_trail_jump``) are read from
THIS module's namespace by the methods below, so a test stub must target
``board_trail_screen``
(reachable as ``ab.board_trail_screen``). ``aitask_board.py`` still re-exports
several of them for its own callers; a stub on the board would be inert for
the trail paths, which the inert-patch guard in the host-protocol test catches.

Contracts (see ``board/__init__.py`` and the parent plan):

* C1 — imported by bare name; imports ``board_widgets`` and
  ``board_trail_view`` and no other board module, never ``aitask_board``, and
  adds nothing to ``sys.path``.
* C2 — resolves no task directory: ``_get_local_project`` reads the host's
  ``tasks_dir``. ``CODEAGENT_SCRIPT`` is cwd-relative, like every launcher path.
"""

from __future__ import annotations

import copy
import dataclasses
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Protocol

from rich.cells import cell_len, set_cell_size
from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.widgets import Static

from agent_command_screen import AgentCommandScreen
from agent_launch_utils import (
    TmuxLaunchConfig, bootstrap_project_session,
    current_tmux_session, find_terminal, is_aitasks_project, launch_in_tmux,
    launch_or_focus_trails, live_project_session, maybe_spawn_minimonitor,
    resolve_agent_string, resolve_dry_run_command, session_owned_by,
    spawn_in_terminal, switch_client_to, trails_supports_focus,
)
from board_trail_view import (
    TRAIL_SELECT_RESCAN, TRAIL_WATCH_INTERVAL, TRAIL_WATCH_MAX_TICKS,
    LinkedTrailsScreen, TrailColumn,
    TrailDetailScreen, TrailJumpConfirmScreen, TrailSelectScreen,
    TrailSummaryScreen,
    build_trail_lanes, load_local_project_name, run_trail_drift,
    trail_drift_by_ref, trail_generated_label, trail_summary_text,
    trail_xdep_refs,
)
from board_widgets import LoadingOverlay
from cross_repo_deps import probe_xdep_status
from keybinding_registry import resolve_key
from topic_semantics import task_own_id
from trail_discovery import (
    _trail_versions, compute_trail_overlaps, discover_trails, load_trail_blob,
    sequenced_trail_read,
)
from trail_links import scan_linked_trails


CODEAGENT_SCRIPT = Path(".aitask-scripts") / "aitask_codeagent.sh"
CODEAGENT_FAILURE_NOTICE = (
    "Code agent invocation failed — check model configuration"
)


# --- Trail bindings (C10: one owner for the trail keys) ---------------------
#
# The SAME Binding objects are declared by every host, so a `(board, <action>)`
# shortcut override resolves once for all of them. `keybinding_registry`
# records the last registrant's default, so a host that built its own copy
# with a different default would silently change the other host's key.
#
# `KanbanApp.BINDINGS` cannot splice these as one block: they interleave with
# board rows that share keys (`r`/`s` pairs gated by `check_action`), and
# Textual's dispatch and footer order follow declaration order. The board
# therefore places each `TRAIL_BINDING["<action>"]` at its own position; the
# rationale for each position is commented there.
TRAIL_BINDINGS = [
    Binding("enter", "view_details", "View/Edit"),
    Binding("r", "trail_refresh_local", "Refresh"),
    Binding("R", "trail_refresh_agent", "Agent Refresh"),
    Binding("d", "trail_refresh_drift", "Freshness"),
    Binding("s", "trail_select", "Select Trail"),
    Binding("S", "trail_sync", "Sync"),
    Binding("v", "trail_summary_expand", "Summary"),
    Binding("L", "trail_linked", "Linked Trails"),
    Binding("T", "trail_task", "Trail"),
    Binding("M", "trail_move_wave", "Move Wave"),
]
TRAIL_BINDING = {b.action: b for b in TRAIL_BINDINGS}

#: `p` — pick the focused task. Not a trail key (the mixin implements no
#: `pick_task`; each host does), but both hosts declare it, so the SAME object
#: rides in both BINDINGS and a `shortcuts.board.pick_task` override rebinds
#: `ait board` and `ait trails` at once (t1946).
PICK_BINDING = Binding("p", "pick_task", "Pick")

#: Optional host members each board-only trail action reaches, directly or
#: through the chain it starts (`_review_then` → `_choose_move_destination` →
#: `_apply_move_to_column`, which reads `marked` and `_column_title`).
TRAIL_ACTION_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "trail_move_wave": ("_review_then", "_choose_move_destination",
                        "_column_title", "marked", "_reject_stale",
                        "_apply_move_to_column"),
    "trail_sync": ("_run_sync",),
}


# --- Linked-trail jump (t1957_4) ------------------------------------------------
#
# Two phases, both on a thread. PREPARE finds (or starts) the target project's
# session and collects warnings, with no effect on the client. FINISH opens the
# trail there and switches the client. Warnings are shown and confirmed BETWEEN
# them: once the client switches, this App is no longer on screen, so a notice
# it showed afterwards would never be read. The resulting invariant — the
# source App only ever shows a notice on a path where the client did NOT
# switch — is why `finish_linked_trail_jump` returns nothing on success.


@dataclass(frozen=True)
class TrailJump:
    """A prepared jump. ``error`` is terminal (nothing switches; the source App
    shows it); ``launch`` is False when the target's `ait trails` cannot take
    ``--trail``. Two kinds of message must be confirmed before ``finish``
    runs, and they age differently:

    * ``warnings`` describe the target as it is NOW (an older framework).
      Every prepare derives them afresh, so they are never carried over.
    * ``notices`` record a one-time event of THIS prepare (the bootstrap
      started the session under a fallback name). A later prepare finds the
      session running and cannot produce them again, so a notice paused under
      another dialog is carried to the retry."""
    link: object
    session: str = ""
    launch: bool = False
    warnings: tuple = ()
    notices: tuple = ()
    error: str = ""

    @property
    def to_confirm(self) -> tuple:
        return (*self.notices, *self.warnings)


def _manual_trail_command(link) -> str:
    """The command a user can paste instead. Quoted: a registry name may hold
    spaces, and every value here came from another repository's export."""
    return shlex.join(["ait", "projects", "exec", str(link.project), "--",
                       "./ait", "trails", "--trail", str(link.handle)])


def prepare_linked_trail_jump(link) -> TrailJump:
    """Resolve the session ``link`` jumps to — starting it when the project
    has none running — and collect what the user must read first. Blocking
    (tmux and the bootstrap subprocess): thread workers only. Opens nothing
    and does not touch the client."""
    if current_tmux_session() is None:
        # Not a pane of the gateway server (outside tmux, or in another tmux
        # server): switch-client could not reach this client, so start nothing.
        return TrailJump(link, error=(
            "Not in an aitasks tmux session — open the trail with: "
            f"{_manual_trail_command(link)}"))
    root = Path(link.root)
    if not is_aitasks_project(root):
        return TrailJump(link, error=(
            f"{link.project}: {link.root} is no longer an aitasks project — "
            "press L to search again"))
    notices = []
    session = live_project_session(root)
    if session is None:
        boot = bootstrap_project_session(root)
        if not boot.ok:
            return TrailJump(link, error=(
                f"Could not start a tmux session for {link.project}: "
                f"{boot.error}"))
        session = live_project_session(root)
        if session is None:
            return TrailJump(link, error=(
                f"Started a tmux session for {link.project}, but could not "
                "find it — press L to try again"))
        if boot.default_session_problem:
            notices.append(
                f"{link.project}: tmux.default_session is unusable "
                f"({boot.default_session_problem}); started session "
                f"'{session}'")
    warnings = []
    launch = trails_supports_focus(root)
    if not launch:
        warnings.append(
            f"{link.project} runs an older aitasks without trail jumps — run "
            f"`ait upgrade` there; you will land in its session without "
            f"{link.handle} opened")
    return TrailJump(link, session=session, launch=launch,
                     warnings=tuple(warnings), notices=tuple(notices))


def finish_linked_trail_jump(jump: TrailJump) -> list[tuple[str, str]]:
    """Open the trail in the prepared session and switch the client there.

    Returns ``(message, severity)`` notices, and only for paths that did NOT
    switch — after a switch nobody is looking at this App. The destination is
    checked again first: a warning dialog may have stayed open for any length
    of time, and the session could have stopped and its name been reused by
    another project, which would then receive the trail and the client."""
    link = jump.link
    root = Path(link.root)
    if (not is_aitasks_project(root)
            or not session_owned_by(jump.session, root)):
        return [(f"The tmux session for {link.project} changed before the "
                 "jump — press L to try again", "error")]
    if jump.launch:
        ok, err = launch_or_focus_trails(jump.session, root, link.handle)
        if not ok:
            return [(f"Could not open {link.handle} in {link.project}: {err}",
                     "error")]
    if not switch_client_to(jump.session):
        return [(f"Could not switch to tmux session '{jump.session}' — "
                 f"{_manual_trail_command(link)}", "error")]
    return []


@dataclass(eq=False)
class TrailSession:
    """One opened trail's in-memory state (session-only, never persisted;
    t1210_4). ``eq=False``: sessions compare by identity — "is this the active
    session" is an ``is`` question, never a field-by-field one.

    Two supersession stamps, both drawn from the mixin's ``_trail_gen`` counter:
    ``reload_gen`` names the latest reload request (a superseded reload result
    is discarded), ``drift_gen`` the latest drift request — and it is also
    re-drawn whenever the session's content changes from any source, so a
    verdict computed for an older document never lands on a newer one.

    Cross-repo status (t1957_1) has its own stamp, ``xdep_gen``. ``xdep``
    holds COMPLETED probe results only (``repo#id`` → status) and
    ``xdep_inflight`` the refs the current probe covers; a ref in neither is
    rendered "not checked", never as a failure."""
    handle: str
    doc: dict | None = None
    error: str = ""                # fail-closed load error
    versions_fallback: list = field(default_factory=list)
    drift: tuple | None = None     # (verdict, reasons) | None
    owner_id: str = ""             # the trail's owner task
    owner_archived: bool = False   # §9.2 archived-owner banner
    reload_gen: int = 0
    drift_gen: int = 0
    xdep: dict = field(default_factory=dict)   # completed xdep probe results
    xdep_inflight: frozenset = frozenset()     # refs the current probe covers
    xdep_gen: int = 0
    focus_filename: str = ""       # last focused card, restored on tab switch
    focus_col_id: str = ""
    updated: bool = False          # background change not yet seen (tab's •)
    read_seq: int = 0              # fetch-order sequence of `doc` (0 = unknown)


def _session_field(name: str, default_factory):
    """A mixin property that reads / writes ``name`` on the ACTIVE session.

    The scalar By-Trail state used to live on the App; it now lives per
    session, and these properties keep every existing reader and writer — the
    board's ``z`` view and the tests — working unchanged. Reading with no
    active session yields the old default; WRITING with none raises, because
    the value would have nowhere to live (every writer sets the handle
    first)."""
    def fget(self):
        session = self._trail_active
        return default_factory() if session is None else getattr(session, name)

    def fset(self, value):
        session = self._trail_active
        if session is None:
            raise RuntimeError(f"no active trail session to store {name!r} in")
        setattr(session, name, value)

    return property(fget, fset)


class TrailHost(Protocol):
    """The App surface ``TrailScreenMixin`` reads off ``self``.

    ``KanbanApp`` is the reference host. Besides these members a host must
    compose the widgets in ``REQUIRED_WIDGETS`` (``TrailColumn`` lanes are
    mounted into ``#board_container``; the banner budget reads
    ``HeaderTitle``) and give ``manager`` the ``MANAGER_MEMBERS``.
    ``_refresh_subtitle`` is the mixin's own; its non-trail fallback is why
    ``manager`` needs ``auto_refresh_minutes`` and ``settings``.
    """

    REQUIRED_WIDGETS: ClassVar[tuple[str, ...]] = (
        "HeaderTitle", "#trail_summary", "#trail_summary_body",
        "#board_container",
    )
    MANAGER_MEMBERS: ClassVar[tuple[str, ...]] = (
        "load_tasks", "task_datas", "child_task_datas",
        "find_task_including_archived", "auto_refresh_minutes", "settings",
    )

    manager: object
    tasks_dir: Path
    base_filter: str
    sub_title: str
    title: str

    def refresh_board(self, refocus_filename: str = "", *args, **kwargs) -> None: ...

    def _focused_card(self): ...

    def _modal_is_active(self) -> bool: ...

    def _get_focused_col_id(self): ...

    def _queue_refocus(self, refocus_filename: str = "",
                       refocus_col_id: str = "") -> None: ...

    def apply_filter(self, cols=None) -> None: ...

    def refresh_bindings(self) -> None: ...

    def _banner_budget(self) -> int: ...

    def _after_dialog_command(self, refocus_filename: str = "") -> None: ...

    def _suspend_sync_guard(self, what: str):
        """Context manager yielding whether a suspended launch may run.

        The host owns sync coordination for ``run_dialog_command``'s
        suspended child (t1955): True means proceed (any lock it takes is
        held until the block exits), False means refused and already
        notified.
        """
        ...

    def _trail_task_target(self) -> str | None: ...

    def notify(self, message, *args, **kwargs) -> None: ...

    def push_screen(self, screen, callback=None, *args, **kwargs): ...

    def pop_screen(self): ...

    def set_interval(self, interval, callback=None, *args, **kwargs): ...

    def call_after_refresh(self, callback, *args, **kwargs): ...

    def query_one(self, selector, *args, **kwargs): ...

    def query(self, selector=None): ...

    def suspend(self): ...


class TrailScreenMixin:
    """By-Trail screen behaviour for an App that provides ``TrailHost``."""

    #: Host policy (t1895). False — the board's ``z`` view: one session at a
    #: time, activating a trail replaces it, and ``s`` always re-scans. True —
    #: ``ait trails``: every explicitly opened trail keeps its own session (one
    #: tab each), activating an open trail switches to it, and ``s`` serves the
    #: discovery cache, re-scanning only when it is missing or empty.
    _TRAIL_TABBED: ClassVar[bool] = False

    # The active session's state, under the names the single-trail view used.
    _trail_doc = _session_field("doc", lambda: None)
    _trail_error = _session_field("error", str)
    _trail_versions_fallback = _session_field("versions_fallback", list)
    _trail_drift = _session_field("drift", lambda: None)
    _trail_xdep = _session_field("xdep", dict)
    _trail_xdep_inflight = _session_field("xdep_inflight", frozenset)
    _trail_owner_id = _session_field("owner_id", str)
    _trail_owner_archived = _session_field("owner_archived", bool)

    def _init_trail_state(self) -> None:
        """Create the By-Trail session state. The host calls this from its
        ``__init__`` (the mixin has no ``__init__`` of its own)."""
        # --- By-Trail view state (session-only, never persisted; t1210_4) ---
        # Open sessions in tab order (insertion order), and the active one.
        self._trail_sessions: dict[str, TrailSession] = {}
        self._trail_active: TrailSession | None = None
        self._trail_infos: list | None = None    # discovery cache
        # Monotonic counter. Consumers never compare against it directly;
        # they compare against STAMPS drawn from it: `_trail_discovery_gen`
        # (the in-flight scan) and each session's `reload_gen` / `drift_gen`.
        # A callback carrying a stale stamp is discarded.
        self._trail_gen = 0
        self._trail_discovery_gen = 0
        self._local_project: str | None = None   # lazy project-name cache
        # --- Artifact-version watch (t1268) ---
        # Installed only after a confirmed agent refresh actually launched;
        # polls `artifact versions` until the stored trail moves, then reloads.
        # Its own supersession token, deliberately NOT _trail_gen: the
        # post-launch _reload_active_trail() bumps _trail_gen and must not
        # disarm a watch that is still waiting for the agent's write.
        self._trail_watch_timer = None
        self._trail_watch_handle: str = ""
        self._trail_watch_baseline: list | None = None
        self._trail_watch_ticks = 0
        self._trail_watch_busy = False
        self._trail_watch_gen = 0
        # A confirmed agent launch whose baseline read is still in flight.
        # The baseline worker can take up to _trail_versions' 15s timeout, and
        # the dialog is already closed by then — without this guard a user who
        # thinks nothing happened can confirm `R` again and spawn a second
        # expensive refresh agent (t1268).
        self._trail_launch_pending = False
        # --- Linked trails (t1957_4) ---
        # The stamp of the linked-trail search whose result may still show;
        # drawn from `_trail_gen`, re-drawn to retire it.
        self._trail_link_gen = 0
        # At most one scan runs at a time (t1979): a press while one is in
        # flight only records the newest request — with its OWN snapshot — and
        # it starts when the running scan lands. Every scan runs one export
        # subprocess per registered project, so held or repeated `L` presses
        # would otherwise multiply them for results that are superseded anyway.
        self._trail_link_running = False
        self._trail_link_pending: tuple | None = None
        # A jump is between "picked" and "done" (prepare, the warning dialog,
        # finish): a second pick would race it into a second trails window.
        self._trail_jump_busy = False
        # One-time notices (`TrailJump.notices`) of a jump paused under
        # another dialog, by target root, not yet read. The retry cannot
        # produce them again — the session already runs — so its dialog shows
        # them. Warnings are never kept: the retry derives them afresh.
        self._trail_jump_unread: dict[str, tuple] = {}

    # --- Sessions (t1895) ---------------------------------------------------

    @property
    def active_trail_handle(self) -> str | None:
        session = self._trail_active
        return session.handle if session is not None else None

    @active_trail_handle.setter
    def active_trail_handle(self, handle: str | None) -> None:
        """Make ``handle``'s session active, creating a blank one if needed.

        ``None`` deactivates without closing anything. A non-tabbed host keeps
        at most one session, so a new handle replaces the old session."""
        if handle is None:
            self._trail_active = None
            return
        session = self._trail_sessions.get(handle)
        if session is None:
            if not self._TRAIL_TABBED:
                self._trail_sessions.clear()
            session = TrailSession(handle, reload_gen=self._trail_gen,
                                   drift_gen=self._trail_gen)
            self._trail_sessions[handle] = session
        self._trail_active = session

    def _trail_session(self, handle: str):
        """The open session for ``handle``, or None."""
        return self._trail_sessions.get(handle)

    def _bump_trail_gen(self) -> int:
        """Draw a fresh stamp from the supersession counter."""
        self._trail_gen += 1
        return self._trail_gen

    def _supersede_trail_workers(self) -> None:
        """Retire every in-flight trail worker result: the pending scan and each
        session's reload, drift and xdep probe. The board calls this on
        entering and leaving the By-Trail view (its re-entry points).

        A retired xdep probe also drops its in-flight coverage, so its refs
        read "not checked" until the next start rather than "checking…"
        forever."""
        gen = self._bump_trail_gen()
        self._trail_discovery_gen = gen
        self._trail_link_gen = gen
        for session in self._trail_sessions.values():
            session.reload_gen = gen
            session.drift_gen = gen
            session.xdep_gen = gen
            session.xdep_inflight = frozenset()

    def _drop_trail_link_scan(self) -> None:
        """Retire an in-flight linked-trail search: its result belongs to the
        trail it started from, so a tab switch, a close or a new activation
        means it must not show (t1957_4)."""
        self._trail_link_gen = self._bump_trail_gen()

    def _refresh_trail_tabs(self) -> None:
        """Repaint the host's tab strip. A tabbed host overrides this; the
        board's single-trail view has no strip."""

    def _newest_trail_content(self, handle: str, incoming: tuple) -> tuple:
        """The newest ``(doc, error, versions, read_seq)`` known for ``handle``.

        Candidates: ``incoming``, the discovery-cache entry and the open
        session. The largest ``read_seq`` wins — ``sequenced_trail_read`` makes
        that the read which sampled the stored artifact last — and a tie keeps
        ``incoming``. The ONLY place two reads of a trail are ordered, so a scan
        and a reload that complete in either order converge on one answer."""
        best = incoming
        info = next((i for i in (self._trail_infos or [])
                     if i.handle == handle), None)
        if info is not None and info.read_seq > best[3]:
            best = (info.doc, info.load_error, list(info.versions),
                    info.read_seq)
        session = self._trail_session(handle)
        if session is not None and session.read_seq > best[3]:
            best = (session.doc, session.error,
                    list(session.versions_fallback), session.read_seq)
        return best

    def _store_trail_info_content(self, handle: str, content: tuple) -> None:
        """Write ``content`` into the cached ``TrailInfo`` for ``handle`` in
        place (owner fields kept). No-op when the handle is not cached."""
        infos = self._trail_infos or []
        for idx, info in enumerate(infos):
            if info.handle == handle:
                doc, error, versions, read_seq = content
                infos[idx] = dataclasses.replace(
                    info, doc=doc, load_error=error, versions=list(versions),
                    read_seq=read_seq)
                return

    def _apply_trail_content(self, session, content: tuple, *,
                             restart_drift: bool) -> None:
        """Move ``session`` onto ``content`` and redraw whatever shows it.

        Unchanged content only advances ``read_seq`` — no redraw and no drift
        subprocess, so a plain rescan does not churn every open tab — unless
        ``restart_drift`` (the reload path, whose request cleared the
        verdict). A changed document re-draws ``drift_gen``, so a verdict still
        in flight for the old document is discarded when it lands."""
        doc, error, versions, read_seq = content
        # The recorded versions are content too: they are what the fail-closed
        # error card lists, so a new failing revision with the same error must
        # still reach the session.
        changed = (doc != session.doc or error != session.error
                   or list(versions) != list(session.versions_fallback))
        session.read_seq = max(session.read_seq, read_seq)
        if not changed and not restart_drift:
            return
        session.doc = doc
        session.error = error
        session.versions_fallback = list(versions)
        session.drift = None
        session.drift_gen = self._bump_trail_gen()
        if session is self._trail_active:
            # Start BEFORE rendering: the render reads the xdep probe's
            # in-flight coverage, so a new member must already read
            # "checking…" on this first paint (t1957_1).
            if doc is not None and not error:
                self._start_trail_drift()
            self._rerender_trail()
            self._refresh_subtitle()
            return
        if changed:
            session.updated = True
            # New members: resolve them now, not on the switch to this tab.
            self._resolve_trail_members(session)
        if doc is not None and not error:
            self._start_session_drift(session)
        self._refresh_trail_tabs()

    def _load_trail_tasks(self) -> None:
        """Re-read the task files — and, in a tabbed host, resolve every open
        trail's archived members while I/O is expected.

        ``load_tasks`` clears the manager's archived-task cache, and a trail
        member that is not a live task is projected through
        ``find_task_including_archived`` — which reads the archive, possibly a
        ``zstd``-compressed bundle. Without this, a tab switch after any reload
        (opening another trail runs one) would do that read on the UI thread,
        breaking the in-memory switch. Resolving here leaves the switch with
        cache hits only. The board has one session, which it re-renders
        right after every reload anyway."""
        self.manager.load_tasks()
        if self._TRAIL_TABBED:
            tasks_by_id = self._live_tasks_by_id()     # once for every tab
            for session in self._trail_sessions.values():
                self._resolve_trail_members(session, tasks_by_id)

    def _resolve_trail_members(self, session, tasks_by_id=None) -> None:
        """Warm the manager's archive cache for ``session``'s members by running
        the same projection a render runs (and discarding it), so the lookups
        are exactly the ones a later render — a tab switch — will make."""
        if session.doc is None or session.error:
            return
        if tasks_by_id is None:
            tasks_by_id = self._live_tasks_by_id()
        build_trail_lanes(session.doc, tasks_by_id, self._get_local_project(),
                          self.manager.find_task_including_archived, {})

    def _store_trail_focus(self) -> None:
        """Remember the focused card in the active session (tab switch)."""
        session = self._trail_active
        focused = self._focused_card()
        if session is not None and focused is not None:
            session.focus_filename = focused.task_data.filename
            session.focus_col_id = focused.column_id

    def _show_trail_session(self, session) -> None:
        """Render ``session`` as the active one from memory: zero subprocesses,
        no task reload, no drift re-run. Its saved focus is restored."""
        # Drop the outgoing card's focus first, so the re-render does not carry
        # the old trail's column over as the refocus target.
        self.screen.set_focus(None)
        self._trail_active = session
        session.updated = False
        self._rerender_trail()
        self._queue_refocus(session.focus_filename, session.focus_col_id)
        self._refresh_trail_tabs()
        self.refresh_bindings()

    def _switch_trail_session(self, handle: str) -> None:
        """Tab switch: make the open session for ``handle`` active."""
        session = self._trail_session(handle)
        if session is None or session is self._trail_active:
            return
        self._drop_trail_link_scan()
        self._store_trail_focus()
        self._show_trail_session(session)

    def _close_trail_session(self, handle: str) -> None:
        """Close ``handle``'s tab. The artifact-version watch belongs to its
        trail, so closing the trail is what stops it. Closing the active tab
        shows its right-hand neighbour (else the left one), or the empty state
        when none is left."""
        session = self._trail_session(handle)
        if session is None:
            return
        self._drop_trail_link_scan()
        order = list(self._trail_sessions)
        idx = order.index(handle)
        del self._trail_sessions[handle]
        if self._trail_watch_handle == handle:
            self._stop_trail_watch()
        if session is self._trail_active:
            remaining = list(self._trail_sessions.values())
            if remaining:
                self._show_trail_session(remaining[min(idx, len(remaining) - 1)])
                return
            self._trail_active = None
            self.screen.set_focus(None)
            self._rerender_trail()
        self._refresh_trail_tabs()
        self.refresh_bindings()

    def _has_trail_capability(self, action: str) -> bool:
        """Whether this host provides every optional member ``action`` needs.

        ``trail_move_wave`` and ``trail_sync`` reach board-only machinery (the
        move review chain, task-data sync). A host without it still declares
        their bindings (one override owner, C10) but must neither show nor run
        them; the action methods check this first so a remapped key or the
        command palette cannot reach a missing member either."""
        return all(hasattr(self, name)
                   for name in TRAIL_ACTION_CAPABILITIES.get(action, ()))

    def _open_trail_entry_detail(self, card) -> bool:
        """Open the trail detail projection for a trail card (RFC §9.1).

        Returns False — opening nothing — when ``card`` is not a trail card, so
        the host's ``action_view_details`` can fall through to its own detail.
        Duck-typed on ``trail_entry``: live and ghost trail cards both carry it."""
        entry = getattr(card, "trail_entry", None)
        if entry is None:
            return False
        reasons = self._trail_drift[1] if self._trail_drift else []
        self.push_screen(TrailDetailScreen(
            self._trail_doc or {}, reasons, entry=entry,
            wave=getattr(card, "trail_wave", None)))
        return True

    # --- By-Trail view (t1210_4) ---
    # Read-only in-process: rendering, selection, detail and drift checks all
    # run here; every trail WRITE happens in the launched /aitask-trail skill.

    def _trail_depth_note(self) -> str:
        """`" · lite"` / `" · deep"` from the trail's advisory
        ``rendering_hints.depth`` (t1505_1 label_trail_depth), else `""`.

        An **absent** hint renders NOTHING — never "deep". Every trail authored
        before t1505_4 started writing the hint carries none, and defaulting
        would state a falsehood about all of them. An *unrecognised* value is
        also ignored rather than echoed: the header is a fixed-width budget, not
        a place to render arbitrary artifact strings."""
        hints = (self._trail_doc or {}).get("rendering_hints")
        if not isinstance(hints, dict):
            return ""
        depth = hints.get("depth")
        if isinstance(depth, str) and depth.strip().lower() in ("lite", "deep"):
            return f" · {depth.strip().lower()}"
        return ""

    def _trail_generated_note(self) -> str:
        """`" · gen 07-10 17:00"` — when the trail was generated, in local time
        (t2112), else `""`.

        An absent, non-string or unparseable ``generation.generated_at``
        renders NOTHING — no `?`, no raw value: the header is a fixed-width
        budget, not a place to render arbitrary artifact strings. Only an
        agent refresh rewrites the value, and both trail-doc seams funnel into
        ``_refresh_subtitle``, so a new timestamp shows with no extra wiring."""
        generation = (self._trail_doc or {}).get("generation")
        if not isinstance(generation, dict):
            return ""
        label = trail_generated_label(generation.get("generated_at"))
        return f" · gen {label}" if label else ""

    def _trail_banner(self, title: str, suffix: str, owner_note: str,
                      depth_note: str = "", gen_note: str = "") -> str:
        """Compose the By-Trail banner so the freshness marker always survives.

        HeaderTitle ellipsis-truncates the TAIL, and the marker is the tail —
        so without this the one volatile signal is the FIRST thing lost as the
        terminal narrows. Measured before this shed (t1278): at 80 columns with
        a short trail title, "(⚠ stale: 3)" already clipped to "(⚠ s…"; with a
        long title it clipped at 120. 80 columns is an ordinary terminal, so
        the header fix alone did not make the banner readable.

        Sheds context from the widest rung down until it fits the measured
        budget, dropping the trail title (recoverable — it is also on the
        selection modal and the lanes) before the marker."""
        budget = self._banner_budget()
        # Depth is ADDITIVE-IF-IT-FITS (t1505_1): shown only while the
        # untruncated banner still fits, then dropped whole. It is deliberately
        # NOT threaded through the rungs below as an owner_note sibling — that
        # would make the title shed earlier than it does today for every trail
        # carrying a hint, and would leave no rung at which depth alone is
        # dropped (it would survive to rung 3 and then vanish in the same cliff
        # that drops the title). Kept out of the ladder, the rungs below stay
        # byte-identical to their pre-t1505_1 behaviour for every trail, and the
        # volatile freshness marker is still the last survivor.
        #
        # The generation note (t2112) follows the same rule for the same
        # reasons: it is dropped whole before the title is ever elided, so the
        # rungs below stay byte-identical for trails with and without it. It
        # sits right after the title it describes — safe, since it only appears
        # when the whole string fits. Between the two additive notes,
        # generation is tried FIRST and depth is added only if it still fits:
        # the age is what a reader cannot get elsewhere on screen, while depth
        # is an advisory rendering hint.
        def fits(text: str) -> bool:
            return not budget or cell_len(text) <= budget

        def compose(gen: str, depth: str) -> str:
            return f'By-Trail: "{title}"{gen}{suffix}{owner_note}{depth}'

        shown_gen = gen_note if gen_note and fits(compose(gen_note, "")) else ""
        shown_depth = (depth_note if depth_note
                       and fits(compose(shown_gen, depth_note)) else "")
        if shown_gen or shown_depth:
            return compose(shown_gen, shown_depth)
        full = f'By-Trail: "{title}"{suffix}{owner_note}'
        if not budget or cell_len(full) <= budget:
            return full
        # Rung 2: keep the marker, elide the title to whatever room is left.
        fixed = f'By-Trail: ""{suffix}{owner_note}'
        room = budget - cell_len(fixed)
        if room >= 2:
            return (f'By-Trail: "{set_cell_size(title, room - 1)}…"'
                    f'{suffix}{owner_note}')
        # Rung 3: no room for any title at all.
        without_title = f"By-Trail:{suffix}{owner_note}"
        if cell_len(without_title) <= budget:
            return without_title
        # Rung 4: even the label does not fit — the marker alone is what
        # matters. Bare (no parens): it is no longer a suffix to anything.
        return suffix.strip().strip("()") or without_title

    def _refresh_trail_summary(self) -> str:
        """Single owner of the By-Trail summary pane (t1505_1).

        Resolves the summary ONCE and writes the pane's body text and its
        visibility together, returning the resolved text so the expand modal
        renders exactly what the pane shows.

        **Content and visibility must move together.** ``self._trail_doc`` is
        rewritten at two seams — ``_activate_trail`` (the `s` trail switch) and
        ``_on_trail_reload`` (the artifact reload / version watch) — and both
        already funnel into ``_refresh_subtitle``, which calls this. Refreshing
        ``display`` there while writing the body anywhere else would leave the
        pane, and the modal built from it, showing the PREVIOUS trail's summary
        after a switch: a wrong answer that renders exactly like a right one and
        that a presence-only test cannot see."""
        text = ("" if self.base_filter != "bytrail"
                else trail_summary_text(self._trail_doc))
        try:
            pane = self.query_one("#trail_summary")
            body = self.query_one("#trail_summary_body", Static)
        except NoMatches:
            # Called before the first compose (on_mount runs _update_subtitle
            # via refresh_board). The resolved text is still correct for the
            # caller; the pane picks it up on the next refresh.
            return text
        # Text(), not the bare str: trail prose is free-form, so brackets in it
        # are content. Rendering it as markup would silently swallow a literal
        # "[blocked]" and would raise MarkupError on a bracketed URL — from
        # inside _refresh_subtitle, taking the banner down with the pane. The
        # modal renders through Text() for the same reason.
        body.update(Text(text))
        pane.display = bool(text)
        return text

    def _refresh_subtitle(self):
        """Single writer for By-Trail chrome — the app subtitle **and** the
        summary pane (t1210_4; pane added t1505_1).

        By-Trail with a selected trail → the trail banner (title + freshness
        suffix); every other state → the auto-refresh status. All subtitle
        updates (view switches, drift callbacks, settings changes, resizes)
        route through here, so leaving By-Trail restores the auto-refresh
        text — and, since t1505_1, hides the summary pane and gives the lanes
        their full height back."""
        self._refresh_trail_summary()
        if self.base_filter == "bytrail" and self.active_trail_handle:
            if self._trail_error:
                # Left unbudgeted deliberately (t1278): a clipped tail here
                # loses part of a handle the user just selected, not a
                # volatile freshness signal.
                self.sub_title = (f"By-Trail: {self.active_trail_handle} — "
                                  f"trail unavailable")
            elif self._trail_doc:
                title = str(self._trail_doc.get("title")
                            or self.active_trail_handle)
                if self._trail_drift is None:
                    suffix = " (⟳ checking freshness…)"
                else:
                    verdict, reasons = self._trail_drift
                    if verdict == "STALE":
                        suffix = f" (⚠ stale: {max(len(reasons), 1)})"
                    elif verdict == "CURRENT":
                        suffix = ""
                    else:
                        kind = verdict.split(":", 2)[1] if ":" in verdict else verdict
                        suffix = f" (drift unavailable: {kind})"
                # §9.2: an archived trail owner is noted on the banner.
                owner_note = ""
                if self._trail_owner_archived:
                    owner = (f"t{self._trail_owner_id}"
                             if self._trail_owner_id else "task")
                    owner_note = f" · owner {owner} archived"
                self.sub_title = self._trail_banner(
                    title, suffix, owner_note, self._trail_depth_note(),
                    self._trail_generated_note())
            else:
                self.sub_title = f"By-Trail: {self.active_trail_handle}"
            return
        minutes = self.manager.auto_refresh_minutes
        sync = self.manager.settings.get("sync_on_refresh", False)
        if minutes > 0:
            suffix = " + sync" if sync else ""
            self.sub_title = f"Auto-refresh: {minutes}min{suffix}"
        else:
            self.sub_title = "Auto-refresh: off"

    def _rerender_trail(self, refocus_filename: str = ""):
        """Re-mount the By-Trail lanes from in-memory state only.

        Deliberately does NOT call refresh_git_status() / refresh_lock_map() /
        xdep_status_cache.clear() the way refresh_board() does. TrailTaskCard
        and TrailGhostCard fully override TaskCard.compose, and every reader of
        modified_files / lock_map / xdep_status_cache lives in that base
        compose — so By-Trail consumes none of it. Their cross-repo lines read
        the session's ``xdep`` / ``xdep_inflight``, which a worker fills off
        the UI thread (t1957_1) — never a probe in compose. Routing this view through
        refresh_board() would block the UI thread on `git status` (5s timeout)
        and `aitask_lock.sh --list` (10s timeout) to produce an identical
        render (t1268).

        PRECONDITION: both trail cards override TaskCard.compose. A future
        trail card that reads is_modified / lock_map must either refresh that
        state itself or stop using this helper.
        """
        if self.base_filter != "bytrail":
            return
        refocus_col_id = self._get_focused_col_id() or ""
        container = self.query_one("#board_container")
        container.remove_children()
        self._render_bytrail(container)
        self.call_after_refresh(self.apply_filter)
        self._queue_refocus(refocus_filename, refocus_col_id)

    def action_trail_summary_expand(self):
        """`v` in By-Trail: open the trail summary full-height and scrollable.

        Re-checks the same condition `check_action` gates on. **A binding gate
        is not an action guard:** check_action controls footer visibility and
        key dispatch, but the action stays reachable through the command
        palette, a user remap, or a race with a view switch — so the guard has
        to live here too.

        The text comes from `_refresh_trail_summary()`, the single owner, rather
        than from a second `trail_summary_text(self._trail_doc)` call, so the
        modal always shows exactly what the pane shows."""
        if self._modal_is_active():
            return
        if self.base_filter != "bytrail":
            return
        summary = self._refresh_trail_summary()
        if not summary:
            return
        title = str((self._trail_doc or {}).get("title")
                    or self.active_trail_handle or "")
        self.push_screen(TrailSummaryScreen(summary, title))

    def action_trail_refresh_local(self):
        """`r` in By-Trail: reload task files from disk and re-project the
        CACHED trail document. Zero subprocesses, no agent, no artifact read —
        a card whose frontmatter status changed on disk updates immediately."""
        if self._modal_is_active():
            return
        focused = self._focused_card()
        refocus = focused.task_data.filename if focused else ""
        self._load_trail_tasks()           # file I/O; archive reads (see there)
        self._rerender_trail(refocus)

    def action_trail_refresh_drift(self):
        """`d` in By-Trail: re-fetch the stored artifact and re-run the
        read-only drift check. Never writes the artifact."""
        if self._modal_is_active():
            return
        self._reload_active_trail()

    def action_trail_refresh_agent(self):
        """`R` in By-Trail: launch /aitask-trail --refresh for the active
        trail (the heavyweight, model-authored refresh)."""
        if (self._modal_is_active() or not self.active_trail_handle
                or self._trail_launch_pending):
            return
        handle_id = self.active_trail_handle
        if handle_id.startswith("art:"):
            handle_id = handle_id[len("art:"):]
        # The version watch is installed inside _launch_trail's result
        # callback, on a CONFIRMED launch only — _launch_trail merely pushes a
        # confirmation dialog. Arming here would orphan a watch on cancel and
        # burn the tick ceiling while the dialog sits open.
        #
        # debounce_key (t1279): the dialog binds `R` to Run, so without this a
        # second `R` tapped while the dialog is opening confirms it and
        # launches the agent unreviewed. This covers the dialog's first
        # OPENING_DEBOUNCE_SECONDS; the `_trail_launch_pending` guard above
        # covers the DISJOINT window that starts once the dialog has closed and
        # the baseline read is in flight. Neither is a duplicate of the other —
        # do not delete one as redundant.
        self._launch_trail(["--refresh", self.active_trail_handle],
                           handle_id, watch_handle=self.active_trail_handle,
                           debounce_key=resolve_key(
                               "board", "trail_refresh_agent", "R") or "R")

    def action_trail_select(self):
        """`s` in By-Trail: open the trail selector.

        The board re-scans every time. A tabbed host serves the discovery cache
        and re-scans only when it is missing or EMPTY: a successful zero-trail
        scan must not pin a dead end, because an empty list never opens the
        selector whose `r` key would re-scan (t1895)."""
        if self._modal_is_active():
            return
        self._open_trail_select(
            rescan=not self._TRAIL_TABBED or not self._trail_infos)

    def action_trail_sync(self):
        """`S` in By-Trail: ait sync, then the local recompute.

        Task data lives on the aitask-data branch, so a status changed by a
        remote agent or another machine only reaches this checkout via a
        sync — previously unreachable from this view (t1268)."""
        if not self._has_trail_capability("trail_sync"):
            return
        if self._modal_is_active():
            return
        self.push_screen(LoadingOverlay("Syncing with remote..."))
        self._run_sync(show_notification=True, show_overlay=True)

    def action_trail_move_wave(self) -> None:
        """`M`: move the focused wave's tasks to a column, in position order.

        The By-Trail half of the passive t1162 report bridge (RFC §9.4/§10):
        the user moves a whole wave into a board column, and the Work Report
        reads that column unchanged. The trail artifact is never consulted or
        modified by the move.
        """
        if not self._has_trail_capability("trail_move_wave"):
            return
        if self._modal_is_active():
            return
        # A binding gate is not an action guard — the palette calls action_*
        # directly (same reason action_trail_summary_expand re-checks).
        if self.base_filter != "bytrail":
            return
        focused = self._focused_card()
        if focused is None:
            return
        # Same ghost guard as `m`, and for the same reason: check_action hides
        # `M` on a ghost, but the palette dispatches straight here. Refuse with
        # a reason rather than silently — RFC §9.1 gives ghosts no move action,
        # so saying so beats looking broken.
        if getattr(focused, "is_ghost", False):
            self.notify("Read-only trail member — move the wave from a live "
                        "card in it.", severity="warning")
            return
        lane = next((c for c in self.query(TrailColumn)
                     if c.col_id == focused.column_id), None)
        if lane is None:
            return

        names, ghosts, children, dupes, seen = [], [], [], [], set()
        for view in lane.wave_entries():            # position order
            ref = str(view.entry.get("task") or "?")
            if view.task is None:
                ghosts.append(ref)
            elif "_" in (task_own_id(view.task) or ""):
                children.append(ref)
            elif view.task.filename in seen:
                # Two entries, one task. `entry_id` is unique and `position`
                # strictly increasing, but trail_schema enforces NOTHING on
                # `entry.task` — the same ref may legally appear twice in a
                # wave, and both render. `MoveTaskSelectScreen`'s row key must
                # be unique (it is the SelectionList value), so dedup here, on
                # FIRST occurrence, keeping the earliest position's slot.
                dupes.append(ref)
            else:
                seen.add(view.task.filename)
                names.append(view.task.filename)

        # Which-item reports, never a bare count (the t1243_6 refusal idiom).
        skipped = []
        if ghosts:
            skipped.append(f"{len(ghosts)} ghost: " + ", ".join(ghosts[:3]))
        if children:
            skipped.append(f"{len(children)} child: " + ", ".join(children[:3]))
        if not names:
            detail = (" — " + "; ".join(skipped)) if skipped else ""
            self.notify(f"Nothing movable in this wave{detail}",
                        severity="warning")
            return
        if skipped:
            self.notify("Skipping " + "; ".join(skipped))
        if dupes:
            # Not a skip — the task still moves, once. Reported so a review
            # dialog listing fewer rows than the wave shows is explained.
            self.notify(f"{len(dupes)} task(s) appear twice in this wave "
                        f"({', '.join(dupes[:3])}) — moving each once.")
        # ALWAYS review: a wave is a bulk action and the search filter may have
        # hidden some of its cards. `_review_then` preserves the order it is
        # given and MoveTaskSelectScreen confirms in displayed order, which
        # `move_tasks_to_column` consumes verbatim — so the destination
        # sequence matches wave order. Deliberately NOT `_board_order()`: that
        # re-sorts by column/boardidx and would destroy exactly that.
        #
        # The SAME destination method `action_move_to_column` uses — one chain,
        # not a parallel one.
        self._review_then(names, self._choose_move_destination)

    # --- Linked trails (t1957_4) --------------------------------------------
    # `L`: search the other registered projects for trails linked to the
    # active one (lib/trail_links.py), list them, and jump to the chosen one.

    def _trail_link_ready(self) -> bool:
        """Whether the active trail can be searched from: it has loaded and did
        not fail closed. An unloaded trail has no known members, and a scan of
        none comes back COMPLETE and empty — the definitive "no linked trails"
        for a trail whose members nobody read."""
        return bool(self.active_trail_handle and self._trail_doc
                    and not self._trail_error)

    def action_trail_linked(self) -> None:
        """`L` in By-Trail: search for linked trails off the UI thread.

        The search reads a private SNAPSHOT of the trail and remembers it: a
        reload or a rescan can replace the session's document in place while
        the scan runs, and links found for the old members must not show as
        the new revision's.

        Presses while a scan runs coalesce: only the newest is kept, and it
        runs when that scan lands (`_on_trail_links`)."""
        if self._modal_is_active():
            return
        # A binding gate is not an action guard — the palette and a remap
        # reach this directly (same reason as action_trail_summary_expand).
        if self.base_filter != "bytrail":
            return
        if not self._trail_link_ready():
            self.notify("Trail not loaded — nothing to search from",
                        severity="warning")
            return
        origin = self._trail_active
        source = (copy.deepcopy(origin.doc), origin.error)
        gen = self._trail_link_gen = self._bump_trail_gen()
        self.notify("Searching for linked trails in other projects…")
        if self._trail_link_running:
            self._trail_link_pending = (gen, origin, source)
            return
        self._start_trail_link_scan(gen, origin, source)

    def _start_trail_link_scan(self, gen: int, origin, source: tuple) -> None:
        self._trail_link_running = True
        self._trail_link_worker(gen, origin, source)

    # Every non-exclusive worker in this mixin runs in its own group:
    # `exclusive` workers in the default group (`_run_sync`,
    # `run_dialog_command`) cancel every worker there, and one cancelled
    # before it started never runs its body or its `finally` — so state set
    # before the start and reset only by the callback stays stuck. Here the
    # scan slot would stay taken and every later `L` would only queue (t1979,
    # t1988).
    @work(thread=True, group="trail_link")
    def _trail_link_worker(self, gen: int, origin, source: tuple):
        scan, error = None, ""
        try:
            scan = scan_linked_trails(source[0])
        except Exception as exc:          # a crash is a result, not silence
            error = str(exc) or type(exc).__name__
        finally:
            self.app.call_from_thread(self._on_trail_links, gen, origin,
                                      source, scan, error)

    def _on_trail_links(self, gen: int, origin, source: tuple, scan,
                        error: str) -> None:
        # Free the scan slot FIRST — before any early return — or every later
        # `L` would only queue. The pending request runs only while it is
        # still current: a tab switch / close / activation and leaving the view
        # retire it by drawing a new `_trail_link_gen`, exactly as they retire
        # a running scan's result.
        self._trail_link_running = False
        pending, self._trail_link_pending = self._trail_link_pending, None
        if pending is not None and pending[0] == self._trail_link_gen:
            self._start_trail_link_scan(*pending)
        # Supersession: a newer search, a tab switch / close / activation, or
        # leaving the view retired this one — the user moved on, say nothing.
        if (gen != self._trail_link_gen or self.base_filter != "bytrail"
                or self._trail_active is not origin
                or self._trail_session(origin.handle) is not origin):
            return
        # Same trail, newer content. Equality, not identity: an unchanged
        # reload still assigns a fresh (equal) document object.
        if origin.doc != source[0] or origin.error != source[1]:
            self.notify(f"Trail {origin.handle} changed during the "
                        "linked-trail search — press L to search again",
                        severity="warning", markup=False)
            return
        if error:
            self.notify(f"Linked-trail search failed: {error}",
                        severity="error", markup=False)
            return
        if self._modal_is_active():
            # Stacking on another modal could strand it (a LoadingOverlay pops
            # itself only while it is on top).
            self.notify("Linked-trail search finished while a dialog was "
                        "open — press L again")
            return
        if not scan.links and scan.complete:
            self.notify("No linked trails in other projects")
            return
        self.push_screen(
            LinkedTrailsScreen(scan.links, scan.errors, scan.complete),
            self._on_linked_trail_chosen)

    def _on_linked_trail_chosen(self, link) -> None:
        if link is None:
            return
        if self._trail_jump_busy:
            self.notify("A jump is already in progress", severity="warning")
            return
        self._trail_jump_busy = True
        self._trail_jump_prepare_worker(link)

    # Own group (see `_trail_link_worker`): a cancel before start would leave
    # `_trail_jump_busy` set and refuse every later jump.
    @work(thread=True, group="trail_jump")
    def _trail_jump_prepare_worker(self, link):
        jump = TrailJump(link, error=f"Jump to {link.handle} failed")
        try:
            jump = prepare_linked_trail_jump(link)
        except Exception as exc:
            jump = TrailJump(link, error=(
                f"Jump to {link.handle} failed: "
                f"{str(exc) or type(exc).__name__}"))
        finally:
            self.app.call_from_thread(self._on_trail_jump_prepared, jump)

    def _on_trail_jump_prepared(self, jump: TrailJump) -> None:
        if jump.error:
            self._trail_jump_busy = False
            self.notify(jump.error, severity="error", markup=False,
                        timeout=12)
            return
        carried = self._trail_jump_unread.pop(str(jump.link.root), ())
        if carried:
            jump = dataclasses.replace(jump, notices=tuple(
                dict.fromkeys((*carried, *jump.notices))))
        if not jump.to_confirm:
            self._trail_jump_finish_worker(jump)
            return
        if self._modal_is_active():
            # Same no-stacking rule as the search result. Only the one-time
            # notices are kept for the retry: it cannot produce them again,
            # while its own warnings describe the target as it is then.
            if jump.notices:
                self._trail_jump_unread[str(jump.link.root)] = jump.notices
            self._trail_jump_busy = False
            self.notify(f"Jump to {jump.link.handle} paused — a dialog was "
                        "open. Press L to try again", severity="warning",
                        markup=False)
            return

        def on_confirm(go) -> None:
            if go:
                self._trail_jump_finish_worker(jump)
            else:
                self._trail_jump_busy = False

        self.push_screen(
            TrailJumpConfirmScreen(jump.session, jump.to_confirm), on_confirm)

    @work(thread=True, group="trail_jump")      # as the prepare worker
    def _trail_jump_finish_worker(self, jump: TrailJump):
        notices = [(f"Jump to {jump.link.handle} failed", "error")]
        try:
            notices = finish_linked_trail_jump(jump)
        except Exception as exc:
            notices = [(f"Jump to {jump.link.handle} failed: "
                        f"{str(exc) or type(exc).__name__}", "error")]
        finally:
            self.app.call_from_thread(self._on_trail_jump_done, notices)

    def _on_trail_jump_done(self, notices) -> None:
        self._trail_jump_busy = False
        for message, severity in notices:
            self.notify(message, severity=severity, markup=False, timeout=12)

    def _get_local_project(self) -> str:
        """Lazily cached project name for canonical-ref resolution."""
        if self._local_project is None:
            self._local_project = load_local_project_name(self.tasks_dir)
        return self._local_project

    def _render_bytrail(self, container):
        """Mount the By-Trail content per the §9.2 state matrix."""
        if not self.active_trail_handle:
            hint = ("No trail selected — press s to choose one, or create a "
                    "trail with T on a task card (or /aitask-trail).")
            if self._trail_infos is not None and not self._trail_infos:
                hint = ("No implementation trails found — create one with T "
                        "on a task card (or /aitask-trail).")
            container.mount(Static(Text(hint), classes="trail-empty"))
            self._refresh_subtitle()
            return
        if self._trail_error:
            # Missing blob / corrupt manifest / schema-invalid document:
            # fail closed — an error card, never a partial render (§9.2/§12).
            lines = [f"Trail {self.active_trail_handle} could not be loaded "
                     f"(fail-closed):",
                     f"  {self._trail_error}"]
            if self._trail_versions_fallback:
                lines.append("")
                lines.append("Recorded versions (ait artifact versions "
                             f"{self.active_trail_handle}):")
                lines.extend(f"  {v}" for v in self._trail_versions_fallback)
            lines.append("")
            lines.append("Press s to select another trail.")
            container.mount(Static(Text("\n".join(lines)),
                                   classes="trail-error"))
            self._refresh_subtitle()
            return
        if not self._trail_doc:
            container.mount(Static(Text("Loading trail…"),
                                   classes="trail-empty"))
            self._refresh_subtitle()
            return
        if not self._get_local_project():
            container.mount(Static(Text(
                "Warning: project name unavailable "
                "(aitasks/metadata/project_config.yaml) — all trail members "
                "render as unresolvable ghosts."), classes="trail-error"))
        for lane in self._build_active_trail_lanes():
            container.mount(TrailColumn(lane, self.manager))
        self._refresh_subtitle()

    def _live_tasks_by_id(self) -> dict:
        """The live By-Topic task universe, keyed by own id."""
        all_tasks = (list(self.manager.task_datas.values())
                     + list(self.manager.child_task_datas.values()))
        tasks_by_id = {}
        for task in all_tasks:
            own = task_own_id(task)
            if own:
                tasks_by_id.setdefault(own, task)
        return tasks_by_id

    def _build_active_trail_lanes(self):
        """Project the active trail onto the live By-Topic task universe."""
        drift_by_ref = trail_drift_by_ref(
            self._trail_drift[1] if self._trail_drift else [])
        return build_trail_lanes(
            self._trail_doc, self._live_tasks_by_id(), self._get_local_project(),
            self.manager.find_task_including_archived, drift_by_ref,
            xdep_status=self._trail_xdep,
            xdep_inflight=self._trail_xdep_inflight)

    def _open_trail_select(self, rescan: bool = False, then=None):
        """Open the trail-selection modal, running discovery when needed.

        ``then`` replaces the selector as the continuation once the discovery
        cache is current (a fresh scan reconciled, or the cache served as is):
        `_open_trail_by_handle` uses it to look a handle up after a rescan."""
        if self._modal_is_active():
            return
        # Only the scan is superseded here: open sessions' reloads and drift
        # checks keep running while the selector is up.
        self._trail_discovery_gen = self._bump_trail_gen()
        if rescan or self._trail_infos is None:
            # Persistent busy affordance for the archive scan + blob loads.
            overlay = LoadingOverlay("Scanning for trails…")
            self.push_screen(overlay)
            self._trail_discovery_worker(self._trail_discovery_gen, overlay,
                                         then)
        else:
            (then or self._open_trail_select_from_cache)()

    # Own group (see `_trail_link_worker`): a cancel before start would never
    # pop the overlay.
    @work(thread=True, group="trail_discovery")
    def _trail_discovery_worker(self, gen: int, overlay, then=None):
        """Discovery + blob loads off the UI thread (subprocess-heavy)."""
        infos, unreadable = discover_trails()
        self.app.call_from_thread(self._on_trail_discovery, gen, infos,
                                  unreadable, overlay, then)

    def _on_trail_discovery(self, gen: int, infos: list, unreadable: list,
                            overlay, then=None):
        # Pop OUR overlay first (even for superseded results — each scan owns
        # its own overlay instance, so a stale callback can never pop a newer
        # scan's overlay).
        if overlay is not None and self.screen is overlay:
            self.pop_screen()
        # Supersession guard: discard when the view moved on mid-scan.
        if gen != self._trail_discovery_gen or self.base_filter != "bytrail":
            return
        if unreadable:
            shown = ", ".join(unreadable[:3])
            if len(unreadable) > 3:
                shown += f" (+{len(unreadable) - 3} more)"
            self.notify(
                f"Trail scan skipped {len(unreadable)} unreadable active task "
                f"file(s): {shown} — the list may be incomplete; press s to "
                "retry.", severity="warning")
        if not infos and unreadable:
            # A torn read is a retryable snapshot race, not an answer. ASSIGN
            # None rather than merely returning: _open_trail_select does not
            # clear the cache before a rescan, so an earlier scan's handles
            # would otherwise survive this one and stay live for
            # _activate_trail's lookup. None also keeps the result
            # non-authoritative — _render_bytrail's definitive "No
            # implementation trails found" hint is gated on `is not None` (t1365).
            self._trail_infos = None
            if not self.active_trail_handle:
                # Redraw so the definitive hint gives way to the neutral one.
                # Only safe with no active trail: the view then holds just that
                # hint, so there is no card focus or column scroll to lose.
                self._rerender_trail()
            return
        self._reconcile_discovered_trails(infos)
        (then or self._open_trail_select_from_cache)()

    def _reconcile_discovered_trails(self, infos: list) -> None:
        """Adopt a scan's result without letting it roll anything back.

        A reload of an open trail can land while the scan runs, and its read
        may have sampled the artifact later than the scan's own read of that
        trail. Each returned entry therefore takes the newest content known for
        its handle (owner fields stay the scan's), and an open session moves
        onto that content too — so neither the cache nor a tab is left on an
        older revision, whichever result completed first."""
        resolved = []
        for info in infos:
            best = self._newest_trail_content(
                info.handle, (info.doc, info.load_error, list(info.versions),
                              info.read_seq))
            resolved.append(dataclasses.replace(
                info, doc=best[0], load_error=best[1], versions=list(best[2]),
                read_seq=best[3]))
        self._trail_infos = resolved
        for info in resolved:
            session = self._trail_session(info.handle)
            if session is None:
                continue
            # Ownership comes from the task frontmatter the scan just read, not
            # from the artifact, so it is adopted whatever the content did.
            self._apply_trail_owner(session, info)
            # Strictly newer only: an equal sequence (both unknown) is no
            # evidence that the scan's copy should replace the tab's.
            if info.read_seq > session.read_seq:
                self._apply_trail_content(
                    session, (info.doc, info.load_error, list(info.versions),
                              info.read_seq), restart_drift=False)

    def _apply_trail_owner(self, session, info) -> None:
        """Move ``session`` onto the scan's owner (id and archived state) — the
        §9.2 banner note — and redraw what shows it."""
        owner = (info.owner_id, bool(info.owner_archived))
        if owner == (session.owner_id, session.owner_archived):
            return
        session.owner_id, session.owner_archived = owner
        if session is self._trail_active:
            self._refresh_subtitle()
        else:
            session.updated = True
            self._refresh_trail_tabs()

    def _open_trail_select_from_cache(self):
        infos = self._trail_infos or []
        if not infos:
            self.notify("No implementation trails found — create one with T "
                        "on a task card (or /aitask-trail).")
            if self.base_filter == "bytrail":
                self.refresh_board()
            return

        def on_select(handle):
            if handle is None:
                return
            if handle == TRAIL_SELECT_RESCAN:
                self._open_trail_select(rescan=True)
                return
            self._activate_trail(handle)

        tabbed = self._TRAIL_TABBED
        self.push_screen(
            TrailSelectScreen(
                infos, compute_trail_overlaps(infos),
                open_handles=set(self._trail_sessions) if tabbed else (),
                allow_rescan=tabbed),
            on_select)

    def _open_trail_by_handle(self, handle: str, rescan: bool = True,
                              is_current=None) -> None:
        """Open ``handle`` by name — `ait trails --trail` and the focus mailbox.

        `_activate_trail` alone cannot: with no discovery entry it builds a
        session with no document that never loads. So an open tab or a cached
        handle activates at once; an unknown one is looked up again after ONE
        rescan (a trail authored after this App's last scan), and a handle still
        unknown after that is reported and the selector offered instead.

        ``is_current`` lets the caller retire the request: a request superseded
        while its rescan ran must activate nothing when the scan lands. Never
        acts under a modal (the caller decides what a modal means)."""
        if self._modal_is_active():
            return
        if is_current is not None and not is_current():
            return
        known = (self._TRAIL_TABBED and handle in self._trail_sessions) or any(
            i.handle == handle for i in (self._trail_infos or []))
        if known:
            self._activate_trail(handle)
        elif rescan:
            self._open_trail_select(
                rescan=True,
                then=lambda: self._open_trail_by_handle(
                    handle, rescan=False, is_current=is_current))
        else:
            self.notify(f"Trail {handle} not found in this project",
                        severity="warning")
            self._open_trail_select_from_cache()

    def _activate_trail(self, handle: str):
        """Make ``handle`` the active trail and render it.

        A tabbed host switches to an already-open trail from memory; any other
        activation builds a fresh session from the discovery cache. The board
        keeps one session, so that replaces (and un-watches) the old trail; a
        tabbed host keeps the outgoing tab — its focus, and its watch."""
        self._drop_trail_link_scan()
        if self._TRAIL_TABBED and handle in self._trail_sessions:
            self._switch_trail_session(handle)
            return
        # Discovery reads task files from disk, but the LANE PROJECTION still
        # builds tasks_by_id from the manager. A freshly authored trail usually
        # references tasks created after board start, so without this its
        # members would render as missing ghosts until the user pressed `r`
        # (t1365). Here rather than in the discovery callback: this is the one
        # activation funnel, it is followed by a full refresh_board(), and the
        # selector's Esc-cancel path is left untouched — replacing Task objects
        # while the modal is open would strand the board's card references with
        # no focused card to restore (_focused_card queries "TaskCard:focus",
        # which is empty behind a modal).
        self._load_trail_tasks()
        if self._TRAIL_TABBED:
            self._store_trail_focus()
        else:
            # A watch belongs to the trail it was installed for (t1268).
            self._stop_trail_watch()
            self._trail_sessions.clear()
        info = next((i for i in (self._trail_infos or [])
                     if i.handle == handle), None)
        gen = self._bump_trail_gen()
        session = TrailSession(
            handle,
            doc=info.doc if info else None,
            error=info.load_error if info else "",
            versions_fallback=list(info.versions) if info else [],
            owner_id=info.owner_id if info else "",
            owner_archived=bool(info.owner_archived) if info else False,
            reload_gen=gen, drift_gen=gen,
            read_seq=info.read_seq if info else 0)
        self._trail_sessions[handle] = session
        self._trail_active = session
        # Start before the render, which reads the xdep probe's coverage.
        if self._trail_doc is not None and not self._trail_error:
            self._start_trail_drift()
        self.refresh_board()
        self._refresh_subtitle()
        self._refresh_trail_tabs()
        self.refresh_bindings()

    def _start_trail_drift(self):
        """Kick the read-only drift check for the active trail (view entry /
        activation). Updates rendered badges only — never the artifact."""
        if self._trail_active is None:
            return
        self._start_session_drift(self._trail_active)

    def _start_session_drift(self, session):
        """Kick the drift check for ``session`` (active or background). Only
        the latest drift request of a session is accepted when it lands."""
        if session.doc is None:
            return
        session.drift = None
        session.drift_gen = self._bump_trail_gen()
        self._trail_drift_worker(session.drift_gen, session.handle)
        self._start_session_xdep(session)

    def _start_session_xdep(self, session):
        """Probe ``session``'s cross-repo refs off the UI thread (t1957_1).

        Started with every drift check, so it shares drift's triggers:
        activation, view entry, reload / `d`, sync and background content
        changes — never `r` or a tab switch, which stay zero-subprocess.

        Callers must START BEFORE THEY RENDER: the render reads
        ``xdep_inflight`` to tell a ref being checked from one nobody probed.
        Cached results stay shown while the new probe runs."""
        if session.doc is None or session.error:
            return
        refs = trail_xdep_refs(session.doc, self._live_tasks_by_id(),
                               self._get_local_project())
        session.xdep_gen = self._bump_trail_gen()
        session.xdep_inflight = frozenset(refs)
        if refs:
            self._trail_xdep_worker(session.xdep_gen, session.handle, refs)

    # Own group (see `_trail_link_worker`): a cancel before start would leave
    # `xdep_inflight` claiming its refs are being checked.
    @work(thread=True, group="trail_xdep")
    def _trail_xdep_worker(self, gen: int, handle: str, refs: dict):
        result = {}
        try:
            for key, (repo, task_id) in refs.items():
                result[key] = probe_xdep_status(repo, task_id)
        finally:
            # Even a failed run lands, so its coverage is released; refs it
            # never reached stay absent from the result ("not checked").
            self.app.call_from_thread(self._on_trail_xdep, gen, handle, result)

    def _on_trail_xdep(self, gen: int, handle: str, result: dict):
        # Same supersession guard as drift: a stale stamp, a closed trail or
        # a different view discards the result.
        session = self._trail_session(handle)
        if (session is None or gen != session.xdep_gen
                or self.base_filter != "bytrail"):
            return
        # Replace, not merge: the result holds exactly the refs this probe
        # covered, so no ref it did not probe can turn into a failure.
        session.xdep = dict(result)
        session.xdep_inflight = frozenset()
        if session is not self._trail_active:
            session.updated = True
            self._refresh_trail_tabs()
            return
        focused = self._focused_card()
        self._rerender_trail(focused.task_data.filename if focused else "")

    # Own group (see `_trail_link_worker`): a cancel before start would leave
    # the subtitle at "checking freshness…".
    @work(thread=True, group="trail_drift")
    def _trail_drift_worker(self, gen: int, handle: str):
        verdict, reasons = run_trail_drift(handle)
        self.app.call_from_thread(
            self._on_trail_drift, gen, handle, verdict, reasons)

    def _on_trail_drift(self, gen: int, handle: str, verdict: str,
                        reasons: list):
        # Supersession guard: a slow drift check must not clobber a newer
        # check, newer content or a different view (stale stamp → discard).
        # Keyed by handle: a closed trail has no session and is discarded too.
        session = self._trail_session(handle)
        if (session is None or gen != session.drift_gen
                or self.base_filter != "bytrail"):
            return
        session.drift = (verdict, reasons)
        if session is not self._trail_active:
            # A background tab: nothing on screen shows it but its tab.
            session.updated = True
            self._refresh_trail_tabs()
            return
        # Re-render so the per-card drift markers appear. _rerender_trail, NOT
        # refresh_board: this is an async callback, and refresh_board would put
        # up to 15s of git/lock subprocesses on the UI thread (t1268).
        focused = self._focused_card()
        self._rerender_trail(focused.task_data.filename if focused else "")
        self._refresh_subtitle()

    def _reload_active_trail(self):
        """Re-fetch the active trail's stored blob, then re-run drift.

        Read-only (artifact get/versions): the board never writes a trail."""
        if self.base_filter != "bytrail" or self._trail_active is None:
            return
        self._reload_trail_session(self._trail_active)

    def _reload_trail_session(self, session):
        """Re-fetch ``session``'s stored blob (active or background tab)."""
        if (self.base_filter != "bytrail"
                or self._trail_session(session.handle) is not session):
            return
        # As before, a reload also retires an in-flight verdict.
        gen = self._bump_trail_gen()
        session.reload_gen = gen
        session.drift_gen = gen
        session.drift = None
        if session is self._trail_active:
            self._refresh_subtitle()      # back to "⟳ checking freshness…"
        else:
            self._refresh_trail_tabs()
        self._trail_reload_worker(gen, session.handle)

    # Own group (see `_trail_link_worker`): a cancel before start would drop
    # the reload and the drift check it restarts.
    @work(thread=True, group="trail_reload")
    def _trail_reload_worker(self, gen: int, handle: str):
        # Fetch-ordered read: `read_seq` tells this result apart from a scan's
        # read of the same trail, whichever lands first (t1895).
        (doc, error, versions), read_seq = sequenced_trail_read(
            handle, load_trail_blob)
        self.app.call_from_thread(self._on_trail_reload, gen, handle,
                                  doc, error, versions, read_seq)

    def _on_trail_reload(self, gen: int, handle: str, doc, error: str,
                         versions: list, read_seq: int = 0):
        session = self._trail_session(handle)
        if (session is None or gen != session.reload_gen
                or self.base_filter != "bytrail"):
            return
        # The newest content known for the handle — normally this result, but
        # a scan that sampled the artifact later and landed first wins.
        best = self._newest_trail_content(
            handle, (doc, error, list(versions), read_seq))
        self._apply_trail_content(session, best, restart_drift=True)
        # The cache follows, in place: a later `s` can neither resurrect the
        # superseded document nor serve one older than this tab's.
        self._store_trail_info_content(handle, best)

    # --- Artifact-version watch (t1268) -----------------------------------
    # An agent refresh launched into a tmux window finishes long after its
    # dialog closes, so the board polls the stored artifact's version listing
    # until it moves, then reloads. Bounded and self-stopping.

    def _stop_trail_watch(self):
        """Tear down the watch and retire any in-flight worker."""
        self._trail_watch_gen += 1        # invalidate in-flight callbacks
        if self._trail_watch_timer is not None:
            self._trail_watch_timer.stop()
        self._trail_watch_timer = None
        self._trail_watch_handle = ""
        self._trail_watch_baseline = None
        self._trail_watch_ticks = 0
        self._trail_watch_busy = False

    def _install_trail_watch(self, handle: str, baseline):
        """Install (or replace) the watch for ``handle``, keyed to ``baseline``.

        Called ONLY after a launch actually succeeded — never from the cancel
        or tmux-failure paths, which must leave an earlier watch running."""
        if not baseline:
            # Unreadable reference point (_trail_versions returns [] on every
            # failure). Returning BEFORE _stop_trail_watch is deliberate:
            # tearing down first would destroy a still-valid watch from an
            # earlier in-flight refresh and put nothing in its place. Better
            # to keep watching the older baseline than to watch nothing.
            return
        self._stop_trail_watch()          # bumps the token, kills old timer
        self._trail_watch_gen += 1        # this watch's own token
        self._trail_watch_handle = handle
        self._trail_watch_baseline = list(baseline)
        self._trail_watch_ticks = 0
        self._trail_watch_busy = False
        self._trail_watch_timer = self.set_interval(
            TRAIL_WATCH_INTERVAL, self._trail_watch_tick, name="trail_watch")

    def _trail_watch_tick(self):
        handle = self._trail_watch_handle
        # The watch belongs to its trail, not to the active tab: it survives a
        # tab switch and stops when the trail's session is gone.
        if (self.base_filter != "bytrail" or not handle
                or self._trail_session(handle) is None):
            self._stop_trail_watch()
            return
        self._trail_watch_ticks += 1
        if self._trail_watch_ticks > TRAIL_WATCH_MAX_TICKS:
            self._stop_trail_watch()
            return
        if self._trail_watch_busy:        # a slow poll is still in flight
            return
        self._trail_watch_busy = True
        self._trail_watch_worker(self._trail_watch_gen, handle)

    # Own group (see `_trail_link_worker`): a cancel before start would leave
    # `_trail_watch_busy` set, and every tick would skip until the ceiling.
    @work(thread=True, group="trail_watch")
    def _trail_watch_worker(self, watch_gen: int, handle: str):
        versions = _trail_versions(handle)
        self.app.call_from_thread(self._on_trail_watch, watch_gen, handle,
                                  versions)

    def _on_trail_watch(self, watch_gen: int, handle: str, versions: list):
        # Token check FIRST: a callback that outlived its watch must not clear
        # the newer watch's busy flag nor be compared against its baseline.
        if watch_gen != self._trail_watch_gen:
            return
        self._trail_watch_busy = False
        session = self._trail_session(handle)
        if (self.base_filter != "bytrail" or session is None
                or handle != self._trail_watch_handle):
            self._stop_trail_watch()
            return
        # _trail_versions() returns [] for EVERY failure (non-zero exit,
        # timeout, missing script) — indistinguishable from a real listing.
        # Treat it as "no signal, poll again", never as a version change.
        if not versions:
            return
        if versions == self._trail_watch_baseline:
            return
        self._stop_trail_watch()
        self.notify("Trail artifact updated — reloading")
        if session is self._trail_active:
            self._reload_active_trail()
        else:
            self._reload_trail_session(session)

    def action_trail_task(self):
        """`T`: launch /aitask-trail for the host's chosen target.

        Which task `T` acts on is host policy (t1794, C10): the board resolves
        the focused card — its By-Topic lane root in that view — and refuses in
        the In-Flight and By-Trail views; another host picks its own rule. The
        launch itself is shared."""
        target = self._trail_task_target()
        if target is None:
            return
        self._launch_trail([target], target)

    def _launch_trail(self, op_args: list, window_suffix: str,
                      watch_handle: str = "", debounce_key: str = ""):
        """Resolve and launch /aitask-trail (create or refresh).

        Mirrors _launch_work_report. The launched skill owns every artifact
        write (after its own confirmation); the board only builds the launch.
        Args are whitespace-free ids/handles (the codeagent guard refuses
        otherwise).

        ``watch_handle`` (t1268) requests an artifact-version watch for that
        trail — installed only if a launch is actually confirmed.

        ``debounce_key`` (t1279) is the key that opened this dialog, when that
        key is one the dialog itself binds; an immediate repeat of it is then
        swallowed while the dialog is new."""
        full_cmd = resolve_dry_run_command(Path("."), "trail", *op_args)
        if not full_cmd:
            self.notify("Could not resolve agent command — launching directly")
            direct_cmd = shlex.join(
                [str(CODEAGENT_SCRIPT), "invoke", "trail", *op_args])
            # This fallback still launches a real agent, so it carries the
            # same baseline→launch→watch contract as the dialog path — an
            # early return here would silently opt the fallback out of the
            # post-refresh pickup (t1268).
            self._with_trail_baseline(
                watch_handle,
                lambda baseline: self._finish_trail_launch(
                    baseline, watch_handle,
                    lambda: self.run_dialog_command(direct_cmd)))
            return
        prompt_str = "/aitask-trail " + " ".join(op_args)
        agent_string = resolve_agent_string(Path("."), "trail")
        suffix = re.sub(r"[^0-9A-Za-z_.-]+", "-",
                        str(window_suffix)).strip("-") or "trail"
        screen = AgentCommandScreen(
            "Implementation Trail", full_cmd, prompt_str,
            default_window_name=f"agent-trail-{suffix}",
            project_root=Path("."),
            operation="trail",
            operation_args=list(op_args),
            default_agent_string=agent_string,
            skill_name="trail",
            debounce_key=debounce_key,
        )

        def on_trail_result(result):
            if result == "run":
                self._with_trail_baseline(
                    watch_handle,
                    lambda baseline: self._finish_trail_launch(
                        baseline, watch_handle,
                        lambda: self.run_dialog_command(screen.full_command)))
                return

            if isinstance(result, TmuxLaunchConfig):
                def launch_tmux():
                    _pid, err = launch_in_tmux(screen.full_command, result)
                    if err:
                        # launch_in_tmux returns (pane_pid, error): a non-None
                        # error means the agent NEVER started.
                        self.notify(err, severity="error")
                        return False
                    if result.new_window:
                        maybe_spawn_minimonitor(result.session, result.window)
                    return True

                self._with_trail_baseline(
                    watch_handle,
                    lambda baseline: self._finish_trail_launch(
                        baseline, watch_handle, launch_tmux))
                return

            # Cancelled / dismissed: nothing launched, and THIS dialog armed
            # nothing. A watch from an earlier still-running agent MUST
            # survive — stopping it here would strand that agent's eventual
            # write. Skip the re-fetch too: a cancel changes nothing.
            self._after_trail_launch(reload=False)
        self.push_screen(screen, on_trail_result)

    def _with_trail_baseline(self, watch_handle: str, then):
        """Read the artifact version baseline, then call ``then(baseline)``.

        Off the UI thread when a watch is wanted: _trail_versions() shells out
        with a 15s timeout, and this runs from a screen-result callback on the
        UI thread — reading it inline could freeze the TUI for that long. The
        launch itself is performed from ``then``, so the strict
        baseline-before-launch ordering is preserved (t1268)."""
        if not watch_handle:
            then(None)          # no watch wanted → stay fully synchronous
            return
        self._trail_launch_pending = True
        # The flag changes check_action's answer for trail_refresh_agent, and
        # the mounted Footer only recomposes on the bindings_updated signal —
        # without this the key stays rendered while it is a no-op (t1268).
        self.refresh_bindings()
        self._trail_baseline_worker(watch_handle, then)

    # Own group (see `_trail_link_worker`): a cancel before start would never
    # launch the confirmed agent and leave `_trail_launch_pending` set.
    @work(thread=True, group="trail_launch")
    def _trail_baseline_worker(self, handle: str, then):
        versions = _trail_versions(handle)
        self.app.call_from_thread(then, versions)

    def _finish_trail_launch(self, baseline, watch_handle: str, launch):
        """Perform ``launch()``, then install the watch only if it succeeded.

        ``launch`` returns False when the agent never started; anything else
        (including a Worker handle) counts as launched."""
        # The pending window closes the moment the baseline lands, whatever
        # the launch outcome — clear it first so a failed launch can be retried.
        # Paired refresh_bindings() so the footer re-advertises the key.
        self._trail_launch_pending = False
        self.refresh_bindings()
        if launch() is False:
            # Install nothing, leave an earlier watch untouched, and skip the
            # re-fetch — nothing can have changed.
            self._after_trail_launch(reload=False)
            return
        if watch_handle:
            self._install_trail_watch(watch_handle, baseline)
        self._after_trail_launch(handle=watch_handle)

    def _after_trail_launch(self, reload: bool = True, handle: str = ""):
        """Post-dialog refresh. The immediate reload picks up the synchronous
        in-dialog `run` case; an installed watch covers the async tmux case.

        ``handle`` names the trail the launch was for: the user may have
        switched tabs while the baseline read ran, so that trail — not the
        active one — is reloaded, and nothing when its tab was closed."""
        if self.base_filter == "bytrail" and self.active_trail_handle:
            if reload and handle:
                session = self._trail_session(handle)
                if session is self._trail_active:
                    self._reload_active_trail()
                elif session is not None:
                    self._reload_trail_session(session)
            elif reload:
                self._reload_active_trail()
            else:
                self._rerender_trail()
        else:
            self.refresh_board()

    @work(exclusive=True)
    async def run_dialog_command(
        self,
        full_command: str,
        refocus_filename: str = "",
        error_notice: str | None = CODEAGENT_FAILURE_NOTICE,
    ):
        """Dispatch an agent-command dialog's stored ``full_command`` verbatim.

        Every AgentCommandScreen "run" (run-in-terminal) branch routes here:
        ``run_terminal`` stores user edits into ``screen.full_command`` and the
        agent/profile controls regenerate it, so rebuilding default wrapper
        args at the call site would silently discard them (t1225). The
        ``["sh", "-c", ...]`` dispatch mirrors the tui_switcher "run" path.

        ``refocus_filename`` is handed to the host's ``_after_dialog_command``
        hook, which owns the post-run refresh (the board reloads tasks and
        refreshes, keeping each branch's historical refocus; it is empty for the
        column-scoped work-report launch, which has no task file).
        ``error_notice`` is None for the non-agent TUI launches (create /
        brainstorm), whose non-zero exit is an ordinary cancel, not a failure.

        The suspended run is under the host's ``_suspend_sync_guard``
        (t1955): on the board it never overlaps a task-data sync. A refused
        run launches nothing and skips the refresh hook.
        """
        args = ["sh", "-c", full_command]
        terminal = find_terminal()
        if terminal:
            spawn_in_terminal(terminal, args)
        else:
            with self._suspend_sync_guard("launch") as allowed:
                if not allowed:
                    return
                with self.suspend():
                    ret = subprocess.call(args)
            if ret != 0 and error_notice:
                self.notify(error_notice, severity="error")
            self._after_dialog_command(refocus_filename)
