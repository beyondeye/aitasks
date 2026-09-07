"""State machine for the session store (t1705_2).

`StateVerbMatrixTests` enumerates the FULL state x verb cross-product and
asserts every cell against the legal-from table, rather than testing the happy
paths and trusting the rest. That shape is deliberate: the defect that motivated
it (A3) was a MISSING legal edge -- `standin-respawned` from `freezing`, which
the pinned reconcile table calls but the pinned verb list did not admit -- and a
happy-path suite cannot see a missing edge at all. A matrix can.

The lease treatment of `standin-respawned` differs per source state and is the
subtle part: from `freezing` the lease is KEPT (the freeze is still in flight
and a later pass commits it), from `aborting` and `frozen` it is released.
`StandinRespawnedTests` pins all three.

NEGATIVE CONTROLS:

  lost freezing edge : remove STATE_FREEZING from `standin_respawned`'s
                       `_require_state` -> the matrix cell
                       (freezing, standin-respawned) fails, and so does
                       `test_from_freezing_keeps_the_lease`.
  lease over-clear   : make `standin_respawned` clear the lease unconditionally
                       -> `test_from_freezing_keeps_the_lease` fails.
  blind confirm      : drop the `launch_pid` check in `restore_confirm` ->
                       `test_confirm_without_launch_evidence_is_refused` fails.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_sessions as A  # noqa: E402

#: verb -> (callable, states it is legal from, extra kwargs)
#
# This IS the legal-from table of the plan's §C3, in executable form. A change
# to the state machine that is not mirrored here fails the matrix below.
VERBS = {
    "freeze-begin": (
        A.freeze_begin, {A.STATE_LIVE},
        dict(capture_ansi="/a", capture_txt="/b", lines=1, owner_pid=4242),
    ),
    "freeze-commit": (A.freeze_commit, {A.STATE_FREEZING}, dict(pane="%1", pane_pid=9)),
    "freeze-abort": (A.freeze_abort, {A.STATE_FREEZING}, {}),
    "restore-begin": (
        A.restore_begin, {A.STATE_FROZEN}, dict(mode="resume", owner_pid=4242)
    ),
    "restore-launched": (
        A.restore_launched, {A.STATE_RESTORING}, dict(pane="%1", pane_pid=9)
    ),
    "restore-abort": (A.restore_abort, {A.STATE_RESTORING}, {}),
    "standin-respawned": (
        A.standin_respawned,
        {A.STATE_FREEZING, A.STATE_ABORTING, A.STATE_FROZEN},
        dict(pane="%1", pane_pid=9),
    ),
}

#: Verbs that mint their own lease and so must NOT be handed a `nonce`.
MINTING = {"freeze-begin", "restore-begin"}


class _TransitionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        os.environ[A.FROZEN_DIR_ENV] = str(self.tmp / "frozen")
        self.addCleanup(os.environ.pop, A.FROZEN_DIR_ENV, None)
        self.addCleanup(self._tmp.cleanup)
        self.now = time.time()

    def store_in(self, state, *, nonce="aabbccdd", launch_pid=0):
        """A one-record store parked in `state`, leased when the state needs it."""
        sf = A.SessionsFile()
        sf, line = A.upsert(
            sf, root=str(self.tmp), window="agent-pick-1", pane="%1",
            pane_pid=100, pane_alive=lambda pid: True, now=self.now,
        )
        rid = line.split(":")[1].split("|")[0]
        rec = sf.by_id(rid)
        rec.state = state
        rec.state_at = A._iso(self.now)
        rec.launch_pid = launch_pid
        if state != A.STATE_LIVE:
            rec.op_nonce = nonce
            rec.op_owner_pid = os.getpid()
            rec.op_started_at = A._iso(self.now)
        return sf, rid


class StateVerbMatrixTests(_TransitionTestCase):
    """Every (state, verb) cell — the shape that can see a MISSING edge."""

    def test_full_matrix(self):
        for verb, (fn, legal, extra) in VERBS.items():
            for state in A.STATES:
                with self.subTest(verb=verb, state=state):
                    sf, rid = self.store_in(state, launch_pid=9)
                    kwargs = dict(extra)
                    # Always supply the nonce for a leased verb, even in the
                    # cells that must refuse: `_require_state` runs BEFORE
                    # `_require_nonce`, so a refusal cell must fail on the
                    # state, not on a missing argument. That ordering is
                    # asserted on its own below.
                    if verb not in MINTING:
                        kwargs["nonce"] = "aabbccdd"
                    if state in legal:
                        sf2, line = fn(sf, rid, now=self.now, **kwargs)
                        self.assertTrue(line, f"{verb} from {state} produced no line")
                    else:
                        with self.assertRaises(A.TransitionRefused):
                            fn(sf, rid, now=self.now, **kwargs)

    def test_refusal_wire_line_names_state_and_verb(self):
        sf, rid = self.store_in(A.STATE_FROZEN)
        with self.assertRaises(A.TransitionRefused) as ctx:
            A.freeze_begin(
                sf, rid, capture_ansi="/a", capture_txt="/b", lines=1,
                owner_pid=1, now=self.now,
            )
        self.assertEqual(str(ctx.exception), f"TRANSITION_REFUSED:{rid}|frozen|freeze-begin")

    def test_a_refused_transition_writes_nothing(self):
        sf, rid = self.store_in(A.STATE_FROZEN)
        before = vars(sf.by_id(rid)).copy()
        with self.assertRaises(A.TransitionRefused):
            A.freeze_commit(sf, rid, nonce="aabbccdd", pane="%9", pane_pid=9, now=self.now)
        self.assertEqual(vars(sf.by_id(rid)), before)

    def test_drop_is_legal_from_every_state(self):
        for state in A.STATES:
            with self.subTest(state=state):
                sf, rid = self.store_in(state)
                sf, line = A.drop(sf, rid)
                self.assertEqual(line, f"DROPPED:{rid}")
                self.assertEqual(sf.sessions, [])

    def test_state_is_checked_before_the_nonce(self):
        """An illegal verb reports the STATE, not a nonce mismatch.

        The ordering matters for the caller: `TRANSITION_REFUSED` (exit 5) means
        "wrong state, retry is pointless", while `NONCE_MISMATCH` (exit 6) means
        "reconcile got here first". Reporting the latter for the former would
        send a coordinator down the wrong recovery branch.
        """
        sf, rid = self.store_in(A.STATE_LIVE)
        with self.assertRaises(A.TransitionRefused):
            A.freeze_commit(sf, rid, nonce="deadbeef", pane="%1", pane_pid=1, now=self.now)

    def test_restore_begin_is_refused_from_aborting(self):
        """`aborting` is nonce-owned: no second restore may start in the gap."""
        sf, rid = self.store_in(A.STATE_ABORTING)
        with self.assertRaises(A.TransitionRefused):
            A.restore_begin(sf, rid, mode="resume", owner_pid=1, now=self.now)


class FreezeTests(_TransitionTestCase):
    def test_begin_records_the_captures_and_enters_freezing(self):
        sf, rid = self.store_in(A.STATE_LIVE)
        sf, line = A.freeze_begin(
            sf, rid, capture_ansi="/a.ansi", capture_txt="/a.txt", lines=42,
            phase="planning", owner_pid=4242, now=self.now,
        )
        rec = sf.by_id(rid)
        self.assertTrue(line.startswith(f"FREEZING:{rid}|"))
        self.assertEqual(rec.state, A.STATE_FREEZING)
        self.assertEqual((rec.capture_ansi, rec.capture_lines), ("/a.ansi", 42))
        self.assertEqual(rec.last_phase, "planning")

    def test_commit_writes_the_standin_location_and_frozen_at(self):
        sf, rid = self.store_in(A.STATE_FREEZING)
        sf, line = A.freeze_commit(
            sf, rid, nonce="aabbccdd", pane="%77", pane_pid=7777, now=self.now
        )
        rec = sf.by_id(rid)
        self.assertEqual(line, f"FROZEN:{rid}")
        self.assertEqual(rec.state, A.STATE_FROZEN)
        self.assertEqual((rec.pane_id, rec.standin_pid), ("%77", 7777))
        self.assertTrue(rec.frozen_at)

    def test_the_gone_pane_commit_is_accepted(self):
        """`--pane "" --pane-pid 0` — reconcile's commit for a vanished pane."""
        sf, rid = self.store_in(A.STATE_FREEZING)
        sf, _ = A.freeze_commit(sf, rid, nonce="aabbccdd", pane="", pane_pid=0, now=self.now)
        rec = sf.by_id(rid)
        self.assertEqual(rec.state, A.STATE_FROZEN)
        self.assertEqual((rec.pane_id, rec.standin_pid), ("", 0))

    def test_abort_returns_to_live_and_deletes_the_captures(self):
        sf, rid = self.store_in(A.STATE_FREEZING)
        d = A.ensure_capture_dir(rid)
        (d / "capture.ansi").write_text("x", encoding="utf-8")
        sf.by_id(rid).capture_ansi = str(d / "capture.ansi")
        sf, line = A.freeze_abort(sf, rid, nonce="aabbccdd", now=self.now)
        rec = sf.by_id(rid)
        self.assertEqual(line, f"LIVE:{rid}")
        self.assertEqual(rec.state, A.STATE_LIVE)
        self.assertFalse(d.exists())
        self.assertEqual(rec.capture_ansi, "")


