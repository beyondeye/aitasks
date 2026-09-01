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

**These were observations, not requirements — and t1657_2 has now changed two of
them.** Cases 3 and 4 below originally recorded a *limitation*: a divergent or
one-sided ``## Inbox`` conflicted the whole body, because the section was
unregistered and therefore lived in the prose head. t1657_2 registered
``INBOX_SPEC`` (ahead of the gate spec) and those two cases now assert a
per-section **union** instead. They are named ``test_divergent_inbox_unions_per_section``
and ``test_one_sided_inbox_resolves``. The remaining cases are untouched
characterizations.

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

# A '## Inbox' section in the REAL t1657_2 format. Its marker namespace is
# 'note', and it carries id=/at= rather than run=/attempt= — the exact reason
# the gate spec's validation, identity and ordering keys do not transfer to it
# (t1657_1 F5).
#
# t1657_2 note: these fixtures were originally sketched with placeholder ids
# ('.aa') and no provenance, because the writer did not exist yet. Registering
# INBOX_SPEC makes the section VALIDATED, so they now carry the real shape —
# 24-hex id suffix and the full provenance set. Without that the union would
# (correctly) reject them and bail the body to conflict markers.
_INBOX_COMMENT = ("<!-- Appended by the note framework. Do not edit by hand; "
                  "use `./ait note`. -->")
_OID_A = "a" * 40
_OID_B = "b" * 40


def _inbox(sender: str, iso: str, suffix: str, body: str, oid: str) -> str:
    return (
        "## Inbox\n"
        f"{_INBOX_COMMENT}\n"
        "\n"
        f"> **✉ note:{sender}** id={iso}.{suffix} from={sender} at={iso} "
        f"base={oid} base_branch=main dirty=no host=pc1\n"
        ">\n"
        f"> | {body}\n"
    )


_INBOX_T349 = _inbox("t349", "2026-09-01T10:00:00Z", "a" * 24,
                     "first note body", _OID_A)
_INBOX_T350 = _inbox("t350", "2026-09-01T11:00:00Z", "b" * 24,
                     "second note body", _OID_B)


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

        # _split_gate_section is the legacy single-spec wrapper: it passes
        # (GATE_SPEC,) explicitly, so the boundary is the first '## Gate Runs'
        # and everything before it — including a whole foreign section — is
        # 'head'. That is why this stays true even though t1657_2 registered
        # '## Inbox' globally; merge_body(), which uses REGISTERED_SPECS, now
        # splits the two sections apart (see ForeignSectionUnionTest).
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

    def test_divergent_inbox_unions_per_section(self):
        """The limitation this test used to record is GONE (t1657_2).

        It previously asserted that two PCs appending different notes conflicts
        the whole body, because '## Inbox' was unregistered and therefore lived
        in the prose head. Registering INBOX_SPEC makes it a real section, so
        the two notes now union like any append-only ledger.
        """
        a = _blk("tests_pass", "pass", "2026-06-30T10:00:00Z")
        merged, resolved = merge_body(_with_inbox(_INBOX_T349, a),
                                      _with_inbox(_INBOX_T350, a))

        self.assertTrue(resolved)
        self.assertNotIn("<<<<<<<", merged)
        self.assertIn("note:t349", merged)
        self.assertIn("note:t350", merged)
        # One section, and ordered by (at, id) — t349 at 10:00 before t350 at 11:00.
        self.assertEqual(merged.count("## Inbox"), 1)
        self.assertLess(merged.index("note:t349"), merged.index("note:t350"))

    def test_one_sided_inbox_resolves(self):
        """The common concurrent-append case: one PC appends, the other has not.

        This is the case that mattered most and was worst before t1657_2 — an
        unregistered Inbox put the note in the prose head, so a one-sided append
        conflicted the ENTIRE task-file body. It now resolves.
        """
        a = _blk("tests_pass", "pass", "2026-06-30T10:00:00Z")
        merged, resolved = merge_body(_with_inbox(_INBOX_T349, a),
                                      _HEAD + _ledger(a))

        self.assertTrue(resolved)
        self.assertNotIn("<<<<<<<", merged)
        self.assertIn("note:t349", merged)


if __name__ == "__main__":
    unittest.main()
