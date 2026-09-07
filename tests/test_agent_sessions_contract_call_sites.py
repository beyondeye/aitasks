"""Contract conformance for every §C/§D call site (t1705_2, inline post-phase).

WHY THIS EXISTS. The t1705 pinned contract specifies the store in one section
(§A: schema, verbs, state machine) and CALLS it from two others (§C: the freeze
flow and the reconcile table; §D: the restore flow). Nothing mechanically ties
the two halves together, and re-reading them by eye has now missed defects
twice:

  * A3 — §C's reconcile row "freezing / pane dead -> respawn the stand-in,
    `standin-respawned`, then re-check" invokes a verb §A did not admit from
    `freezing`. A STATE-legality defect.
  * A7 — §C and §D both say the lease records "the coordinator's" pid, but §A's
    forms for `freeze-begin` / `restore-begin` / `lease-take` had no argument to
    carry one. An ARGUMENT-SHAPE defect.

Those two failure modes are different, and a table that checks only one of them
catches only one of the two defects. So every row below is checked BOTH ways:
the `(state, verb)` pair must be legal (or refused with the pinned wire line),
AND the arguments the call site supplies must be exactly what the verb requires
and accepts.

HOW TO USE IT. `CALL_SITES` is a transcription of the pinned tables, not a
derivation from the implementation — that is the whole point. When a row here
cannot be satisfied, the contract is wrong and the fix is upstream in the parent
plan (as it was for A3 and A7); do NOT relax the row to match the code.
"""
from __future__ import annotations

import inspect
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

#: verb -> the transition function it dispatches to.
VERB_FN = {
    "upsert": A.upsert,
    "freeze-begin": A.freeze_begin,
    "freeze-commit": A.freeze_commit,
    "freeze-abort": A.freeze_abort,
    "restore-begin": A.restore_begin,
    "restore-launched": A.restore_launched,
    "restore-confirm": A.restore_confirm,
    "restore-abort": A.restore_abort,
    "standin-respawned": A.standin_respawned,
    "lease-take": A.lease_take,
    "drop": A.drop,
}

# Every invocation the pinned §C and §D name, as (source, record state, verb,
# argument names supplied). `None` for the state means "any".
CALL_SITES = [
    # --- §C freeze flow -----------------------------------------------------
    ("C.freeze.1 fallback record resolution", A.STATE_LIVE, "upsert",
     ["root", "window", "pane", "pane_pid"]),
    ("C.freeze.3 begin", A.STATE_LIVE, "freeze-begin",
     ["capture_ansi", "capture_txt", "lines", "phase", "owner_pid"]),
    ("C.freeze.6 commit", A.STATE_FREEZING, "freeze-commit",
     ["nonce", "pane", "pane_pid"]),
    ("C.freeze.4-fail abort", A.STATE_FREEZING, "freeze-abort", ["nonce"]),
    # --- §C reconcile table -------------------------------------------------
    ("C.rec freezing + standin up -> commit", A.STATE_FREEZING, "freeze-commit",
     ["nonce", "pane", "pane_pid"]),
    ("C.rec freezing + agent alive -> abort", A.STATE_FREEZING, "freeze-abort",
     ["nonce"]),
    # THE A3 ROW. Called on a `freezing` record; §A's verb list did not admit it.
    ("C.rec freezing + pane dead -> respawn standin", A.STATE_FREEZING,
     "standin-respawned", ["nonce", "pane", "pane_pid"]),
    ("C.rec freezing + pane gone -> gone-pane commit", A.STATE_FREEZING,
     "freeze-commit", ["nonce", "pane", "pane_pid"]),
    # THE A7 ROW. Reconcile must lease-take before acting on a leased record.
    ("C.rec frozen + pane dead -> lease-take", A.STATE_FROZEN, "lease-take",
     ["owner_pid"]),
    ("C.rec frozen + pane dead -> respawn standin", A.STATE_FROZEN,
     "standin-respawned", ["nonce", "pane", "pane_pid"]),
    ("C.rec restoring + mismatch -> abort", A.STATE_RESTORING, "restore-abort",
     ["nonce"]),
    ("C.rec aborting -> standin back", A.STATE_ABORTING, "standin-respawned",
     ["nonce", "pane", "pane_pid"]),
    ("C.rec restoring + replacement here -> confirm", A.STATE_RESTORING,
     "restore-confirm", ["nonce", "pane", "pane_pid"]),
    ("C.kill_agent_pane_smart on a frozen pane -> drop", A.STATE_FROZEN, "drop", []),
    # --- §D restore flow ----------------------------------------------------
    ("D.restore.2 begin", A.STATE_FROZEN, "restore-begin", ["mode", "owner_pid"]),
    ("D.restore.3 launched", A.STATE_RESTORING, "restore-launched",
     ["nonce", "pane", "pane_pid"]),
    ("D.restore.4 hook ack", A.STATE_RESTORING, "upsert",
     ["root", "window", "pane", "pane_pid", "restore_of", "nonce", "session_id"]),
    ("D.restore.4 liveness confirm", A.STATE_RESTORING, "restore-confirm",
     ["nonce", "pane", "pane_pid"]),
    ("D.restore.4 agent_exited -> abort", A.STATE_RESTORING, "restore-abort",
     ["nonce"]),
]

