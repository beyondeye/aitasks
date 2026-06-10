"""Render-level regression tests for codebrowser's CodeViewer (t960).

The t959 refactor moved CodeViewer's render loop onto the shared
``NumberedSourceView`` base (``.aitask-scripts/lib/numbered_source_view.py``),
unifying ``_highlighted_lines`` -> ``_lines`` and relocating the
annotation-gutter precompute into a ``_prepare_build`` hook plus a per-row
``_extra_cell(file_idx)`` lookup that indexes off ``file_idx -
self._build_start``. The existing ``test_code_viewer_control_chars.py`` never
drives the widget, so these Textual-pilot tests assert the post-refactor render
contract end to end:

- one Rich ``Table`` row per source line; ``_total_lines == len(splitlines())``;
- the 3-column layout (line number + content + annotation gutter) with per-line
  highlight spans;
- annotation-gutter indexing, including the non-zero ``_build_start`` in
  viewport mode (the off-by-one guard);
- cursor / selection row styles applied to the right rows;
- the wrap-vs-truncate toggle;
- viewport windowing for >2000-line files with above/below indicator rows.

Mirrors the pilot-harness style of ``tests/test_brainstorm_proposal_preview.py``.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# code_viewer lives in codebrowser/ and imports numbered_source_view from lib/
# (it self-inserts lib at import time; we add both explicitly for clarity).
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "codebrowser"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from textual.app import App, ComposeResult  # noqa: E402

from code_viewer import CodeViewer, CURSOR_STYLE, SELECTION_STYLE  # noqa: E402
from annotation_data import AnnotationRange  # noqa: E402


class _HostApp(App):
    """Minimal host that mounts a single CodeViewer."""

    def compose(self) -> ComposeResult:
        yield CodeViewer(id="viewer")


def _content_cells(viewer: CodeViewer):
    """Rendered content-column cells (Rich column index 1) of the last build.

    Column 0 is the line-number gutter, 1 is the source content (and any
    viewport indicator rows), 2 is the annotation gutter.
    """
    return viewer._table.columns[1]._cells


class _CodeViewerRenderTestBase(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def _write(self, tmpdir: str, name: str, content: str) -> Path:
        path = Path(tmpdir) / name
        path.write_text(content)
        return path


class RowMappingTests(_CodeViewerRenderTestBase):
    def test_one_table_row_per_source_line(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                content = "def foo():\n    x = 1\n    return x\n"
                path = self._write(td, "sample.py", content)
                app = _HostApp()
                async with app.run_test(size=(80, 24)) as pilot:
                    viewer = app.query_one(CodeViewer)
                    await pilot.pause()
                    viewer.load_file(path)
                    await pilot.pause()
                    expected = len(content.splitlines())
                    self.assertEqual(viewer._total_lines, expected)
                    # Small file: no viewport, one table row per source line.
                    self.assertFalse(viewer._viewport_mode)
                    self.assertEqual(viewer._table.row_count, expected)

        self._run(runner())

    def test_three_column_layout_and_highlight_spans(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                content = "def foo(x):\n    return x + 1  # comment\n"
                path = self._write(td, "sample.py", content)
                app = _HostApp()
                async with app.run_test(size=(80, 24)) as pilot:
                    viewer = app.query_one(CodeViewer)
                    await pilot.pause()
                    viewer.load_file(path)
                    await pilot.pause()
                    # line-number + content + annotation gutter.
                    self.assertEqual(len(viewer._table.columns), 3)
                    # Syntax highlighting attaches style spans to the per-line Text.
                    self.assertTrue(any(line.spans for line in viewer._lines))

        self._run(runner())


class AnnotationGutterTests(_CodeViewerRenderTestBase):
    def test_gutter_indexing_non_viewport(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                content = "".join(f"line_{i}\n" for i in range(10))
                path = self._write(td, "sample.py", content)
                app = _HostApp()
                async with app.run_test(size=(80, 24)) as pilot:
                    viewer = app.query_one(CodeViewer)
                    await pilot.pause()
                    viewer.load_file(path)
                    await pilot.pause()
                    viewer.set_annotations(
                        [AnnotationRange(start_line=3, end_line=3, task_ids=["42"])]
                    )
                    await pilot.pause()
                    self.assertEqual(viewer._build_start, 0)
                    # File line 3 == 0-indexed 2 carries the gutter label.
                    self.assertEqual(viewer._extra_cell(2).plain, "t42")
                    # An un-annotated line's gutter cell is empty.
                    self.assertEqual(viewer._extra_cell(0).plain, "")

        self._run(runner())

    def test_gutter_indexing_viewport_build_start_offset(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                content = "".join(f"row {i}\n" for i in range(2500))
                path = self._write(td, "big.py", content)
                app = _HostApp()
                async with app.run_test(size=(80, 24)) as pilot:
                    viewer = app.query_one(CodeViewer)
                    await pilot.pause()
                    viewer.load_file(path)
                    await pilot.pause()
                    self.assertTrue(viewer._viewport_mode)
                    # Annotate the 2400th source line (0-indexed 2399).
                    viewer.set_annotations(
                        [
                            AnnotationRange(
                                start_line=2400, end_line=2400, task_ids=["77"]
                            )
                        ]
                    )
                    # Bring the annotated line into the viewport window so the
                    # render range (and thus _build_start) is non-zero.
                    viewer.move_cursor(2399)
                    await pilot.pause()
                    self.assertGreater(viewer._build_start, 0)
                    # _extra_cell maps file_idx -> gutter via file_idx - _build_start.
                    self.assertEqual(viewer._extra_cell(2399).plain, "t77")
                    # Off-by-one neighbor must be empty (guards the offset math).
                    self.assertEqual(viewer._extra_cell(2398).plain, "")

        self._run(runner())


class CursorSelectionStyleTests(_CodeViewerRenderTestBase):
    def test_cursor_and_selection_row_styles(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                content = "".join(f"line_{i}\n" for i in range(20))
                path = self._write(td, "sample.py", content)
                app = _HostApp()
                async with app.run_test(size=(80, 24)) as pilot:
                    viewer = app.query_one(CodeViewer)
                    await pilot.pause()
                    viewer.load_file(path)
                    await pilot.pause()
                    viewer.move_cursor(5)
                    await pilot.pause()
                    self.assertIs(viewer._row_style(5), CURSOR_STYLE)
                    # Extend the selection to 5..7 (cursor ends on row 7).
                    viewer.extend_selection(1)
                    viewer.extend_selection(1)
                    await pilot.pause()
                    # Mid-selection row gets the selection style...
                    self.assertIs(viewer._row_style(6), SELECTION_STYLE)
                    # ...while the cursor row's style wins over selection.
                    self.assertIs(viewer._row_style(7), CURSOR_STYLE)
                    # A row outside cursor + selection has no special style.
                    self.assertIsNone(viewer._row_style(0))

        self._run(runner())


class WrapToggleTests(_CodeViewerRenderTestBase):
    def test_truncate_then_wrap(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                long_line = "x" * 200  # > content width at size (80, 24)
                content = long_line + "\nshort tail\n"
                path = self._write(td, "wide.py", content)
                app = _HostApp()
                async with app.run_test(size=(80, 24)) as pilot:
                    viewer = app.query_one(CodeViewer)
                    await pilot.pause()
                    viewer.load_file(path)
                    await pilot.pause()
                    # Default truncate mode: long line clipped with an ellipsis.
                    self.assertEqual(viewer._wrap_mode, "truncate")
                    truncated = _content_cells(viewer)[0].plain
                    self.assertTrue(truncated.endswith("…"))
                    self.assertLess(len(truncated), len(long_line))
                    # Toggle to wrap mode: full line kept, no ellipsis.
                    self.assertEqual(viewer.cycle_wrap_mode(), "wrap")
                    await pilot.pause()
                    wrapped = _content_cells(viewer)[0].plain
                    self.assertEqual(wrapped, long_line)
                    self.assertFalse(wrapped.endswith("…"))

        self._run(runner())


class ViewportWindowingTests(_CodeViewerRenderTestBase):
    def test_indicator_rows_and_row_count(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                content = "".join(f"row {i}\n" for i in range(2500))
                path = self._write(td, "big.py", content)
                app = _HostApp()
                async with app.run_test(size=(80, 24)) as pilot:
                    viewer = app.query_one(CodeViewer)
                    await pilot.pause()
                    viewer.load_file(path)
                    await pilot.pause()
                    self.assertTrue(viewer._viewport_mode)
                    size = viewer._viewport_size
                    # At the top: only a "lines below" indicator (no "above").
                    texts = [c.plain for c in _content_cells(viewer)]
                    self.assertEqual(viewer._table.row_count, size + 1)
                    self.assertTrue(any("lines below" in t for t in texts))
                    self.assertFalse(any("lines above" in t for t in texts))
                    # Scroll into the middle: both indicator rows appear.
                    viewer.move_cursor(1200)
                    await pilot.pause()
                    self.assertGreater(viewer._viewport_start, 0)
                    texts = [c.plain for c in _content_cells(viewer)]
                    self.assertEqual(viewer._table.row_count, size + 2)
                    self.assertTrue(any("lines above" in t for t in texts))
                    self.assertTrue(any("lines below" in t for t in texts))

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
