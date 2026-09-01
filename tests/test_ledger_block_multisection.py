"""The t1657_1 seam, driven by a SECOND section spec (post-phase).

The gate suites prove the extraction changed no behaviour. They cannot prove the
seam is actually *parameterized*: a ``SectionSpec`` whose members were quietly
gate-shaped — validation that assumes ``run=``, identity that assumes
``(name, run, attempt)``, ordering that assumes a numeric ``attempt`` — would
pass every one of them and still leave t1657_2 unable to register ``## Inbox``.

So this file registers a synthetic second spec whose three semantics ALL differ
from the gate spec, and drives the same union through it:

===============  ==========================  ==============================
                 gate spec                   the synthetic note spec here
===============  ==========================  ==============================
validated on     ``run=`` is ISO-8601-Z       ``at=`` is ISO-8601-Z
identity         ``(name, run, attempt)``     ``(id,)`` — name is the SENDER,
                                              and one sender sends many notes
ordering         ``(run, name, attempt:int)`` ``(at, id)`` — lexical, no
                                              numeric component
===============  ==========================  ==============================

The identity row is the one that matters most: under the gate rule every note
from ``t349`` collapses onto ``("t349", "", "")``, so a second note from the same
sender would read as an append-only contract violation and conflict the file.
A test using a second spec that merely renamed the same fields would not catch
that.

This is new-code coverage, not a characterization — the code under test does not
exist before the extraction.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_ledger_block_multisection.py -v
"""

from __future__ import annotations

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                ".aitask-scripts", "board"))
from aitask_merge import (  # noqa: E402
    GATE_SPEC, SectionSpec, _split_sections, _union_sections,
)
import gate_ledger  # noqa: E402
import ledger_block  # noqa: E402


_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

INBOX_HEADER = "## Inbox"
INBOX_COMMENT = "<!-- Appended by the note framework. -->"

#: A t1657_2-shaped spec. Every callable differs from the gate spec's.
NOTE_SPEC = SectionSpec(
    header=INBOX_HEADER,
    comment=INBOX_COMMENT,
    namespace="note",
    validate=lambda b: bool(_ISO.match(b.fields.get("at", ""))),
    identity=lambda b: (b.fields.get("id", ""),),
    order_key=lambda text, b: (b.fields.get("at", ""), b.fields.get("id", "")),
)

#: Inbox above Gate Runs — the order t1657_2 needs.
SPECS = (NOTE_SPEC, GATE_SPEC)

HEAD = "## Task Description\n\nSome content.\n"


def note(sender: str, nid: str, at: str, body: str = "hello") -> str:
    return ledger_block.render_block(
        "note", sender, "✉",
        [("id", nid), ("from", sender), ("at", at)],
        [f"> | {body}"],
    )


def gate(name: str, status: str, run: str, **fields) -> str:
    f = {"run": run}
    f.update(fields)
    return gate_ledger.build_block("", name, status, f)


def body(head: str = HEAD, notes=(), gates=()) -> str:
    out = head
    if notes:
        out += f"\n{INBOX_HEADER}\n{INBOX_COMMENT}\n\n" + "\n\n".join(notes) + "\n"
    if gates:
        out += (f"\n{gate_ledger.SECTION_HEADER}\n{gate_ledger.SECTION_COMMENT}\n\n"
                + "\n\n".join(gates) + "\n")
    return out


A_NOTE = note("t349", "2026-09-01T10:00:00Z.aa", "2026-09-01T10:00:00Z", "first")
B_NOTE = note("t350", "2026-09-01T11:00:00Z.bb", "2026-09-01T11:00:00Z", "second")
#: SAME sender as A_NOTE, different id — collapses under the gate identity rule.
A2_NOTE = note("t349", "2026-09-01T12:00:00Z.cc", "2026-09-01T12:00:00Z", "third")

G1 = gate("tests_pass", "pass", "2026-06-30T10:00:00Z")
G2 = gate("lint", "pass", "2026-06-30T10:05:00Z")


