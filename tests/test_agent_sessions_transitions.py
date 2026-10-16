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
  confirm past error : drop the current-nonce `last_error` check in
                       `restore_confirm` -> both
                       `ConfirmRefusesARecordedMismatchTests` refusals fail.
  lost handover      : drop the prefix rewrite in `lease_take` ->
                       `test_a_takeover_carries_the_attempts_error_to_the_new_nonce`
                       and `test_after_a_takeover_the_carried_error_still_refuses`
                       fail.
"""
from __future__ import annotations

import contextlib
import io
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

    def store_in(self, state, *, nonce="aabbccdd", launch_pid=0, leased=True):
        """A one-record store parked in `state`, leased when the state needs it.

        `leased=False` produces a record with NO lease — which is what a real
        `frozen` record looks like (`freeze-commit` clears the lease) and is the
        only shape a lease-MINTING verb is ever called on. Minting on a record
        whose lease is live is refused now (t1705_6), so a fixture that leased
        unconditionally would make `restore-begin from frozen` fail for a reason
        production never produces.
        """
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
        if state != A.STATE_LIVE and leased:
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
                    sf, rid = self.store_in(
                        state, launch_pid=9, leased=verb not in MINTING)
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
    def test_begin_is_refused_while_the_lease_is_held(self):
        """A holder's claim must PREVENT a restore, not merely detect one.

        `aitask_frozen.sh drop` claims the record, checks the pane, then kills
        it. Before this rule a restore could squeeze into that window and
        respawn a replacement AGENT into the same pane — which the drop then
        killed. Detecting the race afterwards does not undo a killed agent.
        """
        sf, rid = self.store_in(A.STATE_FROZEN, nonce="aabbccdd")
        with self.assertRaises(A.LeaseHeld):
            A.restore_begin(sf, rid, mode="resume", owner_pid=4242,
                            now=self.now, pid_alive=lambda pid: True)
        self.assertEqual(sf.by_id(rid).state, A.STATE_FROZEN)
        self.assertEqual(sf.by_id(rid).restore_attempts, 0)

    def test_begin_takes_over_a_STALE_lease(self):
        """A crashed coordinator must not make a record un-restorable."""
        sf, rid = self.store_in(A.STATE_FROZEN, nonce="aabbccdd")
        sf.by_id(rid).op_started_at = A._iso(self.now - 10_000)
        sf, line = A.restore_begin(
            sf, rid, mode="resume", owner_pid=4242, now=self.now,
            pid_alive=lambda pid: False,
        )
        self.assertTrue(line.startswith(f"RESTORING:{rid}|"))

    def test_begin_retains_captures_and_counts_the_attempt(self):
        # Leaseless: what `freeze-commit` actually leaves behind.
        sf, rid = self.store_in(A.STATE_FROZEN, leased=False)
        sf.by_id(rid).capture_ansi = "/keep.ansi"
        sf.by_id(rid).last_error = "stale"
        sf, line = A.restore_begin(sf, rid, mode="resume", owner_pid=1, now=self.now)
        rec = sf.by_id(rid)
        self.assertTrue(line.startswith(f"RESTORING:{rid}|"))
        self.assertEqual(rec.capture_ansi, "/keep.ansi")
        self.assertEqual(rec.restore_attempts, 1)
        self.assertEqual((rec.launch_pid, rec.last_error), (0, ""))

    def test_begin_rejects_an_unknown_mode(self):
        sf, rid = self.store_in(A.STATE_FROZEN, leased=False)
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


class DropNonceTests(_TransitionTestCase):
    """`drop`'s two forms — the unconditional one and the leased one (t1705_6).

    `drop` deletes the record AND its capture files, and it used to be the ONE
    mutating verb exempt from the §A rule "every verb that mutates a record
    holding a lease requires --nonce". That exemption is what let a `drop` land
    on a record another coordinator was mid-transaction on.
    """

    def _capture_files(self, rid):
        d = A.ensure_capture_dir(rid)
        (d / "capture.ansi").write_text("x")
        (d / "capture.txt").write_text("x")
        return d

    def test_the_bare_form_is_still_unconditional(self):
        """`kill_agent_pane_smart`'s contract: any state, no nonce."""
        for state in (A.STATE_LIVE, A.STATE_FROZEN, A.STATE_RESTORING,
                      A.STATE_ABORTING, A.STATE_FREEZING):
            sf, rid = self.store_in(state)
            sf, line = A.drop(sf, rid)
            self.assertEqual(line, f"DROPPED:{rid}", state)
            self.assertIsNone(sf.by_id(rid))

    def test_the_leased_form_accepts_the_held_nonce(self):
        sf, rid = self.store_in(A.STATE_FROZEN, nonce="aabbccdd")
        d = self._capture_files(rid)
        sf, line = A.drop(sf, rid, nonce="aabbccdd")
        self.assertEqual(line, f"DROPPED:{rid}")
        self.assertIsNone(sf.by_id(rid))
        self.assertFalse(d.exists(), "the capture must go with the record")

    def test_a_wrong_nonce_refuses_and_writes_NOTHING(self):
        sf, rid = self.store_in(A.STATE_FROZEN, nonce="aabbccdd")
        d = self._capture_files(rid)
        with self.assertRaises(A.NonceMismatch):
            A.drop(sf, rid, nonce="deadbeef")
        self.assertIsNotNone(sf.by_id(rid))
        self.assertTrue(d.exists(), "a refused drop must not touch the capture")

    def test_an_empty_stored_nonce_never_matches(self):
        """A record with NO lease cannot be dropped by the leased form.

        Otherwise a coordinator whose claim had already been cleared could still
        delete — which is the ABA hole in a different disguise.
        """
        sf, rid = self.store_in(A.STATE_LIVE)          # live => no lease
        self.assertEqual(sf.by_id(rid).op_nonce, "")
        with self.assertRaises(A.NonceMismatch):
            A.drop(sf, rid, nonce="aabbccdd")
        self.assertIsNotNone(sf.by_id(rid))


