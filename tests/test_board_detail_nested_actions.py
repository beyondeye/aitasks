"""Regression test: board task-detail actions must fire when the detail is
opened from a *nested* navigation (a dependency / parent / child / picker), not
just from the board itself (t1062).

Root cause that this guards against: ``TaskDetailScreen`` performs no action
itself — every action (pick, edit, rename, …) is signalled to the caller via
``self.dismiss(<result>)``. Historically only the top-level board push wired a
result callback; every nested open pushed ``TaskDetailScreen`` with **no
callback**, so pressing e.g. ``p`` (pick) on a dependency detail silently
dropped the result and popped back to the parent detail. The fix routes every
open through ``KanbanApp.open_task_detail``, which always wires the callback.

The reported repro was: open task 968 detail → open its dependency 929_3 (via
the multi-dependency picker) → press ``p`` → nothing happens. Case 2 below
reproduces that exact picker path.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_detail_nested_actions.py -v
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

BOARD_SRC = REPO_ROOT / ".aitask-scripts" / "board" / "aitask_board.py"


class NestedDetailActionTests(unittest.TestCase):
    """Drive the real KanbanApp via Pilot and assert that the pick action,
    triggered from a nested detail screen, routes to the *nested* task — and
    that the multi-level Esc-pop screen history still works."""

    @classmethod
    def setUpClass(cls):
        cls._orig_cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        # Import after chdir so module-level Path("aitasks") resolves correctly.
        from aitask_board import (  # noqa: E402
            KanbanApp, TaskDetailScreen, AgentCommandScreen,
            DependencyPickerScreen, DepPickerItem, TaskCard,
        )
        cls.KanbanApp = KanbanApp
        cls.TaskDetailScreen = TaskDetailScreen
        cls.AgentCommandScreen = AgentCommandScreen
        cls.DependencyPickerScreen = DependencyPickerScreen
        cls.DepPickerItem = DepPickerItem
        cls.TaskCard = TaskCard

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)

    def _run(self, coro):
        return asyncio.run(coro)

    def _parents(self, app):
        return list(app.manager.task_datas.values())

    def _num(self, task):
        task_num, _ = self.TaskCard._parse_filename(task.filename)
        return task_num.lstrip("t")

    async def _assert_pick_routes_to(self, app, pilot, task):
        """Press ``p`` on the currently-open detail and assert the pick action
        is initiated for ``task`` (an AgentCommandScreen for its id is pushed)."""
        # Deterministic stub so the pick branch builds the AgentCommandScreen
        # rather than depending on a configured pick command.
        app._resolve_pick_command = lambda task_num: "true"
        # Neutralise the pick-button enabled gate so "p" exercises the real
        # action_pick -> pick_task -> dismiss("pick") path deterministically.
        app.screen.query_one("#btn_pick").disabled = False
        await pilot.pause()
        await pilot.press("p")
        await pilot.pause()
        self.assertIsInstance(
            app.screen, self.AgentCommandScreen,
            "pick on a nested detail must initiate the pick (push AgentCommandScreen), "
            "not silently pop back to the parent detail",
        )
        self.assertEqual(
            app.screen.operation_args, [self._num(task)],
            "pick must target the nested task, not the parent detail's task",
        )

    def test_pick_routes_through_open_task_detail_helper(self):
        """The wired helper: open a detail via open_task_detail and pick it."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                parents = self._parents(app)
                if len(parents) < 1:
                    self.skipTest("no parent tasks loaded on the board")
                taskB = parents[0]
                app.open_task_detail(taskB)
                await pilot.pause()
                self.assertIsInstance(app.screen, self.TaskDetailScreen)
                self.assertIs(app.screen.task_data, taskB)
                await self._assert_pick_routes_to(app, pilot, taskB)
        self._run(go())

    def test_pick_through_multi_dependency_picker(self):
        """The reported repro path: open the dependency picker, select a
        dependency, then pick it — the pick must target that dependency."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                parents = self._parents(app)
                if len(parents) < 2:
                    self.skipTest("need >= 2 parent tasks to model a dependency")
                taskA, taskB = parents[0], parents[1]
                items = [(self._num(taskB), taskB, f"{self._num(taskB)} B")]
                if len(parents) >= 3:
                    taskC = parents[2]
                    items.append((self._num(taskC), taskC, f"{self._num(taskC)} C"))
                app.push_screen(
                    self.DependencyPickerScreen(items, app.manager, taskA))
                await pilot.pause()
                target = next(it for it in app.screen.query(self.DepPickerItem)
                              if it.dep_task is taskB)
                target.focus()
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                # Picker dismissed; the dependency detail is now open AND wired.
                self.assertIsInstance(app.screen, self.TaskDetailScreen)
                self.assertIs(app.screen.task_data, taskB)
                await self._assert_pick_routes_to(app, pilot, taskB)
        self._run(go())

    def test_escape_pops_one_detail_at_a_time(self):
        """Wiring a result callback must not break multi-level push/pop: open A,
        open B on top, Esc reveals A (not the board), Esc again returns to the
        board."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                parents = self._parents(app)
                if len(parents) < 2:
                    self.skipTest("need >= 2 parent tasks for a nested stack")
                taskA, taskB = parents[0], parents[1]
                app.open_task_detail(taskA)
                await pilot.pause()
                app.open_task_detail(taskB)
                await pilot.pause()
                self.assertIs(app.screen.task_data, taskB)

                await pilot.press("escape")
                await pilot.pause()
                self.assertIsInstance(
                    app.screen, self.TaskDetailScreen,
                    "first Esc must reveal the parent detail, not the board",
                )
                self.assertIs(
                    app.screen.task_data, taskA,
                    "first Esc must pop exactly one detail (B), revealing A",
                )

                await pilot.press("escape")
                await pilot.pause()
                self.assertNotIsInstance(
                    app.screen, self.TaskDetailScreen,
                    "second Esc must return to the board",
                )
        self._run(go())

    def test_single_taskdetailscreen_push_site(self):
        """Structural invariant: the find-all conversion left exactly one
        TaskDetailScreen instantiation, and it lives inside open_task_detail.
        Fails loudly if any nested open site is missed or a new callback-less
        push is added later."""
        src = BOARD_SRC.read_text()
        # Two references total: the `class TaskDetailScreen(...)` definition and
        # the single push instantiation inside open_task_detail.
        refs = list(re.finditer(r"\bTaskDetailScreen\(", src))
        self.assertEqual(
            len(refs), 2,
            "expected exactly one TaskDetailScreen instantiation (in "
            "open_task_detail) plus the class definition; a different count "
            "means a nested open site was missed or a duplicate push was added",
        )
        helper = src.index("def open_task_detail(")
        next_method = src.index("\n    def ", helper + 1)
        inst = src.index("TaskDetailScreen(task, self.manager", helper)
        self.assertTrue(
            helper < inst < next_method,
            "the sole TaskDetailScreen push must live inside open_task_detail",
        )


if __name__ == "__main__":
    unittest.main()
