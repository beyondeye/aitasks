"""Board hard-delete attachment decref wiring (t1093).

Covers the board-side contract that the bash helper test cannot:
  * KanbanApp._doomed_attachment_ids — derives the bare ids of doomed TASK files
    (parent + cascade children) from a mixed delete-path list, excluding plan
    files / non-task paths by ROOT (not a substring of the name).
  * KanbanApp._decref_doomed_attachments — assembles the helper command
    (including --protect-task for revived folded tasks, which the helper now
    REBINDS the shared blobs to rather than merely skipping — t1096) and FAILS
    CLOSED (ok=False) on a non-zero helper exit, the signal that gates `git rm`.

Run: python3 -m pytest tests/test_board_decref_doomed_attachments.py -v
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
BOARD_PATH = REPO_ROOT / ".aitask-scripts" / "board" / "aitask_board.py"
for path in (
    REPO_ROOT / ".aitask-scripts",
    REPO_ROOT / ".aitask-scripts" / "board",
    REPO_ROOT / ".aitask-scripts" / "lib",
):
    sys.path.insert(0, str(path))


def _load_board_module(task_dir: Path):
    module_name = f"aitask_board_t1093_{id(task_dir)}"
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


class _FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class DoomedIdExtractionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.task_dir = Path(self.tmp.name) / "aitasks"   # TASKS_DIR.name == "aitasks"
        (self.task_dir / "metadata").mkdir(parents=True)
        self.board = _load_board_module(self.task_dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_extracts_parent_and_children_excludes_plans_and_strays(self):
        td = self.task_dir
        paths = [
            str(td / "t30_primary.md"),                 # parent  -> 30
            str(td / "t30" / "t30_1_childA.md"),        # child   -> 30_1
            str(td / "t30" / "t30_2_childB.md"),        # child   -> 30_2
            "aiplans/p30_primary.md",                   # plan    -> excluded (root)
            "aiplans/p30/p30_1_childA.md",              # plan    -> excluded (root)
            str(td / "metadata" / "labels.txt"),        # non-.md -> excluded
            "myaitasks/t99_decoy.md",                   # 'aitasks' only as a SUBSTRING of a part -> excluded
        ]
        ids = self.board.KanbanApp._doomed_attachment_ids(paths)
        self.assertEqual(ids, ["30", "30_1", "30_2"])

    def test_no_task_files_yields_empty(self):
        ids = self.board.KanbanApp._doomed_attachment_ids(
            ["aiplans/p7_x.md", "myaitasks/t1_x.md"]
        )
        self.assertEqual(ids, [])


class DecrefStepContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.task_dir = Path(self.tmp.name) / "aitasks"
        (self.task_dir / "metadata").mkdir(parents=True)
        self.board = _load_board_module(self.task_dir)
        # A stand-in for `self`: only _doomed_attachment_ids is referenced.
        self.app = types.SimpleNamespace(
            _doomed_attachment_ids=self.board.KanbanApp._doomed_attachment_ids
        )
        self._orig_run = self.board.subprocess.run

    def tearDown(self):
        self.board.subprocess.run = self._orig_run
        self.tmp.cleanup()

    def _patch_run(self, proc):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return proc

        self.board.subprocess.run = fake_run
        return calls

    def test_success_builds_command_with_protect_task(self):
        calls = self._patch_run(_FakeProc(returncode=0, stdout="STAGED:1\n"))
        paths = [str(self.task_dir / "t30_primary.md")]
        ok, msg = self.board.KanbanApp._decref_doomed_attachments(
            self.app, paths, folded_ids=["31"]
        )
        self.assertTrue(ok)
        self.assertEqual(msg, "")
        self.assertEqual(len(calls), 1)
        cmd = calls[0]
        self.assertIn("decref-deleted", cmd)
        self.assertIn("--protect-task", cmd)
        self.assertIn("31", cmd)
        self.assertIn("30", cmd)
        # The doomed ids must come AFTER the --protect-task pair.
        self.assertGreater(cmd.index("30"), cmd.index("31"))

    def test_nonzero_exit_fails_closed(self):
        self._patch_run(_FakeProc(returncode=1, stderr="lock busy"))
        paths = [str(self.task_dir / "t30_primary.md")]
        ok, msg = self.board.KanbanApp._decref_doomed_attachments(
            self.app, paths, folded_ids=[]
        )
        self.assertFalse(ok)            # gates the board's git rm
        self.assertEqual(msg, "lock busy")

    def test_no_doomed_ids_skips_subprocess(self):
        calls = self._patch_run(_FakeProc(returncode=99))  # would fail if ever called
        ok, msg = self.board.KanbanApp._decref_doomed_attachments(
            self.app, ["aiplans/p7_x.md"], folded_ids=[]
        )
        self.assertTrue(ok)
        self.assertEqual(msg, "")
        self.assertEqual(calls, [])     # no task files -> helper never invoked


if __name__ == "__main__":
    unittest.main()
