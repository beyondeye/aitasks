"""Tests for the board's dialog "run" branches dispatching full_command (t1225).

``AgentCommandScreen.run_terminal()`` stores in-dialog command edits into
``screen.full_command`` and the agent/profile controls regenerate it. Every
tmux branch already honored that; the direct-run ("run") branches rebuilt
default wrapper argv from the task filename instead, silently discarding the
user's edits and agent/model/profile overrides. t1162_4 fixed only the
work-report branch; this suite pins the remaining five (pick from the task
detail, pick from the board, brainstorm, resume, create) plus the shared
``run_dialog_command`` worker.

Coverage split:
- Construction-spy tests (``MagicMock`` app, the ``test_board_work_report.py``
  pattern) drive each action's dismiss callback and assert the dispatch.
- Negative controls pin the no-dialog fallback (``resolve_dry_run_command``
  returned None) still rebuilding wrapper argv, and the tmux branch unchanged.
- Worker-level tests cover BOTH dispatch paths. The no-terminal ``suspend()``
  branch is the one neither the construction spies nor a live manual check
  reach (a manual check runs with a real terminal available), so its full side
  effect set — argv, ``manager.load_tasks()``, ``refresh_board(refocus_filename=…)``
  — is asserted explicitly.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402

TASK_FILE = "t42_alpha.md"
# The string a user edit / agent override leaves in screen.full_command.
OVERRIDE = "opencode run --model x '/aitask-pick 42'"


class DialogRunTestBase(bf.FixtureBoardTestBase, unittest.TestCase):
    """Board module comes from the fixture harness (t1354_2); `cls.ab` is set by
    the mixin's setUpClass.

    Every external reach in this module is explicitly stubbed and asserted:
    `ab.find_terminal` and `ab.subprocess.call`, with `assert_called_once_with`
    pinning the exact argv. Nothing here can silently take a missing-helper
    fallback under the fixture cwd — the app is a MagicMock, so no board boot
    and no cwd-relative script is reachable.
    """

    def _mock_app(self, pick_cmd="claude '/aitask-pick 42'",
                  resume_cmd="claude '/aitask-resume 42'"):
        app = MagicMock()
        app._modal_is_active.return_value = False
        app._focus_existing_agent_window.return_value = False
        app._resolve_pick_command.return_value = pick_cmd
        app._resolve_pick_profile.return_value = "fast"
        app._resolve_resume_command.return_value = resume_cmd
        app._resolve_resume_profile.return_value = "fast"
        return app

    def _focused(self, cls=None):
        """Focused card stub carrying a real filename string."""
        if cls is None:
            return SimpleNamespace(
                task_data=SimpleNamespace(filename=TASK_FILE))
        card = MagicMock(spec=cls)
        card.task_data = SimpleNamespace(filename=TASK_FILE)
        return card

    def _dialog(self, app):
        """Pop (screen, callback) off the app's single push_screen call."""
        self.assertEqual(app.push_screen.call_count, 1)
        screen, callback = app.push_screen.call_args.args
        self.assertIsInstance(screen, self.ab.AgentCommandScreen)
        return screen, callback

    def _run_with_override(self, app):
        """Simulate an in-dialog edit, then fire the "run" result."""
        screen, callback = self._dialog(app)
        screen.full_command = OVERRIDE
        callback("run")
        return screen


class PickBranchTests(DialogRunTestBase):
    """Both pick entry points dispatch the dialog command, not wrapper argv."""

    def test_detail_pick_run_dispatches_dialog_command(self):
        ab = self.ab
        app = self._mock_app()
        task_data = SimpleNamespace(filename=TASK_FILE)
        with patch.object(ab, "resolve_agent_string", return_value=None):
            ab.KanbanApp._on_detail_result(app, task_data, "pick")
        self._run_with_override(app)
        app.run_dialog_command.assert_called_once_with(
            OVERRIDE, refocus_filename=TASK_FILE)
        app.run_aitask_pick.assert_not_called()

    def test_board_pick_run_dispatches_dialog_command(self):
        ab = self.ab
        app = self._mock_app()
        app._focused_card.return_value = self._focused()
        with patch.object(ab, "resolve_agent_string", return_value=None):
            ab.KanbanApp.action_pick_task(app)
        self._run_with_override(app)
        app.run_dialog_command.assert_called_once_with(
            OVERRIDE, refocus_filename=TASK_FILE)
        app.run_aitask_pick.assert_not_called()

    def test_detail_pick_without_resolved_command_keeps_wrapper_argv(self):
        """Negative control: no dialog was shown, so there is nothing to honor."""
        ab = self.ab
        app = self._mock_app(pick_cmd=None)
        task_data = SimpleNamespace(filename=TASK_FILE)
        ab.KanbanApp._on_detail_result(app, task_data, "pick")
        app.push_screen.assert_not_called()
        app.run_dialog_command.assert_not_called()
        app.run_aitask_pick.assert_called_once_with(TASK_FILE)

    def test_board_pick_without_resolved_command_keeps_wrapper_argv(self):
        ab = self.ab
        app = self._mock_app(pick_cmd=None)
        app._focused_card.return_value = self._focused()
        ab.KanbanApp.action_pick_task(app)
        app.push_screen.assert_not_called()
        app.run_dialog_command.assert_not_called()
        app.run_aitask_pick.assert_called_once_with(TASK_FILE)

    def test_board_pick_tmux_branch_still_uses_dialog_command(self):
        """Negative control: the tmux branch's behavior is unchanged."""
        ab = self.ab
        app = self._mock_app()
        app._focused_card.return_value = self._focused()
        with patch.object(ab, "resolve_agent_string", return_value=None):
            ab.KanbanApp.action_pick_task(app)
        screen, callback = self._dialog(app)
        screen.full_command = OVERRIDE
        cfg = ab.TmuxLaunchConfig(
            session="s", window="w", new_session=False, new_window=False)
        with patch.object(ab, "launch_in_tmux",
                          return_value=(None, None)) as launch:
            callback(cfg)
        launch.assert_called_once_with(OVERRIDE, cfg)
        app.run_dialog_command.assert_not_called()


