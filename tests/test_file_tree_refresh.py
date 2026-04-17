"""Tests for codebrowser/file_tree.py tracked-files refresh logic.

Run: python3 -m pytest tests/test_file_tree_refresh.py -v
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_scripts = Path(__file__).resolve().parents[1] / ".aitask-scripts"
sys.path.insert(0, str(_scripts / "codebrowser"))

from file_tree import compute_tracked_sets


def _git(cwd, *args):
    result = subprocess.run(
        ["git"] + list(args), capture_output=True, text=True, cwd=cwd,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


class ComputeTrackedSetsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _git(self.root, "init", "-q")
        _git(self.root, "config", "user.email", "t@x")
        _git(self.root, "config", "user.name", "t")
        (self.root / "a.txt").write_text("a")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "b.txt").write_text("b")
        (self.root / "sub" / "deep").mkdir()
        (self.root / "sub" / "deep" / "c.txt").write_text("c")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "init")

    def tearDown(self):
        self._tmp.cleanup()

    def test_initial_scan(self):
        files, dirs = compute_tracked_sets(self.root)
        self.assertEqual(files, {"a.txt", "sub/b.txt", "sub/deep/c.txt"})
        self.assertEqual(dirs, {"sub", "sub/deep"})

    def test_untracked_files_excluded(self):
        (self.root / "untracked.txt").write_text("u")
        (self.root / "sub" / "untracked2.txt").write_text("u")
        files, _ = compute_tracked_sets(self.root)
        self.assertNotIn("untracked.txt", files)
        self.assertNotIn("sub/untracked2.txt", files)

    def test_refresh_picks_up_new_file(self):
        files_before, _ = compute_tracked_sets(self.root)
        self.assertNotIn("NEW.md", files_before)
        (self.root / "NEW.md").write_text("new")
        (self.root / "newdir").mkdir()
        (self.root / "newdir" / "n.txt").write_text("n")
        _git(self.root, "add", "NEW.md", "newdir/n.txt")
        files_after, dirs_after = compute_tracked_sets(self.root)
        self.assertIn("NEW.md", files_after)
        self.assertIn("newdir/n.txt", files_after)
        self.assertIn("newdir", dirs_after)

    def test_refresh_picks_up_deleted_file(self):
        _git(self.root, "rm", "-q", "sub/b.txt")
        files_after, dirs_after = compute_tracked_sets(self.root)
        self.assertNotIn("sub/b.txt", files_after)
        self.assertIn("sub", dirs_after)
        self.assertIn("sub/deep", dirs_after)

    def test_empty_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git(root, "init", "-q")
            files, dirs = compute_tracked_sets(root)
            self.assertEqual(files, set())
            self.assertEqual(dirs, set())


if __name__ == "__main__":
    unittest.main()
