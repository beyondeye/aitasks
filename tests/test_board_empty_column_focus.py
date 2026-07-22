"""Pilot tests for focusing and reordering columns that show no cards (t1209).

Every board column must own exactly one focus anchor: a card when it shows
cards, otherwise an ``EmptyColumnPlaceholder`` (or, when collapsed, the
existing ``CollapsedColumnPlaceholder``). Without one, ``_shift_column`` had no
column to resolve and ``ctrl+left`` / ``ctrl+right`` silently no-opped.

The fixture imposes a deterministic ``Left(2) | Empty(0) | Right(2)`` layout on
the real ``KanbanApp`` rather than asserting against whatever the live board
happens to look like on a given branch.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_empty_column_focus.py -v
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

NO_MATCH = "zzz_no_such_task_zzz"


class BoardEmptyColumnFocusTests(unittest.TestCase):
    """Drives the real KanbanApp via Pilot over a synthetic column layout."""

    @classmethod
    def setUpClass(cls):
        cls._orig_cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        from aitask_board import (  # noqa: E402
            CollapsedColumnPlaceholder,
            EmptyColumnPlaceholder,
            KanbanApp,
            TaskCard,
        )

        cls.KanbanApp = KanbanApp
        cls.TaskCard = TaskCard
        cls.EmptyColumnPlaceholder = EmptyColumnPlaceholder
        cls.CollapsedColumnPlaceholder = CollapsedColumnPlaceholder

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)

    def _run(self, coro):
        return asyncio.run(coro)

    # --- fixture -----------------------------------------------------------

    def _synthetic_board(self, app, n_cards=4, with_children=False):
        """Impose a deterministic Left(2) | Empty(0) | Right(2) layout.

        ``with_children=True`` guarantees the first Left card is a parent whose
        children are retained, so ``.child-wrapper`` rows actually compose.

        Safe by construction: ``Task.board_col`` / ``board_idx`` are pure
        in-memory setters (disk writes only go through
        ``reload_and_save_board_fields``, which nothing here triggers), and
        ``save_metadata`` — the only persistence ``_shift_column`` and
        ``toggle_column_collapsed`` perform — is stubbed out.
        """
        mgr = app.manager
        mgr.save_metadata = lambda: None
        mgr.settings = dict(mgr.settings)
        mgr.settings["collapsed_columns"] = []
        mgr.columns = [
            {"id": "zz_left", "title": "Left", "color": "gray"},
            {"id": "zz_empty", "title": "Empty", "color": "gray"},
            {"id": "zz_right", "title": "Right", "color": "gray"},
        ]
        mgr.column_order = ["zz_left", "zz_empty", "zz_right"]

        parents = sorted(mgr.task_datas.values(), key=lambda t: t.filename)
        kept_children = {}
        if with_children:
            # Query children BEFORE child_task_datas is replaced below.
            def _children(task):
                num, _ = self.TaskCard._parse_filename(task.filename)
                return mgr.get_child_tasks_for_parent(num) if num else []

            parent = next((p for p in parents if _children(p)), None)
            if parent is None:
                self.skipTest("needs a parent task with children in aitasks/")
            parents = [parent] + [p for p in parents if p is not parent]
            kept_children = {c.filename: c for c in _children(parent)}

        tasks = parents[:n_cards]
        if len(tasks) < n_cards:
            self.skipTest(
                f"needs >= {n_cards} parent tasks in aitasks/; found {len(tasks)}"
            )
        mgr.task_datas = {t.filename: t for t in tasks}
        mgr.child_task_datas = kept_children
        for i, task in enumerate(tasks):
            task.board_col = "zz_left" if i < 2 else "zz_right"
            task.board_idx = i * 10
        return tasks

    def _placeholder(self, app, col_id):
        for widget in app.query(self.EmptyColumnPlaceholder):
            if widget.column_id == col_id:
                return widget
        self.fail(f"no EmptyColumnPlaceholder for column {col_id}")

    async def _settle(self, pilot, times=3):
        for _ in range(times):
            await pilot.pause()

    # --- cases -------------------------------------------------------------

    def test_empty_column_gets_a_visible_focusable_placeholder(self):
        """Case 1: only the column showing no cards displays its placeholder."""

        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                empty = self._placeholder(app, "zz_empty")
                self.assertTrue(empty.can_focus)
                self.assertNotEqual(empty.styles.display, "none")
                for populated in ("zz_left", "zz_right"):
                    self.assertEqual(
                        self._placeholder(app, populated).styles.display, "none",
                        f"{populated} has cards; its placeholder must stay hidden",
                    )

        self._run(go())

    def test_lateral_nav_lands_on_the_empty_column(self):
        """Case 2: right-arrow stops on the empty column instead of skipping it."""

        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                app.action_focus_board()
                await self._settle(pilot)
                self.assertEqual(app._get_focused_col_id(), "zz_left")

                await pilot.press("right")
                await self._settle(pilot)
                self.assertEqual(app._get_focused_col_id(), "zz_empty")
                self.assertIsInstance(app.screen.focused, self.EmptyColumnPlaceholder)

                await pilot.press("right")
                await self._settle(pilot)
                self.assertEqual(app._get_focused_col_id(), "zz_right")

        self._run(go())

    def test_move_col_left_reorders_the_empty_column_and_keeps_focus(self):
        """Case 3: the reported bug — ctrl+left on an empty column."""

        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                self._placeholder(app, "zz_empty").focus()
                await self._settle(pilot)

                app.action_move_col_left()
                await self._settle(pilot)

                self.assertEqual(app.manager.column_order,
                                 ["zz_empty", "zz_left", "zz_right"])
                self.assertEqual(app._get_focused_col_id(), "zz_empty",
                                 "focus must survive the post-move refresh")

        self._run(go())

    def test_move_col_at_the_boundaries_is_a_noop(self):
        """Case 4: no wraparound off either end of the column order."""

        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            app.manager.column_order = ["zz_empty", "zz_left", "zz_right"]
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                self._placeholder(app, "zz_empty").focus()
                await self._settle(pilot)

                app.action_move_col_left()
                await self._settle(pilot)
                self.assertEqual(app.manager.column_order,
                                 ["zz_empty", "zz_left", "zz_right"])

                app.manager.column_order = ["zz_left", "zz_right", "zz_empty"]
                app.refresh_board(refocus_col_id="zz_empty")
                await self._settle(pilot)
                app.action_move_col_right()
                await self._settle(pilot)
                self.assertEqual(app.manager.column_order,
                                 ["zz_left", "zz_right", "zz_empty"])

        self._run(go())

    def test_collapsed_column_can_be_reordered(self):
        """Case 5: _shift_column used to bail on a collapsed column too."""

        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            app.manager.settings["collapsed_columns"] = ["zz_left"]
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                collapsed = [w for w in app.query(self.CollapsedColumnPlaceholder)
                             if w.column_id == "zz_left"]
                self.assertTrue(collapsed, "zz_left must render collapsed")
                collapsed[0].focus()
                await self._settle(pilot)

                app.action_move_col_right()
                await self._settle(pilot)
                self.assertEqual(app.manager.column_order,
                                 ["zz_empty", "zz_left", "zz_right"])

        self._run(go())

    def test_filter_emptied_column_shows_placeholder_and_takes_focus(self):
        """Case 6: focus never rests on a card the filter just hid."""

        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                card = app._get_column_cards("zz_left")[0]
                card.focus()
                await self._settle(pilot)

                app.search_filter = NO_MATCH
                app.apply_filter()
                await self._settle(pilot)
                for col_id in ("zz_left", "zz_empty", "zz_right"):
                    self.assertNotEqual(
                        self._placeholder(app, col_id).styles.display, "none",
                        f"{col_id} shows no cards; its placeholder must be visible",
                    )
                self.assertIsInstance(app.screen.focused, self.EmptyColumnPlaceholder)
                self.assertEqual(app._get_focused_col_id(), "zz_left")

                app.search_filter = ""
                app.apply_filter()
                await self._settle(pilot)
                self.assertIsInstance(app.screen.focused, self.TaskCard)
                self.assertEqual(app._get_focused_col_id(), "zz_left")

        self._run(go())

    def test_hidden_child_cards_hide_their_connector_wrapper(self):
        """Case 7: no bare "↳" row survives beside an "(empty)" placeholder."""

        async def go():
            app = self.KanbanApp()
            tasks = self._synthetic_board(app, with_children=True)
            app.expanded_tasks.add(tasks[0].filename)
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                wrappers = list(app.query(".child-wrapper"))
                self.assertTrue(wrappers, "fixture must render child rows")

                app.search_filter = NO_MATCH
                app.apply_filter()
                await self._settle(pilot)
                for wrapper in app.query(".child-wrapper"):
                    self.assertEqual(wrapper.styles.display, "none")

        self._run(go())

    def test_partial_refresh_restores_focus_by_column(self):
        """Case 8: refresh_column/_refocus_card fall back to column identity."""

        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)

                self._placeholder(app, "zz_empty").focus()
                await self._settle(pilot)
                app.refresh_column("zz_empty", refocus_col_id="zz_empty")
                await self._settle(pilot)
                self.assertEqual(app._get_focused_col_id(), "zz_empty")

                app.refresh_column("zz_left",
                                   refocus_filename="t_does_not_exist.md",
                                   refocus_col_id="zz_left")
                await self._settle(pilot)
                self.assertEqual(app._get_focused_col_id(), "zz_left",
                                 "a vanished card must fall back to its column")

        self._run(go())

    def test_full_refresh_preserves_the_focused_empty_column(self):
        """Case 11: `r` / the auto-refresh tick must not drop placeholder focus.

        `action_refresh_board` passes no column, so `refresh_board` has to
        capture the focused column itself — before the DOM teardown that makes
        Textual drop focus.
        """

        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            # Keep the synthetic layout: the real reload would repopulate
            # task_datas from disk with the tasks' true boardcol values.
            app.manager.load_tasks = lambda: None
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)

                self._placeholder(app, "zz_empty").focus()
                await self._settle(pilot)
                app.action_refresh_board()
                await self._settle(pilot)
                self.assertEqual(app._get_focused_col_id(), "zz_empty")

                collapsed_app_state = app.manager.settings["collapsed_columns"]
                collapsed_app_state.append("zz_left")
                app.refresh_board()
                await self._settle(pilot)
                placeholders = [w for w in app.query(self.CollapsedColumnPlaceholder)
                                if w.column_id == "zz_left"]
                self.assertTrue(placeholders)
                placeholders[0].focus()
                await self._settle(pilot)
                app.action_refresh_board()
                await self._settle(pilot)
                self.assertEqual(app._get_focused_col_id(), "zz_left",
                                 "a collapsed column must survive a full refresh too")

        self._run(go())

    def test_hidden_placeholders_stay_out_of_the_focus_chain(self):
        """Case 9: pins the Textual `displayed_children` behaviour we rely on."""

        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                chain = app.screen.focus_chain
                hidden = [w for w in chain
                          if isinstance(w, self.EmptyColumnPlaceholder)
                          and w.styles.display == "none"]
                self.assertEqual(hidden, [],
                                 "tab traversal must not reach a hidden placeholder")
                self.assertIn(self._placeholder(app, "zz_empty"), chain)

        self._run(go())

    def test_populated_column_still_focuses_a_card(self):
        """Case 10: negative control — placeholders never displace real cards."""

        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                self._placeholder(app, "zz_empty").focus()
                await self._settle(pilot)

                await pilot.press("right")
                await self._settle(pilot)
                self.assertIsInstance(app.screen.focused, self.TaskCard)
                self.assertEqual(app._get_focused_col_id(), "zz_right")
                self.assertEqual(app._visible_column_cards("zz_right"),
                                 app._get_column_cards("zz_right"))

        self._run(go())


if __name__ == "__main__":
    unittest.main()
