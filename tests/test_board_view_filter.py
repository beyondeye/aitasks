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

    async def _assert_visible_matches(self, app, keys, expected_set_attrs):
        """Press each key in `keys`, then assert visible cards equal the
        intersection of the helper sets named in `expected_set_attrs`.

        When `expected_set_attrs` is empty, every card is expected visible
        (i.e. base "all" with no add-on).
        """
        for k in keys:
            await app._pilot.press(k)  # use the pilot bound by caller
            await app._pilot.pause()
            await app._pilot.pause()

        cards = list(app.query(self.TaskCard))
        visible = _visible(cards)

        if not expected_set_attrs:
            self.assertEqual(_filenames(visible), _filenames(cards),
                             "no active filter — every card must be visible")
            return

        expected = None
        for attr in expected_set_attrs:
            s = getattr(app, attr)()
            expected = s if expected is None else expected & s

        live_filenames = (set(app.manager.task_datas)
                          | set(app.manager.child_task_datas))
        visible_live = {c.task_data.filename for c in visible
                        if c.task_data.filename in live_filenames}

        self.assertTrue(
            visible_live.issubset(expected),
            f"keys={keys!r}: visible cards {visible_live - expected} leaked "
            f"past filter (expected subset of {len(expected)})")
        for card in cards:
            if card.task_data.filename in expected:
                self.assertNotEqual(
                    card.styles.display, "none",
                    f"keys={keys!r}: card {card.task_data.filename} should "
                    f"be visible (in intended set) but was hidden")

    async def _drive(self, keys, expected_set_attrs, *, prime=None):
        """Spin up the app, optionally `prime(app)` before the first keypress,
        then assert the keypress sequence yields the expected visible set."""
        app = self.KanbanApp()
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause()
            self.assertGreater(len(list(app.query(self.TaskCard))), 0,
                               "test repo must contain at least one task")
            if prime is not None:
                prime(app)
            app._pilot = pilot  # let _assert_visible_matches reuse it
            await self._assert_visible_matches(app, keys, expected_set_attrs)

    def test_locked_filter_hides_non_matching(self):
        async def go():
            await self._drive(["l"], ["_locked_visible_set"])
        self._run(go())

    def test_git_filter_hides_non_matching(self):
        async def go():
            await self._drive(["g"], ["_git_visible_set"])
        self._run(go())

    def test_free_filter_hides_busy_tasks(self):
        async def go():
            await self._drive(["f"], ["_free_visible_set"])
        self._run(go())

    def test_back_to_all_restores_visibility(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await pilot.press("l")
                await pilot.pause()
                await pilot.pause()
                await pilot.press("a")
                await pilot.pause()
                await pilot.pause()
                cards = list(app.query(self.TaskCard))
                hidden = [c for c in cards if c.styles.display == "none"]
                self.assertEqual(hidden, [],
                                 "after pressing 'a', no cards should be hidden")
        self._run(go())

    def test_active_base_keypress_is_noop(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                self.assertEqual(app.base_filter, "all")
                await pilot.press("a")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app.base_filter, "all")
                cards = list(app.query(self.TaskCard))
                hidden = [c for c in cards if c.styles.display == "none"]
                self.assertEqual(hidden, [],
                                 "press 'a' while in All view must be a no-op")
        self._run(go())

    def test_locked_and_git_compose(self):
        async def go():
            await self._drive(["l", "g"],
                              ["_locked_visible_set", "_git_visible_set"])
        self._run(go())

    def test_free_and_type_compose(self):
        """Type add-on toggled on via monkeypatched dialog; intersection
        with free base must hold."""
        def prime(app):
            # Seed a non-empty type selection so the type helper has something
            # to intersect with.
            from aitask_board import _load_task_types
            types = _load_task_types()
            self.assertTrue(types, "test repo must define at least one task type")
            app.manager.settings["filter_issue_types"] = [types[0]]
            # Replace the dialog with a synchronous activator: turning the
            # type toggle ON in tests must not actually push a modal.
            def fake_open():
                app.type_filter_active = True
                app._refresh_selector()
                app._refresh_type_filter_summary()
                app._update_search_placeholder()
                app.apply_filter()
            app._open_type_filter_dialog = fake_open

        async def go():
            await self._drive(["f", "t"],
                              ["_free_visible_set", "_type_visible_set"],
                              prime=prime)
        self._run(go())

    # --- Pure helper unit tests (no Pilot) ---

    def test_locked_filter_includes_lockmap_only_tasks(self):
        """A task present in lock_map with status != Implementing must
        appear in `_locked_visible_set()` (and be excluded from free)."""
        app = self.KanbanApp()
        candidate = next(
            ((fn, t) for fn, t in app.manager.task_datas.items()
             if t.metadata.get('status') != 'Implementing'),
            None,
        )
        self.assertIsNotNone(candidate,
                             "test repo must have a non-Implementing task")
        fn, _ = candidate
        task_num, _ = self.TaskCard._parse_filename(fn)
        app.manager.lock_map[task_num.lstrip('t')] = {
            "locked_by": "test", "hostname": "h", "locked_at": "now",
        }
        self.assertIn(fn, app._locked_visible_set())
        self.assertNotIn(fn, app._free_visible_set())

    def test_free_parent_hidden_when_child_busy(self):
        """A parent with a busy child must be excluded from
        `_free_visible_set()`, even if the parent itself is free."""
        app = self.KanbanApp()
        eligible = None
        for fn, task in app.manager.task_datas.items():
            if app._is_busy(fn, task):
                continue
            task_num, _ = self.TaskCard._parse_filename(fn)
            children = app.manager.get_child_tasks_for_parent(task_num)
            if not children:
                continue
            if any(app._is_busy(c.filename, c) for c in children):
                continue
            eligible = (fn, children)
            break
        if eligible is None:
            self.skipTest("no eligible parent-with-children in test repo")
        parent_fn, children = eligible
        self.assertIn(parent_fn, app._free_visible_set(),
                      "parent should start in free set")
        # Inject a lock for one child; parent must drop out.
        child_fn = children[0].filename
        child_num, _ = self.TaskCard._parse_filename(child_fn)
        app.manager.lock_map[child_num.lstrip('t')] = {
            "locked_by": "test", "hostname": "h", "locked_at": "now",
        }
        self.assertNotIn(parent_fn, app._free_visible_set(),
                         f"{parent_fn} must be hidden when child {child_fn} is busy")


if __name__ == "__main__":
    unittest.main()
