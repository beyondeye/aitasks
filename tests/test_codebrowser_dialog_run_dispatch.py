"""Codebrowser dialog "run" branches dispatch the dialog's full_command (t1929).

``AgentCommandScreen.run_terminal()`` stores in-dialog command edits into
``screen.full_command`` and the agent/profile controls regenerate it (t1225).
The tmux branches already honoured that; codebrowser's run-in-terminal branches
(explain, create, history QA) rebuilt default argv instead, silently launching
a different configuration from the one the dialog showed. All three now route
through the shared ``CodeBrowserApp.run_launch_command`` worker.

Coverage split:
- Construction-spy tests (``MagicMock`` app / screen, unbound action calls)
  drive each action's dismiss callback with an edited ``full_command`` and
  assert the dispatch. Negative controls pin the no-dialog fallback (still
  rebuilt wrapper argv) and the unchanged tmux branch.
- ``CreateDefaultCommandTests`` RUNS the create dialog's *default* command
  through ``sh -c`` under a project root containing a space — the edited-
  command spies replace the default, so they cannot see its quoting.
- ``LaunchWorkerTests`` call the undecorated worker on a ``MagicMock`` app for
  every dispatch / error path.
- ``LaunchWorkerLiveTests`` boot a real Textual app borrowing the real worker:
  the inline OSError must be handled INSIDE the real ``App.suspend`` (which has
  no ``finally`` around the driver resume, Textual 8.2.7), and an exclusive
  launch must not cancel default-group annotation workers.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "codebrowser"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_utils  # noqa: E402
import codebrowser_app as cba  # noqa: E402
import history_screen as hs  # noqa: E402
from agent_command_screen import AgentCommandScreen  # noqa: E402
from agent_launch_utils import TmuxLaunchConfig  # noqa: E402
from codebrowser_app import CodeBrowserApp  # noqa: E402
from history_screen import HistoryScreen  # noqa: E402
from textual import work  # noqa: E402
from textual.app import App, SuspendNotSupported  # noqa: E402
from textual.worker import WorkerState  # noqa: E402

ROOT = Path("/tmp/cb-project")
# The string a user edit / agent override leaves in screen.full_command.
OVERRIDE = "opencode run --model x '/aitask-explain foo.py'"
DEFAULT_EXPLAIN = "claude '/aitask-explain foo.py'"
DEFAULT_QA = "claude '/aitask-qa 42'"
TMUX_CFG = TmuxLaunchConfig(session="s", window="w", new_session=False,
                            new_window=False)


def _code_viewer(selected=None, total_lines=0):
    viewer = MagicMock()
    viewer.get_selected_range.return_value = selected
    viewer._total_lines = total_lines
    return viewer


def _browser_app(root=ROOT, current_file="foo.py", viewer=None):
    app = MagicMock()
    app._project_root = root
    app._current_file_path = root / current_file if current_file else None
    app.query_one.return_value = viewer or _code_viewer()
    app._detect_tmux_window.return_value = None
    app._codeagent_argv = (
        lambda op, arg: CodeBrowserApp._codeagent_argv(app, op, arg))
    return app


def _pop_dialog(push_screen):
    """(screen, callback) off a single push_screen call."""
    assert push_screen.call_count == 1, push_screen.call_count
    screen, callback = push_screen.call_args.args
    assert isinstance(screen, AgentCommandScreen), screen
    return screen, callback


@contextlib.contextmanager
def _explain_seams(dry_run=DEFAULT_EXPLAIN):
    with patch.object(cba, "resolve_agent_binary",
                      return_value=("claude", "claude", None)), \
            patch.object(cba.shutil, "which", return_value="/usr/bin/claude"), \
            patch.object(cba, "resolve_dry_run_command", return_value=dry_run), \
            patch.object(cba, "resolve_agent_string", return_value=None), \
            patch.object(cba, "resolve_skill_profile", return_value="fast"), \
            patch.object(cba, "launch_in_tmux", return_value=(None, None)) as tmux:
        yield tmux


@contextlib.contextmanager
def _qa_seams(dry_run=DEFAULT_QA):
    with patch.object(agent_utils, "resolve_agent_binary",
                      return_value=("claude", "claude", None)), \
            patch.object(hs.shutil, "which", return_value="/usr/bin/claude"), \
            patch.object(hs, "resolve_dry_run_command", return_value=dry_run), \
            patch.object(hs, "resolve_agent_string", return_value=None), \
            patch.object(hs, "resolve_skill_profile", return_value="fast"), \
            patch.object(hs, "launch_in_tmux", return_value=(None, None)) as tmux:
        yield tmux


def _history_screen():
    screen = MagicMock()
    screen._project_root = ROOT
    screen.query_one.return_value = SimpleNamespace(_nav_stack=["42"])
    screen.app._codeagent_argv = (
        lambda op, arg: CodeBrowserApp._codeagent_argv(
            SimpleNamespace(_project_root=ROOT), op, arg))
    return screen


WRAPPER = str(ROOT / ".aitask-scripts" / "aitask_codeagent.sh")


class ExplainBranchTests(unittest.TestCase):
    def test_run_dispatches_dialog_command(self):
        app = _browser_app()
        with _explain_seams():
            CodeBrowserApp.action_launch_agent(app)
            screen, callback = _pop_dialog(app.push_screen)
            self.assertEqual(screen.full_command, DEFAULT_EXPLAIN)
            screen.full_command = OVERRIDE
            callback("run")
        app.run_launch_command.assert_called_once_with(["sh", "-c", OVERRIDE])

    def test_tmux_branch_still_uses_dialog_command(self):
        app = _browser_app()
        with _explain_seams() as tmux:
            CodeBrowserApp.action_launch_agent(app)
            screen, callback = _pop_dialog(app.push_screen)
            screen.full_command = OVERRIDE
            callback(TMUX_CFG)
        tmux.assert_called_once_with(OVERRIDE, TMUX_CFG)
        app.run_launch_command.assert_not_called()

    def test_without_resolved_command_keeps_wrapper_argv(self):
        """Negative control: no dialog was shown, so there is nothing to honour."""
        app = _browser_app()
        with _explain_seams(dry_run=None):
            CodeBrowserApp.action_launch_agent(app)
        app.push_screen.assert_not_called()
        app.run_launch_command.assert_called_once_with(
            [WRAPPER, "invoke", "explain", "foo.py"])


class CreateBranchTests(unittest.TestCase):
    def test_run_dispatches_dialog_command_and_refreshes(self):
        app = _browser_app(viewer=_code_viewer(selected=(3, 9)))
        CodeBrowserApp.action_create_task(app)
        screen, callback = _pop_dialog(app.push_screen)
        screen.full_command = OVERRIDE
        callback("run")
        app.run_launch_command.assert_called_once_with(
            ["sh", "-c", OVERRIDE], refresh_explain=True)

    def test_tmux_branch_still_uses_dialog_command(self):
        app = _browser_app()
        with patch.object(cba, "launch_in_tmux", return_value=(None, None)) as tmux, \
                patch.object(cba, "_lookup_window_name", return_value=None):
            CodeBrowserApp.action_create_task(app)
            screen, callback = _pop_dialog(app.push_screen)
            screen.full_command = OVERRIDE
            callback(TMUX_CFG)
        tmux.assert_called_once_with(OVERRIDE, TMUX_CFG)
        app.run_launch_command.assert_not_called()


class QaBranchTests(unittest.TestCase):
    def test_run_dispatches_dialog_command(self):
        screen_host = _history_screen()
        with _qa_seams():
            HistoryScreen.action_launch_qa(screen_host)
            dialog, callback = _pop_dialog(screen_host.app.push_screen)
            self.assertEqual(dialog.full_command, DEFAULT_QA)
            dialog.full_command = OVERRIDE
            callback("run")
        screen_host.app.run_launch_command.assert_called_once_with(
            ["sh", "-c", OVERRIDE])

    def test_tmux_branch_still_uses_dialog_command(self):
        screen_host = _history_screen()
        with _qa_seams() as tmux:
            HistoryScreen.action_launch_qa(screen_host)
            dialog, callback = _pop_dialog(screen_host.app.push_screen)
            dialog.full_command = OVERRIDE
            callback(TMUX_CFG)
        tmux.assert_called_once_with(OVERRIDE, TMUX_CFG)
        screen_host.app.run_launch_command.assert_not_called()

    def test_without_resolved_command_keeps_wrapper_argv(self):
        screen_host = _history_screen()
        with _qa_seams(dry_run=None):
            HistoryScreen.action_launch_qa(screen_host)
        screen_host.app.push_screen.assert_not_called()
        screen_host.app.run_launch_command.assert_called_once_with(
            [WRAPPER, "invoke", "qa", "42"])


class DeadHelperRemovalTests(unittest.TestCase):
    """The per-branch rebuild workers must stay gone."""

    def test_per_branch_workers_are_removed(self):
        for owner, name in ((CodeBrowserApp, "_run_agent_command"),
                            (CodeBrowserApp, "_run_create_from_selection"),
                            (HistoryScreen, "_run_qa_command")):
            self.assertFalse(
                hasattr(owner, name),
                f"{owner.__name__}.{name} was re-added — route the branch "
                f"through CodeBrowserApp.run_launch_command instead")


class CreateDefaultCommandTests(unittest.TestCase):
    """The create dialog's DEFAULT command runs through a shell (tmux, and
    "run" via sh -c), so the script path must survive a root with spaces."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "My Project"
        scripts = self.root / ".aitask-scripts"
        scripts.mkdir(parents=True)
        self.marker = self.root / "marker"
        stub = scripts / "aitask_create.sh"
        stub.write_text(
            "#!/bin/sh\n"
            f": > '{self.marker}'\n"
            f"for a in \"$@\"; do printf '%s\\n' \"$a\" >> '{self.marker}'; done\n")
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)

    def tearDown(self):
        self._tmp.cleanup()

    def _run_default(self, app):
        CodeBrowserApp.action_create_task(app)
        screen, _ = _pop_dialog(app.push_screen)
        rc = os.spawnvp(os.P_WAIT, "sh", ["sh", "-c", screen.full_command])
        self.assertEqual(rc, 0, screen.full_command)
        self.assertTrue(self.marker.exists(), screen.full_command)
        return self.marker.read_text().splitlines()

    def test_default_command_with_selection(self):
        app = _browser_app(root=self.root, current_file="src/my file.py",
                           viewer=_code_viewer(selected=(3, 9)))
        self.assertEqual(self._run_default(app),
                         ["--file-ref", "src/my file.py:3-9"])

    def test_default_command_without_a_file(self):
        app = _browser_app(root=self.root, current_file=None)
        self.assertEqual(self._run_default(app), [])