#: Arguments every transition accepts implicitly (not named by a call site).
IMPLICIT = {"sf", "record_id", "id", "now", "pane_alive", "pid_alive"}


class ArgumentShapeTests(unittest.TestCase):
    """Does each verb ACCEPT what its call site passes, and REQUIRE no more?

    This is the assertion A7 needed and a (state, verb) table cannot give.
    """

    def _signature(self, verb):
        params = inspect.signature(VERB_FN[verb]).parameters
        accepted = {n for n in params if n not in IMPLICIT}
        required = {
            n for n, p in params.items()
            if n not in IMPLICIT
            and p.default is inspect.Parameter.empty
            and p.kind is inspect.Parameter.KEYWORD_ONLY
        }
        return accepted, required

    def test_every_call_site_argument_is_accepted(self):
        for label, _state, verb, args in CALL_SITES:
            with self.subTest(call_site=label):
                accepted, _ = self._signature(verb)
                unknown = set(args) - accepted
                self.assertEqual(
                    unknown, set(),
                    f"{label}: '{verb}' does not accept {sorted(unknown)}",
                )

    def test_every_required_argument_is_supplied(self):
        for label, _state, verb, args in CALL_SITES:
            with self.subTest(call_site=label):
                _, required = self._signature(verb)
                missing = required - set(args)
                self.assertEqual(
                    missing, set(),
                    f"{label}: '{verb}' requires {sorted(missing)}, "
                    f"which this call site does not pass",
                )

    def test_the_lease_minting_verbs_all_take_an_explicit_owner_pid(self):
        """A7, stated positively and independently of the table above.

        `op_owner_pid` exists to answer "is the coordinator still alive?". If a
        minting verb could be called without one, the wrapper would have to
        invent it — and the only pid it has is its own, which dies immediately,
        collapsing the staleness test to a bare timer.
        """
        for verb in ("freeze-begin", "restore-begin", "lease-take"):
            with self.subTest(verb=verb):
                _, required = self._signature(verb)
                self.assertIn(
                    "owner_pid", required,
                    f"{verb} must REQUIRE owner_pid, never default it",
                )


