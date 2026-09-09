#!/usr/bin/env python3
"""`ait frozenagent` — the stand-in viewer for a frozen code agent (t1705_6).

When the freeze engine (t1705_4) freezes an agent it respawns the agent's own
pane into ``ait frozenagent --record <id>``. This app takes that slot: it renders
the agent's persisted terminal capture in place and offers the way back —
restore, re-pick, or drop. With no ``--record`` it opens a cross-project list of
every frozen record instead; that is the mode the TUI switcher launches.

Two rules from the t1705 parent plan's §B/§D are this module's own
responsibility, and both are load-bearing:

1. **It stamps ``@aitask_standin_ready=<record-id>`` on its OWN pane, after mount
   and only then** — the ``mark_monitor_pane`` rule. That stamp is the only
   positive evidence separating "stand-in up" from "agent still running", and
   reconcile's §C table branches on it, so stamping another pane is worse than
   not stamping at all. List mode stamps nothing: it is not a stand-in.
2. **It never mutates the store and never respawns anything itself.** Restore /
   re-pick / drop shell out to ``aitask_frozen.sh`` through
   ``tmux run-shell -b``, because the coordinator replaces *this very pane* and
   a child of it would be killed mid-transaction (measured, t1705_1).

**How an outcome is observed.** A ``run-shell -b`` job is detached: it returns
immediately, returns nothing, and its stdout never reaches us. So the store is
the channel — and two facts about it shape every poll below:

* the viewer never learns the coordinator's nonce, and ``restore-begin`` is what
  clears ``last_error``. Between dispatch and that call a record whose *previous*
  restore failed still carries the old attempt's ``<nonce>:<reason>``. Reading it
  then would report the new restore as failed before it began — so the poll gates
  on ``restore_attempts`` increasing, and only then matches ``last_error`` on the
  now-known nonce prefix;
* ``drop`` never passes through ``restoring`` or ``live`` — the record simply
  disappears — so it gets its own completion path rather than sharing the restore
  interpreter, which would wait forever for a state it can never see.
"""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS_DIR = _HERE.parent
for _p in (str(_SCRIPTS_DIR), str(_SCRIPTS_DIR / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from rich.cells import cell_len  # noqa: E402
from rich.markup import escape as markup_escape  # noqa: E402
from rich.text import Text  # noqa: E402
from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Horizontal, VerticalScroll  # noqa: E402
from textual.screen import ModalScreen  # noqa: E402
from textual.strip import Strip  # noqa: E402
from textual.widgets import (  # noqa: E402
    Button,
    DataTable,
    Footer,
    Input,
    Markdown,
    Static,
)

import agent_sessions  # noqa: E402
from agent_launch_utils import compact_root  # noqa: E402
from frozenagent.capture_log import CaptureLog  # noqa: E402
from monitor.ansi_utils import strip_ansi  # noqa: E402
from monitor.monitor_core import STANDIN_READY_OPTION, TaskInfoCache  # noqa: E402
from shortcuts_mixin import ShortcutsMixin  # noqa: E402
from tui_clipboard import copy_to_system_clipboard  # noqa: E402
from tmux_exec import TmuxClient  # noqa: E402
from tui_switcher import TuiSwitcherMixin  # noqa: E402

#: The gateway client. Module-level and read through this name at call time so a
#: test can swap it in place (`tests/test_no_raw_tmux.sh` enforces the seam).
_TMUX = TmuxClient()

#: The coordinator this app shells out to. Never imported — it must run detached.
FROZEN_SH = _SCRIPTS_DIR / "aitask_frozen.sh"

#: How long to wait for a dispatched coordinator to reach `restore-begin` before
#: concluding the `run-shell` job never ran (missing binary, unresolvable `ait`).
DISPATCH_GRACE = 10.0

#: How long to wait for a dispatched `drop` to remove the record.
DROP_GRACE = 10.0

#: Poll cadence for both outcome paths.
POLL_INTERVAL = 1.0

#: How long a viewer that mounted on a TRANSITIONAL record keeps refreshing its
#: header while somebody else's settlement completes.
SETTLE_GRACE = 30.0


class ConfirmDialog(ModalScreen[bool]):
    """Yes/no confirmation. Shaped after `monitor_shared.KillConfirmDialog`.

    Deliberately a local copy of that *shape* rather than an import: pulling in
    `monitor_shared` would drag the whole monitor runtime into a stand-in whose
    job is to start fast in a respawned pane.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("y", "confirm", "Yes", show=False),
        Binding("n", "cancel", "No", show=False),
    ]

    DEFAULT_CSS = """
    ConfirmDialog { align: center middle; }
    ConfirmDialog #fa-confirm {
        width: 60%; max-width: 70; height: auto;
        background: $surface; border: thick $error; padding: 1 2;
    }
    ConfirmDialog #fa-confirm-buttons { height: auto; padding: 1 0 0 0; align-horizontal: right; }
    ConfirmDialog #fa-confirm-buttons Button { margin: 0 1; }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="fa-confirm"):
            yield Static(markup_escape(self._message), id="fa-confirm-text")
            with Horizontal(id="fa-confirm-buttons"):
                yield Button("Cancel", id="fa-confirm-no")
                yield Button("Remove", variant="error", id="fa-confirm-yes")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "fa-confirm-yes")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class MarkdownScreen(ModalScreen[None]):
    """Render the whole capture, or the selected range, as Markdown."""

    BINDINGS = [Binding("escape", "close", "Close", show=False)]

    DEFAULT_CSS = """
    MarkdownScreen { align: center middle; }
    MarkdownScreen #fa-md-wrap {
        width: 90%; height: 90%;
        background: $surface; border: thick $accent; padding: 0 1;
    }
    """

    def __init__(self, text: str, title: str) -> None:
        super().__init__()
        self._text = text
        self._title = title

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="fa-md-wrap"):
            yield Static(markup_escape(self._title), id="fa-md-title")
            yield Markdown(self._text, id="fa-md")

    def action_close(self) -> None:
        self.dismiss(None)


