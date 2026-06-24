"""Tests for the TUI switcher's bare-code-agent launch shortcut (t1070).

The switcher gained an `e` quick-jump that opens the shared AgentCommandScreen
with `operation="raw"` and an empty prompt so the user can launch an interactive
code agent that runs no `/aitask-*` slash command. Unlike explore/create (which
fire-and-forget via `_spawn_in_session`), this one pushes the dialog and routes
its result (a TmuxLaunchConfig → tmux, "run" → terminal) in a callback.

Run: python3 tests/test_tui_switcher_agent_launch.py
  or: bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_launch_utils as alu  # noqa: E402
import tui_switcher as ts  # noqa: E402
from agent_command_screen import AgentCommandScreen  # noqa: E402
from agent_launch_utils import TmuxLaunchConfig  # noqa: E402


class QuickJumpRegistrationTests(unittest.TestCase):
    """The action must be registered in BOTH parallel lists, bound to `e`."""

    def test_binding_present(self):
        match = [
            b for b in ts._QUICK_JUMP_BINDINGS
            if b.action == "shortcut_agent"
        ]
        self.assertEqual(len(match), 1, "exactly one shortcut_agent binding")
        self.assertEqual(match[0].key, "e")

    def test_hint_item_present(self):
        actions = {action for (action, _label, _key) in ts._HINT_ITEMS}
        self.assertIn("shortcut_agent", actions)
        entry = next(e for e in ts._HINT_ITEMS if e[0] == "shortcut_agent")
        self.assertEqual(entry[2], "e", "hint default key matches the binding")


class AgentLaunchActionTests(unittest.TestCase):
    def _make_overlay(self):
        ov = ts.TuiSwitcherOverlay(session="s1")
        ov._session = "s1"
        ov._running_names = set()
        ov.dismiss = MagicMock()
        ov._handle_stale_selection = MagicMock(return_value=False)
        ov._ensure_session_live = MagicMock(return_value=True)
        ov._project_root_for_session = MagicMock(return_value=Path("/p1"))
        return ov

    def test_action_pushes_no_task_dialog_and_routes_result(self):
        ov = self._make_overlay()
        mock_app = MagicMock()

        # The method does `from agent_launch_utils import ...` locally, so the
        # closure binds whatever the module attribute is AT CALL TIME — patch
        # the module attributes around both the call and the callback invocation.
        with patch.object(ts.TuiSwitcherOverlay, "app",
                          new_callable=PropertyMock, return_value=mock_app), \
             patch.object(alu, "resolve_dry_run_command",
                          return_value="claude --model claude-opus-4-8"), \
             patch.object(alu, "resolve_agent_string",
                          return_value="claudecode/opus4_8"), \
             patch.object(alu, "launch_in_tmux",
                          return_value=(123, None)) as mock_launch, \
             patch.object(alu, "maybe_spawn_minimonitor") as mock_mm, \
             patch.object(alu, "find_terminal",
                          return_value="xterm") as mock_ft, \
             patch.object(alu, "spawn_in_terminal") as mock_sit:
            ov.action_shortcut_agent()

            # The dialog was pushed with the no-task contract.
            self.assertEqual(mock_app.push_screen.call_count, 1)
            screen, callback = mock_app.push_screen.call_args.args
            self.assertIsInstance(screen, AgentCommandScreen)
            self.assertEqual(screen.prompt_str, "", "no-task launch = empty prompt")
            self.assertEqual(screen.operation, "raw")

            # tmux result → launch_in_tmux + minimonitor (new window) + dismiss.
            cfg = TmuxLaunchConfig("s1", "agent-raw-1",
                                   new_session=False, new_window=True)
            callback(cfg)
            self.assertEqual(mock_launch.call_count, 1)
            self.assertEqual(mock_mm.call_count, 1)
            self.assertTrue(ov.dismiss.called)

            # "run" result → spawn_in_terminal in a found terminal.
            ov.dismiss.reset_mock()
            callback("run")
            self.assertTrue(mock_ft.called)
            self.assertEqual(mock_sit.call_count, 1)
            self.assertTrue(ov.dismiss.called)

            # Cancel (None) → no launch, overlay left open (no extra dismiss).
            ov.dismiss.reset_mock()
            callback(None)
            self.assertFalse(ov.dismiss.called)

    def test_action_aborts_when_command_unresolved(self):
        ov = self._make_overlay()
        mock_app = MagicMock()
        with patch.object(ts.TuiSwitcherOverlay, "app",
                          new_callable=PropertyMock, return_value=mock_app), \
             patch.object(alu, "resolve_dry_run_command", return_value=None):
            ov.action_shortcut_agent()
            self.assertFalse(mock_app.push_screen.called)
            self.assertTrue(mock_app.notify.called)


if __name__ == "__main__":
    unittest.main()
