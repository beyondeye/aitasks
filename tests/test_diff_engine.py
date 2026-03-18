"""Unit tests for .aitask-scripts/diffviewer/diff_engine.py and plan_loader.py."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add the .aitask-scripts directory to path for imports
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from diffviewer.plan_loader import load_plan
from diffviewer.diff_engine import (
    DiffHunk,
    MultiDiffResult,
    PairwiseDiff,
    compute_classical_diff,
    compute_multi_diff,
    compute_structural_diff,
)
from diffviewer.md_parser import Section, parse_sections, normalize_section

TEST_PLANS = SCRIPTS_DIR / "diffviewer" / "test_plans"


class TestPlanLoader(unittest.TestCase):
    def test_load_plan_with_frontmatter(self):
        meta, body, lines = load_plan(str(TEST_PLANS / "plan_alpha.md"))
        self.assertIn("Task", meta)
        self.assertGreater(len(body), 0)
        self.assertGreater(len(lines), 0)

    def test_load_plan_body_excludes_frontmatter(self):
        meta, body, lines = load_plan(str(TEST_PLANS / "plan_alpha.md"))
        self.assertNotIn("---", body[:10])

    def test_load_plan_no_frontmatter(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write("# No frontmatter\n\nJust content.\n")
            path = f.name
        try:
            meta, body, lines = load_plan(path)
            self.assertEqual(meta, {})
            self.assertIn("No frontmatter", body)
            self.assertGreater(len(lines), 0)
        finally:
            os.unlink(path)

    def test_load_plan_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            load_plan("/nonexistent/path.md")

    def test_all_test_plans_loadable(self):
        for name in ("plan_alpha", "plan_beta", "plan_gamma", "plan_delta", "plan_epsilon"):
            path = str(TEST_PLANS / f"{name}.md")
            meta, body, lines = load_plan(path)
            self.assertIsInstance(meta, dict, f"{name}: meta should be dict")
            self.assertGreater(len(lines), 0, f"{name}: should have body lines")


class TestComputeClassicalDiff(unittest.TestCase):
    def test_identical_lines_all_equal(self):
        _, _, lines = load_plan(str(TEST_PLANS / "plan_alpha.md"))
        hunks = compute_classical_diff(lines, lines)
        self.assertTrue(all(h.tag == "equal" for h in hunks))

    def test_different_lines_has_changes(self):
        _, _, alpha = load_plan(str(TEST_PLANS / "plan_alpha.md"))
        _, _, beta = load_plan(str(TEST_PLANS / "plan_beta.md"))
        hunks = compute_classical_diff(alpha, beta)
        tags = {h.tag for h in hunks}
        self.assertTrue(tags - {"equal"}, "Should have non-equal hunks")

    def test_empty_vs_content_all_insert(self):
        hunks = compute_classical_diff([], ["line1\n", "line2\n"])
        self.assertEqual(len(hunks), 1)
        self.assertEqual(hunks[0].tag, "insert")
        self.assertEqual(hunks[0].other_lines, ["line1\n", "line2\n"])
        self.assertEqual(hunks[0].main_lines, [])

    def test_content_vs_empty_all_delete(self):
        hunks = compute_classical_diff(["line1\n", "line2\n"], [])
        self.assertEqual(len(hunks), 1)
        self.assertEqual(hunks[0].tag, "delete")
        self.assertEqual(hunks[0].main_lines, ["line1\n", "line2\n"])
        self.assertEqual(hunks[0].other_lines, [])

    def test_replace_hunk(self):
        hunks = compute_classical_diff(
            ["same\n", "old\n"], ["same\n", "new\n"]
        )
        tags = [h.tag for h in hunks]
        self.assertIn("equal", tags)
        self.assertIn("replace", tags)

    def test_source_plan_propagated(self):
        hunks = compute_classical_diff(
            ["a\n"], ["b\n"], source_plan="test.md"
        )
        self.assertEqual(hunks[0].source_plans, ["test.md"])

    def test_source_plan_empty_when_not_provided(self):
        hunks = compute_classical_diff(["a\n"], ["b\n"])
        self.assertEqual(hunks[0].source_plans, [])

    def test_main_range_tracking(self):
        hunks = compute_classical_diff(
            ["same\n", "old\n", "end\n"],
            ["same\n", "new\n", "end\n"],
        )
        equal_hunks = [h for h in hunks if h.tag == "equal"]
        self.assertEqual(equal_hunks[0].main_range, (0, 1))

    def test_other_range_tracking(self):
        hunks = compute_classical_diff(
            ["same\n", "old\n"],
            ["same\n", "new\n"],
        )
        replace_hunks = [h for h in hunks if h.tag == "replace"]
        self.assertEqual(len(replace_hunks), 1)
        self.assertEqual(replace_hunks[0].other_range, (1, 2))

    def test_both_empty(self):
        hunks = compute_classical_diff([], [])
        self.assertEqual(hunks, [])


class TestComputeMultiDiff(unittest.TestCase):
    def test_two_comparisons(self):
        result = compute_multi_diff(
            str(TEST_PLANS / "plan_alpha.md"),
            [
                str(TEST_PLANS / "plan_beta.md"),
                str(TEST_PLANS / "plan_gamma.md"),
            ],
        )
        self.assertEqual(len(result.comparisons), 2)
        self.assertEqual(result.main_path, str(TEST_PLANS / "plan_alpha.md"))

    def test_unique_to_main_populated(self):
        result = compute_multi_diff(
            str(TEST_PLANS / "plan_alpha.md"),
            [
                str(TEST_PLANS / "plan_beta.md"),
                str(TEST_PLANS / "plan_gamma.md"),
            ],
        )
        self.assertGreater(len(result.unique_to_main), 0)

    def test_unique_to_others_populated(self):
        result = compute_multi_diff(
            str(TEST_PLANS / "plan_alpha.md"),
            [
                str(TEST_PLANS / "plan_beta.md"),
                str(TEST_PLANS / "plan_gamma.md"),
            ],
        )
        self.assertGreater(len(result.unique_to_others), 0)

    def test_mode_is_classical(self):
        result = compute_multi_diff(
            str(TEST_PLANS / "plan_alpha.md"),
            [str(TEST_PLANS / "plan_beta.md")],
        )
        self.assertEqual(result.comparisons[0].mode, "classical")

    def test_single_comparison(self):
        result = compute_multi_diff(
            str(TEST_PLANS / "plan_alpha.md"),
            [str(TEST_PLANS / "plan_delta.md")],
        )
        self.assertEqual(len(result.comparisons), 1)

    def test_gamma_delta_asymmetry(self):
        """Delta is a subset of gamma — gamma as main should have more unique content."""
        r1 = compute_multi_diff(
            str(TEST_PLANS / "plan_gamma.md"),
            [str(TEST_PLANS / "plan_delta.md")],
        )
        r2 = compute_multi_diff(
            str(TEST_PLANS / "plan_delta.md"),
            [str(TEST_PLANS / "plan_gamma.md")],
        )
        self.assertGreater(len(r1.unique_to_main), len(r2.unique_to_main))

    def test_all_five_plans(self):
        result = compute_multi_diff(
            str(TEST_PLANS / "plan_alpha.md"),
            [
                str(TEST_PLANS / "plan_beta.md"),
                str(TEST_PLANS / "plan_gamma.md"),
                str(TEST_PLANS / "plan_delta.md"),
                str(TEST_PLANS / "plan_epsilon.md"),
            ],
        )
        self.assertEqual(len(result.comparisons), 4)


class TestDataClasses(unittest.TestCase):
    def test_diffhunk_defaults(self):
        h = DiffHunk(tag="insert")
        self.assertEqual(h.main_lines, [])
        self.assertEqual(h.other_lines, [])
        self.assertEqual(h.source_plans, [])
        self.assertEqual(h.main_range, (0, 0))
        self.assertEqual(h.other_range, (0, 0))

    def test_diffhunk_repr(self):
        h = DiffHunk(tag="equal", main_lines=["test\n"], main_range=(0, 1))
        self.assertIn("equal", repr(h))

    def test_pairwisediff_defaults(self):
        p = PairwiseDiff(main_path="a.md", other_path="b.md", mode="classical")
        self.assertEqual(p.hunks, [])

    def test_multidiffresult_defaults(self):
        m = MultiDiffResult(main_path="a.md")
        self.assertEqual(m.comparisons, [])
        self.assertEqual(m.unique_to_main, [])
        self.assertEqual(m.unique_to_others, {})

    def test_no_shared_mutable_defaults(self):
        """Ensure each instance gets its own list/dict."""
        h1 = DiffHunk(tag="a")
        h2 = DiffHunk(tag="b")
        h1.main_lines.append("x")
        self.assertEqual(h2.main_lines, [])


class TestParseSections(unittest.TestCase):
    def test_preamble_only(self):
        lines = ["Hello\n", "World\n"]
        sections = parse_sections(lines)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].level, 0)
        self.assertEqual(sections[0].heading, "")
        self.assertEqual(sections[0].content_lines, lines)

    def test_single_heading(self):
        lines = ["# Title\n", "Body line\n"]
        sections = parse_sections(lines)
        self.assertEqual(len(sections), 2)  # preamble + section
        self.assertEqual(sections[0].content_lines, [])  # empty preamble
        self.assertEqual(sections[1].heading, "# Title")
        self.assertEqual(sections[1].level, 1)
        self.assertEqual(sections[1].content_lines, ["Body line\n"])

    def test_multiple_headings(self):
        lines = ["# H1\n", "A\n", "## H2\n", "B\n", "### H3\n", "C\n"]
        sections = parse_sections(lines)
        self.assertEqual(len(sections), 4)  # preamble + 3 headings
        self.assertEqual(sections[1].level, 1)
        self.assertEqual(sections[2].level, 2)
        self.assertEqual(sections[3].level, 3)

    def test_code_fence_not_split(self):
        lines = [
            "# Before\n",
            "```python\n",
            "## Not a heading\n",
            "```\n",
            "# After\n",
            "Body\n",
        ]
        sections = parse_sections(lines)
        headings = [s.heading for s in sections if s.heading]
        self.assertEqual(headings, ["# Before", "# After"])
        # The code fence content stays in "Before" section
        before = [s for s in sections if s.heading == "# Before"][0]
        self.assertIn("## Not a heading\n", before.content_lines)

    def test_preamble_before_first_heading(self):
        lines = ["Preamble\n", "\n", "# Title\n", "Body\n"]
        sections = parse_sections(lines)
        self.assertEqual(sections[0].heading, "")
        self.assertEqual(sections[0].content_lines, ["Preamble\n", "\n"])

    def test_line_ranges(self):
        lines = ["# A\n", "A1\n", "A2\n", "# B\n", "B1\n"]
        sections = parse_sections(lines)
        # Section A starts at line 0, ends before line 3 (where B starts)
        a_section = sections[1]
        self.assertEqual(a_section.original_line_range[0], 0)
        self.assertEqual(a_section.original_line_range[1], 3)

    def test_test_plans_parse(self):
        """Each test plan produces a list of sections with correct headings."""
        for name in ("plan_alpha", "plan_beta", "plan_gamma", "plan_delta", "plan_epsilon"):
            _, _, lines = load_plan(str(TEST_PLANS / f"{name}.md"))
            sections = parse_sections(lines)
            self.assertGreater(len(sections), 1, f"{name}: should have multiple sections")


class TestNormalizeSection(unittest.TestCase):
    def test_heading_normalization(self):
        s = Section(heading="## Step 1: Setup", level=2, content_lines=[])
        n = normalize_section(s)
        self.assertEqual(n.heading, "step 1: setup")

    def test_content_whitespace_strip(self):
        s = Section(
            heading="# T", level=1,
            content_lines=["  line  \n", "other  \n"]
        )
        n = normalize_section(s)
        self.assertEqual(n.content_lines, ["  line\n", "other\n"])

    def test_collapse_blank_lines(self):
        s = Section(
            heading="# T", level=1,
            content_lines=["A\n", "\n", "\n", "\n", "B\n"]
        )
        n = normalize_section(s)
        self.assertEqual(n.content_lines, ["A\n", "\n", "B\n"])

    def test_strip_leading_trailing_blanks(self):
        s = Section(
            heading="# T", level=1,
            content_lines=["\n", "\n", "Content\n", "\n"]
        )
        n = normalize_section(s)
        self.assertEqual(n.content_lines, ["Content\n"])

    def test_immutable(self):
        s = Section(heading="## H", level=2, content_lines=["A\n"])
        n = normalize_section(s)
        self.assertIsNot(s, n)
        self.assertEqual(s.heading, "## H")  # original unchanged


class TestComputeStructuralDiff(unittest.TestCase):
    def test_identical_content_all_equal(self):
        lines = ["# A\n", "Body\n", "# B\n", "Other\n"]
        hunks = compute_structural_diff(lines, lines)
        tags = {h.tag for h in hunks}
        self.assertEqual(tags, {"equal"})

    def test_reordered_sections_are_moved(self):
        main = ["# A\n", "Content A\n", "# B\n", "Content B\n"]
        other = ["# B\n", "Content B\n", "# A\n", "Content A\n"]
        hunks = compute_structural_diff(main, other)
        moved_hunks = [h for h in hunks if h.tag == "moved"]
        self.assertGreater(len(moved_hunks), 0, "Should detect moved sections")

    def test_classical_does_not_detect_moves(self):
        main = ["# A\n", "Content A\n", "# B\n", "Content B\n"]
        other = ["# B\n", "Content B\n", "# A\n", "Content A\n"]
        hunks = compute_classical_diff(main, other)
        moved_hunks = [h for h in hunks if h.tag == "moved"]
        self.assertEqual(len(moved_hunks), 0, "Classical should not detect moves")

    def test_deleted_section(self):
        main = ["# A\n", "A content\n", "# B\n", "B content\n"]
        other = ["# A\n", "A content\n"]
        hunks = compute_structural_diff(main, other)
        delete_hunks = [h for h in hunks if h.tag == "delete"]
        self.assertGreater(len(delete_hunks), 0)

    def test_inserted_section(self):
        main = ["# A\n", "A content\n"]
        other = ["# A\n", "A content\n", "# B\n", "B content\n"]
        hunks = compute_structural_diff(main, other)
        insert_hunks = [h for h in hunks if h.tag == "insert"]
        self.assertGreater(len(insert_hunks), 0)

    def test_replaced_section_content(self):
        main = ["# A\n", "Old content\n"]
        other = ["# A\n", "New content\n"]
        hunks = compute_structural_diff(main, other)
        # Should have replace hunks (same heading, different content, same position)
        tags = {h.tag for h in hunks}
        self.assertIn("replace", tags)

    def test_content_similarity_matching(self):
        """Sections with different headings but similar content should match."""
        main = ["# Setup Step\n", "Install deps\n", "Run config\n", "Test it\n"]
        other = ["# Configuration\n", "Install deps\n", "Run config\n", "Test it\n"]
        hunks = compute_structural_diff(main, other)
        # Should not have delete+insert, should have moved or replace
        delete_hunks = [h for h in hunks if h.tag == "delete"]
        insert_hunks = [h for h in hunks if h.tag == "insert"]
        self.assertEqual(len(delete_hunks), 0, "Should match by content similarity")
        self.assertEqual(len(insert_hunks), 0, "Should match by content similarity")

    def test_source_plan_propagated(self):
        main = ["# A\n", "X\n"]
        other = ["# A\n", "Y\n"]
        hunks = compute_structural_diff(main, other, source_plan="test.md")
        for h in hunks:
            self.assertEqual(h.source_plans, ["test.md"])

    def test_test_plans_structural_detects_moves(self):
        """Alpha vs gamma share 'Verification' heading at different positions."""
        _, _, alpha = load_plan(str(TEST_PLANS / "plan_alpha.md"))
        _, _, gamma = load_plan(str(TEST_PLANS / "plan_gamma.md"))
        struct_hunks = compute_structural_diff(alpha, gamma)
        moved = [h for h in struct_hunks if h.tag == "moved"]
        class_hunks = compute_classical_diff(alpha, gamma)
        class_moved = [h for h in class_hunks if h.tag == "moved"]
        self.assertGreater(len(moved), 0, "Structural should find moved sections")
        self.assertEqual(len(class_moved), 0, "Classical should not find moves")

    def test_empty_inputs(self):
        hunks = compute_structural_diff([], [])
        # Empty preamble sections both sides — should be equal
        for h in hunks:
            self.assertIn(h.tag, ("equal",))


class TestComputeMultiDiffStructural(unittest.TestCase):
    def test_structural_mode_routing(self):
        result = compute_multi_diff(
            str(TEST_PLANS / "plan_alpha.md"),
            [str(TEST_PLANS / "plan_beta.md")],
            mode="structural",
        )
        self.assertEqual(result.comparisons[0].mode, "structural")

    def test_structural_multi_diff_returns_valid_result(self):
        result = compute_multi_diff(
            str(TEST_PLANS / "plan_alpha.md"),
            [
                str(TEST_PLANS / "plan_beta.md"),
                str(TEST_PLANS / "plan_gamma.md"),
            ],
            mode="structural",
        )
        self.assertEqual(len(result.comparisons), 2)
        self.assertEqual(result.main_path, str(TEST_PLANS / "plan_alpha.md"))

    def test_structural_all_five_plans(self):
        result = compute_multi_diff(
            str(TEST_PLANS / "plan_alpha.md"),
            [
                str(TEST_PLANS / "plan_beta.md"),
                str(TEST_PLANS / "plan_gamma.md"),
                str(TEST_PLANS / "plan_delta.md"),
                str(TEST_PLANS / "plan_epsilon.md"),
            ],
            mode="structural",
        )
        self.assertEqual(len(result.comparisons), 4)
        # All comparisons should have hunks
        for comp in result.comparisons:
            self.assertGreater(len(comp.hunks), 0)


if __name__ == "__main__":
    unittest.main()
