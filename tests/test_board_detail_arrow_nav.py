"""Regression test for up/down field navigation in the board detail dialog (t893).

The board binds `up`/`down`/`left`/`right` at the App level with `priority=True`
(`KanbanApp.BINDINGS`). Those nav actions are modal-aware: while a modal is on the
stack, `action_nav_up`/`action_nav_down` call `screen.focus_previous()` /
`focus_next()`, which is how `TaskDetailScreen` moves focus between its metadata
fields, and how the focusable-`Static` pickers move between items.

t848_4 (in-TUI shortcut editor) added a blanket guard in `KanbanApp.check_action`
disabling all four nav actions whenever any screen was pushed, so the shortcut
editor's `DataTable` could own up/down for row navigation. That was too broad: the
detail dialog's fields only self-handle left/right (`CycleField.on_key`), so up/down
fell through to widgets that ignore them and field navigation died.

The fix (t893) keeps left/right falling through (CycleField cycling, Input cursor)
but narrows the up/down fall-through to modals whose focused widget owns vertical
navigation — currently only the shortcut editor's `DataTable`. Every other modal
keeps driving the App's `action_nav_up`/`action_nav_down`.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_detail_arrow_nav.py -v
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


class DetailArrowNavTests(unittest.TestCase):
    """Drive the real KanbanApp via Pilot and assert up/down still drive
    App-level field navigation inside TaskDetailScreen, while the shortcut
    editor's DataTable keeps owning up/down."""

    @classmethod
    def setUpClass(cls):
        cls._orig_cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        # Import after chdir so module-level Path("aitasks") resolves correctly.
        from aitask_board import KanbanApp, TaskDetailScreen  # noqa: E402

        cls.KanbanApp = KanbanApp
        cls.TaskDetailScreen = TaskDetailScreen

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)

    def _run(self, coro):
        return asyncio.run(coro)

    def _first_parent_task(self, app):
        """Return any loaded parent task, or None if the board has none."""
        tasks = list(app.manager.task_datas.values())
        return tasks[0] if tasks else None

    def test_updown_active_for_detail_dialog(self):
        """check_action keeps nav_up/nav_down active for TaskDetailScreen so the
        App's focus_previous/next field navigation fires; left/right stay gated."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                task = self._first_parent_task(app)
                if task is None:
                    self.skipTest("no parent tasks loaded on the board")

                app.push_screen(self.TaskDetailScreen(task, app.manager))
                await pilot.pause()
                self.assertIsInstance(
                    app.screen, self.TaskDetailScreen,
                    "detail dialog should be on the stack",
                )

                # Up/down must NOT be gated off — the detail fields rely on the
                # App's modal-aware action_nav_up/down (focus_previous/next).
                self.assertIsNot(
                    app.check_action("nav_up", None), False,
                    "nav_up must stay active for TaskDetailScreen field navigation",
                )
                self.assertIsNot(
                    app.check_action("nav_down", None), False,
                    "nav_down must stay active for TaskDetailScreen field navigation",
                )

                # Left/right stay gated so CycleField.on_key keeps cycling them.
                self.assertIs(
                    app.check_action("nav_left", None), False,
                    "nav_left must fall through to the focused field widget",
                )
                self.assertIs(
                    app.check_action("nav_right", None), False,
                    "nav_right must fall through to the focused field widget",
                )
        self._run(go())

    def test_down_moves_focus_between_detail_fields(self):
        """Pressing down/up actually advances/retreats focus inside the dialog
        without dismissing it."""
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
                self.assertIsInstance(
                    app.screen, self.TaskDetailScreen,
                    "down must not dismiss or leave the detail dialog",
                )
                second = app.focused
                self.assertIsNot(
                    second, first,
                    "down should advance focus to a different field widget",
                )

                await pilot.press("up")
                await pilot.pause()
                self.assertIsInstance(
                    app.screen, self.TaskDetailScreen,
                    "up must not dismiss or leave the detail dialog",
                )
                self.assertIsNot(
                    app.focused, second,
                    "up should move focus off the second field",
                )
        self._run(go())

    def test_updown_gated_for_shortcut_editor_datatable(self):
        """The shortcut editor's DataTable still owns up/down (row navigation)."""
        async def go():
            from shortcut_editor_modal import ShortcutEditorModal
            from textual.widgets import DataTable

            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                app.push_screen(ShortcutEditorModal("board"))
                await pilot.pause()
                table = app.screen.query_one("#se_table", DataTable)
                table.focus()
                await pilot.pause()
                self.assertIsInstance(
                    app.focused, DataTable,
                    "shortcut editor should focus its DataTable",
                )
                self.assertIs(
                    app.check_action("nav_up", None), False,
                    "nav_up must fall through to the DataTable for row navigation",
                )
                self.assertIs(
                    app.check_action("nav_down", None), False,
                    "nav_down must fall through to the DataTable for row navigation",
                )
        self._run(go())


if __name__ == "__main__":
    unittest.main()
