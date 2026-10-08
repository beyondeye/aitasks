"""The board's conflict dialog offers a code agent (t1911).

`SyncConflictScreen` now dismisses with a closed set — CONFLICT_CHOICE_AGENT,
CONFLICT_CHOICE_INTERACTIVE, or None — instead of a bool. These tests pin the
board's routing of each value (including a stray `True`, which must launch
nothing: a leftover `if resolve:` would read it as "interactive") and the agent
launch that `_launch_data_conflict_agent` builds.

Construction-spy pattern of `tests/test_board_dialog_run_dispatch.py`: the app
is a MagicMock, so no board boots and nothing cwd-relative is reachable; every
external reach (`resolve_dry_run_command`, `launch_in_tmux`,
`maybe_spawn_minimonitor`) is patched on the board module, where the method
looks it up.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402

FILES = ["aitasks/t7_x.md", "aiplans/p7_x.md"]
CMD = "claude 'resolve the conflict'"


class ConflictDialogRoutingTests(bf.FixtureBoardTestBase, unittest.TestCase):
    def _callback(self):
        ab = self.ab
        app = MagicMock()
        ab.KanbanApp._show_conflict_dialog(app, FILES)
        self.assertEqual(app.push_screen.call_count, 1)
        screen, callback = app.push_screen.call_args.args
        self.assertIsInstance(screen, ab.SyncConflictScreen)
        self.assertEqual(screen.conflicted_files, FILES)
        return app, callback

    def test_interactive_choice_runs_interactive_sync(self):
        app, callback = self._callback()
        callback(self.ab.CONFLICT_CHOICE_INTERACTIVE)
        app._run_interactive_sync_shared.assert_called_once_with()
        app._launch_data_conflict_agent.assert_not_called()

    def test_agent_choice_launches_the_agent_for_these_files(self):
        app, callback = self._callback()
        callback(self.ab.CONFLICT_CHOICE_AGENT)
        app._launch_data_conflict_agent.assert_called_once_with(FILES)
        app._run_interactive_sync_shared.assert_not_called()

    def test_dismiss_and_a_stray_true_only_reload(self):
        for choice in (None, True):
            with self.subTest(choice=choice):
                app, callback = self._callback()
                callback(choice)
                app._launch_data_conflict_agent.assert_not_called()
                app._run_interactive_sync_shared.assert_not_called()
                app.manager.load_tasks.assert_called_once_with()
                app.refresh_board.assert_called_once_with()


class LaunchDataConflictAgentTests(bf.FixtureBoardTestBase, unittest.TestCase):
    def _launch(self, cmd=CMD):
        ab = self.ab
        app = MagicMock()
        with patch.object(ab, "resolve_dry_run_command", return_value=cmd) as dry, \
                patch.object(ab, "resolve_agent_string", return_value=None):
            ab.KanbanApp._launch_data_conflict_agent(app, FILES)
        return app, dry

    def _dialog(self, app):
        self.assertEqual(app.push_screen.call_count, 1)
        screen, callback = app.push_screen.call_args.args
        self.assertIsInstance(screen, self.ab.AgentCommandScreen)
        return screen, callback

    def test_dialog_carries_the_launch_context(self):
        app, dry = self._launch()
        screen, _ = self._dialog(app)
        root = str(Path(".").resolve())
        self.assertEqual(screen.default_window_name, self.ab.DATA_CONFLICT_WINDOW_NAME)
        self.assertEqual(screen.operation, "raw")
        self.assertEqual(screen.operation_args, [screen.prompt_str])
        self.assertEqual(screen.full_command, CMD)
        self.assertIn(root, screen.prompt_str)
        for f in FILES:
            self.assertIn(f, screen.prompt_str)
        dry.assert_called_once_with(Path("."), "raw", screen.prompt_str)

    def test_run_result_dispatches_the_dialog_command(self):
        app, _ = self._launch()
        screen, callback = self._dialog(app)
        screen.full_command = "edited"
        callback("run")
        app.run_dialog_command.assert_called_once_with("edited")

    def test_tmux_result_launches_and_spawns_minimonitor(self):
        ab = self.ab
        app, _ = self._launch()
        screen, callback = self._dialog(app)
        cfg = ab.TmuxLaunchConfig(
            session="s", window="w", new_session=False, new_window=True)
        with patch.object(ab, "launch_in_tmux", return_value=(1, None)) as launch, \
                patch.object(ab, "maybe_spawn_minimonitor") as mini:
            callback(cfg)
        launch.assert_called_once_with(CMD, cfg)
        mini.assert_called_once_with("s", "w")
        app.run_dialog_command.assert_not_called()

    def test_cancel_launches_nothing(self):
        ab = self.ab
        app, _ = self._launch()
        _, callback = self._dialog(app)
        with patch.object(ab, "launch_in_tmux") as launch:
            callback(None)
        launch.assert_not_called()
        app.run_dialog_command.assert_not_called()

    def test_unresolvable_command_notifies_and_shows_no_dialog(self):
        app, _ = self._launch(cmd=None)
        app.push_screen.assert_not_called()
        app.notify.assert_called_once()
        self.assertEqual(app.notify.call_args.kwargs.get("severity"), "error")


if __name__ == "__main__":
    unittest.main()
