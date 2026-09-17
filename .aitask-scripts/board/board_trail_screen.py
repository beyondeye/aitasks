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
the host's ``_after_dialog_command(refocus_filename)`` hook owns the refresh.

**Patch targets.** The trail launch, drift, discovery and dialog-dispatch
names (``discover_trails``, ``_trail_versions``, ``load_trail_blob``,
``run_trail_drift``, ``resolve_dry_run_command``, ``AgentCommandScreen``,
``launch_in_tmux``, ``find_terminal`` …) are read from THIS module's namespace
by the methods below, so a test stub must target ``board_trail_screen``
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

import re
import shlex
import subprocess
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
    TmuxLaunchConfig, find_terminal, launch_in_tmux, maybe_spawn_minimonitor,
    resolve_agent_string, resolve_dry_run_command, spawn_in_terminal,
)
from board_trail_view import (
    TRAIL_WATCH_INTERVAL, TRAIL_WATCH_MAX_TICKS, TrailColumn,
    TrailDetailScreen, TrailSelectScreen, TrailSummaryScreen,
    build_trail_lanes, load_local_project_name, run_trail_drift,
    trail_drift_by_ref, trail_summary_text,
)
from board_widgets import LoadingOverlay
from keybinding_registry import resolve_key
from topic_semantics import task_own_id
from trail_discovery import (
    _trail_versions, compute_trail_overlaps, discover_trails, load_trail_blob,
)


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
    Binding("T", "trail_task", "Trail"),
    Binding("M", "trail_move_wave", "Move Wave"),
]
TRAIL_BINDING = {b.action: b for b in TRAIL_BINDINGS}

