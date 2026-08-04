"""Multi-select marking on the board (t1243_6).

`space` toggles a mark on the focused parent card; the mark renders as the t1004
`☑`/`☐` glyph and lives in an app-level `MarkedSelection` keyed by task filename.
This is the selection primitive t1243_7 (`m` move-to-column) and t1243_12 (`G`
group membership) both consume.

Three things here are load-bearing and easy to break silently, so each has its
own class:

* **Scope.** The glyph and the hover restyle must be present exactly where
  `space` acts. A Textual type selector matches the whole MRO, so a bare
  `TaskCard:hover` would restyle In-Flight / By-Trail cards too — `MarkScopeTests`
  pins the `markable-card` class those rules key on.
* **Lifecycle.** Marks survive a filter pass, are cleared by a view switch, and
  are *pruned* (not cleared) by a refresh — with a notify, because
  `refresh_board` is reached by the unattended auto-refresh timer.
* **Rebuild.** t1243_5 transplants a moved card as a NEW widget, so the glyph is
  re-derived from app state at compose rather than held on the widget.
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

PARENT = "t9000_parent.md"      # c0, has two children
OTHER = "t9003_gamma.md"        # c3, no children
CHILD = "t9000_1_childone.md"   # child of t9000


class MarkedSelectionUnitTests(unittest.TestCase):
    """The pure model — no app, no Textual."""

    @classmethod
    def setUpClass(cls):
        cls.tree, cls.ab = bf.enter_fixture_tree(cls.addClassCleanup,
                                                 tag="MarkedSelectionUnit")
        cls.MarkedSelection = cls.ab.MarkedSelection

    def test_toggle_returns_new_state_and_round_trips(self):
        sel = self.MarkedSelection()
        self.assertTrue(sel.toggle("a.md"), "first toggle must report MARKED")
        self.assertIn("a.md", sel)
        self.assertFalse(sel.toggle("a.md"), "second toggle must report UNMARKED")
        self.assertNotIn("a.md", sel)
        self.assertEqual(len(sel), 0)

    def test_clear_empties_the_set(self):
        sel = self.MarkedSelection({"a.md", "b.md"})
        self.assertEqual(sel.cardinality, 2)
        sel.clear()
        self.assertEqual(sel.cardinality, 0)

    def test_retain_returns_dropped_and_keeps_the_rest(self):
        sel = self.MarkedSelection({"a.md", "b.md", "gone.md"})
        dropped = sel.retain(["a.md", "b.md", "never_marked.md"])
        self.assertEqual(dropped, {"gone.md"},
                         "retain must report WHICH marks it dropped")
        self.assertEqual(sel.marked, {"a.md", "b.md"})

    def test_retain_drops_nothing_when_everything_survives(self):
        """The control that keeps the refresh notify quiet on a stable board."""
        sel = self.MarkedSelection({"a.md"})
        self.assertEqual(sel.retain(["a.md", "b.md"]), set())
        self.assertEqual(sel.marked, {"a.md"})

    def test_effective_prefers_marks_over_the_cursor(self):
        sel = self.MarkedSelection({"b.md", "a.md"})
        self.assertEqual(sel.effective("cursor.md"), ["a.md", "b.md"],
                         "marked set wins, sorted for determinism")

    def test_effective_falls_back_to_the_cursor_then_to_empty(self):
        sel = self.MarkedSelection()
        self.assertEqual(sel.effective("cursor.md"), ["cursor.md"])
        self.assertEqual(sel.effective(None), [])
        self.assertEqual(sel.effective(), [])

    def test_constructor_copies_rather_than_aliases(self):
        source = {"a.md"}
        sel = self.MarkedSelection(source)
        sel.toggle("b.md")
        self.assertEqual(source, {"a.md"}, "must not mutate the caller's set")


class _BoardMarkTestBase(bf.FixtureBoardTestBase, bf.PristineTreeMixin):
    """Shared boot + card lookup helpers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KanbanApp = cls.ab.KanbanApp
        cls.TaskCard = cls.ab.TaskCard
        cls.MARK_CHECKED = cls.ab.MARK_CHECKED
        cls.MARK_UNCHECKED = cls.ab.MARK_UNCHECKED
        cls._snapshot_pristine()

    def _run(self, coro):
        return asyncio.run(coro)

    @staticmethod
    def _footer_actions(app) -> set:
        return {active.binding.action
                for active in app.screen.active_bindings.values()}

    def _card(self, app, filename, *, is_child=False):
        for card in app.query(self.TaskCard):
            if card.task_data.filename == filename and card.is_child == is_child:
                return card
        return None

    def _mark_label(self, card):
        labels = card.query(".task-mark")
        return labels.first() if labels else None

    async def _expand_parent(self, app, pilot):
        """Mount the child cards (they exist only under an expanded parent)."""
        app.expanded_tasks.add(PARENT)
        app.refresh_board()
        await pilot.pause()
        await pilot.pause()


