"""Phantom-stub visibility probe for `followup_kind` (t1468_1).

`followup_kind` is deliberately kept OUT of `BOARD_KEYS` — three modules plus
the board itself read "metadata is a subset of BOARD_KEYS" as "this file
carries no real metadata" and drop it as a phantom stub. Adding the field
therefore *changes visibility*: a file that was invisible (only board keys)
becomes visible once it carries a kind.

That is the intended consequence, but it reaches four readers this task does
not otherwise touch, so it is pinned here rather than left incidental. Each
case drives the REAL reader, and each has a board-keys-only negative control
so the assertion cannot pass just because everything is visible.

Run: python3 -m unittest tests.test_followup_kind_phantom_stub -v
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(_REPO / ".aitask-scripts" / "board"))

import board_columns as bc  # noqa: E402
import trail_gather  # noqa: E402
from task_yaml import BOARD_KEYS  # noqa: E402

_BOARD_ONLY = "---\nboardcol: now\nboardidx: 50\nboardgroup: perf_work\n---\n\nbody\n"
_WITH_KIND = ("---\nboardcol: now\nboardidx: 50\nboardgroup: perf_work\n"
              "followup_kind: risk_mitigation\n---\n\nbody\n")


class FollowupKindIsNotABoardKey(unittest.TestCase):

    def test_followup_kind_is_absent_from_board_keys(self):
        """The structural fact the other three cases depend on."""
        self.assertNotIn("followup_kind", BOARD_KEYS)


class BoardColumnsEligibility(unittest.TestCase):
    """`board_columns._eligible` — the index-arithmetic reader."""

    def test_board_keys_only_is_a_phantom_stub(self):
        meta = {"boardcol": "now", "boardidx": 50, "boardgroup": "perf_work"}
        self.assertFalse(bc._eligible(meta),
                         "negative control: board keys alone must stay invisible")

    def test_followup_kind_makes_it_eligible(self):
        meta = {"boardcol": "now", "boardidx": 50, "boardgroup": "perf_work",
                "followup_kind": "risk_mitigation"}
        self.assertTrue(bc._eligible(meta),
                        "a task carrying a followup_kind is real metadata")


class TrailGatherRowLoading(unittest.TestCase):
    """`trail_gather._load_row` — the implementation-trail reader."""

    def _row(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t4242_probe.md"
            path.write_text(text, encoding="utf-8")
            return trail_gather._load_row(path, "local")

    def test_board_keys_only_is_dropped(self):
        self.assertIsNone(self._row(_BOARD_ONLY),
                          "negative control: board keys alone must be dropped")

    def test_followup_kind_survives(self):
        row = self._row(_WITH_KIND)
        self.assertIsNotNone(row, "a followup_kind must make the row visible")
        self.assertEqual(row.metadata.get("followup_kind"), "risk_mitigation")


class WorkReportScanning(unittest.TestCase):
    """`work_report_gather.scan_tasks` — the work-report reader.

    It reads the task directory from the process cwd, so each case runs in its
    own tree.
    """

    def _scan_ids(self, text):
        import work_report_gather
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            tasks = Path(tmp) / "aitasks"
            (tasks / "metadata").mkdir(parents=True)
            (tasks / "t4242_probe.md").write_text(text, encoding="utf-8")
            try:
                os.chdir(tmp)
                return [r.filename for r in work_report_gather.scan_tasks()]
            finally:
                os.chdir(cwd)

    def test_board_keys_only_is_skipped(self):
        self.assertEqual(self._scan_ids(_BOARD_ONLY), [],
                         "negative control: board keys alone must be skipped")

    def test_followup_kind_is_scanned(self):
        self.assertEqual(self._scan_ids(_WITH_KIND), ["t4242_probe.md"])


class BoardTaskManagerPredicate(unittest.TestCase):
    """`TaskManager._is_phantom_stub` — the original the other three mirror.

    Imported lazily: `aitask_board` pulls in Textual, and this is the only case
    that needs it.
    """

    def _is_phantom(self, meta):
        import aitask_board
        return aitask_board.TaskManager._is_phantom_stub(
            None, SimpleNamespace(metadata=meta))

    def test_board_keys_only_is_a_phantom_stub(self):
        self.assertTrue(self._is_phantom(
            {"boardcol": "now", "boardidx": 50, "boardgroup": "perf_work"}),
            "negative control: board keys alone must read as a phantom stub")

    def test_followup_kind_is_not_a_phantom_stub(self):
        self.assertFalse(self._is_phantom(
            {"boardcol": "now", "boardidx": 50, "boardgroup": "perf_work",
             "followup_kind": "risk_mitigation"}))


if __name__ == "__main__":
    unittest.main()
