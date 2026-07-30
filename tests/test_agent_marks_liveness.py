"""Fail-closed liveness-sweep policy for agent marks (t1326).

The sweep must make a **three-way** distinction, and getting any of the three
wrong is a distinct user-visible bug:

  (i)  session enumerated, window still there  -> mark survives
  (ii) session enumerated, window GONE         -> mark is purged  (promptly:
       this is the behaviour the feature exists for; falling back to the 2-day
       TTL here would be a silent regression)
  (iii) session NOT enumerated                 -> mark survives, always
       ("not running", "list-panes failed" and "on another tmux socket" are
       indistinguishable from outside, and none is evidence an agent died)

Case (ii) vs (iii) is the whole reason `sweepable_roots` is passed separately
from `observed`: a sweepable root with an EMPTY window set is meaningful, and a
rule that inferred sweepability from `observed`'s keys could not express it.

NEGATIVE CONTROLS (both directions must be provable, see the plan's Verification
section). Each mutation must make this module FAIL, not merely change coverage:

  over-deletion  : in `sweep_liveness`, drop the `m.root in sweepable_roots`
                   term. This is caught by the MIXED-root tests --
                   `test_unenumerated_root_survives_alongside_a_swept_one` and
                   `test_same_window_name_in_two_roots_is_swept_independently`.
  under-deletion : make `sweepable_roots` default to `set(observed)` instead of
                   the caller's set -> `test_enumerated_session_with_zero_agents
                   _purges_its_marks` fails.

A single-root "nothing was enumerated" case does NOT discriminate against the
over-deletion mutation, and must not be relied on as the control: with an empty
`sweepable_roots` the `if not sweepable_roots: return []` early return fires
first, so such a test passes under the broken implementation too. Only a case
with a NON-empty sweepable set plus a root outside it exercises the membership
term. `test_unenumerated_session_is_never_swept` is kept for the early return
it does guard, but it is deliberately not the control.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_marks  # noqa: E402

ROOT_A = "/repo/alpha"
ROOT_B = "/repo/beta"


def _marks(*entries: tuple[str, str]) -> agent_marks.MarksFile:
    mf = agent_marks.MarksFile(version=agent_marks.SCHEMA_VERSION, marks=[])
    for root, window in entries:
        agent_marks.toggle(mf, root, window, now=1_700_000_000)
    return mf


def _windows(mf: agent_marks.MarksFile) -> list[str]:
    return sorted(f"{m.root}:{m.window}" for m in mf.marks)


class ThreeWayDistinctionTests(unittest.TestCase):
    def test_enumerated_session_with_live_window_keeps_its_mark(self):
        mf = _marks((ROOT_A, "agent-t1"))
        dropped = agent_marks.sweep_liveness(
            mf, {ROOT_A: {"agent-t1"}}, {ROOT_A}
        )
        self.assertEqual(dropped, [])
        self.assertEqual(_windows(mf), [f"{ROOT_A}:agent-t1"])

    def test_enumerated_session_with_dead_window_purges_that_mark(self):
        mf = _marks((ROOT_A, "agent-alive"), (ROOT_A, "agent-gone"))
        dropped = agent_marks.sweep_liveness(
            mf, {ROOT_A: {"agent-alive"}}, {ROOT_A}
        )
        self.assertEqual([d.window for d in dropped], ["agent-gone"])
        self.assertEqual(_windows(mf), [f"{ROOT_A}:agent-alive"])

    def test_enumerated_session_with_zero_agents_purges_its_marks(self):
        """Case (ii) at its limit — the session is up, every agent has exited.

        A rule keyed on "root has >=1 observed pane" would leave these alive
        until the TTL, which is exactly the gap this design closes.
        """
        mf = _marks((ROOT_A, "agent-t1"), (ROOT_A, "agent-t2"))
        dropped = agent_marks.sweep_liveness(mf, {}, {ROOT_A})
        self.assertEqual(sorted(d.window for d in dropped), ["agent-t1", "agent-t2"])
        self.assertEqual(_windows(mf), [])

    def test_unenumerated_session_is_never_swept(self):
        """Case (iii) — the fail-closed direction, and the dangerous one to get
        wrong: a wrong drop silently destroys user intent."""
        mf = _marks((ROOT_B, "agent-t9"))
        dropped = agent_marks.sweep_liveness(mf, {}, set())
        self.assertEqual(dropped, [])
        self.assertEqual(_windows(mf), [f"{ROOT_B}:agent-t9"])

    def test_unenumerated_root_survives_alongside_a_swept_one(self):
        """The mixed case a single-session monitor actually produces."""
        mf = _marks((ROOT_A, "agent-gone"), (ROOT_B, "agent-elsewhere"))
        dropped = agent_marks.sweep_liveness(mf, {}, {ROOT_A})
        self.assertEqual([d.window for d in dropped], ["agent-gone"])
        self.assertEqual(_windows(mf), [f"{ROOT_B}:agent-elsewhere"])


class IncompleteObservationTests(unittest.TestCase):
    def test_incomplete_suppresses_the_entire_sweep(self):
        """One unattributable agent pane suppresses everything.

        Without this, a pane that failed strict root resolution is missing from
        `observed[root]` while its root may still be sweepable — so its live
        mark would be deleted. A visibility gap must never cause a deletion.
        """
        mf = _marks((ROOT_A, "agent-gone"))
        dropped = agent_marks.sweep_liveness(
            mf, {ROOT_A: set()}, {ROOT_A}, complete=False
        )
        self.assertEqual(dropped, [])
        self.assertEqual(_windows(mf), [f"{ROOT_A}:agent-gone"])

    def test_empty_sweepable_set_is_a_no_op(self):
        mf = _marks((ROOT_A, "agent-t1"))
        self.assertEqual(agent_marks.sweep_liveness(mf, {ROOT_A: set()}, set()), [])
        self.assertEqual(len(mf.marks), 1)


class CrossRepoCollisionTests(unittest.TestCase):
    """Two repos whose tmux sessions both fall back to the name "aitasks" is
    the motivating collision: identical window names, different roots."""

    def test_same_window_name_in_two_roots_is_swept_independently(self):
        mf = _marks((ROOT_A, "agent-pick-42"), (ROOT_B, "agent-pick-42"))
        dropped = agent_marks.sweep_liveness(mf, {}, {ROOT_A})
        self.assertEqual([d.root for d in dropped], [ROOT_A])
        self.assertEqual(_windows(mf), [f"{ROOT_B}:agent-pick-42"])

    def test_a_live_window_in_one_root_does_not_protect_the_other(self):
        mf = _marks((ROOT_A, "agent-pick-42"), (ROOT_B, "agent-pick-42"))
        dropped = agent_marks.sweep_liveness(
            mf, {ROOT_A: {"agent-pick-42"}, ROOT_B: set()}, {ROOT_A, ROOT_B}
        )
        self.assertEqual([d.root for d in dropped], [ROOT_B])
        self.assertEqual(_windows(mf), [f"{ROOT_A}:agent-pick-42"])


class ObservationFileTests(unittest.TestCase):
    """The TSV the TUI hands the purge verb. It declares roots separately from
    windows precisely so a zero-window enumerated root can be expressed."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _write(self, body: str) -> str:
        path = self.tmp / "obs.tsv"
        path.write_text(body, encoding="utf-8")
        return str(path)

    def test_roots_and_windows_round_trip(self):
        observed, roots, complete = agent_marks._read_observed(
            self._write(f"ROOT\t{self.tmp}\nWINDOW\t{self.tmp}\tagent-t1\n")
        )
        real = str(self.tmp.resolve())
        self.assertEqual(roots, {real})
        self.assertEqual(observed, {real: {"agent-t1"}})
        self.assertTrue(complete)

    def test_root_with_no_windows_is_expressible(self):
        observed, roots, complete = agent_marks._read_observed(
            self._write(f"ROOT\t{self.tmp}\n")
        )
        self.assertEqual(roots, {str(self.tmp.resolve())})
        self.assertEqual(observed, {})
        self.assertTrue(complete)

    def test_incomplete_marker_is_parsed(self):
        _, _, complete = agent_marks._read_observed(
            self._write(f"INCOMPLETE\nROOT\t{self.tmp}\n")
        )
        self.assertFalse(complete)

    def test_empty_file_yields_nothing_sweepable(self):
        observed, roots, complete = agent_marks._read_observed(self._write(""))
        self.assertEqual((observed, roots, complete), ({}, set(), True))

    def test_malformed_lines_are_ignored_not_fatal(self):
        observed, roots, _ = agent_marks._read_observed(
            self._write("GARBAGE\nROOT\n\nWINDOW\tonly-two\n")
        )
        self.assertEqual((observed, roots), ({}, set()))


if __name__ == "__main__":
    unittest.main(verbosity=1)
