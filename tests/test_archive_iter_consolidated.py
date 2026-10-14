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
import unittest.mock
from pathlib import Path

# Load archive_iter from the lib directory
_lib_dir = Path(__file__).resolve().parents[1] / ".aitask-scripts" / "lib"
sys.path.insert(0, str(_lib_dir))

from archive_iter import (
    _is_child_filename,
    checked_glob,
    find_archived_markdown_by_id,
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


class TestFindArchivedMarkdownById(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.archived = Path(self.tmp.name) / "archived"
        self.archived.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_finds_loose_parent(self):
        (self.archived / "t12_parent.md").write_text("parent", encoding="utf-8")

        result = find_archived_markdown_by_id("12", self.archived)

        self.assertEqual(result, ("t12_parent.md", "parent"))

    def test_finds_loose_child(self):
        child_dir = self.archived / "t12"
        child_dir.mkdir()
        (child_dir / "t12_2_child.md").write_text("child", encoding="utf-8")

        result = find_archived_markdown_by_id("t12_2", self.archived)

        self.assertEqual(result, ("t12_2_child.md", "child"))

    def test_finds_numbered_tar_parent(self):
        _make_archive(
            self.archived / "_b0" / "old0.tar.zst",
            {"t50_task.md": "tar parent"},
        )

        result = find_archived_markdown_by_id("50", self.archived)

        self.assertEqual(result, ("t50_task.md", "tar parent"))

    def test_finds_numbered_tar_child(self):
        _make_archive(
            self.archived / "_b0" / "old0.tar.zst",
            {"t50/t50_2_child.md": "tar child"},
        )

        result = find_archived_markdown_by_id("50_2", self.archived)

        self.assertEqual(result, ("t50_2_child.md", "tar child"))

    def test_falls_back_to_legacy_archive(self):
        _make_archive(
            self.archived / "old.tar.zst",
            {"t999_legacy.md": "legacy"},
        )

        result = find_archived_markdown_by_id("999", self.archived)

        self.assertEqual(result, ("t999_legacy.md", "legacy"))

    def test_missing_returns_none(self):
        self.assertIsNone(find_archived_markdown_by_id("404", self.archived))


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


def _big_bundle(count: int = 400, size: int = 16000) -> dict[str, str]:
    """Enough content that zstd is still writing when a reader stops early."""
    return {f"t{i}_task.md": "---\nstatus: Done\n---\n" + "x" * size
            for i in range(1, count + 1)}


class TestOptInFailureReporting(unittest.TestCase):
    """The keyword-only ``errors`` list (t1957_3): every failure that could
    hide a record is reported, and the default path stays best-effort."""

    def setUp(self):
        # addCleanup, not tearDown: tearDown would run before the LIFO
        # cleanups that restore a locked directory's mode (_lock).
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.archived = Path(self.tmp.name) / "archived"
        self.archived.mkdir()
        self.bundle_dir = self.archived / "_b0"
        self.bundle_dir.mkdir()

    def _corrupt(self, name: str, blob: bytes) -> Path:
        path = self.bundle_dir / name
        path.write_bytes(blob)
        return path

    def _truncated_tar_gz(self, directory: Path, name: str) -> Path:
        """A valid bundle cut in half: gzip raises EOFError reading it."""
        path = directory / name
        _make_tar_gz(path, _big_bundle(count=40, size=4000))
        path.write_bytes(path.read_bytes()[: path.stat().st_size // 2])
        return path

    def test_corrupt_tar_gz_is_reported(self):
        path = self._corrupt("old0.tar.gz", b"not a gzip stream")
        errors: list = []
        self.assertEqual(list(iter_all_archived_markdown(self.archived,
                                                         errors=errors)), [])
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith(f"{path}: "), errors)

    def test_truncated_tar_gz_is_reported(self):
        path = self._truncated_tar_gz(self.bundle_dir, "old0.tar.gz")
        errors: list = []
        list(iter_all_archived_markdown(self.archived, errors=errors))
        self.assertEqual(len(errors), 1)
        self.assertIn(str(path), errors[0])

    def test_corrupt_tar_zst_is_reported(self):
        self._corrupt("old0.tar.zst", b"not a zstd frame")
        errors: list = []
        self.assertEqual(list(iter_all_archived_markdown(self.archived,
                                                         errors=errors)), [])
        self.assertEqual(len(errors), 1)

    def test_truncated_tar_zst_is_reported(self):
        """A stream cut short can end on a tar block boundary, which tarfile
        reads as a clean end of archive — only zstd's exit status tells."""
        path = self.bundle_dir / "old0.tar.zst"
        _make_archive(path, _big_bundle(count=40, size=4000))
        path.write_bytes(path.read_bytes()[: path.stat().st_size // 2])
        errors: list = []
        list(iter_all_archived_markdown(self.archived, errors=errors))
        self.assertEqual(len(errors), 1, errors)
        self.assertIn(str(path), errors[0])

    def test_zstd_failure_after_whole_members_is_reported(self):
        """The case only the exit status catches: zstd emits whole tar members
        (ending on a block boundary, no end-of-archive marker) and then fails
        on a corrupt trailing frame. tarfile sees a clean end of archive and
        yields every member, so nothing but the exit status says the bundle
        was cut short."""
        buf = io.BytesIO()
        tf = tarfile.open(fileobj=buf, mode="w")
        for name, content in {"t1_a.md": "a", "t2_b.md": "b"}.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content.encode()))
        members_only = buf.getvalue()[: buf.tell()]   # before the end marker
        frame = subprocess.run(["zstd", "-q", "-c"], input=members_only,
                               capture_output=True, check=True).stdout
        path = self.bundle_dir / "old0.tar.zst"
        path.write_bytes(frame + b"\x00garbage trailing frame")
        errors: list = []
        names = [n for n, _ in iter_all_archived_markdown(self.archived,
                                                          errors=errors)]
        self.assertEqual(names, ["t1_a.md", "t2_b.md"])
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("zstd exited", errors[0])

    def test_missing_zstd_binary_is_reported(self):
        _make_archive(self.bundle_dir / "old0.tar.zst", {"t1_a.md": "a"})
        empty_bin = Path(self.tmp.name) / "empty_bin"
        empty_bin.mkdir()
        errors: list = []
        with unittest.mock.patch.dict(os.environ, {"PATH": str(empty_bin)}):
            results = list(iter_all_archived_markdown(self.archived,
                                                      errors=errors))
        self.assertEqual(results, [])
        self.assertEqual(len(errors), 1)

    def test_unreadable_loose_file_is_reported(self):
        path = self.archived / "t1_locked.md"
        path.write_text("content")
        path.chmod(0o000)
        try:
            if os.access(path, os.R_OK):
                self.skipTest("running with permissions that ignore mode 000")
            errors: list = []
            list(iter_all_archived_markdown(self.archived, errors=errors))
            self.assertEqual(len(errors), 1)
            self.assertIn("t1_locked.md", errors[0])
        finally:
            path.chmod(0o644)

    def test_unparseable_task_frontmatter_is_reported(self):
        (self.archived / "t1_good.md").write_text("---\na: 1\n---\n")
        (self.archived / "t2_raises.md").write_text("---\nbad\n---\n")
        (self.archived / "t3_none.md").write_text("no frontmatter\n")
        (self.archived / "tnotes_readme.md").write_text("not a task\n")

        def parse(text):
            if "bad" in text:
                raise ValueError("boom")
            return {"a": 1} if text.startswith("---") else None

        errors: list = []
        results = list(iter_archived_frontmatter(self.archived, parse,
                                                 errors=errors))
        self.assertEqual([name for name, _meta in results], ["t1_good.md"])
        self.assertEqual(sorted(e.split(":")[0] for e in errors),
                         ["t2_raises.md", "t3_none.md"])

    def test_lookup_in_a_corrupt_bundle_cannot_prove_absence(self):
        self._corrupt("old0.tar.gz", b"garbage")
        errors: list = []
        self.assertIsNone(find_archived_markdown_by_id("5", self.archived,
                                                       errors=errors))
        self.assertEqual(len(errors), 1)

    def test_clean_miss_reports_nothing(self):
        _make_archive(self.bundle_dir / "old0.tar.zst", {"t1_a.md": "a"})
        errors: list = []
        self.assertIsNone(find_archived_markdown_by_id("7", self.archived,
                                                       errors=errors))
        self.assertEqual(errors, [])

    def test_early_stop_on_a_running_zstd_is_not_a_failure(self):
        """The lookup stops at the first match and closes the pipe while zstd
        is still writing; the SIGPIPE exit that follows must not be reported."""
        _make_archive(self.bundle_dir / "old0.tar.zst", _big_bundle())
        errors: list = []
        found = find_archived_markdown_by_id("1", self.archived, errors=errors)
        self.assertIsNotNone(found)
        self.assertEqual(found[0], "t1_task.md")
        self.assertEqual(errors, [])

    def test_complete_read_of_a_valid_bundle_reports_nothing(self):
        _make_archive(self.bundle_dir / "old0.tar.zst", _big_bundle())
        errors: list = []
        results = list(iter_all_archived_markdown(self.archived, errors=errors))
        self.assertEqual(len(results), 400)
        self.assertEqual(errors, [])

    def _lock(self, directory: Path) -> None:
        """Mode 000 for the test's duration (skips when it is not enforced)."""
        directory.chmod(0o000)
        self.addCleanup(directory.chmod, 0o755)
        if os.access(directory, os.R_OK):
            self.skipTest("running with permissions that ignore mode 000")

    def test_unlistable_archive_dir_is_reported_not_empty(self):
        """Path.glob swallows PermissionError: without the check an
        inaccessible archive would read exactly like an empty one."""
        (self.archived / "t1_a.md").write_text("a")
        self._lock(self.archived)
        errors: list = []
        self.assertEqual(list(iter_all_archived_markdown(self.archived,
                                                         errors=errors)), [])
        self.assertTrue(errors)
        self.assertTrue(all(str(self.archived) in e for e in errors), errors)

    def test_unlistable_child_dir_is_reported(self):
        child = self.archived / "t5"
        child.mkdir()
        (child / "t5_1_c.md").write_text("c")
        (self.archived / "t6_p.md").write_text("p")
        self._lock(child)
        errors: list = []
        names = [n for n, _ in iter_all_archived_markdown(self.archived,
                                                          errors=errors)]
        self.assertEqual(names, ["t6_p.md"])
        self.assertEqual(len(errors), 1)
        self.assertIn(str(child), errors[0])

    def test_unsearchable_bundle_dir_is_reported(self):
        _make_archive(self.bundle_dir / "old0.tar.zst", {"t5_x.md": "x"})
        self._lock(self.bundle_dir)
        errors: list = []
        self.assertIsNone(find_archived_markdown_by_id("5", self.archived,
                                                       errors=errors))
        self.assertTrue(errors)
        errors = []
        list(iter_all_archived_markdown(self.archived, errors=errors))
        self.assertTrue(errors)

    def test_checked_glob_matches_path_glob(self):
        (self.archived / "t1_a.md").write_text("a")
        (self.archived / "t2_3_b.md").write_text("b")
        (self.archived / "notes.md").write_text("n")
        (self.archived / "t4").mkdir()
        (self.archived / "t4" / "t4_1_c.md").write_text("c")
        _make_archive(self.bundle_dir / "old0.tar.zst", {"t5_x.md": "x"})
        _make_tar_gz(self.bundle_dir / "old0.tar.gz", {"t5_x.md": "x"})
        for pattern in ("t*_*.md", "t*/t*_*_*.md", "_b*/old*.tar.zst",
                        "_b*/old*.tar.gz", "t2_3_*.md", "missing/*.md"):
            errors: list = []
            self.assertEqual(checked_glob(self.archived, pattern, errors),
                             sorted(self.archived.glob(pattern)), pattern)
            self.assertEqual(errors, [], pattern)
        errors = []
        self.assertEqual(checked_glob(self.archived / "absent", "*.md",
                                      errors), [])
        self.assertEqual(errors, [], "an absent directory is not a failure")

    def test_default_path_stays_best_effort(self):
        """No list ⇒ the corrupt bundles are skipped silently, as before."""
        self._corrupt("old0.tar.gz", b"garbage")
        (self.archived / "_b1").mkdir()
        (self.archived / "_b1" / "old10.tar.zst").write_bytes(b"garbage")
        self.assertEqual(list(iter_all_archived_markdown(self.archived)), [])
        self.assertIsNone(find_archived_markdown_by_id("5", self.archived))

    def test_truncated_tar_gz_is_skipped_on_the_default_path(self):
        """gzip raises EOFError on a truncated stream and tarfile does not
        convert it; without a list the bundle is skipped like any other
        unreadable one, and the scan goes on to the next bundle."""
        self._truncated_tar_gz(self.bundle_dir, "old0.tar.gz")
        _make_tar_gz(self.archived / "_b1" / "old10.tar.gz",
                     {"t1000_ok.md": "ok"})
        self.assertEqual(
            [name for name, _ in iter_all_archived_markdown(self.archived)],
            ["t1000_ok.md"])
        self.assertIsNone(find_archived_markdown_by_id("5", self.archived))


if __name__ == "__main__":
    unittest.main()