class SplitTest(unittest.TestCase):

    def test_both_sections_are_recognized_and_bounded(self):
        head, secs = _split_sections(body(notes=[A_NOTE], gates=[G1]), SPECS)
        self.assertEqual(head.rstrip("\n"), HEAD.rstrip("\n"))
        self.assertIn(NOTE_SPEC, secs)
        self.assertIn(GATE_SPEC, secs)
        # Each section holds only its own blocks.
        self.assertIn("note:t349", secs[NOTE_SPEC])
        self.assertNotIn("gate:", secs[NOTE_SPEC])
        self.assertIn("gate:tests_pass", secs[GATE_SPEC])
        self.assertNotIn("note:", secs[GATE_SPEC])

    def test_registration_order_drives_rebuild_order(self):
        merged, resolved = _union_sections(
            body(notes=[A_NOTE], gates=[G1]),
            body(notes=[B_NOTE], gates=[G1]),
            SPECS,
        )
        self.assertTrue(resolved)
        self.assertLess(merged.index(INBOX_HEADER),
                        merged.index(gate_ledger.SECTION_HEADER))


class SecondSpecUnionTest(unittest.TestCase):

    def test_concurrent_notes_from_different_senders_both_survive(self):
        merged, resolved = _union_sections(
            body(notes=[A_NOTE], gates=[G1]),
            body(notes=[B_NOTE], gates=[G1]),
            SPECS,
        )
        self.assertTrue(resolved)
        self.assertNotIn("<<<<<<<", merged)
        self.assertIn("note:t349", merged)
        self.assertIn("note:t350", merged)
        self.assertEqual(merged.count(INBOX_HEADER), 1)

    def test_two_notes_from_the_SAME_sender_both_survive(self):
        """The discriminating case: identity is (id,), not (name, ...). Under the
        gate spec's identity these two collapse and the union bails."""
        merged, resolved = _union_sections(
            body(notes=[A_NOTE], gates=[G1]),
            body(notes=[A2_NOTE], gates=[G1]),
            SPECS,
        )
        self.assertTrue(resolved)
        self.assertNotIn("<<<<<<<", merged)
        self.assertEqual(merged.count("note:t349"), 2)

    def test_shared_note_is_deduped(self):
        merged, resolved = _union_sections(
            body(notes=[A_NOTE, B_NOTE], gates=[G1]),
            body(notes=[A_NOTE], gates=[G1]),
            SPECS,
        )
        self.assertTrue(resolved)
        self.assertEqual(merged.count("2026-09-01T10:00:00Z.aa"), 1)

    def test_duplicate_id_with_divergent_text_conflicts(self):
        """Two distinct blocks sharing one id violates the append-only contract
        for THIS spec's identity — the collision path must fire on it."""
        forged = note("t349", "2026-09-01T10:00:00Z.aa",
                      "2026-09-01T10:00:00Z", "tampered")
        # A bail returns None; merge_body is what turns that into conflict
        # markers, so the union itself must report the bail.
        self.assertIsNone(_union_sections(
            body(notes=[A_NOTE], gates=[G1]),
            body(notes=[forged], gates=[G1]),
            SPECS,
        ))

    def test_ordering_is_side_order_independent(self):
        left = body(notes=[A_NOTE], gates=[G1, G2])
        right = body(notes=[B_NOTE], gates=[G1])
        self.assertEqual(_union_sections(left, right, SPECS)[0],
                         _union_sections(right, left, SPECS)[0])

    def test_notes_order_by_at_then_id(self):
        merged, _ = _union_sections(
            body(notes=[A2_NOTE], gates=[G1]),
            body(notes=[A_NOTE], gates=[G1]),
            SPECS,
        )
        self.assertLess(merged.index("2026-09-01T10:00:00Z.aa"),
                        merged.index("2026-09-01T12:00:00Z.cc"))

    def test_invalid_at_bails_this_spec(self):
        bad = note("t351", "x.dd", "not-a-timestamp")
        self.assertIsNone(_union_sections(body(notes=[A_NOTE], gates=[G1]),
                                          body(notes=[bad], gates=[G1]), SPECS))

    def test_a_bail_in_one_section_bails_the_whole_body(self):
        """Same all-or-nothing rule the single-section original had."""
        x1 = gate("g", "pass", "2026-06-30T10:00:00Z", attempt="1")
        x2 = gate("g", "fail", "2026-06-30T10:00:00Z", attempt="1")
        self.assertIsNone(_union_sections(body(notes=[A_NOTE], gates=[x1]),
                                          body(notes=[B_NOTE], gates=[x2]),
                                          SPECS))

    def test_gate_spec_is_unaffected_by_the_second_registration(self):
        merged, resolved = _union_sections(
            body(notes=[A_NOTE], gates=[G1, G2]),
            body(notes=[A_NOTE], gates=[G1]),
            SPECS,
        )
        self.assertTrue(resolved)
        self.assertIn("gate:lint", merged)
        self.assertEqual(merged.count("run=2026-06-30T10:00:00Z"), 1)