class LaunchWorkerTests(unittest.TestCase):
    """Every path of the undecorated worker on a MagicMock app."""

    ARGV = ["sh", "-c", OVERRIDE]

    def _call(self, app, **kwargs):
        asyncio.run(CodeBrowserApp.run_launch_command.__wrapped__(
            app, self.ARGV, **kwargs))

    def _app(self):
        app = MagicMock()
        app._project_root = ROOT
        app.suspend = contextlib.nullcontext
        return app

    def test_terminal_path_spawns_in_project_root(self):
        app = self._app()
        with patch.object(cba, "_find_terminal", return_value="footerm"), \
                patch.object(cba, "spawn_in_terminal") as spawn, \
                patch.object(cba.subprocess, "call") as call:
            self._call(app, refresh_explain=True)
        spawn.assert_called_once_with("footerm", self.ARGV, cwd=str(ROOT))
        call.assert_not_called()
        app.action_refresh_explain.assert_not_called()
        app.notify.assert_not_called()

    def test_terminal_oserror_is_notified(self):
        app = self._app()
        with patch.object(cba, "_find_terminal", return_value="footerm"), \
                patch.object(cba, "spawn_in_terminal",
                             side_effect=FileNotFoundError("footerm")):
            self._call(app)
        app.notify.assert_called_once()
        self.assertEqual(app.notify.call_args.kwargs, {"severity": "error"})

    def test_inline_path_runs_and_refreshes_when_asked(self):
        app = self._app()
        with patch.object(cba, "_find_terminal", return_value=None), \
                patch.object(cba.subprocess, "call", return_value=0) as call:
            self._call(app, refresh_explain=True)
        call.assert_called_once_with(self.ARGV, cwd=str(ROOT))
        app.action_refresh_explain.assert_called_once_with()
        app.notify.assert_not_called()

    def test_inline_path_without_refresh(self):
        app = self._app()
        with patch.object(cba, "_find_terminal", return_value=None), \
                patch.object(cba.subprocess, "call", return_value=0):
            self._call(app)
        app.action_refresh_explain.assert_not_called()

    def test_inline_oserror_is_notified_without_refresh(self):
        app = self._app()
        with patch.object(cba, "_find_terminal", return_value=None), \
                patch.object(cba.subprocess, "call",
                             side_effect=FileNotFoundError("sh")):
            self._call(app, refresh_explain=True)
        app.notify.assert_called_once()
        app.action_refresh_explain.assert_not_called()

    def test_suspend_not_supported_is_notified(self):
        app = self._app()

        def no_suspend():
            raise SuspendNotSupported("nope")

        app.suspend = no_suspend
        with patch.object(cba, "_find_terminal", return_value=None), \
                patch.object(cba.subprocess, "call") as call:
            self._call(app)
        call.assert_not_called()
        app.notify.assert_called_once()
        self.assertIn("cannot suspend", app.notify.call_args.args[0])


