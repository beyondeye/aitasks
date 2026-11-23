#!/usr/bin/env python3
"""Tests for the frozen agent's sitrep state (t2337).

Part 1 pins `agent_sessions.capture_harvested` -- the drop/purge safety
verdict -- across every receipt shape, BEFORE and AFTER the receipt gained
its link lines (`links=` / `triage=` / `review=`). Extra trailing lines must
never change the verdict.

Part 2 covers lib/frozen_sitrep.py: one case per state, the fail-closed
`unknown` inputs, and the publish gate under every race the module doc names
(a settled replacement, a change on both attempts, a rewrite during a
cache-hit store read, an empty capture seen mid-rewrite, an unsettled record).
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_sessions  # noqa: E402
import frozen_sitrep as fs  # noqa: E402
import sitrep_harvest  # noqa: E402
import sitrep_todo  # noqa: E402


def _base_receipt(data: bytes, store: str = "/x/.aitask-sitrep") -> str:
    return (f"sha256={hashlib.sha256(data).hexdigest()}\nstore={store}\n"
            f"cert={agent_sessions.HARVEST_RECEIPT_CERT}\n")


class CaptureHarvestedReceiptShapes(unittest.TestCase):
    """The safety verdict over receipt shapes (pin_receipt_gate_compat)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cap = Path(self._tmp.name) / "capture.txt"
        self.data = b"some agent output\n"
        self.cap.write_bytes(self.data)
        self.rec = agent_sessions.SessionRecord(
            id="0123abcd", root=self._tmp.name, window="agent-pick-1",
            capture_txt=str(self.cap))

    def _receipt(self, text: str) -> None:
        Path(str(self.cap) + agent_sessions.HARVEST_RECEIPT_SUFFIX).write_text(text)

    def test_legacy_base_receipt_certifies(self):
        self._receipt(_base_receipt(self.data))
        self.assertTrue(agent_sessions.capture_harvested(self.rec))

    def test_trailing_link_lines_do_not_change_the_verdict(self):
        self._receipt(_base_receipt(self.data) + "links=1\ntriage=c3\nreview=c4\n")
        self.assertTrue(agent_sessions.capture_harvested(self.rec))

    def test_sha_mismatch_refuses(self):
        self._receipt(_base_receipt(b"other output\n") + "links=1\n")
        self.assertFalse(agent_sessions.capture_harvested(self.rec))

    def test_missing_cert_refuses(self):
        self._receipt(f"sha256={hashlib.sha256(self.data).hexdigest()}\n"
                      "store=/x/.aitask-sitrep\nlinks=1\n")
        self.assertFalse(agent_sessions.capture_harvested(self.rec))

    def test_no_receipt_refuses(self):
        self.assertFalse(agent_sessions.capture_harvested(self.rec))


# --- Part 2: lib/frozen_sitrep.py ------------------------------------------------

def _item(num: int, state: str, kind: str = "question") -> sitrep_todo.Item:
    return sitrep_todo.Item(num=num, rev=num, kind=kind, state=state, group="now",
                            checked_at="never", ref="", derived="script",
                            outcome="", title=f"item {num}")


