"""The column-management dialogs: the manage screen, the column pickers, the
add/edit dialog and its colour swatch, and the delete/merge confirmations
(t1794_8).

Extracted verbatim from ``aitask_board.py`` (parent plan t1794). The board
re-exports every name, so ``ab.ColumnManageScreen`` / ``ab.ColorSwatch`` keep
resolving; inside this module the classes reach each other through THIS
namespace, so a stub of a name they call must target ``board_column_dialogs``,
not the board.

``ColumnEditScreen``, ``DeleteColumnConfirmScreen`` and
``MergeColumnsConfirmScreen`` live here — not only the six classes the parent
file map names — because ``ColumnManageScreen`` pushes all three. Leaving them
in the board would force an ``import aitask_board`` back, which C1 forbids, and
would also strand ``ColorSwatch`` away from ``ColumnEditScreen``, its only
consumer. The board still pushes the edit / delete / select screens directly
(``_open_column_manage``, ``_choose_move_destination``, the add/edit/delete
actions); those call sites stay there and import these names flat.

Contracts (see ``board/__init__.py`` and the parent plan):

* C1 — imported by bare name; never imports ``aitask_board``. **No injection is
  needed here**, unlike ``board_detail_screen``: these classes call no
  module-level board function. ``ColumnManageScreen`` reaches the host only
  through ``self.app`` (``_column_title``, ``_apply_column_edit``,
  ``_merge_source_columns``, ``_report_merge``, ``notify``, ``push_screen``) and
  the column model only through ``self.manager`` — both live objects, resolved
  at call time.
* C2 — resolves no task directory. The column vocabulary comes from
  ``lib/board_columns.py``, which binds no ``TASKS_DIR``-derived path.

The dialogs' CSS stays in ``KanbanApp.CSS`` (the board is the only App that
pushes them — ``trails_app`` uses none — and several rules are shared with other
board modals). No class here declares ``_shortcuts_scope`` or mixes in
``ShortcutsMixin``, so ``lib/shortcut_scopes.py`` needs no row for this file;
their plain ``BINDINGS`` are ordinary ``ModalScreen`` bindings.
"""

from __future__ import annotations

from textual import on
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, SelectionList, Static
from textual.widgets.selection_list import Selection

from board_columns import (
    PALETTE_COLORS, UNORDERED_COLOR, UNORDERED_ID, UNORDERED_TITLE,
    generate_col_id,
)

from board_widgets import PickerItem
from board_task_manager import TaskManager


