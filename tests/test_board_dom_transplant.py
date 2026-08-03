"""In-place DOM transplant for lateral and to-edge board moves (t1243_5).

A lateral move used to end in ``refresh_columns({src, dst})``, recomposing every
card widget of two columns to express a one-card move — 93.6 % of a measured
2173.2 ms keypress (t1243_1). It now prunes just the moved block and mounts a
freshly built one in the destination, because Textual 8.2.7 has **no**
cross-parent widget move: ``move_child`` refuses a foreign child, and
``mount()`` on a live widget is a *silent no-op*.

Rebuilding rather than moving is also what keeps three things true that the
recompose used to maintain for free, so each gets a property here:

1. **Identity.** ``TaskCard.column_id`` is read at 17 sites — filtering, focus,
   navigation, viewport anchoring. A stale one leaves the data model correct
   while navigation and filtering still point at the old column. It is pinned
   *behaviourally* (a search applied after the move), not by reading the
   attribute back, and its control mis-attributes the card on purpose to show
   the assertion discriminates.
2. **The column header count**, baked in at ``ColumnHeader`` construction.
3. **The dirty ``*``**, baked in at ``TaskCard.compose`` from ``is_modified``,
   which the move's own write turns on.

And one property that only exists because the model write is committed *before*
the DOM work: a failure between the prune and the mount must converge on the
model rather than leave the task rendered nowhere. That is fault-injected at
both halves of the window.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_dom_transplant.py -v
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402

#: c0 of `wide_topology(15)` holds t9000 (idx 10), t9005 (60) and t9010 (110).
#: MID is used wherever the card's position does not matter; BOTTOM is used for
#: the round trip, because `move_task_to_column` appends past the destination
#: maximum and only a bottom card returns to its exact slot after right-left.
MID = "t9005_wide5.md"
BOTTOM = "t9010_wide10.md"


class _TransplantTestBase(bf.FixtureBoardTestBase, bf.PristineTreeMixin):
    """Board classes, a Pilot runner, and the DOM/model oracles."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KanbanApp = cls.ab.KanbanApp
        cls.KanbanColumn = cls.ab.KanbanColumn
        cls.TaskCard = cls.ab.TaskCard
        cls.ColumnHeader = cls.ab.ColumnHeader
        cls.EmptyColumnPlaceholder = cls.ab.EmptyColumnPlaceholder
        cls._snapshot_pristine()

    def _run(self, coro):
        return asyncio.run(coro)

    async def _settle(self, pilot, times=4):
        """Drain deferred work AND scheduled animations.

        The transplant queues `_refocus_card` through `call_after_refresh`, the
        header repaint through `refresh(recompose=True)` -> `call_next`, and
        focus scrolls. An assertion that runs too early observes a half-applied
        board and can pass against broken code.
        """
        for _ in range(times):
            await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

    async def _focus(self, pilot, app, filename):
        card = next(c for c in app.query(self.TaskCard)
                    if not c.is_child and c.task_data.filename == filename)
        card.focus()
        await self._settle(pilot)
        return card

    # --- oracles -------------------------------------------------------------

    def _column(self, app, col_id):
        return next((c for c in app.query(self.KanbanColumn)
                     if c.col_id == col_id), None)

    def _dom_order(self, app, col_id):
        """Parent-card filenames in DOM order, read off the column's children."""
        column = self._column(app, col_id)
        return [w.task_data.filename for w in column.children
                if isinstance(w, self.TaskCard) and not w.is_child]

    def _model_order(self, app, col_id):
        """The same list recomputed from the manager — independent ground truth.

        Deliberately NOT read back from the board: comparing the DOM with itself
        would pass a transplant that mounted the block in the wrong place.
        """
        return [t.filename for t in app.manager.get_column_tasks(col_id)]

    def _cards_named(self, app, filename):
        return [c for c in app.query(self.TaskCard)
                if not c.is_child and c.task_data.filename == filename]

    def _header_text(self, app, col_id):
        column = self._column(app, col_id)
        header = next(w for w in column.children
                      if isinstance(w, self.ColumnHeader))
        return header.query(".col-header-title-expanded").first().render().plain

    def _placeholder(self, app, col_id):
        return next((p for p in app.query(self.EmptyColumnPlaceholder)
                     if p.column_id == col_id), None)

    def _spy_recompose(self):
        """Record every `_recompose_column` call by column id."""
        calls: list[str] = []
        original = self.ab.KanbanApp._recompose_column

        def wrapper(app, col_widget):
            calls.append(col_widget.col_id)
            return original(app, col_widget)

        patcher = mock.patch.object(self.ab.KanbanApp, "_recompose_column", wrapper)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls


