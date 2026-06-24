"""Tests for AgentCommandScreen's empty-prompt handling (t1070).

A no-task launch (the switcher's bare-agent command: operation "raw", empty
prompt) passes prompt_str="". The Direct tab's "Prompt only:" row would then
render an empty label and a "Copy Prompt" button that copies nothing, so
`on_mount` skips the whole row when prompt_str is empty. Existing callers all
pass a non-empty prompt and must be unaffected — the row still mounts.

Run: python3 tests/test_agent_command_dialog_empty_prompt.py
  or: bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Label  # noqa: E402

from agent_command_screen import AgentCommandScreen  # noqa: E402


class _DialogHost(App):
    def __init__(self, prompt_str: str) -> None:
        super().__init__()
        self._prompt_str = prompt_str

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(
            AgentCommandScreen(
                title="Launch Code Agent (no task)",
                full_command="claude --model claude-opus-4-8",
                prompt_str=self._prompt_str,
                default_window_name="agent-raw-1",
                project_root=REPO_ROOT,
                operation="raw",
                operation_args=[],
                default_agent_string="claudecode/opus4_8",
            )
        )


class EmptyPromptRowTests(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def _prompt_widget_counts(self, prompt_str: str):
        async def runner():
            app = _DialogHost(prompt_str=prompt_str)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                screen = app.screen
                return (
                    len(screen.query("#agent_cmd_prompt_label")),
                    len(screen.query("#btn_copy_prompt")),
                )

        return self._run(runner())

    def test_empty_prompt_hides_row(self):
        labels, buttons = self._prompt_widget_counts("")
        self.assertEqual(labels, 0, "no prompt label when prompt is empty")
        self.assertEqual(buttons, 0, "no Copy Prompt button when prompt is empty")

    def test_nonempty_prompt_keeps_row(self):
        # Regression guard for existing callers (board/monitor/syncer/...).
        labels, buttons = self._prompt_widget_counts("/aitask-pick 42")
        self.assertEqual(labels, 1, "prompt label still mounts for real prompts")
        self.assertEqual(buttons, 1, "Copy Prompt button still mounts")


if __name__ == "__main__":
    unittest.main()