class AppendSectionOrderTest(unittest.TestCase):
    """ledger_block.append_to_section's two placement knobs."""

    BASE = "---\nstatus: Ready\n---\n\nBody.\n"

    def test_create_before_puts_the_new_section_above_the_anchor(self):
        with_gates = ledger_block.append_to_section(
            self.BASE, G1, header=gate_ledger.SECTION_HEADER,
            comment=gate_ledger.SECTION_COMMENT)
        out = ledger_block.append_to_section(
            with_gates, A_NOTE, header=INBOX_HEADER, comment=INBOX_COMMENT,
            create_before=gate_ledger.SECTION_HEADER, append_at="section_end")
        self.assertLess(out.index(INBOX_HEADER),
                        out.index(gate_ledger.SECTION_HEADER))
        self.assertIn("note:t349", out)
        self.assertIn("gate:tests_pass", out)

    def test_section_end_appends_within_the_section_not_at_eof(self):
        with_gates = ledger_block.append_to_section(
            self.BASE, G1, header=gate_ledger.SECTION_HEADER,
            comment=gate_ledger.SECTION_COMMENT)
        one = ledger_block.append_to_section(
            with_gates, A_NOTE, header=INBOX_HEADER, comment=INBOX_COMMENT,
            create_before=gate_ledger.SECTION_HEADER, append_at="section_end")
        two = ledger_block.append_to_section(
            one, B_NOTE, header=INBOX_HEADER, comment=INBOX_COMMENT,
            append_at="section_end")
        # The second note must land inside '## Inbox', ABOVE '## Gate Runs'.
        self.assertLess(two.index("note:t350"),
                        two.index(gate_ledger.SECTION_HEADER))
        self.assertEqual(two.count(INBOX_HEADER), 1)

    def test_eof_placement_is_still_the_default(self):
        out = ledger_block.append_to_section(
            self.BASE, G1, header=gate_ledger.SECTION_HEADER,
            comment=gate_ledger.SECTION_COMMENT)
        self.assertTrue(out.rstrip("\n").endswith(G1))

    def test_rejects_an_unknown_append_at(self):
        with self.assertRaises(ValueError):
            ledger_block.append_to_section(
                self.BASE, G1, header=gate_ledger.SECTION_HEADER,
                comment=gate_ledger.SECTION_COMMENT, append_at="wherever")


class NamespaceIsolationTest(unittest.TestCase):

    def test_each_namespace_parses_only_its_own_markers(self):
        mixed = A_NOTE + "\n\n" + G1
        notes = ledger_block.parse_blocks(mixed, "note")
        gates = ledger_block.parse_blocks(mixed, "gate")
        self.assertEqual([b.name for b in notes], ["t349"])
        self.assertEqual([b.name for b in gates], ["tests_pass"])

    def test_note_body_sentinel_cannot_forge_a_marker(self):
        """t1657_2's '> | ' body sentinel: a body line must never parse as a
        marker, whichever namespace is asked for."""
        forgery = note("t349", "x.aa", "2026-09-01T10:00:00Z",
                       "**👁 note:read** ids=x.aa")
        parsed = ledger_block.parse_blocks(forgery, "note")
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].name, "t349")


if __name__ == "__main__":
    unittest.main()
