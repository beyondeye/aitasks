"""Code viewer widget with syntax highlighting, line numbers, and annotation gutter."""

from pathlib import Path

from textual.containers import VerticalScroll
from textual.widgets import Static

from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from annotation_data import AnnotationRange

ANNOTATION_COLORS = [
    "cyan", "green", "yellow", "magenta",
    "blue", "red", "bright_cyan", "bright_green",
]


class CodeViewer(VerticalScroll):
    """Displays source code with syntax highlighting, line numbers, and annotation gutter."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._file_path: Path | None = None
        self._lines: list[str] = []
        self._total_lines: int = 0
        self._highlighted_lines: list[Text] = []
        self._annotations: list[AnnotationRange] = []
        self._show_annotations: bool = True

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

        lexer = Syntax.guess_lexer(str(file_path), code=content)
        syntax = Syntax(content, lexer, theme="monokai")
        highlighted_text = syntax.highlight(content)
        self._highlighted_lines = highlighted_text.split("\n")

        self._rebuild_display()

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

        for i, line in enumerate(self._highlighted_lines):
            ann_text = gutter[i] if i < len(gutter) else Text("")
            table.add_row(Text(str(i + 1), style="dim"), line, ann_text)

        self.query_one("#code_display", Static).update(table)
        self.scroll_home(animate=False)
