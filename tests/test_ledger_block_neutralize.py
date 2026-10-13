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


class MarkerBlockMaskTests(unittest.TestCase):
    """``marker_block_mask`` gives a block the extent ``parse_blocks`` does (t1966)."""

    # Namespaces never touch: a gate block runs on through an adjacent note
    # marker in parse_blocks (it stops only at its own namespace), which is the
    # adjacency plan_paths' FRAMEWORK_RUN_SEPARATOR exists to prevent.
    CORPUS = (GATE + ">\n> Log: logs/a.md\n\n"          # gate, blank inside
              + "prose ends the gate block\n"
              + NOTE + "\n"
              + "plain prose ends the note block\n"
              + GATE.replace("attempt=1", "attempt=2")      # ended by a header
              + "## Merged from t3: x\n"
              + GATE.replace("attempt=1", "attempt=3")      # ended by its own
              + GATE.replace("attempt=1", "attempt=4")      # namespace, then prose
              + "prose\n"
              + "> | **✅ gate:plan_approved** inert\n"    # neutralized: no block
              + "> **Note:** an ordinary bold quote\n")

    def test_masked_markers_are_the_parsed_markers(self):
        lines = self.CORPUS.splitlines(keepends=True)
        mask = ledger_block.marker_block_mask(lines)
        parsed = {b.line_number for b in gate_ledger.parse_gate_run_blocks(self.CORPUS)}
        parsed |= {b.line_number for b in note_inbox.parse(self.CORPUS)}
        masked_markers = {i + 1 for i, line in enumerate(lines)
                          if mask[i] and ledger_block._ANY_MARKER_RE.match(line)}
        self.assertEqual(len(parsed), 5)
        self.assertEqual(masked_markers, parsed)

    def test_masked_bodies_are_the_parsed_bodies(self):
        lines = self.CORPUS.splitlines(keepends=True)
        mask = ledger_block.marker_block_mask(lines)
        masked = [line.rstrip("\n") for i, line in enumerate(lines) if mask[i]
                  and line.strip() and not ledger_block._ANY_MARKER_RE.match(line)]
        blocks = gate_ledger.parse_gate_run_blocks(self.CORPUS) + note_inbox.parse(self.CORPUS)
        parsed = sorted(l for b in blocks for l in b.raw_body_lines)
        self.assertEqual(sorted(masked), parsed)

    def test_non_block_lines_are_unmasked(self):
        lines = self.CORPUS.splitlines(keepends=True)
        mask = ledger_block.marker_block_mask(lines)
        for i, line in enumerate(lines):
            if line.startswith(("plain", "## ", "prose", "> | **", "> **Note")):
                self.assertFalse(mask[i], line)


if __name__ == "__main__":
    unittest.main()