class LateralTransplantTests(_TransplantTestBase, unittest.TestCase):
    """A lateral move rebuilds one block instead of two columns."""

    FIXTURE_TASKS = bf.wide_topology(15)

    def test_fixture_facts(self):
        """The preconditions every other case in this class relies on."""
        manager = self.ab.TaskManager()
        self.assertEqual([t.filename for t in manager.get_column_tasks("c0")],
                         ["t9000_wide0.md", MID, BOTTOM],
                         "c0's contents and ORDER are load-bearing: MID must be "
                         "mid-column and BOTTOM must be last, or the round-trip "
                         "case silently stops being a round trip")
        self.assertEqual(len(manager.get_column_tasks("c1")), 3)
        self.assertEqual(manager.get_column_tasks("unordered"), [],
                         "an unordered task would divert every move in this "
                         "class onto the recompose fallback")

    def test_lateral_move_does_not_recompose_either_column(self):
        """The property this task exists for."""
        calls = self._spy_recompose()
        control: list[str] = []

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                await self._focus(pilot, app, MID)
                await pilot.press("shift+right")
                await self._settle(pilot)
                control.extend(calls)
                # Discriminating control: the spy DOES see recomposes, so the
                # empty list above is evidence of absence, not a blind spy.
                calls.clear()
                app.refresh_columns({"c0", "c1"})
                await self._settle(pilot)

        self._run(go())
        self.assertEqual(control, [],
                         f"a lateral move must recompose no column; saw {control}")
        self.assertEqual(sorted(calls), ["c0", "c1"],
                         "control: an explicit refresh_columns must still recompose")

    def test_lateral_move_lands_the_card_where_the_model_says(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                await self._focus(pilot, app, MID)
                await pilot.press("shift+right")
                await self._settle(pilot)
                seen["c0_dom"] = self._dom_order(app, "c0")
                seen["c0_model"] = self._model_order(app, "c0")
                seen["c1_dom"] = self._dom_order(app, "c1")
                seen["c1_model"] = self._model_order(app, "c1")
                seen["copies"] = len(self._cards_named(app, MID))

        self._run(go())
        self.assertEqual(seen["copies"], 1,
                         "the moved task must be mounted exactly once")
        self.assertNotIn(MID, seen["c0_dom"], "the source must lose the card")
        self.assertIn(MID, seen["c1_dom"], "the destination must gain it")
        self.assertEqual(seen["c0_dom"], seen["c0_model"])
        self.assertEqual(seen["c1_dom"], seen["c1_model"])
        self.assertEqual(seen["c1_dom"][-1], MID,
                         "move_task_to_column appends past the destination "
                         "maximum, so the moved card sorts last")

    def test_search_after_the_move_treats_the_card_as_the_destination_s(self):
        """The stale-`column_id` catcher named in the task file.

        Filtering is scoped and accumulated by `TaskCard.column_id`, so a card
        that kept the source's id stays visible while the DESTINATION is judged
        empty and shows its placeholder.
        """
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                await self._focus(pilot, app, MID)
                await pilot.press("shift+right")
                await self._settle(pilot)

                app.search_filter = "wide5"
                app.apply_filter()
                await self._settle(pilot)
                moved = self._cards_named(app, MID)[0]
                seen["visible"] = moved.styles.display != "none"
                seen["c1_placeholder"] = self._placeholder(app, "c1").styles.display
                seen["c0_placeholder"] = self._placeholder(app, "c0").styles.display

                # Control: re-attribute the card to the column it came FROM —
                # exactly what a transplant that forgot `column_id` produces —
                # and the destination is judged empty by the same pass.
                moved.column_id = "c0"
                app.apply_filter({"c0", "c1"})
                await self._settle(pilot)
                seen["stale_c1_placeholder"] = self._placeholder(app, "c1").styles.display

        self._run(go())
        self.assertTrue(seen["visible"], "the searched-for card must stay visible")
        self.assertEqual(seen["c1_placeholder"], "none",
                         "c1 holds the only match, so it must NOT look empty")
        self.assertEqual(seen["c0_placeholder"], "block",
                         "c0 has no match left, so it falls back to its placeholder")
        self.assertEqual(seen["stale_c1_placeholder"], "block",
                         "control: with a stale column_id the destination is "
                         "judged empty — so the assertion above discriminates")

    def test_focus_lands_on_the_moved_card_in_the_destination(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                await self._focus(pilot, app, MID)
                await pilot.press("shift+right")
                await self._settle(pilot)
                focused = app.screen.focused
                seen["is_card"] = isinstance(focused, self.TaskCard)
                seen["filename"] = getattr(getattr(focused, "task_data", None),
                                           "filename", None)
                seen["col"] = app._get_focused_col_id()

        self._run(go())
        self.assertTrue(seen["is_card"], "focus must rest on a card, not be lost")
        self.assertEqual(seen["filename"], MID,
                         "focus must follow the moved task, not stay behind")
        self.assertEqual(seen["col"], "c1",
                         "_get_focused_col_id must report the DESTINATION — it "
                         "reads the widget's column_id, not the task's board_col")

    def test_both_column_headers_repaint_their_counts(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                seen["c0_before"] = self._header_text(app, "c0")
                seen["c2_before"] = self._header_text(app, "c2")
                await self._focus(pilot, app, MID)
                await pilot.press("shift+right")
                await self._settle(pilot)
                seen["c0_after"] = self._header_text(app, "c0")
                seen["c1_after"] = self._header_text(app, "c1")
                seen["c2_after"] = self._header_text(app, "c2")

        self._run(go())
        self.assertIn("(3)", seen["c0_before"])
        self.assertIn("(2)", seen["c0_after"],
                      "the source header must drop to 2 — ColumnHeader bakes the "
                      "count in at construction, so without an explicit repaint "
                      "it keeps rendering 3")
        self.assertIn("(4)", seen["c1_after"], "the destination header must reach 4")
        # Control: an untouched column's header must be left alone, so the two
        # assertions above are not just observing a whole-board repaint.
        self.assertEqual(seen["c2_before"], seen["c2_after"],
                         "an untouched column's header must not be rewritten")

    def test_moved_card_renders_the_dirty_marker(self):
        """Render level: the `*` reaches the screen, not just `modified_files`.

        The move's own write flips `is_modified`, and the marker is baked into
        `TaskCard.compose`. Building a FRESH card is what keeps it correct; a
        widget-preserving move would render the card bare until the next scan.
        """
        rendered = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                await self._focus(pilot, app, MID)
                await pilot.press("shift+right")
                await self._settle(pilot)
                for card in app.query(self.TaskCard):
                    if card.is_child:
                        continue
                    labels = card.query(".task-number")
                    if labels:
                        rendered[card.task_data.filename] = labels.first().render().plain

        self._run(go())
        self.assertEqual(rendered.get(MID), "t9005 *",
                         "the moved card must render the modified marker")
        others = {n: t for n, t in rendered.items() if n != MID}
        self.assertTrue(others, "need untouched cards as a control")
        self.assertTrue(all("*" not in t for t in others.values()),
                        f"control: untouched cards must render bare; got {others}")

    def test_right_then_left_restores_the_board_exactly(self):
        """Stationarity — the property the benchmark's ping-pong depends on."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                seen["before"] = {c: self._dom_order(app, c) for c in ("c0", "c1")}
                await self._focus(pilot, app, BOTTOM)
                await pilot.press("shift+right")
                await self._settle(pilot)
                seen["mid"] = {c: self._dom_order(app, c) for c in ("c0", "c1")}
                await pilot.press("shift+left")
                await self._settle(pilot)
                seen["after"] = {c: self._dom_order(app, c) for c in ("c0", "c1")}
                seen["model"] = {c: self._model_order(app, c) for c in ("c0", "c1")}

        self._run(go())
        self.assertNotEqual(seen["before"], seen["mid"],
                            "the first press must actually move something")
        self.assertEqual(seen["after"], seen["before"],
                         "right-then-left on the bottom card must restore the "
                         "exact pre-state")
        self.assertEqual(seen["after"], seen["model"],
                         "and the DOM must agree with the model, not just with "
                         "its own earlier self")


class EdgeTransplantTests(_TransplantTestBase, unittest.TestCase):
    """`ctrl+up` / `ctrl+down` reposition one block instead of recomposing."""

    FIXTURE_TASKS = bf.wide_topology(15)

    def test_fixture_facts(self):
        manager = self.ab.TaskManager()
        order = [t.filename for t in manager.get_column_tasks("c0")]
        self.assertEqual(order, ["t9000_wide0.md", MID, BOTTOM])
        self.assertNotEqual(order[0], MID,
                            "MID must not already be first, or ctrl+up "
                            "early-returns and the case is vacuous")
        self.assertNotEqual(order[-1], MID,
                            "MID must not already be last, or ctrl+down "
                            "early-returns and the case is vacuous")

    def _drive_edge(self, key):
        calls = self._spy_recompose()
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                await self._focus(pilot, app, MID)
                await pilot.press(key)
                await self._settle(pilot)
                seen["dom"] = self._dom_order(app, "c0")
                seen["model"] = self._model_order(app, "c0")
                seen["copies"] = len(self._cards_named(app, MID))
                focused = app.screen.focused
                seen["focused"] = getattr(getattr(focused, "task_data", None),
                                          "filename", None)
                seen["col"] = app._get_focused_col_id()
                card = self._cards_named(app, MID)[0]
                seen["marker"] = card.query(".task-number").first().render().plain
                seen["header"] = self._header_text(app, "c0")

        self._run(go())
        seen["recomposed"] = list(calls)
        return seen

    def test_move_to_top(self):
        seen = self._drive_edge("ctrl+up")
        self.assertEqual(seen["recomposed"], [],
                         "a to-edge move must not recompose its column")
        self.assertEqual(seen["copies"], 1)
        self.assertEqual(seen["dom"][0], MID, "the card must land first")
        self.assertEqual(seen["dom"], seen["model"])
        self.assertEqual(seen["focused"], MID)
        self.assertEqual(seen["col"], "c0")
        self.assertEqual(seen["marker"], "t9005 *",
                         "rebuilding the block is what keeps the dirty marker "
                         "correct; a bare move_child would render it stale")
        self.assertIn("(3)", seen["header"],
                      "a same-column move must not disturb the count")

    def test_move_to_bottom(self):
        seen = self._drive_edge("ctrl+down")
        self.assertEqual(seen["recomposed"], [],
                         "a to-edge move must not recompose its column")
        self.assertEqual(seen["copies"], 1)
        self.assertEqual(seen["dom"][-1], MID, "the card must land last")
        self.assertEqual(seen["dom"], seen["model"])
        self.assertEqual(seen["focused"], MID)
        self.assertEqual(seen["marker"], "t9005 *")
        self.assertIn("(3)", seen["header"])


class ExpandedBlockTransplantTests(_TransplantTestBase, unittest.TestCase):
    """An expanded parent's `.child-wrapper` rows travel with its card."""

    #: `with_children=True` puts two children under t9000, which sits in c0.
    FIXTURE_TASKS = bf.wide_topology(15, with_children=True)

    PARENT = "t9000_wide0.md"

    def test_fixture_facts(self):
        manager = self.ab.TaskManager()
        num, _ = self.ab.TaskCard._parse_filename(self.PARENT)
        self.assertEqual(len(manager.get_child_tasks_for_parent(num)), 2,
                         "the parent must have children or every assertion in "
                         "this class is vacuous")

    def _wrappers_in(self, app, col_id):
        column = self._column(app, col_id)
        return [w for w in column.children
                if isinstance(w, self.ab.Horizontal) and w.has_class("child-wrapper")]

    def test_card_block_stops_at_the_next_card(self):
        """`_card_block` must claim its own wrappers and nobody else's."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            app.expanded_tasks.add(self.PARENT)
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                column = self._column(app, "c0")
                parent_card = self._cards_named(app, self.PARENT)[0]
                other_card = self._cards_named(app, MID)[0]
                seen["parent_block"] = len(app._card_block(column, parent_card))
                seen["other_block"] = len(app._card_block(column, other_card))
                seen["wrappers"] = len(self._wrappers_in(app, "c0"))

        self._run(go())
        self.assertEqual(seen["wrappers"], 2, "the fixture must render two child rows")
        self.assertEqual(seen["parent_block"], 3,
                         "the expanded parent's block is its card plus both rows")
        # Control: a card with no rows of its own must not swallow its
        # neighbour's — which is what proves the scan stops at the next card.
        self.assertEqual(seen["other_block"], 1,
                         "a childless card's block is the card alone")

    def test_child_rows_follow_the_parent_across_a_lateral_move(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            app.expanded_tasks.add(self.PARENT)
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                seen["c0_wrappers_before"] = len(self._wrappers_in(app, "c0"))
                await self._focus(pilot, app, self.PARENT)
                await pilot.press("shift+right")
                await self._settle(pilot)

                seen["c0_wrappers_after"] = len(self._wrappers_in(app, "c0"))
                dst = self._column(app, "c1")
                children = list(dst.children)
                card = self._cards_named(app, self.PARENT)[0]
                idx = children.index(card)
                trailing = children[idx + 1:]
                seen["adjacent"] = [
                    isinstance(w, self.ab.Horizontal) and w.has_class("child-wrapper")
                    for w in trailing[:2]
                ]
                seen["child_cols"] = [c.column_id for c in dst.query(self.TaskCard)
                                      if c.is_child]

        self._run(go())
        self.assertEqual(seen["c0_wrappers_before"], 2)
        self.assertEqual(seen["c0_wrappers_after"], 0,
                         "the rows must LEAVE the source, not be duplicated")
        self.assertEqual(seen["adjacent"], [True, True],
                         "both child rows must sit immediately after the card")
        self.assertEqual(seen["child_cols"], ["c1", "c1"],
                         "child cards carry column_id too — a stale one breaks "
                         "_get_column_cards and the filter for the subtree")


class TransplantScrollTests(_TransplantTestBase, unittest.TestCase):
    """The moved card is scrolled into view in a column taller than the pane."""

    #: 60 tall parents = 12 per column, so the destination's bottom — where a
    #: lateral move lands — is below the fold. With a short column every card is
    #: already visible and the assertion proves nothing.
    FIXTURE_TASKS = bf.wide_topology(60, tall_titles=True)

    def test_fixture_facts(self):
        manager = self.ab.TaskManager()
        self.assertGreaterEqual(len(manager.get_column_tasks("c1")), 10)

    def test_moved_card_is_scrolled_into_view_not_left_off_screen(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                first = self._model_order(app, "c0")[0]
                dst = self._column(app, "c1")
                seen["scrollable"] = dst.max_scroll_y > 0
                await self._focus(pilot, app, first)
                await pilot.press("shift+right")
                await self._settle(pilot)

                dst = self._column(app, "c1")
                card = self._cards_named(app, first)[0]
                viewport = dst.scrollable_content_region
                seen["laid_out"] = bool(card.region.area)
                seen["inside"] = (viewport.y <= card.region.y
                                  and card.region.bottom <= viewport.bottom)
                seen["scroll_y"] = dst.scroll_y
                seen["scroll_target_y"] = dst.scroll_target_y

        self._run(go())
        self.assertTrue(seen["scrollable"],
                        "the destination must overflow its pane or this case is "
                        "vacuous — every card would be visible anyway")
        self.assertTrue(seen["laid_out"], "the moved card must have been laid out")
        self.assertTrue(seen["inside"],
                        "the moved card lands at the bottom of the destination, "
                        "so focus must scroll it into view")
        self.assertGreater(seen["scroll_y"], 0,
                           "the destination must actually have scrolled, not "
                           "snapped back to the top")
        self.assertEqual(seen["scroll_y"], seen["scroll_target_y"],
                         "scroll and its target must not diverge (t1248)")


class UnorderedColumnFallbackTests(_TransplantTestBase, unittest.TestCase):
    """Moving the last `unordered` task keeps the recompose path.

    `unordered` appears and disappears with its tasks, and only `refresh_columns`
    can express "the column is gone" (it escalates to a full `refresh_board`).
    The transplant declines that case rather than desynchronise the board.
    """

    FIXTURE_TASKS = bf.wide_topology(15) + (
        bf.FixtureTask(task_id="9100", col="unordered", idx=10, slug="inbox"),
    )

    ORPHAN = "t9100_inbox.md"

    def test_fixture_facts(self):
        manager = self.ab.TaskManager()
        self.assertEqual([t.filename for t in manager.get_column_tasks("unordered")],
                         [self.ORPHAN],
                         "exactly one unordered task, so moving it empties the "
                         "column and forces the structural case")

    def test_emptying_unordered_removes_its_column(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                seen["present_before"] = self._column(app, "unordered") is not None
                await self._focus(pilot, app, self.ORPHAN)
                await pilot.press("shift+right")
                await self._settle(pilot)
                seen["present_after"] = self._column(app, "unordered") is not None
                seen["c0_dom"] = self._dom_order(app, "c0")
                seen["c0_model"] = self._model_order(app, "c0")
                seen["copies"] = len(self._cards_named(app, self.ORPHAN))

        self._run(go())
        self.assertTrue(seen["present_before"],
                        "the unordered column must be mounted to begin with")
        self.assertFalse(seen["present_after"],
                         "emptying unordered must remove its column — a "
                         "transplant cannot express that, so the fast path must "
                         "have declined in favour of refresh_columns")
        self.assertEqual(seen["copies"], 1)
        self.assertIn(self.ORPHAN, seen["c0_dom"])
        self.assertEqual(seen["c0_dom"], seen["c0_model"])


class TransplantRecoveryTests(_TransplantTestBase, unittest.TestCase):
    """A failure mid-transplant converges on the committed model.

    The model write lands BEFORE the DOM work, so a raise between the prune and
    the mount would otherwise leave a task the model says exists and the board
    renders nowhere — and an exception escaping an async action reaches
    Textual's message pump and takes the app down.
    """

    FIXTURE_TASKS = bf.wide_topology(15)

    def _inject_once(self, cls, name):
        """Make the first ARMED call to `cls.name` raise, then delegate as normal.

        One-shot on purpose: the recovery path re-enters the board's own
        rendering, and an always-raising patch would break the recovery it is
        meant to exercise.

        Armed explicitly rather than firing on the first call at all, so the
        injection cannot land during app startup or the initial focus — that
        would leave `fired` true while the keypress ran undisturbed, and the
        case would assert against a board nothing was ever injected into.
        """
        original = getattr(cls, name)
        state = {"armed": False, "fired": False}

        def wrapper(self_, *a, **kw):
            if state["armed"] and not state["fired"]:
                state["fired"] = True
                raise RuntimeError(f"injected {name} failure")
            return original(self_, *a, **kw)

        patcher = mock.patch.object(cls, name, wrapper)
        patcher.start()
        self.addCleanup(patcher.stop)
        return state

    def _spy_notify(self):
        calls: list[tuple[str, str]] = []
        original = self.ab.KanbanApp.notify

        def wrapper(app, message, **kw):
            calls.append((str(message), kw.get("severity", "information")))
            return original(app, message, **kw)

        patcher = mock.patch.object(self.ab.KanbanApp, "notify", wrapper)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    def _drive_injected(self, attr):
        state = self._inject_once(self.ab.KanbanColumn, attr)
        notifications = self._spy_notify()
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                await self._focus(pilot, app, MID)
                state["armed"] = True          # only the move may trip it
                await pilot.press("shift+right")
                await self._settle(pilot)
                seen["running"] = app.is_running
                seen["copies"] = len(self._cards_named(app, MID))
                seen["c0_dom"] = self._dom_order(app, "c0")
                seen["c0_model"] = self._model_order(app, "c0")
                seen["c1_dom"] = self._dom_order(app, "c1")
                seen["c1_model"] = self._model_order(app, "c1")
                seen["c0_header"] = self._header_text(app, "c0")
                seen["c1_header"] = self._header_text(app, "c1")
                seen["focused"] = app.screen.focused is not None

        self._run(go())
        seen["fired"] = state["fired"]
        seen["notifications"] = notifications
        return seen

    def _assert_converged(self, seen, attr):
        self.assertTrue(seen["fired"], f"the {attr} injection never ran")
        self.assertTrue(seen["running"],
                        "the app must survive — an exception escaping an async "
                        "action would kill it instead of degrading")
        self.assertEqual(seen["copies"], 1,
                         "the task must be rendered exactly ONCE. Zero is the "
                         "failure this recovery exists to prevent: the write is "
                         "already committed, so the board would show it nowhere")
        self.assertIn(MID, seen["c1_dom"],
                      "recovery rebuilds from the committed model, which puts "
                      "the task in the destination")
        self.assertEqual(seen["c0_dom"], seen["c0_model"])
        self.assertEqual(seen["c1_dom"], seen["c1_model"])
        self.assertIn("(2)", seen["c0_header"])
        self.assertIn("(4)", seen["c1_header"])
        self.assertTrue(seen["focused"], "focus must be restored to something")
        errors = [m for m, sev in seen["notifications"] if sev == "error"]
        self.assertTrue(errors,
                        "the failure must be SURFACED, not swallowed — "
                        f"notifications were {seen['notifications']}")
        self.assertTrue(any("RuntimeError" in m for m in errors),
                        f"the toast must name the failure; got {errors}")

    def test_mount_failure_after_the_prune_still_converges(self):
        """The dangerous half: the old widgets are already gone.

        `mount_compose` is the right injection point precisely because the
        recovery does not use it — `_recompose_column` goes through `mount_all`
        — so the injection breaks only the fast path.
        """
        self._assert_converged(self._drive_injected("mount_compose"), "mount_compose")

    def test_prune_failure_before_the_mount_still_converges(self):
        """The other half of the window: nothing removed, write already on disk."""
        self._assert_converged(self._drive_injected("remove_children"),
                               "remove_children")


if __name__ == "__main__":
    unittest.main()
