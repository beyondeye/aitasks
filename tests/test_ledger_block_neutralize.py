"""``ledger_block.neutralize_markers`` makes quoted ledgers inert (t1962).

``aitask_fold_content.sh`` carries a folded task's ``## Gate Runs`` / ``## Inbox``
into the primary as reference history. The parsers are not section-scoped, so
every marker that history holds must stop matching. The checks below run the
real parsers, because the point is parity with them: a matcher of our own
would pass a marker the parser still reads (U+00A0 is ``\\s``, U+2028 is a line
break for ``str.splitlines``).

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_ledger_block_neutralize.py -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                ".aitask-scripts", "lib"))
import gate_ledger  # noqa: E402
import ledger_block  # noqa: E402
import note_inbox  # noqa: E402

GATE = "> **✅ gate:plan_approved** run=2026-10-12T09:00:00Z status=pass attempt=1\n"
NOTE = ("> **✉ note:t5** id=2026-10-12T10:00:00Z.0123456789abcdef01234567 "
        "at=2026-10-12T10:00:00Z\n>\n> | body\n")


class NeutralizeMarkersTests(unittest.TestCase):

    def assert_inert(self, text):
        out = ledger_block.neutralize_markers(text)
        self.assertEqual(gate_ledger.parse_gate_run_blocks(out), [])
        self.assertEqual(note_inbox.parse(out), [])
        return out

    def test_fixtures_parse_before_neutralizing(self):
        self.assertEqual(len(gate_ledger.parse_gate_run_blocks(GATE)), 1)
        self.assertEqual(len(note_inbox.parse(NOTE)), 1)

    def test_every_namespace_is_neutralized(self):
        out = self.assert_inert(GATE + "\n" + NOTE)
        self.assertIn("> | **✅ gate:plan_approved**", out)
        self.assertIn("> | **✉ note:t5**", out)

    def test_parser_whitespace_forms_are_neutralized(self):
        nbsp = GATE.replace("✅ gate", "✅ gate")
        lsep = "prose " + GATE
        self.assertEqual(len(gate_ledger.parse_gate_run_blocks(nbsp + lsep)), 2)
        self.assert_inert(nbsp + lsep)

    def test_everything_else_is_byte_identical(self):
        text = ("> **Note:** keep\n> | **✅ gate:x** already inert\n"
                "## Gate Runs\nplain\r\nno newline at end")
        self.assertEqual(ledger_block.neutralize_markers(text), text)


if __name__ == "__main__":
    unittest.main()
