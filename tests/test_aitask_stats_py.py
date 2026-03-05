"""Unit tests for aiscripts/aitask_stats.py."""

from __future__ import annotations

import importlib.util
import sys
import tarfile
import tempfile
import unittest
from datetime import date
from pathlib import Path


def _load_stats_module():
    script = Path(__file__).resolve().parents[1] / "aiscripts" / "aitask_stats.py"
    spec = importlib.util.spec_from_file_location("aitask_stats_py", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


stats = _load_stats_module()


class TestWeekStart(unittest.TestCase):
    def test_resolve_week_start_prefix(self):
        self.assertEqual(stats.resolve_week_start("mon"), 1)
        self.assertEqual(stats.resolve_week_start("sun"), 7)

    def test_resolve_week_start_invalid_defaults_monday(self):
        self.assertEqual(stats.resolve_week_start("zzz"), 1)


class TestArgParsing(unittest.TestCase):
    def test_days_accepts_trailing_dot(self):
        args = stats.parse_args(["-d", "7."])
        self.assertEqual(args.days, 7)


class TestFrontmatterParsing(unittest.TestCase):
    def test_completed_at_fallback_to_updated_at(self):
        fm = {
            "status": "Done",
            "updated_at": "2026-03-01 12:30",
        }
        self.assertEqual(stats.parse_completed_date(fm), date(2026, 3, 1))


class TestCollection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

        archived = self.base / "aitasks" / "archived"
        archived.mkdir(parents=True)
        (archived / "t1_parent.md").write_text(
            "---\n"
            "status: Done\n"
            "completed_at: 2026-03-01 10:00\n"
            "labels: [alpha]\n"
            "issue_type: bug\n"
            "---\n"
            "parent\n",
            encoding="utf-8",
        )

        child_dir = archived / "t1"
        child_dir.mkdir()
        (child_dir / "t1_1_child.md").write_text(
            "---\n"
            "status: Done\n"
            "completed_at: 2026-03-02 11:00\n"
            "labels: [beta]\n"
            "issue_type: feature\n"
            "---\n"
            "child\n",
            encoding="utf-8",
        )

        tar_path = archived / "old.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tf:
            old = self.base / "old_task.md"
            old.write_text(
                "---\n"
                "status: Done\n"
                "completed_at: 2026-02-20 09:00\n"
                "labels: [gamma]\n"
                "issue_type: refactor\n"
                "---\n"
                "old\n",
                encoding="utf-8",
            )
            tf.add(old, arcname="aitasks/archived/t2_old_task.md")

        self.orig_task_dir = stats.TASK_DIR
        self.orig_archive_dir = stats.ARCHIVE_DIR
        self.orig_archive_tar = stats.ARCHIVE_TAR
        self.orig_task_types = stats.TASK_TYPES_FILE

        stats.TASK_DIR = self.base / "aitasks"
        stats.ARCHIVE_DIR = stats.TASK_DIR / "archived"
        stats.ARCHIVE_TAR = stats.ARCHIVE_DIR / "old.tar.gz"
        stats.TASK_TYPES_FILE = stats.TASK_DIR / "metadata" / "task_types.txt"

    def tearDown(self):
        stats.TASK_DIR = self.orig_task_dir
        stats.ARCHIVE_DIR = self.orig_archive_dir
        stats.ARCHIVE_TAR = self.orig_archive_tar
        stats.TASK_TYPES_FILE = self.orig_task_types
        self.tmp.cleanup()

    def test_collect_stats_includes_archived_and_tar(self):
        data = stats.collect_stats(today=date(2026, 3, 5), week_start_dow=1)
        self.assertEqual(data.total_tasks, 3)
        self.assertEqual(data.tasks_7d, 2)
        self.assertEqual(data.tasks_30d, 3)
        self.assertEqual(data.label_counts_total["alpha"], 1)
        self.assertEqual(data.label_counts_total["beta"], 1)
        self.assertEqual(data.label_counts_total["gamma"], 1)
        self.assertEqual(len(data.csv_rows), 3)


if __name__ == "__main__":
    unittest.main()
