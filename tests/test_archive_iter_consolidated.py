"""Tests for consolidated archive_iter.py functions (iter_all_archived_markdown,
iter_archived_frontmatter, _is_child_filename).

Run: python3 -m pytest tests/test_archive_iter_consolidated.py -v
"""

from __future__ import annotations

import importlib.util
import io
import os
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

# Load archive_iter from the lib directory
_lib_dir = Path(__file__).resolve().parents[1] / ".aitask-scripts" / "lib"
sys.path.insert(0, str(_lib_dir))

from archive_iter import (
    _is_child_filename,
    iter_all_archived_markdown,
    iter_archived_frontmatter,
)


def _make_archive(archive_path: Path, files: dict[str, str]) -> None:
    """Create a tar.zst at archive_path with the given filename->content mapping."""
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    buf.seek(0)
    subprocess.run(
        ["zstd", "-q", "-f", "-o", str(archive_path)],
        input=buf.read(), check=True,
    )


def _make_tar_gz(archive_path: Path, files: dict[str, str]) -> None:
    """Create a tar.gz at archive_path (for backward compat tests)."""
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as tf:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))


class TestIsChildFilename(unittest.TestCase):
    def test_child_pattern(self):
        self.assertTrue(_is_child_filename("t1_2_foo.md"))

    def test_child_large_numbers(self):
        self.assertTrue(_is_child_filename("t100_5_some_task.md"))

    def test_parent_pattern(self):
        self.assertFalse(_is_child_filename("t1_foo.md"))

    def test_no_match(self):
        self.assertFalse(_is_child_filename("readme.md"))