class FrozenAgentApp(TuiSwitcherMixin, ShortcutsMixin, App):
    """Viewer for one frozen record, or a list of all of them."""

    _shortcuts_scope = "frozenagent"
    TITLE = "ait frozenagent"

    CSS = """
    #fa-header { background: $boost; padding: 0 1; height: auto; }
    #fa-search { height: 1; display: none; }
    #fa-search.visible { display: block; }
    #fa-log { background: $background; height: 1fr; }
    #fa-log.hidden { display: none; }
    #fa-list { height: 1fr; }
    #fa-list.hidden { display: none; }
    """

    BINDINGS = [
        *TuiSwitcherMixin.SWITCHER_BINDINGS,
        *ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS,
        Binding("q", "quit", "Quit"),
        Binding("r", "toggle_plain", "Plain/ANSI"),
        Binding("m", "markdown", "Markdown"),
        Binding("slash", "search", "Search"),
        Binding("n", "search_next", "Next", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("shift+up", "select_up", "", show=False),
        Binding("shift+down", "select_down", "", show=False),
        Binding("y", "copy", "Copy"),
        Binding("g", "scroll_top", "", show=False),
        Binding("G", "scroll_bottom", "", show=False),
        Binding("R", "restore", "Restore"),
        Binding("p", "repick", "Re-pick"),
        Binding("k", "drop", "Drop"),
        Binding("enter", "open", "Open", show=False),
    ]

    def __init__(self, record_id: str | None = None) -> None:
        super().__init__()
        self.current_tui_name = "frozenagent"
        #: None => list mode. A stand-in always has a record id.
        self._record_id = record_id
        self._list_mode = record_id is None
        self._view = agent_sessions.SessionsView()

        # Capture content. `_lines` is the ANSI-stripped mirror used for search,
        # keyboard selection and markdown; the log renders `_ansi` (or `_lines`
        # in plain mode).
        self._ansi = ""
        self._lines: list[str] = []
        self._capture_missing = False
        self._ansi_unavailable = False
        self._plain_mode = False

        # Search state.
        self._search_term = ""
        self._match_line: int | None = None

        # Incremental mark painting. `_pristine` holds the ORIGINAL rendered
        # strip for every line we overwrote, so a mark can be lifted without
        # re-rendering the capture; `_marked` is what is currently painted, and
        # `_marks_dirty` forces one repaint after a full re-render has reset the
        # strips underneath us.
        self._pristine: dict[int, Strip] = {}
        self._marked: set[int] = set()
        self._marked_key: tuple = (frozenset(), None)
        self._marks_dirty = False

        # Keyboard range selection, over `_lines` indices (`code_viewer.py`
        # model: a range stays visible but goes inactive once the cursor moves,
        # so the next shift+arrow starts fresh).
        self._cursor = 0
        self._sel_start: int | None = None
        self._sel_end: int | None = None
        self._sel_active = False

        # In-flight coordinator operations, keyed by RECORD id — not globally,
        # so list mode can legitimately have several running at once (which is
        # exactly what `restore --all` does). Cleared on every terminal outcome.
        self._pending: dict[str, str] = {}
        # NOT `_timers`: `MessagePump._timers` is a set Textual owns, and
        # shadowing it makes every `set_interval` raise.
        self._op_timers: dict[str, object] = {}
        self._header_note = ""
        self._rows: list[agent_sessions.SessionRecord] = []

    # ── composition ────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Static("", id="fa-header")
        yield Input(placeholder="Search (Enter to confirm, Esc to cancel)",
                    id="fa-search")
        yield CaptureLog(highlight=False, markup=False, wrap=False, id="fa-log")
        yield DataTable(id="fa-list")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#fa-log", CaptureLog)
        table = self.query_one("#fa-list", DataTable)
        if self._list_mode:
            log.add_class("hidden")
            table.cursor_type = "row"
            table.add_columns("project", "window", "task", "agent", "frozen", "lines")
            self._reload_list()
            table.focus()
            self._refresh_header()
            return

        table.add_class("hidden")
        # Focus the log FIRST and on EVERY path, including the missing-capture
        # early return below. Textual otherwise focuses the first focusable
        # widget — the hidden search Input — which then swallows every letter,
        # so q/r/m//,n silently type into an invisible field (t1486, the trap
        # `logview_app.py:88-99` documents).
        log.focus()
        self._load_capture()
        self._render_log()
        self._refresh_header()
        log.scroll_end(animate=False)
        # A fresh selection must start where the viewport actually is (G1).
        self._cursor = max(0, len(self._lines) - 1)
        self._stamp_ready()
        self._watch_until_settled()

    def on_unmount(self) -> None:
        # A live timer at `App.run_test` exit fails the ENCLOSING test
        # (aidocs/framework/testing_conventions.md).
        for timer in list(self._op_timers.values()):
            try:
                timer.stop()          # type: ignore[attr-defined]
            except Exception:
                pass
        self._op_timers.clear()

    # ── the self-stamp ─────────────────────────────────────────────────────

    def _stamp_ready(self) -> None:
        """Mark THIS pane as a mounted stand-in — ours, and only ours.

        ``$TMUX_PANE`` is the pane this process was launched into, so it is the
        one identity that cannot name somebody else's pane. Resolving the pane
        from the record instead would stamp whatever pane the record *names*,
        which after a tmux restart or a pane-id recycle belongs to someone else.

        Outside tmux there is nothing to stamp; reconcile reads a missing stamp
        as "not up", which is the fail-closed direction.
        """
        if self._list_mode or not self._record_id:
            return
        pane = os.environ.get("TMUX_PANE", "")
        if not pane:
            return
        rc, _ = _TMUX.run(["set-option", "-p", "-t", pane,
                           STANDIN_READY_OPTION, self._record_id])
        if rc != 0:
            self.log.warning(f"could not stamp {STANDIN_READY_OPTION} on {pane}")

    def _watch_until_settled(self) -> None:
        """Refresh the header until a TRANSITIONAL record settles.

        A replacement stand-in is respawned by `agent_restore._rollback`
        **before** it calls `standin-respawned`, so this viewer routinely mounts
        while the record is still `aborting`. It dispatched no operation of its
        own, so nothing else would ever poll — and the header would sit on
        `aborting` forever, never showing the failure that is about to be
        persisted a few milliseconds later.

        Bounded: this is a courtesy refresh for a settlement already in flight,
        not a supervisor. If it does not settle, reconcile owns it and the header
        keeps saying so.
        """
        rec = self._record()
        if rec is None or rec.state in (agent_sessions.STATE_LIVE,
                                        agent_sessions.STATE_FROZEN):
            return
        elapsed = {"t": 0.0}
        key = f"__settle__{self._record_id}"

        def tick() -> None:
            elapsed["t"] += POLL_INTERVAL
            self._view.invalidate()
            current = self._record()
            settled = current is None or current.state in (
                agent_sessions.STATE_LIVE, agent_sessions.STATE_FROZEN)
            if settled or elapsed["t"] >= SETTLE_GRACE:
                timer = self._op_timers.pop(key, None)
                if timer is not None:
                    try:
                        timer.stop()      # type: ignore[attr-defined]
                    except Exception:
                        pass
            self._refresh_header()

        self._op_timers[key] = self.set_interval(POLL_INTERVAL, tick)

    # ── capture loading / rendering ────────────────────────────────────────

    def _record(self) -> agent_sessions.SessionRecord | None:
        if not self._record_id:
            return None
        return self._view.by_id(self._record_id)

    def _load_capture(self) -> None:
        rec = self._record()
        if rec is None:
            self._capture_missing = True
            return
        ansi_path = Path(rec.capture_ansi) if rec.capture_ansi else None
        txt_path = Path(rec.capture_txt) if rec.capture_txt else None
        try:
            self._ansi = ansi_path.read_text(errors="replace") if ansi_path else ""
        except OSError:
            self._ansi = ""
        try:
            txt = txt_path.read_text(errors="replace") if txt_path else ""
        except OSError:
            txt = ""
        if not txt and self._ansi:
            # A record written before the `.txt` sibling existed, or a partial
            # freeze. Deriving it is better than an empty search index.
            txt = strip_ansi(self._ansi)
        self._lines = txt.splitlines()
        self._capture_missing = not self._ansi and not txt
        # THE TWO FILES CAN FAIL INDEPENDENTLY. When only the ANSI is gone the
        # capture is NOT missing — the text survives, and it is the whole point
        # of the viewer — but the default render path reads `_ansi` and would
        # paint a blank pane over perfectly good content. Fall back to the plain
        # rendering and say so, rather than showing nothing.
        self._ansi_unavailable = bool(self._lines) and not self._ansi
        if self._ansi_unavailable:
            self._plain_mode = True

    def _render_log(self) -> None:
        """Re-render the whole capture. EXPENSIVE — see `_repaint_marks`.

        Only three things justify it: first mount, the plain/ANSI toggle, and a
        reload. Never call it to move a mark.
        """
        log = self.query_one("#fa-log", CaptureLog)
        log.clear()
        # Every saved strip belonged to the previous render.
        self._pristine.clear()
        self._marked.clear()
        self._marked_key = (frozenset(), None)
        self._marks_dirty = True
        if self._capture_missing:
            log.write(Text("(capture file missing — the record can still be "
                           "restored, re-picked or dropped)", style="dim"))
            log.set_plain([])
            return
        if self._plain_mode:
            log.write(Text("\n".join(self._lines)))
        else:
            log.write(Text.from_ansi(self._ansi))
        log.set_plain(self._lines)
        self._repaint_marks()

    def _repaint_marks(self) -> None:
        """Re-apply the search highlight and the keyboard range, INCREMENTALLY.

        Both marks are ours, not Textual's: the native mouse selection is
        painted by `CaptureLog`, but a keyboard range and a search hit have no
        widget-level representation, so they are drawn by replacing the affected
        rendered strips.

        **Only the lines whose mark state CHANGED are touched, and the originals
        are kept so they can be restored.** The obvious implementation — re-run
        `_render_log()` and then re-mark — is what this method exists to avoid:
        it clears the log and re-parses the whole capture, which at the 50000-line
        capture cap takes seconds of blocked event loop for a single
        `shift+down`. That would have thrown away the exact property `CaptureLog`
        was chosen for (O(visible rows) rendering) on every keystroke.
        """
        if self._capture_missing:
            return
        log = self.query_one("#fa-log", CaptureLog)
        lo, hi = self._selection_bounds()
        marked: set[int] = (set(range(lo, hi + 1))
                            if lo is not None and hi is not None else set())
        if self._match_line is not None:
            marked.add(self._match_line)

        limit = min(len(log.lines), len(self._lines))
        marked = {idx for idx in marked if 0 <= idx < limit}
        # The match line is part of the key, not just of the set: it is styled
        # differently from a plain selected line, so a match moving from one
        # already-selected line to another leaves the set identical while the
        # painting must still change.
        key = (frozenset(marked), self._match_line)
        if key == self._marked_key and not self._marks_dirty:
            return

        # Restore the lines that are no longer marked…
        for idx in self._marked - marked:
            original = self._pristine.pop(idx, None)
            if original is not None and idx < len(log.lines):
                log.lines[idx] = original
        # …and paint the ones that are (or whose style changed).
        for idx in marked:
            if idx not in self._pristine:
                self._pristine[idx] = log.lines[idx]
            style = "bold reverse" if idx == self._match_line else "reverse"
            text = Text(self._lines[idx])
            # `stylize`, NOT `Text(..., style=…)`. A Text's base style is applied
            # by the Console at print time and is NOT baked into the segments
            # `render()` produces — so the constructor form yields
            # `Segment(text, None)` and the mark is invisible. `stylize` writes
            # the span, which is what survives into the Strip.
            text.stylize(style, 0, len(self._lines[idx]))
            # `cell_len`, not `len`: a Strip's second argument is its width in
            # terminal CELLS, and a captured agent session routinely contains
            # CJK, box-drawing or emoji, where one character is two cells. A
            # character count there desynchronises the strip from what is
            # actually painted, and the marks land on the wrong columns.
            log.lines[idx] = Strip(
                text.render(self.console), cell_len(self._lines[idx])
            )
        self._marked = marked
        self._marked_key = key
        self._marks_dirty = False
        log._line_cache.clear()
        log.refresh()

    # ── header ─────────────────────────────────────────────────────────────

    def _task_title(self, rec: agent_sessions.SessionRecord) -> str:
        if not rec.task_id:
            return ""
        try:
            info = TaskInfoCache(project_root=Path(rec.root)).get_task_info(
                rec.task_id
            )
        except Exception:
            return ""
        return info.title if info else ""

    def _header_text(self) -> str:
        if self._list_mode:
            return f"frozen records: {len(self._rows)}"
        rec = self._record()
        if rec is None:
            return f"record {markup_escape(self._record_id or '')} not found"
        title = self._task_title(rec)
        task = f"t{rec.task_id}" + (f" {title}" if title else "") if rec.task_id else "(no task)"
        state = self._header_note or self._persisted_note(rec) or rec.state
        if self._capture_missing:
            # The log body says so too, but the header is the line a user reads
            # first — and the actions stay available, so "missing" must not look
            # like "broken".
            state = f"{state} · capture missing"
        elif self._ansi_unavailable:
            state = f"{state} · colour data missing"
        parts = [
            compact_root(Path(rec.root)),
            rec.window,
            task,
            rec.agent_string or "(agent unknown)",
            f"frozen {rec.frozen_at}" if rec.frozen_at else rec.state,
            f"{len(self._lines)} lines",
            state,
        ]
        # EVERY interpolated field is escaped: a window name or a task title
        # containing `[x]` is read by Textual as an unknown tag and silently
        # vanishes — the defect class t1486 pinned.
        line = " · ".join(markup_escape(str(p)) for p in parts)
        if self._ansi_unavailable:
            line += "  \\[colour unavailable — showing plain text]"
        elif self._plain_mode:
            line += "  \\[plain]"
        return line

    @staticmethod
    def _persisted_note(rec: agent_sessions.SessionRecord) -> str:
        """A failure the STORE remembers, for a viewer that was not watching.

        The stand-in is respawned after a failed restore, so the viewer that
        dispatched it is gone by the time the outcome lands. Its replacement
        mounts on a `frozen` record carrying `last_error` — and without this the
        user would see a plain `frozen` header and no hint that their restore
        was even attempted, let alone why it failed.
        """
        if rec.state != agent_sessions.STATE_FROZEN or not rec.last_error:
            return ""
        err = rec.last_error
        reason = err.split(":", 1)[1] if ":" in err else err
        return f"last restore failed: {reason} — capture kept"

    def _refresh_header(self) -> None:
        self.query_one("#fa-header", Static).update(self._header_text())

    # ── list mode ──────────────────────────────────────────────────────────

    def _reload_list(self) -> None:
        table = self.query_one("#fa-list", DataTable)
        table.clear()
        self._view.invalidate()
        self._rows = self._view.frozen()
        for rec in self._rows:
            table.add_row(
                compact_root(Path(rec.root)),
                rec.window,
                f"t{rec.task_id}" if rec.task_id else "—",
                rec.agent_string or "—",
                rec.frozen_at or "—",
                str(rec.capture_lines),
                key=rec.id,
            )

    def _selected_record_id(self) -> str | None:
        """The record the next action applies to, in either mode."""
        if not self._list_mode:
            return self._record_id
        table = self.query_one("#fa-list", DataTable)
        if not self._rows or table.cursor_row is None:
            return None
        if table.cursor_row >= len(self._rows):
            return None
        return self._rows[table.cursor_row].id

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """`enter` on a row. DataTable owns that key, so the App binding never
        fires — the message is the only hook."""
        if event.data_table.id == "fa-list":
            self._open_selected(str(event.row_key.value or ""))

    def action_open(self) -> None:
        """List mode: open the highlighted record in the viewer, in-process."""
        self._open_selected(None)

    def _open_selected(self, rid: str | None) -> None:
        if not self._list_mode:
            return
        rid = rid or self._selected_record_id()
        if not rid:
            return
        self._record_id = rid
        self._list_mode = False
        self.query_one("#fa-list", DataTable).add_class("hidden")
        log = self.query_one("#fa-log", CaptureLog)
        log.remove_class("hidden")
        log.focus()
        self._load_capture()
        self._render_log()
        self._refresh_header()
        log.scroll_end(animate=False)
        self._cursor = max(0, len(self._lines) - 1)
        # A row can be listed while `frozen` and enter `restoring` / `aborting`
        # through ANOTHER coordinator before it is opened, so this entry path
        # needs the settle watch just as much as `on_mount` does.
        self._watch_until_settled()
        # NOT stamped: opening a record from the list does not make this pane
        # that record's stand-in. That asymmetry with `on_mount` is deliberate
        # and must survive any future refactor of this method.

    # ── plain / markdown ───────────────────────────────────────────────────

    def action_toggle_plain(self) -> None:
        if self._ansi_unavailable:
            # There is no ANSI rendering to go back to; toggling would blank
            # the pane.
            self.notify("The ANSI capture is unreadable — plain text only",
                        severity="warning")
            return
        self._plain_mode = not self._plain_mode
        self._render_log()
        self._refresh_header()

    def action_markdown(self) -> None:
        if self._list_mode or self._capture_missing:
            return
        lo, hi = self._selection_bounds()
        if lo is not None and hi is not None:
            body = "\n".join(self._lines[lo:hi + 1])
            title = f"lines {lo + 1}–{hi + 1}"
        else:
            body = "\n".join(self._lines)
            title = f"all {len(self._lines)} lines"
        self.push_screen(MarkdownScreen(body, title))

    # ── search ─────────────────────────────────────────────────────────────

    def action_search(self) -> None:
        if self._list_mode:
            return
        box = self.query_one("#fa-search", Input)
        box.add_class("visible")
        box.focus()

    def action_cancel(self) -> None:
        """Escape: close the search box if open, else clear the range."""
        box = self.query_one("#fa-search", Input)
        if box.has_class("visible"):
            box.remove_class("visible")
            box.value = ""
            self.query_one("#fa-log", CaptureLog).focus()
            return
        self._clear_selection()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "fa-search":
            return
        self._search_term = event.value
        event.input.remove_class("visible")
        self.query_one("#fa-log", CaptureLog).focus()
        if self._search_term:
            self._match_line = None
            self.action_search_next()

    def action_search_next(self) -> None:
        if self._list_mode or not self._search_term:
            return
        needle = self._search_term.lower()
        start = 0 if self._match_line is None else self._match_line + 1
        order = list(range(start, len(self._lines))) + list(range(0, start))
        wrapped_at = len(self._lines) - start
        for pos, idx in enumerate(order):
            if needle in self._lines[idx].lower():
                self._match_line = idx
                self._move_cursor(idx)    # a search hit IS a navigation
                self._repaint_marks()
                if pos >= wrapped_at:
                    self.notify("Search wrapped to top")
                return
        self.notify(f"Not found: {self._search_term}", severity="warning")

    # ── keyboard range selection + copy ────────────────────────────────────

    def _selection_bounds(self) -> tuple[int | None, int | None]:
        if self._sel_start is None or self._sel_end is None:
            return (None, None)
        return (min(self._sel_start, self._sel_end),
                max(self._sel_start, self._sel_end))

    def _clear_selection(self) -> None:
        self._sel_start = self._sel_end = None
        self._sel_active = False
        self._repaint_marks()

    def _extend_selection(self, direction: int) -> None:
        if self._list_mode or not self._lines:
            return
        if not self._sel_active:
            # Snap the cursor into the visible viewport first. `_move_cursor`
            # covers the navigations we own (g / G / a search hit), but ordinary
            # RichLog scrolling — pagedown, the mouse wheel, a scrollbar drag —
            # goes straight through the widget and never reaches us. Deriving
            # the start from the viewport covers EVERY scroll path instead of
            # enumerating keys, and matches what the user means: a fresh
            # selection begins where they are looking.
            self._cursor = self._cursor_in_view()
            self._sel_start = self._cursor
            self._sel_active = True
        self._cursor = max(0, min(self._cursor + direction, len(self._lines) - 1))
        self._sel_end = self._cursor
        self._repaint_marks()
        self.query_one("#fa-log", CaptureLog).scroll_to(y=self._cursor,
                                                        animate=False)

    def _cursor_in_view(self) -> int:
        """`_cursor`, clamped to the lines currently on screen."""
        if not self._lines:
            return 0
        log = self.query_one("#fa-log", CaptureLog)
        top = int(log.scroll_offset.y)
        bottom = top + max(1, log.scrollable_content_region.height) - 1
        bottom = min(bottom, len(self._lines) - 1)
        top = min(top, len(self._lines) - 1)
        return max(top, min(self._cursor, bottom))

    def action_select_up(self) -> None:
        self._extend_selection(-1)

    def action_select_down(self) -> None:
        self._extend_selection(1)

    def action_copy(self) -> None:
        """Copy the keyboard range, else the native mouse selection.

        The copy goes through `lib/tui_clipboard.copy_to_system_clipboard` and
        nothing else — `tests/test_tui_clipboard_seam.sh` fails any direct call
        of Textual's own clipboard method anywhere under `.aitask-scripts/`.
        (Textual's emits a bare OSC 52, which tmux forwards only from a pane in
        the client's visible window; the seam adds the `load-buffer -w`
        gateway forward that works from a background window too.)
        """
        if self._list_mode:
            return
        lo, hi = self._selection_bounds()
        if lo is not None and hi is not None:
            text = "\n".join(self._lines[lo:hi + 1])
        else:
            log = self.query_one("#fa-log", CaptureLog)
            selection = log.text_selection
            extracted = log.get_selection(selection) if selection else None
            text = extracted[0] if extracted else ""
        if not text:
            self.notify("Nothing selected", severity="warning")
            return
        copy_to_system_clipboard(self, text)
        self.notify(f"Copied {len(text.splitlines())} line(s)")

    def _move_cursor(self, line: int) -> None:
        """Move the navigation cursor, ending any active range.

        `_cursor` is the ONE position a fresh `shift+arrow` grows a selection
        from, so every navigation must move it. When it did not, `G` followed by
        `shift+down` left the viewport at the bottom while the range started at
        line 0 — and `y` copied the opening lines instead of the passage the
        user had navigated to. The range stays visible but goes inactive, which
        is `code_viewer`'s `move_cursor` semantics.
        """
        if not self._lines:
            return
        self._cursor = max(0, min(line, len(self._lines) - 1))
        self._sel_active = False
        self.query_one("#fa-log", CaptureLog).scroll_to(
            y=self._cursor, animate=False
        )

    def action_scroll_top(self) -> None:
        if self._list_mode:
            return
        self._move_cursor(0)
        self.query_one("#fa-log", CaptureLog).scroll_home(animate=False)

    def action_scroll_bottom(self) -> None:
        if self._list_mode:
            return
        self._move_cursor(len(self._lines) - 1)
        self.query_one("#fa-log", CaptureLog).scroll_end(animate=False)

    # ── coordinator actions ────────────────────────────────────────────────

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Grey out a destructive key while that record has an op in flight.

        Silently swallowing the press would be worse than refusing it: the user
        would see nothing happen and press again. The guard is per RECORD, so an
        action on a *different* row in list mode stays available.
        """
        if action in ("restore", "repick", "drop"):
            rid = self._selected_record_id()
            if rid is not None and rid in self._pending:
                return False
        return True

    def _run_frozen(self, argv: list[str]) -> None:
        """Dispatch a detached coordinator through the tmux server.

        Never `subprocess`: the coordinator respawns or kills the very pane this
        app runs in, so a child of this process would be killed mid-transaction,
        leaving a `restoring` record for reconcile and a dead pane for the user.
        """
        _TMUX.run(["run-shell", "-b",
                   shlex.join([str(FROZEN_SH), *argv])])

    def _refuse_if_pending(self, rid: str, what: str) -> bool:
        if rid in self._pending:
            self.notify(f"{self._pending[rid]} already in flight for this record",
                        severity="warning")
            return True
        return False

    def action_restore(self) -> None:
        self._start_restore(repick=False)

    def action_repick(self) -> None:
        self._start_restore(repick=True)

    def _start_restore(self, *, repick: bool) -> None:
        rid = self._selected_record_id()
        if rid is None:
            return
        if self._refuse_if_pending(rid, "restore"):
            return
        rec = self._view.by_id(rid)
        if rec is None:
            self.notify("Record is gone", severity="warning")
            return
        if repick and not rec.task_id:
            self.notify("This record has no task id — restore instead",
                        severity="warning")
            return

        # Snapshot BEFORE dispatch. `restore_attempts` is the only field
        # `restore-begin` bumps monotonically, so it — not `state`, and never
        # `last_error` — is what tells us the coordinator actually started.
        snapshot = (rec.restore_attempts, rec.op_nonce)
        self._pending[rid] = "re-pick" if repick else "restore"
        argv = ["restore", rid] + (["--repick"] if repick else [])
        self._run_frozen(argv)
        self._set_note(rid, "dispatching…")
        elapsed = {"t": 0.0}
        self._op_timers[rid] = self.set_interval(
            POLL_INTERVAL,
            lambda: self._poll_restore(rid, snapshot, elapsed),
        )

    def _poll_restore(self, rid: str, snapshot: tuple[int, str],
                      elapsed: dict) -> None:
        elapsed["t"] += POLL_INTERVAL
        self._view.invalidate()
        rec = self._view.by_id(rid)
        if rec is None:
            self._finish(rid, "record vanished", warn=True)
            return

        prev_attempts, _prev_nonce = snapshot
        if rec.restore_attempts <= prev_attempts:
            # PRE-BEGIN. `last_error` here belongs to an EARLIER attempt — the
            # store only clears it inside `restore-begin` — so reading it now
            # would report this restore as failed before it started.
            if elapsed["t"] >= DISPATCH_GRACE:
                self._finish(
                    rid,
                    "restore did not start — run 'ait frozenagent' or reconcile",
                    warn=True,
                )
            return

        if rec.state == agent_sessions.STATE_LIVE:
            if rec.ack == "liveness":
                # A SUCCESS, and the only outcome a codex record can reach
                # (amendment B4). Never styled as an error.
                self._finish(rid, "restored, unverified — capture kept")
            else:
                self._finish(rid, "restored")
            return

        if rec.state == agent_sessions.STATE_FROZEN:
            # Back at `frozen` after the attempt started: the restore failed and
            # its stand-in is back.
            #
            # DO NOT match `last_error` against a freshly read `op_nonce`.
            # Recovery (`restore-abort` -> `standin-respawned`) sets the state
            # back to `frozen` and CLEARS the lease while PRESERVING the error,
            # so by the time we see it `op_nonce` is "" and a prefix test can
            # never match — which silently turned a failed restore into a
            # timeout, reported as "restored elsewhere". The gate above is the
            # correlation: `restore-begin` cleared `last_error` at the start of
            # THIS attempt, so any non-empty value now belongs to it.
            err = rec.last_error or ""
            reason = err.split(":", 1)[1] if ":" in err else err
            if reason:
                self._finish(rid, f"restore failed: {reason} — capture kept",
                             warn=True)
            else:
                self._finish(rid, "restore ended — capture kept", warn=True)
            return

        if elapsed["t"] >= DISPATCH_GRACE + 30.0:
            # A timeout is NOT evidence of success. The record is still
            # transitional (`restoring` / `aborting`) and only reconcile can
            # settle it; say exactly that rather than implying it worked.
            self._finish(rid,
                         f"restore still {rec.state} after the grace — "
                         "run reconcile; capture kept", warn=True)

    def action_drop(self) -> None:
        rid = self._selected_record_id()
        if rid is None:
            return
        if self._refuse_if_pending(rid, "drop"):
            return

        def confirmed(yes: bool | None) -> None:
            if not yes:
                return
            self._pending[rid] = "drop"
            self._run_frozen(["drop", rid])
            self._set_note(rid, "dropping…")
            elapsed = {"t": 0.0}
            self._op_timers[rid] = self.set_interval(
                POLL_INTERVAL, lambda: self._poll_drop(rid, elapsed)
            )

        self.push_screen(
            ConfirmDialog("Remove the frozen record and its capture? "
                          "This cannot be undone."),
            confirmed,
        )

    def _poll_drop(self, rid: str, elapsed: dict) -> None:
        """`drop`'s OWN completion path.

        A dropped record never passes through `restoring` or `live` — it
        disappears — so the restore interpreter would wait for a state it can
        never observe and the header would sit on `dropping…` forever.
        """
        elapsed["t"] += POLL_INTERVAL
        self._view.invalidate()
        if self._view.by_id(rid) is None:
            self._finish(rid, "dropped — capture removed")
            if self._list_mode:
                self._reload_list()
            return
        if elapsed["t"] >= DROP_GRACE:
            # The coordinator's `DROP_FAILED:` / `DROP_REFUSED:` line goes to a
            # detached `run-shell` job whose stdout we cannot read, so the
            # record's continued existence is the observable.
            self._finish(rid, "drop failed — record kept", warn=True)

    def _set_note(self, rid: str, note: str) -> None:
        if rid == self._record_id and not self._list_mode:
            self._header_note = note
            self._refresh_header()

    def _finish(self, rid: str, note: str, *, warn: bool = False) -> None:
        timer = self._op_timers.pop(rid, None)
        if timer is not None:
            try:
                timer.stop()          # type: ignore[attr-defined]
            except Exception:
                pass
        self._pending.pop(rid, None)
        self._set_note(rid, note)
        self.notify(note, severity="warning" if warn else "information")
        self.refresh_bindings()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    record_id: str | None = None
    if argv:
        if argv[0] == "--record" and len(argv) == 2:
            record_id = argv[1]
        else:
            print("usage: ait frozenagent [--record <id>]", file=sys.stderr)
            return 2
    if record_id is not None:
        if not agent_sessions.valid_id(record_id):
            print(f"frozenagent: unknown record {record_id}", file=sys.stderr)
            return 2
        if agent_sessions.SessionsView().by_id(record_id) is None:
            print(f"frozenagent: unknown record {record_id}", file=sys.stderr)
            return 2
    FrozenAgentApp(record_id).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
