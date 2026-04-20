"""Modal for picking which panes go into a custom stats-TUI layout."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, SelectionList
from textual.widgets.selection_list import Selection

from stats.panes import PANE_DEFS


class PaneSelectorModal(ModalScreen):
    """Returns the ordered list of checked pane ids, or None on cancel.

    Enter saves, Escape cancels. Category rows are disabled headers.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=False),
    ]

    CSS = """
    PaneSelectorModal { align: center middle; }

    #pane_selector_dialog {
        width: 70%;
        height: 80%;
        max-width: 100;
        max-height: 30;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    #pane_selector_title {
        text-style: bold;
        color: $accent;
        padding: 0 0 1 0;
    }

    #pane_selector_list { height: 1fr; }

    #pane_selector_buttons {
        padding: 1 0 0 0;
        height: auto;
    }
    #pane_selector_buttons Button { margin: 0 1; }
    """

    def __init__(self, layout_name: str, initial: list[str]) -> None:
        super().__init__()
        self.layout_name = layout_name
        self.initial = list(initial)

    def compose(self) -> ComposeResult:
        with Container(id="pane_selector_dialog"):
            yield Label(
                f"Panes for '{self.layout_name}' — [dim]space to toggle, Enter to save, Esc to cancel[/]",
                id="pane_selector_title",
            )
            yield SelectionList[str](
                *self._build_selections(),
                id="pane_selector_list",
            )
            with Horizontal(id="pane_selector_buttons"):
                yield Button("Save", id="btn_save", variant="primary")
                yield Button("Cancel", id="btn_cancel")

    def on_mount(self) -> None:
        self.query_one("#pane_selector_list", SelectionList).focus()

    def _build_selections(self) -> list[Selection[str]]:
        checked = set(self.initial)
        selections: list[Selection[str]] = []
        current_category: str | None = None
        for pid, pane in PANE_DEFS.items():
            if pane.category != current_category:
                current_category = pane.category
                selections.append(
                    Selection(
                        f"[b]{current_category}[/b]",
                        value=f"__cat_{current_category}",
                        initial_state=False,
                        disabled=True,
                    )
                )
            selections.append(
                Selection(
                    f"  {pane.title}",
                    value=pid,
                    initial_state=pid in checked,
                )
            )
        return selections

    def _selected_pane_ids(self) -> list[str]:
        sl = self.query_one("#pane_selector_list", SelectionList)
        checked = set(sl.selected)
        # Preserve PANE_DEFS iteration order so the sidebar renders
        # predictably (categories first, in-category order preserved).
        return [pid for pid in PANE_DEFS if pid in checked]

    # ─── Actions ───────────────────────────────────────────────────────────

    def action_save(self) -> None:
        self.dismiss(self._selected_pane_ids())

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_save":
            self.dismiss(self._selected_pane_ids())
        else:
            self.dismiss(None)

    # Treat Enter in the SelectionList as "save the current selection".
    # (SelectionList uses space to toggle, so Enter is unused for toggling.)
    def on_selection_list_selection_message(self, event) -> None:
        # No-op placeholder: the default toggle behavior is space; Enter
        # is captured by on_key below for the save shortcut.
        pass

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.dismiss(self._selected_pane_ids())
            event.stop()
