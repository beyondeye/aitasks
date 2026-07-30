"""Store + policy tests for the cross-repo agent-marks primitive (t1326).

Covers `.aitask-scripts/lib/agent_marks.py` with no tmux, no Textual and no
event loop — the module is deliberately free of those imports so this suite can
exercise the persistence and purge policy directly.

The liveness rule gets its own module (`test_agent_marks_liveness.py`), because
its three-way distinction is the subtle part.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_marks  # noqa: E402


class _StoreTestCase(unittest.TestCase):
    """Gives each test an isolated store path under a temp dir."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.store = self.tmp / "agent_marks.json"
        self.addCleanup(self._tmp.cleanup)

    def seed(self, *entries: tuple[str, str]) -> None:
        mf = agent_marks.load(self.store)
        for root, window in entries:
            agent_marks.toggle(mf, root, window)
        agent_marks.dump(mf, self.store)


class PathResolutionTests(_StoreTestCase):
    def test_env_override_wins_over_default(self):
        os.environ[agent_marks.MARKS_ENV] = str(self.store)
        self.addCleanup(os.environ.pop, agent_marks.MARKS_ENV, None)
        self.assertEqual(agent_marks.marks_path(), self.store)

    def test_explicit_arg_wins_over_env(self):
        os.environ[agent_marks.MARKS_ENV] = "/nowhere/x.json"
        self.addCleanup(os.environ.pop, agent_marks.MARKS_ENV, None)
        self.assertEqual(agent_marks.marks_path(self.store), self.store)

    def test_default_is_under_config_aitasks(self):
        os.environ.pop(agent_marks.MARKS_ENV, None)
        self.assertEqual(
            agent_marks.marks_path(),
            Path(os.path.expanduser("~/.config/aitasks/agent_marks.json")),
        )


class RoundTripTests(_StoreTestCase):
    def test_toggle_on_then_off(self):
        mf = agent_marks.load(self.store)
        added = agent_marks.toggle(mf, "/repo/a", "agent-t1")
        self.assertTrue(added.now_marked)
        self.assertIsNotNone(added.record)
        removed = agent_marks.toggle(mf, "/repo/a", "agent-t1")
        self.assertFalse(removed.now_marked)
        self.assertEqual(mf.marks, [])

    def test_marked_at_is_recorded(self):
        mf = agent_marks.load(self.store)
        agent_marks.toggle(mf, "/repo/a", "agent-t1", now=1700000000)
        self.assertEqual(mf.marks[0].marked_at, 1700000000)

    def test_dump_load_round_trip(self):
        self.seed(("/repo/a", "agent-t1"), ("/repo/b", "agent-t2"))
        again = agent_marks.load(self.store)
        self.assertEqual(
            sorted(m.window for m in again.marks), ["agent-t1", "agent-t2"]
        )

    def test_store_is_created_mode_0600(self):
        self.seed(("/repo/a", "agent-t1"))
        self.assertEqual(self.store.stat().st_mode & 0o777, 0o600)

    def test_missing_file_is_an_empty_store_not_an_error(self):
        self.assertEqual(agent_marks.load(self.store).marks, [])

    def test_empty_file_is_an_empty_store(self):
        self.store.write_text("   \n", encoding="utf-8")
        self.assertEqual(agent_marks.load(self.store).marks, [])


