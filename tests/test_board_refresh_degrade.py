"""Board refresh degrades on any subprocess environment failure (t1302).

`TaskManager.refresh_git_status` caught only
`(subprocess.TimeoutExpired, FileNotFoundError)`, while its twin
`refresh_lock_map` directly below it also caught `OSError`. A `PermissionError`
— or any other `OSError` — raised by `subprocess.run` therefore propagated out
of a board refresh instead of degrading to "no git status". Every board refresh
and every task-move keypress goes through that call, so the uncaught path
crashed the TUI.

Both refreshers are driven through the SAME parametrized exception set so the
pair cannot silently re-diverge: the divergence, not either handler on its own,
is what produced the bug.

The collections are SEEDED with sentinel entries before the failure is injected.
A fresh TaskManager starts with both empty, so asserting "still empty" would
only prove the exception was swallowed — not that a failed refresh degrades
stale state to "no git status" / "no locks", which is the actual promise.

Run: python3 tests/test_board_refresh_degrade.py -v
"""

from __future__ import annotations

import errno
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
BOARD_PATH = REPO_ROOT / ".aitask-scripts" / "board" / "aitask_board.py"
for _p in (
    REPO_ROOT / ".aitask-scripts",
    REPO_ROOT / ".aitask-scripts" / "board",
    REPO_ROOT / ".aitask-scripts" / "lib",
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def _load_board_module(task_dir: Path):
    """Import aitask_board.py bound to a temp TASK_DIR (module-level globals)."""
    module_name = f"aitask_board_t1302_{id(task_dir)}"
    previous = os.environ.get("TASK_DIR")
    os.environ["TASK_DIR"] = str(task_dir)
    try:
        spec = importlib.util.spec_from_file_location(module_name, BOARD_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            os.environ.pop("TASK_DIR", None)
        else:
            os.environ["TASK_DIR"] = previous


# The full boundary both handlers promise. TimeoutExpired is a SubprocessError,
# not an OSError; PermissionError/FileNotFoundError are OSError subclasses; the
# bare OSError pins the base class itself rather than only the two subclasses
# that happened to be listed.
_FAILURES = {
    "permission_error": PermissionError(errno.EACCES, "permission denied"),
    "base_oserror": OSError(errno.EMFILE, "too many open files"),
    "file_not_found": FileNotFoundError(errno.ENOENT, "no such file"),
    "timeout": subprocess.TimeoutExpired(cmd=["git"], timeout=5),
}

_STALE_FILE = "aitasks/t9999_stale.md"
_STALE_LOCK_ID = "9999"


class BoardRefreshDegradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        task_dir = Path(cls._tmp.name) / "aitasks"
        task_dir.mkdir(parents=True)
        cls.board = _load_board_module(task_dir)
        cls._cwd = os.getcwd()
        os.chdir(cls._tmp.name)
        try:
            cls.manager = cls.board.TaskManager()
        except Exception:
            os.chdir(cls._cwd)
            cls._tmp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._cwd)
        cls._tmp.cleanup()

    def _seed(self):
        """Populate both caches with stale sentinels a refresh must clear."""
        self.manager.modified_files = {_STALE_FILE}
        self.manager.lock_map = {
            _STALE_LOCK_ID: {
                "locked_by": "stale@example.invalid",
                "hostname": "stalehost",
                "locked_at": "2000-01-01 00:00",
            }
        }

    def test_refresh_git_status_degrades(self):
        for name, exc in _FAILURES.items():
            with self.subTest(failure=name):
                self._seed()
                with mock.patch.object(self.board.subprocess, "run", side_effect=exc):
                    self.manager.refresh_git_status()
                self.assertEqual(
                    set(),
                    self.manager.modified_files,
                    f"{name}: stale git status survived a failed refresh",
                )

    def test_refresh_lock_map_degrades(self):
        for name, exc in _FAILURES.items():
            with self.subTest(failure=name):
                self._seed()
                with mock.patch.object(self.board.subprocess, "run", side_effect=exc):
                    self.manager.refresh_lock_map()
                self.assertEqual(
                    {},
                    self.manager.lock_map,
                    f"{name}: stale lock map survived a failed refresh",
                )


if __name__ == "__main__":
    unittest.main()