class _TrackerCase(unittest.TestCase):
    """A scratch session store with one settled frozen record + a store dir."""

    CAPTURE = b"agent output\n"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.sessions = self.tmp / "agent_sessions.json"
        os.environ[agent_sessions.FROZEN_DIR_ENV] = str(self.tmp / "frozen")
        self.addCleanup(os.environ.pop, agent_sessions.FROZEN_DIR_ENV, None)
        self.root = self.tmp / "project"
        self.root.mkdir()
        self.store = self.root / ".aitask-sitrep"
        self.store.mkdir()
        sf = agent_sessions.SessionsFile()
        sf, line = agent_sessions.upsert(
            sf, root=str(self.root), window="agent-pick-7", pane="%3",
            pane_pid=4242, pane_alive=lambda pid: True)
        self.rid = line.split(":")[1].split("|")[0]
        cdir = agent_sessions.ensure_capture_dir(self.rid)
        self.cap = cdir / "capture.txt"
        self.cap.write_bytes(self.CAPTURE)
        (cdir / "capture.ansi").write_bytes(self.CAPTURE)
        sf, line = agent_sessions.freeze_begin(
            sf, self.rid, capture_ansi=str(cdir / "capture.ansi"),
            capture_txt=str(self.cap), lines=1, owner_pid=os.getpid())
        nonce = line.rsplit("|", 1)[1]
        sf, _ = agent_sessions.freeze_commit(sf, self.rid, nonce=nonce,
                                             pane="%3", pane_pid=100)
        self.sf = sf
        agent_sessions.dump(sf, self.sessions)

    def tracker(self, seam=None) -> fs.FrozenSitrepTracker:
        return fs.FrozenSitrepTracker(self.sessions, seam=seam)

    def receipt(self, *, data: "bytes | None" = None, links=True, triage=(),
                review=(), extra: str = "", store: "str | None" = None) -> None:
        data = self.CAPTURE if data is None else data
        store = str(self.store) if store is None else store
        if links:
            text = sitrep_harvest.receipt_text(data, store, triage, review)
        else:
            text = _base_receipt(data, store)
        Path(str(self.cap) + agent_sessions.HARVEST_RECEIPT_SUFFIX
             ).write_text(text + extra)

    def todo(self, *items) -> None:
        store = sitrep_todo.TodoStore(items={it.num: it for it in items})
        (self.store / "todo.md").write_text(sitrep_todo.render_todo(store))

    def state(self, tracker=None) -> fs.FrozenSitrepState:
        tracker = tracker or self.tracker()
        return tracker.states([self.rid])[self.rid]


class StatesTests(_TrackerCase):

    def test_unharvested_without_a_receipt(self):
        st = self.state()
        self.assertEqual(fs.UNHARVESTED, st.state)
        self.assertFalse(st.safe)

    def test_unharvested_on_a_stale_receipt(self):
        self.receipt(data=b"older output\n")
        self.assertEqual(fs.UNHARVESTED, self.state().state)

    def test_unlinked_legacy_receipt_is_safe(self):
        self.receipt(links=False)
        st = self.state()
        self.assertEqual(fs.UNLINKED, st.state)
        self.assertTrue(st.safe)

    def test_nothing_when_linked_without_ids(self):
        self.receipt()
        self.assertEqual(fs.NOTHING, self.state().state)

    def test_nothing_for_a_stable_empty_capture(self):
        self.cap.write_bytes(b"")
        self.assertEqual(fs.NOTHING, self.state().state)

    def test_triage_open(self):
        self.receipt(triage=[3])
        self.todo(_item(3, "open"))
        st = self.state()
        self.assertEqual(fs.TRIAGE_OPEN, st.state)
        self.assertEqual((("c3", "open"),), st.triage)
        self.assertIn("(c3)", fs.describe(st))

    def test_item_state_unknown_counts_as_open(self):
        self.receipt(triage=[3])
        self.todo(_item(3, "unknown"))
        self.assertEqual(fs.TRIAGE_OPEN, self.state().state)

    def test_triaged_only_when_every_triage_question_is_done(self):
        self.receipt(triage=[3, 4])
        self.todo(_item(3, "done"), _item(4, "done"))
        self.assertEqual(fs.TRIAGED, self.state().state)

    def test_a_dismissed_triage_question_is_closed_not_triaged(self):
        self.receipt(triage=[3, 4])
        self.todo(_item(3, "done"), _item(4, "dismissed"))
        st = self.state()
        self.assertEqual(fs.CLOSED, st.state)
        self.assertNotIn("triaged", fs.describe(st))
        self.assertIn("c4 dismissed", fs.describe(st))

    def test_only_a_closed_review_is_closed_not_triaged(self):
        self.receipt(review=[9])
        self.todo(_item(9, "done"))
        st = self.state()
        self.assertEqual(fs.CLOSED, st.state)
        self.assertIn("c9 review done", fs.describe(st))

    def test_triaged_with_a_closed_review_alongside(self):
        self.receipt(triage=[3], review=[9])
        self.todo(_item(3, "done"), _item(9, "dismissed"))
        self.assertEqual(fs.TRIAGED, self.state().state)

    def test_a_long_item_list_is_named_up_to_three_then_counted(self):
        st = fs.FrozenSitrepState(fs.TRIAGE_OPEN, triage=tuple(
            (f"c{n}", "open") for n in range(1, 9)))
        self.assertIn("(c1, c2, c3 +5 more)", fs.describe(st))

    def test_an_open_review_wins(self):
        self.receipt(triage=[3], review=[9])
        self.todo(_item(3, "open"), _item(9, "open"))
        st = self.state()
        self.assertEqual(fs.REVIEW_PENDING, st.state)
        self.assertIn("(c9)", fs.describe(st))

    def test_unknown_is_never_safe_and_never_says_so(self):
        for st in (fs.FrozenSitrepState(fs.UNKNOWN, reason="x"),
                   fs.FrozenSitrepState(fs.UNHARVESTED)):
            self.assertFalse(st.safe)
            self.assertNotIn("safe to drop", fs.describe(st))
        for name in fs.SAFE_STATES:
            self.assertIn("safe to drop", fs.describe(fs.FrozenSitrepState(name)))

    def test_the_instance_is_record_pane_and_standin_pid(self):
        self.receipt()
        self.assertEqual((self.rid, "%3", 100), self.state().instance)


