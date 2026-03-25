"""Label filtering for history screen: modal dialog, filter functions."""

from __future__ import annotations

from pathlib import Path

from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from history_data import CompletedTask


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def load_labels(project_root: Path) -> list[str]:
    """Read labels from aitasks/metadata/labels.txt, return sorted list."""
    labels_file = project_root / "aitasks" / "metadata" / "labels.txt"
    if not labels_file.exists():
        return []
    lines = labels_file.read_text(encoding="utf-8").strip().splitlines()
    return sorted([l.strip() for l in lines if l.strip()])


def compute_label_counts(task_index: list[CompletedTask]) -> dict[str, int]:
    """Count occurrences of each label across the full task index."""
    counts: dict[str, int] = {}
    for task in task_index:
        for label in task.labels:
            counts[label] = counts.get(label, 0) + 1
    return counts


def filter_index_by_labels(
    task_index: list[CompletedTask], selected_labels: set[str]
) -> list[CompletedTask]:
    """Return tasks matching ANY of the selected labels. Empty set = no filter."""
    if not selected_labels:
        return task_index
    return [t for t in task_index if selected_labels & set(t.labels)]


# ---------------------------------------------------------------------------
# Helper: focus neighbor (same pattern as history_list._focus_neighbor)
# ---------------------------------------------------------------------------


def _focus_neighbor(widget, direction: int) -> None:
    parent = widget.parent
    if parent is None:
        return
    focusable = [
        w for w in parent.children
        if w.can_focus and w.display and w.styles.display != "none"
    ]
    try:
        idx = focusable.index(widget)
    except ValueError:
        return
    target = idx + direction
    if 0 <= target < len(focusable):
        focusable[target].focus()
        focusable[target].scroll_visible()


# ---------------------------------------------------------------------------
# LabelFilterItem widget
# ---------------------------------------------------------------------------


