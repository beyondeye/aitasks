"""Unit tests for TaskInfoCache._resolve archived-fallback behavior (t738).

Verifies that monitor_shared.TaskInfoCache resolves task info from both the
active ``aitasks/`` location and the archived ``aitasks/archived/`` location,
so monitor and minimonitor keep displaying task titles for agent panes whose
tasks have already been archived.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from monitor.monitor_shared import TaskInfoCache  # noqa: E402


def _write_task(path: Path, title: str, status: str = "Ready") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "priority: medium\n"
        "effort: medium\n"
        f"status: {status}\n"
        "issue_type: bug\n"
        "---\n\n"
        f"# {title}\n\n"
        "body line\n",
        encoding="utf-8",
    )


def _write_plan(path: Path, body: str = "plan body") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "Task: stub\n"
        "---\n\n"
        f"{body}\n",
        encoding="utf-8",
    )


class TestArchivedFallback(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "aitasks").mkdir()
        (self.root / "aiplans").mkdir()
        self.cache = TaskInfoCache(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_active_parent_resolves(self) -> None:
        _write_task(self.root / "aitasks/t100_foo.md", "Active Foo")

        info = self.cache._resolve("100")

        self.assertIsNotNone(info)
        self.assertEqual(info.title, "Active Foo")
        self.assertTrue(info.task_file.startswith("aitasks/t100_"))
        self.assertNotIn("archived", info.task_file)

    def test_archived_parent_resolves(self) -> None:
        _write_task(
            self.root / "aitasks/archived/t100_foo.md",
            "Archived Foo",
            status="Done",
        )

        info = self.cache._resolve("100")

        self.assertIsNotNone(info)
        self.assertEqual(info.title, "Archived Foo")
        self.assertEqual(info.status, "Done")
        self.assertIn("archived", info.task_file)

    def test_archived_child_resolves(self) -> None:
        _write_task(
            self.root / "aitasks/archived/t50/t50_2_bar.md",
            "Archived Child",
            status="Done",
        )

        info = self.cache._resolve("50_2")

        self.assertIsNotNone(info)
        self.assertEqual(info.title, "Archived Child")
        self.assertIn("archived/t50/t50_2_", info.task_file)

    def test_active_wins_over_archived(self) -> None:
        _write_task(self.root / "aitasks/t100_foo.md", "Active Foo")
        _write_task(
            self.root / "aitasks/archived/t100_foo.md",
            "Archived Foo",
            status="Done",
        )

        info = self.cache._resolve("100")

        self.assertIsNotNone(info)
        self.assertEqual(info.title, "Active Foo")
        self.assertNotIn("archived", info.task_file)

    def test_archived_plan_resolves_alongside_archived_task(self) -> None:
        _write_task(
            self.root / "aitasks/archived/t100_foo.md",
            "Archived Foo",
            status="Done",
        )
        _write_plan(
            self.root / "aiplans/archived/p100_foo.md",
            body="archived plan body",
        )

        info = self.cache._resolve("100")

        self.assertIsNotNone(info)
        self.assertIsNotNone(info.plan_content)
        self.assertIn("archived plan body", info.plan_content)

    def test_archived_child_plan_resolves(self) -> None:
        _write_task(
            self.root / "aitasks/archived/t50/t50_2_bar.md",
            "Archived Child",
            status="Done",
        )
        _write_plan(
            self.root / "aiplans/archived/p50/p50_2_bar.md",
            body="archived child plan",
        )

        info = self.cache._resolve("50_2")

        self.assertIsNotNone(info)
        self.assertIsNotNone(info.plan_content)
        self.assertIn("archived child plan", info.plan_content)

    def test_missing_returns_none(self) -> None:
        info = self.cache._resolve("999")
        self.assertIsNone(info)


if __name__ == "__main__":
    unittest.main()
