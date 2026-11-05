#!/usr/bin/env python3
"""Committed harvest regression fixtures (t2175_6).

Each directory under tests/fixtures/sitrep_harvest/corpus/ is a reviewed,
redacted harvest review case promoted from the local corpus (`ait sitrep case
export`): `input.txt` plus `case.json` naming what the CURRENT parser must
extract. A fixture records a parser gap that was fixed, so it fails against the
grammar that had the gap (tests/test_sitrep_corpus.sh case 8 proves that for
the joined banner with a flag-flipped copy).

Run: python3 -m unittest tests.test_sitrep_corpus_fixtures
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / ".aitask-scripts" / "lib"))

import sitrep_corpus as C  # noqa: E402

CORPUS = REPO / "tests" / "fixtures" / "sitrep_harvest" / "corpus"


class CorpusFixtureTests(unittest.TestCase):
    def test_there_is_at_least_one_fixture(self):
        self.assertTrue([d for d in CORPUS.iterdir() if d.is_dir()])

    def test_every_fixture_passes_with_the_current_parser(self):
        for d in sorted(p for p in CORPUS.iterdir() if p.is_dir()):
            with self.subTest(fixture=d.name):
                ok, why = C.check_fixture(str(d))
                self.assertTrue(ok, why)


if __name__ == "__main__":
    unittest.main()
