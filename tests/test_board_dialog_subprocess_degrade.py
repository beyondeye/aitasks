"""Board dialog subprocess handlers degrade on any environment failure (t1314).

`TaskDetailScreen.revert_task`, `_do_lock` and `_do_unlock` caught only
`(subprocess.TimeoutExpired, FileNotFoundError)` while the module's other ten
`subprocess.run` call sites also catch `OSError`. A `PermissionError` — or any
other `OSError` — therefore propagated out of a user-triggered dialog handler.
For the two `@work(thread=True)` workers that is the worse failure: the
exception escapes the worker thread *before* the `LoadingOverlay` pop, so the
modal spinner stays up and the board appears hung.

t1302 fixed the same defect class on the refresh path
(`test_board_refresh_degrade.py`); this suite drives the dialog handlers with
the **same** parametrized exception set so the two boundaries cannot silently
re-diverge.

Two distinct promises are pinned, because the fix has two halves:

1. The widened tuple — every failure in `_FAILURES` degrades to a notification.
2. The overlay cleanup is *structural*, not tuple-dependent: the pop lives in a
   `finally` scoped to the `subprocess.run` call. `test_*_overlay_backstop`
   injects a `RuntimeError` — deliberately NOT in the caught tuple — and pins
   that the overlay still comes off while the exception propagates. That case
   fails under a tuple-only fix, so it discriminates half 2 from half 1.

`NormalOutcomeTests` guards the other direction. The fix moves the
result-handling block out of the immediate `try` body into the *outer* `try`, so
a mis-scoped inner `try` or a mis-indented `if result.returncode == 0:` could
strand an overlay, skip a dismissal, or change the error text while every
injected-exception test above still passes. Those controls inject nothing; they
pin the exact dispatch of all five normal outcomes — including the ordering
constraint (pop BEFORE the `ResetTaskConfirmScreen` push) that a body-wide
`finally` would break.

The real classes are exercised — a real `Task`, a real `TaskDetailScreen`, and
the workers' real bodies reached through `__wrapped__` (Textual's `@work`
applies `functools.wraps`) — never a replica, so an absence here is a real
absence in production code.

Run: python3 tests/test_board_dialog_subprocess_degrade.py -v
"""

from __future__ import annotations

import errno
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (
    REPO_ROOT / ".aitask-scripts",
    REPO_ROOT / ".aitask-scripts" / "board",
    REPO_ROOT / ".aitask-scripts" / "lib",
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# The full boundary all three handlers promise — identical to the set
# test_board_refresh_degrade.py drives, so the dialog and refresh handlers stay
# pinned to one boundary. TimeoutExpired is a SubprocessError, not an OSError;
# PermissionError/FileNotFoundError are OSError subclasses; the bare OSError
# pins the base class rather than only the two subclasses that were listed.
_FAILURES = {
    "permission_error": PermissionError(errno.EACCES, "permission denied"),
    "base_oserror": OSError(errno.EMFILE, "too many open files"),
    "file_not_found": FileNotFoundError(errno.ENOENT, "no such file"),
    "timeout": subprocess.TimeoutExpired(cmd=["git"], timeout=10),
}

# Not in any handler's caught tuple: pins the `finally`, not the tuple.
_UNANTICIPATED = RuntimeError("unanticipated failure")

TASK_ID = "42"
_READY = "---\nstatus: Ready\n---\nbody\n"
_IMPLEMENTING = "---\nstatus: Implementing\nassigned_to: someone@example.invalid\n---\nbody\n"


class DialogSubprocessTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig_cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        import aitask_board as ab  # noqa: E402

        cls.ab = ab

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)

    def _screen(self, raw=_READY):
        """A real TaskDetailScreen over a real Task (no disk I/O, no app)."""
        task = self.ab.Task.from_text(Path(f"aitasks/t{TASK_ID}_probe.md"), raw)
        return self.ab.TaskDetailScreen(task)

    # -- dispatch introspection ------------------------------------------

    def _pops(self, app):
        return [c for c in app.call_from_thread.call_args_list
                if c.args[0] is app.pop_screen]

    def _notifies(self, app):
        """(message, severity) for every notify dispatched from the worker."""
        return [(c.args[1], c.kwargs.get("severity"))
                for c in app.call_from_thread.call_args_list
                if c.args[0] is app.notify]

    def _dismisses(self, screen, app):
        return [c.args[1:] for c in app.call_from_thread.call_args_list
                if c.args[0] == screen.dismiss]

    def _pushes(self, app):
        return [c for c in app.call_from_thread.call_args_list
                if c.args[0] is app.push_screen]

    def _index_of(self, app, target):
        for i, c in enumerate(app.call_from_thread.call_args_list):
            if c.args[0] is target:
                return i
        return -1

    # -- worker drivers ---------------------------------------------------

    def _run_worker(self, screen, worker_name, args, *, side_effect=None,
                    returncode=0, stdout="", stderr=""):
        """Run a @work(thread=True) body inline; return the mock app.

        `__wrapped__` is the undecorated function (Textual's work decorator
        applies functools.wraps), so the real body runs synchronously and every
        `call_from_thread` dispatch is recorded rather than executed.
        """
        app = MagicMock()
        worker = getattr(self.ab.TaskDetailScreen, worker_name).__wrapped__
        run_kwargs = ({"side_effect": side_effect} if side_effect is not None
                      else {"return_value": MagicMock(returncode=returncode,
                                                      stdout=stdout, stderr=stderr)})
        with patch.object(self.ab.TaskDetailScreen, "app",
                          new_callable=PropertyMock, return_value=app), \
             patch.object(self.ab.subprocess, "run", **run_kwargs):
            yield_exc = None
            try:
                worker(screen, *args)
            except BaseException as exc:  # noqa: BLE001 — re-raised by callers that want it
                yield_exc = exc
        self._raised = yield_exc
        return app