class StateLegalityTests(unittest.TestCase):
    """Is each call site's `(state, verb)` pair actually legal?

    This is the assertion A3 needed. It runs the real transition rather than
    consulting a table, so it cannot drift from the implementation.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        os.environ[A.FROZEN_DIR_ENV] = str(self.tmp / "frozen")
        self.addCleanup(os.environ.pop, A.FROZEN_DIR_ENV, None)
        self.addCleanup(self._tmp.cleanup)
        self.now = time.time()

    NONCE = "aabbccdd"

    def _fixture(self, state, verb):
        """A store parked in `state`, plus kwargs good enough to execute."""
        sf = A.SessionsFile()
        sf, line = A.upsert(
            sf, root=str(self.tmp), window="agent-pick-1", pane="%1",
            pane_pid=100, pane_alive=lambda pid: True, now=self.now,
            session_id="sid-1",
        )
        rid = line.split(":")[1].split("|")[0]
        rec = sf.by_id(rid)
        rec.state = state
        rec.state_at = A._iso(self.now)
        rec.launch_pid = 555
        rec.restore_mode = "resume"
        if state != A.STATE_LIVE:
            rec.op_nonce = self.NONCE
            rec.op_owner_pid = os.getpid()
            rec.op_started_at = A._iso(self.now)

        kwargs = {
            "nonce": self.NONCE, "pane": "%5", "pane_pid": 555,
            "capture_ansi": "/a", "capture_txt": "/b", "lines": 1, "phase": "",
            "owner_pid": os.getpid(), "mode": "resume",
        }
        return sf, rid, kwargs

    def test_every_call_site_state_verb_pair_is_legal(self):
        for label, state, verb, args in CALL_SITES:
            if verb == "upsert":
                continue  # exercised by its own module; not a (state, verb) row
            with self.subTest(call_site=label):
                sf, rid, kwargs = self._fixture(state, verb)
                accepted = set(inspect.signature(VERB_FN[verb]).parameters)
                call_kwargs = {
                    k: v for k, v in kwargs.items()
                    if k in accepted and k in set(args)
                }
                if "now" in accepted:
                    call_kwargs["now"] = self.now
                try:
                    VERB_FN[verb](sf, rid, **call_kwargs)
                except A.LeaseHeld:
                    # NOT a contract violation. §C: "a LEASE_HELD answer means a
                    # live coordinator owns it and reconcile skips" — it is a
                    # runtime contention answer, and the fixture's lease is
                    # deliberately live. Staleness is covered by its own test
                    # below and by test_agent_sessions_lease.py.
                    pass
                except A.TransitionRefused as exc:
                    self.fail(
                        f"{label}: the pinned contract calls '{verb}' on a "
                        f"'{state}' record, but the state machine refuses it "
                        f"({exc}). Fix the CONTRACT upstream — do not relax "
                        f"this row."
                    )

    def test_lease_take_precedes_every_reconcile_action_on_a_leased_record(self):
        """§C: 'Every reconcile action on a leased record is preceded by
        lease-take; a LEASE_HELD answer means a live coordinator owns it.'

        So `lease-take` must be reachable from every non-live state — otherwise
        reconcile could never legally acquire the records it exists to resolve.
        """
        for state in A.STATES:
            with self.subTest(state=state):
                sf, rid, _ = self._fixture(state, "lease-take")
                sf.by_id(rid).op_started_at = A._iso(self.now - 10_000)
                sf, line = A.lease_take(
                    sf, rid, owner_pid=os.getpid(),
                    now=self.now, pid_alive=lambda pid: False,
                )
                self.assertTrue(line.startswith(f"LEASED:{rid}|"))


class WireLineTests(unittest.TestCase):
    """The strings §C/§D branch on must be exactly what the store emits."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        os.environ[A.FROZEN_DIR_ENV] = str(self.tmp / "frozen")
        self.addCleanup(os.environ.pop, A.FROZEN_DIR_ENV, None)
        self.addCleanup(self._tmp.cleanup)

    def test_last_error_shape_is_what_reconcile_matches_on(self):
        """§C: 'mismatch = last_error begins with the current op_nonce'."""
        sf = A.SessionsFile()
        sf, line = A.upsert(
            sf, root=str(self.tmp), window="w", pane="%1", pane_pid=1,
            pane_alive=lambda pid: True, session_id="sid-1",
        )
        rid = line.split(":")[1].split("|")[0]
        sf.by_id(rid).state = A.STATE_FROZEN
        sf, line = A.restore_begin(sf, rid, mode="resume", owner_pid=os.getpid())
        nonce = line.split("|")[1]
        with self.assertRaises(A.SessionMismatch):
            A.upsert(
                sf, root=str(self.tmp), window="w", pane="%2", pane_pid=2,
                restore_of=rid, nonce=nonce, session_id="a-different-one",
                pane_alive=lambda pid: True,
            )
        self.assertTrue(sf.by_id(rid).last_error.startswith(nonce + ":"))

    def test_exit_code_map_covers_every_raisable_exception(self):
        """The wrapper's documented codes and the module's map must agree."""
        raisable = {
            A.MalformedSessionsError: 4,
            A.TransitionRefused: 5,
            A.NonceMismatch: 6,
            A.SessionMismatch: 7,
            A.LeaseHeld: 8,
        }
        self.assertEqual(A._EXIT_CODES, raisable)


if __name__ == "__main__":
    unittest.main(verbosity=2)
