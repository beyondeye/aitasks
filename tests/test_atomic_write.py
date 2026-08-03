#!/usr/bin/env python3
"""Tests for lib/atomic_write.py and frontmatter_patch.py's use of it (t1371).

Two layers:

* Contract tests for the helper itself -- failure cleanup, mode preservation,
  umask derivation, symlink following.
* Integration tests proving the DEFECT is fixed: a hardlink probe. ``os.link``
  gives a second name for the task file's inode before the patch. An atomic
  rewrite renames a fresh inode over the path, so the probe still holds the
  ORIGINAL bytes; the old truncate-in-place write mutated the shared inode, so
  the probe would show the new content. That is the one assertion that
  discriminates the fix -- see the negative-control table in
  aiplans/archived/p1371_*.md. The mode / residue tests do NOT discriminate it
  (the old write preserved the mode and created no temp file); each defends the
  new implementation against a different tempfile-writer mistake.
"""

import importlib
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import atomic_write  # noqa: E402
import frontmatter_patch  # noqa: E402

STAMP = "2026-08-03 12:00"

TASK_FIXTURE = """\
---
priority: high
status: Ready
updated_at: 2020-01-01 00:00
artifacts:
  - handle: art_aaa
    kind: implementation_trail
    name: trail one
---

Body paragraph one.

Body paragraph two.
"""


class _TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def temps(self, directory):
        """Staged temp files left behind in ``directory``."""
        return sorted(p.name for p in Path(directory).iterdir()
                      if p.name.endswith(".tmp"))

    def mode_of(self, path):
        return stat.S_IMODE(os.stat(path).st_mode)

    def probe_umask(self):
        """Read the process umask independently of the module's own constant."""
        current = os.umask(0)
        os.umask(current)
        return current