class RevertDegradeTests(DialogSubprocessTestBase):
    """revert_task runs on the main thread and pushes no overlay."""

    def test_degrades_to_notification(self):
        for name, exc in _FAILURES.items():
            with self.subTest(failure=name):
                screen = self._screen()
                app = MagicMock()
                with patch.object(self.ab.TaskDetailScreen, "app",
                                  new_callable=PropertyMock, return_value=app), \
                     patch.object(self.ab.subprocess, "run", side_effect=exc):
                    screen.revert_task()  # must not raise
                self.assertEqual(
                    1, app.notify.call_count,
                    f"{name}: expected exactly one failure notification")
                message, kwargs = app.notify.call_args.args[0], app.notify.call_args.kwargs
                self.assertTrue(
                    message.startswith("Revert failed: "),
                    f"{name}: unexpected notification {message!r}")
                self.assertEqual("error", kwargs.get("severity"))


class LockWorkerDegradeTests(DialogSubprocessTestBase):
    """_do_lock / _do_unlock: the overlay must never outlive the worker."""

    WORKERS = {
        "_do_lock": ((TASK_ID, "user@example.invalid"), "Lock failed: "),
        "_do_unlock": ((TASK_ID,), "Unlock failed: "),
    }

    def test_degrades_and_pops_overlay(self):
        for worker_name, (args, prefix) in self.WORKERS.items():
            for name, exc in _FAILURES.items():
                with self.subTest(worker=worker_name, failure=name):
                    screen = self._screen()
                    app = self._run_worker(screen, worker_name, args, side_effect=exc)
                    self.assertIsNone(
                        self._raised,
                        f"{worker_name}/{name}: exception escaped the worker thread")
                    self.assertEqual(
                        1, len(self._pops(app)),
                        f"{worker_name}/{name}: LoadingOverlay not popped exactly once")
                    self.assertEqual(
                        [(f"{prefix}{exc}", "error")], self._notifies(app),
                        f"{worker_name}/{name}: wrong failure notification")

    def test_overlay_backstop_for_unanticipated_exception(self):
        """The pop lives in a `finally`, so it survives an uncaught type.

        A tuple-only fix fails this: RuntimeError is deliberately outside every
        handler's caught tuple, so the pop must come from the `finally` and the
        exception must still propagate (it is a real bug worth surfacing).
        """
        for worker_name, (args, _prefix) in self.WORKERS.items():
            with self.subTest(worker=worker_name):
                screen = self._screen()
                app = self._run_worker(screen, worker_name, args,
                                       side_effect=_UNANTICIPATED)
                self.assertIs(
                    _UNANTICIPATED, self._raised,
                    f"{worker_name}: an unanticipated exception must not be swallowed")
                self.assertEqual(
                    1, len(self._pops(app)),
                    f"{worker_name}: LoadingOverlay stranded by an uncaught exception")
                self.assertEqual(
                    [], self._notifies(app),
                    f"{worker_name}: an uncaught exception must not fake a failure toast")