class CanonicalizationTests(_StoreTestCase):
    """A mark must survive being written and read through different spellings
    of the same root — the classic two-marks-for-one-repo bug."""

    def setUp(self) -> None:
        super().setUp()
        self.real = self.tmp / "real_repo"
        self.real.mkdir()
        self.link = self.tmp / "linked_repo"
        try:
            self.link.symlink_to(self.real)
        except (OSError, NotImplementedError):  # pragma: no cover
            self.skipTest("symlinks unavailable")

    def test_write_via_symlink_reads_via_real_path(self):
        mf = agent_marks.load(self.store)
        agent_marks.toggle(mf, self.link, "agent-t1")
        agent_marks.dump(mf, self.store)
        self.assertTrue(agent_marks.load(self.store).is_marked(self.real, "agent-t1"))

    def test_write_via_real_path_reads_via_symlink(self):
        mf = agent_marks.load(self.store)
        agent_marks.toggle(mf, self.real, "agent-t1")
        agent_marks.dump(mf, self.store)
        self.assertTrue(agent_marks.load(self.store).is_marked(self.link, "agent-t1"))

    def test_toggling_via_the_other_spelling_removes_not_duplicates(self):
        mf = agent_marks.load(self.store)
        agent_marks.toggle(mf, self.real, "agent-t1")
        result = agent_marks.toggle(mf, self.link, "agent-t1")
        self.assertFalse(result.now_marked)
        self.assertEqual(mf.marks, [])

    def test_hand_edited_symlink_spelling_is_canonicalized_on_read(self):
        self.store.write_text(
            json.dumps({
                "version": 1,
                "marks": [
                    {"root": str(self.link), "window": "agent-t1",
                     "marked_at": 1700000000},
                ],
            }),
            encoding="utf-8",
        )
        self.assertTrue(agent_marks.load(self.store).is_marked(self.real, "agent-t1"))


class CorruptionTests(_StoreTestCase):
    """Read fails SAFE (render nothing); write fails LOUD (never clobber).

    The asymmetry is the point: a writer that treated a corrupt file as `{}`
    would round-trip an empty store over the user's marks.
    """

    def _assert_asymmetric(self):
        with self.assertRaises(agent_marks.MalformedMarksError):
            agent_marks.load(self.store)
        self.assertEqual(agent_marks.load_safe(self.store).marks, [])

    def test_malformed_json(self):
        self.store.write_text("{ not json", encoding="utf-8")
        self._assert_asymmetric()

    def test_truncated_json(self):
        self.store.write_text('{"version": 1, "marks": [{"root": "/a"', encoding="utf-8")
        self._assert_asymmetric()

    def test_top_level_not_an_object(self):
        self.store.write_text("[1, 2, 3]", encoding="utf-8")
        self._assert_asymmetric()

    def test_marks_not_a_list(self):
        self.store.write_text('{"version": 1, "marks": {}}', encoding="utf-8")
        self._assert_asymmetric()

    def test_entry_missing_fields(self):
        self.store.write_text(
            '{"version": 1, "marks": [{"root": "/a"}]}', encoding="utf-8"
        )
        self._assert_asymmetric()

    def test_marked_at_bool_is_rejected(self):
        # bool is a subclass of int; without an explicit guard `True` would pass.
        self.store.write_text(
            '{"version": 1, "marks": [{"root": "/a", "window": "w",'
            ' "marked_at": true}]}',
            encoding="utf-8",
        )
        self._assert_asymmetric()

    def test_path_is_a_directory(self):
        target = self.tmp / "as_dir"
        target.mkdir()
        with self.assertRaises(agent_marks.MalformedMarksError):
            agent_marks.load(target)
        self.assertEqual(agent_marks.load_safe(target).marks, [])

    def test_unreadable_file(self):
        self.seed(("/repo/a", "agent-t1"))
        os.chmod(self.store, 0o000)
        self.addCleanup(os.chmod, self.store, 0o600)
        if os.geteuid() == 0:  # pragma: no cover - root ignores the mode
            self.skipTest("running as root; permission bits are not enforced")
        self._assert_asymmetric()

    def test_older_version_is_refused_not_silently_upgraded(self):
        """Version 0 must not be accepted and rewritten as version 1.

        Rewriting it *is* a migration, and no migration exists — so accepting it
        would silently reinterpret fields under whatever v0 meant. Exact
        equality until a migration is written.
        """
        payload = '{"version": 0, "marks": []}'
        self.store.write_text(payload, encoding="utf-8")
        with self.assertRaises(agent_marks.MalformedMarksError):
            agent_marks.load(self.store)
        self.assertEqual(agent_marks.load_safe(self.store).marks, [])
        self.assertEqual(self.store.read_text(encoding="utf-8"), payload)

    def test_future_version_is_refused_not_truncated(self):
        payload = '{"version": 99, "marks": []}'
        self.store.write_text(payload, encoding="utf-8")
        with self.assertRaises(agent_marks.MalformedMarksError):
            agent_marks.load(self.store)
        # The writer refused, so the newer file must still be byte-intact.
        self.assertEqual(self.store.read_text(encoding="utf-8"), payload)

    def test_duplicate_entries_collapse_rather_than_raise(self):
        self.store.write_text(
            json.dumps({
                "version": 1,
                "marks": [
                    {"root": "/repo/a", "window": "w", "marked_at": 1},
                    {"root": "/repo/a", "window": "w", "marked_at": 2},
                ],
            }),
            encoding="utf-8",
        )
        self.assertEqual(len(agent_marks.load(self.store).marks), 1)