class RestoreTests(_TransitionTestCase):
    def test_begin_retains_captures_and_counts_the_attempt(self):
        sf, rid = self.store_in(A.STATE_FROZEN)
        sf.by_id(rid).capture_ansi = "/keep.ansi"
        sf.by_id(rid).last_error = "stale"
        sf, line = A.restore_begin(sf, rid, mode="resume", owner_pid=1, now=self.now)
        rec = sf.by_id(rid)
        self.assertTrue(line.startswith(f"RESTORING:{rid}|"))
        self.assertEqual(rec.capture_ansi, "/keep.ansi")
        self.assertEqual(rec.restore_attempts, 1)
        self.assertEqual((rec.launch_pid, rec.last_error), (0, ""))

    def test_begin_rejects_an_unknown_mode(self):
        sf, rid = self.store_in(A.STATE_FROZEN)
        with self.assertRaises(ValueError):
            A.restore_begin(sf, rid, mode="rewind", owner_pid=1, now=self.now)

    def test_launched_records_the_replacement_pid(self):
        sf, rid = self.store_in(A.STATE_RESTORING)
        sf, line = A.restore_launched(
            sf, rid, nonce="aabbccdd", pane="%5", pane_pid=555, now=self.now
        )
        self.assertEqual(line, f"LAUNCHED:{rid}")
        self.assertEqual(sf.by_id(rid).launch_pid, 555)

    def test_confirm_requires_matching_launch_evidence(self):
        sf, rid = self.store_in(A.STATE_RESTORING, launch_pid=555)
        sf, line = A.restore_confirm(
            sf, rid, nonce="aabbccdd", pane="%5", pane_pid=555, now=self.now
        )
        rec = sf.by_id(rid)
        self.assertEqual(line, f"LIVE:{rid}|liveness")
        self.assertEqual((rec.state, rec.ack), (A.STATE_LIVE, "liveness"))

    def test_confirm_without_launch_evidence_is_refused(self):
        """CONTROL. launch_pid == 0 means no respawn was ever witnessed."""
        sf, rid = self.store_in(A.STATE_RESTORING, launch_pid=0)
        with self.assertRaises(A.TransitionRefused):
            A.restore_confirm(
                sf, rid, nonce="aabbccdd", pane="%5", pane_pid=555, now=self.now
            )

    def test_confirm_against_a_different_pid_is_refused(self):
        """A stand-in viewer in the pane must never confirm as a restored agent."""
        sf, rid = self.store_in(A.STATE_RESTORING, launch_pid=555)
        with self.assertRaises(A.TransitionRefused):
            A.restore_confirm(
                sf, rid, nonce="aabbccdd", pane="%5", pane_pid=666, now=self.now
            )

    def test_a_liveness_confirm_KEEPS_the_captures(self):
        """What stops a malformed resume from destroying the only copy."""
        sf, rid = self.store_in(A.STATE_RESTORING, launch_pid=555)
        d = A.ensure_capture_dir(rid)
        (d / "capture.ansi").write_text("x", encoding="utf-8")
        sf.by_id(rid).capture_ansi = str(d / "capture.ansi")
        sf, _ = A.restore_confirm(
            sf, rid, nonce="aabbccdd", pane="%5", pane_pid=555, now=self.now
        )
        self.assertTrue(d.exists())
        self.assertEqual(sf.by_id(rid).capture_ansi, str(d / "capture.ansi"))

    def test_abort_enters_aborting_and_keeps_the_lease(self):
        sf, rid = self.store_in(A.STATE_RESTORING)
        sf, line = A.restore_abort(sf, rid, nonce="aabbccdd", now=self.now)
        rec = sf.by_id(rid)
        self.assertEqual(line, f"ABORTING:{rid}")
        self.assertEqual(rec.state, A.STATE_ABORTING)
        self.assertEqual(rec.op_nonce, "aabbccdd")


