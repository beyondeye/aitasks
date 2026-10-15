"""Board task-op workers survive an exclusive default-group worker (t1994).

`_do_archive`, `_do_delete`, `_do_rename_task` and `_do_git_commit_tasks` ran as
`@work(thread=True)` in Textual's default group on the `KanbanApp` node, beside
the board's exclusive default-group workers (`_run_sync`, `run_aitask_pick`,
`run_codeagent_operation`, `run_dialog_command`, ...). Textual's
`WorkerManager.add_worker` cancels the whole group for an exclusive worker, and a
worker cancelled before its first step never reaches `run_in_executor`: its body
and its `finally` never run. For these four that meant the user-confirmed
operation was silently dropped AND the caller's `LoadingOverlay` -- popped only
in that `finally` -- was stranded on top, leaving the board modal-locked. Same
mechanism as the trail workers (t1979, t1988).

Each operation is driven through its real caller, which pushes the overlay and
starts the worker in one synchronous call; only the outermost side effect is
stubbed. Every (operation, variant) pair is its own test method with a fresh
fixture tree and app: rename moves the task file and delete removes it, so a
baseline sharing a tree with its same-tick control would hand the control a
missing file. The `*_baseline` methods are the controls -- they pass with or
without the fix, proving the harness drives the real bodies on a valid task, so
a red same-tick method can only mean the cancel.

Run: python3 tests/test_board_task_op_worker_groups.py -v
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import ast
import asyncio
import contextlib
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
BOARD_PATH = REPO_ROOT / ".aitask-scripts" / "board" / "aitask_board.py"
for _p in (
    str(REPO_ROOT / "tests" / "lib"),
    str(REPO_ROOT / ".aitask-scripts"),
    str(REPO_ROOT / ".aitask-scripts" / "board"),
    str(REPO_ROOT / ".aitask-scripts" / "lib"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import board_fixture as bf  # noqa: E402
from textual.worker import WorkerCancelled  # noqa: E402

#: A top-level, childless Ready task of `bf.DEFAULT_TOPOLOGY`.
TASK_FILENAME = "t9003_gamma.md"
TASK_NUM = "t9003"
TASK_PATH = f"aitasks/{TASK_FILENAME}"
RENAMED = "t9003_renamed_probe.md"


class TaskOpSameTickCancelTests(unittest.TestCase):
    """Each task operation lands even when an exclusive default-group worker
    is started in the same tick as its worker."""

    def setUp(self):
        # A fresh tree per METHOD, never per class: rename and delete mutate it.
        self.tree, self.ab = bf.enter_fixture_tree(
            self.addCleanup,
            tag=f"{type(self).__name__}_{self._testMethodName}")
        self.commits: list[tuple[str, list[str]]] = []
        self.archive_calls: list[list[str]] = []
        self.notes: list[str] = []

    def _record_commit(self, message, paths, **_kwargs):
        self.commits.append((message, [str(p) for p in paths]))
        return SimpleNamespace(status="committed", detail="")

    def _overlays(self, app) -> list[str]:
        return [type(s).__name__ for s in app.screen_stack
                if isinstance(s, self.ab.LoadingOverlay)]

    def _drive(self, start, canceller: bool) -> dict:
        """Boot a fresh app, run `start(app, task)` -- the real caller -- and,
        when `canceller`, start an exclusive default-group worker in the SAME
        tick; drain, and report the overlays left on the screen stack."""
        ab = self.ab
        out: dict = {}
        real_run = subprocess.run

        def fake_run(argv, *args, **kwargs):
            # Only the archive script is stood in for; every other subprocess
            # (git status refreshes, ...) runs for real.
            if argv and str(argv[0]).endswith("aitask_archive.sh"):
                self.archive_calls.append(list(argv))
                return subprocess.CompletedProcess(argv, 0, "", "")
            return real_run(argv, *args, **kwargs)

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(200, 48)) as pilot:
                await pilot.pause()
                app.notify = lambda message, **kw: self.notes.append(str(message))
                task = app.manager.task_datas[TASK_FILENAME]
                # A valid task and no overlay up: a red result can then only be
                # the cancel, never state left behind by another variant.
                self.assertTrue(task.filepath.exists(), task.filepath)
                self.assertEqual(self._overlays(app), [])
                start(app, task)
                if canceller:
                    # No await in between: the victim has not taken its first step.
                    app.run_worker(lambda: None, thread=True, exclusive=True)
                for _ in range(3):
                    # Pre-fix the victim's wait() raises WorkerCancelled; let the
                    # assertions below report it rather than gather() erroring.
                    with contextlib.suppress(WorkerCancelled):
                        await app.workers.wait_for_complete()
                    await pilot.pause()
                out["overlays"] = self._overlays(app)

        with patch.object(subprocess, "run", fake_run), \
                patch.object(ab, "commit_task_paths", self._record_commit):
            asyncio.run(go())
        return out

    # -- archive -----------------------------------------------------------

    def _archive(self, canceller):
        out = self._drive(
            lambda app, task: app._execute_archive(TASK_NUM, task), canceller)
        self.assertEqual(
            self.archive_calls,
            [["./.aitask-scripts/aitask_archive.sh", "--superseded", TASK_NUM]])
        self.assertIn(f"Archived {TASK_NUM} as superseded", self.notes)
        self.assertEqual(out["overlays"], [])

    def test_archive_baseline(self):
        self._archive(canceller=False)

    def test_archive_survives_same_tick_exclusive_worker(self):
        self._archive(canceller=True)

    # -- delete ------------------------------------------------------------

    def _delete(self, canceller):
        def start(app, task):
            # The decref shells out to aitask_attach.sh, absent from the fixture;
            # its contract is tests/test_board_decref_doomed_attachments.py.
            app._decref_doomed_attachments = lambda paths, folded: (True, "")
            app._execute_delete(TASK_NUM, [task.filepath], None)

        out = self._drive(start, canceller)
        self.assertEqual(len(self.commits), 1, self.commits)
        self.assertIn(TASK_PATH, self.commits[0][1])
        self.assertFalse((self.tree / TASK_PATH).exists())
        self.assertIn(f"Deleted task {TASK_NUM}", self.notes)
        self.assertEqual(out["overlays"], [])

    def test_delete_baseline(self):
        self._delete(canceller=False)

    def test_delete_survives_same_tick_exclusive_worker(self):
        self._delete(canceller=True)

    # -- rename ------------------------------------------------------------

    def _rename(self, canceller):
        syncs: list[dict] = []

        def start(app, task):
            # The post-rename sync is a worker of its own; record the request.
            app._run_sync = lambda **kwargs: syncs.append(kwargs)
            app._rename_task(task, "renamed probe")

        out = self._drive(start, canceller)
        self.assertEqual(len(self.commits), 1, self.commits)
        self.assertEqual(sorted(self.commits[0][1]),
                         sorted([TASK_PATH, f"aitasks/{RENAMED}"]))
        self.assertTrue((self.tree / "aitasks" / RENAMED).exists())
        self.assertEqual(syncs, [{"show_notification": True}])
        self.assertIn(f"Renamed to {RENAMED}", self.notes)
        self.assertEqual(out["overlays"], [])

    def test_rename_baseline(self):
        self._rename(canceller=False)

    def test_rename_survives_same_tick_exclusive_worker(self):
        self._rename(canceller=True)

    # -- commit ------------------------------------------------------------

    def _commit(self, canceller):
        out = self._drive(
            lambda app, task: app._git_commit_tasks([task], "ait: probe"),
            canceller)
        self.assertEqual(self.commits, [("ait: probe", [TASK_PATH])])
        self.assertIn("Committed 1 file(s)", self.notes)
        self.assertEqual(out["overlays"], [])

    def test_commit_baseline(self):
        self._commit(canceller=False)

    def test_commit_survives_same_tick_exclusive_worker(self):
        self._commit(canceller=True)


class BoardWorkerGroupTests(unittest.TestCase):
    """Every non-exclusive worker of `aitask_board.py` names its own group.

    The `KanbanApp` twin of `TrailWorkerGroupTests`
    (tests/test_board_bytrail_view.py): the four task-op workers are pinned
    behaviourally above; this covers any worker added later."""

    KNOWN = {"_do_archive", "_do_delete", "_do_rename_task",
             "_do_git_commit_tasks"}

    @staticmethod
    def _workers(tree):
        """(name, keywords) of each function decorated with `work`."""
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if isinstance(dec, ast.Name) and dec.id == "work":
                    yield node.name, {}
                elif (isinstance(dec, ast.Call)
                      and isinstance(dec.func, ast.Name)
                      and dec.func.id == "work"):
                    yield node.name, {k.arg: k.value for k in dec.keywords}

    def test_non_exclusive_workers_run_outside_the_default_group(self):
        tree = ast.parse(BOARD_PATH.read_text(encoding="utf-8"))
        scanned, offenders = set(), []
        for name, kw in self._workers(tree):
            exclusive = kw.get("exclusive")
            if isinstance(exclusive, ast.Constant) and exclusive.value is True:
                continue                  # a canceller: its group is deliberate
            scanned.add(name)
            group = kw.get("group")
            if not (isinstance(group, ast.Constant)
                    and isinstance(group.value, str)
                    and group.value not in ("", "default")):
                offenders.append(name)
        # Vacuity guard: a decorator spelled differently would hide workers.
        self.assertLessEqual(self.KNOWN, scanned,
                             f"scan missed workers: {self.KNOWN - scanned}")
        self.assertEqual(offenders, [],
                         "non-exclusive workers in the default group")


if __name__ == "__main__":
    unittest.main(verbosity=2)
