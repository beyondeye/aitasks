"""`ait trails` — the stand-alone By-Trail TUI (t1794_6).

Hosts ``TrailScreenMixin`` (board_trail_screen.py) over ``TaskManager``
(board_task_manager.py), the trail cards / lanes / modals (board_trail_view.py)
and the widget layer (board_widgets.py) **without importing ``aitask_board``**
or any Kanban render path. It is the read-only trail reader: select a trail,
walk its waves, open the entry detail and summary, refresh locally, re-check
drift, watch the artifact, and launch ``/aitask-trail`` for a live member. The
board's ``z`` view stays embedded and unchanged; the two hand off through the
TUI switcher (``j`` → ``i`` from the board, ``j`` → ``b`` back).

Shortcut ownership (parent plan C10): this App registers under scope
``"board"`` and declares the SAME ``TRAIL_BINDINGS`` objects the board does, so
a ``shortcuts.board.<trail action>`` override rebinds both surfaces at once.
``M`` (wave move) and ``S`` (task-data sync) are therefore *declared* here but
hidden and non-dispatching: ``check_action`` refuses them and none of the
``TRAIL_ACTION_CAPABILITIES`` members exist on this class, so the mixin's own
capability guard stops the action even from a remapped key.

The four arrow rows are board rows too — identical ``(action, key,
description)`` — because card focus is what every card-scoped key (``enter``,
``T``) is gated on, and the trail modals rely on the App's ``nav_up`` /
``nav_down`` to cycle their focus.

Contracts (board/__init__.py): C1 — bare-name sibling imports, never
``aitask_board``; C2 — no task directory resolved anywhere in this module
(``main()`` takes ``--tasks-dir`` from the launcher, which applies the
``TASK_DIR`` rule in shell); C7 — ``TRAIL_CSS`` and ``WIDGET_CSS`` are
interpolated, never copied.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
# Own directory too (C1): sibling board modules are imported by bare name.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rich.cells import cell_len
from textual.app import App
from textual.binding import Binding
from textual.containers import HorizontalScroll, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import DataTable, Header, Input, SelectionList, Static

from board_task_manager import TaskManager
from board_trail_screen import TRAIL_BINDINGS, TrailScreenMixin
from board_trail_view import TRAIL_CSS, TrailColumn, TrailTaskCard
from board_widgets import WIDGET_CSS, TaskCard
from multirow_footer import MultiRowFooter
from shortcuts_mixin import ShortcutsMixin
from topic_semantics import task_own_id
from tui_switcher import TuiSwitcherMixin, TuiSwitcherOverlay


class TrailsScreen(Screen):
    """Default screen with Textual's auto-focus off (the board's `BoardScreen`
    idiom, t1491) and a resume hook that re-anchors focus on a card.

    Auto-focus would hand the keyboard to the first focusable widget — a scroll
    container — before `on_mount` runs. And when a modal is dismissed Textual
    restores whatever the base screen had focused, which after the selector on
    boot is nothing, or a `TrailColumn` if the lanes were rebuilt underneath the
    dialog. Either way no card is focused, and every card-gated key is dead
    until the user clicks. The resume hook runs the same rescue `apply_filter`
    performs after a render, so focus lands on a card by itself.
    """

    AUTO_FOCUS = ""

    def on_screen_resume(self) -> None:
        self.app.call_after_refresh(self.app.apply_filter)


class TrailsApp(TuiSwitcherMixin, ShortcutsMixin, TrailScreenMixin, App):
    """The stand-alone trail reader. A `TrailHost` (see board_trail_screen.py)."""

    _shortcuts_scope = "board"
    # `?` must not execute the board just to list the Kanban rows this App
    # never dispatches (C1: nothing here loads aitask_board — pressing a key
    # included). The editor therefore lists the `board` rows THIS App declares
    # (the trail keys, navigation, quit) plus the shared scopes; a Kanban-only
    # row is edited from `ait board` or Settings → Shortcuts, and because the
    # trail Binding objects are shared, an edit made anywhere reaches both.
    _shortcuts_exclude_sources = ("aitask_board",)
    TITLE = "aitasks trails"

    CSS = WIDGET_CSS + """
    Screen { align: center middle; }
    #board_container { height: 1fr; }
    .trail-empty { padding: 1 2; color: $text-muted; }
    .trail-error { padding: 1 2; color: $error; }
    """ + TRAIL_CSS

    BINDINGS = [
        *TuiSwitcherMixin.SWITCHER_BINDINGS,
        *ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS,
        Binding("q", "quit", "Quit"),
        # Card navigation — the board's rows verbatim (same action, key and
        # description), so the `(board, nav_*)` registry defaults are unchanged.
        Binding("up", "nav_up", "Up", show=False, priority=True),
        Binding("down", "nav_down", "Down", show=False, priority=True),
        Binding("left", "nav_left", "Left", show=False, priority=True),
        Binding("right", "nav_right", "Right", show=False, priority=True),
        # The shared trail keys — the SAME objects the board declares (C10).
        *TRAIL_BINDINGS,
    ]

    def __init__(self, *, tasks_dir: Path, metadata_file: Path,
                 gates_registry_file: Path):
        super().__init__()
        self.current_tui_name = "trails"
        self._tasks_dir = Path(tasks_dir)
        # The mixin keys every branch on this; the stand-alone is By-Trail only.
        self.base_filter = "bytrail"
        # Read-only host: never creates the metadata directory nor first-ships
        # board_config.json (persist_on_init=False), and calls no manager writer.
        self.manager = TaskManager(
            tasks_dir=self._tasks_dir, metadata_file=Path(metadata_file),
            gates_registry_file=Path(gates_registry_file),
            on_warning=self.notify, persist_on_init=False)
        self._init_trail_state()

    # --- Composition -------------------------------------------------------

    def compose(self):
        header = Header()
        header.can_focus = False
        yield header
        container = HorizontalScroll(id="board_container")
        container.can_focus = False
        yield container
        # Summary pane: same shape and rules as the board's (t1505_1) — a
        # fixed-height FLOW child, never `dock: bottom`; hidden until
        # `_refresh_trail_summary` has text; markup off for free-form prose.
        summary = VerticalScroll(
            Static("", id="trail_summary_body", markup=False),
            id="trail_summary")
        summary.display = False
        summary.can_focus = False
        yield summary
        footer = MultiRowFooter(hint_action="open_shortcuts_editor")
        footer.can_focus = False
        yield footer

    def get_default_screen(self) -> Screen:
        return TrailsScreen()

    def on_mount(self):
        self.refresh_board()
        # Boot straight into the selection flow, as the board does on `z`.
        self.call_after_refresh(self._open_trail_select)

    def on_resize(self, event):
        # The banner is budgeted against the header width (t1278).
        self._refresh_subtitle()

    # --- TrailHost surface -------------------------------------------------

    @property
    def tasks_dir(self) -> Path:
        return self._tasks_dir

    def refresh_board(self, refocus_filename: str = "", *args, **kwargs):
        """Re-mount the lanes from the manager's in-memory state."""
        refocus_col_id = self._get_focused_col_id() or ""
        container = self.query_one("#board_container")
        container.remove_children()
        self._render_bytrail(container)
        self.call_after_refresh(self.apply_filter)
        self._queue_refocus(refocus_filename, refocus_col_id)

    #: Refresh hops a deferred refocus / rescue waits for the lanes' cards to
    #: be mounted before giving up (the board's `_SCROLL_LAYOUT_HOPS` idiom).
    _MOUNT_HOPS = 5

    def apply_filter(self, cols=None, hops: int = _MOUNT_HOPS) -> None:
        """No filters here — this is the card-focus rescue.

        Runs after every render and on every base-screen resume. The predicate
        is "no ATTACHED `TaskCard` is focused", NOT "nothing is focused": a
        `TrailColumn` is a focusable `VerticalScroll`, so Textual can leave one
        of them holding the keyboard after a modal closes; and a lane re-render
        (the drift callback's `_rerender_trail`) can leave `screen.focused`
        pointing at a card it just REMOVED — a detached widget whose binding
        chain no longer reaches the App, so every key is dead until something
        re-anchors focus. Never touches focus while a modal is up. Re-queues
        itself, bounded, while the re-mounted cards are not queryable yet.
        """
        if self._modal_is_active() or self._focused_card() is not None:
            return
        target = self._first_card()
        if target is not None:
            target.focus()
        elif hops > 0 and self.active_trail_handle:
            self.call_after_refresh(self.apply_filter, None, hops - 1)

    def _focused_card(self):
        """The focused card, or None — a card that has been removed from the
        DOM does not count, whatever `screen.focused` still says."""
        focused = self.screen.focused
        if isinstance(focused, TaskCard) and focused.is_attached:
            return focused
        return None

    def _modal_is_active(self) -> bool:
        return isinstance(self.screen, ModalScreen)

    def _get_focused_col_id(self):
        focused = self._focused_card()
        return focused.column_id if focused else None

    def _queue_refocus(self, refocus_filename: str = "",
                       refocus_col_id: str = "") -> None:
        if refocus_filename or refocus_col_id:
            self.call_after_refresh(self._refocus, refocus_filename,
                                    refocus_col_id)

    def _refocus(self, filename: str, col_id: str,
                 hops: int = _MOUNT_HOPS) -> None:
        cards = list(self.query(TaskCard))
        if not cards and hops > 0:
            # The re-render's mount has not landed yet (it is asynchronous);
            # come back after the next refresh rather than refocus nothing.
            self.call_after_refresh(self._refocus, filename, col_id, hops - 1)
            return
        for card in cards:
            if filename and card.task_data.filename == filename:
                card.focus()
                return
        if col_id:
            in_col = [c for c in cards if c.column_id == col_id]
            if in_col:
                in_col[0].focus()

    def _banner_budget(self) -> int:
        """Cells available to `sub_title` on the header row (0 = unknown);
        the board's rule, read off the live HeaderTitle."""
        try:
            usable = self.query_one("HeaderTitle").content_region.width
        except Exception:
            return 0
        return max(0, usable - cell_len(str(self.title)) - 3)

    def _after_dialog_command(self, refocus_filename: str = "") -> None:
        """`run_dialog_command` suspend-path hook: reload tasks and re-render."""
        self.manager.load_tasks()
        self.refresh_board(refocus_filename=refocus_filename)

    def _trail_task_target(self) -> str | None:
        """`T` policy (C10): the focused live local member's own id, else a
        visible refusal and no launch. Silent only under a modal."""
        if self._modal_is_active():
            return None
        focused = self._focused_card()
        target = ""
        if isinstance(focused, TrailTaskCard) and not focused.is_ghost:
            target = task_own_id(focused.task_data) or ""
        if not target:
            self.notify("T needs a live local task under focus",
                        severity="warning")
            return None
        return target

    def _refresh_subtitle(self):
        """No active trail → say so; the mixin's fallback prints the board's
        `Auto-refresh: …`, which this App has no timer for."""
        if self.active_trail_handle:
            super()._refresh_subtitle()
            return
        self._refresh_trail_summary()
        self.sub_title = "no trail selected — press s"

    # --- Widget hooks reached through `self.app` ---------------------------

    def toggle_column_collapse(self, col_id: str) -> None:
        """Wave lanes do not collapse; the header button is inert here."""

    def action_view_details(self):
        focused = self._focused_card()
        if focused is None:
            return
        self._open_trail_entry_detail(focused)

    # --- Card navigation ---------------------------------------------------

    def _columns(self) -> list:
        return list(self.query(TrailColumn))

    def _column_cards(self, col_id: str) -> list:
        return [c for c in self.query(TaskCard) if c.column_id == col_id]

    def _first_card(self):
        for col in self._columns():
            cards = self._column_cards(col.col_id)
            if cards:
                return cards[0]
        return None

    def _nav_vertical(self, step: int) -> None:
        if self._modal_is_active():
            if step < 0:
                self.screen.focus_previous()
            else:
                self.screen.focus_next()
            return
        focused = self._focused_card()
        if focused is None:
            self.apply_filter()
            return
        cards = self._column_cards(focused.column_id)
        idx = next((i for i, c in enumerate(cards) if c is focused), -1)
        if 0 <= idx + step < len(cards):
            cards[idx + step].focus()

    def _nav_lateral(self, direction: int) -> None:
        if self._modal_is_active():
            return
        focused = self._focused_card()
        if focused is None:
            self.apply_filter()
            return
        cols = [c.col_id for c in self._columns()]
        if focused.column_id not in cols:
            return
        old_cards = self._column_cards(focused.column_id)
        pos = next((i for i, c in enumerate(old_cards) if c is focused), 0)
        idx = cols.index(focused.column_id) + direction
        while 0 <= idx < len(cols):
            cards = self._column_cards(cols[idx])
            if cards:
                cards[min(pos, len(cards) - 1)].focus()
                return
            idx += direction

    def action_nav_up(self):
        self._nav_vertical(-1)

    def action_nav_down(self):
        self._nav_vertical(1)

    def action_nav_left(self):
        self._nav_lateral(-1)

    def action_nav_right(self):
        self._nav_lateral(1)

    # --- Footer / dispatch gating ------------------------------------------

    def check_action(self, action: str, parameters) -> bool | None:
        # Modal widgets that own their arrow keys (the board's rules).
        if action in ("nav_up", "nav_down", "nav_left", "nav_right"):
            if isinstance(self.screen, TuiSwitcherOverlay):
                return False
            if isinstance(self.app.focused, (Input, SelectionList, DataTable)):
                return False
            if action in ("nav_left", "nav_right") and len(self.screen_stack) > 1:
                return False
            if action in ("nav_up", "nav_down"):
                from textual.widgets._select import SelectOverlay
                if isinstance(self.app.focused, SelectOverlay):
                    return False
            return True
        if action in ("trail_move_wave", "trail_sync"):
            # Declared for shortcut ownership (C10), never live here: the
            # board-only machinery they reach does not exist in this App.
            return False
        if action in ("trail_refresh_local", "trail_refresh_drift",
                      "trail_refresh_agent"):
            if not self.active_trail_handle:
                return False
            if action == "trail_refresh_agent" and self._trail_launch_pending:
                return False
        elif action == "trail_summary_expand":
            from board_trail_view import trail_summary_text
            if not trail_summary_text(self._trail_doc):
                return False
        elif action in ("trail_task", "view_details"):
            if not self._focused_card():
                return False
        return True