class LeaseReleaseTests(_TransitionTestCase):
    """`lease-release` — the counterpart `lease-take` never had (t1705_6)."""

    def test_the_correct_nonce_clears_the_whole_triple(self):
        sf, rid = self.store_in(A.STATE_FROZEN, nonce="aabbccdd")
        sf, line = A.lease_release(sf, rid, nonce="aabbccdd")
        self.assertEqual(line, f"RELEASED:{rid}")
        rec = sf.by_id(rid)
        self.assertEqual((rec.op_nonce, rec.op_owner_pid, rec.op_started_at),
                         ("", 0, ""))

    def test_a_released_record_is_immediately_re_leasable(self):
        """The point of the verb: a retry must not wait out the 60s grace."""
        sf, rid = self.store_in(A.STATE_FROZEN, nonce="aabbccdd")
        sf, _ = A.lease_release(sf, rid, nonce="aabbccdd")
        sf, line = A.lease_take(sf, rid, owner_pid=os.getpid())
        self.assertTrue(line.startswith(f"LEASED:{rid}|"))

    def test_a_wrong_nonce_leaves_the_lease_intact(self):
        sf, rid = self.store_in(A.STATE_FROZEN, nonce="aabbccdd")
        with self.assertRaises(A.NonceMismatch):
            A.lease_release(sf, rid, nonce="deadbeef")
        self.assertEqual(sf.by_id(rid).op_nonce, "aabbccdd")



