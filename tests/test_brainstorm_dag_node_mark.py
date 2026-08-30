"""Tests for the DAG node-box space-marked checkbox glyph (t1004).

t983_3 wired space-marking into NodeSelection.marked and reflected it on the
list-view NodeRow glyph only; t1004 renders the same mark (✓/□ since t1638) on
the graph-view DAG node boxes so both Browse views agree. These cover
_render_node_box's title-row glyph and _render_layer's marked_ids threading.

The glyph and its colours moved to lib/mark_glyphs.py in t1638, so everything
here derives from that authority — including the colour, which is now an
explicit hex. It had to be: this is the only surface that renders the mark
through Rich, and Rich resolves the bare name `yellow` to #808000 (ANSI-3 olive)
while Textual resolves it to #FFFF00, so the DAG box had been painting a
different colour from every other mark in the repo.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from mark_glyphs import MARK_CHECKED_COLOUR  # noqa: E402

from brainstorm.brainstorm_dag_display import (  # noqa: E402
    BOX_WIDTH,
    COL_STRIDE,
    MARK_CHECKED,
    MARK_CHECKED_RICH_STYLE,
    MARK_UNCHECKED,
    _render_layer,
    _render_node_box,
)


def _has_bold_colour_span(text, colour: str) -> bool:
    """True if any span carries a bold style in `colour` (the ✓ glyph style).

    Parameterised on the colour rather than hard-coding one: the authority owns
    that value, and a helper pinning its own would be a second authority in the
    very test that exists to stop them multiplying.
    """
    for s in text.spans:
        st = s.style
        if st and getattr(st, "bold", False):
            col = getattr(st, "color", None)
            if col is not None and getattr(col, "name", "") == colour.lower():
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

    def test_checked_glyph_carries_the_ratified_colour(self):
        rows = _render_node_box("n001_x", "desc", False, False, is_marked=True)
        self.assertTrue(
            _has_bold_colour_span(rows[1], MARK_CHECKED_COLOUR),
            f"expected a bold {MARK_CHECKED_COLOUR} span for the "
            f"{MARK_CHECKED} glyph",
        )
        # And the constant itself carries bold + the ratified colour. For a hex,
        # `Style.color.name` round-trips as the lowercased hex string.
        self.assertTrue(MARK_CHECKED_RICH_STYLE.bold)
        self.assertEqual(
            MARK_CHECKED_RICH_STYLE.color.name, MARK_CHECKED_COLOUR.lower()
        )


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
