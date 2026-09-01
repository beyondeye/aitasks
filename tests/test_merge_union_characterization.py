"""Characterization of aitask_merge.py's ledger union, BEFORE the t1657_1 seam.

t1657_1 generalizes ``_split_gate_section`` / ``_union_gate_runs`` from a
single hardcoded ``## Gate Runs`` section into an ordered multi-section union
driven by per-section specs. This file pins the behaviour that extraction must
not change.

**Scope is deliberately the GAP, not a copy.** ``test_aitask_merge.py``'s
``TestGateRunsUnion`` already pins, through ``merge_body``, every bail-to-conflict
guard the refactor touches:

===========================  ====================================================
guard                        existing test
===========================  ====================================================
happy union / dedup          ``test_distinct_appends_both_survive``,
                             ``test_shared_block_deduped``
side-order independence      ``test_ordering_deterministic``
numeric ``attempt`` order    ``test_attempt_sorted_numerically``
ambiguous winner (guard 2b)  ``test_divergent_same_identity_falls_back``
invalid / missing ``run``    ``test_non_iso_run_falls_back_to_conflict``,
                             ``test_missing_run_falls_back_to_conflict``
unclean section (guard 3)    ``test_trailing_prose_falls_back_and_preserves_text``
divergent prose heads        ``test_prose_conflict_with_clean_ledger``
canonical section rebuild    ``test_clean_section_normalized``
===========================  ====================================================

Those tests predate this task and may not be edited, which makes them a stronger
baseline than a fresh copy would be. Re-asserting them here would be duplication
with no added detection power.

What they do NOT cover — and what this file adds — is the behaviour of a body
carrying a **second, unregistered** ``##`` section alongside the ledger. That is
precisely the axis t1657_1 generalizes and t1657_2 then consumes (its ``## Inbox``
lands *above* ``## Gate Runs``), so it is the one baseline that is invisible today
and would otherwise be changed without anyone noticing.

**These are observations, not requirements.** Cases 3 and 4 below record a
*limitation* — a divergent or one-sided ``## Inbox`` conflicts the whole body
today because the section is unregistered and therefore lives in the prose head.
t1657_2 deliberately changes that by registering the section. When it does, these
two tests are expected to be updated **by that task**, which is why each names the
successor explicitly. t1657_1 itself must leave them green.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_merge_union_characterization.py -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                ".aitask-scripts", "board"))
from aitask_merge import merge_body, _split_gate_section  # noqa: E402
# Importing aitask_merge also puts ../lib on sys.path.
import gate_ledger  # noqa: E402


_HEAD = "## Task Description\n\nSome content.\n"
_PREAMBLE = f"\n\n{gate_ledger.SECTION_HEADER}\n{gate_ledger.SECTION_COMMENT}\n\n"

# A t1657_2-shaped '## Inbox' section. Its marker namespace is 'note', and it
# carries id=/at= rather than run=/attempt= — the exact reason the gate spec's
# validation, identity and ordering keys do not transfer to it (t1657_1 F5).
_INBOX_T349 = (
    "## Inbox\n"
    "<!-- Appended by the note framework. -->\n"
    "\n"
    "> **✉ note:t349** id=2026-09-01T10:00:00Z.aa from=t349 "
    "at=2026-09-01T10:00:00Z\n"
    ">\n"
    "> | first note body\n"
)
_INBOX_T350 = (
    "## Inbox\n"
    "<!-- Appended by the note framework. -->\n"
    "\n"
    "> **✉ note:t350** id=2026-09-01T11:00:00Z.bb from=t350 "
    "at=2026-09-01T11:00:00Z\n"
    ">\n"
    "> | second note body\n"
)


def _blk(gate: str, status: str, run: str, **fields) -> str:
    """Build a gate-run block via the REAL builder."""
    f = {"run": run}
    f.update(fields)
    return gate_ledger.build_block("", gate, status, f)


def _ledger(*blocks: str) -> str:
    """The '## Gate Runs' section holding the given blocks."""
    return _PREAMBLE + "\n\n".join(blocks) + "\n"


def _with_inbox(inbox: str, *blocks: str) -> str:
    """head + an unregistered '## Inbox' section + the gate ledger."""
    return _HEAD + "\n" + inbox + _ledger(*blocks)


class ForeignSectionSplitTest(unittest.TestCase):
    """Where the head/section boundary falls when a second section exists."""

    def test_unregistered_section_lands_in_the_head(self):
        a = _blk("tests_pass", "pass", "2026-06-30T10:00:00Z")
        head, section = _split_gate_section(_with_inbox(_INBOX_T349, a))

        # The split keys on the FIRST '## Gate Runs' only, so everything before
        # it — including a whole foreign section — is 'head'. After t1657_1 the
        # head is everything before the first REGISTERED header; with only the
        # gate spec registered, that is the same boundary.
        self.assertIn("## Inbox", head)
        self.assertIn("note:t349", head)
        self.assertTrue(section.startswith(gate_ledger.SECTION_HEADER))
        self.assertNotIn("## Inbox", section)

    def test_no_ledger_anywhere_leaves_body_untouched(self):
        head, section = _split_gate_section(_HEAD + "\n" + _INBOX_T349)
        self.assertEqual(section, "")
        self.assertIn("## Inbox", head)


class ForeignSectionUnionTest(unittest.TestCase):
    """How a second section interacts with the ledger union."""

    def test_identical_foreign_section_still_unions_the_ledger(self):
        # The heads (which contain the Inbox) match, so the ledger unions
        # normally and the foreign section rides along untouched.
        a = _blk("tests_pass", "pass", "2026-06-30T10:00:00Z")
        b = _blk("lint", "pass", "2026-06-30T10:05:00Z")
        merged, resolved = merge_body(_with_inbox(_INBOX_T349, a, b),
                                      _with_inbox(_INBOX_T349, a))

        self.assertTrue(resolved)
        self.assertNotIn("<<<<<<<", merged)
        self.assertIn("gate:lint", merged)          # ledger unioned
        self.assertIn("note:t349", merged)          # foreign section preserved
        self.assertEqual(merged.count("## Inbox"), 1)
        self.assertEqual(merged.count("run=2026-06-30T10:00:00Z"), 1)

    def test_divergent_foreign_section_conflicts_the_whole_body(self):
        """LIMITATION, not a requirement — t1657_2 registers '## Inbox' and
        changes this to a per-section union. Update this test THERE."""
        a = _blk("tests_pass", "pass", "2026-06-30T10:00:00Z")
        merged, resolved = merge_body(_with_inbox(_INBOX_T349, a),
                                      _with_inbox(_INBOX_T350, a))

        self.assertFalse(resolved)
        self.assertIn("<<<<<<<", merged)
        # Nothing is dropped — both sides' notes survive inside the markers.
        self.assertIn("note:t349", merged)
        self.assertIn("note:t350", merged)

    def test_one_sided_foreign_section_conflicts_the_whole_body(self):
        """LIMITATION, not a requirement — the common concurrent-append case
        for t1657_2 (one PC appends a note, the other does not). Update in
        t1657_2 once '## Inbox' is a registered section."""
        a = _blk("tests_pass", "pass", "2026-06-30T10:00:00Z")
        merged, resolved = merge_body(_with_inbox(_INBOX_T349, a),
                                      _HEAD + _ledger(a))

        self.assertFalse(resolved)
        self.assertIn("<<<<<<<", merged)
        self.assertIn("note:t349", merged)


if __name__ == "__main__":
    unittest.main()