class ColumnMultiSelectScreen(ModalScreen):
    """Modal dialog to multi-select board columns.

    Used by the work report (which columns feed it) and by the column-merge flow
    (which columns are the merge sources). Parameterised by ``prompt`` rather
    than forked: t1377's AC7 forbids a second column picker inside the board, and
    a `SelectionList` over ``(col_id, title)`` pairs is exactly what both need.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, columns: list, initial: str | None,
                 prompt: str = "Work report columns"):
        """``columns``: ordered (col_id, title) pairs; ``initial``: pre-checked col_id."""
        super().__init__()
        self.columns = list(columns)
        self.initial = initial
        self.prompt = prompt

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label(
                f"{self.prompt} — [dim]space to toggle, Enter to confirm, "
                "Esc to cancel[/]",
                id="dep_picker_title",
            )
            yield SelectionList[str](
                *(
                    Selection(title, value=col_id,
                              initial_state=(col_id == self.initial))
                    for col_id, title in self.columns
                ),
                id="work_report_column_list",
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Confirm", variant="primary", id="btn_wr_cols_save")
                yield Button("Cancel", variant="default", id="btn_wr_cols_cancel")

    def on_mount(self):
        self.query_one("#work_report_column_list", SelectionList).focus()

    def _selected(self) -> list:
        sl = self.query_one("#work_report_column_list", SelectionList)
        checked = set(sl.selected)
        return [col_id for col_id, _ in self.columns if col_id in checked]

    @on(Button.Pressed, "#btn_wr_cols_save")
    def _btn_save(self):
        self.dismiss(self._selected())

    @on(Button.Pressed, "#btn_wr_cols_cancel")
    def _btn_cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)

    def on_key(self, event):
        # SelectionList uses space for toggle and consumes it. Enter is free,
        # so treat it as "confirm selection".
        if event.key == "enter":
            self.dismiss(self._selected())
            event.stop()


class ColorSwatch(Static):
    """A clickable color swatch for the palette."""

    can_focus = True

    class Selected(Message):
        def __init__(self, color: str):
            super().__init__()
            self.color = color

    def __init__(self, color: str, label: str, selected: bool = False):
        super().__init__()
        self.color = color
        self.label = label
        self.is_selected = selected

    def render(self) -> str:
        marker = "\u25cf" if self.is_selected else "\u25cb"
        return f"[{self.color}]{marker} \u2588\u2588[/]"

    def on_click(self):
        self.post_message(self.Selected(self.color))

    def on_key(self, event):
        if event.key in ("enter", "space"):
            self.post_message(self.Selected(self.color))
            event.prevent_default()
            event.stop()

    def on_focus(self):
        self.styles.border = ("round", self.color)

    def on_blur(self):
        self.styles.border = None


class ColumnEditScreen(ModalScreen):
    """Modal dialog for adding or editing a kanban column."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, manager: TaskManager, col_id: str = None, mode: str = "add"):
        super().__init__()
        self.manager = manager
        self.col_id = col_id
        self.mode = mode
        self.col_conf = manager.get_column_conf(col_id) if col_id else None
        self.selected_color = self.col_conf["color"] if self.col_conf else PALETTE_COLORS[0][0]

    @staticmethod
    def _generate_col_id(name: str, existing_ids: list) -> str:
        """Generate a unique column ID from a display name.

        Thin delegate: the implementation moved to `lib/board_columns.py`
        (t1377_3) so the headless writer and this dialog slug identically. The
        board stays the semantic owner — see that module's docstring.
        """
        return generate_col_id(name, existing_ids)

    def compose(self):
        title = "Add New Column" if self.mode == "add" else f"Edit Column: {self.col_conf['title']}"
        with Container(id="column_edit_dialog"):
            yield Label(title, id="column_edit_title")
            yield Input(
                value=self.col_conf["title"] if self.col_conf else "",
                placeholder="Column name",
                id="col_title_input",
            )
            with Horizontal(id="color_palette"):
                yield Label("Color ", id="color_label")
                for color, label in PALETTE_COLORS:
                    yield ColorSwatch(color, label, selected=(color == self.selected_color))
            with Horizontal(id="detail_buttons"):
                yield Button("Save", variant="success", id="btn_col_save")
                yield Button("Cancel", variant="default", id="btn_col_cancel")

    @on(ColorSwatch.Selected)
    def on_color_selected(self, event: ColorSwatch.Selected):
        self.selected_color = event.color
        for swatch in self.query(ColorSwatch):
            swatch.is_selected = (swatch.color == event.color)
            swatch.refresh()

    @on(Button.Pressed, "#btn_col_save")
    def save(self):
        title = self.query_one("#col_title_input", Input).value.strip()
        if not title:
            self.app.notify("Title is required", severity="warning")
            return
        color = self.selected_color
        if self.mode == "add":
            existing_ids = [c["id"] for c in self.manager.columns]
            col_id = self._generate_col_id(title, existing_ids)
            self.dismiss(("add", col_id, title, color))
        else:
            self.dismiss(("edit", self.col_id, title, color))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.save()

    @on(Button.Pressed, "#btn_col_cancel")
    def cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class DeleteColumnConfirmScreen(ModalScreen):
    """Confirmation dialog to delete a column."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, col_conf: dict, task_count: int):
        super().__init__()
        self.col_conf = col_conf
        self.task_count = task_count

    def compose(self):
        msg = f"Delete column '{self.col_conf['title']}'?"
        if self.task_count > 0:
            msg += f"\n\n{self.task_count} task(s) will be moved to Unsorted / Inbox."
        with Container(id="dep_picker_dialog"):
            yield Label(msg, id="dep_picker_title")
            with Horizontal(id="detail_buttons"):
                yield Button("Delete", variant="error", id="btn_confirm_col_delete")
                yield Button("Cancel", variant="default", id="btn_cancel_col_delete")

    @on(Button.Pressed, "#btn_confirm_col_delete")
    def confirm(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_cancel_col_delete")
    def cancel(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


class ColumnSelectItem(PickerItem):
    """A selectable column item in the picker."""

    def __init__(self, col_conf: dict):
        super().__init__()
        self.col_conf = col_conf

    def render(self) -> str:
        return f"  [{self.col_conf['color']}]\u2588\u2588[/] {self.col_conf['title']} ({self.col_conf['id']})"

    def on_key(self, event):
        if event.key == "enter":
            self.screen.dismiss(self.col_conf["id"])
            event.prevent_default()
            event.stop()

    def on_click(self):
        self.screen.dismiss(self.col_conf["id"])


class ColumnSelectScreen(ModalScreen):
    """Select a column from the list for editing/deleting/collapsing/expanding."""

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
    ]

    def __init__(self, manager: TaskManager, action_label: str, columns: list[dict] = None):
        super().__init__()
        self.manager = manager
        self.action_label = action_label
        self.columns_list = columns if columns is not None else manager.columns

    def compose(self):
        with Container(id="dep_picker_dialog", classes="picker-dialog"):
            yield Label(f"Select column to {self.action_label.lower()}:", id="dep_picker_title")
            for col in self.columns_list:
                yield ColumnSelectItem(col)

    def action_cancel(self):
        self.dismiss(None)


class ColumnManageItem(PickerItem):
    """One column row inside :class:`ColumnManageScreen`."""

    def __init__(self, col_conf: dict, position: int, task_count: int):
        super().__init__()
        self.col_conf = col_conf
        self.position = position
        self.task_count = task_count

    @property
    def col_id(self) -> str:
        return self.col_conf["id"]

    def render(self) -> str:
        n = self.task_count
        return (f"  {self.position:>2}. [{self.col_conf['color']}]██[/] "
                f"{self.col_conf['title']} ({self.col_id}) "
                f"— {n} task{'' if n == 1 else 's'}")

    def on_key(self, event):
        if event.key == "enter":
            self.screen.edit_column(self.col_id)
            event.prevent_default()
            event.stop()

    def on_click(self):
        self.focus()


class MergeColumnsConfirmScreen(ModalScreen):
    """Confirmation for an N->1 column merge, naming what actually moves."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, source_titles: list, dest_title: str, task_count: int):
        super().__init__()
        self.source_titles = list(source_titles)
        self.dest_title = dest_title
        self.task_count = task_count

    def compose(self):
        sources = ", ".join(f"'{t}'" for t in self.source_titles)
        n = self.task_count
        msg = (f"Merge {sources} into '{self.dest_title}'?\n\n"
               f"{n} task{'' if n == 1 else 's'} will move to the bottom of "
               f"'{self.dest_title}'.\n"
               f"The source column{'' if len(self.source_titles) == 1 else 's'} "
               "will be removed.")
        with Container(id="dep_picker_dialog"):
            yield Label(msg, id="dep_picker_title")
            with Horizontal(id="detail_buttons"):
                yield Button("Merge", variant="warning", id="btn_confirm_col_merge")
                yield Button("Cancel", variant="default", id="btn_cancel_col_merge")

    @on(Button.Pressed, "#btn_confirm_col_merge")
    def confirm(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_cancel_col_merge")
    def cancel(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


class ColumnManageScreen(ModalScreen):
    """One dialog behind one key for every column operation (t1377_5).

    Add / edit / delete / reorder / collapse all existed before this screen, but
    **no key was bound to any of them** — they were reachable only through the
    Ctrl+P palette or the column-header pencil button. Merge did not exist at all
    until t1377_4 landed the engine (with zero call sites; this screen is its
    first consumer).

    Every sub-flow reuses an existing modal — `ColumnEditScreen`,
    `DeleteColumnConfirmScreen`, `ColumnMultiSelectScreen`, `ColumnSelectScreen`
    — because t1377's AC7 forbids a second column picker inside the board.

    Mutations are applied without refreshing the board per operation: the screen
    tracks `_changed` and dismisses it, so the caller recomposes exactly once on
    close instead of once per edit under a live modal.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
        Binding("shift+up", "shift_up", "Move column up", show=False),
        Binding("shift+down", "shift_down", "Move column down", show=False),
    ]

    def __init__(self, manager: TaskManager, start_in_merge: bool = False):
        super().__init__()
        self.manager = manager
        self._changed = False
        self._start_in_merge = start_in_merge

    # --- composition -----------------------------------------------------

    def compose(self):
        with Container(id="column_manage_dialog", classes="picker-dialog"):
            yield Label(
                "Manage columns — [dim]shift+↑/↓ reorder, "
                "Enter edit, Esc close[/]",
                id="dep_picker_title",
            )
            yield VerticalScroll(id="column_manage_list")
            # Four buttons, not five: `#detail_buttons` centers without
            # wrapping, so anything past the dialog width is clipped rather
            # than reflowed. A fifth "Close" button pushed the row over the
            # edge at 100 columns — a visible control the user cannot click.
            # Esc closes, `action_cancel` handles it, and the hint line above
            # says so, matching every other modal in this file.
            with Horizontal(id="detail_buttons"):
                yield Button("Add", variant="primary", id="btn_colmgr_add")
                yield Button("Edit", variant="default", id="btn_colmgr_edit")
                yield Button("Delete", variant="error", id="btn_colmgr_delete")
                yield Button("Merge", variant="warning", id="btn_colmgr_merge")

    def on_mount(self):
        self._rebuild()
        if self._start_in_merge:
            self.call_after_refresh(self.action_merge)

    def _rows(self) -> list:
        """`(col_conf, task_count)` for every column actually on the board.

        A `column_order` entry with no matching `columns` definition is dropped
        silently by both the renderer and `load_columns()`, so it is not offered
        here either — listing it would let the user "reorder" a column that does
        not render.
        """
        rows = []
        for col_id in self.manager.column_order:
            conf = self.manager.get_column_conf(col_id)
            if conf:
                rows.append((conf, len(self.manager.get_column_tasks(col_id))))
        return rows

    def _rebuild(self, focus_col_id: str = None):
        listing = self.query_one("#column_manage_list", VerticalScroll)
        listing.remove_children()
        items = [ColumnManageItem(conf, pos, count)
                 for pos, (conf, count) in enumerate(self._rows(), start=1)]
        if items:
            listing.mount_all(items)
            target = focus_col_id or items[0].col_id
            self.call_after_refresh(self._focus_col, target)

    def _focus_col(self, col_id: str):
        for item in self.query(ColumnManageItem):
            if item.col_id == col_id:
                item.focus()
                return

    def _focused_item(self):
        focused = self.screen.focused
        return focused if isinstance(focused, ColumnManageItem) else None

    def _title_of(self, col_id: str) -> str:
        """Display title, delegating so the synthetic lane is named correctly.

        `get_column_conf` returns None for `unordered` (it is not in `columns`),
        so a local fallback to the raw id would confirm and report a merge as
        "unordered" while the picker the user just clicked said "Unsorted /
        Inbox". `KanbanApp._column_title` already owns that mapping.
        """
        return self.app._column_title(col_id)

    # --- reorder ---------------------------------------------------------

    def _shift(self, direction: int):
        item = self._focused_item()
        if item is None:
            return
        visible = [conf["id"] for conf, _ in self._rows()]
        pos = visible.index(item.col_id)
        new_pos = pos + direction
        if not (0 <= new_pos < len(visible)):
            return
        # Swap the two ids WHERE THEY SIT in column_order rather than swapping
        # adjacent order slots: a stale (conf-less) entry can sit between two
        # visible columns, and swapping raw slots would move the stale entry
        # instead of the column the user is looking at.
        order = self.manager.column_order
        a, b = order.index(item.col_id), order.index(visible[new_pos])
        order[a], order[b] = order[b], order[a]
        self.manager.save_metadata()
        self._changed = True
        self._rebuild(focus_col_id=item.col_id)

    def action_shift_up(self):
        self._shift(-1)

    def action_shift_down(self):
        self._shift(1)

    # --- add / edit / delete ---------------------------------------------

    def _on_edit_result(self, result):
        if self.app._apply_column_edit(result):
            self._changed = True
            col_id = result[1] if len(result) > 1 else None
            self._rebuild(focus_col_id=col_id)

    def action_add(self):
        self.app.push_screen(
            ColumnEditScreen(self.manager, mode="add"), self._on_edit_result)

    def edit_column(self, col_id: str):
        self.app.push_screen(
            ColumnEditScreen(self.manager, col_id=col_id, mode="edit"),
            self._on_edit_result)

    def action_edit(self):
        item = self._focused_item()
        if item is None:
            self.app.notify("Select a column to edit", severity="warning")
            return
        self.edit_column(item.col_id)

    def action_delete(self):
        item = self._focused_item()
        if item is None:
            self.app.notify("Select a column to delete", severity="warning")
            return
        col_id = item.col_id
        conf = self.manager.get_column_conf(col_id)
        count = len(self.manager.get_column_tasks(col_id))

        def on_confirmed(confirmed):
            if confirmed:
                self.manager.delete_column(col_id)
                self.app.notify(f"Deleted column: {conf['title']}",
                                severity="information")
                self._changed = True
                self._rebuild()

        self.app.push_screen(DeleteColumnConfirmScreen(conf, count), on_confirmed)

    # --- merge -----------------------------------------------------------

    def action_merge(self):
        """sources (multi-select) -> destination -> confirm -> merge_columns."""
        sources = self.app._merge_source_columns()
        if len(sources) < 2:
            self.app.notify(
                "Merging needs at least two columns to choose from",
                severity="warning")
            return

        def on_sources(chosen):
            if not chosen:
                return
            self._pick_destination(chosen)

        self.app.push_screen(
            ColumnMultiSelectScreen(sources, None, prompt="Merge FROM"),
            on_sources)

    def _pick_destination(self, source_ids: list):
        remaining = [conf for conf, _ in self._rows()
                     if conf["id"] not in source_ids]
        if UNORDERED_ID not in source_ids:
            # Same hand-injection idiom as `action_collapse_column`: the lane is
            # synthetic and absent from `columns`, but `merge_columns` accepts it
            # as a destination (it is what `delete_column` already does).
            remaining.append({"id": UNORDERED_ID, "title": UNORDERED_TITLE,
                              "color": UNORDERED_COLOR})
        if not remaining:
            self.app.notify("No destination column left to merge into",
                            severity="warning")
            return

        def on_destination(dest_id):
            if dest_id:
                self._confirm_merge(source_ids, dest_id)

        self.app.push_screen(
            ColumnSelectScreen(self.manager, "Merge into", columns=remaining),
            on_destination)

    def _confirm_merge(self, source_ids: list, dest_id: str):
        attempted = sum(len(self.manager.get_column_tasks(c)) for c in source_ids)
        titles = [self._title_of(c) for c in source_ids]

        def on_confirmed(confirmed):
            if not confirmed:
                return
            result = self.manager.merge_columns(source_ids, dest_id)
            self.app._report_merge(result, self._title_of(dest_id), attempted)
            if result.merged or result.sources_removed:
                self._changed = True
            self._rebuild()

        self.app.push_screen(
            MergeColumnsConfirmScreen(titles, self._title_of(dest_id), attempted),
            on_confirmed)

    # --- buttons / close --------------------------------------------------

    @on(Button.Pressed, "#btn_colmgr_add")
    def _btn_add(self):
        self.action_add()

    @on(Button.Pressed, "#btn_colmgr_edit")
    def _btn_edit(self):
        self.action_edit()

    @on(Button.Pressed, "#btn_colmgr_delete")
    def _btn_delete(self):
        self.action_delete()

    @on(Button.Pressed, "#btn_colmgr_merge")
    def _btn_merge(self):
        self.action_merge()

    def handle_escape(self):
        """Escape hook honoured by `KanbanApp.action_focus_board`.

        The app binds `escape` with `priority=True`, so it wins over this
        screen's own binding and closes any active modal with a bare
        `self.screen.dismiss()` — i.e. a `None` result. Every other board modal
        treats `None` as "cancelled", so the discarded value is harmless there;
        here it is not, because the dismiss value is the "did anything change?"
        flag the caller uses to decide whether to recompose. Without this hook a
        merge or reorder closed with Escape left the board rendering the removed
        column until the next manual refresh.
        """
        self.dismiss(self._changed)

    def action_cancel(self):
        self.dismiss(self._changed)
