"""Diff display widget with color coding, line numbers, and keyboard navigation."""

from __future__ import annotations

from dataclasses import dataclass

from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Static

from rich.style import Style
from rich.table import Table
from rich.text import Text

from .diff_engine import DiffHunk, PairwiseDiff, MultiDiffResult


# Styles per diff tag
TAG_STYLES = {
    "equal": Style(dim=True),
    "insert": Style(color="white", bgcolor="dark_green"),
    "delete": Style(color="white", bgcolor="dark_red"),
    "replace": Style(color="white", bgcolor="dark_goldenrod"),
    "moved": Style(color="white", bgcolor="dark_cyan"),
}

# Gutter characters per diff tag
TAG_GUTTERS = {
    "equal": " ",
    "insert": "+",
    "delete": "-",
    "replace": "~",
    "moved": ">",
}

CURSOR_STYLE = Style(bold=True)

# Plan identifier colors for multi-diff gutter
PLAN_COLORS = [
    ("A", "#FF5555"),  # Red
    ("B", "#50FA7B"),  # Green
    ("C", "#8BE9FD"),  # Cyan
    ("D", "#FFB86C"),  # Orange
    ("E", "#BD93F9"),  # Purple
]


@dataclass
class _DisplayLine:
    """One rendered line in the display."""
    main_lineno: int | None
    other_lineno: int | None
    tag: str
    content: str
    source_plan: str = ""


class DiffDisplay(VerticalScroll):
    """Widget that renders diff hunks with color coding and keyboard navigation."""

    class CursorMoved(Message):
        """Posted when the cursor line changes."""

        def __init__(self, line: int, total: int) -> None:
            super().__init__()
            self.line = line
            self.total = total

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("pageup", "page_up", "Page Up", show=False),
        Binding("pagedown", "page_down", "Page Down", show=False),
        Binding("home", "cursor_home", "Home", show=False),
        Binding("end", "cursor_end", "End", show=False),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._diff: PairwiseDiff | None = None
        self._multi_diff: MultiDiffResult | None = None
        self._cursor_line: int = 0
        self._flat_lines: list[_DisplayLine] = []
        self._active_comparison_idx: int = 0

    def compose(self):
        yield Static("No diff loaded", id="diff_display")

    # -- Loading API ----------------------------------------------------------

    def load_diff(self, diff: PairwiseDiff) -> None:
        """Load a pairwise diff and render it."""
        self._diff = diff
        self._multi_diff = None
        self._flat_lines = _flatten_hunks(diff.hunks)
        self._cursor_line = 0

        if not self._flat_lines or _all_equal(self._flat_lines):
            self._show_message("No differences found between the plans.")
            return

        self._render_diff()
        self.scroll_home(animate=False)

    def load_multi_diff(self, result: MultiDiffResult, active_idx: int = 0) -> None:
        """Load a multi-diff result, displaying one comparison at a time."""
        self._multi_diff = result
        self._active_comparison_idx = active_idx
        if result.comparisons:
            self._diff = result.comparisons[active_idx]
            self._flat_lines = _flatten_hunks(self._diff.hunks)
        else:
            self._diff = None
            self._flat_lines = []
        self._cursor_line = 0

        if not self._flat_lines or _all_equal(self._flat_lines):
            self._show_message("No differences found between the plans.")
            return

        self._render_diff()
        self.scroll_home(animate=False)

    def set_active_comparison(self, idx: int) -> None:
        """Switch which comparison is displayed without recomputing diffs."""
        if self._multi_diff is None:
            return
        if idx < 0 or idx >= len(self._multi_diff.comparisons):
            return
        self._active_comparison_idx = idx
        self._diff = self._multi_diff.comparisons[idx]
        self._flat_lines = _flatten_hunks(self._diff.hunks)
        self._cursor_line = 0

        if not self._flat_lines or _all_equal(self._flat_lines):
            self._show_message("No differences found between the plans.")
            return

        self._render_diff()
        self.scroll_home(animate=False)

    # -- Rendering ------------------------------------------------------------

    def _show_message(self, message: str) -> None:
        """Show a centered placeholder message."""
        self._flat_lines = []
        self.query_one("#diff_display", Static).update(
            Text(message, style="dim italic")
        )

    def _render_diff(self) -> None:
        """Build and render the diff table from flattened lines."""
        LINENO_WIDTH = 5
        GUTTER_WIDTH = 1
        available = self.size.width if self.size.width > 0 else 120
        content_width = max(20, available - LINENO_WIDTH * 2 - GUTTER_WIDTH - 4)

        table = Table(
            show_header=False,
            show_edge=False,
            box=None,
            pad_edge=False,
        )
        table.add_column(
            style="dim", justify="right", width=LINENO_WIDTH, no_wrap=True,
        )
        table.add_column(
            style="dim", justify="right", width=LINENO_WIDTH, no_wrap=True,
        )
        table.add_column(width=GUTTER_WIDTH, no_wrap=True)
        table.add_column(no_wrap=True, width=content_width)

        use_plan_gutter = (
            self._multi_diff is not None
            and len(self._multi_diff.comparisons) > 1
        )

        for idx, dl in enumerate(self._flat_lines):
            tag_style = TAG_STYLES.get(dl.tag, Style())

            # Line numbers
            main_num = Text(str(dl.main_lineno), style="dim") if dl.main_lineno is not None else Text("")
            other_num = Text(str(dl.other_lineno), style="dim") if dl.other_lineno is not None else Text("")

            # Gutter
            if use_plan_gutter and dl.tag != "equal":
                plan_idx = min(self._active_comparison_idx, len(PLAN_COLORS) - 1)
                letter, color = PLAN_COLORS[plan_idx]
                gutter = Text(letter, style=Style(color=color, bold=True))
            else:
                gutter_char = TAG_GUTTERS.get(dl.tag, " ")
                gutter = Text(gutter_char, style=tag_style)

            # Content
            content = Text(dl.content)
            content.stylize(tag_style)

            # Row style: cursor highlight
            row_style = CURSOR_STYLE if idx == self._cursor_line else None

            table.add_row(main_num, other_num, gutter, content, style=row_style)

        self.query_one("#diff_display", Static).update(table)

    # -- Keyboard navigation --------------------------------------------------

    def _move_cursor(self, line: int) -> None:
        """Move cursor to the given 0-indexed line."""
        if not self._flat_lines:
            return
        line = max(0, min(line, len(self._flat_lines) - 1))
        self._cursor_line = line
        self._render_diff()
        self._scroll_cursor_visible()
        self.post_message(self.CursorMoved(line + 1, len(self._flat_lines)))

    def _scroll_cursor_visible(self) -> None:
        """Scroll to keep the cursor line visible."""
        margin = 2
        top = self.scroll_y
        bottom = top + self.size.height - 1
        if self._cursor_line < top + margin:
            self.scroll_to(y=max(0, self._cursor_line - margin), animate=False)
        elif self._cursor_line > bottom - margin:
            self.scroll_to(
                y=self._cursor_line - self.size.height + 1 + margin, animate=False,
            )

    def action_cursor_up(self) -> None:
        self._move_cursor(self._cursor_line - 1)

    def action_cursor_down(self) -> None:
        self._move_cursor(self._cursor_line + 1)

    def action_page_up(self) -> None:
        self._move_cursor(self._cursor_line - max(1, self.size.height - 2))

    def action_page_down(self) -> None:
        self._move_cursor(self._cursor_line + max(1, self.size.height - 2))

    def action_cursor_home(self) -> None:
        self._move_cursor(0)

    def action_cursor_end(self) -> None:
        self._move_cursor(len(self._flat_lines) - 1)

    def on_resize(self, event) -> None:
        """Rebuild display when widget size changes."""
        if self._flat_lines:
            self._render_diff()


