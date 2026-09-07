"""Operation lease for the session store (t1705_2).

The lease answers one question: **is the coordinator that started this freeze or
restore still working?** `reconcile` uses the answer to decide whether it may
take over a record. Getting it wrong in the permissive direction is the worst
failure the store can have — reconcile respawns a stand-in over an in-flight
restore, or aborts a freeze that is still capturing, and the real coordinator
then fails `NONCE_MISMATCH` and loses the user's work silently.

`_lease_stale` is deliberately a CONJUNCTION: the grace must have elapsed AND
the owner must be gone. `OwnerPidTests` is the control on the second term, and
it is the reason `--owner-pid` is a required argument rather than a default
(t1705_2 A7). Note what it takes to actually catch that defect: a test that
mints a lease with `os.getpid()` passes under a broken implementation too,
because the test process is alive and so is the wrapper. The discriminating case
is a lease whose owner is a pid that is alive but is NOT this process --
`test_a_live_foreign_owner_is_never_stale` -- paired with a provably dead one.

NEGATIVE CONTROLS:

  timer-only lease : delete the `not alive(rec.op_owner_pid)` term from
                     `_lease_stale` (what an `owner_pid` defaulted to the
                     ephemeral helper effectively produces) ->
                     `test_a_live_foreign_owner_is_never_stale` and
                     `test_live_owner_past_the_grace_still_holds` fail.
  pid-only lease   : delete the `op_started_at + grace >= now` term ->
                     `test_a_dead_owner_inside_the_grace_still_holds` fails.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_sessions  # noqa: E402

GRACE = agent_sessions.STALE_OP_GRACE_DEFAULT


class _LeaseTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        os.environ[agent_sessions.FROZEN_DIR_ENV] = str(self.tmp / "frozen")
        self.addCleanup(os.environ.pop, agent_sessions.FROZEN_DIR_ENV, None)
        self.addCleanup(self._tmp.cleanup)
        self.sf = agent_sessions.SessionsFile()
        self.now = time.time()
        self.sf, line = agent_sessions.upsert(
            self.sf, root=str(self.tmp), window="agent-pick-1",
            pane="%1", pane_pid=100, pane_alive=lambda pid: True, now=self.now,
        )
        self.rid = line.split(":")[1].split("|")[0]

    def freeze(self, owner_pid, at=None):
        self.sf, line = agent_sessions.freeze_begin(
            self.sf, self.rid, capture_ansi="/a", capture_txt="/b", lines=1,
            owner_pid=owner_pid, now=at if at is not None else self.now,
        )
        return line.split("|")[1]


class MintingTests(_LeaseTestCase):
    def test_freeze_begin_mints_a_nonce_and_records_the_owner(self):
        nonce = self.freeze(owner_pid=4242)
        rec = self.sf.by_id(self.rid)
        self.assertTrue(agent_sessions.valid_id(nonce))
        self.assertEqual(rec.op_nonce, nonce)
        self.assertEqual(rec.op_owner_pid, 4242)
        self.assertTrue(rec.op_started_at)

    def test_nonces_are_distinct_per_operation(self):
        first = self.freeze(owner_pid=1)
        self.sf, _ = agent_sessions.freeze_abort(self.sf, self.rid, nonce=first)
        second = self.freeze(owner_pid=1)
        self.assertNotEqual(first, second)

    def test_a_lease_clearing_transition_clears_all_three_fields(self):
        nonce = self.freeze(owner_pid=4242)
        self.sf, _ = agent_sessions.freeze_commit(
            self.sf, self.rid, nonce=nonce, pane="%1", pane_pid=999, now=self.now
        )
        rec = self.sf.by_id(self.rid)
        self.assertEqual((rec.op_nonce, rec.op_owner_pid, rec.op_started_at), ("", 0, ""))


class NonceTests(_LeaseTestCase):
    def test_wrong_nonce_refuses_and_writes_nothing(self):
        self.freeze(owner_pid=4242)
        before = vars(self.sf.by_id(self.rid)).copy()
        with self.assertRaises(agent_sessions.NonceMismatch):
            agent_sessions.freeze_commit(
                self.sf, self.rid, nonce="deadbeef", pane="%9", pane_pid=9, now=self.now
            )
        self.assertEqual(vars(self.sf.by_id(self.rid)), before)

    def test_empty_nonce_never_authenticates(self):
        self.freeze(owner_pid=4242)
        with self.assertRaises(agent_sessions.NonceMismatch):
            agent_sessions.freeze_abort(self.sf, self.rid, nonce="", now=self.now)

    def test_every_leased_verb_requires_the_nonce(self):
        verbs = [
            ("freeze_commit", dict(pane="%1", pane_pid=1)),
            ("freeze_abort", {}),
            ("standin_respawned", dict(pane="%1", pane_pid=1)),
        ]
        for name, kw in verbs:
            with self.subTest(verb=name):
                self.setUp()
                self.freeze(owner_pid=4242)
                with self.assertRaises(agent_sessions.NonceMismatch):
                    getattr(agent_sessions, name)(
                        self.sf, self.rid, nonce="deadbeef", now=self.now, **kw
                    )


class OwnerPidTests(_LeaseTestCase):
    """The control on `--owner-pid`. See this module's docstring."""

    def test_a_live_foreign_owner_is_never_stale(self):
        """CONTROL. A pid that is alive but is NOT this process.

        This is the case a timer-only lease gets wrong, and the case a lease
        owned by the ephemeral wrapper can never produce.
        """
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        self.freeze(owner_pid=proc.pid)
        rec = self.sf.by_id(self.rid)
        # Well past the grace: only the live owner keeps the lease held.
        self.assertFalse(agent_sessions._lease_stale(rec, self.now + GRACE * 10))
        with self.assertRaises(agent_sessions.LeaseHeld):
            agent_sessions.lease_take(
                self.sf, self.rid, owner_pid=999, now=self.now + GRACE * 10
            )

    def test_live_owner_past_the_grace_still_holds(self):
        self.freeze(owner_pid=os.getpid())
        rec = self.sf.by_id(self.rid)
        self.assertFalse(agent_sessions._lease_stale(rec, self.now + GRACE + 1))

    def test_a_dead_owner_past_the_grace_is_taken_over(self):
        self.freeze(owner_pid=4242)
        self.sf, line = agent_sessions.lease_take(
            self.sf, self.rid, owner_pid=777,
            now=self.now + GRACE + 1, pid_alive=lambda pid: False,
        )
        self.assertTrue(line.startswith(f"LEASED:{self.rid}|"))
        self.assertEqual(self.sf.by_id(self.rid).op_owner_pid, 777)

    def test_a_dead_owner_inside_the_grace_still_holds(self):
        """CONTROL on the timer term: within the grace, reconcile keeps off."""
        self.freeze(owner_pid=4242)
        with self.assertRaises(agent_sessions.LeaseHeld):
            agent_sessions.lease_take(
                self.sf, self.rid, owner_pid=777,
                now=self.now + 1, pid_alive=lambda pid: False,
            )

    def test_a_record_with_no_lease_is_takeable(self):
        self.sf, line = agent_sessions.lease_take(
            self.sf, self.rid, owner_pid=777, now=self.now
        )
        self.assertTrue(line.startswith(f"LEASED:{self.rid}|"))

    def test_lease_take_mints_a_fresh_nonce_invalidating_the_old_one(self):
        """The old coordinator fails closed rather than double-acting."""
        old = self.freeze(owner_pid=4242)
        self.sf, line = agent_sessions.lease_take(
            self.sf, self.rid, owner_pid=777,
            now=self.now + GRACE + 1, pid_alive=lambda pid: False,
        )
        new = line.split("|")[1]
        self.assertNotEqual(old, new)
        with self.assertRaises(agent_sessions.NonceMismatch):
            agent_sessions.freeze_commit(
                self.sf, self.rid, nonce=old, pane="%1", pane_pid=1, now=self.now
            )


class PidAlivePredicateTests(unittest.TestCase):
    """Fail-closed: only ESRCH proves death."""

    def test_this_process_is_alive(self):
        self.assertTrue(agent_sessions._pid_alive(os.getpid()))

    def test_pid_zero_and_negative_are_not_alive(self):
        self.assertFalse(agent_sessions._pid_alive(0))
        self.assertFalse(agent_sessions._pid_alive(-1))

    def test_a_reaped_child_is_dead(self):
        proc = subprocess.Popen([sys.executable, "-c", ""])
        proc.wait()
        self.assertFalse(agent_sessions._pid_alive(proc.pid))

    def test_pid_1_is_alive_though_unverifiable(self):
        """EPERM means 'exists, not yours' — treated as ALIVE, never dead."""
        self.assertTrue(agent_sessions._pid_alive(1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
