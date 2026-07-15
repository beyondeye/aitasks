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


class ExplorePickRegistrationTests(unittest.TestCase):
    """The `X` explore-with-picker action registers alongside the untouched
    fire-and-forget `x` explore shortcut (t1148)."""

    def test_binding_present(self):
        match = [
            b for b in ts._QUICK_JUMP_BINDINGS
            if b.action == "shortcut_explore_pick"
        ]
        self.assertEqual(len(match), 1, "exactly one shortcut_explore_pick binding")
        self.assertEqual(match[0].key, "X")

    def test_hint_item_present(self):
        self.assertIn(
            ("shortcut_explore_pick", "explore+", "X"), ts._HINT_ITEMS,
        )

    def test_fire_and_forget_explore_untouched(self):
        # Negative control: adding the picker variant must not disturb the
        # original `x` fire-and-forget binding/hint.
        explore = [
            b for b in ts._QUICK_JUMP_BINDINGS if b.action == "shortcut_explore"
        ]
        self.assertEqual(len(explore), 1)
        self.assertEqual(explore[0].key, "x")
        self.assertIn(("shortcut_explore", "explore", "x"), ts._HINT_ITEMS)


class AgentLaunchActionTests(unittest.TestCase):
    def _make_overlay(self):
        ov = ts.TuiSwitcherOverlay(session="s1")
        # _session is a derived read-only property (t1099); identity lives in
        # _selected_key. With no discovered sessions it returns the provisional
        # "s1", matching the pre-t1099 behavior this test asserts.
        ov._selected_key = "s1"
        ov._running_names = set()
        ov.dismiss = MagicMock()
        ov._handle_stale_selection = MagicMock(return_value=False)
        ov._ensure_session_live = MagicMock(return_value=True)
        ov._selected_project_root = MagicMock(return_value=Path("/p1"))
        return ov

    def _make_overlay_narrow(self):
        ov = ts.TuiSwitcherOverlay(session="s1", narrow=True)
        ov._selected_key = "s1"
        ov._running_names = set()
        ov.dismiss = MagicMock()
        ov._handle_stale_selection = MagicMock(return_value=False)
        ov._ensure_session_live = MagicMock(return_value=True)
        ov._selected_project_root = MagicMock(return_value=Path("/p1"))
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
            # Negative control: a wide host (default overlay, narrow=False) must
            # NOT stack the dialog — this is the board / full-monitor path.
            self.assertFalse(screen._narrow, "wide host keeps the full layout")

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

    def test_narrow_host_opens_narrow_dialog(self):
        """Regression (t1122): a narrow host (minimonitor) opens the raw-agent
        dialog in the narrow small-pane layout."""
        ov = self._make_overlay_narrow()
        mock_app = MagicMock()
        with patch.object(ts.TuiSwitcherOverlay, "app",
                          new_callable=PropertyMock, return_value=mock_app), \
             patch.object(alu, "resolve_dry_run_command",
                          return_value="claude --model claude-opus-4-8"), \
             patch.object(alu, "resolve_agent_string",
                          return_value="claudecode/opus4_8"):
            ov.action_shortcut_agent()
            self.assertEqual(mock_app.push_screen.call_count, 1)
            screen, _callback = mock_app.push_screen.call_args.args
            self.assertIsInstance(screen, AgentCommandScreen)
            self.assertTrue(screen._narrow, "narrow host stacks the dialog")

    def test_action_aborts_when_command_unresolved(self):
        ov = self._make_overlay()
        mock_app = MagicMock()
        with patch.object(ts.TuiSwitcherOverlay, "app",
                          new_callable=PropertyMock, return_value=mock_app), \
             patch.object(alu, "resolve_dry_run_command", return_value=None):
            ov.action_shortcut_agent()
            self.assertFalse(mock_app.push_screen.called)
            self.assertTrue(mock_app.notify.called)