# -- Helpers (module-level) ---------------------------------------------------

def _flatten_hunks(hunks: list[DiffHunk]) -> list[_DisplayLine]:
    """Convert a list of DiffHunks into a flat list of display lines."""
    lines: list[_DisplayLine] = []

    for hunk in hunks:
        tag = hunk.tag
        m_start = hunk.main_range[0]
        o_start = hunk.other_range[0]
        source = hunk.source_plans[0] if hunk.source_plans else ""

        if tag == "equal":
            for i, text in enumerate(hunk.main_lines):
                lines.append(_DisplayLine(
                    main_lineno=m_start + i + 1,
                    other_lineno=o_start + i + 1,
                    tag="equal",
                    content=text,
                    source_plan=source,
                ))

        elif tag == "insert":
            for i, text in enumerate(hunk.other_lines):
                lines.append(_DisplayLine(
                    main_lineno=None,
                    other_lineno=o_start + i + 1,
                    tag="insert",
                    content=text,
                    source_plan=source,
                ))

        elif tag == "delete":
            for i, text in enumerate(hunk.main_lines):
                lines.append(_DisplayLine(
                    main_lineno=m_start + i + 1,
                    other_lineno=None,
                    tag="delete",
                    content=text,
                    source_plan=source,
                ))

        elif tag == "replace":
            # Show deleted lines from main, then inserted lines from other
            for i, text in enumerate(hunk.main_lines):
                lines.append(_DisplayLine(
                    main_lineno=m_start + i + 1,
                    other_lineno=None,
                    tag="delete",
                    content=text,
                    source_plan=source,
                ))
            for i, text in enumerate(hunk.other_lines):
                lines.append(_DisplayLine(
                    main_lineno=None,
                    other_lineno=o_start + i + 1,
                    tag="insert",
                    content=text,
                    source_plan=source,
                ))

        elif tag == "moved":
            for i, text in enumerate(hunk.other_lines):
                lines.append(_DisplayLine(
                    main_lineno=m_start + i + 1 if i < len(hunk.main_lines) else None,
                    other_lineno=o_start + i + 1,
                    tag="moved",
                    content=text,
                    source_plan=source,
                ))

    return lines


def _all_equal(lines: list[_DisplayLine]) -> bool:
    """Check if all display lines are 'equal' (no actual differences)."""
    return all(dl.tag == "equal" for dl in lines)
