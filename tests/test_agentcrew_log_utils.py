"""Unit tests for agentcrew_log_utils: list, tail, full read, size formatting."""

from __future__ import annotations

import os
import sys
import tempfile
import time
import shutil
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from agentcrew.agentcrew_log_utils import (
    format_log_size,
    list_agent_logs,
    read_log_full,
    read_log_tail,
)


class TestListAgentLogs(unittest.TestCase):
    """Tests for list_agent_logs()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="log_utils_test_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_empty_worktree(self):
        result = list_agent_logs(self.tmpdir)
        self.assertEqual(result, [])

    def test_finds_log_files(self):
        for name in ["explorer", "patcher"]:
            Path(self.tmpdir, f"{name}_log.txt").write_text(f"output from {name}\n")
        result = list_agent_logs(self.tmpdir)
        self.assertEqual(len(result), 2)
        names = {r["name"] for r in result}
        self.assertEqual(names, {"explorer", "patcher"})

    def test_extracts_correct_fields(self):
        log_path = Path(self.tmpdir, "agent1_log.txt")
        log_path.write_text("hello\n")
        result = list_agent_logs(self.tmpdir)[0]
        self.assertEqual(result["name"], "agent1")
        self.assertEqual(result["path"], str(log_path))
        self.assertGreater(result["size"], 0)
        self.assertIsInstance(result["mtime"], float)
        self.assertRegex(result["mtime_str"], r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")

    def test_sorted_by_mtime_newest_first(self):
        p1 = Path(self.tmpdir, "old_log.txt")
        p1.write_text("old\n")
        # Ensure different mtime
        time.sleep(0.05)
        p2 = Path(self.tmpdir, "new_log.txt")
        p2.write_text("new\n")
        result = list_agent_logs(self.tmpdir)
        self.assertEqual(result[0]["name"], "new")
        self.assertEqual(result[1]["name"], "old")

    def test_ignores_non_log_files(self):
        Path(self.tmpdir, "agent1_log.txt").write_text("log\n")
        Path(self.tmpdir, "crew.yaml").write_text("not a log\n")
        Path(self.tmpdir, "agent1_output.txt").write_text("not a log\n")
        result = list_agent_logs(self.tmpdir)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "agent1")


class TestReadLogTail(unittest.TestCase):
    """Tests for read_log_tail()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="log_utils_test_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_nonexistent_file(self):
        self.assertEqual(read_log_tail("/nonexistent/path"), "")

    def test_empty_file(self):
        p = Path(self.tmpdir, "empty_log.txt")
        p.write_text("")
        self.assertEqual(read_log_tail(str(p)), "")

    def test_returns_last_n_lines(self):
        p = Path(self.tmpdir, "agent_log.txt")
        p.write_text("\n".join(f"Line {i}" for i in range(100)) + "\n")
        result = read_log_tail(str(p), lines=5)
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 5)
        self.assertIn("Line 99", lines[-1])

    def test_file_shorter_than_requested(self):
        p = Path(self.tmpdir, "short_log.txt")
        p.write_text("line1\nline2\nline3\n")
        result = read_log_tail(str(p), lines=50)
        lines = [l for l in result.split("\n") if l]
        self.assertEqual(len(lines), 3)

    def test_default_50_lines(self):
        p = Path(self.tmpdir, "agent_log.txt")
        p.write_text("\n".join(f"Line {i}" for i in range(200)) + "\n")
        result = read_log_tail(str(p))
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 50)


class TestReadLogFull(unittest.TestCase):
    """Tests for read_log_full()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="log_utils_test_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_nonexistent_file(self):
        self.assertEqual(read_log_full("/nonexistent/path"), "")

    def test_reads_full_content(self):
        p = Path(self.tmpdir, "agent_log.txt")
        content = "Line 1\nLine 2\nLine 3\n"
        p.write_text(content)
        self.assertEqual(read_log_full(str(p)), content)

    def test_truncates_large_file(self):
        p = Path(self.tmpdir, "big_log.txt")
        # Write more than max_bytes
        p.write_text("x" * 2000)
        result = read_log_full(str(p), max_bytes=500)
        self.assertTrue(result.startswith("... (truncated"))
        # The actual content after the notice should be ~500 bytes
        content_after_notice = result.split("\n", 1)[1]
        self.assertEqual(len(content_after_notice), 500)

    def test_no_truncation_under_limit(self):
        p = Path(self.tmpdir, "small_log.txt")
        content = "small content\n"
        p.write_text(content)
        result = read_log_full(str(p), max_bytes=500)
        self.assertFalse(result.startswith("..."))
        self.assertEqual(result, content)


class TestFormatLogSize(unittest.TestCase):
    """Tests for format_log_size()."""

    def test_bytes(self):
        self.assertEqual(format_log_size(0), "0 B")
        self.assertEqual(format_log_size(256), "256 B")
        self.assertEqual(format_log_size(1023), "1023 B")

    def test_kilobytes(self):
        self.assertEqual(format_log_size(1024), "1.0 KB")
        self.assertEqual(format_log_size(1536), "1.5 KB")
        self.assertEqual(format_log_size(10240), "10.0 KB")

    def test_megabytes(self):
        self.assertEqual(format_log_size(1048576), "1.0 MB")
        self.assertEqual(format_log_size(1572864), "1.5 MB")
        self.assertEqual(format_log_size(500000), "488.3 KB")


if __name__ == "__main__":
    unittest.main()