class FailClosedTests(_TrackerCase):

    def test_malformed_link_line(self):
        self.receipt(extra="triage=3\n")
        self.assertEqual("receipt_malformed", self.state().reason)

    def test_an_undecodable_receipt_is_unknown_not_unharvested(self):
        Path(str(self.cap) + agent_sessions.HARVEST_RECEIPT_SUFFIX
             ).write_bytes(b"sha256=\xff\xfe\n")
        st = self.state()
        self.assertEqual("receipt_unreadable", st.reason)
        self.assertFalse(st.safe)

    @unittest.skipIf(os.geteuid() == 0, "root reads mode-000 files")
    def test_an_os_level_receipt_read_failure_is_a_bound_unknown(self):
        self.receipt()
        receipt = Path(str(self.cap) + agent_sessions.HARVEST_RECEIPT_SUFFIX)
        receipt.chmod(0)
        self.addCleanup(receipt.chmod, 0o600)
        tracker = self.tracker()
        st = self.state(tracker)
        self.assertEqual(fs.UNKNOWN, st.state)
        self.assertEqual("PermissionError", st.reason)
        self.assertEqual((self.rid, "%3", 100), st.instance,
                         "bound, so the row shows `sitrep ?` instead of nothing")
        self.assertFalse(st.safe)
        receipt.chmod(0o600)
        self.assertEqual(fs.NOTHING, self.state(tracker).state,
                         "uncached: the same tracker recovers")

    @unittest.skipIf(os.geteuid() == 0, "root reads mode-000 files")
    def test_a_warm_drop_ok_does_not_survive_a_permission_change(self):
        """chmod changes only ctime: the cache key must notice it."""
        self.receipt()
        receipt = Path(str(self.cap) + agent_sessions.HARVEST_RECEIPT_SUFFIX)
        tracker = self.tracker()
        self.assertEqual(fs.NOTHING, self.state(tracker).state)
        self.assertEqual(fs.NOTHING, self.state(tracker).state)   # warm hit
        self.assertEqual(1, tracker.derives)
        receipt.chmod(0)
        self.addCleanup(receipt.chmod, 0o600)
        st = self.state(tracker)
        self.assertEqual(fs.UNKNOWN, st.state, st)
        self.assertFalse(st.safe)
        receipt.chmod(0o600)
        self.assertEqual(fs.NOTHING, self.state(tracker).state)

    def test_a_missing_capture_with_a_leftover_receipt_is_stable_nothing(self):
        self.receipt()
        self.cap.unlink()
        tracker = self.tracker()
        self.assertEqual(fs.NOTHING, self.state(tracker).state)
        self.assertEqual(1, tracker.derives, "settled on the first attempt")

    def test_unknown_links_version(self):
        self.receipt(links=False, extra="links=2\n")
        self.assertEqual(fs.UNKNOWN, self.state().state)

    def test_bad_store_line(self):
        self.receipt(triage=[3], store="relative/.aitask-sitrep")
        self.todo(_item(3, "open"))
        self.assertEqual("receipt_store", self.state().reason)

    def test_store_without_todo(self):
        self.receipt(triage=[3])
        self.assertEqual("store_unreadable", self.state().reason)

    def test_a_store_that_becomes_readable_recovers_in_the_same_tracker(self):
        """`unknown` is never cached: the store can heal with no change to the
        record, capture or receipt (the inputs a cache hit rechecks)."""
        self.receipt(triage=[3])
        tracker = self.tracker()
        self.assertEqual("store_unreadable", self.state(tracker).reason)
        self.todo(_item(3, "open"))
        self.assertEqual(fs.TRIAGE_OPEN, self.state(tracker).state)

    def test_an_item_that_appears_later_recovers_in_the_same_tracker(self):
        self.receipt(triage=[3])
        self.todo(_item(4, "open"))
        tracker = self.tracker()
        self.assertEqual("item_missing:c3", self.state(tracker).reason)
        self.todo(_item(3, "done"), _item(4, "open"))
        self.assertEqual(fs.TRIAGED, self.state(tracker).state)

    def test_damaged_todo(self):
        self.receipt(triage=[3])
        (self.store / "todo.md").write_text("not a store\n")
        self.assertEqual("store_unreadable", self.state().reason)

    def test_item_missing_from_the_store(self):
        self.receipt(triage=[3])
        self.todo(_item(4, "open"))
        self.assertEqual("item_missing:c3", self.state().reason)

    def test_no_record(self):
        st = self.tracker().states(["deadbeef"])["deadbeef"]
        self.assertEqual("no_record", st.reason)

    def test_one_record_failure_leaves_the_others(self):
        self.receipt()
        real = fs.read_evidence
        failing = {"boom": True}

        def read_evidence(rec):
            if failing["boom"]:
                failing["boom"] = False
                raise RuntimeError("injected")
            return real(rec)
        fs.read_evidence = read_evidence
        self.addCleanup(setattr, fs, "read_evidence", real)
        tracker = self.tracker()
        st = tracker.states([self.rid])[self.rid]
        self.assertEqual("RuntimeError", st.reason)
        self.assertFalse(st.safe)
        # Nothing was cached for the failed record; the next pass derives.
        self.assertEqual(fs.NOTHING, tracker.states([self.rid])[self.rid].state)
        out = tracker.states(["deadbeef", self.rid])
        self.assertEqual(fs.NOTHING, out[self.rid].state)
        self.assertEqual("no_record", out["deadbeef"].reason)


