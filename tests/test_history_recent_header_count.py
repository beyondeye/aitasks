"""Pilot tests: the codebrowser "Recently Opened (N)" header follows the list (t2343).

`HistoryLeftPane` used to recompute the header only in `_update_headers()`
(index load, progressive chunks, label filter). Opening a task goes through
`RecentlyOpenedList.add_to_history`, which re-rendered the rows but left the
header at its previous value — "Recently Opened (0)" above a list showing the
task. The list now posts `RecentlyOpenedList.Changed` after every rebuild and
the pane refreshes the header from it.

Every assertion compares the header against the rows actually mounted, so a
header that drifts from the list in either direction fails.

Run via ``bash tests/run_all_python_tests.sh`` or directly with unittest.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "codebrowser"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Static  # noqa: E402

from history_data import CompletedTask  # noqa: E402
from history_list import (  # noqa: E402
    HISTORY_FILE,
    MAX_RECENT,
    HistoryLeftPane,
    HistoryTaskItem,
    RecentlyOpenedList,
)


def _task(task_id: str, day: int) -> CompletedTask:
    return CompletedTask(
        task_id=task_id,
        name=f"task_{task_id}",
        issue_type="bug",
        labels=[],
        priority="medium",
        effort="medium",
        commit_date=f"2026-06-{day:02d}T10:00:00",
        commit_hash="deadbee",
        file_source="loose",
        metadata={},
        has_code_commits=True,
    )


class _HostApp(App):
    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self._project_root = project_root

    def compose(self) -> ComposeResult:
        yield HistoryLeftPane(self._project_root, id="history_left")


def _seed_history(root: Path, task_ids: list[str]) -> None:
    path = root / HISTORY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([{"task_id": t, "timestamp": "2026-06-01T00:00:00"} for t in task_ids]),
        encoding="utf-8",
    )


def _header(app: App) -> str:
    return str(app.query_one("#recent_header", Static).content)


def _rows(app: App) -> list[str]:
    recent = app.query_one("#recent_list", RecentlyOpenedList)
    return [i.completed_task.task_id for i in recent.query(HistoryTaskItem)]


class RecentHeaderCountTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, body) -> None:
        async def scenario():
            app = _HostApp(self.root)
            async with app.run_test() as pilot:
                await body(app, pilot)

        asyncio.run(scenario())

    def test_add_to_history_updates_header(self) -> None:
        index = [_task("20", 2), _task("10", 1)]

        async def body(app, pilot):
            pane = app.query_one(HistoryLeftPane)
            pane.set_data(index)
            await pilot.pause()
            self.assertEqual(_header(app), "Recently Opened (0)")
            self.assertEqual(_rows(app), [])

            recent = pane.get_recently_opened_list()
            recent.add_to_history("10")
            await pilot.pause()
            self.assertEqual(_rows(app), ["10"])
            self.assertEqual(_header(app), "Recently Opened (1)")

            recent.add_to_history("20")
            await pilot.pause()
            self.assertEqual(_rows(app), ["20", "10"])
            self.assertEqual(_header(app), "Recently Opened (2)")

            # Re-opening moves to the top without duplicating.
            recent.add_to_history("10")
            await pilot.pause()
            self.assertEqual(_rows(app), ["10", "20"])
            self.assertEqual(_header(app), "Recently Opened (2)")

        self._run(body)

    def test_unknown_task_not_counted(self) -> None:
        index = [_task("10", 1)]

        async def body(app, pilot):
            pane = app.query_one(HistoryLeftPane)
            pane.set_data(index)
            await pilot.pause()
            recent = pane.get_recently_opened_list()
            recent.add_to_history("10")
            await pilot.pause()
            recent.add_to_history("999")  # not in the index → no row
            await pilot.pause()
            self.assertEqual(_rows(app), ["10"])
            self.assertEqual(_header(app), "Recently Opened (1)")

        self._run(body)

    def test_unknown_task_evicts_shown_entry_at_cap(self) -> None:
        # add_to_history inserts, then trims to MAX_RECENT, before rows are
        # filtered against the index: an unknown id pushed onto a full list
        # evicts the oldest shown entry, so the count goes DOWN.
        ids = [str(100 + n) for n in range(MAX_RECENT)]
        index = [_task(t, n + 1) for n, t in enumerate(ids)]
        _seed_history(self.root, ids)

        async def body(app, pilot):
            pane = app.query_one(HistoryLeftPane)
            pane.set_data(index)
            await pilot.pause()
            self.assertEqual(_rows(app), ids)
            self.assertEqual(_header(app), f"Recently Opened ({MAX_RECENT})")

            pane.get_recently_opened_list().add_to_history("999")
            await pilot.pause()
            self.assertEqual(_rows(app), ids[: MAX_RECENT - 1])
            self.assertEqual(_header(app), f"Recently Opened ({MAX_RECENT - 1})")

        self._run(body)

    def test_preexisting_history_counted_on_load(self) -> None:
        _seed_history(self.root, ["10", "999"])

        async def body(app, pilot):
            pane = app.query_one(HistoryLeftPane)
            pane.set_data([_task("10", 1)])
            await pilot.pause()
            self.assertEqual(_rows(app), ["10"])
            self.assertEqual(_header(app), "Recently Opened (1)")

        self._run(body)


if __name__ == "__main__":
    unittest.main()
