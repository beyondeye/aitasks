"""Identity + `(root, window)` conflict policy for the session store (t1705_2).

`upsert` is the ONLY creator of records, and its resolution order is the part of
the pinned contract most likely to go subtly wrong: every branch produces a
plausible-looking record, and picking the wrong one silently binds a pane to
another agent's history.

NEGATIVE CONTROLS (each mutation must make this module FAIL, not merely change
coverage):

  fail-open relocation : in `upsert`, change the `len(dead) == 1` guard to
                         `len(dead) >= 1` (i.e. adopt the first of several
                         ambiguous candidates) ->
                         `test_two_dead_candidates_fail_closed_and_create` fails.
  over-eager relocation: drop the `not alive(r.pane_pid)` term so any live
                         sibling is a candidate ->
                         `test_a_live_sibling_is_never_relocated_onto` fails.
  pane recycling       : select by `pane_id` without requiring the
                         `(root, window)` match ->
                         `test_recycled_pane_id_in_another_window_creates` fails.

A single-candidate test does NOT discriminate against the fail-open mutation --
with one candidate both `== 1` and `>= 1` relocate. Only a case with TWO dead
candidates exercises the closed branch, which is why that test carries the
control and `test_single_dead_candidate_is_relocated` is its paired positive.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_sessions  # noqa: E402

ALIVE = lambda pid: True        # noqa: E731
DEAD = lambda pid: False        # noqa: E731


class _UpsertTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        # realpath, because that is what records store: on macOS the temp dir is
        # /var/... -> /private/var/..., so a raw str() would silently miss every
        # `sf.at()` lookup and make root-keyed assertions pass vacuously.
        self.root = os.path.realpath(str(self.tmp))
        os.environ[agent_sessions.FROZEN_DIR_ENV] = str(self.tmp / "frozen")
        self.addCleanup(os.environ.pop, agent_sessions.FROZEN_DIR_ENV, None)
        self.addCleanup(self._tmp.cleanup)
        self.sf = agent_sessions.SessionsFile()

    def up(self, **kw):
        kw.setdefault("root", self.root)
        kw.setdefault("window", "agent-pick-1")
        kw.setdefault("pane", "%1")
        kw.setdefault("pane_pid", 100)
        kw.setdefault("pane_alive", ALIVE)
        self.sf, line = agent_sessions.upsert(self.sf, **kw)
        return line

    @staticmethod
    def rid(line: str) -> str:
        return line.split(":")[1].split("|")[0]

    @staticmethod
    def disposition(line: str) -> str:
        return line.split("|", 1)[1]


class CreateTests(_UpsertTestCase):
    def test_first_agent_creates_slot_zero(self):
        line = self.up()
        self.assertEqual(self.disposition(line), "created")
        self.assertEqual(self.sf.sessions[0].window_slot, 0)
        self.assertEqual(self.sf.sessions[0].state, agent_sessions.STATE_LIVE)

    def test_a_live_sibling_is_never_relocated_onto(self):
        """A second agent split into the same window gets its own slot."""
        self.up(pane="%1", pane_pid=100)
        line = self.up(pane="%2", pane_pid=200)
        self.assertEqual(self.disposition(line), "created_slot1")
        self.assertEqual(len(self.sf.sessions), 2)

    def test_slot_allocation_fills_the_lowest_gap(self):
        self.up(pane="%1", pane_pid=100)
        self.up(pane="%2", pane_pid=200)
        self.sf.sessions = [r for r in self.sf.sessions if r.window_slot != 0]
        line = self.up(pane="%3", pane_pid=300)
        self.assertEqual(self.disposition(line), "created_slot0")

    def test_a_retained_frozen_record_never_blocks_a_live_launch(self):
        first = self.rid(self.up())
        self.sf.by_id(first).state = agent_sessions.STATE_FROZEN
        line = self.up(pane="%9", pane_pid=900)
        self.assertEqual(self.disposition(line), "created_slot1")
        self.assertEqual(self.sf.by_id(first).state, agent_sessions.STATE_FROZEN)

    def test_agent_kind_is_derived_from_the_agent_string(self):
        rid = self.rid(self.up(agent_string="claudecode/opus5"))
        self.assertEqual(self.sf.by_id(rid).agent_kind, "claudecode")

    def test_session_name_is_stored(self):
        """The pinned schema carries `session`; without --session it is unwritable."""
        rid = self.rid(self.up(session="aitasks"))
        self.assertEqual(self.sf.by_id(rid).session, "aitasks")


class RelocationTests(_UpsertTestCase):
    def test_same_pane_id_updates_in_place(self):
        rid = self.rid(self.up(pane="%1", pane_pid=100))
        line = self.up(pane="%1", pane_pid=101)
        self.assertEqual(self.disposition(line), "updated")
        self.assertEqual(self.rid(line), rid)
        self.assertEqual(self.sf.by_id(rid).pane_pid, 101)
        self.assertEqual(len(self.sf.sessions), 1)

    def test_single_dead_candidate_is_relocated(self):
        """The tmux-restart / reattach case: no second record."""
        rid = self.rid(self.up(pane="%1", pane_pid=100))
        line = self.up(pane="%77", pane_pid=777, pane_alive=DEAD)
        self.assertEqual(self.disposition(line), "updated")
        self.assertEqual(self.rid(line), rid)
        self.assertEqual(self.sf.by_id(rid).pane_id, "%77")

    def test_two_dead_candidates_fail_closed_and_create(self):
        """CONTROL. Nothing distinguishes two pre-restart agents; never guess."""
        self.up(pane="%1", pane_pid=100)
        self.up(pane="%2", pane_pid=200)
        line = self.up(pane="%77", pane_pid=777, pane_alive=DEAD)
        self.assertEqual(self.disposition(line), "created_slot2|ambiguous_relocation")
        self.assertEqual(len(self.sf.sessions), 3)

    def test_ambiguous_relocation_leaves_the_stale_records_for_purge(self):
        a = self.rid(self.up(pane="%1", pane_pid=100))
        b = self.rid(self.up(pane="%2", pane_pid=200))
        self.up(pane="%77", pane_pid=777, pane_alive=DEAD)
        self.assertEqual(self.sf.by_id(a).pane_id, "%1")
        self.assertEqual(self.sf.by_id(b).pane_id, "%2")

    def test_recycled_pane_id_in_another_window_creates(self):
        """CONTROL. A recycled %N attaches to nothing on its own."""
        self.up(window="agent-pick-1", pane="%5", pane_pid=100)
        line = self.up(window="agent-qa-9", pane="%5", pane_pid=500)
        self.assertEqual(self.disposition(line), "created")
        self.assertEqual(len(self.sf.sessions), 2)

    def test_explicit_id_wins_over_root_window(self):
        """A renamed window keeps its record."""
        rid = self.rid(self.up(window="agent-pick-1"))
        line = self.up(id=rid, window="agent-renamed", pane="%3", pane_pid=300)
        self.assertEqual(self.rid(line), rid)
        self.assertEqual(self.disposition(line), "updated")
        self.assertEqual(len(self.sf.sessions), 1)

    def test_a_renamed_window_is_written_back_to_the_record(self):
        """CONTROL (t1705_2 A10). "Keeps its record" is not enough on its own.

        Selecting by `--id` and leaving `window` stale looks harmless — the
        record is still there, still `live`, still pointing at the right pane.
        The damage lands one purge later: the record names a window that no
        longer exists, so the liveness sweep drops it as `dead_window` and the
        agent silently becomes unfreezable and unrestorable.
        `test_a_renamed_window_survives_the_next_purge` is the end-to-end half.
        """
        rid = self.rid(self.up(window="agent-pick-1"))
        self.up(id=rid, window="agent-renamed", pane="%1", pane_pid=100)
        self.assertEqual(self.sf.by_id(rid).window, "agent-renamed")

    def test_a_renamed_window_survives_the_next_purge(self):
        rid = self.rid(self.up(window="agent-pick-1"))
        self.up(id=rid, window="agent-renamed", pane="%1", pane_pid=100)
        obs = agent_sessions.Observation(complete=True)
        obs.roots = {self.root}
        obs.windows = {self.root: {"agent-renamed"}}
        obs.panes = {(self.root, "agent-renamed"): [("%1", 100, 0)]}
        obs.pane_complete = {self.root: True}
        self.sf, dropped = agent_sessions.purge(self.sf, obs, pid_alive=ALIVE)
        self.assertEqual(dropped, [])
        self.assertEqual(len(self.sf.sessions), 1)

    def test_a_rename_into_an_occupied_window_takes_a_free_slot(self):
        """The old slot number means nothing under the new (root, window)."""
        self.up(window="agent-target", pane="%9", pane_pid=900)
        rid = self.rid(self.up(window="agent-source", pane="%1", pane_pid=100))
        self.up(id=rid, window="agent-target", pane="%1", pane_pid=100)
        moved = self.sf.by_id(rid)
        self.assertEqual(moved.window, "agent-target")
        self.assertEqual(moved.window_slot, 1)
        slots = [r.window_slot for r in self.sf.at(self.root, "agent-target")]
        self.assertEqual(sorted(slots), [0, 1], "slots must stay unique per window")

    def test_a_same_window_update_keeps_its_slot(self):
        self.up(window="agent-pick-1", pane="%1", pane_pid=100)
        rid = self.rid(self.up(window="agent-pick-1", pane="%2", pane_pid=200))
        self.assertEqual(self.sf.by_id(rid).window_slot, 1)
        self.up(id=rid, window="agent-pick-1", pane="%2", pane_pid=201)
        self.assertEqual(self.sf.by_id(rid).window_slot, 1)


class RefusalTests(_UpsertTestCase):
    """Select first, then gate on state (plan §C2)."""

    def _in_state(self, state):
        rid = self.rid(self.up(pane="%1", pane_pid=100))
        self.sf.by_id(rid).state = state
        return rid

    def test_refusal_reason_per_transitional_state(self):
        cases = {
            agent_sessions.STATE_FREEZING: "freezing_unacknowledged",
            agent_sessions.STATE_RESTORING: "restoring_unacknowledged",
            agent_sessions.STATE_ABORTING: "aborting_unacknowledged",
            agent_sessions.STATE_FROZEN: "frozen",
        }
        for state, reason in cases.items():
            with self.subTest(state=state):
                self.setUp()
                rid = self._in_state(state)
                line = self.up(pane="%1", pane_pid=100)
                self.assertEqual(line, f"UPSERT_REFUSED:{rid}|{reason}")

    def test_a_frozen_record_selected_by_id_refuses(self):
        """A hook firing in a stand-in pane is a bug — the pane carries --id."""
        rid = self._in_state(agent_sessions.STATE_FROZEN)
        line = self.up(id=rid, pane="%1", pane_pid=100)
        self.assertEqual(line, f"UPSERT_REFUSED:{rid}|frozen")

    def test_a_transitional_sibling_is_not_a_candidate_for_another_pane(self):
        """Not selected -> not refused either: it falls through to create."""
        self._in_state(agent_sessions.STATE_RESTORING)
        line = self.up(pane="%2", pane_pid=200)
        self.assertEqual(self.disposition(line), "created_slot1")

    def test_a_refusal_writes_nothing(self):
        rid = self._in_state(agent_sessions.STATE_FREEZING)
        before = vars(self.sf.by_id(rid)).copy()
        self.up(pane="%1", pane_pid=999, agent_string="other/x")
        self.assertEqual(vars(self.sf.by_id(rid)), before)


class RestoreAckTests(_UpsertTestCase):
    """The `--restore-of` branch: selects the OLD record from a brand-new pane."""

    def _restoring(self, mode="resume", session_id="sid-1"):
        rid = self.rid(self.up(pane="%1", pane_pid=100, session_id=session_id))
        rec = self.sf.by_id(rid)
        rec.state = agent_sessions.STATE_FROZEN
        self.sf, line = agent_sessions.restore_begin(
            self.sf, rid, mode=mode, owner_pid=os.getpid()
        )
        return rid, line.split("|")[1]

    def test_successful_resume_ack(self):
        rid, nonce = self._restoring()
        line = self.up(
            pane="%42", pane_pid=4242, restore_of=rid, nonce=nonce, session_id="sid-1"
        )
        self.assertEqual(line, f"UPSERTED:{rid}|restored")
        rec = self.sf.by_id(rid)
        self.assertEqual(rec.state, agent_sessions.STATE_LIVE)
        self.assertEqual(rec.ack, "hook")
        self.assertEqual(rec.pane_id, "%42")
        self.assertEqual(rec.op_nonce, "")
        self.assertEqual(len(self.sf.sessions), 1)

    def test_wrong_nonce_is_a_nonce_mismatch(self):
        rid, _ = self._restoring()
        with self.assertRaises(agent_sessions.NonceMismatch):
            self.up(pane="%42", pane_pid=4242, restore_of=rid, nonce="deadbeef")

    def test_session_mismatch_persists_last_error_then_raises(self):
        """The record IS the channel: the hook cannot reach the coordinator."""
        rid, nonce = self._restoring(session_id="sid-1")
        with self.assertRaises(agent_sessions.SessionMismatch):
            self.up(
                pane="%42", pane_pid=4242, restore_of=rid, nonce=nonce,
                session_id="a-different-session",
            )
        rec = self.sf.by_id(rid)
        self.assertEqual(rec.last_error, f"{nonce}:session_mismatch")
        self.assertEqual(rec.state, agent_sessions.STATE_RESTORING)

    def test_repick_mode_adopts_the_new_session_id(self):
        rid, nonce = self._restoring(mode="repick", session_id="old-sid")
        line = self.up(
            pane="%42", pane_pid=4242, restore_of=rid, nonce=nonce, session_id="new-sid"
        )
        self.assertEqual(line, f"UPSERTED:{rid}|restored")
        self.assertEqual(self.sf.by_id(rid).codeagent_session_id, "new-sid")

    def test_ack_deletes_the_captures(self):
        rid, nonce = self._restoring()
        rec = self.sf.by_id(rid)
        d = agent_sessions.ensure_capture_dir(rid)
        (d / "capture.ansi").write_text("x", encoding="utf-8")
        rec.capture_ansi = str(d / "capture.ansi")
        self.up(pane="%42", pane_pid=4242, restore_of=rid, nonce=nonce, session_id="sid-1")
        self.assertFalse(d.exists())
        self.assertEqual(self.sf.by_id(rid).capture_ansi, "")

    def test_restore_of_a_non_restoring_record_is_refused(self):
        rid = self.rid(self.up())
        with self.assertRaises(agent_sessions.TransitionRefused):
            self.up(pane="%42", pane_pid=4242, restore_of=rid, nonce="aabbccdd")


if __name__ == "__main__":
    unittest.main(verbosity=2)