class StandinRespawnedTests(_TransitionTestCase):
    """Three legal sources, three lease treatments (t1705_2 A3)."""

    def test_from_freezing_keeps_the_lease(self):
        """CONTROL. The freeze is still in flight; a later pass commits it.

        Without this edge the pinned reconcile row `freezing / pane dead ->
        respawn, standin-respawned, re-check` cannot be implemented at all.
        """
        sf, rid = self.store_in(A.STATE_FREEZING)
        sf, line = A.standin_respawned(
            sf, rid, nonce="aabbccdd", pane="%8", pane_pid=888, now=self.now
        )
        rec = sf.by_id(rid)
        self.assertEqual(line, f"STANDIN:{rid}")
        self.assertEqual(rec.state, A.STATE_FREEZING)
        self.assertEqual(rec.op_nonce, "aabbccdd")
        self.assertEqual(rec.standin_pid, 888)

    def test_freezing_respawn_then_commit_completes_the_freeze(self):
        """The full reconcile sequence the A3 edge exists to serve."""
        sf, rid = self.store_in(A.STATE_FREEZING)
        sf, _ = A.standin_respawned(
            sf, rid, nonce="aabbccdd", pane="%8", pane_pid=888, now=self.now
        )
        sf, line = A.freeze_commit(
            sf, rid, nonce="aabbccdd", pane="%8", pane_pid=888, now=self.now
        )
        self.assertEqual(line, f"FROZEN:{rid}")
        self.assertEqual(sf.by_id(rid).state, A.STATE_FROZEN)

    def test_from_aborting_returns_to_frozen_and_clears_the_lease(self):
        sf, rid = self.store_in(A.STATE_ABORTING)
        sf, line = A.standin_respawned(
            sf, rid, nonce="aabbccdd", pane="%8", pane_pid=888, now=self.now
        )
        rec = sf.by_id(rid)
        self.assertEqual(line, f"STANDIN:{rid}")
        self.assertEqual(rec.state, A.STATE_FROZEN)
        self.assertEqual(rec.op_nonce, "")

    def test_from_frozen_updates_and_clears_the_lease(self):
        """A lease-taken relaunch of a dead stand-in."""
        sf, rid = self.store_in(A.STATE_FROZEN)
        sf, _ = A.standin_respawned(
            sf, rid, nonce="aabbccdd", pane="%8", pane_pid=888, now=self.now
        )
        rec = sf.by_id(rid)
        self.assertEqual(rec.state, A.STATE_FROZEN)
        self.assertEqual((rec.op_nonce, rec.standin_pid), ("", 888))

    def test_a_stale_nonce_cannot_respawn_over_a_newer_attempt(self):
        sf, rid = self.store_in(A.STATE_ABORTING, nonce="11111111")
        with self.assertRaises(A.NonceMismatch):
            A.standin_respawned(
                sf, rid, nonce="22222222", pane="%8", pane_pid=888, now=self.now
            )


class UnknownRecordTests(_TransitionTestCase):
    def test_a_missing_record_is_an_error(self):
        sf = A.SessionsFile()
        with self.assertRaises(A.MalformedSessionsError):
            A.drop(sf, "aabbccdd")

    def test_a_non_canonical_id_is_a_value_error(self):
        sf = A.SessionsFile()
        with self.assertRaises(ValueError):
            A.drop(sf, "../../etc")


if __name__ == "__main__":
    unittest.main(verbosity=2)