class AtomicWriteContractTests(_TempDirCase):
    def existing(self, name="target.txt", text="old contents\n"):
        path = self.tmp / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_failed_replace_leaves_original_and_no_residue(self):
        target = self.existing()
        with mock.patch.object(atomic_write, "_os_replace",
                               side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                atomic_write.atomic_write_text(str(target), "new contents\n")

        self.assertEqual(target.read_text(encoding="utf-8"), "old contents\n")
        self.assertEqual(self.temps(self.tmp), [], "no .tmp residue")

    def test_render_failure_leaves_original_and_no_residue(self):
        target = self.existing()

        def exploding_render(fh):
            fh.write("partial")
            raise ValueError("render blew up")

        with self.assertRaises(ValueError):
            atomic_write.atomic_write(str(target), exploding_render)

        self.assertEqual(target.read_text(encoding="utf-8"), "old contents\n")
        self.assertEqual(self.temps(self.tmp), [], "no .tmp residue")

    def test_mode_is_preserved(self):
        for mode in (0o644, 0o600, 0o640):
            with self.subTest(mode=oct(mode)):
                target = self.existing(name=f"m{mode:o}.txt")
                os.chmod(target, mode)
                atomic_write.atomic_write_text(str(target), "new\n")
                self.assertEqual(
                    self.mode_of(target), mode,
                    "an atomic rewrite must not change the file's mode")

    def test_new_file_mode_respects_umask(self):
        target = self.tmp / "fresh.txt"
        atomic_write.atomic_write_text(str(target), "new\n")
        self.assertEqual(self.mode_of(target), 0o666 & ~self.probe_umask())

    def test_new_file_mode_tracks_a_changed_umask(self):
        """Under a restrictive umask the default must move with it.

        Without this, `test_new_file_mode_respects_umask` alone would pass for an
        implementation that hardcoded 0o644 -- the usual umask of 022 makes the
        derived and hardcoded answers identical.
        """
        previous = os.umask(0o077)
        try:
            reloaded = importlib.reload(atomic_write)
            target = self.tmp / "fresh_restrictive.txt"
            reloaded.atomic_write_text(str(target), "new\n")
            self.assertEqual(self.mode_of(target), 0o600)
        finally:
            os.umask(previous)
            importlib.reload(atomic_write)

    def test_creates_missing_parent_directories(self):
        target = self.tmp / "deep" / "nested" / "file.txt"
        atomic_write.atomic_write_text(str(target), "new\n")
        self.assertEqual(target.read_text(encoding="utf-8"), "new\n")

    def test_symlinked_target_is_followed_not_replaced(self):
        backing_dir = self.tmp / "real"
        backing_dir.mkdir()
        backing = backing_dir / "backing.txt"
        backing.write_text("old\n", encoding="utf-8")
        link = self.tmp / "link.txt"
        link.symlink_to(backing)

        atomic_write.atomic_write_text(str(link), "new\n")

        self.assertTrue(link.is_symlink(), "the link itself must survive")
        self.assertEqual(backing.read_text(encoding="utf-8"), "new\n",
                         "the write must reach the backing file")

    def test_prepare_commit_split_stages_before_visibility(self):
        target = self.existing()
        staged = atomic_write.prepare(str(target), lambda fh: fh.write("new\n"))
        self.assertEqual(target.read_text(encoding="utf-8"), "old contents\n",
                         "a staged write must not be visible yet")
        atomic_write.commit(staged, str(target))
        self.assertEqual(target.read_text(encoding="utf-8"), "new\n")


class FrontmatterPatchAtomicityTests(_TempDirCase):
    def task_file(self, mode=None):
        path = self.tmp / "t1_example.md"
        path.write_text(TASK_FIXTURE, encoding="utf-8")
        if mode is not None:
            os.chmod(path, mode)
        return path

    def hardlink_probe(self, path):
        """A second name for ``path``'s current inode, plus its bytes."""
        probe = self.tmp / (path.name + ".probe")
        os.link(path, probe)
        return probe, path.read_text(encoding="utf-8")

    def test_append_does_not_mutate_the_original_file_object(self):
        task = self.task_file()
        probe, original = self.hardlink_probe(task)

        frontmatter_patch.cmd_append(
            str(task), "artifacts", STAMP,
            {"handle": "art_bbb", "kind": "implementation_trail",
             "name": "trail two"})

        self.assertEqual(
            probe.read_text(encoding="utf-8"), original,
            "the pre-patch inode must be untouched -- a truncate-then-write "
            "would have mutated it in place, which is exactly the window a "
            "concurrent reader fell into")
        self.assertIn("art_bbb", task.read_text(encoding="utf-8"))
        self.assertNotEqual(os.stat(task).st_ino, os.stat(probe).st_ino,
                            "the patched path must be a freshly renamed inode")
        self.assertEqual(self.temps(self.tmp), [])

    def test_remove_does_not_mutate_the_original_file_object(self):
        task = self.task_file()
        probe, original = self.hardlink_probe(task)

        frontmatter_patch.cmd_remove(
            str(task), "artifacts", "handle", "art_aaa", STAMP)

        self.assertEqual(probe.read_text(encoding="utf-8"), original,
                         "the pre-patch inode must be untouched")
        self.assertNotIn("art_aaa", task.read_text(encoding="utf-8"))
        self.assertNotEqual(os.stat(task).st_ino, os.stat(probe).st_ino)
        self.assertEqual(self.temps(self.tmp), [])

    def test_patch_preserves_mode(self):
        # 0o640 is neither mkstemp's 0600 nor the usual umask default 0644, so
        # it fails for both ways a tempfile-based writer gets the mode wrong.
        task = self.task_file(mode=0o640)
        frontmatter_patch.cmd_append(
            str(task), "artifacts", STAMP, {"handle": "art_ccc"})
        self.assertEqual(self.mode_of(task), 0o640)

    def test_patch_content_is_unchanged_by_the_atomic_write(self):
        """The rewrite is byte-for-byte what the line splicer produced."""
        task = self.task_file()
        frontmatter_patch.cmd_append(
            str(task), "artifacts", STAMP, {"handle": "art_bbb"})
        text = task.read_text(encoding="utf-8")

        self.assertIn("updated_at: %s\n" % STAMP, text)
        self.assertIn("  - handle: art_aaa\n", text)
        self.assertIn("  - handle: art_bbb\n", text)
        self.assertTrue(text.endswith("Body paragraph two.\n"),
                        "the body must survive the rewrite verbatim")


if __name__ == "__main__":
    unittest.main()
