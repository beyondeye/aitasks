#!/usr/bin/env python3
"""Atomicity of the Python task/plan-file writers converted in t1379.

t1371 closed the `frontmatter_patch` window and created `lib/atomic_write.py`;
this covers the writers t1371 recorded as upstream defects and t1379 converted:

* `board.aitask_board.Task.save` — the board's own task-file writer
* `board.aitask_merge` — the sync conflict-resolution writer
* `diffviewer.merge_engine.write_merged_plan` — extracted out of the Textual
  `SaveMergeDialog.on_save` precisely so it can be tested without a `Pilot`

**The hardlink probe is the assertion that discriminates the fix**, and only for
truncate-in-place writes, which is all three of these. `os.link` gives a second
name for the file's inode before the write; an atomic replacement renames a
fresh inode over the path, so the probe still holds the ORIGINAL bytes, while
`open(path, "w")` / `Path.write_text` mutate the shared inode and the probe
shows the new content.

It is NOT evidence about a cross-device rename: a real cross-device `mv` also
leaves the probe on the old bytes with a new inode at the path. Nothing here
claims otherwise — the shell suite (`tests/test_atomic_write_sh.sh`) asserts the
staging *location*, which is the property that rules a cross-device rename out.

Negative controls — one mutation per test:

    | test                          | mutation that must make it fail        |
    |-------------------------------|----------------------------------------|
    | task_save_*                   | restore `open(self.filepath, "w")`     |
    | merge_*                       | restore `filepath.write_text(...)`     |
    | write_merged_plan_*           | restore the `open(path, "w")` block    |

Run each with PYTHONDONTWRITEBYTECODE=1 and confirm the failing test id is the
expected one: same-size mutations otherwise collide in CPython's pyc cache,
which is keyed on (source mtime in whole seconds, source size) — the trap t1371
hit.
"""

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "lib"))
sys.path.insert(0, str(SCRIPTS / "board"))

TASK_FIXTURE = """\
---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [test]
created_at: 2026-01-01 00:00
updated_at: 2026-01-01 00:00
---

Body paragraph one.

Body paragraph two.
"""


class _ProbeCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def hardlink_probe(self, path):
        """A second name for ``path``'s current inode, plus its bytes."""
        probe = path.with_name(path.name + ".probe")
        os.link(path, probe)
        return probe, path.read_text(encoding="utf-8")

    def assert_replaced_not_mutated(self, path, probe, original, must_contain):
        self.assertEqual(
            probe.read_text(encoding="utf-8"), original,
            "the pre-write inode must be untouched — a truncate-then-write "
            "mutates it in place, which is the window a concurrent "
            "frontmatter reader falls into")
        self.assertIn(must_contain, path.read_text(encoding="utf-8"))
        self.assertNotEqual(
            os.stat(path).st_ino, os.stat(probe).st_ino,
            "the written path must be a freshly renamed inode")

    def temps(self, directory):
        return sorted(p.name for p in Path(directory).iterdir()
                      if p.name.startswith(".") and p.name.endswith(".tmp"))

    def mode_of(self, path):
        return stat.S_IMODE(os.stat(path).st_mode)


class TaskSaveTests(_ProbeCase):
    """board/aitask_board.py — Task.save (reachable from ~12 call sites)."""

    def task(self, name="t1_example.md", mode=None):
        path = self.tmp / name
        path.write_text(TASK_FIXTURE, encoding="utf-8")
        if mode is not None:
            os.chmod(path, mode)
        import aitask_board
        return path, aitask_board.Task(path)

    def test_save_does_not_mutate_the_original_file_object(self):
        path, task = self.task()
        probe, original = self.hardlink_probe(path)

        task.metadata["status"] = "Implementing"
        task.save()

        self.assert_replaced_not_mutated(path, probe, original,
                                         "status: Implementing")
        self.assertEqual(self.temps(self.tmp), [])

    def test_save_preserves_mode(self):
        # 0o640 is neither mkstemp's 0600 nor the umask default 0644, so it
        # fails for both ways a tempfile-based writer gets the mode wrong.
        path, task = self.task(mode=0o640)
        task.metadata["status"] = "Implementing"
        task.save()
        self.assertEqual(self.mode_of(path), 0o640)

    def test_save_preserves_body(self):
        path, task = self.task()
        task.metadata["status"] = "Implementing"
        task.save()
        text = path.read_text(encoding="utf-8")
        self.assertIn("Body paragraph one.", text)
        self.assertIn("Body paragraph two.", text)


class MergeWriteTests(_ProbeCase):
    """board/aitask_merge.py — the sync conflict-resolution writer."""

    CONFLICTED = """\
---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [test]
<<<<<<< HEAD
boardidx: 10
=======
boardidx: 20
>>>>>>> origin/aitask-data
created_at: 2026-01-01 00:00
updated_at: 2026-01-01 00:00
---

Body.
"""

    def test_merge_does_not_mutate_the_original_file_object(self):
        path = self.tmp / "t1_example.md"
        path.write_text(self.CONFLICTED, encoding="utf-8")
        probe, original = self.hardlink_probe(path)

        # Driven through the real CLI entry point rather than an imported
        # main(): that is the surface aitask_sync.sh invokes.
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "board" / "aitask_merge.py"),
             str(path), "--batch"],
            capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": str(SCRIPTS / "board"),
                 "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        merged = path.read_text(encoding="utf-8")
        self.assertNotIn("<<<<<<<", merged, "conflict markers must be resolved")
        self.assertEqual(
            probe.read_text(encoding="utf-8"), original,
            "the pre-merge inode must be untouched")
        self.assertNotEqual(os.stat(path).st_ino, os.stat(probe).st_ino)
        self.assertEqual(self.temps(self.tmp), [])


class WriteMergedPlanTests(_ProbeCase):
    """diffviewer/merge_engine.py — write_merged_plan."""

    def call(self, path, meta=None, lines=None):
        from diffviewer.merge_engine import write_merged_plan
        write_merged_plan(
            str(path),
            meta if meta is not None else {"Task": "t1_x.md",
                                           "merged_from": ["a.md", "b.md"]},
            lines if lines is not None else ["body line one\n", "body line two\n"],
        )

    def test_overwrite_does_not_mutate_the_original_file_object(self):
        path = self.tmp / "p1_merged.md"
        path.write_text("OLD PLAN\n", encoding="utf-8")
        probe, original = self.hardlink_probe(path)

        self.call(path)

        self.assert_replaced_not_mutated(path, probe, original, "body line one")
        self.assertEqual(self.temps(self.tmp), [])

    def test_renders_frontmatter_and_body(self):
        path = self.tmp / "p1_merged.md"
        self.call(path)
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        self.assertIn("Task: t1_x.md\n", text)
        self.assertIn("merged_from: [a.md, b.md]\n", text)
        self.assertIn("---\n\nbody line one\nbody line two\n", text)

    def test_creates_missing_directory(self):
        path = self.tmp / "nested" / "dir" / "p1_merged.md"
        self.call(path)
        self.assertIn("body line one", path.read_text(encoding="utf-8"))

    def test_preserves_mode_of_an_existing_plan(self):
        path = self.tmp / "p1_merged.md"
        path.write_text("OLD PLAN\n", encoding="utf-8")
        os.chmod(path, 0o640)
        self.call(path)
        self.assertEqual(self.mode_of(path), 0o640)


if __name__ == "__main__":
    unittest.main()
