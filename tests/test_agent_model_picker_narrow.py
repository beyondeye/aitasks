"""Tests for AgentModelPickerScreen narrow mode (t1153).

The minimonitor companion pane is ~40 cols wide. The shared model picker was
fixed at width:65% and not narrow-aware, so option rows "<agent>/<name>" were
clipped after the long "claudecode/" prefix (11 chars), hiding the model name.
`narrow=True` widens the dialog to full width so the name stays visible.

Mirrors tests/test_agent_command_dialog_narrow.py — drive the screen with a
small terminal and assert the narrow class is applied and the claudecode option
row is wide enough to render the model name un-clipped. Also asserts the flag is
actually threaded from AgentCommandScreen (not merely accepted).

Run: python3 -m pytest tests/test_agent_model_picker_narrow.py -v
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

from agent_model_picker import AgentModelPickerScreen, FuzzyOption  # noqa: E402
from agent_command_screen import AgentCommandScreen  # noqa: E402


# A claudecode model whose name would be clipped by the old 65% width once the
# "claudecode/" prefix is prepended.
_ALL_MODELS = {"claudecode": {"models": [{"name": "opus4_8"}]}}
_CLAUDE_ROW = "claudecode/opus4_8"


class _PickerHost(App):
    def __init__(self, narrow: bool) -> None:
        super().__init__()
        self._narrow = narrow

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(
            AgentModelPickerScreen(
                "pick",
                all_models=_ALL_MODELS,
                narrow=self._narrow,
            )
        )


class _CommandHost(App):
    """Hosts AgentCommandScreen(narrow=True) to prove the flag is threaded
    through action_change_agent into the pushed picker."""

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(
            AgentCommandScreen(
                title="Pick Task t1153",
                full_command="claude '/aitask-pick 1153'",
                prompt_str="/aitask-pick 1153",
                default_window_name="agent-pick-1153",
                project_root=REPO_ROOT,
                operation="pick",
                operation_args=["1153"],
                default_agent_string="claudecode/opus4_8",
                skill_name="pick",
                default_profile="fast",
                narrow=True,
            )
        )


class AgentModelPickerNarrowTests(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_narrow_class_applied(self):
        async def runner():
            app = _PickerHost(narrow=True)
            async with app.run_test(size=(40, 50)) as pilot:
                await pilot.pause()
                await pilot.pause()
                self.assertIsInstance(app.screen, AgentModelPickerScreen)
                self.assertIn("narrow", app.screen.classes)

        self._run(runner())

    def test_default_is_not_narrow(self):
        async def runner():
            app = _PickerHost(narrow=False)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                self.assertIsInstance(app.screen, AgentModelPickerScreen)
                self.assertNotIn("narrow", app.screen.classes)

        self._run(runner())

    def test_claudecode_model_name_fits_narrow(self):
        """At 40 cols the claudecode option row has room for the full model
        name (prefix + "claudecode/opus4_8") — the bug clipped it at 65%."""
        async def runner():
            app = _PickerHost(narrow=True)
            async with app.run_test(size=(40, 50)) as pilot:
                await pilot.pause()
                # Switch to the "all" mode (index 2), which renders from the
                # passed all_models rather than reading real models_*.json.
                app.screen.action_next_list()  # top -> top_usage
                app.screen.action_next_list()  # top_usage -> all
                await pilot.pause()
                await pilot.pause()

                rows = [
                    o for o in app.screen.query(FuzzyOption)
                    if o.display_text == _CLAUDE_ROW
                ]
                self.assertEqual(
                    len(rows), 1,
                    f"expected exactly one {_CLAUDE_ROW!r} option row, "
                    f"got {[o.display_text for o in app.screen.query(FuzzyOption)]}",
                )
                row = rows[0]
                # FuzzyOption.render() prefixes the display text with " >> " when
                # highlighted / "    " otherwise — 4 cols either way. The row must
                # be wide enough to show that prefix plus the full model name.
                needed = len("    " + _CLAUDE_ROW)
                self.assertGreaterEqual(
                    row.region.width, needed,
                    f"narrow option row width {row.region.width} < {needed} "
                    f"needed for un-clipped {_CLAUDE_ROW!r}",
                )

        self._run(runner())

    def test_command_screen_threads_narrow_into_picker(self):
        """AgentCommandScreen(narrow=True).action_change_agent() pushes a
        narrow-aware picker — the flag is threaded, not just accepted."""
        async def runner():
            app = _CommandHost()
            async with app.run_test(size=(40, 50)) as pilot:
                await pilot.pause()
                await pilot.pause()
                app.screen.action_change_agent()
                await pilot.pause()
                await pilot.pause()
                self.assertIsInstance(app.screen, AgentModelPickerScreen)
                self.assertIn("narrow", app.screen.classes)

        self._run(runner())

    def test_switch_hint_stays_visible_narrow(self):
        """In narrow mode the "Shift+←/→ to switch" hint stacks onto its own
        line so it is not clipped off the right edge (2 lines, hint present)."""
        async def runner():
            app = _PickerHost(narrow=True)
            async with app.run_test(size=(40, 50)) as pilot:
                await pilot.pause()
                await pilot.pause()
                from textual.widgets import Label
                label = app.screen.query_one("#picker_step_label", Label)
                text = label.render().plain
                self.assertIn("Shift", text)
                # Own line = a newline separates the mode label from the hint,
                # and the label is two rows tall.
                self.assertIn("\n", text)
                self.assertGreaterEqual(label.size.height, 2)

        self._run(runner())

    def test_switch_hint_single_line_wide(self):
        """Wide (default) hosts keep the hint inline on one line — no regression."""
        async def runner():
            app = _PickerHost(narrow=False)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                from textual.widgets import Label
                label = app.screen.query_one("#picker_step_label", Label)
                text = label.render().plain
                self.assertIn("Shift", text)
                self.assertNotIn("\n", text)

        self._run(runner())


class AgentCommandScreenEscapeTests(unittest.TestCase):
    """AgentCommandScreen must be cancelable via Esc even on hosts that do NOT
    delegate to handle_escape() — the minimonitor Shift+E launch has no
    App-level escape binding (board/codebrowser do), so the screen owns one."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_escape_dismisses_on_non_delegating_host(self):
        async def runner():
            app = _CommandHost()  # plain App, no escape binding of its own
            async with app.run_test(size=(40, 50)) as pilot:
                await pilot.pause()
                await pilot.pause()
                self.assertIsInstance(app.screen, AgentCommandScreen)
                # Clear any Input focus so escape dismisses rather than unfocuses.
                app.screen.set_focus(None)
                await pilot.press("escape")
                await pilot.pause()
                await pilot.pause()
                self.assertNotIsInstance(app.screen, AgentCommandScreen)

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