class SettledRecordTests(_TrackerCase):

    def _unsettle(self, **fields) -> None:
        rec = self.sf.by_id(self.rid)
        for k, v in fields.items():
            setattr(rec, k, v)
        agent_sessions.dump(self.sf, self.sessions)

    def test_a_freezing_record_is_in_flight(self):
        self.receipt()
        self._unsettle(state=agent_sessions.STATE_FREEZING)
        self.assertEqual("operation_in_flight", self.state().reason)

    def test_a_held_lease_is_in_flight_even_with_an_empty_capture(self):
        self.cap.write_bytes(b"")
        self._unsettle(op_nonce="abcd1234", op_owner_pid=os.getpid(),
                       op_started_at="2026-11-22T10:00:00Z")
        st = self.state()
        self.assertEqual("operation_in_flight", st.reason)
        self.assertFalse(st.safe)


class PublishGateTests(_TrackerCase):

    def test_one_settled_replacement_yields_the_fresh_verdict(self):
        self.receipt()
        fired = []

        def seam(point, rid):
            if point == "candidate" and not fired:
                fired.append(1)
                self.cap.write_bytes(b"a re-freeze wrote new text\n")
        tracker = self.tracker(seam)
        st = self.state(tracker)
        self.assertEqual(fs.UNHARVESTED, st.state, "the stale drop-ok is discarded")
        self.assertEqual(2, tracker.derives)
        tracker.seam = None
        self.assertEqual(fs.UNHARVESTED, self.state(tracker).state)
        self.assertEqual(2, tracker.derives, "the cache holds the new verdict")

    def test_a_change_on_both_attempts_is_unknown_and_uncached(self):
        self.receipt()
        n = [0]

        def seam(point, rid):
            if point == "candidate":
                n[0] += 1
                self.cap.write_bytes(b"change %d\n" % n[0])
        tracker = self.tracker(seam)
        st = self.state(tracker)
        self.assertEqual("changed_during_read", st.reason)
        self.assertFalse(st.safe)
        tracker.seam = None
        before = tracker.derives
        self.receipt(data=self.cap.read_bytes())
        self.assertEqual(fs.NOTHING, self.state(tracker).state)
        self.assertEqual(before + 1, tracker.derives, "nothing was cached")

    def test_a_rewrite_during_a_cache_hit_store_read_is_not_safe(self):
        self.receipt(triage=[3])
        self.todo(_item(3, "done"))
        tracker = self.tracker()
        self.assertEqual(fs.TRIAGED, self.state(tracker).state)

        def seam(point, rid):
            if point == "todo_read" and self.cap.read_bytes() == self.CAPTURE:
                with open(self.cap, "r+b") as fh:   # in place, as _write_private
                    fh.truncate(0)
                    fh.write(b"rewritten in place, longer than before\n")
        tracker.seam = seam
        st = self.state(tracker)
        self.assertFalse(st.safe, st)

    def test_an_empty_capture_seen_mid_rewrite_is_not_nothing(self):
        self.receipt()
        with open(self.cap, "r+b") as fh:
            fh.truncate(0)            # O_TRUNC done, the write not yet
        fired = []

        def seam(point, rid):
            if point == "candidate" and not fired:
                fired.append(1)
                with open(self.cap, "r+b") as fh:
                    fh.write(b"the new capture text\n")
        st = self.state(self.tracker(seam))
        self.assertNotEqual(fs.NOTHING, st.state)
        self.assertFalse(st.safe)

    def test_a_cache_hit_reads_no_capture(self):
        self.receipt(triage=[3])
        self.todo(_item(3, "open"))
        tracker = self.tracker()
        self.state(tracker)
        self.state(tracker)
        self.assertEqual(1, tracker.derives)
        self.assertEqual(1, tracker.parses)

    def test_a_receipt_rewrite_invalidates_the_cache(self):
        self.receipt()
        tracker = self.tracker()
        self.assertEqual(fs.NOTHING, self.state(tracker).state)
        self.receipt(triage=[3])
        self.todo(_item(3, "open"))
        self.assertEqual(fs.TRIAGE_OPEN, self.state(tracker).state)

    def test_a_todo_change_invalidates_the_cache(self):
        self.receipt(triage=[3])
        self.todo(_item(3, "open"))
        tracker = self.tracker()
        self.assertEqual(fs.TRIAGE_OPEN, self.state(tracker).state)
        self.todo(_item(3, "done"))
        self.assertEqual(fs.TRIAGED, self.state(tracker).state)

    def test_a_refreeze_with_the_same_id_is_a_new_instance(self):
        self.receipt()
        tracker = self.tracker()
        self.assertEqual((self.rid, "%3", 100), self.state(tracker).instance)
        rec = self.sf.by_id(self.rid)
        rec.standin_pid = 200
        rec.pane_pid = 200
        agent_sessions.dump(self.sf, self.sessions)
        self.assertEqual((self.rid, "%3", 200), self.state(tracker).instance)