class FillTaskTests(_TransitionTestCase):
    """`fill-task` (t1848): blank fields only, any state, nothing else touched."""

    ALL_STATES = (A.STATE_LIVE, A.STATE_FREEZING, A.STATE_FROZEN,
                  A.STATE_RESTORING, A.STATE_ABORTING)

    def test_fills_blanks_in_every_state_and_touches_nothing_else(self):
        for state in self.ALL_STATES:
            with self.subTest(state=state):
                sf, rid = self.store_in(state)
                before = dict(vars(sf.by_id(rid)))
                sf, line = A.fill_task(sf, rid, operation="pick", task_id="1")
                self.assertEqual(line, f"FILLED:{rid}|operation,task_id")
                after = dict(vars(sf.by_id(rid)))
                self.assertEqual((after.pop("operation"), after.pop("task_id")),
                                 ("pick", "1"))
                before.pop("operation"), before.pop("task_id")
                self.assertEqual(after, before,
                                 "state, lease and location must be untouched")

    def test_a_stored_value_is_never_overwritten(self):
        sf, rid = self.store_in(A.STATE_FROZEN, leased=False)
        rec = sf.by_id(rid)
        rec.operation, rec.task_id = "qa", "999"
        sf, line = A.fill_task(sf, rid, operation="pick", task_id="1")
        self.assertEqual(line, f"FILL_NOOP:{rid}|unchanged")
        self.assertEqual((rec.operation, rec.task_id), ("qa", "999"))

    def test_each_field_is_filled_independently(self):
        sf, rid = self.store_in(A.STATE_LIVE)
        sf.by_id(rid).operation = "qa"
        sf, line = A.fill_task(sf, rid, operation="pick", task_id="1")
        self.assertEqual(line, f"FILLED:{rid}|task_id")
        self.assertEqual((sf.by_id(rid).operation, sf.by_id(rid).task_id),
                         ("qa", "1"))

    def test_a_blank_supplied_value_writes_nothing(self):
        sf, rid = self.store_in(A.STATE_LIVE)
        sf, line = A.fill_task(sf, rid)
        self.assertEqual(line, f"FILL_NOOP:{rid}|unchanged")

    def test_an_unknown_record_is_an_error(self):
        with self.assertRaises(A.MalformedSessionsError):
            A.fill_task(A.SessionsFile(), "0badc0de", task_id="1")


def _codex_restoring(case, *, mode="resume", agent_kind="codex", launch_pid=555,
                     session="11111111-2222-3333-4444-555555555555"):
    """A `restoring` codex record with a capture on disk, as a rollout confirm
    meets it. Returns ``(sf, rid, capture_dir)``."""
    sf, rid = case.store_in(A.STATE_RESTORING, launch_pid=launch_pid)
    rec = sf.by_id(rid)
    rec.restore_mode = mode
    rec.agent_kind = agent_kind
    rec.agent_string = f"{agent_kind}/gpt5" if agent_kind else ""
    rec.codeagent_session_id = session
    d = A.ensure_capture_dir(rid)
    (d / "capture.ansi").write_text("x", encoding="utf-8")
    rec.capture_ansi = str(d / "capture.ansi")
    rec.capture_lines = 1
    return sf, rid, d


class RolloutConfirmTests(_TransitionTestCase):
    """`restore-confirm --rollout-session` (t2040): verified, like a hook ack."""

    SID = "11111111-2222-3333-4444-555555555555"

    def test_a_matching_rollout_verifies_and_deletes_the_captures(self):
        sf, rid, d = _codex_restoring(self)
        sf.by_id(rid).last_error = "deadbeef:an older attempt"
        sf, line = A.restore_confirm(
            sf, rid, nonce="aabbccdd", pane="%5", pane_pid=555,
            rollout_session=self.SID, now=self.now)
        rec = sf.by_id(rid)
        self.assertEqual(line, f"LIVE:{rid}|rollout")
        self.assertEqual((rec.state, rec.ack), (A.STATE_LIVE, "rollout"))
        self.assertFalse(d.exists(), "a verified confirm deletes the captures")
        self.assertEqual((rec.capture_ansi, rec.capture_lines), ("", 0))
        self.assertEqual(rec.last_error, "")
        self.assertEqual(rec.op_nonce, "", "the lease is cleared")
        self.assertEqual(rec.pane_id, "%5")

    def test_a_mismatching_rollout_persists_the_error_and_raises(self):
        sf, rid, d = _codex_restoring(self)
        with self.assertRaises(A.SessionMismatch):
            A.restore_confirm(
                sf, rid, nonce="aabbccdd", pane="%5", pane_pid=555,
                rollout_session="99999999-2222-3333-4444-555555555555",
                now=self.now)
        rec = sf.by_id(rid)
        self.assertEqual(rec.last_error, "aabbccdd:session_mismatch")
        self.assertEqual(rec.state, A.STATE_RESTORING)
        self.assertTrue(d.exists(), "a mismatch keeps the only copy")

    def test_refused_for_a_repick_a_non_codex_record_and_a_foreign_pid(self):
        cases = (
            ("repick", dict(mode="repick"), 555),
            ("claudecode", dict(agent_kind="claudecode"), 555),
            ("blank kind", dict(agent_kind=""), 555),
            ("foreign pid", {}, 666),
        )
        for label, overrides, pid in cases:
            with self.subTest(case=label):
                sf, rid, d = _codex_restoring(self, **overrides)
                with self.assertRaises(A.TransitionRefused):
                    A.restore_confirm(
                        sf, rid, nonce="aabbccdd", pane="%5", pane_pid=pid,
                        rollout_session=self.SID, now=self.now)
                rec = sf.by_id(rid)
                self.assertEqual(rec.state, A.STATE_RESTORING)
                self.assertEqual(rec.last_error, "", "a refusal writes nothing")
                self.assertTrue(d.exists())

    def test_without_the_option_it_is_still_the_liveness_confirm(self):
        """CONTROL. The same record, no evidence: captures kept."""
        sf, rid, d = _codex_restoring(self)
        sf, line = A.restore_confirm(
            sf, rid, nonce="aabbccdd", pane="%5", pane_pid=555, now=self.now)
        self.assertEqual(line, f"LIVE:{rid}|liveness")
        self.assertEqual(sf.by_id(rid).ack, "liveness")
        self.assertTrue(d.exists())


