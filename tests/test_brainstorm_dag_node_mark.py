"""Tests for the DAG node-box space-marked checkbox glyph (t1004).

t983_3 wired space-marking into NodeSelection.marked and reflected it on the
list-view NodeRow glyph only; t1004 renders the same checkbox (☑/☐) on the
graph-view DAG node boxes so both Browse views agree. These cover
_render_node_box's title-row glyph and _render_layer's marked_ids threading.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from brainstorm.brainstorm_dag_display import (  # noqa: E402
    BOX_WIDTH,
    COL_STRIDE,
    MARK_CHECKED,
    MARK_CHECKED_STYLE,
    MARK_UNCHECKED,
    _render_layer,
    _render_node_box,
)


def _has_bold_yellow_span(text) -> bool:
    """True if any span carries a bold-yellow style (the ☑ glyph style)."""
    for s in text.spans:
        st = s.style
        if st and getattr(st, "bold", False):
            col = getattr(st, "color", None)
            if col is not None and getattr(col, "name", "") == "yellow":
                return True
    return False


class TestRenderNodeBoxMark(unittest.TestCase):
    def test_marked_title_has_checked_glyph(self):
        rows = _render_node_box("n001_x", "desc", False, False, is_marked=True)
        # Row 1 is the title row.
        self.assertIn(MARK_CHECKED, rows[1].plain)
        self.assertNotIn(MARK_UNCHECKED, rows[1].plain)

    def test_unmarked_title_has_unchecked_glyph_by_default(self):
        # Default is_marked=False renders the empty box.
        rows = _render_node_box("n001_x", "desc", False, False)
        self.assertIn(MARK_UNCHECKED, rows[1].plain)
        self.assertNotIn(MARK_CHECKED, rows[1].plain)

    def test_width_preserved_for_both_states(self):
        # The always-on 2-char glyph must not break box-width alignment, for
        # marked/unmarked × head/non-head.
        for is_marked in (True, False):
            for is_head in (True, False):
                with self.subTest(is_marked=is_marked, is_head=is_head):
                    rows = _render_node_box(
                        "n001_x", "desc", is_head, False, is_marked=is_marked
                    )
                    for i, row in enumerate(rows):
                        self.assertEqual(
                            len(row.plain), BOX_WIDTH,
                            f"row {i} width {len(row.plain)} != {BOX_WIDTH}: "
                            f"{row.plain!r}",
                        )

    def test_checked_glyph_is_bold_yellow(self):
        rows = _render_node_box("n001_x", "desc", False, False, is_marked=True)
        self.assertTrue(
            _has_bold_yellow_span(rows[1]),
            "expected a bold-yellow span for the ☑ glyph",
        )
        # And the constant itself is bold yellow.
        self.assertTrue(MARK_CHECKED_STYLE.bold)
        self.assertEqual(MARK_CHECKED_STYLE.color.name, "yellow")


class TestRenderLayerMark(unittest.TestCase):
    def test_marks_only_listed_node(self):
        layer = ["n001", "n002"]
        descs = {"n001": "first", "n002": "second"}
        total_width = COL_STRIDE * 2
        lines = _render_layer(
            layer, descs, head=None, focused_id=None,
            total_width=total_width, marked_ids={"n001"},
        )
        # Row 1 is the (composited) title row for the whole layer.
        title_line = lines[1].plain
        self.assertEqual(title_line.count(MARK_CHECKED), 1)
        self.assertEqual(title_line.count(MARK_UNCHECKED), 1)

    def test_no_marks_when_marked_ids_empty(self):
        layer = ["n001", "n002"]
        descs = {"n001": "first", "n002": "second"}
        lines = _render_layer(
            layer, descs, head=None, focused_id=None,
            total_width=COL_STRIDE * 2,
        )
        title_line = lines[1].plain
        self.assertEqual(title_line.count(MARK_CHECKED), 0)
        self.assertEqual(title_line.count(MARK_UNCHECKED), 2)


if __name__ == "__main__":
    unittest.main()