class NormalOutcomeTests(DialogSubprocessTestBase):
    """No exception injected — pins every normal outcome the refactor moved.

    Each case asserts exactly one overlay pop plus the exact dispatch, so a
    mis-scoped `try` or mis-indented result branch is caught even though no
    injected-exception test would notice.
    """

    def test_lock_success(self):
        screen = self._screen()
        app = self._run_worker(screen, "_do_lock", (TASK_ID, "user@example.invalid"),
                               returncode=0)
        self.assertIsNone(self._raised)
        self.assertEqual(1, len(self._pops(app)))
        self.assertEqual([(f"Locked t{TASK_ID}", "information")], self._notifies(app))
        self.assertEqual([("locked",)], self._dismisses(screen, app))

    def test_lock_nonzero_returncode(self):
        screen = self._screen()
        app = self._run_worker(screen, "_do_lock", (TASK_ID, "user@example.invalid"),
                               returncode=1, stderr="boom-lock\n")
        self.assertIsNone(self._raised)
        self.assertEqual(1, len(self._pops(app)))
        self.assertEqual([("Lock failed: boom-lock", "error")], self._notifies(app))
        self.assertEqual([], self._dismisses(screen, app),
                         "a failed lock must not dismiss the dialog")

    def test_unlock_success_without_reset_prompt(self):
        """status != Implementing: plain dismissal, no confirm dialog."""
        screen = self._screen(_READY)
        app = self._run_worker(screen, "_do_unlock", (TASK_ID,), returncode=0)
        self.assertIsNone(self._raised)
        self.assertEqual(1, len(self._pops(app)))
        self.assertEqual([(f"Unlocked t{TASK_ID}", "information")], self._notifies(app))
        self.assertEqual([("unlocked",)], self._dismisses(screen, app))
        self.assertEqual([], self._pushes(app),
                         "no reset confirmation is due for a non-Implementing task")

    def test_unlock_success_pops_overlay_before_reset_prompt(self):
        """status == Implementing: the ordering a body-wide `finally` breaks.

        pop_screen removes the TOP screen, so the LoadingOverlay pop must be
        dispatched BEFORE ResetTaskConfirmScreen is pushed — otherwise the pop
        dismisses the confirmation dialog the user is meant to answer.
        """
        screen = self._screen(_IMPLEMENTING)
        app = self._run_worker(screen, "_do_unlock", (TASK_ID,), returncode=0)
        self.assertIsNone(self._raised)
        self.assertEqual(1, len(self._pops(app)))
        pushes = self._pushes(app)
        self.assertEqual(1, len(pushes), "expected the reset confirmation push")
        self.assertIsInstance(pushes[0].args[1], self.ab.ResetTaskConfirmScreen)
        self.assertLess(
            self._index_of(app, app.pop_screen), self._index_of(app, app.push_screen),
            "LoadingOverlay must be popped before ResetTaskConfirmScreen is pushed")
        self.assertEqual([], self._dismisses(screen, app),
                         "dismissal is deferred to the reset confirmation callback")

    def test_unlock_nonzero_returncode(self):
        screen = self._screen(_IMPLEMENTING)
        app = self._run_worker(screen, "_do_unlock", (TASK_ID,),
                               returncode=1, stderr="boom-unlock\n")
        self.assertIsNone(self._raised)
        self.assertEqual(1, len(self._pops(app)))
        self.assertEqual([("Unlock failed: boom-unlock", "error")], self._notifies(app))
        self.assertEqual([], self._dismisses(screen, app),
                         "a failed unlock must not dismiss the dialog")
        self.assertEqual([], self._pushes(app))

    def test_revert_nonzero_returncode(self):
        """revert_task notifies DIRECTLY — it runs on the main thread."""
        screen = self._screen()
        app = MagicMock()
        with patch.object(self.ab.TaskDetailScreen, "app",
                          new_callable=PropertyMock, return_value=app), \
             patch.object(self.ab.subprocess, "run",
                          return_value=MagicMock(returncode=1, stdout="",
                                                 stderr="boom-revert\n")):
            screen.revert_task()
        app.notify.assert_called_once_with("Revert failed: boom-revert", severity="error")
        self.assertEqual([], app.call_from_thread.call_args_list,
                         "revert_task runs on the main thread — no call_from_thread")


if __name__ == "__main__":
    unittest.main()
