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
    def __init__(
        self,
        show_preview: bool,
        snap: PaneSnapshot | None = None,
        task_info: TaskInfo | None = None,
    ) -> None:
        super().__init__()
        self._show_preview = show_preview
        self._snap = snap if snap is not None else _snapshot()
        self._task_info = task_info if task_info is not None else _task_info()

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(
            KillConfirmDialog(
                self._snap,
                self._task_info,
                show_preview=self._show_preview,
            )
        )


def _snapshot(
    window_name: str = "agent-t995-codex", current_command: str = "bash"
) -> PaneSnapshot:
    pane = TmuxPaneInfo(
        window_index="1",
        window_name=window_name,
        pane_index="0",
        pane_id="%42",
        pane_pid=4242,
        current_command=current_command,
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


def _task_info(title: str = "Trim minimonitor kill confirmation dialog") -> TaskInfo:
    return TaskInfo(
        task_id="995",
        task_file="aitasks/t995_minimonitor_kill_confirm_dialog_trim.md",
        title=title,
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

    def test_user_fields_with_markup_render_literally(self):
        """Window name, task title and command are user-derived text on a
        markup-enabled Static (t2006). Unescaped, `[/]` raises MarkupError and
        takes the app down; under `rich.markup.escape` a backslash before a
        bracket doubles and a trailing backslash eats the next tag. Read back
        through the real widget, so the parser is Textual's, not Rich's."""
        cases = [
            ("agent-\\[bold]y", "Fix [/] ends with \\", "cmd\\"),
            ("agent-[/]x", "a [dim]b[/dim]", "[/]cmd"),
        ]
        for window, title, cmd in cases:
            with self.subTest(window=window):
                async def runner():
                    app = _KillDialogHost(
                        show_preview=False,
                        snap=_snapshot(window_name=window, current_command=cmd),
                        task_info=_task_info(title=title),
                    )
                    async with app.run_test(size=(100, 24)) as pilot:
                        await pilot.pause()
                        await pilot.pause()

                        details = app.screen.query_one("#kill-details").render()
                        lines = details.plain.split("\n")
                        self.assertEqual(lines[0], f"Window:   1:{window} (pane 0)")
                        self.assertEqual(lines[1], f"Task:     t995: {title}")
                        self.assertEqual(lines[-1], f"Process:  {cmd} (PID 4242)")
                        start = details.plain.index(f"1:{window}")
                        end = start + len(f"1:{window}")
                        self.assertIn(
                            "bold",
                            {str(s.style) for s in details.spans
                             if s.start == start and s.end == end},
                        )
                        self.assertIsNone(app.return_code)

                self._run(runner())


if __name__ == "__main__":
    unittest.main()