class _LaunchHost(App):
    """Minimal real App borrowing the REAL worker (no codebrowser boot)."""

    run_launch_command = CodeBrowserApp.run_launch_command

    def __init__(self, root: Path):
        super().__init__()
        self._project_root = root
        self.refreshes = 0

    def action_refresh_explain(self) -> None:
        self.refreshes += 1

    # Mirrors _load_explain_data / _refresh_explain_data: exclusive, default group.
    @work(exclusive=True)
    async def annotation_blocker(self, release: asyncio.Event) -> None:
        await release.wait()


class LaunchWorkerLiveTests(unittest.TestCase):
    @staticmethod
    def _fake_driver(events: list, can_suspend: bool = True) -> MagicMock:
        driver = MagicMock()
        driver.can_suspend = can_suspend
        driver.no_automatic_restart = lambda: contextlib.nullcontext()
        driver.suspend_application_mode.side_effect = (
            lambda: events.append("suspend"))
        driver.resume_application_mode.side_effect = (
            lambda: events.append("resume"))
        return driver

    def _run_inline(self, call, *, can_suspend=True):
        """Drive the worker through the REAL App.suspend with a stand-in
        driver. ``events`` is one sequence shared by the driver, the inline
        call and notify, so ordering (resume BEFORE notify) is observable."""
        events: list[str] = []
        notices: list[tuple] = []
        result: dict = {}

        def recorded_call(argv, **kwargs):
            events.append("call")
            return call(argv, **kwargs)

        async def runner():
            app = _LaunchHost(ROOT)
            async with app.run_test() as pilot:
                def notify(message, **kwargs):
                    events.append("notify")
                    notices.append((message, kwargs.get("severity")))

                driver = self._fake_driver(events, can_suspend)
                with patch.object(app, "_driver", driver), \
                        patch.object(app, "notify", notify), \
                        patch.object(cba, "_find_terminal", return_value=None), \
                        patch.object(cba.subprocess, "call", recorded_call):
                    worker = app.run_launch_command(["sh", "-c", OVERRIDE],
                                                    refresh_explain=True)
                    await worker.wait()
                await pilot.pause()
                result.update(running=app.is_running, refreshes=app.refreshes)

        asyncio.run(runner())
        return events, notices, result

    def test_inline_oserror_resumes_the_terminal_then_notifies(self):
        def call(argv, **kwargs):
            raise FileNotFoundError(2, "No such file or directory", "sh")

        events, notices, result = self._run_inline(call)
        self.assertEqual(events, ["suspend", "call", "resume", "notify"])
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0][1], "error")
        self.assertIn("Could not launch command", notices[0][0])
        self.assertTrue(result["running"])
        self.assertEqual(result["refreshes"], 0)

    def test_inline_success_resumes_then_refreshes(self):
        events, notices, result = self._run_inline(lambda argv, **kw: 0)
        self.assertEqual(events, ["suspend", "call", "resume"])
        self.assertEqual(notices, [])
        self.assertEqual(result["refreshes"], 1)

    def test_inline_without_suspend_support_is_contained(self):
        def call(argv, **kwargs):
            raise AssertionError("must not run without a suspended terminal")

        events, notices, result = self._run_inline(call, can_suspend=False)
        self.assertEqual(events, ["notify"])
        self.assertIn("cannot suspend", notices[0][0])
        self.assertTrue(result["running"])

    def test_launch_does_not_cancel_annotation_workers(self):
        states: dict = {}

        async def runner():
            app = _LaunchHost(ROOT)
            async with app.run_test() as pilot:
                release = asyncio.Event()
                blocker = app.annotation_blocker(release)
                await pilot.pause()
                with patch.object(cba, "_find_terminal", return_value="footerm"), \
                        patch.object(cba, "spawn_in_terminal") as spawn:
                    launch = app.run_launch_command(["sh", "-c", OVERRIDE])
                    await launch.wait()
                await pilot.pause()
                states["spawned"] = spawn.call_count
                states["after_launch"] = blocker.state
                release.set()
                if blocker.state != WorkerState.CANCELLED:
                    await blocker.wait()
                states["final"] = blocker.state

        asyncio.run(runner())
        self.assertEqual(states["spawned"], 1)
        self.assertNotEqual(states["after_launch"], WorkerState.CANCELLED)
        self.assertEqual(states["final"], WorkerState.SUCCESS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
