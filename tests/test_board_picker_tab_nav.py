"""Regression test for cross-repo ref picker Tab navigation (t886).

The board binds `Tab` -> `focus_search` at the App level with `priority=True`
(`KanbanApp.BINDINGS`). Textual checks App priority bindings before the focused
widget, and they keep firing while a `ModalScreen` is on the stack — so inside
the `CrossRepoRefPickerScreen` popup, pressing Tab used to yank focus out to the
board's `#search_box` instead of cycling to the next `CrossRepoRefItem`. With
two or more refs, only the first (auto-focused) item was keyboard-reachable.

The fix gates `focus_search` in `KanbanApp.check_action` when a modal is on the
stack (`len(self.screen_stack) > 1`), mirroring the existing `nav_*` guard, so
Tab falls through to default widget focus-cycling inside the modal. Escape is
left untouched: `action_focus_board` is already modal-aware and dismisses.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_picker_tab_nav.py -v
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


class PickerTabNavTests(unittest.TestCase):
    """Drive the real KanbanApp via Pilot and assert Tab stays inside the
    cross-repo ref picker modal instead of escaping to the board search box."""

    @classmethod
    def setUpClass(cls):
        cls._orig_cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        # Import after chdir so module-level Path("aitasks") resolves correctly.
        from aitask_board import (  # noqa: E402
            KanbanApp,
            CrossRepoRefPickerScreen,
            CrossRepoRefItem,
        )
        from textual.widgets import Button, Input  # noqa: E402

        cls.KanbanApp = KanbanApp
        cls.CrossRepoRefPickerScreen = CrossRepoRefPickerScreen
        cls.CrossRepoRefItem = CrossRepoRefItem
        cls.Button = Button
        cls.Input = Input

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)

    def _run(self, coro):
        return asyncio.run(coro)

    def test_focus_search_gated_only_while_modal_on_stack(self):
        """check_action returns False for focus_search iff a modal is pushed."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()

                # Base board: Tab -> search must stay active.
                self.assertIsNot(
                    app.check_action("focus_search", None), False,
                    "focus_search must stay active on the base board so "
                    "Tab still focuses the search box",
                )

                # Push the picker; the gate must now disable focus_search.
                app.push_screen(
                    self.CrossRepoRefPickerScreen([("repoA", "1"), ("repoB", "2")])
                )
                await pilot.pause()
                self.assertIs(
                    app.check_action("focus_search", None), False,
                    "focus_search must be gated off while a modal is on the "
                    "stack so Tab falls through to the modal",
                )
        self._run(go())

    def test_tab_cycles_within_picker_not_to_search_box(self):
        """Tab inside the picker cycles its widgets; never lands on #search_box."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                search_box = app.query_one("#search_box", self.Input)

                app.push_screen(
                    self.CrossRepoRefPickerScreen([("repoA", "1"), ("repoB", "2")])
                )
                await pilot.pause()

                # Modal auto-focuses its first focusable widget (a ref item).
                self.assertIsInstance(
                    app.focused, self.CrossRepoRefItem,
                    "picker should auto-focus its first cross-repo ref item",
                )
                first = app.focused

                # Tab must move focus to another picker widget — never the
                # board search box — and the picker must stay on screen.
                await pilot.press("tab")
                await pilot.pause()
                self.assertIsInstance(
                    app.screen, self.CrossRepoRefPickerScreen,
                    "Tab must not dismiss or leave the picker",
                )
                self.assertIsNot(
                    app.focused, search_box,
                    "Tab must not yank focus out to the board search box",
                )
                self.assertIsInstance(
                    app.focused, (self.CrossRepoRefItem, self.Button),
                    "Tab should land on a picker ref item or the Cancel button",
                )
                self.assertIsNot(
                    app.focused, first,
                    "Tab should advance focus to a different picker widget",
                )
        self._run(go())


if __name__ == "__main__":
    unittest.main()