class ConfirmRefusesARecordedMismatchTests(_TransitionTestCase):
    """A mismatch the hook persisted for THIS attempt blocks every confirm
    (t2040). It can land after the coordinator's last poll."""

    def test_a_current_nonce_mismatch_refuses_the_liveness_confirm(self):
        sf, rid, d = _codex_restoring(self)
        sf.by_id(rid).last_error = "aabbccdd:session_mismatch"
        with self.assertRaises(A.TransitionRefused):
            A.restore_confirm(
                sf, rid, nonce="aabbccdd", pane="%5", pane_pid=555, now=self.now)
        self.assertEqual(sf.by_id(rid).state, A.STATE_RESTORING)

    def test_a_current_nonce_mismatch_refuses_the_rollout_confirm(self):
        sf, rid, d = _codex_restoring(self)
        sf.by_id(rid).last_error = "aabbccdd:session_mismatch"
        with self.assertRaises(A.TransitionRefused):
            A.restore_confirm(
                sf, rid, nonce="aabbccdd", pane="%5", pane_pid=555,
                rollout_session=RolloutConfirmTests.SID, now=self.now)
        self.assertTrue(d.exists())

    def test_an_older_attempts_error_does_not_block(self):
        """CONTROL. `restore-begin` clears `last_error`, but a stale prefix must
        never be read as this attempt's report anyway."""
        sf, rid, _ = _codex_restoring(self)
        sf.by_id(rid).last_error = "deadbeef:session_mismatch"
        sf, line = A.restore_confirm(
            sf, rid, nonce="aabbccdd", pane="%5", pane_pid=555, now=self.now)
        self.assertEqual(line, f"LIVE:{rid}|liveness")


