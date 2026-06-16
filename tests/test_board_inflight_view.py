"""Tests for the board In-Flight action view (t635_9)."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))


def _manager():
    from aitask_board import TaskManager

    mgr = TaskManager.__new__(TaskManager)
    mgr.task_datas = {}
    mgr.child_task_datas = {}
    mgr.archived_task_cache = {}
    mgr.columns = []
    mgr.column_order = []
    mgr.modified_files = set()
    mgr.lock_map = {}
    mgr.xdep_status_cache = {}
    mgr.gate_state_cache = {}
    mgr.gate_registry_cache = None
    mgr.gate_registry_error = ""
    mgr.settings = {}
    return mgr


def _task(tmp: Path, name: str, body: str):
    from aitask_board import Task

    path = tmp / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return Task.from_text(path, body)


def _body(status: str, extra_fm: str = "", ledger: str = "") -> str:
    return f"""---
priority: high
effort: low
status: {status}
{extra_fm}---

Body.
{ledger}
"""


LEDGER_PENDING_HUMAN = """
## Gate Runs

> **⏸ gate:review_approved** run=2026-01-01T00:00:00Z status=pending type=human
"""

LEDGER_REVIEW_PASS = """
## Gate Runs

> **✅ gate:review_approved** run=2026-01-01T00:00:00Z status=pass attempt=1 type=human
"""


class InFlightModelTests(unittest.TestCase):
    def test_implementing_without_ledger_is_included(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _manager()
            task = _task(Path(td), "t1_plain.md", _body("Implementing"))
            mgr.task_datas[task.filename] = task

            items = mgr.get_inflight_items()
            self.assertEqual([i.task_id for i in items], ["t1"])
            self.assertEqual(items[0].group, "agent")
            self.assertIn("no gate ledger", items[0].next_action)

    def test_ready_with_ledger_is_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _manager()
            task = _task(
                Path(td),
                "t2_ready.md",
                _body("Ready", "gates: [review_approved]\n", LEDGER_REVIEW_PASS),
            )
            mgr.task_datas[task.filename] = task

            self.assertEqual(mgr.get_inflight_items(), [])

    def test_pending_human_gate_needs_action(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _manager()
            task = _task(
                Path(td),
                "t3_review.md",
                _body("Implementing", "gates: [review_approved]\n", LEDGER_PENDING_HUMAN),
            )
            mgr.task_datas[task.filename] = task

            item = mgr.get_inflight_items()[0]
            self.assertEqual(item.group, "human")
            self.assertEqual(item.human_gates, ["review_approved"])

    def test_gate_satisfied_dependency_does_not_block(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _manager()
            upstream = _task(
                Path(td),
                "t10_upstream.md",
                _body("Implementing", "gates: [review_approved]\n", LEDGER_REVIEW_PASS),
            )
            dependent = _task(
                Path(td),
                "t11_dependent.md",
                _body("Ready", "depends: [10]\n"),
            )
            mgr.task_datas[upstream.filename] = upstream
            mgr.task_datas[dependent.filename] = dependent

            self.assertEqual(mgr.unresolved_local_deps(dependent), [])

    def test_gate_parse_failure_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _manager()
            task = _task(Path(td), "t12_missing.md", _body("Implementing"))
            task.filepath = Path(td) / "does_not_exist.md"
            mgr.task_datas[task.filename] = task

            item = mgr.get_inflight_items()[0]
            self.assertEqual(item.group, "agent")
            self.assertIn("unavailable", item.next_action)
            self.assertTrue(item.state_error)


class InFlightPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig_cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        from aitask_board import InFlightColumn, KanbanApp, KanbanColumn

        cls.InFlightColumn = InFlightColumn
        cls.KanbanApp = KanbanApp
        cls.KanbanColumn = KanbanColumn

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)

    def _run(self, coro):
        return asyncio.run(coro)

    def test_i_switches_to_inflight_columns_and_a_returns(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await pilot.press("i")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app.base_filter, "inflight")
                self.assertTrue(list(app.query(self.InFlightColumn)))
                self.assertFalse(list(app.query(self.KanbanColumn)))

                await pilot.press("a")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app.base_filter, "all")
                self.assertTrue(list(app.query(self.KanbanColumn)))
        self._run(go())

    def test_existing_agent_window_guard_reuses_window(self):
        app = self.KanbanApp()
        with patch("aitask_board._current_tmux_session", return_value="aitasks"), \
                patch("aitask_board.find_window_by_name", return_value=("aitasks", "2")), \
                patch("aitask_board.subprocess.Popen") as popen:
            self.assertTrue(app._focus_existing_agent_window("42"))
            popen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
