"""Regression tests for board footer hiding semantics (t1112).

Textual 8.2.7 keeps bindings in ``screen.active_bindings`` when
``check_action`` returns ``None``; they render greyed in the footer. Returning
``False`` removes them from ``active_bindings`` entirely. These tests assert the
footer surface, not just that the actions are blocked.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402


class BoardFooterVisibilityTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """Assert inapplicable board actions are absent from the footer.

    Boots against a fixture tree (t1354_2); `cls.ab` / `cls.tree` come from the
    harness. Helper audit: the only external reach at boot is the board's own
    `aitask_lock.sh --list`, which is absent under the fixture cwd and degrades
    to an empty `lock_map` — this module never asserts on lock state, and the
    focused card is a `SimpleNamespace` stub, so nothing here can pass via a
    missing-helper fallback.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KanbanApp = cls.ab.KanbanApp
        cls.TaskCard = cls.ab.TaskCard

    def _run(self, coro):
        return asyncio.run(coro)

    def test_fixture_facts(self):
        """Preconditions this module's assertions depend on (t1354_2 Step 2a).

        Fails loudly if the fixture is reshaped out from under the tests rather
        than letting them pass vacuously.
        """
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                self.assertTrue(
                    list(app.query(self.TaskCard)),
                    "fixture must render at least one task card")
                # The old live-tree `skipTest` guard is now this precondition.
                self.assertIsNotNone(
                    self._find_task_without_children_or_cross_repo_refs(app),
                    "fixture must contain a parent task with no children and "
                    "no cross-repo refs — the footer assertions target it")
        self._run(go())

    @staticmethod
    def _footer_actions(app) -> set[str]:
        return {
            active.binding.action
            for active in app.screen.active_bindings.values()
        }

    def _find_task_without_children_or_cross_repo_refs(self, app):
        """The first eligible task, or None. Pure lookup — no skip."""
        for task in app.manager.task_datas.values():
            task_num, _ = self.TaskCard._parse_filename(task.filename)
            if not task_num:
                continue
            if app.manager.get_child_tasks_for_parent(task_num):
                continue
            if app._gather_cross_repo_refs(task):
                continue
            return task
        return None

    def _task_without_children_or_cross_repo_refs(self, app):
        """Same lookup, asserted. On the live tree this used to `skipTest`; the
        fixture guarantees the shape, so an absence is now a real failure."""
        task = self._find_task_without_children_or_cross_repo_refs(app)
        self.assertIsNotNone(
            task, "fixture must contain a parent task with no children and no "
                  "cross-repo refs")
        return task

    def test_focused_inapplicable_actions_are_absent_from_footer(self):
        """Focused states exercise each action-specific inapplicable branch."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                task = self._task_without_children_or_cross_repo_refs(app)
                app.manager.modified_files.clear()
                app._focused_card = lambda: SimpleNamespace(
                    task_data=task,
                    is_child=False,
                    column_id="now",
                )

                for action in (
                    "commit_selected",
                    "open_cross_repo",
                    "toggle_children",
                ):
                    self.assertIs(app.check_action(action, None), False)

                actions = self._footer_actions(app)
                self.assertNotIn("commit_selected", actions)
                self.assertNotIn("open_cross_repo", actions)
                self.assertNotIn("toggle_children", actions)

        self._run(go())

    def test_no_focus_or_no_modified_tasks_are_absent_from_footer(self):
        """Global/no-focus inapplicable states are hidden, not disabled."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                app.manager.modified_files.clear()
                app._focused_card = lambda: None

                for action in (
                    "commit_all",
                    "pick_task",
                    "brainstorm_task",
                ):
                    self.assertIs(app.check_action(action, None), False)

                actions = self._footer_actions(app)
                self.assertNotIn("commit_all", actions)
                self.assertNotIn("pick_task", actions)
                self.assertNotIn("brainstorm_task", actions)

        self._run(go())


if __name__ == "__main__":
    unittest.main()
