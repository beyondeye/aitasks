"""Code viewer widget with syntax highlighting, line numbers, and annotation gutter."""

from pathlib import Path

from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Static

from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from annotation_data import AnnotationRange

ANNOTATION_COLORS = [
    "cyan", "green", "yellow", "magenta",
    "blue", "red", "bright_cyan", "bright_green",
]

CURSOR_STYLE = Style(bgcolor="grey27")
SELECTION_STYLE = Style(bgcolor="dark_blue")


class CodeViewer(VerticalScroll):
    """Displays source code with syntax highlighting, line numbers, and annotation gutter."""

    class CursorMoved(Message):
        """Posted when the cursor line changes."""

        def __init__(self, line: int, total: int):
            super().__init__()
            self.line = line
            self.total = total

    BINDINGS = [
        Binding("up", "cursor_up", "Cursor up", show=False),
        Binding("down", "cursor_down", "Cursor down", show=False),
        Binding("shift+up", "select_up", "Select up", show=False),
        Binding("shift+down", "select_down", "Select down", show=False),
        Binding("escape", "clear_selection", "Clear selection", show=False),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._file_path: Path | None = None
        self._lines: list[str] = []
        self._total_lines: int = 0
        self._highlighted_lines: list[Text] = []
        self._annotations: list[AnnotationRange] = []
        self._show_annotations: bool = True
        self._cursor_line: int = 0
        self._selection_start: int | None = None
        self._selection_end: int | None = None
        self._selection_active: bool = False
        self._mouse_dragging: bool = False

    def compose(self):
        yield Static("Select a file to view", id="code_display")

    def load_file(self, file_path: Path) -> None:
        """Load and display a file with syntax highlighting."""
        try:
            content = file_path.read_text(errors="replace")
        except OSError as e:
            self.query_one("#code_display", Static).update(
                f"Error reading file: {e}"
            )
            return

        self._file_path = file_path
        self._lines = content.splitlines()
        self._total_lines = len(self._lines)
        self._annotations = []
        self._cursor_line = 0
        self._selection_start = None
        self._selection_end = None
        self._selection_active = False

        lexer = Syntax.guess_lexer(str(file_path), code=content)
        syntax = Syntax(content, lexer, theme="monokai")
        highlighted_text = syntax.highlight(content)
        self._highlighted_lines = highlighted_text.split("\n")

        self._rebuild_display()
        self.scroll_home(animate=False)

    def set_annotations(self, annotations: list[AnnotationRange]) -> None:
        """Set annotation data and rebuild display if annotations are visible."""
        self._annotations = annotations
        if self._show_annotations:
            self._rebuild_display()

    def toggle_annotations(self) -> None:
        """Toggle annotation gutter visibility."""
        self._show_annotations = not self._show_annotations
        self._rebuild_display()

    def _build_annotation_gutter(self) -> list[Text]:
        """Build per-line annotation text from AnnotationRange data."""
        gutter = [Text("") for _ in range(len(self._highlighted_lines))]
        for ann in self._annotations:
            label = ",".join(f"t{tid}" for tid in ann.task_ids)
            color = ANNOTATION_COLORS[
                hash(ann.task_ids[0]) % len(ANNOTATION_COLORS)
            ] if ann.task_ids else "dim"
            for line_num in range(ann.start_line, ann.end_line + 1):
                idx = line_num - 1
                if 0 <= idx < len(gutter):
                    gutter[idx] = Text(label, style=color)
        return gutter

    def _rebuild_display(self) -> None:
        """Build and render the line-number + code + annotation table."""
        table = Table(
            show_header=False,
            show_edge=False,
            box=None,
            pad_edge=False,
        )
        table.add_column(style="dim", justify="right", width=5, no_wrap=True)
        table.add_column(no_wrap=True)
        table.add_column(width=12, no_wrap=True, justify="left")

        if self._show_annotations and self._annotations:
            gutter = self._build_annotation_gutter()
        else:
            gutter = [Text("") for _ in range(len(self._highlighted_lines))]

        sel_min, sel_max = self._selection_bounds()

        for i, line in enumerate(self._highlighted_lines):
            ann_text = gutter[i] if i < len(gutter) else Text("")
            row_style = None
            if i == self._cursor_line:
                row_style = CURSOR_STYLE
            elif sel_min is not None and sel_min <= i <= sel_max:
                row_style = SELECTION_STYLE
            table.add_row(
                Text(str(i + 1), style="dim"), line, ann_text, style=row_style
            )

        self.query_one("#code_display", Static).update(table)

    def _selection_bounds(self) -> tuple[int | None, int | None]:
        """Return (min, max) of selection range, or (None, None)."""
        if self._selection_start is not None and self._selection_end is not None:
            return min(self._selection_start, self._selection_end), max(
                self._selection_start, self._selection_end
            )
        return None, None

    def _scroll_cursor_visible(self) -> None:
        """Scroll only if the cursor line is outside the visible viewport."""
        margin = 2
        top = self.scroll_y
        bottom = top + self.size.height - 1
        if self._cursor_line < top + margin:
            self.scroll_to(y=max(0, self._cursor_line - margin), animate=False)
        elif self._cursor_line > bottom - margin:
            self.scroll_to(
                y=self._cursor_line - self.size.height + 1 + margin, animate=False
            )

    def move_cursor(self, line: int) -> None:
        """Move cursor to the given 0-indexed line. Selection stays visible but is
        marked inactive so the next shift+arrow starts a fresh selection."""
        if self._total_lines == 0:
            return
        line = max(0, min(line, self._total_lines - 1))
        self._cursor_line = line
        self._selection_active = False
        self._rebuild_display()
        self._scroll_cursor_visible()
        self.post_message(self.CursorMoved(line + 1, self._total_lines))

    def extend_selection(self, direction: int) -> None:
        """Extend selection by one line in the given direction (+1 or -1).
        If selection is inactive (shift was released), start fresh from cursor."""
        if self._total_lines == 0:
            return
        if not self._selection_active:
            self._selection_start = self._cursor_line
            self._selection_active = True
        new_line = max(0, min(self._cursor_line + direction, self._total_lines - 1))
        self._cursor_line = new_line
        self._selection_end = new_line
        self._rebuild_display()
        self._scroll_cursor_visible()
        self.post_message(self.CursorMoved(new_line + 1, self._total_lines))

    def clear_selection(self) -> None:
        """Clear the current selection entirely."""
        self._selection_start = None
        self._selection_end = None
        self._selection_active = False
        self._rebuild_display()

    def get_selected_range(self) -> tuple[int, int] | None:
        """Return 1-indexed (start, end) of selection, or None."""
        sel_min, sel_max = self._selection_bounds()
        if sel_min is not None and sel_max is not None:
            return (sel_min + 1, sel_max + 1)
        return None

    def action_cursor_up(self) -> None:
        self.move_cursor(self._cursor_line - 1)

    def action_cursor_down(self) -> None:
        self.move_cursor(self._cursor_line + 1)

    def action_select_up(self) -> None:
        self.extend_selection(-1)

    def action_select_down(self) -> None:
        self.extend_selection(1)

    def action_clear_selection(self) -> None:
        self.clear_selection()

    # -- Mouse handlers -------------------------------------------------------

    def on_mouse_down(self, event) -> None:
        """Left-click moves cursor to clicked line and starts drag tracking."""
        if event.button != 1 or self._total_lines == 0:
            return
        line = int(self.scroll_y) + event.y
        line = max(0, min(line, self._total_lines - 1))
        self._cursor_line = line
        self._selection_start = line
        self._selection_end = line
        self._selection_active = True
        self._mouse_dragging = True
        self.capture_mouse()
        self._rebuild_display()
        self.post_message(self.CursorMoved(line + 1, self._total_lines))

    def on_mouse_move(self, event) -> None:
        """Extend selection while dragging with left button held."""
        if not self._mouse_dragging:
            return
        line = int(self.scroll_y) + event.y
        line = max(0, min(line, self._total_lines - 1))
        if line == self._cursor_line:
            return
        self._cursor_line = line
        self._selection_end = line
        self._rebuild_display()
        self._scroll_cursor_visible()
        self.post_message(self.CursorMoved(line + 1, self._total_lines))

    def on_mouse_up(self, event) -> None:
        """Finalize click or drag selection."""
        if not self._mouse_dragging:
            return
        self._mouse_dragging = False
        self.release_mouse()
        if self._selection_start == self._selection_end:
            # Single click (no drag) — clear selection, just keep cursor
            self._selection_start = None
            self._selection_end = None
            self._selection_active = False
            self._rebuild_display()
