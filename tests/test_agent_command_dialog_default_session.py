"""Tests for AgentCommandScreen initial-session selection (t640).

Verifies the priority order used by `pick_initial_session`:
  1. per-project last-session memory (if live)
  2. project_config's tmux.default_session (if live)
  3. first live session
  4. _NEW_SESSION_SENTINEL (no sessions at all)

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_agent_command_dialog_default_session.py -v
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "lib"))

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
