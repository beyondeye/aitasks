"""Tests for the shared monitor kill confirmation dialog."""

from __future__ import annotations

import asyncio
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Button, Label  # noqa: E402

from monitor.monitor_core import PaneCategory, PaneSnapshot, TmuxPaneInfo  # noqa: E402
from monitor.monitor_shared import KillConfirmDialog, TaskInfo  # noqa: E402


class _KillDialogHost(App):
    def __init__(self, show_preview: bool) -> None:
        super().__init__()
        self._show_preview = show_preview

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(
            KillConfirmDialog(
                _snapshot(),
                _task_info(),
                show_preview=self._show_preview,
            )
        )


def _snapshot() -> PaneSnapshot:
    pane = TmuxPaneInfo(
        window_index="1",
        window_name="agent-t995-codex",
        pane_index="0",
        pane_id="%42",
        pane_pid=4242,
        current_command="bash",
        width=80,
        height=24,
        category=PaneCategory.AGENT,
        session_name="aitasks",
    )
    return PaneSnapshot(
        pane=pane,
        content="\n".join(f"line {idx}" for idx in range(20)),
        timestamp=time.monotonic(),
        idle_seconds=0,
        is_idle=False,
    )


def _task_info() -> TaskInfo:
    return TaskInfo(
        task_id="995",
        task_file="aitasks/t995_minimonitor_kill_confirm_dialog_trim.md",
        title="Trim minimonitor kill confirmation dialog",
        priority="medium",
        effort="low",
        issue_type="enhancement",
        status="Implementing",
        body="",
        plan_content=None,
    )


class KillConfirmDialogTests(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_preview_is_shown_by_default(self):
        async def runner():
            app = _KillDialogHost(show_preview=True)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.pause()

                self.assertEqual(
                    len(list(app.screen.query("#kill-preview-label"))),
                    1,
                )
                self.assertEqual(len(list(app.screen.query("#kill-preview"))), 1)

        self._run(runner())

    def test_preview_can_be_hidden_for_minimonitor(self):
        async def runner():
            app = _KillDialogHost(show_preview=False)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.pause()

                self.assertEqual(
                    len(list(app.screen.query("#kill-preview-label"))),
                    0,
                )
                self.assertEqual(len(list(app.screen.query("#kill-preview"))), 0)
                self.assertEqual(len(list(app.screen.query("#btn-kill"))), 1)
                self.assertEqual(len(list(app.screen.query("#btn-cancel"))), 1)

        self._run(runner())

    def test_buttons_fit_inside_narrow_dialog(self):
        async def runner():
            app = _KillDialogHost(show_preview=False)
            async with app.run_test(size=(34, 18)) as pilot:
                await pilot.pause()
                await pilot.pause()

                dialog = app.screen.query_one("#kill-dialog")
                buttons = list(app.screen.query("#kill-buttons Button"))
                self.assertEqual(len(buttons), 2)
                dialog_left = dialog.region.x
                dialog_right = dialog.region.x + dialog.region.width
                for button in buttons:
                    self.assertIsInstance(button, Button)
                    button_left = button.region.x
                    button_right = button.region.x + button.region.width
                    self.assertGreaterEqual(button_left, dialog_left)
                    self.assertLessEqual(button_right, dialog_right)

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
