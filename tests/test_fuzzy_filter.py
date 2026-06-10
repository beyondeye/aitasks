"""Tests for the general-purpose fuzzy subsequence matcher (t958).

`lib/fuzzy_filter.py` backs the shortcut-dialog search boxes. Covers:
  - match(): subsequence hit/miss, case-insensitivity, empty query.
  - scoring: consecutive runs and word-start hits outrank scattered matches.
  - rank(): blank-query passthrough, non-matches filtered out, best-first order.

Run: python3 tests/test_fuzzy_filter.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import fuzzy_filter  # noqa: E402


class MatchTests(unittest.TestCase):
    def test_subsequence_hit(self):
        score, positions = fuzzy_filter.match("sav", "save")
        self.assertGreater(score, 0)
        self.assertEqual(list(positions), [0, 1, 2])

    def test_non_subsequence_misses(self):
        self.assertEqual(fuzzy_filter.match("xyz", "save"), (0.0, ()))
        # right letters, wrong order
        self.assertEqual(fuzzy_filter.match("eva", "save"), (0.0, ()))

    def test_empty_query(self):
        self.assertEqual(fuzzy_filter.match("", "anything"), (0.0, ()))

    def test_case_insensitive_by_default(self):
        self.assertGreater(fuzzy_filter.match("SAV", "save")[0], 0)

    def test_case_sensitive_opt_in(self):
        self.assertEqual(
            fuzzy_filter.match("SAV", "save", case_sensitive=True), (0.0, ())
        )

    def test_consecutive_outranks_scattered(self):
        # "ac" is consecutive in "action" (a,c adjacent) but scattered in
        # "atomic" (a..c with gaps) -> action scores higher.
        consecutive = fuzzy_filter.match("ac", "action")[0]
        scattered = fuzzy_filter.match("ac", "atomic")[0]
        self.assertGreater(consecutive, scattered)

    def test_word_start_bonus(self):
        # 's' at a word start (save) beats 's' mid-word (pass).
        at_start = fuzzy_filter.match("s", "save")[0]
        mid_word = fuzzy_filter.match("s", "pass")[0]
        self.assertGreater(at_start, mid_word)


class RankTests(unittest.TestCase):
    def test_blank_query_returns_unchanged(self):
        items = ["b", "a", "c"]
        self.assertEqual(
            fuzzy_filter.rank("", items, key=str), items
        )
        self.assertEqual(
            fuzzy_filter.rank("   ", items, key=str), items
        )

    def test_filters_out_non_matches(self):
        items = ["save", "open", "quit"]
        self.assertEqual(
            fuzzy_filter.rank("zz", items, key=str), []
        )

    def test_best_match_first(self):
        items = ["atomic", "action"]
        # "action" (consecutive 'ac') should rank ahead of "atomic".
        self.assertEqual(
            fuzzy_filter.rank("ac", items, key=str), ["action", "atomic"]
        )

    def test_key_extractor(self):
        rows = [("pick", "Pick task"), ("brainstorm", "Brainstorm")]
        out = fuzzy_filter.rank("pick", rows, key=lambda r: f"{r[0]} {r[1]}")
        self.assertEqual(out, [("pick", "Pick task")])

    def test_ties_keep_original_order(self):
        # Two identical candidates score equally; stable order is preserved.
        items = [("first", "ab"), ("second", "ab")]
        out = fuzzy_filter.rank("ab", items, key=lambda r: r[1])
        self.assertEqual([r[0] for r in out], ["first", "second"])


if __name__ == "__main__":
    unittest.main()
