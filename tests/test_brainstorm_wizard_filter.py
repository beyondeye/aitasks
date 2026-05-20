"""Tests for the brainstorm wizard fuzzy-filter helper (t806).

Pure-logic test for `_filter_labels`, the case-insensitive substring filter
backing the Synthesize/Compare wizard `FuzzyCheckList` search boxes. End-to-end
TUI behaviour (Pilot/manual) is verified separately during interactive
testing.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from brainstorm.brainstorm_app import _filter_labels  # noqa: E402


class FilterLabelsTests(unittest.TestCase):
    LABELS = ["alpha", "beta", "gamma", "Alpha2", "delta"]

    def test_blank_query_keeps_everything(self):
        self.assertEqual(_filter_labels("", self.LABELS), self.LABELS)
        self.assertEqual(_filter_labels("   ", self.LABELS), self.LABELS)

    def test_substring_match(self):
        self.assertEqual(_filter_labels("eta", self.LABELS), ["beta"])

    def test_case_insensitive(self):
        self.assertEqual(
            _filter_labels("alpha", self.LABELS), ["alpha", "Alpha2"])
        self.assertEqual(
            _filter_labels("ALPHA", self.LABELS), ["alpha", "Alpha2"])

    def test_order_preserved(self):
        # Every label contains "a" — result keeps the original order.
        self.assertEqual(_filter_labels("a", self.LABELS), self.LABELS)

    def test_no_match_returns_empty(self):
        self.assertEqual(_filter_labels("zzz", self.LABELS), [])

    def test_query_is_trimmed(self):
        self.assertEqual(_filter_labels("  beta  ", self.LABELS), ["beta"])

    def test_blank_query_returns_a_copy(self):
        result = _filter_labels("", self.LABELS)
        self.assertEqual(result, self.LABELS)
        self.assertIsNot(result, self.LABELS)


if __name__ == "__main__":
    unittest.main()