class ResumeBranchTests(DialogRunTestBase):
    def _open(self, app):
        ab = self.ab
        app._focused_card.return_value = self._focused(ab.InFlightTaskCard)
        with patch.object(ab, "resolve_agent_string", return_value=None):
            ab.KanbanApp.action_gate_resume(app)

    def test_resume_run_dispatches_dialog_command(self):
        app = self._mock_app()
        self._open(app)
        self._run_with_override(app)
        app.run_dialog_command.assert_called_once_with(
            OVERRIDE, refocus_filename=TASK_FILE)
        app.run_codeagent_operation.assert_not_called()

    def test_resume_without_resolved_command_keeps_wrapper_argv(self):
        app = self._mock_app(resume_cmd=None)
        self._open(app)
        app.push_screen.assert_not_called()
        app.run_dialog_command.assert_not_called()
        app.run_codeagent_operation.assert_called_once_with(
            "resume", TASK_FILE)


class BrainstormBranchTests(DialogRunTestBase):
    def test_brainstorm_run_dispatches_dialog_command_without_notice(self):
        ab = self.ab
        app = self._mock_app()
        with patch.object(ab, "_current_tmux_session", return_value="sess"), \
                patch.object(ab, "find_window_by_name", return_value=None):
            ab.KanbanApp._launch_brainstorm(app, "42", TASK_FILE)
        self._run_with_override(app)
        # Not a code agent: a non-zero exit is an ordinary TUI quit.
        app.run_dialog_command.assert_called_once_with(
            OVERRIDE, refocus_filename=TASK_FILE, error_notice=None)


class CreateBranchTests(DialogRunTestBase):
    def test_create_run_dispatches_dialog_command_without_notice(self):
        ab = self.ab
        app = self._mock_app()
        ab.KanbanApp.action_create_task(app)
        self._run_with_override(app)
        # Column-scoped launch: no task file, so no refocus.
        app.run_dialog_command.assert_called_once_with(
            OVERRIDE, error_notice=None)


class DeadHelperRemovalTests(DialogRunTestBase):
    """The per-branch workers the dialog branches replaced must stay gone."""

    def test_per_branch_terminal_workers_are_removed(self):
        for name in ("_run_create_in_terminal", "_run_brainstorm_in_terminal",
                     "run_work_report"):
            self.assertFalse(
                hasattr(self.ab.KanbanApp, name),
                f"{name} was re-added — route the branch through "
                f"run_dialog_command instead")


class RunDialogCommandWorkerTests(DialogRunTestBase):
    """Both dispatch paths of the shared worker, incl. suspend side effects."""

    def _call(self, app, **kwargs):
        coro = self.ab.KanbanApp.run_dialog_command.__wrapped__(
            app, OVERRIDE, **kwargs)
        asyncio.run(coro)

    def test_terminal_path_shells_out_verbatim(self):
        ab = self.ab
        app = MagicMock()
        with patch.object(ab, "find_terminal", return_value="footerm"), \
                patch.object(ab, "spawn_in_terminal") as spawn:
            self._call(app, refocus_filename=TASK_FILE)
        spawn.assert_called_once_with("footerm", ["sh", "-c", OVERRIDE])
        # Fire-and-forget: the dialog callback owns the post-run refresh.
        app.manager.load_tasks.assert_not_called()
        app.refresh_board.assert_not_called()

    def test_suspend_path_dispatches_reloads_and_refocuses(self):
        ab = self.ab
        app = MagicMock()
        with patch.object(ab, "find_terminal", return_value=None), \
                patch.object(ab.subprocess, "call", return_value=0) as call:
            self._call(app, refocus_filename=TASK_FILE)
        call.assert_called_once_with(["sh", "-c", OVERRIDE])
        app.manager.load_tasks.assert_called_once_with()
        app.refresh_board.assert_called_once_with(refocus_filename=TASK_FILE)
        app.notify.assert_not_called()

    def test_suspend_path_without_refocus_refreshes_whole_board(self):
        ab = self.ab
        app = MagicMock()
        with patch.object(ab, "find_terminal", return_value=None), \
                patch.object(ab.subprocess, "call", return_value=0):
            self._call(app)
        app.refresh_board.assert_called_once_with(refocus_filename="")

    def test_suspend_path_notifies_on_failure_and_still_refreshes(self):
        ab = self.ab
        app = MagicMock()
        with patch.object(ab, "find_terminal", return_value=None), \
                patch.object(ab.subprocess, "call", return_value=1):
            self._call(app, refocus_filename=TASK_FILE)
        app.notify.assert_called_once_with(
            ab.CODEAGENT_FAILURE_NOTICE, severity="error")
        app.manager.load_tasks.assert_called_once_with()
        app.refresh_board.assert_called_once_with(refocus_filename=TASK_FILE)

    def test_suspend_path_stays_silent_when_notice_suppressed(self):
        """create / brainstorm: a non-zero exit is a cancel, not a failure."""
        ab = self.ab
        app = MagicMock()
        with patch.object(ab, "find_terminal", return_value=None), \
                patch.object(ab.subprocess, "call", return_value=1):
            self._call(app, refocus_filename=TASK_FILE, error_notice=None)
        app.notify.assert_not_called()
        app.manager.load_tasks.assert_called_once_with()
        app.refresh_board.assert_called_once_with(refocus_filename=TASK_FILE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