def main(argv: list[str] | None = None) -> None:
    """Launcher entry point. The task directory arrives as an ARGUMENT
    (`aitask_trails.sh` exports `TASK_DIR="${TASK_DIR:-aitasks}"` and passes
    `--tasks-dir "$TASK_DIR"` last), so this module never resolves it itself —
    C2 holds for the whole file, not just its import time — while trail
    discovery and the artifact / agent subprocesses, which read `TASK_DIR`
    from the environment, see the same directory.

    `--tasks-dir` is therefore the launcher's flag, not a user override: two
    different values on one command line (a user's plus the launcher's) mean
    the manager and discovery would read different trees, and the app refuses
    to start rather than let either silently win. Set `TASK_DIR` instead."""
    import argparse

    parser = argparse.ArgumentParser(description="aitasks implementation-trails TUI")
    # Default is the framework's literal default, so a bare `python
    # trails_app.py` (the footprint measurement, run with TASK_DIR unset)
    # reads `aitasks/` — the same tree discovery's own default names.
    parser.add_argument("--tasks-dir", action="append", type=Path,
                        help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    given = list(dict.fromkeys(args.tasks_dir or []))
    if len(given) > 1:
        parser.error("conflicting --tasks-dir values "
                     f"{[str(p) for p in given]}: the launcher sets this "
                     "flag from TASK_DIR — set TASK_DIR instead of passing it")
    tasks = given[0] if given else Path("aitasks")
    TrailsApp(tasks_dir=tasks,
              metadata_file=tasks / "metadata" / "board_config.json",
              gates_registry_file=tasks / "metadata" / "gates.yaml").run()


if __name__ == "__main__":
    main()
