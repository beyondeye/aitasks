"""Unit tests for .aitask-scripts/diffviewer/diff_display.py."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Add the .aitask-scripts directory to path for imports
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from diffviewer.diff_display import (
    _DisplayLine,
    _SideBySideLine,
    _flatten_hunks,
    _flatten_hunks_side_by_side,
    _all_equal,
    PLAN_COLORS,
    TAG_GUTTERS,
    TAG_STYLES,
)
from diffviewer.diff_engine import (
    DiffHunk,
    PairwiseDiff,
    MultiDiffResult,
    compute_classical_diff,
    compute_multi_diff,
)

TEST_PLANS = SCRIPTS_DIR / "diffviewer" / "test_plans"


class TestFlattenHunks(unittest.TestCase):
    """Tests for _flatten_hunks() — the core data transformation."""

    def test_equal_hunk(self):
        hunks = [DiffHunk(
            tag="equal",
            main_lines=["a", "b"],
            other_lines=["a", "b"],
            main_range=(0, 2),
            other_range=(0, 2),
        )]
        flat = _flatten_hunks(hunks)
        self.assertEqual(len(flat), 2)
        self.assertEqual(flat[0].tag, "equal")
        self.assertEqual(flat[0].main_lineno, 1)
        self.assertEqual(flat[0].other_lineno, 1)
        self.assertEqual(flat[0].content, "a")
        self.assertEqual(flat[1].main_lineno, 2)
        self.assertEqual(flat[1].other_lineno, 2)

    def test_insert_hunk(self):
        hunks = [DiffHunk(
            tag="insert",
            main_lines=[],
            other_lines=["new"],
            main_range=(3, 3),
            other_range=(3, 4),
        )]
        flat = _flatten_hunks(hunks)
        self.assertEqual(len(flat), 1)
        self.assertEqual(flat[0].tag, "insert")
        self.assertIsNone(flat[0].main_lineno)
        self.assertEqual(flat[0].other_lineno, 4)
        self.assertEqual(flat[0].content, "new")

    def test_delete_hunk(self):
        hunks = [DiffHunk(
            tag="delete",
            main_lines=["old"],
            other_lines=[],
            main_range=(5, 6),
            other_range=(5, 5),
        )]
        flat = _flatten_hunks(hunks)
        self.assertEqual(len(flat), 1)
        self.assertEqual(flat[0].tag, "delete")
        self.assertEqual(flat[0].main_lineno, 6)
        self.assertIsNone(flat[0].other_lineno)

    def test_replace_hunk_splits_to_delete_then_insert(self):
        hunks = [DiffHunk(
            tag="replace",
            main_lines=["old1", "old2"],
            other_lines=["new1"],
            main_range=(0, 2),
            other_range=(0, 1),
        )]
        flat = _flatten_hunks(hunks)
        self.assertEqual(len(flat), 3)
        # First: deleted lines from main
        self.assertEqual(flat[0].tag, "delete")
        self.assertEqual(flat[0].main_lineno, 1)
        self.assertEqual(flat[1].tag, "delete")
        self.assertEqual(flat[1].main_lineno, 2)
        # Then: inserted lines from other
        self.assertEqual(flat[2].tag, "insert")
        self.assertEqual(flat[2].other_lineno, 1)

    def test_moved_hunk(self):
        hunks = [DiffHunk(
            tag="moved",
            main_lines=["moved content"],
            other_lines=["moved content"],
            source_plans=["plan_b"],
            main_range=(10, 11),
            other_range=(20, 21),
        )]
        flat = _flatten_hunks(hunks)
        self.assertEqual(len(flat), 1)
        self.assertEqual(flat[0].tag, "moved")
        self.assertEqual(flat[0].main_lineno, 11)
        self.assertEqual(flat[0].other_lineno, 21)
        self.assertEqual(flat[0].source_plan, "plan_b")

    def test_mixed_hunks_ordering(self):
        hunks = [
            DiffHunk(tag="equal", main_lines=["a"], other_lines=["a"],
                     main_range=(0, 1), other_range=(0, 1)),
            DiffHunk(tag="insert", main_lines=[], other_lines=["b"],
                     main_range=(1, 1), other_range=(1, 2)),
            DiffHunk(tag="delete", main_lines=["c"], other_lines=[],
                     main_range=(1, 2), other_range=(2, 2)),
        ]
        flat = _flatten_hunks(hunks)
        self.assertEqual(len(flat), 3)
        self.assertEqual([dl.tag for dl in flat], ["equal", "insert", "delete"])

    def test_empty_hunks(self):
        flat = _flatten_hunks([])
        self.assertEqual(flat, [])

    def test_line_numbers_are_one_based(self):
        """Line numbers in display should be 1-based (human-readable)."""
        hunks = [DiffHunk(
            tag="equal",
            main_lines=["first"],
            other_lines=["first"],
            main_range=(0, 1),
            other_range=(0, 1),
        )]
        flat = _flatten_hunks(hunks)
        self.assertEqual(flat[0].main_lineno, 1)
        self.assertEqual(flat[0].other_lineno, 1)

    def test_source_plan_propagation(self):
        hunks = [DiffHunk(
            tag="insert",
            main_lines=[],
            other_lines=["x"],
            source_plans=["plan_c"],
            main_range=(0, 0),
            other_range=(0, 1),
        )]
        flat = _flatten_hunks(hunks)
        self.assertEqual(flat[0].source_plan, "plan_c")

    def test_source_plan_empty_when_not_set(self):
        hunks = [DiffHunk(
            tag="equal",
            main_lines=["x"],
            other_lines=["x"],
            main_range=(0, 1),
            other_range=(0, 1),
        )]
        flat = _flatten_hunks(hunks)
        self.assertEqual(flat[0].source_plan, "")


class TestAllEqual(unittest.TestCase):
    """Tests for _all_equal() helper."""

    def test_all_equal_lines(self):
        lines = [
            _DisplayLine(1, 1, "equal", "a"),
            _DisplayLine(2, 2, "equal", "b"),
        ]
        self.assertTrue(_all_equal(lines))

    def test_mixed_tags(self):
        lines = [
            _DisplayLine(1, 1, "equal", "a"),
            _DisplayLine(None, 2, "insert", "b"),
        ]
        self.assertFalse(_all_equal(lines))

    def test_empty_list(self):
        self.assertTrue(_all_equal([]))

    def test_single_non_equal(self):
        lines = [_DisplayLine(1, None, "delete", "a")]
        self.assertFalse(_all_equal(lines))


class TestConstants(unittest.TestCase):
    """Tests for module-level constants."""

    def test_all_tags_have_styles(self):
        for tag in ["equal", "insert", "delete", "replace", "moved"]:
            self.assertIn(tag, TAG_STYLES, f"Missing style for tag '{tag}'")

    def test_all_tags_have_gutters(self):
        for tag in ["equal", "insert", "delete", "replace", "moved"]:
            self.assertIn(tag, TAG_GUTTERS, f"Missing gutter for tag '{tag}'")

    def test_gutter_chars(self):
        self.assertEqual(TAG_GUTTERS["equal"], " ")
        self.assertEqual(TAG_GUTTERS["insert"], "+")
        self.assertEqual(TAG_GUTTERS["delete"], "-")
        self.assertEqual(TAG_GUTTERS["replace"], "~")
        self.assertEqual(TAG_GUTTERS["moved"], ">")

    def test_plan_colors_count(self):
        self.assertEqual(len(PLAN_COLORS), 5)

    def test_plan_colors_format(self):
        for letter, color in PLAN_COLORS:
            self.assertEqual(len(letter), 1)
            self.assertTrue(color.startswith("#"))


class TestFlattenHunksSideBySide(unittest.TestCase):
    """Tests for _flatten_hunks_side_by_side() — side-by-side alignment."""

    def test_equal_hunk_both_sides(self):
        hunks = [DiffHunk(
            tag="equal",
            main_lines=["a", "b"],
            other_lines=["a", "b"],
            main_range=(0, 2),
            other_range=(0, 2),
        )]
        rows = _flatten_hunks_side_by_side(hunks)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].main_content, "a")
        self.assertEqual(rows[0].other_content, "a")
        self.assertEqual(rows[0].main_lineno, 1)
        self.assertEqual(rows[0].other_lineno, 1)
        self.assertEqual(rows[0].tag, "equal")

    def test_insert_blank_on_main_side(self):
        hunks = [DiffHunk(
            tag="insert",
            main_lines=[],
            other_lines=["new"],
            main_range=(3, 3),
            other_range=(3, 4),
        )]
        rows = _flatten_hunks_side_by_side(hunks)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0].main_lineno)
        self.assertEqual(rows[0].main_content, "")
        self.assertEqual(rows[0].other_lineno, 4)
        self.assertEqual(rows[0].other_content, "new")
        self.assertEqual(rows[0].tag, "insert")

    def test_delete_blank_on_other_side(self):
        hunks = [DiffHunk(
            tag="delete",
            main_lines=["old"],
            other_lines=[],
            main_range=(5, 6),
            other_range=(5, 5),
        )]
        rows = _flatten_hunks_side_by_side(hunks)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].main_lineno, 6)
        self.assertEqual(rows[0].main_content, "old")
        self.assertIsNone(rows[0].other_lineno)
        self.assertEqual(rows[0].other_content, "")
        self.assertEqual(rows[0].tag, "delete")

    def test_replace_pairs_lines_horizontally(self):
        hunks = [DiffHunk(
            tag="replace",
            main_lines=["old1", "old2"],
            other_lines=["new1"],
            main_range=(0, 2),
            other_range=(0, 1),
        )]
        rows = _flatten_hunks_side_by_side(hunks)
        self.assertEqual(len(rows), 2)
        # First row: paired
        self.assertEqual(rows[0].main_content, "old1")
        self.assertEqual(rows[0].other_content, "new1")
        self.assertEqual(rows[0].tag, "replace")
        # Second row: main has content, other padded blank
        self.assertEqual(rows[1].main_content, "old2")
        self.assertEqual(rows[1].other_content, "")
        self.assertIsNone(rows[1].other_lineno)

    def test_replace_other_longer_than_main(self):
        hunks = [DiffHunk(
            tag="replace",
            main_lines=["old"],
            other_lines=["new1", "new2", "new3"],
            main_range=(0, 1),
            other_range=(0, 3),
        )]
        rows = _flatten_hunks_side_by_side(hunks)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].main_content, "old")
        self.assertEqual(rows[0].other_content, "new1")
        # Rows 1 and 2: main is padded
        self.assertIsNone(rows[1].main_lineno)
        self.assertEqual(rows[1].main_content, "")
        self.assertEqual(rows[2].other_content, "new3")

    def test_moved_hunk_both_sides(self):
        hunks = [DiffHunk(
            tag="moved",
            main_lines=["moved content"],
            other_lines=["moved content"],
            source_plans=["plan_b"],
            main_range=(10, 11),
            other_range=(20, 21),
        )]
        rows = _flatten_hunks_side_by_side(hunks)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].main_content, "moved content")
        self.assertEqual(rows[0].other_content, "moved content")
        self.assertEqual(rows[0].tag, "moved")
        self.assertEqual(rows[0].source_plan, "plan_b")

    def test_empty_hunks(self):
        rows = _flatten_hunks_side_by_side([])
        self.assertEqual(rows, [])

    def test_source_plan_default(self):
        sbl = _SideBySideLine(
            main_lineno=1, main_content="a",
            other_lineno=1, other_content="a",
            tag="equal",
        )
        self.assertEqual(sbl.source_plan, "")

    def test_end_to_end_classical(self):
        """Side-by-side flattening of real diff engine output."""
        result = compute_multi_diff(
            str(TEST_PLANS / "plan_alpha.md"),
            [str(TEST_PLANS / "plan_beta.md")],
            mode="classical",
        )
        rows = _flatten_hunks_side_by_side(result.comparisons[0].hunks)
        self.assertGreater(len(rows), 0)
        for row in rows:
            self.assertIn(row.tag, ("equal", "insert", "delete", "replace", "moved"))
            if row.tag == "equal":
                self.assertIsNotNone(row.main_lineno)
                self.assertIsNotNone(row.other_lineno)
            elif row.tag == "insert":
                self.assertIsNone(row.main_lineno)
                self.assertEqual(row.main_content, "")
            elif row.tag == "delete":
                self.assertIsNone(row.other_lineno)
                self.assertEqual(row.other_content, "")


class TestEndToEnd(unittest.TestCase):
    """End-to-end tests using real diff engine output."""

    def test_classical_diff_with_real_plans(self):
        result = compute_multi_diff(
            str(TEST_PLANS / "plan_alpha.md"),
            [str(TEST_PLANS / "plan_beta.md")],
            mode="classical",
        )
        flat = _flatten_hunks(result.comparisons[0].hunks)
        self.assertGreater(len(flat), 0)
        self.assertFalse(_all_equal(flat))
        # Should have a mix of tags
        tags = {dl.tag for dl in flat}
        self.assertIn("equal", tags)

    def test_structural_diff_with_moved(self):
        result = compute_multi_diff(
            str(TEST_PLANS / "plan_alpha.md"),
            [str(TEST_PLANS / "plan_gamma.md")],
            mode="structural",
        )
        flat = _flatten_hunks(result.comparisons[0].hunks)
        tags = {dl.tag for dl in flat}
        self.assertIn("moved", tags, "Structural diff should detect moved sections")

    def test_multi_diff_multiple_comparisons(self):
        result = compute_multi_diff(
            str(TEST_PLANS / "plan_alpha.md"),
            [
                str(TEST_PLANS / "plan_beta.md"),
                str(TEST_PLANS / "plan_gamma.md"),
            ],
            mode="classical",
        )
        self.assertEqual(len(result.comparisons), 2)
        for comp in result.comparisons:
            flat = _flatten_hunks(comp.hunks)
            self.assertGreater(len(flat), 0)

    def test_large_diff_performance(self):
        """100+ hunks should flatten without issues."""
        hunks = []
        for i in range(150):
            hunks.append(DiffHunk(
                tag="equal",
                main_lines=[f"line {i}"],
                other_lines=[f"line {i}"],
                main_range=(i, i + 1),
                other_range=(i, i + 1),
            ))
        flat = _flatten_hunks(hunks)
        self.assertEqual(len(flat), 150)

    def test_identical_plans_all_equal(self):
        """Diffing a plan against itself should produce all-equal lines."""
        result = compute_multi_diff(
            str(TEST_PLANS / "plan_alpha.md"),
            [str(TEST_PLANS / "plan_alpha.md")],
            mode="classical",
        )
        flat = _flatten_hunks(result.comparisons[0].hunks)
        self.assertTrue(_all_equal(flat))


if __name__ == "__main__":
    unittest.main()