class AgreementTests(_TrackerCase):
    """The badge and the drop gate share ONE certification rule."""

    def test_capture_harvested_and_derive_agree_on_every_shape(self):
        shapes = {
            "none": None,
            "legacy": _base_receipt(self.CAPTURE, str(self.store)),
            "linked": sitrep_harvest.receipt_text(self.CAPTURE, str(self.store)),
            "stale": _base_receipt(b"x\n", str(self.store)),
            "certless": "sha256=%s\nstore=%s\n" % (
                hashlib.sha256(self.CAPTURE).hexdigest(), self.store),
        }
        receipt_path = Path(str(self.cap) + agent_sessions.HARVEST_RECEIPT_SUFFIX)
        for name, text in shapes.items():
            with self.subTest(name):
                if text is None:
                    receipt_path.unlink(missing_ok=True)
                else:
                    receipt_path.write_text(text)
                rec = agent_sessions.load(self.sessions).by_id(self.rid)
                self.assertEqual(agent_sessions.capture_harvested(rec),
                                 self.state().safe)

    def test_link_version_constants_match(self):
        self.assertEqual(sitrep_harvest.RECEIPT_LINKS,
                         agent_sessions.HARVEST_RECEIPT_LINKS)

    def test_store_name_matches(self):
        self.assertEqual(sitrep_harvest.STORE_NAME, fs.STORE_NAME)


if __name__ == "__main__":
    unittest.main(verbosity=2)
