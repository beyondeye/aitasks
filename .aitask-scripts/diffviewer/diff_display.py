"""Diff display widget with color coding, line numbers, and keyboard navigation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Static

from rich.style import Style
from rich.table import Table
from rich.text import Text

from .diff_engine import DiffHunk, PairwiseDiff, MultiDiffResult


# Styles per diff tag — dim backgrounds for readability, light foreground text
TAG_STYLES = {
    "equal": Style(dim=True),
    "insert": Style(color="#d0d0d0", bgcolor="#264d26"),
    "delete": Style(color="#d0d0d0", bgcolor="#4d2626"),
    "replace": Style(color="#d0d0d0", bgcolor="#4d3826"),
    "moved": Style(color="#d0d0d0", bgcolor="#263a4d"),
    # Dimmed variants for matching words in word-level diff lines
    "insert_dim": Style(color="#a0a0a0", bgcolor="#152a15"),
    "delete_dim": Style(color="#a0a0a0", bgcolor="#2a1515"),
    "replace_dim": Style(color="#a0a0a0", bgcolor="#2a1f15"),
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

# Markdown syntax highlighting styles — themable dict, same pattern as TAG_STYLES
MD_STYLES = {
    "h1": Style(bold=True, color="#BD93F9"),
    "h2": Style(bold=True, color="#8BE9FD"),
    "h3": Style(bold=True, color="#50FA7B"),
    "h4": Style(bold=True, color="#FFB86C"),
    "h5": Style(bold=True, color="#FF79C6"),
    "h6": Style(bold=True, color="#6272A4"),
    "bold": Style(bold=True),
    "italic": Style(italic=True),
    "code": Style(color="#F1FA8C"),
    "bullet": Style(bold=True, color="#FF79C6"),
}

# Compiled markdown regex patterns
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s")
_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_MD_CODE_RE = re.compile(r"`([^`]+)`")
_MD_LIST_RE = re.compile(r"^(\s*)([-*])\s")
_MD_OLIST_RE = re.compile(r"^(\s*)(\d+\.)\s")


def _highlight_md_line(line: str) -> Text:
    """Apply inline markdown syntax highlighting to a line.

    Returns a Rich Text object with markdown-level styles applied.
    All styles are looked up from MD_STYLES for easy theming.
    """
    text = Text(line)

    # Headings — style the whole line, early return
    m = _MD_HEADING_RE.match(line)
    if m:
        level = len(m.group(1))
        style = MD_STYLES.get(f"h{level}", MD_STYLES["h6"])
        text.stylize(style)
        return text

    # Bold: **text**
    for m in _MD_BOLD_RE.finditer(line):
        text.stylize(MD_STYLES["bold"], m.start(), m.end())

    # Italic: *text* (not preceded/followed by *)
    for m in _MD_ITALIC_RE.finditer(line):
        text.stylize(MD_STYLES["italic"], m.start(), m.end())

    # Inline code: `text`
    for m in _MD_CODE_RE.finditer(line):
        text.stylize(MD_STYLES["code"], m.start(), m.end())

    # List bullets (unordered)
    m = _MD_LIST_RE.match(line)
    if m:
        text.stylize(MD_STYLES["bullet"], m.start(2), m.end(2))
    else:
        # Ordered list numbers
        m = _MD_OLIST_RE.match(line)
        if m:
            text.stylize(MD_STYLES["bullet"], m.start(2), m.end(2))

    return text


def _word_diff_texts(
    main_line: str,
    other_line: str,
    main_style: Style,
    other_style: Style,
    main_dim_style: Style | None = None,
    other_dim_style: Style | None = None,
) -> tuple[Text, Text]:
    """Return styled Text objects with word-level diff highlighting.

    Tokenizes by whitespace-delimited words, then diffs the word lists.
    Matching words get the dim style (dimmed background variant);
    differing words get their respective full tag style.
    """
    from difflib import SequenceMatcher

    main_text = _highlight_md_line(main_line)
    other_text = _highlight_md_line(other_line)

    # Apply dim background to entire line first (matching words keep this)
    m_dim = main_dim_style if main_dim_style is not None else Style(dim=True)
    o_dim = other_dim_style if other_dim_style is not None else Style(dim=True)
    main_text.stylize(m_dim)
    other_text.stylize(o_dim)

    # Tokenize into words with character positions
    main_words = [(m.group(), m.start(), m.end()) for m in re.finditer(r"\S+", main_line)]
    other_words = [(m.group(), m.start(), m.end()) for m in re.finditer(r"\S+", other_line)]

    main_strs = [w[0] for w in main_words]
    other_strs = [w[0] for w in other_words]

    sm = SequenceMatcher(None, main_strs, other_strs, autojunk=False)
    for op, m_start, m_end, o_start, o_end in sm.get_opcodes():
        if op != "equal":
            if m_start < m_end:
                char_start = main_words[m_start][1]
                char_end = main_words[m_end - 1][2]
                main_text.stylize(main_style, char_start, char_end)
            if o_start < o_end:
                char_start = other_words[o_start][1]
                char_end = other_words[o_end - 1][2]
                other_text.stylize(other_style, char_start, char_end)

    return main_text, other_text

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
    replace_partner: str | None = None


@dataclass
class _SideBySideLine:
    """One row in the side-by-side display, pairing left and right content."""
    main_lineno: int | None
    main_content: str
    other_lineno: int | None
    other_content: str
    tag: str
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
        self._sbs_lines: list[_SideBySideLine] = []
        self._side_by_side: bool = False
        self._active_comparison_idx: int = 0
        self._main_label: str = ""
        self._other_label: str = ""

    def compose(self):
        yield Static("No diff loaded", id="diff_display")

    # -- Loading API ----------------------------------------------------------

    def load_diff(self, diff: PairwiseDiff) -> None:
        """Load a pairwise diff and render it."""
        import os
        self._diff = diff
        self._multi_diff = None
        self._flat_lines = _flatten_hunks(diff.hunks)
        self._sbs_lines = _flatten_hunks_side_by_side(diff.hunks)
        self._main_label = os.path.basename(diff.main_path)
        self._other_label = os.path.basename(diff.other_path)
        self._cursor_line = 0

        if not self._flat_lines or _all_equal(self._flat_lines):
            self._show_message("No differences found between the plans.")
            return

        self._render_diff()
        self.scroll_home(animate=False)

    def load_multi_diff(self, result: MultiDiffResult, active_idx: int = 0) -> None:
        """Load a multi-diff result, displaying one comparison at a time."""
        import os
        self._multi_diff = result
        self._active_comparison_idx = active_idx
        if result.comparisons:
            self._diff = result.comparisons[active_idx]
            self._flat_lines = _flatten_hunks(self._diff.hunks)
            self._sbs_lines = _flatten_hunks_side_by_side(self._diff.hunks)
            self._main_label = os.path.basename(result.main_path)
            self._other_label = os.path.basename(self._diff.other_path)
        else:
            self._diff = None
            self._flat_lines = []
            self._sbs_lines = []
        self._cursor_line = 0

        if not self._flat_lines or _all_equal(self._flat_lines):
            self._show_message("No differences found between the plans.")
            return

        self._render_diff()
        self.scroll_home(animate=False)

    def set_active_comparison(self, idx: int) -> None:
        """Switch which comparison is displayed without recomputing diffs."""
        import os
        if self._multi_diff is None:
            return
        if idx < 0 or idx >= len(self._multi_diff.comparisons):
            return
        self._active_comparison_idx = idx
        self._diff = self._multi_diff.comparisons[idx]
        self._flat_lines = _flatten_hunks(self._diff.hunks)
        self._sbs_lines = _flatten_hunks_side_by_side(self._diff.hunks)
        self._other_label = os.path.basename(self._diff.other_path)
        self._cursor_line = 0

        if not self._flat_lines or _all_equal(self._flat_lines):
            self._show_message("No differences found between the plans.")
            return

        self._render_diff()
        self.scroll_home(animate=False)

    def set_layout(self, side_by_side: bool) -> None:
        """Switch between interleaved and side-by-side layout."""
        if self._side_by_side == side_by_side:
            return

        # Capture reference line number from first visible line
        target_lineno = None
        visible_idx = max(0, int(self.scroll_y))
        if self._side_by_side:
            if visible_idx < len(self._sbs_lines):
                sbl = self._sbs_lines[visible_idx]
                target_lineno = sbl.main_lineno or sbl.other_lineno
        else:
            if visible_idx < len(self._flat_lines):
                dl = self._flat_lines[visible_idx]
                target_lineno = dl.main_lineno or dl.other_lineno

        self._side_by_side = side_by_side

        # Find equivalent position in new layout
        new_pos = 0
        if target_lineno is not None:
            if self._side_by_side:
                for i, sbl in enumerate(self._sbs_lines):
                    lineno = sbl.main_lineno or sbl.other_lineno
                    if lineno is not None and lineno >= target_lineno:
                        new_pos = i
                        break
            else:
                for i, dl in enumerate(self._flat_lines):
                    lineno = dl.main_lineno or dl.other_lineno
                    if lineno is not None and lineno >= target_lineno:
                        new_pos = i
                        break

        self._cursor_line = new_pos
        if self._active_lines_count() > 0:
            self._render_diff()
            self.scroll_to(y=new_pos, animate=False)

    def _active_lines_count(self) -> int:
        """Number of lines in current layout mode."""
        return len(self._sbs_lines) if self._side_by_side else len(self._flat_lines)

    # -- Rendering ------------------------------------------------------------

    def _show_message(self, message: str) -> None:
        """Show a centered placeholder message."""
        self._flat_lines = []
        self._sbs_lines = []
        self.query_one("#diff_display", Static).update(
            Text(message, style="dim italic")
        )

    def _render_diff(self) -> None:
        """Build and render the diff table from flattened lines."""
        if self._side_by_side:
            self._render_side_by_side()
        else:
            self._render_interleaved()

    def _render_interleaved(self) -> None:
        """Build and render the interleaved diff table."""
        LINENO_WIDTH = 5
        GUTTER_WIDTH = 1
        available = self.size.width if self.size.width > 0 else 120
        content_width = max(20, available - LINENO_WIDTH * 2 - GUTTER_WIDTH - 4)

        table = Table(
            show_header=False,
            show_edge=False,
            box=None,
            pad_edge=False,
            padding=0,
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

            # Gutter — plan label only for other-file lines (insert/moved),
            # not for main-file lines (delete) or unchanged lines (equal)
            if use_plan_gutter and dl.tag in ("insert", "moved"):
                plan_idx = min(self._active_comparison_idx, len(PLAN_COLORS) - 1)
                letter, color = PLAN_COLORS[plan_idx]
                gutter = Text(letter, style=Style(color=color, bold=True))
            elif use_plan_gutter and dl.tag == "delete":
                # Main-file line in diff context — show "M" for main
                gutter = Text("M", style=Style(dim=True))
            else:
                gutter_char = TAG_GUTTERS.get(dl.tag, " ")
                gutter = Text(gutter_char, style=tag_style)

            # Content — word-level diff for replace partners
            if dl.replace_partner is not None:
                if dl.tag == "delete":
                    content, _ = _word_diff_texts(
                        dl.content, dl.replace_partner,
                        TAG_STYLES["delete"], TAG_STYLES["insert"],
                        TAG_STYLES["delete_dim"], TAG_STYLES["insert_dim"],
                    )
                else:  # insert
                    _, content = _word_diff_texts(
                        dl.replace_partner, dl.content,
                        TAG_STYLES["delete"], TAG_STYLES["insert"],
                        TAG_STYLES["delete_dim"], TAG_STYLES["insert_dim"],
                    )
            else:
                # Use a space for empty lines so background color renders
                content = _highlight_md_line(dl.content or " ")
                content.stylize(tag_style)

            # Row style: cursor highlight
            row_style = CURSOR_STYLE if idx == self._cursor_line else None

            table.add_row(main_num, other_num, gutter, content, style=row_style)

        self.query_one("#diff_display", Static).update(table)

    def _render_side_by_side(self) -> None:
        """Build and render the side-by-side diff table."""
        LINENO_WIDTH = 5
        GUTTER_WIDTH = 3
        available = self.size.width if self.size.width > 0 else 120
        content_each = max(10, (available - LINENO_WIDTH * 2 - GUTTER_WIDTH - 4) // 2)

        show_headers = bool(self._main_label or self._other_label)
        table = Table(
            show_header=show_headers,
            show_edge=False,
            box=None,
            pad_edge=False,
            padding=0,
            header_style="bold",
        )
        # Left side: main
        table.add_column(header="", style="dim", justify="right", width=LINENO_WIDTH, no_wrap=True)
        table.add_column(header=self._main_label, no_wrap=True, width=content_each)
        # Center gutter
        table.add_column(header="", width=GUTTER_WIDTH, no_wrap=True)
        # Right side: other
        table.add_column(header="", style="dim", justify="right", width=LINENO_WIDTH, no_wrap=True)
        table.add_column(header=self._other_label, no_wrap=True, width=content_each)

        use_plan_gutter = (
            self._multi_diff is not None
            and len(self._multi_diff.comparisons) > 1
        )

        for idx, sbl in enumerate(self._sbs_lines):
            tag_style = TAG_STYLES.get(sbl.tag, Style())

            # Left line number
            main_num = (
                Text(str(sbl.main_lineno), style="dim")
                if sbl.main_lineno is not None else Text("")
            )

            # Left and right content — word-level diff for replace rows
            if sbl.tag == "replace" and sbl.main_content and sbl.other_content:
                replace_dim = TAG_STYLES.get("replace_dim", Style(dim=True))
                main_text, other_text = _word_diff_texts(
                    sbl.main_content, sbl.other_content,
                    tag_style, tag_style,
                    replace_dim, replace_dim,
                )
            else:
                # Left content — use space for empty lines so background renders
                main_text = _highlight_md_line(sbl.main_content or " ")
                if sbl.tag in ("delete", "replace", "moved"):
                    main_text.stylize(tag_style)
                elif sbl.tag == "equal":
                    main_text.stylize(TAG_STYLES["equal"])

                # Right content — use space for empty lines so background renders
                other_text = _highlight_md_line(sbl.other_content or " ")
                if sbl.tag in ("insert", "replace", "moved"):
                    other_text.stylize(tag_style)
                elif sbl.tag == "equal":
                    other_text.stylize(TAG_STYLES["equal"])

            # Gutter — in side-by-side both columns are visible,
            # so show plan label for all non-equal lines
            if use_plan_gutter and sbl.tag != "equal":
                plan_idx = min(self._active_comparison_idx, len(PLAN_COLORS) - 1)
                letter, color = PLAN_COLORS[plan_idx]
                gutter = Text(f" {letter} ", style=Style(color=color, bold=True))
            else:
                gutter_char = TAG_GUTTERS.get(sbl.tag, " ")
                gutter = Text(f" {gutter_char} ", style=tag_style)

            # Right line number
            other_num = (
                Text(str(sbl.other_lineno), style="dim")
                if sbl.other_lineno is not None else Text("")
            )

            # Cursor highlight
            row_style = CURSOR_STYLE if idx == self._cursor_line else None

            table.add_row(main_num, main_text, gutter, other_num, other_text, style=row_style)

        self.query_one("#diff_display", Static).update(table)

    # -- Keyboard navigation --------------------------------------------------

    def _move_cursor(self, line: int) -> None:
        """Move cursor to the given 0-indexed line."""
        count = self._active_lines_count()
        if count == 0:
            return
        line = max(0, min(line, count - 1))
        self._cursor_line = line
        self._render_diff()
        self._scroll_cursor_visible()
        self.post_message(self.CursorMoved(line + 1, count))

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
        self._move_cursor(self._active_lines_count() - 1)

    def on_resize(self, event) -> None:
        """Rebuild display when widget size changes."""
        if self._active_lines_count() > 0:
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
            # Pair main/other lines row-by-row for word-level diff
            for i, text in enumerate(hunk.main_lines):
                partner = hunk.other_lines[i] if i < len(hunk.other_lines) else None
                lines.append(_DisplayLine(
                    main_lineno=m_start + i + 1,
                    other_lineno=None,
                    tag="delete",
                    content=text,
                    source_plan=source,
                    replace_partner=partner,
                ))
            for i, text in enumerate(hunk.other_lines):
                partner = hunk.main_lines[i] if i < len(hunk.main_lines) else None
                lines.append(_DisplayLine(
                    main_lineno=None,
                    other_lineno=o_start + i + 1,
                    tag="insert",
                    content=text,
                    source_plan=source,
                    replace_partner=partner,
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


def _flatten_hunks_side_by_side(hunks: list[DiffHunk]) -> list[_SideBySideLine]:
    """Convert DiffHunks into side-by-side aligned rows."""
    rows: list[_SideBySideLine] = []

    for hunk in hunks:
        tag = hunk.tag
        m_start = hunk.main_range[0]
        o_start = hunk.other_range[0]
        source = hunk.source_plans[0] if hunk.source_plans else ""

        if tag == "equal":
            for i, text in enumerate(hunk.main_lines):
                other_text = hunk.other_lines[i] if i < len(hunk.other_lines) else ""
                rows.append(_SideBySideLine(
                    main_lineno=m_start + i + 1,
                    main_content=text,
                    other_lineno=o_start + i + 1,
                    other_content=other_text,
                    tag="equal",
                    source_plan=source,
                ))

        elif tag == "insert":
            for i, text in enumerate(hunk.other_lines):
                rows.append(_SideBySideLine(
                    main_lineno=None,
                    main_content="",
                    other_lineno=o_start + i + 1,
                    other_content=text,
                    tag="insert",
                    source_plan=source,
                ))

        elif tag == "delete":
            for i, text in enumerate(hunk.main_lines):
                rows.append(_SideBySideLine(
                    main_lineno=m_start + i + 1,
                    main_content=text,
                    other_lineno=None,
                    other_content="",
                    tag="delete",
                    source_plan=source,
                ))

        elif tag == "replace":
            max_len = max(len(hunk.main_lines), len(hunk.other_lines))
            for i in range(max_len):
                has_main = i < len(hunk.main_lines)
                has_other = i < len(hunk.other_lines)
                rows.append(_SideBySideLine(
                    main_lineno=(m_start + i + 1) if has_main else None,
                    main_content=hunk.main_lines[i] if has_main else "",
                    other_lineno=(o_start + i + 1) if has_other else None,
                    other_content=hunk.other_lines[i] if has_other else "",
                    tag="replace",
                    source_plan=source,
                ))

        elif tag == "moved":
            max_len = max(len(hunk.main_lines), len(hunk.other_lines))
            for i in range(max_len):
                has_main = i < len(hunk.main_lines)
                has_other = i < len(hunk.other_lines)
                rows.append(_SideBySideLine(
                    main_lineno=(m_start + i + 1) if has_main else None,
                    main_content=hunk.main_lines[i] if has_main else "",
                    other_lineno=(o_start + i + 1) if has_other else None,
                    other_content=hunk.other_lines[i] if has_other else "",
                    tag="moved",
                    source_plan=source,
                ))

    return rows
