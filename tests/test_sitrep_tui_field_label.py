#!/usr/bin/env python3
"""The sitrep TUI's details label column (t2357).

``sitrep_tui_app._field`` pads a label to the 12-cell ``_LABEL_W`` column and
appends the value. Two pins:

``OriginLabelTests``
    Every origin key the store writer accepts (``sitrep_todo.ORIGIN_KEYS``) has
    a label, and every label fits the column with its two-cell indent. A new
    accepted key without a label would otherwise fall back to the raw key, as
    ``incarnation`` did.

``SeparatorTests``
    A label that fills the column still gets one space before its value, and
    every label of 11 cells or fewer renders exactly as it did before.

The end-to-end pin (a real recovery item's details) is
``tests/test_sitrep_tui_app.py``
``test_a_recovery_items_origin_shows_its_episode``.

Run: python3 -m unittest tests.test_sitrep_tui_field_label -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / ".aitask-scripts"
for _p in (str(SCRIPTS), str(SCRIPTS / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import sitrep_todo as st  # noqa: E402
from sitrep_tui import sitrep_tui_app as appmod  # noqa: E402
from sitrep_tui import sitrep_tui_model as model  # noqa: E402


def _plain(label: str, value: str, indent: str = "") -> str:
    return appmod._field(label, value, indent).plain


class OriginLabelTests(unittest.TestCase):
    def test_every_accepted_origin_key_has_a_label(self):
        self.assertEqual(set(model.ORIGIN_LABELS), set(st.ORIGIN_KEYS))

    def test_incarnation_reads_as_episode(self):
        self.assertEqual(model.ORIGIN_LABELS["incarnation"], "Episode")

    def test_every_origin_label_fits_the_column(self):
        for key, label in model.ORIGIN_LABELS.items():
            with self.subTest(key=key):
                self.assertLessEqual(len("  " + label), appmod._LABEL_W - 1)
                self.assertEqual(_plain(label, "V", "  "),
                                 ("  " + label).ljust(appmod._LABEL_W) + "V")


class SeparatorTests(unittest.TestCase):
    def test_a_label_filling_the_column_keeps_a_space(self):
        self.assertEqual(_plain("incarnation", "0123456789ab", "  "),
                         "  incarnation 0123456789ab")
        self.assertEqual(_plain("A" * 12, "V"), "A" * 12 + " V")
        self.assertEqual(_plain("A" * 20, "V"), "A" * 20 + " V")

    def test_labels_up_to_eleven_cells_are_unchanged(self):
        self.assertEqual(_plain("Task status", "V"), "Task status V")
        self.assertEqual(_plain("What to do", "V"), "What to do  V")
        self.assertEqual(_plain("Agent", "V", "  "), "  Agent     V")

    def test_a_label_without_a_value_is_not_padded(self):
        self.assertEqual(_plain("Origin", ""), "Origin")


if __name__ == "__main__":
    unittest.main()