class ExpiryTests(_StoreTestCase):
    """TTL boundary, checked under / at / over."""

    NOW = 1_700_000_000.0
    DAY = 86400.0

    def _mf(self, age_days: float) -> agent_marks.MarksFile:
        mf = agent_marks.load(self.store)
        agent_marks.toggle(
            mf, "/repo/a", "agent-t1", now=int(self.NOW - age_days * self.DAY)
        )
        return mf

    def test_under_ttl_survives(self):
        mf = self._mf(1.0)
        self.assertEqual(agent_marks.expire(mf, ttl=2.0, now=self.NOW), [])
        self.assertEqual(len(mf.marks), 1)

    def test_exactly_at_ttl_survives(self):
        mf = self._mf(2.0)
        self.assertEqual(agent_marks.expire(mf, ttl=2.0, now=self.NOW), [])

    def test_over_ttl_is_dropped_and_returned(self):
        mf = self._mf(2.5)
        dropped = agent_marks.expire(mf, ttl=2.0, now=self.NOW)
        self.assertEqual([d.window for d in dropped], ["agent-t1"])
        self.assertEqual(mf.marks, [])

    def test_visible_marks_filters_without_mutating(self):
        mf = self._mf(2.5)
        self.assertEqual(agent_marks.visible_marks(mf, ttl=2.0, now=self.NOW), set())
        self.assertEqual(len(mf.marks), 1, "visible_marks must not mutate the store")


class TtlEnvTests(unittest.TestCase):
    """A typo must never silently expire every mark."""

    def tearDown(self) -> None:
        os.environ.pop(agent_marks.TTL_ENV, None)

    def test_absent_env_uses_default(self):
        os.environ.pop(agent_marks.TTL_ENV, None)
        self.assertEqual(agent_marks.ttl_days(), agent_marks.DEFAULT_TTL_DAYS)

    def test_valid_env_is_honoured(self):
        os.environ[agent_marks.TTL_ENV] = "7"
        self.assertEqual(agent_marks.ttl_days(), 7.0)

    def test_garbage_falls_back_to_default(self):
        for bad in ("2 days", "", "abc", "None"):
            with self.subTest(value=bad):
                os.environ[agent_marks.TTL_ENV] = bad
                self.assertEqual(agent_marks.ttl_days(), agent_marks.DEFAULT_TTL_DAYS)

    def test_non_positive_falls_back_to_default(self):
        for bad in ("0", "-1"):
            with self.subTest(value=bad):
                os.environ[agent_marks.TTL_ENV] = bad
                self.assertEqual(agent_marks.ttl_days(), agent_marks.DEFAULT_TTL_DAYS)


