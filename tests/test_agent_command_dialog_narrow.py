"""Tests for AgentCommandScreen narrow mode (t1012).

The minimonitor companion pane is ~40 cols wide. Pressing `n` (pick next
sibling) eventually pushes AgentCommandScreen ("Pick Task t<N>"), which in its
default 80%-wide layout overflowed the pane (truncated buttons, clipped command
text, cut-off Select boxes). `narrow=True` widens the dialog and stacks the
horizontal rows vertically so every control fits.

Mirrors tests/test_kill_confirm_dialog.py::test_buttons_fit_inside_narrow_dialog
— drive the screen with a small terminal and assert every control's region sits
within the dialog's region.

Run: python3 -m pytest tests/test_agent_command_dialog_narrow.py -v
  or: bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Button, Input, Label, Select  # noqa: E402

from agent_command_screen import AgentCommandScreen  # noqa: E402


class _DialogHost(App):
    def __init__(self, narrow: bool) -> None:
        super().__init__()
        self._narrow = narrow

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(
            AgentCommandScreen(
                title="Pick Task t5_5",
                full_command="claude --model claude-opus-4-8 '/aitask-pick 5_5'",
                prompt_str="/aitask-pick 5_5",
                default_window_name="agent-pick-5_5",
                project_root=REPO_ROOT,
                operation="pick",
                operation_args=["5_5"],
                default_agent_string="claudecode/opus4_8",
                skill_name="pick",
                default_profile="fast",
                narrow=self._narrow,
            )
        )


class AgentCommandDialogNarrowTests(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_narrow_class_applied(self):
        async def runner():
            app = _DialogHost(narrow=True)
            async with app.run_test(size=(40, 50)) as pilot:
                await pilot.pause()
                await pilot.pause()
                # The `narrow` class is added to the screen itself (the CSS
                # selector is `AgentCommandScreen.narrow #agent_cmd_dialog`).
                self.assertIsInstance(app.screen, AgentCommandScreen)
                self.assertIn("narrow", app.screen.classes)

        self._run(runner())

    def test_default_is_not_narrow(self):
        async def runner():
            app = _DialogHost(narrow=False)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                self.assertIsInstance(app.screen, AgentCommandScreen)
                self.assertNotIn("narrow", app.screen.classes)

        self._run(runner())

    def test_controls_fit_inside_narrow_dialog(self):
        """Every button/input/select renders fully within the dialog at 40 cols."""
        async def runner():
            app = _DialogHost(narrow=True)
            async with app.run_test(size=(40, 50)) as pilot:
                await pilot.pause()
                await pilot.pause()

                dialog = app.screen.query_one("#agent_cmd_dialog")
                dialog_left = dialog.region.x
                dialog_right = dialog.region.x + dialog.region.width

                controls = [
                    w
                    for w in app.screen.query("Button, Input, Select")
                    if isinstance(w, (Button, Input, Select))
                ]
                # The dialog always has at least the command Input and the
                # Direct-tab buttons; guard against a query that silently
                # returns nothing.
                self.assertGreater(len(controls), 0)
                for widget in controls:
                    # Skip widgets that are not currently displayed (e.g. the
                    # inactive tab's content or hidden new-session rows).
                    if widget.region.width == 0 and widget.region.height == 0:
                        continue
                    left = widget.region.x
                    right = widget.region.x + widget.region.width
                    self.assertGreaterEqual(
                        left, dialog_left,
                        f"{widget!r} left {left} < dialog left {dialog_left}",
                    )
                    self.assertLessEqual(
                        right, dialog_right,
                        f"{widget!r} right {right} > dialog right {dialog_right}",
                    )

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
