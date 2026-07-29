"""Unit tests for TaskInfoCache file-identity freshness (t1322).

Before t1322 a resolved entry was immortal: ``get_task_info`` cached on
``(session_name, task_id)`` with no TTL and no file key, so a task archived
while a monitor TUI was open served its pre-archival ``TaskInfo`` forever. That
made a COMPLETED agent status impossible to detect.

These tests pin the replacement contract — an ``(st_mtime_ns, st_size)``
identity gate, re-resolution (never fail-closed) when the file moves, and a
negative-entry backoff that decays to a sparse interval but never stops.

No sleeps: the clock is injected via ``cache._now`` and mtimes are moved with
``os.utime`` (per aidocs/framework/testing_conventions.md).
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from monitor.monitor_shared import TaskInfoCache  # noqa: E402


def _task_text(title: str, status: str = "Ready") -> str:
    return (
        "---\n"
        "priority: medium\n"
        "effort: medium\n"
        f"status: {status}\n"
        "issue_type: bug\n"
        "---\n\n"
        f"# {title}\n\n"
        "body line\n"
    )


def _write_task(path: Path, title: str, status: str = "Ready") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_task_text(title, status), encoding="utf-8")


def _bump_mtime(path: Path, seconds: int = 1) -> None:
    """Move a file's mtime forward deterministically (no sleep)."""
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + seconds * 1_000_000_000))


def _pin_mtime(path: Path, identity_source: os.stat_result) -> None:
    """Force a file's mtime back to another stat's value (same-mtime case)."""
    os.utime(path, ns=(identity_source.st_atime_ns, identity_source.st_mtime_ns))


class FreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "aitasks").mkdir()
        (self.root / "aiplans").mkdir()
        self.cache = TaskInfoCache(self.root)

        # Count _resolve calls: the only way to tell "served from cache" from
        # "re-read and happened to match".
        self.resolves = {"n": 0}
        orig = TaskInfoCache._resolve

        def counting(inner_self, *a, **k):
            self.resolves["n"] += 1
            return orig(inner_self, *a, **k)

        TaskInfoCache._resolve = counting
        self.addCleanup(setattr, TaskInfoCache, "_resolve", orig)

        # Injected monotonic clock for the negative-retry schedule.
        self.clock = 1000.0
        self.cache._now = lambda: self.clock

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- positive entries ---------------------------------------------------

    def test_unchanged_file_resolved_once(self) -> None:
        """Cost negative control: an unchanged task is never re-read.

        Fails if someone "fixes" staleness by dropping the cache entirely.
        """
        _write_task(self.root / "aitasks/t100_foo.md", "Foo")
        self.assertEqual(self.cache.get_task_info("100").title, "Foo")
        self.assertEqual(self.cache.get_task_info("100").title, "Foo")
        self.assertEqual(self.resolves["n"], 1)

    def test_in_place_status_edit_is_seen(self) -> None:
        """The pre-move rewrite: aitask_archive.sh sets Done before it moves."""
        p = self.root / "aitasks/t100_foo.md"
        _write_task(p, "Foo", status="Ready")
        self.assertEqual(self.cache.get_task_info("100").status, "Ready")

        _write_task(p, "Foo", status="Done")
        _bump_mtime(p)
        self.assertEqual(self.cache.get_task_info("100").status, "Done")
        self.assertEqual(self.resolves["n"], 2)

    def test_archive_move_reresolves_to_archived(self) -> None:
        """THE feature: status flips to Done and the path moves to archived/.

        Reverting the freshness fix fails on ``'Ready' != 'Done'``. The
        assertIsNotNone guards the *wrong* fix — copying GateSummaryCache's
        fail-closed-on-OSError behaviour, which would blank the pane's task on
        exactly the tick it completes.
        """
        src = self.root / "aitasks/t100_foo.md"
        _write_task(src, "Foo", status="Ready")
        self.assertEqual(self.cache.get_task_info("100").status, "Ready")

        # Simulate aitask_archive.sh: rewrite status in place, then MOVE.
        src.write_text(_task_text("Foo", status="Done"), encoding="utf-8")
        dst = self.root / "aitasks/archived/t100_foo.md"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))

        info = self.cache.get_task_info("100")
        self.assertIsNotNone(info)
        self.assertEqual(info.status, "Done")
        self.assertIn("archived", info.task_file)
        self.assertEqual(self.resolves["n"], 2)

    def test_same_mtime_different_size_is_seen(self) -> None:
        """Keying on st_mtime_ns alone is not enough.

        Needed separately from the move case: shutil.move preserves mtime, so
        the move is caught by ENOENT rather than by the size component.
        """
        p = self.root / "aitasks/t100_foo.md"
        _write_task(p, "Short")
        before = p.stat()
        self.assertEqual(self.cache.get_task_info("100").title, "Short")

        _write_task(p, "A considerably longer title than before")
        _pin_mtime(p, before)
        self.assertEqual(
            self.cache.get_task_info("100").title,
            "A considerably longer title than before",
        )

    def test_identity_sampled_before_read(self) -> None:
        """The ordering trap: stat-after-read pins stale content permanently.

        The archive script's rewrites are rename-based, so a read racing a
        rewrite returns the OLD bytes. Simulated by a read_text that bumps the
        file's mtime as a side effect: if the identity were sampled after the
        read, it would record the post-rewrite identity for pre-rewrite content
        and never re-resolve again.
        """
        p = self.root / "aitasks/t100_foo.md"
        _write_task(p, "Foo")

        orig_read = Path.read_text

        def racing_read(inner_self, *a, **k):
            data = orig_read(inner_self, *a, **k)
            if inner_self == p:
                _bump_mtime(p)
            return data

        Path.read_text = racing_read
        self.addCleanup(setattr, Path, "read_text", orig_read)

        self.cache.get_task_info("100")
        self.assertEqual(self.resolves["n"], 1)
        # The on-disk identity is now newer than what was sampled, so the next
        # lookup MUST re-resolve rather than trust the entry.
        self.cache.get_task_info("100")
        self.assertEqual(self.resolves["n"], 2)

    # -- negative entries ---------------------------------------------------

    def test_negative_entry_not_reglobbed_every_call(self) -> None:
        """An unresolvable id must not cost a directory glob per tick."""
        for _ in range(3):
            self.assertIsNone(self.cache.get_task_info("999"))
        self.assertEqual(self.resolves["n"], 1)

    def test_negative_entry_retried_after_backoff(self) -> None:
        """A miss caused by a transient (an archive rename window) recovers."""
        self.assertIsNone(self.cache.get_task_info("999"))
        _write_task(self.root / "aitasks/t999_late.md", "Late")

        self.clock += 1.0                      # inside the first backoff step
        self.assertIsNone(self.cache.get_task_info("999"))
        self.clock += 10.0                     # past it
        self.assertIsNotNone(self.cache.get_task_info("999"))

    def test_negative_retry_backs_off_but_never_stops(self) -> None:
        """The recovery guarantee: the schedule decays but never terminates.

        A budget that stopped would permanently poison a pane whose miss
        outlived it — an interrupted archive, or a long .aitask-data
        reconciliation — with nothing else guaranteeing recovery.
        """
        self.assertIsNone(self.cache.get_task_info("999"))
        # Walk past every backoff step so the entry reaches the terminal one.
        for step in TaskInfoCache._MISS_RETRY_SCHEDULE:
            self.clock += step + 1.0
            self.assertIsNone(self.cache.get_task_info("999"))
        exhausted = self.resolves["n"]

        # Still firing, at the terminal interval — not stopped.
        _write_task(self.root / "aitasks/t999_late.md", "Late")
        self.clock += TaskInfoCache._MISS_RETRY_TERMINAL - 1.0
        self.assertIsNone(self.cache.get_task_info("999"))
        self.assertEqual(self.resolves["n"], exhausted)

        self.clock += 2.0
        self.assertIsNotNone(self.cache.get_task_info("999"))

    def test_negative_retry_is_sparse_at_steady_state(self) -> None:
        """The cost side: a permanent miss costs one resolve per interval."""
        self.assertIsNone(self.cache.get_task_info("999"))
        for step in TaskInfoCache._MISS_RETRY_SCHEDULE:
            self.clock += step + 1.0
            self.cache.get_task_info("999")
        baseline = self.resolves["n"]

        # An hour of 3-second ticks must not mean an hour of globs.
        for _ in range(1200):
            self.clock += 3.0
            self.cache.get_task_info("999")
        elapsed = 1200 * 3.0
        expected_max = int(elapsed / TaskInfoCache._MISS_RETRY_TERMINAL) + 1
        self.assertLessEqual(self.resolves["n"] - baseline, expected_max)

    def test_explicit_invalidate_resets_miss_budget(self) -> None:
        """invalidate() is still the immediate retry for a cached negative."""
        self.assertIsNone(self.cache.get_task_info("999"))
        _write_task(self.root / "aitasks/t999_late.md", "Late")

        # Backoff not yet due — a plain lookup still says None.
        self.assertIsNone(self.cache.get_task_info("999"))
        # The user's explicit gesture must not have to wait for it.
        self.cache.invalidate("999")
        self.assertIsNotNone(self.cache.get_task_info("999"))

    # -- cross-project ------------------------------------------------------

    def test_update_session_mapping_still_clears(self) -> None:
        """The identity key CANNOT catch a project-root switch.

        The old root's path may still stat fine (a real t100 in the fallback
        project), so the gate would serve the wrong project's task forever.
        Deleting the clear() as "now redundant" must fail here.
        """
        _write_task(self.root / "aitasks/t100_foo.md", "Local Foo")
        self.assertEqual(self.cache.get_task_info("100", "sessA").title, "Local Foo")
        self.assertEqual(self.resolves["n"], 1)

        other = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, other, True)
        (other / "aitasks").mkdir()
        (other / "aiplans").mkdir()
        _write_task(other / "aitasks/t100_foo.md", "Other Foo")

        self.cache.update_session_mapping({"sessA": other})
        self.assertEqual(self.cache.get_task_info("100", "sessA").title, "Other Foo")
        self.assertEqual(self.resolves["n"], 2)


if __name__ == "__main__":
    unittest.main()
