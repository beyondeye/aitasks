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
- ``SuspendNotSupported`` is contained;
- it never overlaps a sync (t1947): an edit during an in-flight ``_run_sync``
  is refused, a sync started mid-edit waits for the editor, and a timed-out
  sync whose session could not be proven stopped refuses edits and syncs
  until the probe proves it gone.

Every test boots a real Textual app that borrows the REAL decorated workers —
from the ``board_fixture``-bound board module, never the live tree — and
drives them through the real ``App.suspend`` with a stand-in driver and a
stand-in ``run_sync_batch``; one shared ``events`` list records driver,
launch, notify and reload calls in order.
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
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
from sync_action_runner import (  # noqa: E402
    STATUS_NOTHING, STATUS_TIMEOUT, SyncResult,
)

FILE = Path("/tmp/board-project/aitasks/t42_foo.md")


class _ProbeLock:
    """A real lock that reports every BLOCKING acquire attempt.

    ``attempting`` is the handshake proving a sync thread reached the lock —
    without it, "the sync has not run yet" could just mean "not scheduled
    yet". The editor's non-blocking acquire never sets it.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.attempting = threading.Event()

    def acquire(self, blocking=True, timeout=-1):
        if blocking:
            self.attempting.set()
        return self._lock.acquire(blocking, timeout)

    def release(self):
        self._lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()

    def is_free(self) -> bool:
        if self._lock.acquire(blocking=False):
            self._lock.release()
            return True
        return False


class _SyncStandIn:
    """``run_sync_batch`` stand-in: blocks until released, returns ``result``."""

    def __init__(self, result: SyncResult | None = None):
        self.result = result or SyncResult(status=STATUS_NOTHING)
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def __call__(self, *args, **kwargs) -> SyncResult:
        self.calls += 1
        self.entered.set()
        self.release.wait(timeout=10)
        return self.result


class _EditorHostBase(App):
    """Minimal real App; ``_host_class`` adds the REAL workers (no board boot)."""

    def __init__(self, events: list):
        super().__init__()
        self.events = events
        self.refocused: list[str] = []
        self.manager = MagicMock()
        self.manager.load_tasks.side_effect = lambda: events.append("load")
        # What run_editor / _run_sync / _stray_sync_blocks read.
        self._sync_edit_lock = _ProbeLock()
        self._stray_sync_session = None
        self.base_filter = "all"
        self.active_trail_handle = None

    def refresh_board(self, refocus_filename=None, **kwargs) -> None:
        if refocus_filename is not None:
            self.refocused.append(refocus_filename)

    # Mirrors run_aitask_pick / _run_interactive_sync_shared: exclusive,
    # default group, async.
    @work(exclusive=True)
    async def default_group_blocker(self, release: asyncio.Event) -> None:
        await release.wait()



def _host_class(ab):
    """Host borrowing the real editor/sync workers from the bound module ``ab``."""
    return type("_EditorHost", (_EditorHostBase,), {
        "run_editor": ab.KanbanApp.run_editor,
        "_run_sync": ab.KanbanApp._run_sync,
        "_stray_sync_blocks": ab.KanbanApp._stray_sync_blocks,
    })


def _fake_driver(events: list, can_suspend: bool = True) -> MagicMock:
    driver = MagicMock()
    driver.can_suspend = can_suspend
    driver.no_automatic_restart = lambda: contextlib.nullcontext()
    driver.suspend_application_mode.side_effect = lambda: events.append("suspend")
    driver.resume_application_mode.side_effect = lambda: events.append("resume")
    return driver


def _run_editor(ab, env_editor, call=lambda argv: 0, *, can_suspend=True,
                blocker=None, during_call=None):
    """Run the editor worker; return (events, argvs, notices, result).

    ``blocker`` is ``None``, ``"async"`` (default-group async worker),
    ``"sync"`` (the REAL ``_run_sync``, still blocked in the stand-in
    ``run_sync_batch`` when the editor runs) or ``"sync_finished"`` (the same
    sync, released and finished before the editor runs — the negative
    control). ``during_call(app, sync, result)`` runs inside the stand-in
    ``subprocess.call``, i.e. while the editor is open and the event loop is
    blocked; it may return a thread to join (off the loop) afterwards.

    ``events`` is the snapshot taken when the editor worker ended, so a
    released sync's own reload never leaks into the editor's sequence.
    """
    events: list[str] = []
    argvs: list[list[str]] = []
    notices: list[tuple] = []
    result: dict = {}
    sync = _SyncStandIn()
    holder: dict = {}

    def recorded_call(argv, **kwargs):
        events.append("call")
        argvs.append(list(argv))
        if during_call is not None:
            holder["thread"] = during_call(holder["app"], sync, result)
        return call(argv)

    env = {k: v for k, v in os.environ.items() if k != "EDITOR"}
    if env_editor is not None:
        env["EDITOR"] = env_editor

    async def runner():
        app = _host_class(ab)(events)
        holder["app"] = app

        def notify(message, **kwargs):
            events.append("notify")
            notices.append((message, kwargs.get("severity")))

        async with app.run_test() as pilot:
            with patch.object(app, "notify", notify), \
                    patch.object(ab, "run_sync_batch", sync):
                worker = None
                release = None
                if blocker == "async":
                    release = asyncio.Event()
                    worker = app.default_group_blocker(release)
                    await pilot.pause()
                elif blocker in ("sync", "sync_finished"):
                    worker = app._run_sync(show_notification=False)
                    result["sync_entered"] = await asyncio.to_thread(
                        sync.entered.wait, 5)
                    if blocker == "sync_finished":
                        sync.release.set()
                        await worker.wait()
                        await pilot.pause()
                    events.clear()
                driver = _fake_driver(events, can_suspend)
                with patch.dict(os.environ, env, clear=True), \
                        patch.object(app, "_driver", driver), \
                        patch.object(ab.subprocess, "call", recorded_call):
                    editor = app.run_editor(str(FILE))
                    await editor.wait()
                await pilot.pause()
                result["events"] = list(events)
                result.update(running=app.is_running,
                              refocused=list(app.refocused))
                thread = holder.get("thread")
                if thread is not None:
                    # Off the loop: the real sync body blocks on
                    # call_from_thread, which needs the loop running.
                    result["entered_after"] = await asyncio.to_thread(
                        sync.entered.wait, 5)
                    await asyncio.to_thread(thread.join, 5)
                    result["thread_alive"] = thread.is_alive()
                if worker is not None:
                    result["blocker_after_editor"] = worker.state
                    if blocker == "async":
                        release.set()
                    else:
                        sync.release.set()
                    if worker.state != WorkerState.CANCELLED:
                        await worker.wait()
                    result["blocker_final"] = worker.state
                await pilot.pause()
                result["lock_free_after"] = app._sync_edit_lock.is_free()

    asyncio.run(runner())
    return result["events"], argvs, notices, result


def _start_raw_sync(app, sync, result):
    """``during_call`` hook: a sync started mid-edit from a plain thread.

    The ``_do_rename_task`` shape — a thread calling into ``_run_sync`` — run
    on the undecorated body so it is not a Textual worker. The handshake
    (``attempting``) proves the thread reached the lock before exclusion is
    checked.
    """
    raw = type(app)._run_sync.__wrapped__
    ctx = contextvars.copy_context()  # the body uses self.app
    thread = threading.Thread(target=ctx.run, args=(raw, app),
                              kwargs={"show_notification": False})
    thread.start()
    result["attempted"] = app._sync_edit_lock.attempting.wait(5)
    result["entered_while_open"] = sync.entered.wait(0.3)
    sync.release.set()  # it returns at once once it gets the lock
    return thread


def _run_stray_sequence(ab, stray: SyncResult) -> dict:
    """Timed-out stray sync → refused edit and sync → probe clears → edit runs."""
    events: list[str] = []
    notices: list[tuple] = []
    out: dict = {}
    sync = _SyncStandIn(stray)
    sync.release.set()
    probe = {"running": True}
    env = {k: v for k, v in os.environ.items() if k != "EDITOR"}
    env["EDITOR"] = "vim"

    def recorded_call(argv, **kwargs):
        events.append("call")
        return 0

    async def runner():
        app = _host_class(ab)(events)

        def notify(message, **kwargs):
            events.append("notify")
            notices.append((message, kwargs.get("severity")))

        async def edit() -> list[str]:
            events.clear()
            with patch.dict(os.environ, env, clear=True), \
                    patch.object(app, "_driver", _fake_driver(events)), \
                    patch.object(ab.subprocess, "call", recorded_call):
                await app.run_editor(str(FILE)).wait()
            await pilot.pause()
            return list(events)

        async with app.run_test() as pilot:
            with patch.object(app, "notify", notify), \
                    patch.object(ab, "run_sync_batch", sync), \
                    patch.object(ab, "sync_session_running",
                                 lambda sid: probe["running"]):
                await app._run_sync(show_notification=False).wait()
                await pilot.pause()
                out["recorded"] = app._stray_sync_session
                out["timeout_notices"] = list(notices)

                notices.clear()
                out["refused_events"] = await edit()
                out["refused_notices"] = list(notices)

                notices.clear()
                await app._run_sync(show_notification=False).wait()
                await pilot.pause()
                out["sync_calls_after_skip"] = sync.calls
                out["skip_notices"] = list(notices)

                probe["running"] = False
                out["recovered_events"] = await edit()
                out["final_state"] = app._stray_sync_session
                out["lock_free_after"] = app._sync_edit_lock.is_free()

    asyncio.run(runner())
    return out


@unittest.skipIf(sys.platform == "win32", "shlex-split $EDITOR is POSIX-only")
class RunEditorTests(bf.FixtureBoardTestBase, unittest.TestCase):
    def test_success_reloads_and_refocuses(self):
        events, argvs, notices, result = _run_editor(self.ab, "vim")
        self.assertEqual(argvs, [["vim", str(FILE)]])
        self.assertEqual(events, ["suspend", "call", "resume", "load"])
        self.assertEqual(notices, [])
        self.assertEqual(result["refocused"], [FILE.name])
        self.assertTrue(result["lock_free_after"])

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
        self.assertTrue(result["lock_free_after"])

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
        self.assertTrue(result["lock_free_after"])

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

    def test_editor_refuses_while_a_sync_is_in_flight(self):
        # A sync already running (e.g. the silent auto-sync) would pull or
        # commit under the open file; worker state cannot see it, the lock can.
        events, argvs, notices, result = _run_editor(self.ab, "vim",
                                                     blocker="sync")
        self.assertTrue(result["sync_entered"])
        self.assertEqual(argvs, [])
        self.assertEqual(events, ["notify"])
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0][1], "warning")
        self.assertIn("Sync in progress", notices[0][0])
        self.assertEqual(result["refocused"], [])
        self.assertNotEqual(result["blocker_after_editor"], WorkerState.CANCELLED)
        self.assertEqual(result["blocker_final"], WorkerState.SUCCESS)
        self.assertTrue(result["lock_free_after"])

    def test_editor_runs_once_the_sync_has_finished(self):
        # Negative control: a finished sync leaves nothing to refuse.
        events, argvs, notices, result = _run_editor(self.ab, "vim",
                                                     blocker="sync_finished")
        self.assertTrue(result["sync_entered"])
        self.assertEqual(argvs, [["vim", str(FILE)]])
        self.assertEqual(events, ["suspend", "call", "resume", "load"])
        self.assertEqual(notices, [])
        self.assertTrue(result["lock_free_after"])

    def test_sync_started_mid_edit_waits_for_the_editor(self):
        _, argvs, _, result = _run_editor(self.ab, "vim",
                                          during_call=_start_raw_sync)
        self.assertEqual(argvs, [["vim", str(FILE)]])
        self.assertTrue(result["attempted"], "sync thread never reached the lock")
        self.assertFalse(result["entered_while_open"],
                         "sync ran while the editor was open")
        self.assertTrue(result["entered_after"])
        self.assertFalse(result["thread_alive"])
        self.assertTrue(result["lock_free_after"])

    def test_stray_timeout_refuses_edit_and_sync_until_proven_stopped(self):
        stray = SyncResult(
            status=STATUS_TIMEOUT, stray_session=4242,
            error_message="sync timed out after 30s; its processes could not "
                          "be confirmed stopped (session 4242)")
        out = _run_stray_sequence(self.ab, stray)
        # 1. The timed-out sync is announced even though show_notification
        #    was False, and its session is recorded.
        self.assertEqual(out["recorded"], 4242)
        self.assertEqual(out["timeout_notices"][0][1], "error")
        self.assertIn("session 4242", out["timeout_notices"][0][0])
        # 2. While the probe says it runs: the edit is refused without
        #    suspending, and the next sync never reaches run_sync_batch.
        self.assertEqual(out["refused_events"], ["notify"])
        self.assertEqual(out["refused_notices"][0][1], "error")
        self.assertIn("edit refused", out["refused_notices"][0][0])
        self.assertEqual(out["sync_calls_after_skip"], 1)
        self.assertIn("Sync skipped", out["skip_notices"][0][0])
        # 3. Once the probe proves it gone, the edit runs and the state clears.
        self.assertEqual(out["recovered_events"],
                         ["suspend", "call", "resume", "load"])
        self.assertIsNone(out["final_state"])
        self.assertTrue(out["lock_free_after"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
