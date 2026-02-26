"""Code viewer widget with syntax highlighting, line numbers, and annotation gutter."""

import time
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
        Binding("pagedown", "page_down", "Page down", show=False),
        Binding("pageup", "page_up", "Page up", show=False),
    ]

    MAX_LINE_WIDTH = 500

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
        self._edge_scroll_timer = None
        self._edge_scroll_direction: int = 0  # +1 down, -1 up, 0 none
        # Viewport windowing (for large files)
        self._viewport_mode: bool = False
        self._viewport_start: int = 0
        self._viewport_size: int = 200
        self._viewport_threshold: int = 2000
        self._viewport_margin: int = 30

    def compose(self):
        yield Static("Select a file to view", id="code_display")

    def _reset_state(self) -> None:
        """Reset viewer state for a new file load."""
        self._annotations = []
        self._cursor_line = 0
        self._selection_start = None
        self._selection_end = None
        self._selection_active = False
        self._viewport_mode = False
        self._viewport_start = 0

    def _show_message(self, message: str) -> None:
        """Show a placeholder message instead of code content."""
        self._lines = []
        self._total_lines = 0
        self._highlighted_lines = []
        self._reset_state()
        self.query_one("#code_display", Static).update(message)

    def load_file(self, file_path: Path) -> None:
        """Load and display a file with syntax highlighting."""
        self._file_path = file_path

        # Read file — detect binary content
        try:
            content = file_path.read_text()
        except UnicodeDecodeError:
            self._show_message("Binary file — cannot display")
            return
        except OSError as e:
            self._show_message(f"Error reading file: {e}")
            return

        if "\x00" in content:
            self._show_message("Binary file — cannot display")
            return

        # Empty file
        if not content:
            self._show_message("(empty file)")
            return

        # Normalize tabs to spaces
        content = content.expandtabs(4)

        self._lines = content.splitlines()
        self._total_lines = len(self._lines)
        self._reset_state()
        self._viewport_mode = self._total_lines > self._viewport_threshold

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

    def _ensure_viewport_contains_cursor(self) -> bool:
        """Shift viewport window so the cursor stays within the margin.

        Returns True if the viewport was moved (caller should rebuild display).
        """
        if not self._viewport_mode:
            return False
        old_start = self._viewport_start
        if self._cursor_line < self._viewport_start + self._viewport_margin:
            self._viewport_start = max(0, self._cursor_line - self._viewport_margin)
        elif self._cursor_line >= self._viewport_start + self._viewport_size - self._viewport_margin:
            self._viewport_start = min(
                max(0, self._total_lines - self._viewport_size),
                self._cursor_line - self._viewport_size + self._viewport_margin + 1,
            )
        self._viewport_start = max(0, self._viewport_start)
        return self._viewport_start != old_start

    @property
    def viewport_info(self) -> str:
        """Return viewport position string for the info bar, or empty string."""
        if not self._viewport_mode:
            return ""
        vp_end = min(self._viewport_start + self._viewport_size, self._total_lines)
        return f"(viewport {self._viewport_start + 1}\u2013{vp_end})"

    def _build_annotation_gutter(
        self, vp_start: int = 0, vp_end: int | None = None,
    ) -> list[Text]:
        """Build per-line annotation text from AnnotationRange data.

        When *vp_start*/*vp_end* are given the returned list covers only
        lines ``[vp_start, vp_end)`` (0-indexed).
        """
        if vp_end is None:
            vp_end = len(self._highlighted_lines)
        size = vp_end - vp_start

        # Build task_id -> color_index lookup for deterministic unique colors
        unique_task_ids: set[str] = set()
        for ann in self._annotations:
            unique_task_ids.update(ann.task_ids)
        task_color = {
            tid: i % len(ANNOTATION_COLORS)
            for i, tid in enumerate(sorted(unique_task_ids))
        }

        gutter = [Text("") for _ in range(size)]
        for ann in self._annotations:
            label = ",".join(f"t{tid}" for tid in ann.task_ids)
            color = ANNOTATION_COLORS[
                task_color[ann.task_ids[0]]
            ] if ann.task_ids else "dim"
            for line_num in range(ann.start_line, ann.end_line + 1):
                idx = line_num - 1  # 0-indexed file line
                if vp_start <= idx < vp_end:
                    gutter[idx - vp_start] = Text(label, style=color)
        return gutter

    def _annotation_col_width(self) -> int:
        """Return annotation column width, adjusted for narrow terminals."""
        try:
            app_width = self.app.size.width
        except Exception:
            return 12
        if app_width < 80:
            return 10
        return 12

    def _rebuild_display(self) -> None:
        """Build and render the line-number + code + annotation table."""
        t0 = time.perf_counter()

        # Calculate column widths dynamically based on available space
        LINE_NUM_WIDTH = 5
        available = self.size.width if self.size.width > 0 else 120
        show_ann = self._show_annotations and self._annotations
        ann_width = self._annotation_col_width() if show_ann else 0
        code_max_width = max(20, available - LINE_NUM_WIDTH - ann_width - 2)

        table = Table(
            show_header=False,
            show_edge=False,
            box=None,
            pad_edge=False,
        )
        table.add_column(style="dim", justify="right", width=LINE_NUM_WIDTH, no_wrap=True)
        table.add_column(no_wrap=True, width=code_max_width)
        table.add_column(width=ann_width, no_wrap=True, justify="left")

        # Determine line range to render
        if self._viewport_mode:
            vp_start = self._viewport_start
            vp_end = min(vp_start + self._viewport_size, self._total_lines)
        else:
            vp_start = 0
            vp_end = self._total_lines

        if self._show_annotations and self._annotations:
            gutter = self._build_annotation_gutter(vp_start, vp_end)
        else:
            gutter = [Text("") for _ in range(vp_end - vp_start)]

        sel_min, sel_max = self._selection_bounds()

        # Top indicator for viewport mode
        if self._viewport_mode and vp_start > 0:
            table.add_row(
                Text("", style="dim"),
                Text(f"\u00b7\u00b7\u00b7 {vp_start} lines above \u00b7\u00b7\u00b7", style="dim italic"),
                Text(""),
            )

        for file_idx in range(vp_start, vp_end):
            gutter_idx = file_idx - vp_start
            line = self._highlighted_lines[file_idx]
            ann_text = gutter[gutter_idx] if gutter_idx < len(gutter) else Text("")
            row_style = None
            if file_idx == self._cursor_line:
                row_style = CURSOR_STYLE
            elif sel_min is not None and sel_min <= file_idx <= sel_max:
                row_style = SELECTION_STYLE
            effective_max = min(self.MAX_LINE_WIDTH, code_max_width)
            if len(line) > effective_max:
                line = line.copy()
                line.truncate(effective_max)
                line.append("\u2026", style="dim")
            table.add_row(
                Text(str(file_idx + 1), style="dim"), line, ann_text, style=row_style
            )

        # Bottom indicator for viewport mode
        if self._viewport_mode and vp_end < self._total_lines:
            lines_below = self._total_lines - vp_end
            table.add_row(
                Text("", style="dim"),
                Text(f"\u00b7\u00b7\u00b7 {lines_below} lines below \u00b7\u00b7\u00b7", style="dim italic"),
                Text(""),
            )

        self.query_one("#code_display", Static).update(table)

        elapsed = time.perf_counter() - t0
        if elapsed > 0.05:
            self.log(f"_rebuild_display: {elapsed*1000:.1f}ms ({self._total_lines} lines, viewport={self._viewport_mode})")

    def on_resize(self, event) -> None:
        """Rebuild display when widget size changes so column widths adapt."""
        if self._total_lines > 0:
            self._rebuild_display()

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
        # In viewport mode, use cursor position relative to the rendered table
        cursor_row = self._cursor_line
        if self._viewport_mode:
            # Account for the "lines above" indicator row
            cursor_row = self._cursor_line - self._viewport_start
            if self._viewport_start > 0:
                cursor_row += 1
            # Clamp to valid table range (cursor may temporarily drift outside viewport during drag)
            max_row = self._viewport_content_height() - 1
            cursor_row = max(0, min(cursor_row, max_row))
        top = self.scroll_y
        bottom = top + self.size.height - 1
        if cursor_row < top + margin:
            self.scroll_to(y=max(0, cursor_row - margin), animate=False)
        elif cursor_row > bottom - margin:
            self.scroll_to(
                y=cursor_row - self.size.height + 1 + margin, animate=False
            )

    def move_cursor(self, line: int) -> None:
        """Move cursor to the given 0-indexed line. Selection stays visible but is
        marked inactive so the next shift+arrow starts a fresh selection."""
        if self._total_lines == 0:
            return
        line = max(0, min(line, self._total_lines - 1))
        self._cursor_line = line
        self._selection_active = False
        self._ensure_viewport_contains_cursor()
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
        self._ensure_viewport_contains_cursor()
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

    def action_page_down(self) -> None:
        """Move cursor down by a screen-height of lines."""
        self.move_cursor(self._cursor_line + max(1, self.size.height - 2))

    def action_page_up(self) -> None:
        """Move cursor up by a screen-height of lines."""
        self.move_cursor(self._cursor_line - max(1, self.size.height - 2))

    def _viewport_content_height(self) -> int:
        """Return the number of rendered rows in viewport mode (data + indicators)."""
        vp_end = min(self._viewport_start + self._viewport_size, self._total_lines)
        rows = vp_end - self._viewport_start
        if self._viewport_start > 0:
            rows += 1  # "lines above" indicator
        if vp_end < self._total_lines:
            rows += 1  # "lines below" indicator
        return rows

    # -- Edge scroll (constant-speed scrolling during mouse drag) ------------

    def _start_edge_scroll(self, direction: int) -> None:
        """Start constant-speed edge scrolling in the given direction."""
        if self._edge_scroll_direction == direction:
            return
        self._stop_edge_scroll()
        self._edge_scroll_direction = direction
        self._edge_scroll_timer = self.set_interval(1 / 20, self._edge_scroll_tick)

    def _stop_edge_scroll(self) -> None:
        """Stop edge scrolling."""
        if self._edge_scroll_timer is not None:
            self._edge_scroll_timer.stop()
            self._edge_scroll_timer = None
        self._edge_scroll_direction = 0

    def _edge_scroll_tick(self) -> None:
        """Timer callback: move cursor by 1 line at constant rate."""
        if not self._mouse_dragging or self._edge_scroll_direction == 0:
            self._stop_edge_scroll()
            return
        line = self._cursor_line + self._edge_scroll_direction
        line = max(0, min(line, self._total_lines - 1))
        if line == self._cursor_line:
            self._stop_edge_scroll()
            return
        self._cursor_line = line
        self._selection_end = line
        # During edge scroll, position viewport so cursor is at the edge
        if self._viewport_mode:
            if self._edge_scroll_direction > 0:
                desired = max(0, line - self._viewport_size + 3)
            else:
                desired = max(0, line - 2)
            self._viewport_start = min(
                desired, max(0, self._total_lines - self._viewport_size)
            )
        self._rebuild_display()
        self._scroll_cursor_visible()
        self.post_message(self.CursorMoved(line + 1, self._total_lines))

    # -- Mouse handlers -------------------------------------------------------

    def on_mouse_scroll_down(self, event) -> None:
        """In viewport mode, shift viewport when scrolling past the bottom."""
        if not self._viewport_mode:
            return
        vp_end = min(self._viewport_start + self._viewport_size, self._total_lines)
        if vp_end >= self._total_lines:
            return
        max_scroll = max(0, self._viewport_content_height() - self.size.height)
        if self.scroll_y >= max_scroll - 1:
            shift = min(3, self._total_lines - vp_end)
            self._viewport_start += shift
            self._rebuild_display()

    def on_mouse_scroll_up(self, event) -> None:
        """In viewport mode, shift viewport when scrolling past the top."""
        if not self._viewport_mode or self._viewport_start <= 0:
            return
        if self.scroll_y <= 1:
            shift = min(3, self._viewport_start)
            self._viewport_start -= shift
            self._rebuild_display()
            self.scroll_to(y=shift, animate=False)

    def on_mouse_down(self, event) -> None:
        """Left-click moves cursor to clicked line and starts drag tracking.

        Before capture_mouse(), event.y is in content coordinates (includes
        scroll offset), so no scroll_y adjustment is needed.  In viewport mode,
        the rendered table starts at _viewport_start so we add the offset.
        """
        if event.button != 1 or self._total_lines == 0:
            return
        row = event.y
        if self._viewport_mode:
            # Skip the "lines above" indicator row
            if self._viewport_start > 0:
                row = max(0, row - 1)
            line = max(0, min(row + self._viewport_start, self._total_lines - 1))
        else:
            line = max(0, min(row, self._total_lines - 1))
        self._cursor_line = line
        self._selection_start = line
        self._selection_end = line
        self._selection_active = True
        self._mouse_dragging = True
        self.capture_mouse()
        self._rebuild_display()
        self.post_message(self.CursorMoved(line + 1, self._total_lines))

    def on_mouse_move(self, event) -> None:
        """Extend selection while dragging with left button held.

        After capture_mouse(), event.y is in viewport coordinates (relative to
        the widget's visible area), so scroll_y must be added for the content
        line.  When mouse is outside the visible area, start constant-speed
        edge scrolling via a timer (stops when mouse returns inside).
        """
        if not self._mouse_dragging:
            return
        viewport_height = max(1, self.size.height)
        if event.y < 0:
            self._start_edge_scroll(-1)
            return
        elif event.y >= viewport_height:
            self._start_edge_scroll(1)
            return
        else:
            self._stop_edge_scroll()
            row = int(self.scroll_y) + event.y
            if self._viewport_mode:
                # Skip the "lines above" indicator row
                if self._viewport_start > 0:
                    row = max(0, row - 1)
                line = row + self._viewport_start
            else:
                line = row
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
        self._stop_edge_scroll()
        self.release_mouse()
        # Snap viewport to final cursor position (may have drifted during throttled drag)
        self._ensure_viewport_contains_cursor()
        if self._selection_start == self._selection_end:
            # Single click (no drag) — clear selection, just keep cursor
            self._selection_start = None
            self._selection_end = None
            self._selection_active = False
        self._rebuild_display()
