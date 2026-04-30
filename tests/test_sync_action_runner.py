#!/usr/bin/env python3
"""Tests for .aitask-scripts/lib/sync_action_runner.py — parser only."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
LIB_SRC = PROJECT_DIR / ".aitask-scripts" / "lib"
sys.path.insert(0, str(LIB_SRC))

from sync_action_runner import (  # noqa: E402
    STATUS_AUTOMERGED,
    STATUS_CONFLICT,
    STATUS_ERROR,
    STATUS_NOTHING,
    STATUS_NO_NETWORK,
    STATUS_NO_REMOTE,
    STATUS_PULLED,
    STATUS_PUSHED,
    STATUS_SYNCED,
    parse_sync_output,
)


class ParseSyncOutputTests(unittest.TestCase):
    def test_synced(self):
        r = parse_sync_output("SYNCED")
        self.assertEqual(r.status, STATUS_SYNCED)
        self.assertEqual(r.conflicted_files, [])
        self.assertIsNone(r.error_message)

    def test_pushed(self):
        self.assertEqual(parse_sync_output("PUSHED").status, STATUS_PUSHED)

    def test_pulled(self):
        self.assertEqual(parse_sync_output("PULLED").status, STATUS_PULLED)

    def test_nothing(self):
        self.assertEqual(parse_sync_output("NOTHING").status, STATUS_NOTHING)

    def test_automerged(self):
        self.assertEqual(parse_sync_output("AUTOMERGED").status, STATUS_AUTOMERGED)

    def test_no_network(self):
        self.assertEqual(parse_sync_output("NO_NETWORK").status, STATUS_NO_NETWORK)

    def test_no_remote(self):
        self.assertEqual(parse_sync_output("NO_REMOTE").status, STATUS_NO_REMOTE)

    def test_conflict_multi(self):
        r = parse_sync_output("CONFLICT:a.md,b.md")
        self.assertEqual(r.status, STATUS_CONFLICT)
        self.assertEqual(r.conflicted_files, ["a.md", "b.md"])

    def test_conflict_single(self):
        r = parse_sync_output("CONFLICT:single.md")
        self.assertEqual(r.status, STATUS_CONFLICT)
        self.assertEqual(r.conflicted_files, ["single.md"])

    def test_conflict_bare_preserves_legacy_split(self):
        # Pure extraction: "".split(",") returns [""] in Python.
        # We preserve the historical board behavior verbatim.
        r = parse_sync_output("CONFLICT:")
        self.assertEqual(r.status, STATUS_CONFLICT)
        self.assertEqual(r.conflicted_files, [""])

    def test_error(self):
        r = parse_sync_output("ERROR:something bad happened")
        self.assertEqual(r.status, STATUS_ERROR)
        self.assertEqual(r.error_message, "something bad happened")

    def test_empty_string(self):
        r = parse_sync_output("")
        self.assertEqual(r.status, STATUS_ERROR)
        self.assertIn("empty", r.error_message or "")

    def test_only_whitespace(self):
        r = parse_sync_output("\n\n   \n")
        self.assertEqual(r.status, STATUS_ERROR)
        self.assertIn("empty", r.error_message or "")

    def test_unknown_status(self):
        r = parse_sync_output("WEIRDSTATUS")
        self.assertEqual(r.status, STATUS_ERROR)
        self.assertIn("unknown status", r.error_message or "")
        self.assertIn("WEIRDSTATUS", r.error_message or "")

    def test_first_line_only_with_trailing_noise(self):
        r = parse_sync_output("PUSHED\nextra debug noise\n")
        self.assertEqual(r.status, STATUS_PUSHED)

    def test_leading_blank_lines_stripped(self):
        r = parse_sync_output("\n\nPUSHED\n")
        self.assertEqual(r.status, STATUS_PUSHED)

    def test_per_line_whitespace_stripped(self):
        r = parse_sync_output("  PUSHED  ")
        self.assertEqual(r.status, STATUS_PUSHED)

    def test_raw_output_preserved(self):
        raw = "PUSHED\ntrailing\n"
        r = parse_sync_output(raw)
        self.assertEqual(r.raw_output, raw)


if __name__ == "__main__":
    unittest.main()
