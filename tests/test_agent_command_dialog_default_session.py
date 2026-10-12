"""Tests for AgentCommandScreen initial-session selection (t640, t1953).

Verifies the priority order used by `pick_initial_session`:
  1. the caller's explicit session (if live) — the TUI switcher's selection
  2. per-project last-session memory (if live)
  3. project_config's tmux.default_session (if live)
  4. first live session
  5. _NEW_SESSION_SENTINEL (no sessions at all)

and that the mounted dialog's tmux tab actually displays the resolved session
and lists that session's windows.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_agent_command_dialog_default_session.py -v
"""
import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "lib"))

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Label, Select  # noqa: E402

import agent_command_screen as acs  # noqa: E402
from agent_command_screen import (  # noqa: E402
    AgentCommandScreen,
    pick_initial_session,
    should_default_to_new_window,
    _NEW_SESSION_SENTINEL,
    _NEW_WINDOW_SENTINEL,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class PickInitialSessionTests(unittest.TestCase):
    def test_config_default_wins_when_no_memory(self):
        self.assertEqual(
            pick_initial_session(["aitasks", "aitasks_mob"], "aitasks_mob", None),
            "aitasks_mob",
        )

    def test_per_project_memory_wins_over_config(self):
        self.assertEqual(
            pick_initial_session(["aitasks", "aitasks_mob"], "aitasks_mob", "aitasks"),
            "aitasks",
        )

    def test_memory_ignored_when_session_not_live(self):
        self.assertEqual(
            pick_initial_session(["aitasks_mob"], "aitasks_mob", "aitasks_dead"),
            "aitasks_mob",
        )

    def test_config_default_ignored_when_not_live(self):
        self.assertEqual(
            pick_initial_session(["aitasks", "aitasks_other"], "aitasks_mob", None),
            "aitasks",
        )

    def test_no_config_no_memory_uses_first_session(self):
        self.assertEqual(
            pick_initial_session(["aitasks", "aitasks_mob"], None, None),
            "aitasks",
        )

    def test_empty_sessions_returns_sentinel(self):
        self.assertEqual(
            pick_initial_session([], "aitasks_mob", "aitasks"),
            _NEW_SESSION_SENTINEL,
        )

    def test_empty_string_default_treated_as_none(self):
        self.assertEqual(
            pick_initial_session(["aitasks"], "", None),
            "aitasks",
        )

    def test_explicit_session_wins_over_memory_and_config(self):
        self.assertEqual(
            pick_initial_session(
                ["s1", "s2"], "s1", "s1", explicit_session="s2",
            ),
            "s2",
        )

    def test_explicit_session_ignored_when_not_live(self):
        # Falls back through the unchanged order: memory, then config, then first.
        self.assertEqual(
            pick_initial_session(["s1", "s2"], "s1", "s2", explicit_session="gone"),
            "s2",
        )
        self.assertEqual(
            pick_initial_session(["s1", "s2"], "s2", None, explicit_session="gone"),
            "s2",
        )
        self.assertEqual(
            pick_initial_session(["s1", "s2"], None, None, explicit_session="gone"),
            "s1",
        )

    def test_empty_explicit_session_treated_as_none(self):
        self.assertEqual(
            pick_initial_session(["s1", "s2"], None, "s2", explicit_session=""),
            "s2",
        )


class _SavedSessionMemory:
    """Save/restore the class-level per-project session memory."""

    def setUp(self):
        self._saved_last_sessions = dict(AgentCommandScreen._last_session_by_project)
        AgentCommandScreen._last_session_by_project.clear()

    def tearDown(self):
        AgentCommandScreen._last_session_by_project.clear()
        AgentCommandScreen._last_session_by_project.update(self._saved_last_sessions)


class InitialSessionSeamTests(_SavedSessionMemory, unittest.TestCase):
    """The screen threads `default_tmux_session` into the resolution."""

    def _screen(self, **kwargs) -> AgentCommandScreen:
        return AgentCommandScreen(
            title="Launch Code Agent (no task)",
            full_command="claude",
            prompt_str="",
            default_window_name="agent-raw-1",
            project_root=REPO_ROOT,
            operation="raw",
            **kwargs,
        )

    def test_explicit_session_beats_remembered_one(self):
        screen = self._screen(default_tmux_session="s2")
        AgentCommandScreen._last_session_by_project[screen._project_key] = "s1"
        self.assertEqual(screen._initial_session(["s1", "s2"]), "s2")

    def test_without_explicit_session_memory_still_wins(self):
        # Negative control: every other caller passes no session.
        screen = self._screen()
        AgentCommandScreen._last_session_by_project[screen._project_key] = "s1"
        self.assertEqual(screen._initial_session(["s1", "s2"]), "s1")


class _DialogHost(App):
    """Plain App that pushes the real AgentCommandScreen."""

    def __init__(self, **screen_kwargs) -> None:
        super().__init__()
        self._screen_kwargs = screen_kwargs

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(AgentCommandScreen(
            "Launch Code Agent (no task)",
            "claude",
            "",
            default_window_name="agent-raw-1",
            project_root=REPO_ROOT,
            operation="raw",
            operation_args=[],
            **self._screen_kwargs,
        ))


class MountedTmuxTabSessionTests(_SavedSessionMemory, unittest.TestCase):
    """The mounted tmux tab displays the resolved session and lists ITS
    windows — so the seam above cannot pass with `_populate_tmux_tab`
    disconnected from it (t1953)."""

    _WINDOWS = {"s1": [("0", "s1win")], "s2": [("0", "s2win")]}

    def _mount(self, **screen_kwargs):
        window_calls: list[str] = []

        def _windows(session):
            window_calls.append(session)
            return list(self._WINDOWS.get(session, []))

        # Both the memory and the configured default point at s1.
        AgentCommandScreen._last_session_by_project[REPO_ROOT.resolve()] = "s1"
        patches = [
            patch.object(acs, "is_tmux_available", lambda: True),
            patch.object(acs, "get_tmux_sessions", lambda: ["s1", "s2"]),
            patch.object(acs, "get_tmux_windows", _windows),
            patch.object(acs, "load_tmux_defaults", lambda root: {
                "default_split": "vertical",
                "default_session": "s1",
                "prefer_tmux": True,
            }),
        ]
        observed: dict = {}

        async def go():
            app = _DialogHost(**screen_kwargs)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                screen = app.screen
                self.assertIsInstance(screen, AgentCommandScreen)
                observed["session"] = screen.query_one(
                    "#tmux_session_select", Select).value
                observed["window_labels"] = [
                    str(prompt) for prompt, _value in screen.query_one(
                        "#tmux_window_select", Select)._options
                ]

        for ctx in patches:
            ctx.start()
        try:
            asyncio.run(go())
        finally:
            for ctx in reversed(patches):
                ctx.stop()
        observed["window_calls"] = window_calls
        return observed

    def test_explicit_session_is_displayed_with_its_windows(self):
        got = self._mount(default_tmux_session="s2")
        self.assertEqual(got["session"], "s2")
        self.assertEqual(got["window_calls"][0], "s2")
        self.assertIn("0: s2win", got["window_labels"])
        self.assertNotIn("0: s1win", got["window_labels"])

    def test_no_explicit_session_keeps_the_remembered_one(self):
        got = self._mount()
        self.assertEqual(got["session"], "s1")
        self.assertEqual(got["window_calls"][0], "s1")
        self.assertIn("0: s1win", got["window_labels"])
        self.assertNotIn("0: s2win", got["window_labels"])

    def test_dead_explicit_session_falls_back(self):
        got = self._mount(default_tmux_session="gone")
        self.assertEqual(got["session"], "s1")
        self.assertIn("0: s1win", got["window_labels"])


class PickInitialWindowTests(unittest.TestCase):
    def setUp(self):
        self._saved_last_windows = dict(AgentCommandScreen._last_window_by_project)
        AgentCommandScreen._last_window_by_project.clear()

    def tearDown(self):
        AgentCommandScreen._last_window_by_project.clear()
        AgentCommandScreen._last_window_by_project.update(self._saved_last_windows)

    def _screen(self, **kwargs) -> AgentCommandScreen:
        return AgentCommandScreen(
            title="Pick Task t1111_2",
            full_command="codex -m gpt-5.5 '/aitask-pick 1111_2'",
            prompt_str="/aitask-pick 1111_2",
            project_root=REPO_ROOT,
            **kwargs,
        )

    def test_agent_launch_ignores_remembered_monitor_window(self):
        screen = self._screen(
            default_window_name="agent-pick-1111_2",
            operation="pick",
            operation_args=["1111_2"],
        )
        AgentCommandScreen._last_window_by_project[screen._project_key] = "9"

        with patch(
            "agent_command_screen.get_tmux_windows",
            return_value=[("9", "monitor"), ("10", "agent-pick-old")],
        ):
            _options, value = screen._compute_window_options("aitasks")

        self.assertEqual(value, _NEW_WINDOW_SENTINEL)

    def test_explicit_tmux_window_still_wins_for_agent_launch(self):
        screen = self._screen(
            default_window_name="agent-pick-1111_2",
            default_tmux_window="9",
            operation="pick",
            operation_args=["1111_2"],
        )
        AgentCommandScreen._last_window_by_project[screen._project_key] = "10"

        with patch(
            "agent_command_screen.get_tmux_windows",
            return_value=[("9", "monitor"), ("10", "agent-pick-old")],
        ):
            _options, value = screen._compute_window_options("aitasks")

        self.assertEqual(value, "9")

    def test_non_agent_launch_preserves_remembered_window(self):
        screen = self._screen(default_window_name="scratch")
        AgentCommandScreen._last_window_by_project[screen._project_key] = "9"

        with patch(
            "agent_command_screen.get_tmux_windows",
            return_value=[("9", "monitor"), ("10", "agent-pick-old")],
        ):
            _options, value = screen._compute_window_options("aitasks")

        self.assertEqual(value, "9")

    def test_fresh_window_policy_is_explicitly_overridable(self):
        self.assertTrue(should_default_to_new_window("agent-raw-1", "raw", None))
        self.assertTrue(should_default_to_new_window("create-task", None, None))
        self.assertFalse(should_default_to_new_window("agent-raw-1", "raw", "3"))
        self.assertFalse(should_default_to_new_window("scratch", None, None))


if __name__ == "__main__":
    unittest.main()
