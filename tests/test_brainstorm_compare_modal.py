"""Tests for compare-modal arrow navigation helper (t746).

Pure-logic test for `_next_checkbox_index`, the index computation used by
`CompareNodeSelectModal._navigate_checkboxes`. End-to-end TUI behavior
(Pilot/manual) is verified separately during interactive testing.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from brainstorm.brainstorm_app import _next_checkbox_index  # noqa: E402


class NextCheckboxIndexTests(unittest.TestCase):
    def test_no_checkboxes_returns_none(self):
        self.assertIsNone(_next_checkbox_index(None, 0, 1))
        self.assertIsNone(_next_checkbox_index(None, 0, -1))
        self.assertIsNone(_next_checkbox_index(0, 0, 1))

    def test_no_focus_down_focuses_first(self):
        self.assertEqual(_next_checkbox_index(None, 5, 1), 0)

    def test_no_focus_up_focuses_last(self):
        self.assertEqual(_next_checkbox_index(None, 5, -1), 4)

    def test_down_increments(self):
        self.assertEqual(_next_checkbox_index(0, 5, 1), 1)
        self.assertEqual(_next_checkbox_index(2, 5, 1), 3)

    def test_up_decrements(self):
        self.assertEqual(_next_checkbox_index(4, 5, -1), 3)
        self.assertEqual(_next_checkbox_index(1, 5, -1), 0)

    def test_down_at_bottom_stays(self):
        self.assertIsNone(_next_checkbox_index(4, 5, 1))

    def test_up_at_top_stays(self):
        self.assertIsNone(_next_checkbox_index(0, 5, -1))

    def test_single_checkbox_no_movement(self):
        self.assertIsNone(_next_checkbox_index(0, 1, 1))
        self.assertIsNone(_next_checkbox_index(0, 1, -1))


if __name__ == "__main__":
    unittest.main()
