"""Code viewer widget with syntax highlighting and line numbers."""

from pathlib import Path

from textual.containers import VerticalScroll
from textual.widgets import Static

from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text


class CodeViewer(VerticalScroll):
    """Displays source code with syntax highlighting and line numbers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._file_path: Path | None = None
        self._lines: list[str] = []
        self._total_lines: int = 0
        self._highlighted_lines: list[Text] = []

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

        lexer = Syntax.guess_lexer(str(file_path), code=content)
        syntax = Syntax(content, lexer, theme="monokai")
        highlighted_text = syntax.highlight(content)
        self._highlighted_lines = highlighted_text.split("\n")

        self._rebuild_display()

    def _rebuild_display(self) -> None:
        """Build and render the line-number + code table."""
        table = Table(
            show_header=False,
            show_edge=False,
            box=None,
            pad_edge=False,
        )
        table.add_column(style="dim", justify="right", width=5, no_wrap=True)
        table.add_column(no_wrap=True)

        for i, line in enumerate(self._highlighted_lines):
            table.add_row(Text(str(i + 1), style="dim"), line)

        self.query_one("#code_display", Static).update(table)
        self.scroll_home(animate=False)
