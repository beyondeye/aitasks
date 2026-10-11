"""Board edit (``run_editor``) is contained like codebrowser's ``E`` (t1943).

``KanbanApp.run_editor`` suspends the board and runs ``$EDITOR`` on a task or
plan file. It must match the containment t1936 gave codebrowser's
``action_open_in_editor``:

- its own worker group, so editing does not cancel the board's exclusive
  default-group workers (``_run_sync``, ``run_aitask_pick``, …);
- ``$EDITOR`` resolves through ``resolve_editor_argv``: ``code -w`` is argv
  ``["code", "-w", ...]``, a value naming a whole executable stays one argv[0];
- an ``OSError`` from the launch is caught INSIDE the real ``App.suspend``
  (which resumes the driver with no ``finally``, Textual 8.2.7), so the
  terminal is resumed before the error is notified, the board keeps running,
  and the task reload is skipped;
- ``SuspendNotSupported`` is contained.

Every test boots a real Textual app that borrows the REAL decorated worker —
from the ``board_fixture``-bound board module, never the live tree — and
drives it through the real ``App.suspend`` with a stand-in driver; one shared
``events`` list records driver, launch, notify and reload calls in order.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402
from textual import work  # noqa: E402
from textual.app import App  # noqa: E402
from textual.worker import WorkerState  # noqa: E402

FILE = Path("/tmp/board-project/aitasks/t42_foo.md")


class _EditorHostBase(App):
    """Minimal real App; ``_host_class`` adds the REAL worker (no board boot)."""

    def __init__(self, events: list):
        super().__init__()
        self.events = events
        self.refocused: list[str] = []
        self.manager = MagicMock()
        self.manager.load_tasks.side_effect = lambda: events.append("load")

    def refresh_board(self, refocus_filename=None, **kwargs) -> None:
        self.refocused.append(refocus_filename)

    # Mirrors run_aitask_pick / _run_interactive_sync_shared: exclusive,
    # default group, async.
    @work(exclusive=True)
    async def default_group_blocker(self, release: asyncio.Event) -> None:
        await release.wait()

    # Mirrors _run_sync: exclusive, default group, THREAD worker blocked in a
    # subprocess (here: an Event) that cancellation never interrupts.
    @work(exclusive=True, thread=True)
    def threaded_sync_blocker(self, started: threading.Event,
                              release: threading.Event,
                              finished: threading.Event) -> None:
        started.set()
        try:
            release.wait(timeout=10)
        finally:
            # Set by the thread itself on its way out — the only signal that
            # says it is no longer running (the release flag says only that
            # the test asked it to stop).
            finished.set()


def _host_class(ab):
    """Host borrowing ``run_editor`` from the fixture-bound board module ``ab``."""
    return type("_EditorHost", (_EditorHostBase,),
                {"run_editor": ab.KanbanApp.run_editor})


def _fake_driver(events: list, can_suspend: bool = True) -> MagicMock:
    driver = MagicMock()
    driver.can_suspend = can_suspend
    driver.no_automatic_restart = lambda: contextlib.nullcontext()
    driver.suspend_application_mode.side_effect = lambda: events.append("suspend")
    driver.resume_application_mode.side_effect = lambda: events.append("resume")
    return driver


def _run_editor(ab, env_editor, call=lambda argv: 0, *, can_suspend=True,
                blocker=None):
    """Run the editor worker; return (events, argvs, notices, result).

    ``blocker`` is ``None``, ``"async"`` (default-group async worker),
    ``"thread"`` (default-group thread worker shaped like ``_run_sync``, still
    blocked when the editor launches) or ``"thread_finished"`` (the same
    worker, released and finished before the editor launches — the negative
    control for the overlap probe).
    """
    events: list[str] = []
    argvs: list[list[str]] = []
    notices: list[tuple] = []
    result: dict = {}
    thread_release = threading.Event()
    thread_finished = threading.Event()
    threaded = blocker in ("thread", "thread_finished")

    def recorded_call(argv, **kwargs):
        events.append("call")
        argvs.append(list(argv))
        if threaded:
            # Read the thread's own exit signal at launch time.
            result["thread_running_during_call"] = not thread_finished.is_set()
        return call(argv)

    env = {k: v for k, v in os.environ.items() if k != "EDITOR"}
    if env_editor is not None:
        env["EDITOR"] = env_editor

    async def runner():
        app = _host_class(ab)(events)
        async with app.run_test() as pilot:
            def notify(message, **kwargs):
                events.append("notify")
                notices.append((message, kwargs.get("severity")))

            worker = None
            release = None
            if blocker == "async":
                release = asyncio.Event()
                worker = app.default_group_blocker(release)
                await pilot.pause()
            elif threaded:
                started = threading.Event()
                worker = app.threaded_sync_blocker(
                    started, thread_release, thread_finished)
                result["thread_started"] = await asyncio.to_thread(
                    started.wait, 5)
                if blocker == "thread_finished":
                    thread_release.set()
                    await worker.wait()
            driver = _fake_driver(events, can_suspend)
            with patch.dict(os.environ, env, clear=True), \
                    patch.object(app, "_driver", driver), \
                    patch.object(app, "notify", notify), \
                    patch.object(ab.subprocess, "call", recorded_call):
                editor = app.run_editor(str(FILE))
                await editor.wait()
            await pilot.pause()
            result.update(running=app.is_running, refocused=list(app.refocused))
            if worker is not None:
                result["blocker_after_editor"] = worker.state
                if blocker == "async":
                    release.set()
                else:
                    thread_release.set()
                if worker.state != WorkerState.CANCELLED:
                    await worker.wait()
                result["blocker_final"] = worker.state

    asyncio.run(runner())
    return events, argvs, notices, result


@unittest.skipIf(sys.platform == "win32", "shlex-split $EDITOR is POSIX-only")
class RunEditorTests(bf.FixtureBoardTestBase, unittest.TestCase):
    def test_success_reloads_and_refocuses(self):
        events, argvs, notices, result = _run_editor(self.ab, "vim")
        self.assertEqual(argvs, [["vim", str(FILE)]])
        self.assertEqual(events, ["suspend", "call", "resume", "load"])
        self.assertEqual(notices, [])
        self.assertEqual(result["refocused"], [FILE.name])

    def test_editor_with_arguments_is_split(self):
        _, argvs, _, _ = _run_editor(self.ab, "code -w")
        self.assertEqual(argvs, [["code", "-w", str(FILE)]])

    def test_quoted_editor_path_stays_one_word(self):
        _, argvs, _, _ = _run_editor(self.ab, "'/opt/my editor/bin/ed' --wait")
        self.assertEqual(argvs, [["/opt/my editor/bin/ed", "--wait", str(FILE)]])

    def test_unquoted_executable_path_with_spaces_stays_whole(self):
        with tempfile.TemporaryDirectory() as tmp:
            editor = Path(tmp) / "my editor" / "ed"
            editor.parent.mkdir()
            editor.write_text("#!/bin/sh\nexit 0\n")
            editor.chmod(0o755)
            _, argvs, notices, _ = _run_editor(self.ab, str(editor))
        self.assertEqual(argvs, [[str(editor), str(FILE)]])
        self.assertEqual(notices, [])

    def test_unset_editor_defaults_to_nano(self):
        _, argvs, _, _ = _run_editor(self.ab, None)
        self.assertEqual(argvs, [["nano", str(FILE)]])

    def test_blank_editor_defaults_to_nano(self):
        _, argvs, _, _ = _run_editor(self.ab, "   ")
        self.assertEqual(argvs, [["nano", str(FILE)]])

    def test_missing_editor_resumes_the_terminal_then_notifies(self):
        def call(argv):
            raise FileNotFoundError(2, "No such file or directory", argv[0])

        events, _, notices, result = _run_editor(self.ab, "no-such-editor", call)
        self.assertEqual(events, ["suspend", "call", "resume", "notify"])
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0][1], "error")
        self.assertIn("Could not launch editor", notices[0][0])
        self.assertTrue(result["running"])
        self.assertEqual(result["refocused"], [])

    def test_without_suspend_support_is_contained(self):
        def call(argv):
            raise AssertionError("must not run without a suspended terminal")

        events, argvs, notices, result = _run_editor(self.ab, "vim", call,
                                                    can_suspend=False)
        self.assertEqual(events, ["notify"])
        self.assertEqual(argvs, [])
        self.assertIn("cannot suspend", notices[0][0])
        self.assertTrue(result["running"])
        self.assertEqual(result["refocused"], [])

    def test_malformed_editor_is_notified_without_suspending(self):
        events, argvs, notices, result = _run_editor(self.ab, 'vim "unterminated')
        self.assertEqual(events, ["notify"])
        self.assertEqual(argvs, [])
        self.assertEqual(notices[0][1], "error")
        self.assertIn("Invalid $EDITOR", notices[0][0])
        self.assertTrue(result["running"])

    def test_editor_does_not_cancel_default_group_workers(self):
        _, argvs, _, result = _run_editor(self.ab, "vim", blocker="async")
        self.assertEqual(argvs, [["vim", str(FILE)]])
        self.assertNotEqual(result["blocker_after_editor"], WorkerState.CANCELLED)
        self.assertEqual(result["blocker_final"], WorkerState.SUCCESS)

    def test_editor_overlaps_an_in_flight_threaded_sync(self):
        # Pins today's behaviour, not a safety claim: a `_run_sync`-shaped
        # thread worker already in flight keeps running while the editor is
        # open (cancellation never stopped its thread/subprocess, before or
        # after t1943); the editor neither waits for it nor cancels it.
        _, argvs, _, result = _run_editor(self.ab, "vim", blocker="thread")
        self.assertTrue(result["thread_started"])
        self.assertEqual(argvs, [["vim", str(FILE)]])
        self.assertTrue(result["thread_running_during_call"])
        self.assertNotEqual(result["blocker_after_editor"], WorkerState.CANCELLED)
        self.assertEqual(result["blocker_final"], WorkerState.SUCCESS)


    def test_overlap_probe_sees_a_thread_that_finished_first(self):
        # Negative control for the probe above: when the sync stand-in has
        # already finished before the editor launches, the probe must say so.
        _, argvs, _, result = _run_editor(self.ab, "vim",
                                          blocker="thread_finished")
        self.assertTrue(result["thread_started"])
        self.assertEqual(argvs, [["vim", str(FILE)]])
        self.assertFalse(result["thread_running_during_call"])
        self.assertEqual(result["blocker_final"], WorkerState.SUCCESS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
