"""Regression tests for board view-mode filters (t751).

The board's view-mode filters (`a` All, `g` Git, `i` Implementing, `t` Type)
are wired through `KanbanApp._set_view_mode` -> `refresh_board` -> `apply_filter`.
The previous implementation called `apply_filter` synchronously immediately
after `container.mount(KanbanColumn(...))`. In Textual the new column's
`compose()` (which yields the TaskCards) runs asynchronously when the Mount
event is processed, so the synchronous `query(TaskCard)` could not see the
freshly composed cards and the filter silently no-op'd — every card stayed
visible.

These tests drive the real KanbanApp via `Pilot` against the live repo data
and assert the post-filter visible set matches the algorithm's intent.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_view_filter.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))


def _visible(cards):
    return [c for c in cards if c.styles.display != "none"]


def _filenames(cards):
    return sorted(c.task_data.filename for c in cards)


class BoardViewFilterTests(unittest.TestCase):
    """End-to-end Pilot tests covering the refresh_board → apply_filter race.

    Runs against the live `aitasks/` directory because KanbanApp resolves its
    paths from cwd at import time. The tests don't assert specific filenames —
    only that the visible set equals what the corresponding *_visible_set()
    helper returns. So they stay green regardless of which tasks happen to be
    in the repo.
    """

    @classmethod
    def setUpClass(cls):
        cls._orig_cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        # Import after chdir so module-level Path("aitasks") resolves correctly.
        from aitask_board import KanbanApp, TaskCard  # noqa: E402
        cls.KanbanApp = KanbanApp
        cls.TaskCard = TaskCard

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro) \
            if False else asyncio.run(coro)

    async def _assert_view(self, mode_key: str, expected_set_attr: str | None):
        """Press `mode_key`, then assert visible filenames == expected set.

        `expected_set_attr` is the name of the helper on KanbanApp that
        returns the intended visible filename set (e.g.
        `_implementing_visible_set`). When `None`, the view should be "all"
        and every card is expected visible.
        """
        app = self.KanbanApp()
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause()
            # Sanity: starting view is "all", every card visible.
            cards = list(app.query(self.TaskCard))
            self.assertGreater(len(cards), 0,
                               "test repo must contain at least one task")
            self.assertEqual(len(_visible(cards)), len(cards),
                             "before filter, all cards must be visible")

            await pilot.press(mode_key)
            await pilot.pause()
            # Allow one extra refresh tick — call_after_refresh schedules our
            # apply_filter for the *next* refresh, and pilot.pause() only
            # guarantees one tick.
            await pilot.pause()

            cards = list(app.query(self.TaskCard))
            visible = _visible(cards)

            if expected_set_attr is None:
                self.assertEqual(_filenames(visible), _filenames(cards),
                                 "All view must show every card")
                return

            expected = getattr(app, expected_set_attr)()
            # The intended set is computed against the manager's task_datas.
            # Some cards in the DOM may belong to old, mid-removal columns that
            # the filter does not narrow (it only sets display on what it sees).
            # Constrain the comparison to cards whose filename is currently in
            # the manager — those are the ones the filter is responsible for.
            live_filenames = (set(app.manager.task_datas)
                              | set(app.manager.child_task_datas))
            visible_live = [c for c in visible
                            if c.task_data.filename in live_filenames]
            visible_set_live = {c.task_data.filename for c in visible_live}

            # Every visible (live) card must be in the intended set.
            self.assertTrue(
                visible_set_live.issubset(expected),
                f"{mode_key!r}: visible cards {visible_set_live - expected} "
                f"leaked past filter (expected subset of {len(expected)} entries)")

            # Every card whose filename IS in the intended set must be visible.
            for card in cards:
                if card.task_data.filename in expected:
                    self.assertNotEqual(
                        card.styles.display, "none",
                        f"{mode_key!r}: card {card.task_data.filename} should "
                        f"be visible (in intended set) but was hidden")

    def test_implementing_filter_hides_non_matching(self):
        async def go():
            await self._assert_view("i", "_implementing_visible_set")
        self._run(go())

    def test_git_filter_hides_non_matching(self):
        async def go():
            await self._assert_view("g", "_git_visible_set")
        self._run(go())

    def test_back_to_all_restores_visibility(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await pilot.press("i")
                await pilot.pause()
                await pilot.pause()
                # Now back to all.
                await pilot.press("a")
                await pilot.pause()
                await pilot.pause()
                cards = list(app.query(self.TaskCard))
                hidden = [c for c in cards if c.styles.display == "none"]
                self.assertEqual(hidden, [],
                                 "after pressing 'a', no cards should be hidden")
        self._run(go())


if __name__ == "__main__":
    unittest.main()
