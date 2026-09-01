"""Risk mitigation ``union_inbox_roundtrip`` (t1657_2).

Drives the **real registered** ``INBOX_SPEC`` through ``aitask_merge.merge_body``
-- not the synthetic spec ``test_ledger_block_multisection.py`` uses to prove the
seam is parameterized. That file answers "can the seam take a second spec?"; this
one answers "is the spec we actually shipped correct?", and only the second
question can catch a wrong ``identity`` or ``order_key``.

Why this needs its own coverage: a mis-specified Inbox spec fails **silently**.
The gate spec's three semantics do not transfer -- a note carries ``id=``/``at=``
and neither ``run=`` nor ``attempt=`` -- so with the wrong keys the union would
not error, it would mis-order notes, or collapse every note from one sender onto
a single identity and report a false ambiguous winner. Nothing else in the suite
would notice.

The one-sided case is the headline. Before t1657_2 registered the section,
``## Inbox`` lived in the merge driver's prose head, so one PC appending a note
while the other had not conflicted the **entire task-file body**. That is the
single most common concurrent case for a mailbox.

Run: bash tests/run_all_python_tests.sh --test-dir tests
  or: python3 -m pytest tests/test_inbox_union_roundtrip.py -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                ".aitask-scripts", "board"))
from aitask_merge import merge_body, INBOX_SPEC, REGISTERED_SPECS  # noqa: E402
# Importing aitask_merge also puts ../lib on sys.path.
import gate_ledger  # noqa: E402

_HEAD = "## Task Description\n\nSome content.\n"
_OID = "a" * 40
_COMMENT = ("<!-- Appended by the note framework. Do not edit by hand; "
            "use `./ait note`. -->")


def _note(sender: str, iso: str, suffix: str, body: str = "hi", **over) -> str:
    """One '## Inbox' block in the shipped format."""
    f = {
        "id": f"{iso}.{suffix}",
        "from": sender,
        "at": iso,
        "base": _OID,
        "base_branch": "main",
        "dirty": "no",
        "host": "pc1",
    }
    # Pop the marker-name override BEFORE merging, or it would leak into the
    # marker as a spurious '_name=' field and the name-disagreement test would
    # pass for the wrong reason.
    name = over.pop("_name", sender)
    f.update(over)
    kv = " ".join(f"{k}={v}" for k, v in f.items() if v is not None)
    return f"> **✉ note:{name}** {kv}\n>\n> | {body}\n"


def _inbox(*blocks: str) -> str:
    return f"## Inbox\n{_COMMENT}\n\n" + "\n".join(blocks)


def _ledger(*gates: str) -> str:
    return (f"\n{gate_ledger.SECTION_HEADER}\n{gate_ledger.SECTION_COMMENT}\n\n"
            + "\n\n".join(gates) + "\n")


def _gate(name: str, run: str) -> str:
    return gate_ledger.build_block("", name, "pass", {"run": run})


_N1 = _note("t349", "2026-09-01T10:00:00Z", "1" * 24, "from t349")
_N2 = _note("t350", "2026-09-01T11:00:00Z", "2" * 24, "from t350")
_G1 = _gate("tests_pass", "2026-06-30T10:00:00Z")
_G2 = _gate("lint", "2026-06-30T10:05:00Z")


class RegistrationTest(unittest.TestCase):

    def test_inbox_is_registered_ahead_of_the_gate_ledger(self):
        # Registration order IS rebuild order, and the writer places the Inbox
        # above the ledger -- so a registration in the other order would rebuild
        # merged bodies with the sections swapped.
        headers = [s.header for s in REGISTERED_SPECS]
        self.assertEqual(headers, ["## Inbox", "## Gate Runs"])

    def test_spec_constants_match_the_writer(self):
        # The header/comment the merger rebuilds must be byte-identical to what
        # aitask_note.sh writes, or a round-trip would rewrite the section.
        self.assertEqual(INBOX_SPEC.header, "## Inbox")
        self.assertEqual(INBOX_SPEC.comment, _COMMENT)
        self.assertEqual(INBOX_SPEC.namespace, "note")


class InboxUnionTest(unittest.TestCase):

    def test_one_sided_append_resolves(self):
        """One PC appended a note, the other has not -- the common case.

        This conflicted the WHOLE body before the section was registered.
        """
        local = _HEAD + "\n" + _inbox(_N1) + _ledger(_G1)
        remote = _HEAD + _ledger(_G1)
        merged, resolved = merge_body(local, remote)

        self.assertTrue(resolved)
        self.assertNotIn("<<<<<<<", merged)
        self.assertIn("note:t349", merged)
        self.assertEqual(merged.count("## Inbox"), 1)

    def test_one_sided_append_resolves_in_either_direction(self):
        # Side order must not matter: the union is symmetric.
        local = _HEAD + _ledger(_G1)
        remote = _HEAD + "\n" + _inbox(_N1) + _ledger(_G1)
        merged, resolved = merge_body(local, remote)

        self.assertTrue(resolved)
        self.assertIn("note:t349", merged)

    def test_divergent_appends_union_in_at_order(self):
        local = _HEAD + "\n" + _inbox(_N1) + _ledger(_G1)
        remote = _HEAD + "\n" + _inbox(_N2) + _ledger(_G1)
        merged, resolved = merge_body(local, remote)

        self.assertTrue(resolved)
        self.assertNotIn("<<<<<<<", merged)
        self.assertEqual(merged.count("## Inbox"), 1)
        # Ordered by (at, id): t349 at 10:00 precedes t350 at 11:00.
        self.assertLess(merged.index("note:t349"), merged.index("note:t350"))

    def test_order_is_by_at_not_by_arrival(self):
        """The EARLIER note arriving on the REMOTE side still sorts first.

        A spec that ordered by anything arrival-shaped would pass the previous
        test and fail this one.
        """
        local = _HEAD + "\n" + _inbox(_N2) + _ledger(_G1)   # 11:00 locally
        remote = _HEAD + "\n" + _inbox(_N1) + _ledger(_G1)  # 10:00 remotely
        merged, resolved = merge_body(local, remote)

        self.assertTrue(resolved)
        self.assertLess(merged.index("note:t349"), merged.index("note:t350"))

    def test_many_notes_from_one_sender_all_survive(self):
        """identity is (id,), NOT (name, ...).

        One sender sends many notes. A name-keyed identity would collapse them
        onto a single key and report a false ambiguous winner -- which is why
        t1657_1's handoff called this out explicitly.
        """
        a = _note("t349", "2026-09-01T10:00:00Z", "1" * 24, "first")
        b = _note("t349", "2026-09-01T10:00:01Z", "3" * 24, "second")
        c = _note("t349", "2026-09-01T10:00:02Z", "4" * 24, "third")
        merged, resolved = merge_body(_HEAD + "\n" + _inbox(a, b) + _ledger(_G1),
                                      _HEAD + "\n" + _inbox(a, c) + _ledger(_G1))

        self.assertTrue(resolved)
        self.assertNotIn("<<<<<<<", merged)
        self.assertEqual(merged.count("note:t349"), 3)
        for body in ("first", "second", "third"):
            self.assertIn(body, merged)

    def test_duplicate_id_with_different_text_conflicts(self):
        # Two DISTINCT blocks sharing one identity violates the append-only
        # contract; the union must bail rather than pick a winner.
        a = _note("t349", "2026-09-01T10:00:00Z", "1" * 24, "one text")
        b = _note("t349", "2026-09-01T10:00:00Z", "1" * 24, "OTHER text")
        merged, resolved = merge_body(_HEAD + "\n" + _inbox(a) + _ledger(_G1),
                                      _HEAD + "\n" + _inbox(b) + _ledger(_G1))

        self.assertFalse(resolved)
        self.assertIn("<<<<<<<", merged)

    def test_identical_id_and_text_dedups(self):
        merged, resolved = merge_body(_HEAD + "\n" + _inbox(_N1) + _ledger(_G1),
                                      _HEAD + "\n" + _inbox(_N1) + _ledger(_G1))
        self.assertTrue(resolved)
        self.assertEqual(merged.count("note:t349"), 1)

    def test_both_sections_present_only_one_divergent(self):
        """A divergent Inbox must not stop the gate ledger unioning, or vice versa."""
        merged, resolved = merge_body(
            _HEAD + "\n" + _inbox(_N1) + _ledger(_G1, _G2),
            _HEAD + "\n" + _inbox(_N2) + _ledger(_G1))

        self.assertTrue(resolved)
        self.assertNotIn("<<<<<<<", merged)
        self.assertIn("note:t349", merged)
        self.assertIn("note:t350", merged)
        self.assertIn("gate:lint", merged)
        # Rebuilt in registered order: Inbox above the ledger, matching what the
        # writer produces.
        self.assertLess(merged.index("## Inbox"), merged.index("## Gate Runs"))


class InboxValidationTest(unittest.TestCase):
    """Reject, never repair -- a non-conforming block bails the whole body.

    These are MERGE cases, not writer-output checks, and that distinction is the
    point: the merge driver consumes blocks written by ANOTHER PC, which is the
    only route a malformed or abbreviated value actually arrives from. A
    writer-side test structurally cannot see it.
    """

    def _bails(self, bad_block: str, msg: str):
        merged, resolved = merge_body(
            _HEAD + "\n" + _inbox(bad_block) + _ledger(_G1),
            _HEAD + "\n" + _inbox(_N2) + _ledger(_G1))
        self.assertFalse(resolved, msg)
        self.assertIn("<<<<<<<", merged, msg)

    def test_abbreviated_base_is_rejected(self):
        # The exact value the dogfood note carried before expansion.
        self._bails(_note("t349", "2026-09-01T10:00:00Z", "1" * 24,
                          base="451dd3af7"),
                    "an abbreviated base must not union")

    def test_malformed_id_is_rejected(self):
        self._bails(_note("t349", "2026-09-01T10:00:00Z", "1" * 24, id="nope"),
                    "a malformed id must not union")

    def test_missing_id_is_rejected(self):
        # identity is (id,), so a missing id would key every malformed block on
        # ("",) and collide two unrelated blocks as one entry.
        self._bails(_note("t349", "2026-09-01T10:00:00Z", "1" * 24, id=None),
                    "a missing id must not union")

    def test_non_iso_at_is_rejected(self):
        self._bails(_note("t349", "2026-09-01T10:00:00Z", "1" * 24, at="yesterday"),
                    "a non-ISO at must not union")

    def test_name_disagreeing_with_from_is_rejected(self):
        # The marker name IS the sender; a disagreement is a malformed block.
        self._bails(_note("t349", "2026-09-01T10:00:00Z", "1" * 24, _name="t999"),
                    "name/from disagreement must not union")

    def test_from_verified_no_is_rejected(self):
        # The writer OMITS the field rather than writing 'no', so absence and
        # disproof stay distinct. A literal 'no' is out of vocabulary.
        self._bails(_note("t349", "2026-09-01T10:00:00Z", "1" * 24,
                          from_verified="no"),
                    "from_verified=no must not union")

    def test_base_branch_beside_a_sentinel_is_rejected(self):
        # No repo => no branch.
        self._bails(_note("t349", "2026-09-01T10:00:00Z", "1" * 24,
                          base="none", dirty="unknown"),
                    "base_branch beside base=none must not union")

    def test_mergebase_without_a_real_base_is_rejected(self):
        self._bails(_note("t349", "2026-09-01T10:00:00Z", "1" * 24,
                          base="unknown", base_branch=None,
                          base_mergebase="b" * 40),
                    "base_mergebase without a real base must not union")

    def test_out_of_vocabulary_dirty_is_rejected(self):
        self._bails(_note("t349", "2026-09-01T10:00:00Z", "1" * 24, dirty="maybe"),
                    "dirty=maybe must not union")

    def test_missing_host_is_rejected(self):
        self._bails(_note("t349", "2026-09-01T10:00:00Z", "1" * 24, host=None),
                    "a missing host must not union")

    def test_dirty_unknown_with_a_real_base_is_rejected(self):
        # 'unknown' IFF base=none, fail-closed in BOTH directions: this half is
        # a refusal to measure something measurable.
        self._bails(_note("t349", "2026-09-01T10:00:00Z", "1" * 24,
                          dirty="unknown"),
                    "dirty=unknown with a real base must not union")

    def test_dirty_no_with_base_none_is_rejected(self):
        # ...and this half is a fabricated observation.
        self._bails(_note("t349", "2026-09-01T10:00:00Z", "1" * 24,
                          base="none", base_branch=None, dirty="no"),
                    "dirty=no with no repository must not union")

    def test_receipt_carrying_provenance_is_rejected(self):
        # Receipts are not tree-relative claims (t1657_3 ships them).
        bad = ("> **👁 note:read** id=2026-09-01T10:00:00Z." + "5" * 24
               + " by=t357 at=2026-09-01T10:00:00Z mode=explicit"
               + " ids=2026-09-01T10:00:00Z." + "1" * 24
               + f" base={_OID}\n")
        self._bails(bad, "a receipt with provenance must not union")

    def test_receipt_with_a_bad_mode_is_rejected(self):
        bad = ("> **👁 note:read** id=2026-09-01T10:00:00Z." + "5" * 24
               + " by=t357 at=2026-09-01T10:00:00Z mode=sideways"
               + " ids=2026-09-01T10:00:00Z." + "1" * 24 + "\n")
        self._bails(bad, "an out-of-vocabulary mode must not union")

    def test_receipt_missing_ids_is_rejected(self):
        bad = ("> **👁 note:read** id=2026-09-01T10:00:00Z." + "5" * 24
               + " by=t357 at=2026-09-01T10:00:00Z mode=explicit\n")
        self._bails(bad, "a receipt with no ids= must not union")


class InboxUnknownKeyTest(unittest.TestCase):
    """Unknown and cross-variant keys are REJECTED, not ignored (F20).

    A permissive validator silently accepts exactly the blocks it exists to
    catch. Each of these was measured unioning before the key-set check landed.
    """

    def _bails(self, block: str, msg: str):
        merged, resolved = merge_body(
            _HEAD + "\n" + _inbox(block) + _ledger(_G1),
            _HEAD + "\n" + _inbox(_N2) + _ledger(_G1))
        self.assertFalse(resolved, msg)
        self.assertIn("<<<<<<<", merged, msg)

    def test_unknown_key_is_rejected(self):
        self._bails(_note("t349", "2026-09-01T10:00:00Z", "1" * 24, bogus="1"),
                    "an unrecognized marker key must not union")

    def test_migrated_no_is_rejected(self):
        # Keyed on PRESENCE, not == "yes": a block claiming the variant without
        # satisfying it is malformed, not an ordinary note.
        self._bails(_note("t349", "2026-09-01T10:00:00Z", "1" * 24,
                          migrated="no"),
                    "migrated=no must not fall through to the ordinary branch")

    def test_claimed_at_on_an_ordinary_note_is_rejected(self):
        self._bails(_note("t349", "2026-09-01T10:00:00Z", "1" * 24,
                          claimed_at="2026-09-01"),
                    "claimed_at is a migration-only key")

    def test_garbage_claimed_at_on_a_migrated_note_is_rejected(self):
        self._bails(_note("t357", "2026-09-01T10:00:00Z", "1" * 24,
                          **{"from": "thinking_app#357", "_name": "t357",
                             "claimed_at": "garbage", "migrated": "yes",
                             "dirty": None, "host": None}),
                    "a free-text claimed_at must not union")

    def test_migrated_note_carrying_dirty_is_rejected(self):
        self._bails(_note("t357", "2026-09-01T10:00:00Z", "1" * 24,
                          **{"from": "thinking_app#357", "_name": "t357",
                             "claimed_at": "2026-09-01", "migrated": "yes",
                             "host": None}),
                    "a migrated block must not carry a measured dirty")

    def test_ordinary_note_missing_a_required_key_is_rejected(self):
        self._bails(_note("t349", "2026-09-01T10:00:00Z", "1" * 24, host=None),
                    "a required key must be present")

    def test_receipt_with_an_extra_key_is_rejected(self):
        bad = ("> **👁 note:read** id=2026-09-01T10:00:00Z." + "5" * 24
               + " by=t357 at=2026-09-01T10:00:00Z mode=explicit"
               + " ids=2026-09-01T10:00:00Z." + "1" * 24 + " extra=1\n")
        self._bails(bad, "a receipt with an extra key must not union")


class InboxPositiveValidationTest(unittest.TestCase):
    """The complements -- so the rejections above are discriminating, not blanket."""

    def _unions(self, block: str, msg: str):
        merged, resolved = merge_body(
            _HEAD + "\n" + _inbox(block) + _ledger(_G1),
            _HEAD + "\n" + _inbox(_N2) + _ledger(_G1))
        self.assertTrue(resolved, msg)
        self.assertNotIn("<<<<<<<", merged, msg)

    def test_full_40_hex_base_unions(self):
        self._unions(_note("t349", "2026-09-01T10:00:00Z", "1" * 24),
                     "a full 40-hex base must union")

    def test_full_64_hex_base_unions(self):
        # sha256 repositories.
        self._unions(_note("t349", "2026-09-01T10:00:00Z", "1" * 24,
                           base="c" * 64),
                     "a full 64-hex base must union")

    def test_no_repo_sentinel_pair_unions(self):
        self._unions(_note("t349", "2026-09-01T10:00:00Z", "1" * 24,
                           base="none", base_branch=None, dirty="unknown"),
                     "base=none with dirty=unknown must union")

    def test_unborn_branch_keeps_a_measured_dirty(self):
        # base=unknown does NOT take the sentinel: git status still reports.
        self._unions(_note("t349", "2026-09-01T10:00:00Z", "1" * 24,
                           base="unknown", base_branch=None, dirty="yes"),
                     "base=unknown with a measured dirty must union")

    def test_migrated_block_validates_without_dirty_or_host(self):
        # The migration variant: provenance is CLAIMED, not observed, so
        # dirty/host/from_verified are absent BY CONTRACT.
        self._unions(_note("t357", "2026-09-01T10:00:00Z", "1" * 24,
                           **{"from": "thinking_app#357", "_name": "t357",
                              "claimed_at": "2026-09-01", "migrated": "yes",
                              "dirty": None, "host": None}),
                     "a migrated block must union without dirty/host")

    def test_cross_repo_sender_with_the_local_marker_name_unions(self):
        self._unions(_note("t357", "2026-09-01T10:00:00Z", "1" * 24,
                           **{"from": "thinking_app#357", "_name": "t357",
                              "claimed_at": "2026-09-01", "migrated": "yes",
                              "dirty": None, "host": None}),
                     "cross-repo from= with a t<id> marker name must union")

    def test_from_verified_yes_unions(self):
        self._unions(_note("t349", "2026-09-01T10:00:00Z", "1" * 24,
                           from_verified="yes"),
                     "from_verified=yes must union")


if __name__ == "__main__":
    unittest.main()