class LabelFilterItem(Static):
    """Focusable row for one label in the filter modal."""

    can_focus = True

    DEFAULT_CSS = """
    LabelFilterItem {
        height: 1;
        padding: 0 1;
    }
    LabelFilterItem:focus {
        background: $accent 20%;
    }
    LabelFilterItem:hover {
        background: $accent 10%;
    }
    """

    def __init__(self, label: str, count: int, selected: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.label_name = label
        self.count = count
        self.is_selected = selected

    def render(self) -> str:
        check = "[bold #50FA7B]x[/]" if self.is_selected else " "
        return f"  \\[{check}] {self.label_name}  [dim]({self.count})[/]"

    def _toggle(self) -> None:
        self.is_selected = not self.is_selected
        self.refresh()
        # Notify parent modal to update summaries
        modal = self.screen
        if isinstance(modal, LabelFilterModal):
            modal._on_item_toggled(self.label_name, self.is_selected)

    def on_key(self, event) -> None:
        if event.key == "enter" or event.key == "space":
            self._toggle()
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            _focus_neighbor(self, 1)
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            # If first item, move focus back to search input
            parent = self.parent
            if parent is not None:
                focusable = [
                    w for w in parent.children
                    if w.can_focus and w.display and w.styles.display != "none"
                ]
                try:
                    idx = focusable.index(self)
                except ValueError:
                    idx = 1
                if idx == 0:
                    # First item — move to search input
                    modal = self.screen
                    if isinstance(modal, LabelFilterModal):
                        modal.query_one("#label_search", Input).focus()
                    event.prevent_default()
                    event.stop()
                    return
            _focus_neighbor(self, -1)
            event.prevent_default()
            event.stop()

    def on_click(self) -> None:
        self._toggle()


# ---------------------------------------------------------------------------
# LabelFilterModal
# ---------------------------------------------------------------------------


class LabelFilterModal(ModalScreen[set[str] | None]):
    """Modal dialog for multi-select label filtering with fuzzy search."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close"),
        Binding("o", "confirm_ok", "OK", show=False),
        Binding("r", "confirm_reset", "Reset", show=False),
    ]

    DEFAULT_CSS = """
    LabelFilterModal {
        align: center middle;
    }
    #label_filter_dialog {
        width: 60%;
        max-height: 60%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #label_filter_title {
        text-style: bold;
        margin-bottom: 1;
    }
    #label_search {
        margin-bottom: 0;
    }
    #label_keybind_help {
        height: 1;
        padding: 0 1;
        color: $text-muted;
        margin-bottom: 1;
    }
    #label_selection_summary {
        height: auto;
        padding: 0 1;
        color: #FFB86C;
        text-style: italic;
    }
    #label_match_count {
        height: 1;
        padding: 0 1;
        color: #50FA7B;
        margin-bottom: 1;
    }
    #label_list {
        height: 1fr;
    }
    #label_buttons {
        margin-top: 1;
        height: auto;
    }
    #label_buttons Button {
        margin-right: 1;
    }
    """

    def __init__(
        self,
        all_labels: list[str],
        label_counts: dict[str, int],
        currently_selected: set[str],
        task_index: list[CompletedTask],
    ) -> None:
        super().__init__()
        self._all_labels = all_labels
        self._label_counts = label_counts
        self._selected: set[str] = set(currently_selected)
        self._task_index = task_index
        self._search_query = ""

    def compose(self):
        with Container(id="label_filter_dialog"):
            yield Static("Filter by Labels", id="label_filter_title")
            yield Input(placeholder="Search labels...", id="label_search")
            yield Static(
                "[dim]\\[Up/Down] navigate  \\[Enter/Space] toggle  \\[o] OK  \\[r] reset  \\[Esc] cancel[/]",
                id="label_keybind_help",
            )
            yield Static("", id="label_selection_summary")
            yield Static("", id="label_match_count")
            yield VerticalScroll(id="label_list")
            with Horizontal(id="label_buttons"):
                yield Button("OK", variant="primary", id="btn_label_ok")
                yield Button("Reset", variant="warning", id="btn_label_reset")
                yield Button("Cancel", variant="default", id="btn_label_cancel")

    def on_mount(self) -> None:
        self._refresh_list()
        self._update_summaries()
        self.query_one("#label_search", Input).focus()

    def on_key(self, event) -> None:
        """Handle Down arrow from Input to move focus to first label item."""
        if event.key == "down":
            focused = self.focused
            if isinstance(focused, Input) and focused.id == "label_search":
                container = self.query_one("#label_list", VerticalScroll)
                items = list(container.query(LabelFilterItem))
                if items:
                    items[0].focus()
                    items[0].scroll_visible()
                    event.prevent_default()
                    event.stop()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "label_search":
            self._search_query = event.value.lower()
            self._refresh_list()

    def _get_filtered_labels(self) -> list[str]:
        if not self._search_query:
            return self._all_labels
        return [l for l in self._all_labels if self._search_query in l.lower()]

    def _refresh_list(self) -> None:
        container = self.query_one("#label_list", VerticalScroll)
        for item in container.query(LabelFilterItem):
            item.remove()
        for label in self._get_filtered_labels():
            count = self._label_counts.get(label, 0)
            selected = label in self._selected
            container.mount(LabelFilterItem(label, count, selected=selected))

    def _on_item_toggled(self, label: str, selected: bool) -> None:
        """Called by LabelFilterItem when toggled. Update _selected set."""
        if selected:
            self._selected.add(label)
        else:
            self._selected.discard(label)
        self._update_summaries()

    def _update_summaries(self) -> None:
        # Selection summary — show ALL selected labels, no truncation
        if self._selected:
            labels_str = ", ".join(sorted(self._selected))
            self.query_one("#label_selection_summary", Static).update(
                f"Selected: {labels_str}"
            )
        else:
            self.query_one("#label_selection_summary", Static).update("")
        # Match count
        if self._selected:
            matched = sum(
                1 for t in self._task_index if self._selected & set(t.labels)
            )
            self.query_one("#label_match_count", Static).update(
                f"Matching tasks: {matched}"
            )
        else:
            total = len(self._task_index)
            self.query_one("#label_match_count", Static).update(
                f"All tasks: {total}"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_label_ok":
            self.dismiss(set(self._selected))
        elif event.button.id == "btn_label_reset":
            self.dismiss(set())  # empty set = clear filter
        elif event.button.id == "btn_label_cancel":
            self.dismiss(None)  # None = keep existing

    def action_confirm_ok(self) -> None:
        # Don't fire when typing in search input
        if isinstance(self.focused, Input):
            return
        self.dismiss(set(self._selected))

    def action_confirm_reset(self) -> None:
        # Don't fire when typing in search input
        if isinstance(self.focused, Input):
            return
        self.dismiss(set())

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)
