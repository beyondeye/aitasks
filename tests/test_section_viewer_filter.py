"""Unit tests for section_viewer._filter_sections (t721)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from section_viewer import _filter_sections, parse_sections  # noqa: E402


SAMPLE = (
    "<!-- section: a [dimensions: requirements_perf] -->\nA\n"
    "<!-- /section: a -->\n"
    "<!-- section: b [dimensions: assumption_x] -->\nB\n"
    "<!-- /section: b -->\n"
    "<!-- section: c [dimensions: requirements_perf] -->\nC\n"
    "<!-- /section: c -->\n"
)


class FilterSectionsTests(unittest.TestCase):
    def test_no_filter_returns_all(self):
        parsed = parse_sections(SAMPLE)
        out = _filter_sections(parsed, None)
        self.assertEqual([s.name for s in out], ["a", "b", "c"])

    def test_filter_preserves_parse_order(self):
        parsed = parse_sections(SAMPLE)
        # names argument order should be ignored — parse order wins
        out = _filter_sections(parsed, ["c", "a"])
        self.assertEqual([s.name for s in out], ["a", "c"])

    def test_filter_with_subset(self):
        parsed = parse_sections(SAMPLE)
        out = _filter_sections(parsed, ["b"])
        self.assertEqual([s.name for s in out], ["b"])

    def test_unknown_names_silently_skipped(self):
        parsed = parse_sections(SAMPLE)
        self.assertEqual(_filter_sections(parsed, ["zzz"]), [])

    def test_empty_filter_returns_empty(self):
        parsed = parse_sections(SAMPLE)
        self.assertEqual(_filter_sections(parsed, []), [])


if __name__ == "__main__":
    unittest.main()