class LeaseTakeCarriesTheAttemptErrorTests(_TransitionTestCase):
    """The recovery handover (t2040): reconcile reads the record BEFORE it takes
    the lease, so a hook mismatch landing in between must follow the lease to
    the new nonce, or the current-nonce guard above stops seeing it."""

    def _stale(self, sf, rid):
        sf.by_id(rid).op_started_at = A._iso(self.now - 10_000)

    def test_a_takeover_carries_the_attempts_error_to_the_new_nonce(self):
        sf, rid, _ = _codex_restoring(self)
        sf.by_id(rid).last_error = "aabbccdd:session_mismatch"
        self._stale(sf, rid)
        sf, line = A.lease_take(sf, rid, owner_pid=os.getpid(), now=self.now,
                                pid_alive=lambda pid: False)
        new = line.split("|")[1]
        self.assertNotEqual(new, "aabbccdd")
        self.assertEqual(sf.by_id(rid).last_error, f"{new}:session_mismatch")

    def test_an_older_attempts_error_is_left_alone(self):
        sf, rid, _ = _codex_restoring(self)
        sf.by_id(rid).last_error = "deadbeef:agent_exited"
        self._stale(sf, rid)
        A.lease_take(sf, rid, owner_pid=os.getpid(), now=self.now,
                     pid_alive=lambda pid: False)
        self.assertEqual(sf.by_id(rid).last_error, "deadbeef:agent_exited")

    def test_a_record_with_no_lease_is_left_alone(self):
        """`drop` claims a `frozen` record whose lease `freeze-commit` cleared;
        an empty outgoing nonce matches every `:`-prefixed string, so it must
        never be treated as one."""
        sf, rid = self.store_in(A.STATE_FROZEN, leased=False)
        sf.by_id(rid).last_error = ":odd"
        A.lease_take(sf, rid, owner_pid=os.getpid(), now=self.now)
        self.assertEqual(sf.by_id(rid).last_error, ":odd")

    def test_after_a_takeover_the_carried_error_still_refuses(self):
        """THE RACE, end to end: snapshot (clean) -> hook persists a mismatch
        under N1 -> reconcile takes the lease (N2) -> confirm under N2."""
        for rollout in (None, RolloutConfirmTests.SID):
            with self.subTest(rollout=rollout):
                # A fresh record per path, so neither can pass because the
                # other already moved the record out of `restoring`.
                sf, rid, d = _codex_restoring(self)
                sf.by_id(rid).last_error = "aabbccdd:session_mismatch"  # late hook
                self._stale(sf, rid)
                sf, line = A.lease_take(sf, rid, owner_pid=os.getpid(),
                                        now=self.now, pid_alive=lambda pid: False)
                new = line.split("|")[1]
                with self.assertRaises(A.TransitionRefused):
                    A.restore_confirm(sf, rid, nonce=new, pane="%5", pane_pid=555,
                                      rollout_session=rollout, now=self.now)
                self.assertEqual(sf.by_id(rid).state, A.STATE_RESTORING)
                self.assertTrue(d.exists())


class RolloutConfirmCliTests(_TransitionTestCase):
    """The CLI persists a rollout mismatch before exiting 7, as for a hook ack."""

    def setUp(self) -> None:
        super().setUp()
        quiet = contextlib.ExitStack()
        quiet.enter_context(contextlib.redirect_stdout(io.StringIO()))
        quiet.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.addCleanup(quiet.close)

    def test_a_mismatch_through_main_exits_7_and_is_on_disk(self):
        path = self.tmp / "sessions.json"
        sf, rid, _ = _codex_restoring(self)
        A.dump(sf, path)
        rc = A.main(["--file", str(path), "restore-confirm", rid,
                     "--nonce", "aabbccdd", "--pane", "%5", "--pane-pid", "555",
                     "--rollout-session", "99999999-2222-3333-4444-555555555555"])
        self.assertEqual(rc, 7)
        self.assertEqual(A.load(path).by_id(rid).last_error,
                         "aabbccdd:session_mismatch")

    def test_a_match_through_main_is_live_rollout(self):
        path = self.tmp / "sessions.json"
        sf, rid, _ = _codex_restoring(self)
        A.dump(sf, path)
        rc = A.main(["--file", str(path), "restore-confirm", rid,
                     "--nonce", "aabbccdd", "--pane", "%5", "--pane-pid", "555",
                     "--rollout-session", RolloutConfirmTests.SID])
        self.assertEqual(rc, 0)
        self.assertEqual(A.load(path).by_id(rid).ack, "rollout")

    def test_an_empty_rollout_session_is_a_usage_error(self):
        path = self.tmp / "sessions.json"
        sf, rid, _ = _codex_restoring(self)
        A.dump(sf, path)
        rc = A.main(["--file", str(path), "restore-confirm", rid,
                     "--nonce", "aabbccdd", "--pane", "%5", "--pane-pid", "555",
                     "--rollout-session", ""])
        self.assertEqual(rc, 2)
        self.assertEqual(A.load(path).by_id(rid).state, A.STATE_RESTORING)


if __name__ == "__main__":
    unittest.main(verbosity=2)