class TestIterAllArchivedMarkdown(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.archived = Path(self.tmp.name) / "archived"
        self.archived.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_loose_parent_files(self):
        (self.archived / "t1_foo.md").write_text("content1")
        (self.archived / "t2_bar.md").write_text("content2")
        results = list(iter_all_archived_markdown(self.archived))
        names = [r[0] for r in results]
        self.assertEqual(names, ["t1_foo.md", "t2_bar.md"])

    def test_skips_child_at_top_level(self):
        (self.archived / "t1_2_child.md").write_text("child content")
        (self.archived / "t3_parent.md").write_text("parent content")
        results = list(iter_all_archived_markdown(self.archived))
        names = [r[0] for r in results]
        self.assertNotIn("t1_2_child.md", names)
        self.assertIn("t3_parent.md", names)

    def test_loose_child_files(self):
        child_dir = self.archived / "t1"
        child_dir.mkdir()
        (child_dir / "t1_1_sub.md").write_text("sub1")
        (child_dir / "t1_2_sub.md").write_text("sub2")
        results = list(iter_all_archived_markdown(self.archived))
        names = [r[0] for r in results]
        self.assertIn("t1_1_sub.md", names)
        self.assertIn("t1_2_sub.md", names)

    def test_numbered_tar(self):
        _make_archive(
            self.archived / "_b0" / "old0.tar.zst",
            {"t50_task.md": "tar content"},
        )
        results = list(iter_all_archived_markdown(self.archived))
        names = [r[0] for r in results]
        self.assertIn("t50_task.md", names)
        self.assertEqual(
            [r[1] for r in results if r[0] == "t50_task.md"],
            ["tar content"],
        )

    def test_skips_legacy_tar(self):
        _make_archive(
            self.archived / "old.tar.zst",
            {"t99_legacy.md": "legacy content"},
        )
        results = list(iter_all_archived_markdown(self.archived))
        names = [r[0] for r in results]
        self.assertNotIn("t99_legacy.md", names)

    def test_combined_order(self):
        # Loose parent
        (self.archived / "t1_parent.md").write_text("p1")
        # Loose child
        child_dir = self.archived / "t1"
        child_dir.mkdir()
        (child_dir / "t1_1_child.md").write_text("c1")
        # Numbered tar
        _make_archive(
            self.archived / "_b0" / "old0.tar.zst",
            {"t50_tar.md": "tar1"},
        )
        results = list(iter_all_archived_markdown(self.archived))
        names = [r[0] for r in results]
        # Loose parents first, then children, then tar
        parent_idx = names.index("t1_parent.md")
        child_idx = names.index("t1_1_child.md")
        tar_idx = names.index("t50_tar.md")
        self.assertLess(parent_idx, child_idx)
        self.assertLess(child_idx, tar_idx)

    def test_empty_dir(self):
        results = list(iter_all_archived_markdown(self.archived))
        self.assertEqual(results, [])

    def test_nonexistent_dir(self):
        nonexistent = Path(self.tmp.name) / "does_not_exist"
        results = list(iter_all_archived_markdown(nonexistent))
        self.assertEqual(results, [])

    def test_unreadable_file_skipped(self):
        path = self.archived / "t1_unreadable.md"
        path.write_text("content")
        (self.archived / "t2_readable.md").write_text("readable")
        # Remove read permission
        path.chmod(0o000)
        try:
            results = list(iter_all_archived_markdown(self.archived))
            names = [r[0] for r in results]
            self.assertNotIn("t1_unreadable.md", names)
            self.assertIn("t2_readable.md", names)
        finally:
            path.chmod(0o644)

    def test_backward_compat_tar_gz(self):
        """Verify .tar.gz archives are still readable (backward compat)."""
        _make_tar_gz(
            self.archived / "_b0" / "old0.tar.gz",
            {"t50_legacy.md": "legacy content"},
        )
        results = list(iter_all_archived_markdown(self.archived))
        names = [r[0] for r in results]
        self.assertIn("t50_legacy.md", names)
        self.assertEqual(
            [r[1] for r in results if r[0] == "t50_legacy.md"],
            ["legacy content"],
        )

    def test_tar_zst_preferred_over_tar_gz(self):
        """When both .tar.zst and .tar.gz exist for same bundle, prefer .tar.zst."""
        _make_archive(
            self.archived / "_b0" / "old0.tar.zst",
            {"t50_task.md": "zst content"},
        )
        _make_tar_gz(
            self.archived / "_b0" / "old0.tar.gz",
            {"t50_task.md": "gz content"},
        )
        results = list(iter_all_archived_markdown(self.archived))
        contents = [r[1] for r in results if r[0] == "t50_task.md"]
        self.assertEqual(len(contents), 1)
        self.assertEqual(contents[0], "zst content")


class TestIterArchivedFrontmatter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.archived = Path(self.tmp.name) / "archived"
        self.archived.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _parse_fn(self, text: str):
        """Simple YAML-like parser for test fixtures."""
        if not text.startswith("---"):
            return None
        lines = text.split("\n")
        end = -1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end = i
                break
        if end < 0:
            return None
        meta = {}
        for line in lines[1:end]:
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        return meta

    def test_yields_metadata(self):
        (self.archived / "t1_task.md").write_text(
            "---\npriority: high\n---\nbody\n"
        )
        results = list(iter_archived_frontmatter(self.archived, self._parse_fn))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "t1_task.md")
        self.assertEqual(results[0][1]["priority"], "high")

    def test_skips_no_frontmatter(self):
        (self.archived / "t1_nofm.md").write_text("no frontmatter here\n")
        results = list(iter_archived_frontmatter(self.archived, self._parse_fn))
        self.assertEqual(results, [])

    def test_skips_parse_error(self):
        (self.archived / "t1_good.md").write_text(
            "---\npriority: low\n---\nbody\n"
        )
        (self.archived / "t2_bad.md").write_text("---\npriority: high\n---\n")

        def failing_parse(text):
            if "high" in text:
                raise ValueError("parse error")
            return self._parse_fn(text)

        results = list(iter_archived_frontmatter(self.archived, failing_parse))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "t1_good.md")


if __name__ == "__main__":
    unittest.main()
