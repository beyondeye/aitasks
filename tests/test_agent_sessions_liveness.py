"""Fail-closed liveness purge for the session store (t1705_2).

The purge must make a FOUR-way distinction, and getting any of them wrong is a
distinct user-visible bug:

  (i)   root enumerated, window still there, pane alive -> record survives
  (ii)  root enumerated, window GONE                    -> `dead_window`
  (iii) root enumerated, window there, pane gone/dead AND its pid dead
                                                        -> `dead_pane`
  (iv)  root NOT enumerated, or the observation is INCOMPLETE, or the root is
        only pane-incomplete -> record survives, always

Case (iii) is what retires the stale records an ambiguous relocation leaves
behind, and it is the one that needs the most evidence: BOTH the pane must be
absent-or-dead in the observation AND the recorded pid must be provably gone.
Either alone is a visibility gap, not a death.

Transitional records (`freezing` / `restoring` / `aborting`) are NEVER purged by
liveness — `aitask_frozen.sh reconcile` resolves those, and deleting a record
mid-freeze would strand the capture files with nothing pointing at them.

NEGATIVE CONTROLS:

  over-deletion (roots)  : drop the `rec.root in observed.roots` term ->
                           `test_an_unenumerated_root_survives_beside_a_swept_one` fails.
  over-deletion (panes)  : drop the `not alive(rec.pane_pid)` term ->
                           `test_a_missing_pane_with_a_live_pid_survives` fails.
  over-deletion (partial): drop the `pane_complete` guard ->
                           `test_pane_incomplete_root_keeps_dead_pane_records` fails.
  under-deletion         : infer sweepable roots from `observed.windows` keys
                           instead of `roots` ->
                           `test_enumerated_root_with_zero_windows_purges` fails.
  transitional deletion  : purge every state, not just live/frozen ->
                           `test_transitional_records_are_never_purged` fails.

A single-root "nothing was enumerated" case does NOT discriminate against the
first mutation — with empty roots nothing is swept under either implementation.
Only a case with a NON-empty root set plus a record outside it exercises the
membership term, which is why that test carries the control.
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

import agent_sessions as A  # noqa: E402

ALIVE = lambda pid: True        # noqa: E731
DEAD = lambda pid: False        # noqa: E731


class _PurgeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        os.environ[A.FROZEN_DIR_ENV] = str(self.tmp / "frozen")
        self.addCleanup(os.environ.pop, A.FROZEN_DIR_ENV, None)
        self.addCleanup(self._tmp.cleanup)
        self.root = os.path.realpath(str(self.tmp))

    def record(self, sf=None, *, window="agent-pick-1", pane="%1", pane_pid=100,
               root=None, state=A.STATE_LIVE, **kw):
        sf = sf or A.SessionsFile()
        sf, line = A.upsert(
            sf, root=root or self.root, window=window, pane=pane,
            pane_pid=pane_pid, pane_alive=ALIVE,
        )
        rec = sf.by_id(line.split(":")[1].split("|")[0])
        rec.state = state
        for key, value in kw.items():
            setattr(rec, key, value)
        return sf, rec

    @staticmethod
    def obs(*, roots=(), windows=None, panes=None, complete=True, pane_complete=None):
        o = A.Observation(complete=complete)
        o.roots = set(roots)
        o.windows = dict(windows or {})
        o.panes = dict(panes or {})
        if pane_complete is None:
            pane_complete = {r: True for r in o.roots}
        o.pane_complete = dict(pane_complete)
        return o

    @staticmethod
    def ids(lines):
        return sorted(line.split(":")[1].split("|")[0] for line in lines)


class SurvivalTests(_PurgeTestCase):
    def test_a_live_pane_survives(self):
        sf, rec = self.record()
        sf, dropped = A.purge(sf, self.obs(
            roots=[self.root],
            windows={self.root: {"agent-pick-1"}},
            panes={(self.root, "agent-pick-1"): [("%1", 100, 0)]},
        ), pid_alive=ALIVE)
        self.assertEqual(dropped, [])
        self.assertEqual(len(sf.sessions), 1)

    def test_incomplete_suppresses_the_whole_sweep(self):
        sf, rec = self.record()
        sf, dropped = A.purge(sf, self.obs(roots=[self.root], complete=False))
        self.assertEqual(dropped, [])
        self.assertEqual(len(sf.sessions), 1)

    def test_an_unenumerated_root_survives_beside_a_swept_one(self):
        """CONTROL. 'not running', 'list-panes failed' and 'other socket' are
        indistinguishable from outside, and none is evidence an agent died."""
        other = os.path.realpath(str(self.tmp / "other"))
        (self.tmp / "other").mkdir()
        sf, gone = self.record(window="agent-gone")
        sf, elsewhere = self.record(sf, root=other, window="agent-elsewhere")
        sf, dropped = A.purge(sf, self.obs(
            roots=[self.root], windows={self.root: set()},
        ), pid_alive=DEAD)
        self.assertEqual(self.ids(dropped), [gone.id])
        self.assertEqual([r.id for r in sf.sessions], [elsewhere.id])

    def test_a_missing_pane_with_a_live_pid_survives(self):
        """CONTROL. The pid is the second, independent piece of evidence."""
        sf, rec = self.record(pane="%1", pane_pid=100)
        sf, dropped = A.purge(sf, self.obs(
            roots=[self.root],
            windows={self.root: {"agent-pick-1"}},
            panes={(self.root, "agent-pick-1"): [("%9", 900, 0)]},
        ), pid_alive=ALIVE)
        self.assertEqual(dropped, [])

    def test_pane_incomplete_root_keeps_dead_pane_records(self):
        """CONTROL. Windows were enumerated, panes were not — a partial view."""
        sf, rec = self.record()
        sf, dropped = A.purge(sf, self.obs(
            roots=[self.root],
            windows={self.root: {"agent-pick-1"}},
            panes={},
            pane_complete={self.root: False},
        ), pid_alive=DEAD)
        self.assertEqual(dropped, [])
        self.assertEqual(len(sf.sessions), 1)

    def test_transitional_records_are_never_purged(self):
        """CONTROL. Reconcile owns these; deleting one strands its captures."""
        sf = A.SessionsFile()
        for i, state in enumerate(A.TRANSITIONAL_STATES):
            sf, _ = self.record(sf, window=f"agent-{state}", pane=f"%{i}", state=state)
        sf, dropped = A.purge(sf, self.obs(
            roots=[self.root], windows={self.root: set()},
        ), pid_alive=DEAD)
        self.assertEqual(dropped, [])
        self.assertEqual(len(sf.sessions), len(A.TRANSITIONAL_STATES))


class DeadWindowTests(_PurgeTestCase):
    def test_window_gone_from_an_enumerated_root(self):
        sf, rec = self.record()
        sf, dropped = A.purge(sf, self.obs(
            roots=[self.root], windows={self.root: {"agent-other"}},
        ), pid_alive=ALIVE)
        self.assertEqual(dropped, [f"DROPPED:{rec.id}|dead_window"])
        self.assertEqual(sf.sessions, [])

    def test_enumerated_root_with_zero_windows_purges(self):
        """CONTROL on under-deletion: an empty window set is MEANINGFUL.

        The session is up and simply has no agents left, so its records are
        dead. A rule that inferred sweepability from `windows`' keys could not
        express this and would leave them alive forever.
        """
        sf, rec = self.record()
        sf, dropped = A.purge(sf, self.obs(roots=[self.root], windows={}),
                              pid_alive=ALIVE)
        self.assertEqual(dropped, [f"DROPPED:{rec.id}|dead_window"])

    def test_same_window_name_in_two_roots_is_swept_independently(self):
        other = os.path.realpath(str(self.tmp / "other"))
        (self.tmp / "other").mkdir()
        sf, here = self.record(window="agent-pick-1")
        sf, there = self.record(sf, root=other, window="agent-pick-1", pane="%2")
        sf, dropped = A.purge(sf, self.obs(
            roots=[self.root, other],
            windows={self.root: set(), other: {"agent-pick-1"}},
            panes={(other, "agent-pick-1"): [("%2", 100, 0)]},
        ), pid_alive=ALIVE)
        self.assertEqual(self.ids(dropped), [here.id])
        self.assertEqual([r.id for r in sf.sessions], [there.id])


class DeadPaneTests(_PurgeTestCase):
    def test_pane_absent_and_pid_dead(self):
        """Retires the stale records an ambiguous relocation left behind."""
        sf, rec = self.record(pane="%1", pane_pid=100)
        sf, dropped = A.purge(sf, self.obs(
            roots=[self.root],
            windows={self.root: {"agent-pick-1"}},
            panes={(self.root, "agent-pick-1"): [("%9", 900, 0)]},
        ), pid_alive=DEAD)
        self.assertEqual(dropped, [f"DROPPED:{rec.id}|dead_pane"])

    def test_pane_present_but_flagged_dead_and_pid_dead(self):
        sf, rec = self.record(pane="%1", pane_pid=100)
        sf, dropped = A.purge(sf, self.obs(
            roots=[self.root],
            windows={self.root: {"agent-pick-1"}},
            panes={(self.root, "agent-pick-1"): [("%1", 100, 1)]},
        ), pid_alive=DEAD)
        self.assertEqual(dropped, [f"DROPPED:{rec.id}|dead_pane"])

    def test_pane_present_and_alive_survives_even_with_a_dead_pid(self):
        sf, rec = self.record(pane="%1", pane_pid=100)
        sf, dropped = A.purge(sf, self.obs(
            roots=[self.root],
            windows={self.root: {"agent-pick-1"}},
            panes={(self.root, "agent-pick-1"): [("%1", 100, 0)]},
        ), pid_alive=DEAD)
        self.assertEqual(dropped, [])

    def test_the_ambiguous_relocation_pair_is_retired_leaving_the_new_record(self):
        """The end-to-end shape: fail-closed create, then liveness cleanup."""
        sf, a = self.record(pane="%1", pane_pid=100)
        sf, b = self.record(sf, pane="%2", pane_pid=200)
        sf, line = A.upsert(
            sf, root=self.root, window="agent-pick-1", pane="%77",
            pane_pid=777, pane_alive=DEAD,
        )
        self.assertIn("ambiguous_relocation", line)
        fresh = line.split(":")[1].split("|")[0]
        sf, dropped = A.purge(sf, self.obs(
            roots=[self.root],
            windows={self.root: {"agent-pick-1"}},
            panes={(self.root, "agent-pick-1"): [("%77", 777, 0)]},
        ), pid_alive=lambda pid: pid == 777)
        self.assertEqual(self.ids(dropped), sorted([a.id, b.id]))
        self.assertEqual([r.id for r in sf.sessions], [fresh])


class CaptureMissingTests(_PurgeTestCase):
    def test_a_frozen_record_whose_capture_vanished_is_dropped(self):
        sf, rec = self.record(state=A.STATE_FROZEN,
                              capture_ansi=str(self.tmp / "gone.ansi"))
        sf, dropped = A.purge(sf, self.obs(roots=[self.root]), pid_alive=ALIVE)
        self.assertEqual(dropped, [f"DROPPED:{rec.id}|capture_missing"])

    def test_a_frozen_record_with_an_EMPTY_capture_path_is_dropped(self):
        """An empty path is a missing capture, not an exempt one.

        A frozen record exists to hold something the user can still read and
        restore from. With no path there is nothing to show and nothing to
        restore — and because frozen records are deliberately exempt from the
        `dead_window` and `dead_pane` rules, treating "" as "no capture to check"
        leaves the garbage record alive through every future purge.
        """
        sf, rec = self.record(state=A.STATE_FROZEN, capture_ansi="")
        sf, dropped = A.purge(sf, self.obs(roots=[self.root]), pid_alive=ALIVE)
        self.assertEqual(dropped, [f"DROPPED:{rec.id}|capture_missing"])
        self.assertEqual(sf.sessions, [])

    def test_a_frozen_record_with_its_capture_survives(self):
        capture = self.tmp / "here.ansi"
        capture.write_text("x", encoding="utf-8")
        sf, rec = self.record(state=A.STATE_FROZEN, capture_ansi=str(capture))
        sf, dropped = A.purge(sf, self.obs(roots=[self.root]), pid_alive=ALIVE)
        self.assertEqual(dropped, [])

    def test_a_frozen_record_is_never_dropped_for_a_dead_window(self):
        """It is restorable into a fresh window; the window name is reusable."""
        capture = self.tmp / "here.ansi"
        capture.write_text("x", encoding="utf-8")
        sf, rec = self.record(state=A.STATE_FROZEN, capture_ansi=str(capture))
        sf, dropped = A.purge(sf, self.obs(
            roots=[self.root], windows={self.root: set()},
        ), pid_alive=DEAD)
        self.assertEqual(dropped, [])

    def test_a_dropped_record_takes_its_capture_directory_with_it(self):
        sf, rec = self.record()
        d = A.ensure_capture_dir(rec.id)
        (d / "capture.ansi").write_text("x", encoding="utf-8")
        sf, dropped = A.purge(sf, self.obs(
            roots=[self.root], windows={self.root: set()},
        ), pid_alive=ALIVE)
        self.assertEqual(len(dropped), 1)
        self.assertFalse(d.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
