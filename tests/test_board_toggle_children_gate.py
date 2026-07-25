"""Regression tests for the `toggle_children` dispatch gate (t1245).

`KanbanApp.check_action` hides `toggle_children` in the derived views
(In-Flight / By-Topic / By-Trail), which render every relevant card — children
included — directly. Before t1245 the `TaskCard` double-click shortcut called
`action_toggle_children()` straight through, so the mouse path still mutated
`expanded_tasks` in views where the action is deliberately unavailable.

These tests pin both halves of the fix:
- the mouse path consults the gate and falls through to the detail modal, and
- `action_toggle_children` itself refuses to run when the gate says no (so any
  other dispatch surface is covered too).

`test_all_view_double_click_still_expands` is the positive control: it proves
the double-click machinery actually reaches the card, so the "unchanged"
assertions above are not vacuous.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_toggle_children_gate.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))


class BoardToggleChildrenGateTests(unittest.TestCase):
    """Drives the real KanbanApp via Pilot against the live `aitasks/` repo."""

    @classmethod
    def setUpClass(cls):
        cls._orig_cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        from aitask_board import KanbanApp, TaskCard  # noqa: E402
        cls.KanbanApp = KanbanApp
        cls.TaskCard = TaskCard

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)

    def _run(self, coro):
        return asyncio.run(coro)

    async def _enter_bytopic(self, app, pilot):
        """Press 'y' and let the board re-render settle (see
        tests/test_board_topic_view.py — bytopic builds from in-memory tasks)."""
        await pilot.press("y")
        await pilot.pause()
        await pilot.pause()

    @staticmethod
    def _is_clickable(app, card) -> bool:
        """True when the card is fully on screen, so Pilot's synthesized click
        lands on it rather than on whatever occupies those coordinates."""
        region = card.region
        return region.area > 0 and app.screen.region.contains_region(region)

    def _clickable_parent_cards(self, app) -> list:
        """Visible, fully on-screen, non-child cards in DOM order."""
        return [c for c in app.query(self.TaskCard)
                if not c.is_child
                and c.styles.display != "none"
                and self._is_clickable(app, c)]

    def test_bytopic_double_click_does_not_expand(self):
        """By-Topic hides `toggle_children`; a double-click must honor that gate
        and open details instead of mutating `expanded_tasks`."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(220, 60)) as pilot:
                await pilot.pause()
                self.assertGreater(len(list(app.query(self.TaskCard))), 0,
                                   "test repo must contain at least one task")
                await self._enter_bytopic(app, pilot)
                self.assertEqual(app.base_filter, "bytopic")

                cards = self._clickable_parent_cards(app)
                if not cards:
                    self.skipTest("no clickable parent card in the bytopic view")
                card = cards[0]

                # Make the card look like a collapsed parent *with* children —
                # the exact shape that triggered the bypass — independently of
                # what the live repo happens to contain.
                app.expanded_tasks.discard(card.task_data.filename)
                before = set(app.expanded_tasks)
                app.action_view_details = Mock()
                with patch.object(app.manager, "get_child_tasks_for_parent",
                                  return_value=[object()]):
                    await pilot.click(card, times=2)
                    await pilot.pause()

                self.assertEqual(
                    app.action_view_details.call_count, 1,
                    "the double-click must reach the card and fall through to "
                    "the detail modal")
                self.assertEqual(
                    set(app.expanded_tasks), before,
                    "double-click in bytopic must not mutate expanded_tasks — "
                    "check_action hides toggle_children there")
        self._run(go())

    def test_all_view_double_click_still_expands(self):
        """Positive control: where the gate allows it, double-click expands."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(220, 60)) as pilot:
                await pilot.pause()
                self.assertEqual(app.base_filter, "all")

                card = None
                for candidate in self._clickable_parent_cards(app):
                    task_num, _ = self.TaskCard._parse_filename(
                        candidate.task_data.filename)
                    if not task_num:
                        continue
                    if not app.manager.get_child_tasks_for_parent(task_num):
                        continue
                    if candidate.task_data.filename in app.expanded_tasks:
                        continue
                    card = candidate
                    break
                if card is None:
                    self.skipTest("no clickable collapsed parent with children")

                filename = card.task_data.filename
                await pilot.click(card, times=2)
                await pilot.pause()

                self.assertIn(
                    filename, app.expanded_tasks,
                    "double-click on a collapsed parent must still expand it "
                    "in the normal kanban views")
        self._run(go())

    def test_action_toggle_children_is_noop_in_derived_view(self):
        """The action itself re-asserts the gate, so non-mouse dispatch
        surfaces (bindings, programmatic calls) cannot bypass it either."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(220, 60)) as pilot:
                await pilot.pause()
                await self._enter_bytopic(app, pilot)
                self.assertEqual(app.base_filter, "bytopic")

                cards = [c for c in app.query(self.TaskCard) if not c.is_child]
                if not cards:
                    self.skipTest("no parent card in the bytopic view")
                card = cards[0]
                card.focus()
                await pilot.pause()
                self.assertIs(app._focused_card(), card,
                              "the card must be focused for the action to have "
                              "a target to expand")

                app.expanded_tasks.discard(card.task_data.filename)
                before = set(app.expanded_tasks)
                with patch.object(app.manager, "get_child_tasks_for_parent",
                                  return_value=[object()]):
                    app.action_toggle_children()
                    await pilot.pause()

                self.assertEqual(
                    set(app.expanded_tasks), before,
                    "action_toggle_children must be a no-op while the gate "
                    "hides it")
        self._run(go())


if __name__ == "__main__":
    unittest.main()
