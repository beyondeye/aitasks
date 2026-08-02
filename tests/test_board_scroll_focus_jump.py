"""Pilot tests for board column scroll surviving a focus change (t1248).

Wheel-scrolling a board column used to snap back to the top of the column. The
cause was not the wheel: a stray ``down``/``up`` key (tmux's alternate-screen
wheel -> cursor-key emulation) reached ``action_nav_down``, which stepped from
the *currently focused* card — far off-screen because the user had scrolled away
from it — to its neighbour near the top. ``TaskCard.on_focus`` then called
``scroll_visible()`` with Textual's defaults (``animate=True, immediate=False``),
a deferred animated scroll that landed mid-scroll and drove the column's
``scroll_target_y`` back to ~0 while ``scroll_y`` was still 158. Because the
wheel handler computes its next position from ``scroll_target_y``, the following
tick resumed from the poisoned target and the view snapped to 2.

Two invariants are pinned here:

* a nav key arriving while the viewport has scrolled away from the focused card
  re-anchors the cursor to what is on screen instead of teleporting the view;
* the focus-driven scroll is synchronous and unanimated, so it can never land
  behind input the user has already produced, and ``scroll_y`` and
  ``scroll_target_y`` never diverge.

Both must hold without breaking what ``on_focus`` exists to provide: keyboard
navigation still scrolls an off-screen card into view.

The fixture imposes a deterministic Tall(30) | Side(10) layout on the real
``KanbanApp`` rather than asserting against whatever the live board happens to
look like on a given branch.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_scroll_focus_jump.py -v
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402

TALL = "zz_tall"
SIDE = "zz_side"
N_TALL = 30
N_SIDE = 10


class BoardScrollFocusJumpTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """Drives the real KanbanApp via Pilot over a synthetic two-column layout."""

    #: This module's property is volume-dependent *and* height-dependent: it
    #: imposes a Tall(30) | Side(10) layout, so the tree must hold N_TALL +
    #: N_SIDE parents, AND two cases require a card taller than the viewport
    #: ("oversized card must not trap the cursor", "no card fully visible in a
    #: short pane"). Default short slugs render 5-row cards and silently break
    #: both — `tall_titles` reproduces the wrapping real task titles produce.
    FIXTURE_TASKS = bf.wide_topology(N_TALL + N_SIDE, tall_titles=True)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from textual import events  # noqa: E402

        cls.KanbanApp = cls.ab.KanbanApp
        cls.KanbanColumn = cls.ab.KanbanColumn
        cls.TaskCard = cls.ab.TaskCard
        cls.events = events

    def _run(self, coro):
        return asyncio.run(coro)

    def test_fixture_facts(self):
        """Precondition (t1354_2 Step 2a): the tree must hold >= N_TALL+N_SIDE
        parents.

        This is the one genuinely *volume*-dependent module in the migration —
        the bug it guards only reproduces in a column tall enough to scroll, so
        the fixture reproduces the shape rather than shrinking it away.
        """
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                self.assertGreaterEqual(
                    len(app.manager.task_datas), N_TALL + N_SIDE,
                    f"fixture must load >= {N_TALL + N_SIDE} parent tasks")
        self._run(go())

    def test_fixture_cards_are_taller_than_a_short_viewport(self):
        """Precondition (t1354_2 Step 2a): card **height**, not just count.

        Two cases below need a card taller than the pane. Cards rendered from
        short slugs are 5 rows and would silently satisfy neither, so this
        pins the property directly rather than letting those cases fail
        obscurely later.
        """
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 12)) as pilot:
                await self._settle(pilot)
                self._synthetic_board(app)
                app.refresh_board()
                await self._settle(pilot)
                column = self._column(app, TALL)
                cards = [c for c in self._cards(app, TALL) if c.region.area]
                self.assertTrue(cards, "TALL column must render cards")
                self.assertGreater(
                    max(c.region.height for c in cards),
                    column.scrollable_content_region.height,
                    "fixture cards must exceed a short viewport — use "
                    "wide_topology(..., tall_titles=True)")
        self._run(go())

    # --- fixture -----------------------------------------------------------

    def _synthetic_board(self, app):
        """Impose a deterministic Tall(30) | Side(10) layout.

        Safe by construction, exactly as in ``test_board_empty_column_focus``:
        ``Task.board_col`` / ``board_idx`` are pure in-memory setters (disk
        writes only go through ``reload_and_save_board_fields``, which nothing
        here triggers) and ``save_metadata`` is stubbed out.
        """
        mgr = app.manager
        mgr.save_metadata = lambda: None
        mgr.settings = dict(mgr.settings)
        mgr.settings["collapsed_columns"] = []
        mgr.columns = [
            {"id": TALL, "title": "Tall", "color": "gray"},
            {"id": SIDE, "title": "Side", "color": "gray"},
        ]
        mgr.column_order = [TALL, SIDE]

        parents = sorted(mgr.task_datas.values(), key=lambda t: t.filename)
        tasks = parents[: N_TALL + N_SIDE]
        self.assertGreaterEqual(
            len(tasks), N_TALL + N_SIDE,
            f"fixture must load >= {N_TALL + N_SIDE} parent tasks to impose the "
            f"Tall({N_TALL}) | Side({N_SIDE}) layout; found {len(tasks)}")
        mgr.task_datas = {t.filename: t for t in tasks}
        mgr.child_task_datas = {}
        for i, task in enumerate(tasks):
            task.board_col = TALL if i < N_TALL else SIDE
            task.board_idx = i * 10
        return tasks

    # --- helpers -----------------------------------------------------------

    def _column(self, app, col_id):
        for col in app.query(self.KanbanColumn):
            if col.col_id == col_id:
                return col
        self.fail(f"no KanbanColumn for column {col_id}")

    def _cards(self, app, col_id):
        return [c for c in app.query(self.TaskCard) if c.column_id == col_id]

    def _wheel(self, app, column, down=True, times=1):
        """Post wheel events through the screen's normal forwarding path.

        Textual 8.2.7's ``Pilot`` has no scroll helper (only press/click/hover),
        so this dispatches the same event objects the driver would — the seam
        the bug lives on. Coordinates sit inside the column so the event routes
        to it exactly as a real wheel over that column would.
        """
        cls = (self.events.MouseScrollDown if down else self.events.MouseScrollUp)
        x, y = column.region.x + 2, column.region.y + 2
        for _ in range(times):
            app.screen._forward_event(
                cls(widget=None, x=x, y=y, delta_x=0, delta_y=1, button=0,
                    shift=False, meta=False, ctrl=False, screen_x=x, screen_y=y)
            )

    async def _settle(self, pilot, times=3):
        """Drain deferred work AND scheduled animations.

        The pre-fix scroll was both deferred (``call_after_refresh``) and
        animated, so an assertion that ran too early could observe the
        un-rewound value and pass against unfixed code. Draining both keeps the
        baseline-failure proof honest if Pilot's internal settling ever changes.
        """
        for _ in range(times):
            await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

    def _visible_cards(self, app, col_id):
        """Cards lying wholly inside the column viewport, in DOM order."""
        column = self._column(app, col_id)
        viewport = column.scrollable_content_region
        return [c for c in self._cards(app, col_id)
                if c.region.area
                and viewport.y <= c.region.y
                and c.region.bottom <= viewport.bottom]

    async def _scrolled_away(self, pilot, app, ticks=40, down=True):
        """Focus an end card, then wheel the column away from it.

        Returns ``(column, scroll_y, scroll_target_y)`` once the focused card is
        off-screen — the exact state the stray key used to corrupt.
        """
        column = self._column(app, TALL)
        cards = self._cards(app, TALL)
        (cards[0] if down else cards[-1]).focus()
        await self._settle(pilot)
        if not down:
            column.scroll_to(y=column.max_scroll_y, animate=False, immediate=True)
            await self._settle(pilot)
        self._wheel(app, column, down=down, times=ticks)
        await self._settle(pilot)
        return column, column.scroll_y, column.scroll_target_y

    # --- regression pins (must fail before the fix) ------------------------

    def test_stray_nav_key_does_not_rewind_wheel_scroll(self):
        """Case 1: a stray `down` mid-scroll must not rewind the column."""
        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            async with app.run_test(size=(200, 50)) as pilot:
                await self._settle(pilot)
                column, before_y, before_target = await self._scrolled_away(pilot, app)
                self.assertGreater(before_y, 0, "fixture failed to scroll the column")

                await pilot.press("down")
                await self._settle(pilot)
                self.assertGreaterEqual(
                    column.scroll_y, before_y,
                    "stray nav key rewound scroll_y",
                )
                self.assertGreaterEqual(
                    column.scroll_target_y, before_target,
                    "stray nav key poisoned scroll_target_y — the next wheel "
                    "tick resumes from it",
                )

                self._wheel(app, column, down=True, times=1)
                await self._settle(pilot)
                self.assertGreaterEqual(
                    column.scroll_y, before_y,
                    "wheel resumed from a rewound position after the nav key",
                )
        self._run(go())

    def test_stray_nav_key_up_does_not_rewind(self):
        """Case 2: the `up` mirror at the bottom of the column."""
        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            async with app.run_test(size=(200, 50)) as pilot:
                await self._settle(pilot)
                column, before_y, before_target = await self._scrolled_away(
                    pilot, app, down=False)
                self.assertLess(before_y, column.max_scroll_y,
                                "fixture failed to scroll the column up")

                await pilot.press("up")
                await self._settle(pilot)
                self.assertLessEqual(
                    column.scroll_y, before_y,
                    "stray nav key drove scroll_y forward",
                )
                self.assertLessEqual(
                    column.scroll_target_y, before_target,
                    "stray nav key poisoned scroll_target_y",
                )
        self._run(go())

    def test_anchor_side_is_chosen_by_focus_position_not_key(self):
        """Case 3: focus above the viewport + `up` lands on the FIRST visible card.

        The assertion form matters. Checking only "focus == first visible card
        *now*" is not discriminating: after unfixed code rewinds the column the
        focused card can coincidentally sit at the top of the new viewport.
        Membership in the set of cards visible *before* the key fails by
        construction instead.
        """
        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            async with app.run_test(size=(200, 50)) as pilot:
                await self._settle(pilot)
                column, _, _ = await self._scrolled_away(pilot, app)
                before_visible = self._visible_cards(app, TALL)
                self.assertTrue(before_visible, "fixture left no visible card")

                await pilot.press("up")
                await self._settle(pilot)
                focused = app.screen.focused
                self.assertIn(
                    focused, before_visible,
                    "nav key focused a card that was NOT on screen beforehand",
                )
                self.assertIs(
                    focused, before_visible[0],
                    "focus fell off the TOP, so the anchor must be the topmost "
                    "visible card regardless of the key direction",
                )
        self._run(go())

    def test_short_viewport_nudge_is_bounded_by_one_card(self):
        """Case 4: in a pane too short to show a whole card, movement is bounded.

        At this height no card is fully visible, so the anchor comes from the
        overlap fallback and bringing it into view costs at most its own height
        — against the ~50-row rewind unfixed code produces.
        """
        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            async with app.run_test(size=(200, 18)) as pilot:
                await self._settle(pilot)
                column, before_y, _ = await self._scrolled_away(pilot, app, ticks=30)
                self.assertFalse(
                    self._visible_cards(app, TALL),
                    "fixture precondition: no card may be fully visible here",
                )
                tallest = max(c.region.height
                              for c in self._cards(app, TALL) if c.region.area)

                await pilot.press("down")
                await self._settle(pilot)
                self.assertLessEqual(
                    abs(column.scroll_y - before_y), tallest,
                    f"movement exceeded the stated one-card bound ({tallest} rows)",
                )
        self._run(go())

    def test_focus_scroll_is_immediate_and_unanimated(self):
        """Case 5: `on_focus` must not queue a deferred animated scroll.

        A construction spy rather than a timing assertion: the contract is the
        arguments `on_focus` passes, and pinning those is deterministic where
        racing the deferral is not.
        """
        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            captured = []
            original = self.TaskCard.scroll_visible

            def spy(card_self, *args, **kwargs):
                captured.append((args, kwargs))
                return original(card_self, *args, **kwargs)

            self.TaskCard.scroll_visible = spy
            try:
                async with app.run_test(size=(200, 50)) as pilot:
                    await self._settle(pilot)
                    captured.clear()
                    self._cards(app, TALL)[3].focus()
                    await self._settle(pilot)
            finally:
                self.TaskCard.scroll_visible = original

            self.assertTrue(captured, "on_focus did not call scroll_visible")
            args, kwargs = captured[0]
            animate = kwargs.get("animate", args[0] if args else True)
            self.assertFalse(
                animate,
                "focus scroll must not animate — an animated scroll leaves "
                "scroll_target_y ahead of scroll_y, and the wheel reads the target",
            )
            self.assertTrue(
                kwargs.get("immediate", False),
                "focus scroll must be immediate — a deferred scroll lands behind "
                "input the user has already produced",
            )
        self._run(go())

    def test_lateral_nav_uses_viewport_anchor(self):
        """Case 6: `left`/`right` carries the on-screen position, not a stale index."""
        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            async with app.run_test(size=(200, 50)) as pilot:
                await self._settle(pilot)
                await self._scrolled_away(pilot, app)
                anchor = self._visible_cards(app, TALL)[0]
                anchor_pos = self._cards(app, TALL).index(anchor)
                self.assertGreater(
                    anchor_pos, 0,
                    "fixture precondition: the on-screen anchor must differ "
                    "from the off-screen focused index",
                )

                await pilot.press("right")
                await self._settle(pilot)
                side_cards = self._cards(app, SIDE)
                expected = side_cards[min(anchor_pos, len(side_cards) - 1)]
                self.assertIs(
                    app.screen.focused, expected,
                    "lateral nav used the off-screen focus index instead of the "
                    "viewport anchor",
                )
        self._run(go())

    # --- guards (must pass before AND after the fix) -----------------------

    def test_nav_never_dead_ends_on_oversized_card(self):
        """Guard: a card taller than the viewport must not trap the cursor.

        The re-anchor could otherwise resolve to the focused card itself and
        make `down` a permanent no-op. Only the new code can fail this.
        """
        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            async with app.run_test(size=(200, 12)) as pilot:
                await self._settle(pilot)
                cards = self._cards(app, TALL)
                cards[2].focus()
                await self._settle(pilot)
                column = self._column(app, TALL)
                self.assertGreater(
                    max(c.region.height for c in cards if c.region.area),
                    column.scrollable_content_region.height,
                    "fixture precondition: a card must exceed the viewport",
                )
                before = app.screen.focused
                await pilot.press("down")
                await self._settle(pilot)
                self.assertIsNot(
                    app.screen.focused, before,
                    "`down` dead-ended: focus did not move",
                )
        self._run(go())

    def test_nav_from_visible_card_still_steps_one(self):
        """Guard: ordinary stepping is untouched when the cursor is on screen."""
        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            async with app.run_test(size=(200, 50)) as pilot:
                await self._settle(pilot)
                cards = self._cards(app, TALL)
                cards[1].focus()
                await self._settle(pilot)
                await pilot.press("down")
                await self._settle(pilot)
                self.assertIs(
                    app.screen.focused, cards[2],
                    "a visible card must step to its immediate neighbour",
                )
        self._run(go())

    def test_nav_scrolls_offscreen_card_into_view(self):
        """Guard: what `on_focus` exists for — nav brings its target into view."""
        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            async with app.run_test(size=(200, 50)) as pilot:
                await self._settle(pilot)
                column = self._column(app, TALL)
                self._cards(app, TALL)[0].focus()
                await self._settle(pilot)
                start = column.scroll_y
                for _ in range(15):
                    await pilot.press("down")
                    await pilot.pause()
                await self._settle(pilot)
                self.assertGreater(
                    column.scroll_y, start,
                    "walking past the fold did not scroll the column",
                )
                self.assertIn(
                    app.screen.focused, self._visible_cards(app, TALL),
                    "the focused card was left off-screen",
                )
                self.assertEqual(
                    column.scroll_y, column.scroll_target_y,
                    "scroll_y and scroll_target_y diverged",
                )
        self._run(go())

    def test_lateral_nav_still_reaches_the_target_column(self):
        """Guard: the ancestor effect of the immediate/unanimated focus scroll.

        `scroll_to_widget` walks every ancestor, so the focus scroll also drives
        the horizontal board container. This pins that lateral navigation still
        lands on the other column with the container's offset settled.
        """
        async def go():
            app = self.KanbanApp()
            self._synthetic_board(app)
            async with app.run_test(size=(60, 40)) as pilot:
                await self._settle(pilot)
                container = app.query_one("#board_container")
                self._cards(app, TALL)[0].focus()
                await self._settle(pilot)
                await pilot.press("right")
                await self._settle(pilot)
                self.assertEqual(
                    getattr(app.screen.focused, "column_id", None), SIDE,
                    "lateral nav did not reach the neighbouring column",
                )
                self.assertEqual(
                    container.scroll_x, container.scroll_target_x,
                    "board container left mid-scroll: scroll_x != scroll_target_x",
                )
        self._run(go())


if __name__ == "__main__":
    unittest.main()
