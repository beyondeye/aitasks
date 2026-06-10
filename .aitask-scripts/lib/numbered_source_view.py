"""Shared base widget for reflow-stable, syntax-highlighted, line-numbered views.

Extracted (t959) from the two near-identical implementations that grew up
independently:

- codebrowser ``CodeViewer`` (``.aitask-scripts/codebrowser/code_viewer.py``) —
  the full source viewer with an annotation gutter, viewport windowing,
  cursor/selection, and a wrap/truncate toggle.
- brainstorm ``_NumberedProposal`` (``.aitask-scripts/brainstorm/brainstorm_app.py``,
  added in t954) — the Actions-tab numbered proposal preview.

Both render a boxless Rich ``Table`` with a right-justified ``no_wrap``
line-number column beside a content column, **one source line per table row** so
the line number stays anchored even when a long line wraps across several
terminal rows (numbers track *source* lines, not wrapped rows). The highlight is
computed once and cached per line; ``on_resize`` only re-lays out the table
width.

This base owns that shared idiom and exposes override hooks for the points where
the two diverge (lexer, per-row styling, an optional extra column, the rendered
line range + indicator rows, and wrap-vs-truncate). The **defaults reproduce
``_NumberedProposal``'s behavior exactly** (markdown lexer, always-wrap, full
range, two columns, no per-row style), so the brainstorm side is a near-empty
subclass while ``CodeViewer`` overrides the hooks it needs.

Dependencies are limited to ``textual`` + ``rich`` + stdlib (no codebrowser or
brainstorm imports) so the module imports cleanly under both PyPy (codebrowser's
fast path) and CPython (brainstorm).
"""

from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text


class NumberedSourceView(VerticalScroll):
    """Reflow-stable, syntax-highlighted, line-numbered source view.

    Renders ``self._lines`` (cached highlighted per-line ``Text``) as a boxless
    table: a fixed-width right-justified line-number column plus a content
    column, one row per source line. Subclasses customize behavior via the hook
    methods below; the defaults match the brainstorm numbered-proposal preview.
    """

    LINE_NUM_WIDTH = 5
    # Inner Static id — overridden per host so existing CSS selectors keep
    # matching (codebrowser targets ``#code_display``; brainstorm targets
    # ``#preview_numbered_inner``).
    _INNER_ID = "numbered_source_inner"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._text = ""
        self._lines: list[Text] = []  # cached highlighted per-line Text
        self._table = None  # last built Table (one row per source line)
        self._build_start = 0  # render-range start of the last build

    def compose(self) -> ComposeResult:
        yield Static(self._placeholder(), id=self._INNER_ID)

    def _inner_static(self) -> Static:
        return self.query_one(f"#{self._INNER_ID}", Static)

    # ---- hooks (override points; defaults == _NumberedProposal behavior) ----

    def _placeholder(self) -> str:
        """Initial Static content before any text is loaded."""
        return ""

    def _select_lexer(self, code: str) -> str:
        """Pygments lexer name for highlighting. Default: markdown."""
        return "markdown"

    def _wrap(self) -> bool:
        """True → content column wraps; False → truncate via ``_truncate_line``."""
        return True

    def _render_range(self) -> tuple[int, int]:
        """Half-open ``[start, end)`` 0-indexed range of source lines to render."""
        return 0, len(self._lines)

    def _has_extra_column(self) -> bool:
        """Whether to add a third column (e.g. codebrowser's annotation gutter)."""
        return False

    def _extra_column_width(self) -> int:
        """Width of the optional third column (0 → present but collapsed)."""
        return 0

    def _extra_cell(self, file_idx: int) -> Text:
        """Content for the optional third column at a given source line."""
        return Text("")

    def _row_style(self, file_idx: int):
        """Per-row Rich ``Style`` (e.g. cursor / selection), or None."""
        return None

    def _truncate_line(self, line: Text, code_max_width: int) -> Text:
        """Transform a line when not wrapping. Default: unchanged."""
        return line

    def _prepare_build(self, start: int, end: int) -> None:
        """Precompute per-build state (e.g. the annotation gutter) before the row loop."""

    def _pre_rows(self, table: Table, start: int, end: int) -> None:
        """Add rows before the data rows (e.g. a 'N lines above' indicator)."""

    def _post_rows(self, table: Table, start: int, end: int) -> None:
        """Add rows after the data rows (e.g. a 'N lines below' indicator)."""

    def _rebuild_log_detail(self) -> str:
        """Detail string for the slow-rebuild perf log."""
        return f"{len(self._lines)} lines"

    # ---- core ----

    def _highlight(self, text: str) -> list[Text]:
        """Syntax-highlight *text* and split into one ``Text`` per source line.

        ``Syntax.highlight`` drops the empty trailing line after a final newline
        (conventional line count), so the result length matches the source line
        count.
        """
        lexer = self._select_lexer(text)
        return Syntax(text, lexer, theme="monokai").highlight(text).split("\n")

    def set_text(self, text: str) -> None:
        """Load *text*, (re)highlight it, and rebuild the table."""
        self._text = text or ""
        self._lines = self._highlight(self._text)
        self._rebuild_display()

    def _content_width(self) -> int:
        """Available width for the content column after the gutter columns."""
        available = self.size.width if self.size.width > 0 else 120
        extra = self._extra_column_width() if self._has_extra_column() else 0
        return max(20, available - self.LINE_NUM_WIDTH - extra - 2)

    def _rebuild_display(self) -> None:
        """Build and render the line-number + content (+ optional extra) table."""
        t0 = time.perf_counter()

        start, end = self._render_range()
        self._build_start = start
        self._prepare_build(start, end)

        code_w = self._content_width()
        table = Table(
            show_header=False,
            show_edge=False,
            box=None,
            pad_edge=False,
        )
        table.add_column(
            style="dim", justify="right", width=self.LINE_NUM_WIDTH, no_wrap=True
        )
        table.add_column(no_wrap=not self._wrap(), width=code_w)
        if self._has_extra_column():
            table.add_column(
                width=self._extra_column_width(), no_wrap=True, justify="left"
            )

        self._pre_rows(table, start, end)
        for file_idx in range(start, end):
            line = self._lines[file_idx]
            if not self._wrap():
                line = self._truncate_line(line, code_w)
            cells = [Text(str(file_idx + 1), style="dim"), line]
            if self._has_extra_column():
                cells.append(self._extra_cell(file_idx))
            table.add_row(*cells, style=self._row_style(file_idx))
        self._post_rows(table, start, end)

        self._table = table
        self._inner_static().update(table)

        elapsed = time.perf_counter() - t0
        if elapsed > 0.05:
            self.log(
                f"_rebuild_display: {elapsed*1000:.1f}ms ({self._rebuild_log_detail()})"
            )

    def on_resize(self, event) -> None:
        """Rebuild when the widget resizes so column widths adapt."""
        if self._lines:
            self._rebuild_display()
