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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "lib"))

from agent_command_screen import pick_initial_session, _NEW_SESSION_SENTINEL


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


if __name__ == "__main__":
    unittest.main()
