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
import re
import sys
import unittest
from datetime import date
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
    def __init__(self, narrow: bool, operation: str = "pick",
                 all_models: dict | None = None,
                 today: date | None = None) -> None:
        super().__init__()
        self._narrow = narrow
        self._operation = operation
        self._all_models = _ALL_MODELS if all_models is None else all_models
        self._today = today

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(
            AgentModelPickerScreen(
                self._operation,
                all_models=self._all_models,
                narrow=self._narrow,
                today=self._today,
            )
        )


# t2194 empty-state fixture: one model with current `pick` usage only, so the
# all-ops list is populated and the `raw` this-op list is genuinely empty.
_TODAY = date(2026, 11, 4)
_PICK_ONLY_MODELS = {"claudecode": {"models": [{
    "name": "opus5_5",
    "usagestats": {"pick": {
        "all_time": {"runs": 3},
        "month": {"period": "2026-11", "runs": 3},
    }},
}]}}


def _screen_words(app) -> set[str]:
    """Every alphabetic word the exported screen shows. Per word, not per
    phrase: a wrapped label splits phrases across lines."""
    svg = app.export_screenshot()
    text = " ".join(
        part.replace("&#160;", " ") for part in re.findall(r">([^<]*)<", svg)
    )
    return set(re.findall(r"[A-Za-z]+", text))


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
                app.screen.action_next_list()  # top_all_ops -> top_usage
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


class EmptyStateHintVisibilityTests(unittest.TestCase):
    """t2194: an empty top list must SAY why it is empty, legibly.

    FuzzyOption rows are one line high, so the explanation lives in the
    wrapping #picker_empty_hint label; the placeholder row stays short. A long
    placeholder was measured clipped at both 40 and 120 cols.
    """

    def _run(self, coro):
        return asyncio.run(coro)

    def _assert_raw_this_op_hint_visible(self, narrow: bool, size: tuple[int, int]):
        async def runner():
            app = _PickerHost(narrow=narrow, operation="raw",
                              all_models=_PICK_ONLY_MODELS, today=_TODAY)
            async with app.run_test(size=size) as pilot:
                await pilot.pause()
                await pilot.pause()
                screen = app.screen
                hint = screen.query_one("#picker_empty_hint", Label)

                # Negative control: the all-ops list has an entry, so no hint.
                self.assertEqual(
                    [o.option_value for o in screen.query(FuzzyOption)],
                    ["claudecode/opus5_5"],
                )
                self.assertFalse(hint.display)

                screen.action_next_list()  # top_all_ops -> top_usage
                await pilot.pause()
                await pilot.pause()

                expected = AgentModelPickerScreen._EMPTY_HINT["top_usage"]
                self.assertTrue(hint.display)
                self.assertEqual(hint.render().plain, expected)
                dialog = screen.query_one("#picker_dialog")
                self.assertTrue(
                    dialog.region.contains_region(hint.region),
                    f"hint {hint.region} not inside dialog {dialog.region}",
                )
                if narrow:
                    self.assertGreaterEqual(hint.region.height, 2)  # it wrapped
                missing = [w for w in re.findall(r"[A-Za-z]+", expected)
                           if w not in _screen_words(app)]
                self.assertEqual(missing, [], f"hint words not on screen at {size}")

                rows = list(screen.query(FuzzyOption))
                self.assertEqual(len(rows), 1)
                row = rows[0]
                self.assertEqual(row.display_text, "(no recent usage for this op)")
                self.assertLessEqual(len("    " + row.display_text), row.region.width)

        self._run(runner())

    def test_hint_visible_narrow(self):
        self._assert_raw_this_op_hint_visible(narrow=True, size=(40, 50))

    def test_hint_visible_wide(self):
        self._assert_raw_this_op_hint_visible(narrow=False, size=(120, 40))

    def test_hint_hidden_again_on_a_populated_list(self):
        async def runner():
            app = _PickerHost(narrow=True, operation="raw",
                              all_models=_PICK_ONLY_MODELS, today=_TODAY)
            async with app.run_test(size=(40, 50)) as pilot:
                await pilot.pause()
                screen = app.screen
                screen.action_next_list()  # -> top_usage (empty)
                await pilot.pause()
                self.assertTrue(screen.query_one("#picker_empty_hint", Label).display)
                screen.action_next_list()  # -> all (populated)
                await pilot.pause()
                self.assertFalse(screen.query_one("#picker_empty_hint", Label).display)

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
