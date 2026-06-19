"""End-to-end Pilot tests for the board by-topic view (t1016_4).

Pressing `y` switches the board into the group-by-anchor "by-topic" base view:
`refresh_board` re-buckets tasks into TopicColumn swimlanes via
`group_tasks_by_topic`, and `apply_filter` keeps every eligible card visible
(so search / git / type add-ons still apply on top). Mirrors the inflight-view
harness in tests/test_board_view_filter.py.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_topic_view.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))


class BoardTopicViewTests(unittest.TestCase):
    """Drives the real KanbanApp via Pilot against the live `aitasks/` repo."""

    @classmethod
    def setUpClass(cls):
        cls._orig_cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        from aitask_board import KanbanApp, TaskCard, TopicColumn  # noqa: E402
        cls.KanbanApp = KanbanApp
        cls.TaskCard = TaskCard
        cls.TopicColumn = TopicColumn

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)

    def _run(self, coro):
        return asyncio.run(coro)

    async def _enter_bytopic(self, app, pilot):
        """Press 'y' and let the board re-render settle. By-topic builds from
        in-memory tasks (no disk reload / worker), so a couple of pauses suffice."""
        await pilot.press("y")
        await pilot.pause()
        await pilot.pause()

    def test_bytopic_renders_topic_columns(self):
        """Pressing 'y' enters bytopic and mounts TopicColumn swimlanes."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                self.assertGreater(len(list(app.query(self.TaskCard))), 0,
                                   "test repo must contain at least one task")
                await self._enter_bytopic(app, pilot)
                self.assertEqual(app.base_filter, "bytopic")
                columns = list(app.query(self.TopicColumn))
                if not columns:
                    self.skipTest("no topic lanes in the live repo")
                # Every card under bytopic must be visible (no base hiding).
                hidden = [c for c in app.query(self.TaskCard)
                          if c.styles.display == "none"]
                self.assertEqual(hidden, [],
                                 "bytopic shows all eligible cards by default")
        self._run(go())

    def test_bytopic_does_not_force_disk_reload(self):
        """Entering bytopic builds from in-memory tasks (like all/locked/free) —
        it must NOT force a full task-file reload, which made the view slow."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                with patch.object(app.manager, "load_tasks",
                                  wraps=app.manager.load_tasks) as spy:
                    await self._enter_bytopic(app, pilot)
                self.assertEqual(app.base_filter, "bytopic")
                self.assertEqual(
                    spy.call_count, 0,
                    "entering bytopic must not force a disk reload")
        self._run(go())

    def test_bytopic_repress_is_noop(self):
        """Re-pressing 'y' while already in bytopic must not reload."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_bytopic(app, pilot)
                self.assertEqual(app.base_filter, "bytopic")
                with patch.object(app, "refresh_board",
                                  wraps=app.refresh_board) as spy:
                    await pilot.press("y")
                    await pilot.pause()
                    await pilot.pause()
                self.assertEqual(spy.call_count, 0,
                                 "re-pressing 'y' in bytopic must be a no-op")
        self._run(go())

    def test_bytopic_left_right_moves_focus_between_columns(self):
        """Right arrow moves focus from a card in one topic lane to a card in
        the next lane (TopicColumn must participate in lateral nav)."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(220, 60)) as pilot:
                await pilot.pause()
                await self._enter_bytopic(app, pilot)
                by_col = {}
                for c in app.query(self.TaskCard):
                    by_col.setdefault(c.column_id, []).append(c)
                cols_with_cards = [cid for cid in app._get_visible_col_ids()
                                   if by_col.get(cid)]
                if len(cols_with_cards) < 2:
                    self.skipTest("need >=2 topic lanes with cards for nav")

                by_col[cols_with_cards[0]][0].focus()
                await pilot.pause()
                self.assertEqual(app._focused_card().column_id, cols_with_cards[0])
                await pilot.press("right")
                await pilot.pause()
                landed = app._focused_card()
                self.assertIsNotNone(landed, "right arrow should keep a card focused")
                self.assertEqual(
                    landed.column_id, cols_with_cards[1],
                    "right arrow must move focus into the next topic lane")
        self._run(go())

    def test_bytopic_search_placeholder_is_topic_aware(self):
        """The search box hint reflects the by-topic base and lists 'y' as a
        base-switch key."""
        app = self.KanbanApp()
        app.base_filter = "bytopic"
        placeholder = app._compute_search_placeholder()
        self.assertIn("topic", placeholder.lower(),
                      f"placeholder should mention topics, got {placeholder!r}")
        self.assertIn("y", placeholder,
                      "base-switch hint should include the 'y' key")

    def test_bytopic_search_hides_non_matching(self):
        """Under bytopic, a no-match search hides every card and clearing it
        restores them — proving apply_filter's bytopic branch honors search."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_bytopic(app, pilot)
                cards = list(app.query(self.TaskCard))
                if not cards:
                    self.skipTest("no cards in the live repo")

                app.search_filter = "zzz_no_such_task_qqq"
                app.apply_filter()
                await pilot.pause()
                hidden = [c for c in cards if c.styles.display == "none"]
                self.assertEqual(len(hidden), len(cards),
                                 "a no-match search must hide every card")

                app.search_filter = ""
                app.apply_filter()
                await pilot.pause()
                still_hidden = [c for c in cards if c.styles.display == "none"]
                self.assertEqual(still_hidden, [],
                                 "clearing the search restores all cards")
        self._run(go())


if __name__ == "__main__":
    unittest.main()
