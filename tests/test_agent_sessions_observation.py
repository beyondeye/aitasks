"""Observation-file protocol for the session store (t1705_2).

The observation file is a SHARED artifact: one producer writes it, and two
independent purges read it — `agent_marks.sweep_liveness` (which needs only
`ROOT` / `WINDOW`) and `agent_sessions.purge` (which additionally needs `PANE`).
That sharing is the whole reason the format is a superset rather than two files,
and it is what `tests/test_agent_marks_liveness.py`'s `PANE`-row test guards
from the other side.

The subtle rule here is `pane_complete`: a root whose windows were enumerated
but whose PANES were not is *partially* observed. `dead_window` is still safe to
apply to it (the window list is authoritative), but `dead_pane` is not — the
record's pane may be perfectly alive and simply unreported. Conflating the two
completeness levels would delete live agents' records whenever a producer wrote
only the marks-level rows, which is exactly what every pre-t1705 producer does.
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


class _ObsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, *lines) -> str:
        path = self.tmp / "obs.tsv"
        path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
        return str(path)


class ParseTests(_ObsTestCase):
    def test_the_four_row_kinds(self):
        obs = A.read_observation(self.write(
            f"ROOT\t{self.tmp}",
            f"WINDOW\t{self.tmp}\tagent-pick-1",
            f"PANE\t{self.tmp}\tagent-pick-1\t%1\t100\t0",
        ))
        root = os.path.realpath(self.tmp)
        self.assertEqual(obs.roots, {root})
        self.assertEqual(obs.windows, {root: {"agent-pick-1"}})
        self.assertEqual(obs.panes[(root, "agent-pick-1")], [("%1", 100, 0)])
        self.assertTrue(obs.complete)

    def test_incomplete_suppresses_everything(self):
        obs = A.read_observation(self.write("INCOMPLETE", f"ROOT\t{self.tmp}"))
        self.assertFalse(obs.complete)

    def test_blank_lines_are_ignored(self):
        obs = A.read_observation(self.write(f"ROOT\t{self.tmp}", "", ""))
        self.assertEqual(len(obs.roots), 1)

    def test_roots_are_canonicalized(self):
        real = self.tmp / "real"
        real.mkdir()
        link = self.tmp / "link"
        link.symlink_to(real)
        obs = A.read_observation(self.write(f"ROOT\t{link}"))
        self.assertEqual(obs.roots, {os.path.realpath(str(real))})

    def test_unknown_row_kind_is_corruption(self):
        """Unlike the marks reader, this one is strict: it needs every row."""
        with self.assertRaises(A.MalformedSessionsError):
            A.read_observation(self.write("PLANE\t/x"))

    def test_non_numeric_pane_fields_are_corruption(self):
        with self.assertRaises(A.MalformedSessionsError):
            A.read_observation(self.write(f"PANE\t{self.tmp}\tw\t%1\tnotapid\t0"))

    def test_multiple_panes_per_window(self):
        obs = A.read_observation(self.write(
            f"ROOT\t{self.tmp}",
            f"WINDOW\t{self.tmp}\tw",
            f"PANE\t{self.tmp}\tw\t%1\t100\t0",
            f"PANE\t{self.tmp}\tw\t%2\t200\t1",
        ))
        rows = obs.panes[(os.path.realpath(self.tmp), "w")]
        self.assertEqual(sorted(rows), [("%1", 100, 0), ("%2", 200, 1)])


class PaneCompletenessTests(_ObsTestCase):
    def test_a_window_with_pane_rows_is_pane_complete(self):
        obs = A.read_observation(self.write(
            f"ROOT\t{self.tmp}",
            f"WINDOW\t{self.tmp}\tw",
            f"PANE\t{self.tmp}\tw\t%1\t100\t0",
        ))
        self.assertTrue(obs.pane_complete[os.path.realpath(self.tmp)])

    def test_a_window_without_pane_rows_is_pane_incomplete(self):
        """A marks-era producer writes exactly this shape."""
        obs = A.read_observation(self.write(
            f"ROOT\t{self.tmp}", f"WINDOW\t{self.tmp}\tw"
        ))
        self.assertFalse(obs.pane_complete[os.path.realpath(self.tmp)])

    def test_one_missing_window_makes_the_whole_root_pane_incomplete(self):
        obs = A.read_observation(self.write(
            f"ROOT\t{self.tmp}",
            f"WINDOW\t{self.tmp}\tseen",
            f"WINDOW\t{self.tmp}\tunseen",
            f"PANE\t{self.tmp}\tseen\t%1\t100\t0",
        ))
        self.assertFalse(obs.pane_complete[os.path.realpath(self.tmp)])

    def test_a_zero_window_root_is_pane_complete(self):
        """An enumerated session with no agents left: its records are dead."""
        obs = A.read_observation(self.write(f"ROOT\t{self.tmp}"))
        self.assertTrue(obs.pane_complete[os.path.realpath(self.tmp)])


class MarksReaderCompatibilityTests(_ObsTestCase):
    """The other half of the shared-file contract (t1705_2 A1).

    `agent_marks._read_observed` must take its own subset of the SAME file and
    ignore `PANE` rows. Asserted from both sides on purpose: this module owns
    "the superset parses", `test_agent_marks_liveness.py` owns "the subset
    reader is unaffected by the extra rows".
    """

    def test_marks_reader_ignores_pane_rows_in_a_shared_file(self):
        sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
        import agent_marks

        path = self.write(
            f"ROOT\t{self.tmp}",
            f"WINDOW\t{self.tmp}\tagent-pick-1",
            f"PANE\t{self.tmp}\tagent-pick-1\t%1\t100\t0",
        )
        observed, roots, complete = agent_marks._read_observed(path)
        root = os.path.realpath(self.tmp)
        self.assertEqual(roots, {root})
        self.assertEqual(observed, {root: {"agent-pick-1"}})
        self.assertTrue(complete)

    def test_both_readers_agree_on_the_same_file(self):
        import agent_marks

        path = self.write(
            "INCOMPLETE",
            f"ROOT\t{self.tmp}",
            f"WINDOW\t{self.tmp}\tw",
            f"PANE\t{self.tmp}\tw\t%1\t100\t0",
        )
        _, _, marks_complete = agent_marks._read_observed(path)
        sessions = A.read_observation(path)
        self.assertFalse(marks_complete)
        self.assertFalse(sessions.complete)


if __name__ == "__main__":
    unittest.main(verbosity=2)
