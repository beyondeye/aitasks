"""Pilot tests for History progressive-chunk reconciliation (t975).

`HistoryTaskList.update_index` receives a freshly re-sorted index for every
progressive chunk. Recently-archived child tasks arrive in a later chunk and
sort *into* a position the list has already paged past; the old implementation
left the mounted rows untouched, so those children never appeared (not even via
"Load more"). The fix re-renders the displayed window when its contents change,
while keeping a fast path that avoids re-mounting when the window is unchanged.

These tests drive ``set_index`` + ``update_index`` directly with chunk sequences
where children show up only in the later (fuller) index.

Run via ``bash tests/run_all_python_tests.sh`` or directly with unittest.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "codebrowser"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from textual.app import App, ComposeResult  # noqa: E402

from history_data import CompletedTask  # noqa: E402
from history_list import HistoryTaskList, HistoryTaskItem, _compute_child_counts  # noqa: E402


def _task(task_id: str, date: str, issue_type: str = "bug") -> CompletedTask:
    """Build a minimal CompletedTask; ``date`` drives the (caller-side) sort."""
    return CompletedTask(
        task_id=task_id,
        name=f"task_{task_id}",
        issue_type=issue_type,
        labels=[],
        priority="medium",
        effort="medium",
        commit_date=date,
        commit_hash="deadbee",
        file_source="loose",
        metadata={},
        has_code_commits=True,
    )


# Chunk 1 of the progressive load: loose parents only, sorted by date desc.
_CHUNK1 = [
    _task("973", "2026-06-10T10:00:00"),
    _task("972", "2026-06-09T10:00:00"),
    _task("953", "2026-06-08T10:00:00"),
    _task("950", "2026-06-03T10:00:00"),
    _task("940", "2026-06-02T10:00:00"),
]

# Final index: same parents plus recent CHILD tasks that sort into the top of
# the list (dates between t953 and t950), as the real loader would yield once
# the loose-child subdirs are scanned.
_CHILDREN = [
    _task("891_3", "2026-06-07T10:00:00"),
    _task("891_2", "2026-06-06T10:00:00"),
    _task("891_1", "2026-06-05T10:00:00"),
]
_FINAL = sorted(
    _CHUNK1 + _CHILDREN, key=lambda t: t.commit_date, reverse=True
)
# Sanity: children really do land in the first 5 positions of the final index.
assert [t.task_id for t in _FINAL[:5]] == ["973", "972", "953", "891_3", "891_2"]


class _HostApp(App):
    """Mounts a single HistoryTaskList."""

    def compose(self) -> ComposeResult:
        yield HistoryTaskList(id="history_list")


def _displayed_ids(task_list: HistoryTaskList) -> list[str]:
    return [it.completed_task.task_id for it in task_list.query(HistoryTaskItem)]


class TestProgressiveReconcile(unittest.TestCase):

    def _run(self, coro):
        return asyncio.run(coro)

    def test_children_surface_after_later_chunk(self):
        """A child arriving in a later chunk re-renders into the visible window."""

        async def runner():
            app = _HostApp()
            async with app.run_test(size=(60, 30)) as pilot:
                await pilot.pause()
                tl = app.query_one(HistoryTaskList)

                # Chunk 1: only parents are loaded and displayed.
                tl.set_index(_CHUNK1, _compute_child_counts(_CHUNK1))
                await pilot.pause()
                self.assertEqual(_displayed_ids(tl), [t.task_id for t in _CHUNK1])
                self.assertNotIn("891_3", _displayed_ids(tl))
                offset_before = tl._offset

                # Later chunk re-sorts the index; children sort into the window.
                tl.update_index(_FINAL)
                await pilot.pause()
                shown = _displayed_ids(tl)
                # The displayed window now interleaves the recent children...
                self.assertIn("891_3", shown)
                self.assertIn("891_2", shown)
                # ...exactly as the freshly re-sorted top-N window.
                self.assertEqual(shown, [t.task_id for t in _FINAL[:offset_before]])
                # The number of loaded rows (offset) is preserved.
                self.assertEqual(tl._offset, offset_before)

        self._run(runner())

    def test_load_more_never_skips(self):
        """After reconciliation, displayed + one Load-more covers the full index."""

        async def runner():
            app = _HostApp()
            async with app.run_test(size=(60, 30)) as pilot:
                await pilot.pause()
                tl = app.query_one(HistoryTaskList)
                tl.set_index(_CHUNK1, _compute_child_counts(_CHUNK1))
                await pilot.pause()
                tl.update_index(_FINAL)
                await pilot.pause()

                # One "Load more" pulls in the rest with no gaps or dupes.
                self.assertTrue(tl._has_more)
                tl._load_chunk()
                await pilot.pause()
                shown = _displayed_ids(tl)
                self.assertEqual(sorted(shown), sorted(t.task_id for t in _FINAL))
                self.assertEqual(len(shown), len(set(shown)))  # no duplicates
                self.assertFalse(tl._has_more)

        self._run(runner())

    def test_unchanged_window_uses_fast_path(self):
        """When the visible window is unchanged, rows are not re-mounted."""

        async def runner():
            app = _HostApp()
            async with app.run_test(size=(60, 30)) as pilot:
                await pilot.pause()
                tl = app.query_one(HistoryTaskList)
                tl.set_index(_CHUNK1, _compute_child_counts(_CHUNK1))
                await pilot.pause()
                items_before = list(tl.query(HistoryTaskItem))

                # A later chunk that only appends an OLDER task below the fold
                # leaves the top-N window identical -> fast path, same widgets.
                appended = _CHUNK1 + [_task("800", "2026-06-01T10:00:00")]
                tl.update_index(appended)
                await pilot.pause()
                items_after = list(tl.query(HistoryTaskItem))
                self.assertEqual(
                    [id(w) for w in items_before], [id(w) for w in items_after]
                )
                # ...but the Load-more indicator now reflects the new tail.
                self.assertTrue(tl._has_more)

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