#: Optional host members each board-only trail action reaches, directly or
#: through the chain it starts (`_review_then` → `_choose_move_destination` →
#: `_apply_move_to_column`, which reads `marked` and `_column_title`).
TRAIL_ACTION_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "trail_move_wave": ("_review_then", "_choose_move_destination",
                        "_column_title", "marked", "_reject_stale",
                        "_apply_move_to_column"),
    "trail_sync": ("_run_sync",),
}


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

    def _init_trail_state(self) -> None:
        """Create the By-Trail session state. The host calls this from its
        ``__init__`` (the mixin has no ``__init__`` of its own)."""
        # --- By-Trail view state (session-only, never persisted; t1210_4) ---
        self.active_trail_handle: str | None = None
        self._trail_infos: list | None = None    # discovery cache
        self._trail_doc: dict | None = None      # active trail document
        self._trail_error: str = ""              # fail-closed load error
        self._trail_versions_fallback: list = []
        self._trail_drift: tuple | None = None   # (verdict, reasons) | None
        self._trail_owner_id: str = ""           # active trail's owner task
        self._trail_owner_archived = False       # §9.2 archived-owner banner
        # Supersession token: bumped on EVERY re-entry point (enter/leave the
        # view, trail selection, selection-modal reopen). Worker callbacks
        # discard results carrying a stale token.
        self._trail_gen = 0
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

    def _trail_banner(self, title: str, suffix: str, owner_note: str,
                      depth_note: str = "") -> str:
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
        if depth_note:
            full_with_depth = f'By-Trail: "{title}"{suffix}{owner_note}{depth_note}'
            if not budget or cell_len(full_with_depth) <= budget:
                return full_with_depth
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
                    title, suffix, owner_note, self._trail_depth_note())
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
        compose — so By-Trail consumes none of it. Routing this view through
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
        self.manager.load_tasks()          # pure file I/O
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
        """`s` in By-Trail: open the trail selector (rescans discovery)."""
        if self._modal_is_active():
            return
        self._open_trail_select(rescan=True)

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

    def _build_active_trail_lanes(self):
        """Project the active trail onto the live By-Topic task universe."""
        all_tasks = (list(self.manager.task_datas.values())
                     + list(self.manager.child_task_datas.values()))
        tasks_by_id = {}
        for task in all_tasks:
            own = task_own_id(task)
            if own:
                tasks_by_id.setdefault(own, task)
        drift_by_ref = trail_drift_by_ref(
            self._trail_drift[1] if self._trail_drift else [])
        return build_trail_lanes(
            self._trail_doc, tasks_by_id, self._get_local_project(),
            self.manager.find_task_including_archived, drift_by_ref)

    def _open_trail_select(self, rescan: bool = False):
        """Open the trail-selection modal, running discovery when needed."""
        if self._modal_is_active():
            return
        self._trail_gen += 1
        if rescan or self._trail_infos is None:
            # Persistent busy affordance for the archive scan + blob loads.
            overlay = LoadingOverlay("Scanning for trails…")
            self.push_screen(overlay)
            self._trail_discovery_worker(self._trail_gen, overlay)
        else:
            self._open_trail_select_from_cache()

    @work(thread=True)
    def _trail_discovery_worker(self, gen: int, overlay):
        """Discovery + blob loads off the UI thread (subprocess-heavy)."""
        infos, unreadable = discover_trails()
        self.app.call_from_thread(self._on_trail_discovery, gen, infos,
                                  unreadable, overlay)

    def _on_trail_discovery(self, gen: int, infos: list, unreadable: list,
                            overlay):
        # Pop OUR overlay first (even for superseded results — each scan owns
        # its own overlay instance, so a stale callback can never pop a newer
        # scan's overlay).
        if overlay is not None and self.screen is overlay:
            self.pop_screen()
        # Supersession guard: discard when the view moved on mid-scan.
        if gen != self._trail_gen or self.base_filter != "bytrail":
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
        self._trail_infos = infos
        self._open_trail_select_from_cache()

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
            self._activate_trail(handle)

        self.push_screen(
            TrailSelectScreen(infos, compute_trail_overlaps(infos)), on_select)

    def _activate_trail(self, handle: str):
        """Make ``handle`` the session's active trail and render it."""
        self._trail_gen += 1
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
        self.manager.load_tasks()
        # A watch belongs to the trail it was installed for (t1268).
        self._stop_trail_watch()
        self.active_trail_handle = handle
        info = next((i for i in (self._trail_infos or [])
                     if i.handle == handle), None)
        self._trail_doc = info.doc if info else None
        self._trail_error = info.load_error if info else ""
        self._trail_versions_fallback = list(info.versions) if info else []
        self._trail_owner_id = info.owner_id if info else ""
        self._trail_owner_archived = bool(info.owner_archived) if info else False
        self._trail_drift = None
        self.refresh_board()
        if self._trail_doc is not None and not self._trail_error:
            self._start_trail_drift()
        self._refresh_subtitle()
        self.refresh_bindings()

    def _start_trail_drift(self):
        """Kick the read-only drift check for the active trail (view entry /
        activation). Updates rendered badges only — never the artifact."""
        if not self.active_trail_handle or self._trail_doc is None:
            return
        self._trail_drift = None
        self._trail_drift_worker(self._trail_gen, self.active_trail_handle)

    @work(thread=True)
    def _trail_drift_worker(self, gen: int, handle: str):
        verdict, reasons = run_trail_drift(handle)
        self.app.call_from_thread(
            self._on_trail_drift, gen, handle, verdict, reasons)

    def _on_trail_drift(self, gen: int, handle: str, verdict: str,
                        reasons: list):
        # Supersession guard: a slow drift check must not clobber a newer
        # selection or a different view (stale token → discard).
        if (gen != self._trail_gen or self.base_filter != "bytrail"
                or handle != self.active_trail_handle):
            return
        self._trail_drift = (verdict, reasons)
        # Re-render so the per-card drift markers appear. _rerender_trail, NOT
        # refresh_board: this is an async callback, and refresh_board would put
        # up to 15s of git/lock subprocesses on the UI thread (t1268).
        focused = self._focused_card()
        self._rerender_trail(focused.task_data.filename if focused else "")
        self._refresh_subtitle()

    def _reload_active_trail(self):
        """Re-fetch the active trail's stored blob, then re-run drift.

        Read-only (artifact get/versions): the board never writes a trail."""
        if self.base_filter != "bytrail" or not self.active_trail_handle:
            return
        self._trail_gen += 1
        self._trail_drift = None
        self._refresh_subtitle()          # back to "⟳ checking freshness…"
        self._trail_reload_worker(self._trail_gen, self.active_trail_handle)

    @work(thread=True)
    def _trail_reload_worker(self, gen: int, handle: str):
        doc, error, versions = load_trail_blob(handle)
        self.app.call_from_thread(self._on_trail_reload, gen, handle,
                                  doc, error, versions)

    def _on_trail_reload(self, gen: int, handle: str, doc, error: str,
                         versions: list):
        if (gen != self._trail_gen or self.base_filter != "bytrail"
                or handle != self.active_trail_handle):
            return
        self._trail_doc = doc
        self._trail_error = error
        self._trail_versions_fallback = list(versions)
        # The discovery cache still holds the OLD doc for this handle; drop it
        # so a later `s` re-select cannot resurrect the superseded document.
        self._trail_infos = None
        self._rerender_trail()
        if doc is not None and not error:
            self._start_trail_drift()
        self._refresh_subtitle()

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
        if (self.base_filter != "bytrail" or not handle
                or handle != self.active_trail_handle):
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

    @work(thread=True)
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
        if (self.base_filter != "bytrail"
                or handle != self.active_trail_handle
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
        self._reload_active_trail()

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

    @work(thread=True)
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
        self._after_trail_launch()

    def _after_trail_launch(self, reload: bool = True):
        """Post-dialog refresh. The immediate reload picks up the synchronous
        in-dialog `run` case; an installed watch covers the async tmux case."""
        if self.base_filter == "bytrail" and self.active_trail_handle:
            if reload:
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
        """
        args = ["sh", "-c", full_command]
        terminal = find_terminal()
        if terminal:
            spawn_in_terminal(terminal, args)
        else:
            with self.suspend():
                ret = subprocess.call(args)
            if ret != 0 and error_notice:
                self.notify(error_notice, severity="error")
            self._after_dialog_command(refocus_filename)