class MarksViewTests(_StoreTestCase):
    """The per-tick reader: correct, and free when nothing changed."""

    def _counting_view(self) -> tuple[agent_marks.MarksView, list[int]]:
        view = agent_marks.MarksView(self.store)
        calls: list[int] = []
        real = agent_marks.load_safe

        def counting(path=None):
            calls.append(1)
            return real(path)

        agent_marks.load_safe = counting
        self.addCleanup(setattr, agent_marks, "load_safe", real)
        return view, calls

    def test_reports_marked_state(self):
        self.seed(("/repo/a", "agent-t1"))
        view = agent_marks.MarksView(self.store)
        view.refresh()
        self.assertTrue(view.is_marked("/repo/a", "agent-t1"))
        self.assertFalse(view.is_marked("/repo/a", "agent-other"))
        self.assertFalse(view.is_marked("/repo/b", "agent-t1"))

    def test_unchanged_file_is_not_re_read(self):
        self.seed(("/repo/a", "agent-t1"))
        view, calls = self._counting_view()
        self.assertTrue(view.refresh())
        self.assertEqual(len(calls), 1)
        for _ in range(5):
            self.assertFalse(view.refresh(), "steady state must not re-read")
        self.assertEqual(len(calls), 1)

    def test_changed_file_is_re_read(self):
        self.seed(("/repo/a", "agent-t1"))
        view = agent_marks.MarksView(self.store)
        view.refresh()
        self.assertFalse(view.is_marked("/repo/a", "agent-t2"))
        # Force a distinct (mtime_ns, size) pair.
        time.sleep(0.01)
        self.seed(("/repo/a", "agent-t2"))
        self.assertTrue(view.refresh())
        self.assertTrue(view.is_marked("/repo/a", "agent-t2"))

    def test_invalidate_forces_a_re_read(self):
        """A toggle can land inside the same coarse mtime tick as the last read,
        which the stamp alone would not catch."""
        self.seed(("/repo/a", "agent-t1"))
        view, calls = self._counting_view()
        view.refresh()
        view.refresh()
        self.assertEqual(len(calls), 1)
        view.invalidate()
        self.assertTrue(view.refresh())
        self.assertEqual(len(calls), 2)

    def test_equal_size_replace_within_one_timestamp_is_still_detected(self):
        """The staleness trap this store is uniquely exposed to.

        A cross-repo mark flip is frequently *equal length* — one window name
        swapped for another of the same width — and the store is only ever
        replaced via ``os.replace``. On a coarse-granularity filesystem both
        ``st_mtime_ns`` and ``st_size`` can be unchanged across a real content
        change, so a ``(mtime, size)`` stamp would leave the other repo's final
        state invisible indefinitely. Every replace yields a new inode, which is
        what makes the stamp replacement-sensitive.

        The mtime is forced back deliberately: relying on a genuinely coarse
        filesystem would make this test pass vacuously on ext4/tmpfs.
        """
        now = int(time.time())
        first = agent_marks.MarksFile(
            version=agent_marks.SCHEMA_VERSION,
            marks=[agent_marks.MarkRecord("/repo/a", "agent-aaa", now)],
        )
        agent_marks.dump(first, self.store)
        before = os.stat(self.store)

        view = agent_marks.MarksView(self.store)
        view.refresh()
        self.assertTrue(view.is_marked("/repo/a", "agent-aaa"))

        second = agent_marks.MarksFile(
            version=agent_marks.SCHEMA_VERSION,
            marks=[agent_marks.MarkRecord("/repo/a", "agent-bbb", now)],
        )
        agent_marks.dump(second, self.store)
        os.utime(self.store, ns=(before.st_atime_ns, before.st_mtime_ns))
        after = os.stat(self.store)

        # Precondition: the (mtime, size) pair really is unchanged, so this test
        # is exercising the gap rather than a size difference.
        self.assertEqual(before.st_size, after.st_size)
        self.assertEqual(before.st_mtime_ns, after.st_mtime_ns)

        self.assertTrue(view.refresh(), "replacement was not detected")
        self.assertFalse(view.is_marked("/repo/a", "agent-aaa"), "stale mark survived")
        self.assertTrue(view.is_marked("/repo/a", "agent-bbb"))

    def test_missing_store_is_empty_not_an_error(self):
        view = agent_marks.MarksView(self.tmp / "absent.json")
        view.refresh()
        self.assertFalse(view.is_marked("/repo/a", "agent-t1"))

    def test_corrupt_store_renders_nothing_and_does_not_raise(self):
        self.store.write_text("{ not json", encoding="utf-8")
        view = agent_marks.MarksView(self.store)
        view.refresh()
        self.assertFalse(view.is_marked("/repo/a", "agent-t1"))

    def test_expired_marks_are_not_visible(self):
        mf = agent_marks.load(self.store)
        agent_marks.toggle(mf, "/repo/a", "old", now=int(time.time() - 10 * 86400))
        agent_marks.toggle(mf, "/repo/a", "new")
        agent_marks.dump(mf, self.store)
        view = agent_marks.MarksView(self.store)
        view.refresh()
        self.assertFalse(view.is_marked("/repo/a", "old"))
        self.assertTrue(view.is_marked("/repo/a", "new"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
