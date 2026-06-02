"""Tests for the collapsible metadata sections + enlarged board detail dialog (t904).

The board's TaskDetailScreen accumulated many metadata fields (risk, cross-repo,
folded, contributor, lock, ...) that squeezed the markdown viewer. t904 (1) grows
#detail_dialog to 96% height and (2) wraps the secondary metadata fields in three
collapsed-by-default Textual Collapsible sections (#sec_relations, #sec_tracking,
#sec_lockfiles), keeping the editable core (#meta_editable) always visible.

These tests drive the real KanbanApp via Pilot and assert:
  * the secondary sections are present and collapsed on open,
  * the editable core stays a direct (visible) child of #detail_dialog,
  * the dialog height is 96%,
  * Enter on a section title expands it,
  * up/down field navigation is unaffected (regression guard alongside
    tests/test_board_detail_arrow_nav.py).

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_detail_collapsible.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))


class DetailCollapsibleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig_cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        from aitask_board import KanbanApp, TaskDetailScreen  # noqa: E402

        cls.KanbanApp = KanbanApp
        cls.TaskDetailScreen = TaskDetailScreen

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)

    def _run(self, coro):
        return asyncio.run(coro)

    def _first_parent_task(self, app):
        tasks = list(app.manager.task_datas.values())
        return tasks[0] if tasks else None

    def test_sections_present_and_collapsed(self):
        """Every .meta-section Collapsible is collapsed on open; the lock & files
        section always exists."""
        from textual.widgets import Collapsible

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                task = self._first_parent_task(app)
                if task is None:
                    self.skipTest("no parent tasks loaded on the board")

                app.push_screen(self.TaskDetailScreen(task, app.manager))
                await pilot.pause()

                sections = list(app.screen.query(".meta-section"))
                self.assertTrue(sections, "expected at least one collapsible meta-section")
                for sec in sections:
                    self.assertIsInstance(sec, Collapsible)
                    self.assertTrue(
                        sec.collapsed,
                        f"section {sec.id} should be collapsed on open",
                    )
                # Lock & files is always present (file refs + lock status).
                self.assertTrue(
                    app.screen.query("#sec_lockfiles"),
                    "lock & files section should always be present",
                )
        self._run(go())

    def test_core_stays_visible_outside_collapsibles(self):
        """The editable core (#meta_editable) is a direct child of #detail_dialog,
        not nested inside any Collapsible."""
        from textual.widgets import Collapsible

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                task = self._first_parent_task(app)
                if task is None:
                    self.skipTest("no parent tasks loaded on the board")

                app.push_screen(self.TaskDetailScreen(task, app.manager))
                await pilot.pause()

                meta = app.screen.query_one("#meta_editable")
                # No Collapsible ancestor between #meta_editable and the dialog.
                ancestor = meta.parent
                while ancestor is not None:
                    self.assertNotIsInstance(
                        ancestor, Collapsible,
                        "#meta_editable must not be nested inside a Collapsible",
                    )
                    if getattr(ancestor, "id", None) == "detail_dialog":
                        break
                    ancestor = ancestor.parent
                self.assertIsNotNone(ancestor, "#meta_editable should live under #detail_dialog")
        self._run(go())

    def test_dialog_height_is_96_percent(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                task = self._first_parent_task(app)
                if task is None:
                    self.skipTest("no parent tasks loaded on the board")

                app.push_screen(self.TaskDetailScreen(task, app.manager))
                await pilot.pause()
                dialog = app.screen.query_one("#detail_dialog")
                height = dialog.styles.height
                # A CSS `%` height is stored as Scalar(value, unit=HEIGHT).
                self.assertEqual(height.value, 96.0, f"unexpected dialog height: {height!r}")
                self.assertEqual(height.unit.name, "HEIGHT", f"height should be relative: {height!r}")
        self._run(go())

    def test_enter_expands_focused_section(self):
        """Focusing a section's CollapsibleTitle and pressing enter expands it."""
        from textual.widgets import Collapsible
        from textual.widgets._collapsible import CollapsibleTitle

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                task = self._first_parent_task(app)
                if task is None:
                    self.skipTest("no parent tasks loaded on the board")

                app.push_screen(self.TaskDetailScreen(task, app.manager))
                await pilot.pause()

                section = app.screen.query_one("#sec_lockfiles", Collapsible)
                self.assertTrue(section.collapsed)
                title = section.query_one(CollapsibleTitle)
                title.focus()
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                self.assertFalse(
                    section.collapsed,
                    "enter on the section title should expand it",
                )
                self.assertIsInstance(
                    app.screen, self.TaskDetailScreen,
                    "expanding a section must not dismiss the dialog",
                )
        self._run(go())

    def test_risk_section_present_readonly_and_first_when_set(self):
        """When risk is set, a read-only #sec_risk collapsible appears as the
        first meta-section (before #sec_relations); no editable risk CycleField."""
        from textual.widgets import Collapsible

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                task = self._first_parent_task(app)
                if task is None:
                    self.skipTest("no parent tasks loaded on the board")
                # Per-instance mutation: a fresh manager is loaded each test.
                task.metadata["risk_code_health"] = "high"
                task.metadata["risk_goal_achievement"] = "medium"

                app.push_screen(self.TaskDetailScreen(task, app.manager))
                await pilot.pause()

                risk_sec = app.screen.query_one("#sec_risk", Collapsible)
                self.assertTrue(risk_sec.collapsed)
                # Read-only fields, two of them; no editable risk CycleField.
                ro = list(risk_sec.query(".meta-ro"))
                self.assertEqual(len(ro), 2, "expected 2 read-only risk fields")
                self.assertFalse(
                    app.screen.query("#cf_risk_code_health"),
                    "risk must not be an editable CycleField anymore",
                )
                # Risk is the first meta-section (before Dependencies & hierarchy).
                sections = list(app.screen.query(".meta-section"))
                self.assertEqual(
                    sections[0].id, "sec_risk",
                    "risk section should come first, before relations",
                )
        self._run(go())

    def test_risk_section_absent_when_unset(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                task = self._first_parent_task(app)
                if task is None:
                    self.skipTest("no parent tasks loaded on the board")
                task.metadata.pop("risk_code_health", None)
                task.metadata.pop("risk_goal_achievement", None)

                app.push_screen(self.TaskDetailScreen(task, app.manager))
                await pilot.pause()
                self.assertFalse(
                    app.screen.query("#sec_risk"),
                    "no risk section when risk is unset",
                )
        self._run(go())

    def test_view_indicator_in_title_bar(self):
        """The view-mode indicator lives inside the title bar and starts as Task."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                task = self._first_parent_task(app)
                if task is None:
                    self.skipTest("no parent tasks loaded on the board")

                app.push_screen(self.TaskDetailScreen(task, app.manager))
                await pilot.pause()
                indicator = app.screen.query_one("#view_indicator")
                bar = app.screen.query_one("#detail_title_bar")
                self.assertIn(
                    indicator, list(bar.query("#view_indicator")),
                    "view indicator should be inside the title bar",
                )
                self.assertTrue(
                    indicator.has_class("viewing-task"),
                    "indicator should start in the Task state",
                )
        self._run(go())

    def test_updown_navigation_still_works(self):
        """Regression: down/up still advance/retreat focus among visible fields
        and section titles without dismissing the dialog."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                task = self._first_parent_task(app)
                if task is None:
                    self.skipTest("no parent tasks loaded on the board")

                app.push_screen(self.TaskDetailScreen(task, app.manager))
                await pilot.pause()
                first = app.focused
                await pilot.press("down")
                await pilot.pause()
                self.assertIsInstance(app.screen, self.TaskDetailScreen)
                self.assertIsNot(app.focused, first, "down should advance focus")
        self._run(go())


if __name__ == "__main__":
    unittest.main()