class MarkFixtureFactsTests(_BoardMarkTestBase, unittest.TestCase):
    """Preconditions every other class here depends on.

    Fails loudly if the fixture is reshaped rather than letting the assertions
    below pass vacuously.
    """

    def test_fixture_facts(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                self.assertIsNotNone(self._card(app, PARENT),
                                     f"fixture must render {PARENT}")
                self.assertIsNotNone(self._card(app, OTHER),
                                     f"fixture must render {OTHER}")
                await self._expand_parent(app, pilot)
                self.assertIsNotNone(self._card(app, CHILD, is_child=True),
                                     f"fixture must render child {CHILD}")
                self.assertEqual(app.base_filter, "all",
                                 "the board must boot into a markable view")
                self.assertEqual(len(app.marked), 0,
                                 "a fresh board must start with no marks")
        self._run(go())


class MarkGlyphRenderTests(_BoardMarkTestBase, unittest.TestCase):
    """Render-level: what the card actually draws."""

    def test_unmarked_card_renders_the_empty_checkbox(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                label = self._mark_label(self._card(app, PARENT))
                self.assertIsNotNone(label, "a markable card must render a glyph")
                self.assertEqual(label.render().plain, self.MARK_UNCHECKED)
                self.assertNotIn(self.MARK_CHECKED, label.render().plain)
                self.assertNotIn("task-marked", label.classes)
        self._run(go())

    def test_space_marks_the_focused_card_and_round_trips(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                card = self._card(app, PARENT)
                card.focus()
                await pilot.pause()

                await pilot.press("space")
                await pilot.pause()
                await pilot.pause()
                label = self._mark_label(self._card(app, PARENT))
                self.assertEqual(label.render().plain, self.MARK_CHECKED)
                self.assertNotIn(self.MARK_UNCHECKED, label.render().plain)
                self.assertIn("task-marked", label.classes,
                              "the marked glyph must carry the bold-yellow class")
                self.assertIn(PARENT, app.marked)

                await pilot.press("space")
                await pilot.pause()
                await pilot.pause()
                label = self._mark_label(self._card(app, PARENT))
                self.assertEqual(label.render().plain, self.MARK_UNCHECKED)
                self.assertNotIn("task-marked", label.classes)
                self.assertNotIn(PARENT, app.marked)
        self._run(go())

    def test_marking_one_card_leaves_the_others_unmarked(self):
        """Discriminating control: the glyph is per-card, not board-wide."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                self._card(app, PARENT).focus()
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await pilot.pause()

                other = self._mark_label(self._card(app, OTHER))
                self.assertEqual(other.render().plain, self.MARK_UNCHECKED,
                                 "an untouched card must stay unmarked")
                self.assertEqual(app.marked.marked, {PARENT})
        self._run(go())


class MarkScopeTests(_BoardMarkTestBase, unittest.TestCase):
    """`markable-card` is what the hover rules select — pin where it appears.

    Without this, scoping the hover restyle to the class could regress to a bare
    `TaskCard:hover` (which matches the whole MRO) with nothing failing.
    """

    def test_kanban_parent_card_is_markable(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                card = self._card(app, PARENT)
                self.assertTrue(card.markable)
                self.assertIn("markable-card", card.classes)
        self._run(go())

    def test_child_card_is_not_markable_and_has_no_glyph(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._expand_parent(app, pilot)
                child = self._card(app, CHILD, is_child=True)
                self.assertFalse(child.markable)
                self.assertNotIn("markable-card", child.classes)
                self.assertIsNone(self._mark_label(child),
                                  "a child card must render no checkbox at all")
        self._run(go())

    def test_bytopic_cards_are_not_markable(self):
        """By-Topic mounts BASE TaskCards, so an unguarded glyph would leak here."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                app._set_base_filter("bytopic")
                await pilot.pause()
                await pilot.pause()
                cards = list(app.query(self.TaskCard))
                self.assertTrue(cards, "By-Topic must render some cards")
                for card in cards:
                    self.assertFalse(
                        card.markable,
                        f"{card.task_data.filename} must not be markable in By-Topic")
                    self.assertNotIn("markable-card", card.classes)
                    self.assertIsNone(self._mark_label(card))
        self._run(go())

    def test_inflight_cards_are_not_markable(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                app._set_base_filter("inflight")
                await pilot.pause()
                await pilot.pause()
                for card in app.query(self.TaskCard):
                    self.assertFalse(card.markable)
                    self.assertNotIn("markable-card", card.classes)
                    self.assertIsNone(self._mark_label(card))
        self._run(go())

    def test_ghost_cards_are_mounted_only_by_the_bytrail_column(self):
        """Pins the reachability argument the action guard relies on.

        `action_toggle_mark` has no ghost arm because a ghost can only exist
        under `base_filter == "bytrail"`, which the view gate returns on first.
        If a future view starts mounting ghosts elsewhere, this fails and forces
        that guard to be reconsidered rather than silently going wrong.
        """
        source = (REPO_ROOT / ".aitask-scripts" / "board"
                  / "aitask_board.py").read_text(encoding="utf-8")
        construction_lines = [
            line for line in source.splitlines()
            if "TrailGhostCard(" in line and "class " not in line
        ]
        self.assertEqual(
            len(construction_lines), 1,
            "exactly one TrailGhostCard construction site expected; a new one "
            "means ghosts may now appear outside By-Trail")
        self.assertIn("yield TrailGhostCard(", construction_lines[0])


class MarkGatingTests(_BoardMarkTestBase, unittest.TestCase):
    """check_action hides the binding in the derived views.

    `assertIs(..., False)` deliberately — Textual keeps a binding in
    `active_bindings` (greyed) when check_action returns None, and only removes
    it on False, so False and None are NOT interchangeable here.
    """

    def test_binding_is_visible_in_the_kanban_views(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                self.assertIs(app.check_action("toggle_mark", None), True)
                self.assertIn("toggle_mark", self._footer_actions(app))
        self._run(go())

    def test_binding_is_hidden_in_the_derived_views(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                for view in ("inflight", "bytopic", "bytrail"):
                    with self.subTest(view=view):
                        app._set_base_filter(view)
                        await pilot.pause()
                        await pilot.pause()
                        self.assertIs(app.check_action("toggle_mark", None), False)
                        self.assertNotIn("toggle_mark", self._footer_actions(app))
                    app._set_base_filter("all")
                    await pilot.pause()
                    await pilot.pause()
        self._run(go())

    def test_action_refuses_in_a_derived_view_even_when_called_directly(self):
        """A binding gate is not an action guard — the action re-checks."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                card = self._card(app, PARENT)
                card.focus()
                await pilot.pause()
                app._focused_card = lambda: card   # survive the view teardown
                app.base_filter = "bytrail"
                app.action_toggle_mark()
                self.assertEqual(len(app.marked), 0,
                                 "the action must refuse in a derived view")
        self._run(go())


class MarkModalInertTests(_BoardMarkTestBase, unittest.TestCase):
    """`space` belongs to SelectionList modals while one is open."""

    def test_space_is_inert_while_a_modal_is_open(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                card = self._card(app, PARENT)
                card.focus()
                await pilot.pause()

                app.action_view_details()
                await pilot.pause()
                await pilot.pause()
                self.assertTrue(app._modal_is_active(),
                                "precondition: a modal must be on the stack")

                app.action_toggle_mark()
                self.assertEqual(len(app.marked), 0,
                                 "space must not mark through a modal")
        self._run(go())


class MarkRefusalTests(_BoardMarkTestBase, unittest.TestCase):
    """A child card refuses with a reason, not with silence."""

    def test_space_on_a_child_card_refuses_and_explains(self):
        async def go():
            notices = []
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._expand_parent(app, pilot)
                child = self._card(app, CHILD, is_child=True)
                self.assertIsNotNone(child, "precondition: a child card must exist")
                child.focus()
                await pilot.pause()

                app.notify = lambda msg, **kw: notices.append((msg, kw))
                await pilot.press("space")
                await pilot.pause()
                await pilot.pause()

            self.assertEqual(len(app.marked), 0,
                             "a child must never enter the marked set")
            self.assertTrue(notices, "the refusal must be explained, not silent")
            message, kwargs = notices[0]
            self.assertIn("Child tasks move with their parent", message)
            self.assertEqual(kwargs.get("severity"), "warning")
        self._run(go())

    def test_the_binding_stays_visible_on_a_child_card(self):
        """Unlike movement, the mark binding is NOT hidden for children — that
        is what lets the action explain itself."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._expand_parent(app, pilot)
                child = self._card(app, CHILD, is_child=True)
                child.focus()
                await pilot.pause()
                self.assertIs(app.check_action("toggle_mark", None), True)
                self.assertIs(app.check_action("move_task_right", None), False,
                              "control: movement IS hidden for a child")
        self._run(go())


class MarkLifecycleTests(_BoardMarkTestBase, unittest.TestCase):
    """Clear on view switch, prune (loudly) on refresh, survive everything else."""

    async def _mark(self, app, pilot, filename):
        card = self._card(app, filename)
        card.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        await pilot.pause()
        self.assertIn(filename, app.marked, "precondition: the mark must be set")

    def test_marks_survive_a_search_filter_pass(self):
        """Filtering is a view operation, not a selection operation."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._mark(app, pilot, PARENT)

                app.search_filter = "gamma"
                app.apply_filter()
                await pilot.pause()
                await pilot.pause()

                self.assertIn(PARENT, app.marked,
                              "a filter pass must not clear marks")
                label = self._mark_label(self._card(app, PARENT))
                self.assertEqual(label.render().plain, self.MARK_CHECKED,
                                 "the glyph must survive the filter pass too")
        self._run(go())

    def test_marks_are_cleared_by_a_view_switch(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._mark(app, pilot, PARENT)

                app._set_base_filter("locked")
                await pilot.pause()
                await pilot.pause()

                self.assertEqual(len(app.marked), 0,
                                 "a view switch must discard the selection")
        self._run(go())

    def test_refresh_prunes_a_vanished_mark_and_says_so(self):
        async def go():
            notices = []
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._mark(app, pilot, PARENT)
                app.marked.marked.add("t9999_archived_elsewhere.md")

                app.notify = lambda msg, **kw: notices.append((msg, kw))
                app.refresh_board()
                await pilot.pause()
                await pilot.pause()

            self.assertIn(PARENT, app.marked,
                          "a still-present mark must survive the refresh")
            self.assertNotIn("t9999_archived_elsewhere.md", app.marked,
                             "a vanished task must be pruned")
            self.assertTrue(notices, "a silent prune would hide the change")
            message, kwargs = notices[0]
            self.assertIn("t9999_archived_elsewhere.md", message,
                          "the notify must name what it dropped")
            self.assertEqual(kwargs.get("severity"), "warning")
        self._run(go())

    def test_refresh_with_nothing_to_prune_is_silent(self):
        """Control: the warning must not fire on every auto-refresh tick."""
        async def go():
            notices = []
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._mark(app, pilot, PARENT)

                app.notify = lambda msg, **kw: notices.append((msg, kw))
                app.refresh_board()
                await pilot.pause()
                await pilot.pause()

            self.assertEqual(notices, [],
                             "a stable refresh must not warn")
            self.assertIn(PARENT, app.marked)
        self._run(go())

    def test_a_mark_survives_a_lateral_move(self):
        """t1243_5 transplants the moved card as a NEW widget, so the glyph must
        be re-derived from app state rather than held on the old one."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._mark(app, pilot, OTHER)

                await pilot.press("shift+right")
                await pilot.pause()
                await pilot.pause()

                self.assertIn(OTHER, app.marked,
                              "the move must not drop the mark")
                label = self._mark_label(self._card(app, OTHER))
                self.assertIsNotNone(label, "the moved card must still be mounted")
                self.assertEqual(label.render().plain, self.MARK_CHECKED,
                                 "the REBUILT card must repaint the mark")
        self._run(go())


class MarkNarrowWidthTests(_BoardMarkTestBase, unittest.TestCase):
    """The glyph takes 2 columns from a `width: 1fr` title.

    Asserted at SCREEN level, not on the label: `Label.render().plain` stays
    fully populated even when its parent clips it to nothing, so a non-empty-text
    assertion would pass vacuously exactly when the title is unreadable.
    """

    FIXTURE_TASKS = bf.wide_topology(6, tall_titles=True)

    @staticmethod
    def _screen_text(app) -> str:
        return "\n".join(strip.text
                         for strip in app.screen._compositor.render_strips())

    def test_title_stays_readable_beside_the_glyph_at_a_narrow_width(self):
        async def go():
            captured = {}
            app = self.KanbanApp()
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                card = next(c for c in app.query(self.TaskCard) if c.markable)
                captured["filename"] = card.task_data.filename
                captured["title_width"] = card.query_one(
                    ".task-title").region.width
                captured["screen"] = self._screen_text(app)

            number, title = self.TaskCard._parse_filename(captured["filename"])
            first_word = title.split()[0]

            glyph_lines = [line for line in captured["screen"].splitlines()
                           if self.MARK_UNCHECKED in line]
            self.assertTrue(glyph_lines,
                            "the checkbox must actually paint at 80 columns")
            self.assertTrue(
                any(number in line and first_word in line for line in glyph_lines),
                f"the glyph line must still carry {number!r} and {first_word!r}; "
                f"got {glyph_lines[:3]!r}")
            self.assertGreater(
                captured["title_width"], 0,
                "the title label must retain a non-zero width beside the glyph")
        self._run(go())


if __name__ == "__main__":
    unittest.main()
