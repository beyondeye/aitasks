#!/usr/bin/env python3
"""Fetch-ordered trail reads: `trail_discovery.sequenced_trail_read` (t1895).

`ait trails` keeps several trails open, so a discovery scan and a background
reload can read the same trail concurrently. The tab view keeps whichever
result carries the larger `read_seq`, so `read_seq` must follow the order in
which the reads SAMPLED the stored artifact, not the order they were requested
in. Every schedule below makes request order and sampling order differ, using
real threads and a fake store; nothing hand-assigns "newer = larger".

* stall before sampling — the read requested first samples last and must carry
  the larger sequence;
* stall after sampling, inside the read — a second read of the same handle has
  to wait, so it samples the newer revision and carries the larger sequence;
* negative control — the same schedule with the per-handle lock disabled gives
  the OLDER revision the larger sequence, which is the race the lock removes;
* different handles never wait on each other.

Imports the lib module directly: no board, no Textual.

Run: ~/.aitask/venv/bin/python -m pytest tests/test_trail_discovery_sequencing.py -q
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import contextlib
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import trail_discovery as td  # noqa: E402

#: Bound on every wait, so a broken schedule fails instead of hanging.
TIMEOUT = 5.0


class _Store:
    """A stored artifact whose revision only moves forward."""

    def __init__(self):
        self.rev = "rev1"


def _thread(target) -> threading.Thread:
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread


def _join(test, *threads):
    for thread in threads:
        thread.join(TIMEOUT)
        test.assertFalse(thread.is_alive(), "schedule deadlocked")


class SequencedReadTests(unittest.TestCase):

    def test_a_read_that_stalls_before_sampling_carries_the_larger_seq(self):
        """T1 is requested first but samples last (after the store advanced)."""
        store = _Store()
        go = threading.Event()
        results = {}

        def t1():
            go.wait(TIMEOUT)            # requested, not yet reading
            results["t1"] = td.sequenced_trail_read(
                "art:a", lambda h: store.rev)

        def t2():
            results["t2"] = td.sequenced_trail_read(
                "art:a", lambda h: store.rev)

        first = _thread(t1)             # request order: T1 then T2
        second = _thread(t2)
        _join(self, second)
        store.rev = "rev2"
        go.set()
        _join(self, first)

        (rev1, seq_t1), (rev2, seq_t2) = results["t1"], results["t2"]
        self.assertEqual((rev1, rev2), ("rev2", "rev1"))
        self.assertGreater(seq_t1, seq_t2,
                           "the later sample must carry the larger read_seq")

    def _stall_after_sampling(self, lock_disabled: bool):
        """T1 samples rev1 and stalls inside the read; the store advances; T2
        is requested; then T1 is released. Returns both results and whether T2
        sampled while T1 was still inside its read."""
        store = _Store()
        t1_sampled = threading.Event()
        t1_release = threading.Event()
        t2_sampled = threading.Event()
        results = {}

        def loader1(handle):
            value = store.rev
            t1_sampled.set()
            t1_release.wait(TIMEOUT)
            return value

        def loader2(handle):
            t2_sampled.set()
            return store.rev

        def t1():
            results["t1"] = td.sequenced_trail_read("art:a", loader1)

        def t2():
            results["t2"] = td.sequenced_trail_read("art:a", loader2)

        patcher = (patch.object(td, "_trail_read_lock",
                                lambda handle: contextlib.nullcontext())
                   if lock_disabled else contextlib.nullcontext())
        with patcher:
            first = _thread(t1)
            self.assertTrue(t1_sampled.wait(TIMEOUT))
            store.rev = "rev2"
            second = _thread(t2)
            # Give T2 the chance to run; with the lock it must still be waiting.
            sampled_early = t2_sampled.wait(0.3)
            t1_release.set()
            _join(self, first, second)
        return results["t1"], results["t2"], sampled_early

    def test_a_same_handle_read_waits_and_samples_the_newer_revision(self):
        (rev_t1, seq_t1), (rev_t2, seq_t2), early = self._stall_after_sampling(
            lock_disabled=False)
        self.assertFalse(early, "T2 read while T1 was still inside its read")
        self.assertEqual((rev_t1, rev_t2), ("rev1", "rev2"))
        self.assertGreater(seq_t2, seq_t1)

    def test_negative_control_without_the_lock_the_older_read_wins(self):
        """Same schedule, lock disabled: T2 reads rev2 and finishes first, T1
        finishes later with rev1 — and the OLDER revision gets the larger
        sequence. This is the race the per-handle lock removes, and it proves
        the positive test above can fail."""
        (rev_t1, seq_t1), (rev_t2, seq_t2), early = self._stall_after_sampling(
            lock_disabled=True)
        self.assertTrue(early)
        self.assertEqual((rev_t1, rev_t2), ("rev1", "rev2"))
        self.assertGreater(seq_t1, seq_t2)

    def test_different_handles_do_not_wait_on_each_other(self):
        release = threading.Event()
        done = threading.Event()

        def blocked():
            td.sequenced_trail_read(
                "art:a", lambda h: release.wait(TIMEOUT))

        def other():
            td.sequenced_trail_read("art:b", lambda h: "x")
            done.set()

        first = _thread(blocked)
        time.sleep(0.05)
        second = _thread(other)
        self.assertTrue(done.wait(TIMEOUT),
                        "a read of art:b waited on a read of art:a")
        release.set()
        _join(self, first, second)

    def test_discovery_stamps_every_info(self):
        """`discover_trails` reads through the sequencer: each discovered trail
        carries a real, distinct `read_seq`."""
        infos = [td.TrailInfo(handle=h, owner_id="1", owner_archived=False,
                              owner_folded=False)
                 for h in ("art:a", "art:b")]
        with patch.object(td, "_iter_trail_frontmatter_records",
                          lambda unreadable, scan_errors=None: iter(infos)), \
                patch.object(td, "load_trail_blob",
                             lambda h: ({"title": h}, "", [])):
            found, _unreadable = td.discover_trails()
        seqs = [i.read_seq for i in found]
        self.assertTrue(all(s > 0 for s in seqs), seqs)
        self.assertEqual(len(set(seqs)), len(seqs))
        self.assertEqual([i.doc["title"] for i in found], ["art:a", "art:b"])


if __name__ == "__main__":
    unittest.main()
