"""Regression tests for archived relation lookup in ait board (t992).

Run: python3 -m pytest tests/test_board_archived_relation_lookup.py -v
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
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


def _write_task(path: Path, title: str, status: str = "Ready") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "priority: medium\n"
        "effort: low\n"
        f"status: {status}\n"
        "issue_type: bug\n"
        "---\n\n"
        f"## {title}\n\n"
        "body\n",
        encoding="utf-8",
    )


def _load_board_module(task_dir: Path):
    module_name = f"aitask_board_t992_{id(task_dir)}"
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


class ArchivedRelationLookupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.task_dir = Path(self.tmp.name) / "aitasks"
        (self.task_dir / "metadata").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _manager(self):
        board = _load_board_module(self.task_dir)
        return board, board.TaskManager()

    def test_active_task_wins_over_archived_duplicate(self) -> None:
        _write_task(self.task_dir / "t20_active.md", "Active")
        _write_task(self.task_dir / "archived" / "t20_archived.md", "Archived", "Done")
        _write_task(self.task_dir / "t1_owner.md", "Owner")

        board, manager = self._manager()

        task = manager.find_task_including_archived("t20")
        self.assertIsNotNone(task)
        self.assertEqual(task.filename, "t20_active.md")
        self.assertFalse(getattr(task, "archived", False))
        self.assertIs(manager.find_task_by_id("t20"), task)

    def test_verifies_field_resolves_archived_child(self) -> None:
        _write_task(self.task_dir / "archived" / "t13" / "t13_9_verified.md", "Verified", "Done")
        _write_task(self.task_dir / "t1_owner.md", "Owner")

        board, manager = self._manager()
        owner = manager.find_task_by_id("t1")
        field = board.VerifiesField(["13_9"], manager, owner)

        task = field._find_task_by_number("13_9")
        self.assertIsNotNone(task)
        self.assertEqual(task.filename, "t13_9_verified.md")
        self.assertTrue(task.archived)

    def test_depends_field_resolves_archived_parent(self) -> None:
        _write_task(self.task_dir / "archived" / "t44_dependency.md", "Dependency", "Done")
        _write_task(self.task_dir / "t1_owner.md", "Owner")

        board, manager = self._manager()
        owner = manager.find_task_by_id("t1")
        field = board.DependsField([44], manager, owner)

        task = field._find_task_by_number(44)
        self.assertIsNotNone(task)
        self.assertEqual(task.filename, "t44_dependency.md")
        self.assertTrue(task.archived)

    def test_missing_relation_stays_missing(self) -> None:
        _write_task(self.task_dir / "t1_owner.md", "Owner")

        board, manager = self._manager()
        owner = manager.find_task_by_id("t1")
        field = board.VerifiesField([999], manager, owner)

        self.assertIsNone(field._find_task_by_number(999))
        self.assertIsNone(manager.archived_task_cache["999"])


if __name__ == "__main__":
    unittest.main()