class ExplorePickActionTests(unittest.TestCase):
    """The `X` handler opens the AgentCommandScreen for operation="explore"
    and routes its result exactly like the raw-agent handler (t1148)."""

    def _make_overlay(self, narrow=False):
        ov = ts.TuiSwitcherOverlay(session="s1", narrow=narrow)
        ov._selected_key = "s1"
        ov._running_names = set()
        ov.dismiss = MagicMock()
        ov._handle_stale_selection = MagicMock(return_value=False)
        ov._ensure_session_live = MagicMock(return_value=True)
        ov._selected_project_root = MagicMock(return_value=Path("/p1"))
        return ov

    def test_action_pushes_explore_dialog_and_routes_result(self):
        ov = self._make_overlay()
        mock_app = MagicMock()

        with patch.object(ts.TuiSwitcherOverlay, "app",
                          new_callable=PropertyMock, return_value=mock_app), \
             patch.object(alu, "resolve_dry_run_command",
                          return_value="claude --model claude-opus-4-8 /aitask-explore"), \
             patch.object(alu, "resolve_agent_string",
                          return_value="claudecode/opus4_8"), \
             patch.object(alu, "launch_in_tmux",
                          return_value=(123, None)) as mock_launch, \
             patch.object(alu, "maybe_spawn_minimonitor") as mock_mm, \
             patch.object(alu, "find_terminal",
                          return_value="xterm") as mock_ft, \
             patch.object(alu, "spawn_in_terminal") as mock_sit:
            ov.action_shortcut_explore_pick()

            # The dialog was pushed for the explore operation.
            self.assertEqual(mock_app.push_screen.call_count, 1)
            screen, callback = mock_app.push_screen.call_args.args
            self.assertIsInstance(screen, AgentCommandScreen)
            self.assertEqual(screen.operation, "explore")
            self.assertEqual(screen.prompt_str, "/aitask-explore")
            # Negative control: a wide host keeps the full layout.
            self.assertFalse(screen._narrow, "wide host keeps the full layout")

            # tmux result → launch_in_tmux + minimonitor (new window) + dismiss.
            cfg = TmuxLaunchConfig("s1", "agent-explore-1",
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

    def test_narrow_host_opens_narrow_dialog(self):
        ov = self._make_overlay(narrow=True)
        mock_app = MagicMock()
        with patch.object(ts.TuiSwitcherOverlay, "app",
                          new_callable=PropertyMock, return_value=mock_app), \
             patch.object(alu, "resolve_dry_run_command",
                          return_value="claude /aitask-explore"), \
             patch.object(alu, "resolve_agent_string",
                          return_value="claudecode/opus4_8"):
            ov.action_shortcut_explore_pick()
            self.assertEqual(mock_app.push_screen.call_count, 1)
            screen, _callback = mock_app.push_screen.call_args.args
            self.assertIsInstance(screen, AgentCommandScreen)
            self.assertTrue(screen._narrow, "narrow host stacks the dialog")

    def test_action_aborts_when_command_unresolved(self):
        ov = self._make_overlay()
        mock_app = MagicMock()
        with patch.object(ts.TuiSwitcherOverlay, "app",
                          new_callable=PropertyMock, return_value=mock_app), \
             patch.object(alu, "resolve_dry_run_command", return_value=None):
            ov.action_shortcut_explore_pick()
            self.assertFalse(mock_app.push_screen.called)
            self.assertTrue(mock_app.notify.called)


class SwitcherNarrowSeamTests(unittest.TestCase):
    """The narrow decision seam (t1122): the mixin default, the minimonitor
    override, and the threading through the real entry point action_tui_switcher.
    """

    def test_base_mixin_defaults_wide(self):
        # A bare host using only the mixin declares itself wide.
        self.assertIs(ts.TuiSwitcherMixin._switcher_narrow(object()), False)

    def test_minimonitor_declares_narrow(self):
        # The narrow host overrides the hook to True.
        sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
        from monitor import minimonitor_app as mm  # noqa: E402
        self.assertIs(mm.MiniMonitorApp._switcher_narrow(object()), True)

    def test_entry_point_threads_narrow_into_overlay(self):
        """action_tui_switcher must pass whatever _switcher_narrow() returns
        into the overlay it pushes — pin the decision at the real entry point,
        not just the leaf construction."""
        for declared in (True, False):
            with self.subTest(declared=declared):
                host = ts.TuiSwitcherMixin()
                host.current_tui_name = "minimonitor"
                host.notify = MagicMock()
                host.push_screen = MagicMock()
                host._switcher_selected_session = MagicMock(return_value=None)
                host._switcher_narrow = MagicMock(return_value=declared)
                with patch.dict(ts.os.environ, {"TMUX": "/tmp/x"}), \
                     patch.object(ts, "_detect_current_session",
                                  return_value="s1"):
                    host.action_tui_switcher()
                self.assertEqual(host.push_screen.call_count, 1)
                overlay = host.push_screen.call_args.args[0]
                self.assertIsInstance(overlay, ts.TuiSwitcherOverlay)
                self.assertEqual(overlay._narrow, declared)


if __name__ == "__main__":
    unittest.main()
