"""Codebrowser ``E`` (open in $EDITOR) is contained like the launch worker (t1936).

``CodeBrowserApp.action_open_in_editor`` suspends the TUI and runs ``$EDITOR``.
It must match the containment t1929 gave ``run_launch_command``:

- its own worker group, so pressing ``E`` does not cancel the exclusive
  default-group annotation workers (``_load_explain_data`` /
  ``_refresh_explain_data``);
- ``$EDITOR`` is shlex-split, so ``code -w`` is argv ``["code", "-w", ...]`` —
  but a value that already names a whole executable (an unquoted path with
  spaces) still launches as one argv[0], as it did before;
- an ``OSError`` from the launch is caught INSIDE the real ``App.suspend``
  (which resumes the driver with no ``finally``, Textual 8.2.7), so the
  terminal is resumed before the error is notified and the app keeps running;
- ``SuspendNotSupported`` is contained.

Every test boots a real Textual app that borrows the REAL decorated worker and
drives it through the real ``App.suspend`` with a stand-in driver; one shared
``events`` list records driver, launch and notify calls in order.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "codebrowser"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import codebrowser_app as cba  # noqa: E402
from codebrowser_app import CodeBrowserApp  # noqa: E402
from textual import work  # noqa: E402
from textual.app import App  # noqa: E402
from textual.worker import WorkerState  # noqa: E402

FILE = Path("/tmp/cb-project/src/foo.py")


class _EditorHost(App):
    """Minimal real App borrowing the REAL worker (no codebrowser boot)."""

    action_open_in_editor = CodeBrowserApp.action_open_in_editor

    def __init__(self, current_file: Path | None = FILE):
        super().__init__()
        self._current_file_path = current_file
        self.explain_manager = object()
        self.refreshed: list[Path] = []

    def _refresh_explain_data(self, file_path: Path) -> None:
        self.refreshed.append(file_path)

    # Mirrors _load_explain_data / _refresh_explain_data: exclusive, default group.
    @work(exclusive=True)
    async def annotation_blocker(self, release: asyncio.Event) -> None:
        await release.wait()


def _fake_driver(events: list, can_suspend: bool = True) -> MagicMock:
    driver = MagicMock()
    driver.can_suspend = can_suspend
    driver.no_automatic_restart = lambda: contextlib.nullcontext()
    driver.suspend_application_mode.side_effect = lambda: events.append("suspend")
    driver.resume_application_mode.side_effect = lambda: events.append("resume")
    return driver


def _run_editor(env_editor, call=lambda argv: 0, *, can_suspend=True,
                current_file=FILE, with_blocker=False):
    """Run the editor worker; return (events, argvs, notices, result)."""
    events: list[str] = []
    argvs: list[list[str]] = []
    notices: list[tuple] = []
    result: dict = {}

    def recorded_call(argv, **kwargs):
        events.append("call")
        argvs.append(list(argv))
        return call(argv)

    env = {k: v for k, v in os.environ.items() if k != "EDITOR"}
    if env_editor is not None:
        env["EDITOR"] = env_editor

    async def runner():
        app = _EditorHost(current_file)
        async with app.run_test() as pilot:
            def notify(message, **kwargs):
                events.append("notify")
                notices.append((message, kwargs.get("severity")))

            blocker = release = None
            if with_blocker:
                release = asyncio.Event()
                blocker = app.annotation_blocker(release)
                await pilot.pause()
            driver = _fake_driver(events, can_suspend)
            with patch.dict(os.environ, env, clear=True), \
                    patch.object(app, "_driver", driver), \
                    patch.object(app, "notify", notify), \
                    patch.object(cba.subprocess, "call", recorded_call):
                worker = app.action_open_in_editor()
                await worker.wait()
            await pilot.pause()
            result.update(running=app.is_running, refreshed=list(app.refreshed))
            if with_blocker:
                result["blocker_after_editor"] = blocker.state
                release.set()
                if blocker.state != WorkerState.CANCELLED:
                    await blocker.wait()
                result["blocker_final"] = blocker.state

    asyncio.run(runner())
    return events, argvs, notices, result


@unittest.skipIf(sys.platform == "win32", "shlex-split $EDITOR is POSIX-only")
class OpenInEditorTests(unittest.TestCase):
    def test_editor_with_arguments_is_split(self):
        events, argvs, notices, result = _run_editor("code -w")
        self.assertEqual(argvs, [["code", "-w", str(FILE)]])
        self.assertEqual(events, ["suspend", "call", "resume"])
        self.assertEqual(notices, [])
        self.assertEqual(result["refreshed"], [FILE])

    def test_quoted_editor_path_stays_one_word(self):
        _, argvs, _, _ = _run_editor("'/opt/my editor/bin/ed' --wait")
        self.assertEqual(argvs, [["/opt/my editor/bin/ed", "--wait", str(FILE)]])

    def test_unquoted_executable_path_with_spaces_stays_whole(self):
        # A real executable: the whole-value check must see it on disk.
        with tempfile.TemporaryDirectory() as tmp:
            editor = Path(tmp) / "my editor" / "ed"
            editor.parent.mkdir()
            editor.write_text("#!/bin/sh\nexit 0\n")
            editor.chmod(0o755)
            events, argvs, notices, _ = _run_editor(str(editor))
        self.assertEqual(argvs, [[str(editor), str(FILE)]])
        self.assertEqual(events, ["suspend", "call", "resume"])
        self.assertEqual(notices, [])

    def test_unset_editor_defaults_to_nano(self):
        _, argvs, _, _ = _run_editor(None)
        self.assertEqual(argvs, [["nano", str(FILE)]])

    def test_blank_editor_defaults_to_nano(self):
        _, argvs, _, _ = _run_editor("   ")
        self.assertEqual(argvs, [["nano", str(FILE)]])

    def test_missing_editor_resumes_the_terminal_then_notifies(self):
        def call(argv):
            raise FileNotFoundError(2, "No such file or directory", argv[0])

        events, _, notices, result = _run_editor("no-such-editor", call)
        self.assertEqual(events, ["suspend", "call", "resume", "notify"])
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0][1], "error")
        self.assertIn("Could not launch editor", notices[0][0])
        self.assertTrue(result["running"])
        self.assertEqual(result["refreshed"], [])

    def test_without_suspend_support_is_contained(self):
        def call(argv):
            raise AssertionError("must not run without a suspended terminal")

        events, argvs, notices, result = _run_editor("vim", call,
                                                     can_suspend=False)
        self.assertEqual(events, ["notify"])
        self.assertEqual(argvs, [])
        self.assertIn("cannot suspend", notices[0][0])
        self.assertTrue(result["running"])
        self.assertEqual(result["refreshed"], [])

    def test_malformed_editor_is_notified_without_suspending(self):
        events, argvs, notices, result = _run_editor('vim "unterminated')
        self.assertEqual(events, ["notify"])
        self.assertEqual(argvs, [])
        self.assertEqual(notices[0][1], "error")
        self.assertIn("Invalid $EDITOR", notices[0][0])
        self.assertTrue(result["running"])

    def test_no_file_selected_warns_without_launching(self):
        events, argvs, notices, _ = _run_editor("vim", current_file=None)
        self.assertEqual(events, ["notify"])
        self.assertEqual(argvs, [])
        self.assertEqual(notices, [("No file selected", "warning")])

    def test_editor_does_not_cancel_annotation_workers(self):
        _, argvs, _, result = _run_editor("vim", with_blocker=True)
        self.assertEqual(argvs, [["vim", str(FILE)]])
        self.assertNotEqual(result["blocker_after_editor"], WorkerState.CANCELLED)
        self.assertEqual(result["blocker_final"], WorkerState.SUCCESS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
