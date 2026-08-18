#!/usr/bin/env python3
"""Characterization + body-boundary tests for stats_data's flat frontmatter scanner.

Deliberately imports **only** `stats_data`. The characterization half has to be
runnable *before* `lib/task_category.py` exists, so that it can pin
`parse_frontmatter`'s behaviour ahead of the `split_frontmatter` extraction
(t1544_2). Putting it in `tests/test_task_category.py` would make that
impossible: that module's bootstrap imports `task_category`, which is created
only after `stats_data.py` has already been edited.

Every characterization case below names the mutation it discriminates, so a
case that can no longer fail is visible as such rather than quietly decorative.
"""

import os
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, ".aitask-scripts", "lib"))

import stats_data  # noqa: E402


class TestParseFrontmatterCharacterization(unittest.TestCase):
    """Pin `parse_frontmatter`'s behaviour so the extraction cannot change it.

    Written and run green BEFORE `split_frontmatter` exists; re-run unchanged
    afterwards. No assertion here may be edited to accommodate the refactor --
    if one needs editing, the extraction changed behaviour and is wrong.
    """

    def test_normal_frontmatter(self):
        content = "---\nstatus: Ready\npriority: high\n---\n\n## Goal\n\nprose\n"
        self.assertEqual(
            stats_data.parse_frontmatter(content),
            {"status": "Ready", "priority": "high"},
        )

    def test_no_frontmatter_at_all(self):
        """Real shape: archived t20 starts with prose."""
        content = "there is already a skill of handling aitask selection\nmore prose\n"
        self.assertEqual(stats_data.parse_frontmatter(content), {})

    def test_pseudo_delimiter_first_line(self):
        """Real shape: archived t21/t22 start with `--- effort:med pri:hi`.

        The first line starts with `---` but is not exactly `---`, so it is NOT
        a frontmatter delimiter. This is the case a substring split on
        `content.split('---', 2)` gets wrong.
        """
        content = "--- effort:med pri:hi\n\nI would like to modify the scripts\n"
        self.assertEqual(stats_data.parse_frontmatter(content), {})

    def test_unterminated_block_consumes_whole_file(self):
        """No closing `---`: the loop exhausts and returns what it accumulated."""
        content = "---\nstatus: Ready\npriority: high\n"
        self.assertEqual(
            stats_data.parse_frontmatter(content),
            {"status": "Ready", "priority": "high"},
        )

    def test_bare_delimiter_inside_body_is_not_reparsed(self):
        """A later `---` in the body must not resume frontmatter parsing."""
        content = "---\nstatus: Done\n---\n\nprose\n\n---\nCOMPLETED: 2026-02-01\n"
        self.assertEqual(stats_data.parse_frontmatter(content), {"status": "Done"})

    def test_body_key_value_does_not_leak_into_metadata(self):
        """Discriminates: dropping the `break` at the closing delimiter.

        Without the break, `status: FAKE` from the body overwrites the real
        value. This is the case that catches a mis-placed terminator boundary
        at the metadata level.
        """
        content = "---\nstatus: Ready\n---\n\nstatus: FAKE\nprose\n"
        self.assertEqual(stats_data.parse_frontmatter(content), {"status": "Ready"})

    def test_colon_in_value_is_kept_whole(self):
        """Discriminates: `split(':')` instead of `split(':', 1)` (raises)."""
        content = "---\nissue: https://example.test/a:b\n---\nbody\n"
        self.assertEqual(
            stats_data.parse_frontmatter(content),
            {"issue": "https://example.test/a:b"},
        )

    def test_line_without_colon_is_skipped(self):
        """Discriminates: dropping the `if ':' not in line` guard (raises)."""
        content = "---\nplainline\nkey: v\n---\nbody\n"
        self.assertEqual(stats_data.parse_frontmatter(content), {"key": "v"})

    def test_quotes_are_kept_verbatim(self):
        """The scanner does NOT unquote -- this is why task_category._unquote exists."""
        content = "---\nfollowup_kind: \"carry_over\"\n---\nbody\n"
        self.assertEqual(
            stats_data.parse_frontmatter(content),
            {"followup_kind": '"carry_over"'},
        )

    def test_indented_key_is_normalized(self):
        """Documentation, not a tripwire.

        Measured during implementation: using `stripped` instead of the raw
        `line` for the `':' in ...` test and the split is behaviourally INERT,
        because `key.strip()` / `value.strip()` already normalize the result
        (0 divergences across 9 whitespace shapes). Recorded so nobody re-adds
        this as a "guard" believing it discriminates something.
        """
        content = "---\n  key:   value  \n---\nbody\n"
        self.assertEqual(stats_data.parse_frontmatter(content), {"key": "value"})


class TestSplitFrontmatter(unittest.TestCase):
    """Exact ``(metadata, body)`` assertions for the new boundary-returning API.

    Metadata assertions alone cannot see the body boundary: an off-by-one at
    the terminator, or returning the whole document, preserves every legacy
    metadata assertion while handing the retro-classifier frontmatter text or
    dropping the first line of prose. So every case below pins the body by
    string equality, never a substring check.
    """

    def test_normal_body_starts_after_the_terminator(self):
        content = "---\nstatus: Ready\n---\n\n## Goal\n\nprose\n"
        self.assertEqual(
            stats_data.split_frontmatter(content),
            ({"status": "Ready"}, "\n## Goal\n\nprose"),
        )

    def test_no_frontmatter_returns_content_verbatim(self):
        """Body is the ORIGINAL string, not a splitlines round-trip."""
        content = "there is already a skill\nmore prose\n"
        self.assertEqual(stats_data.split_frontmatter(content), ({}, content))

    def test_pseudo_delimiter_is_all_body(self):
        """t21/t22 shape: the leading `--- effort:...` is body, not a delimiter.

        A substring split on ``content.split('---', 2)`` gets exactly this
        wrong -- it would slice at the pseudo delimiter and return garbage.
        """
        content = "--- effort:med pri:hi\n\nI would like to modify\n"
        self.assertEqual(stats_data.split_frontmatter(content), ({}, content))

    def test_unterminated_block_has_no_body(self):
        content = "---\nstatus: Ready\npriority: high\n"
        self.assertEqual(
            stats_data.split_frontmatter(content),
            ({"status": "Ready", "priority": "high"}, ""),
        )

    def test_bare_delimiter_in_body_stays_in_the_body(self):
        """The FIRST closing `---` ends the block; a later one is plain prose."""
        content = "---\nstatus: Done\n---\n\nprose\n\n---\nCOMPLETED: 2026-02-01\n"
        self.assertEqual(
            stats_data.split_frontmatter(content),
            ({"status": "Done"}, "\nprose\n\n---\nCOMPLETED: 2026-02-01"),
        )

    def test_parse_frontmatter_is_the_metadata_half(self):
        """Pins the delegation: one boundary definition, not two."""
        for content in (
            "---\nstatus: Ready\n---\n\nprose\n",
            "no frontmatter here\n",
            "--- effort:med\nbody\n",
            "---\nunterminated: yes\n",
        ):
            self.assertEqual(
                stats_data.parse_frontmatter(content),
                stats_data.split_frontmatter(content)[0],
            )

if __name__ == "__main__":
    unittest.main(verbosity=2)
