"""Pilot tests for in-column task groups: rendering, focus and navigation (t1243_9).

t1243_8 landed the data model (`lib/board_groups.py`, the `boardgroup` field);
this module pins what the board does with it. The headline case is a column
holding **only collapsed groups**: it mounts group headers and no cards at all,
which `_column_focus_target` used to answer with `None` — so `_refocus_column`
silently did nothing and focus was lost. Everything else here exists because
making a header a first-class focus unit widens seams that many callers share.

House style, followed throughout: every class opens with a `test_fixture_facts`
precondition case, and every positive assertion is paired with a
**discriminating negative control** — a guard whose control also passes is
testing nothing.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_group_focus.py -v
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

PERF = "perf_work"
ALPHA = "alpha_grp"
SOLO = "solo_grp"
BETA = "beta_grp"

#: Additive topology — `DEFAULT_TOPOLOGY` / `RICH_TOPOLOGY` are deliberately NOT
#: widened (both are pinned by files that byte-differ or count them exactly).
#:
#:   c0  a 2-member `perf_work` group whose FIRST member has children, plus one
#:       ungrouped card after it — the integration shape.
#:   c1  ONLY a group. Collapsing it leaves the column with zero cards, which is
#:       the case the whole unit abstraction exists for.
#:   c2  a SINGLE-member group: renders as a plain card, no header.
#:   c3  ungrouped only — the negative control column for every grouped claim,
#:       and the one that must keep the in-place DOM fast path.
#:   c4  an ungrouped card FOLLOWED by a group — the group is deliberately not
#:       the column's first unit, which is the only shape in which the explicit
#:       post-collapse refocus is observable (otherwise the generic
#:       `_column_focus_target` would land on the header for free).
GROUP_TOPOLOGY = (
    bf.FixtureTask(task_id="9000", col="c0", idx=10, slug="parent",
                   extra={"boardgroup": PERF}),
    bf.FixtureTask(task_id="9000_1", col="c0", idx=20, slug="childone"),
    bf.FixtureTask(task_id="9000_2", col="c0", idx=30, slug="childtwo"),
    bf.FixtureTask(task_id="9003", col="c0", idx=20, slug="gamma",
                   extra={"boardgroup": PERF}),
    bf.FixtureTask(task_id="9004", col="c0", idx=30, slug="delta"),

    bf.FixtureTask(task_id="9010", col="c1", idx=10, slug="alphaone",
                   extra={"boardgroup": ALPHA}),
    bf.FixtureTask(task_id="9011", col="c1", idx=20, slug="alphatwo",
                   extra={"boardgroup": ALPHA}),

    bf.FixtureTask(task_id="9020", col="c2", idx=10, slug="lonely",
                   extra={"boardgroup": SOLO}),

    bf.FixtureTask(task_id="9030", col="c3", idx=10, slug="plainone"),
    bf.FixtureTask(task_id="9031", col="c3", idx=20, slug="plaintwo"),
    bf.FixtureTask(task_id="9032", col="c3", idx=30, slug="plainthree"),

    bf.FixtureTask(task_id="9040", col="c4", idx=10, slug="target"),
    bf.FixtureTask(task_id="9041", col="c4", idx=20, slug="betaone",
                   extra={"boardgroup": BETA}),
    bf.FixtureTask(task_id="9042", col="c4", idx=30, slug="betatwo",
                   extra={"boardgroup": BETA}),
)

P_9000 = "t9000_parent.md"
P_9003 = "t9003_gamma.md"
P_9004 = "t9004_delta.md"
C_9000_1 = "t9000_1_childone.md"
C_9000_2 = "t9000_2_childtwo.md"
P_9010 = "t9010_alphaone.md"
P_9011 = "t9011_alphatwo.md"
P_9020 = "t9020_lonely.md"
P_9040 = "t9040_target.md"
P_9041 = "t9041_betaone.md"
P_9030 = "t9030_plainone.md"
P_9031 = "t9031_plaintwo.md"
P_9032 = "t9032_plainthree.md"


class _GroupFocusBase(bf.FixtureBoardTestBase, bf.PristineTreeMixin):
    FIXTURE_TASKS = GROUP_TOPOLOGY

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KanbanApp = cls.ab.KanbanApp
        cls.KanbanColumn = cls.ab.KanbanColumn
        cls.TaskCard = cls.ab.TaskCard
        cls.GroupHeader = cls.ab.GroupHeader
        cls.EmptyColumnPlaceholder = cls.ab.EmptyColumnPlaceholder
        cls._snapshot_pristine()

    def _run(self, coro):
        return asyncio.run(coro)

    async def _settle(self, pilot, times=4):
        """Drain deferred work AND scheduled animations.

        Collapse queues `_refocus_group_header` through `call_after_refresh`, a
        recompose queues its mounts, and focus scrolls. An assertion that runs
        too early observes a half-applied board and can pass against broken code.
        """
        for _ in range(times):
            await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

    # --- oracles -------------------------------------------------------------

    def _column(self, app, col_id):
        return next((c for c in app.query(self.KanbanColumn)
                     if c.col_id == col_id), None)

    def _dom_units(self, app, col_id):
        """Focus units in DOM order, read off the column's own children.

        A header is reported as `("group", slug)` and a card as its filename, so
        one list expresses the whole interleaving.
        """
        out = []
        for w in self._column(app, col_id).children:
            if isinstance(w, self.GroupHeader):
                out.append(("group", w.slug))
            elif isinstance(w, self.TaskCard) and not w.is_child:
                out.append(w.task_data.filename)
        return out

    def _model_units(self, app, col_id):
        """The same list recomputed from the manager — INDEPENDENT ground truth.

        Deliberately not read back from the board: comparing the DOM with itself
        would pass a compose that emitted units in the wrong order.
        """
        from board_groups import build_column_units
        out = []
        for slug, members in build_column_units(
                app.manager.get_column_tasks(col_id)):
            if slug and len(members) > 1:
                out.append(("group", slug))
            out.extend(m.filename for m in members)
        return out

    def _header(self, app, col_id, slug):
        return next((h for h in app.query(self.GroupHeader)
                     if h.column_id == col_id and h.slug == slug), None)

    def _placeholder(self, app, col_id):
        return next((p for p in app.query(self.EmptyColumnPlaceholder)
                     if p.column_id == col_id), None)

    def _card(self, app, filename):
        return next((c for c in app.query(self.TaskCard)
                     if not c.is_child and c.task_data.filename == filename), None)

    def _child_card(self, app, filename):
        return next((c for c in app.query(self.TaskCard)
                     if c.is_child and c.task_data.filename == filename), None)

    async def _focus(self, pilot, app, widget):
        widget.focus()
        await self._settle(pilot)
        return widget

    def _focus_id(self, app):
        """A comparable description of what holds focus."""
        f = app.screen.focused
        if isinstance(f, self.GroupHeader):
            return ("group", f.column_id, f.slug)
        if isinstance(f, self.TaskCard):
            return ("card", f.task_data.filename)
        if isinstance(f, self.EmptyColumnPlaceholder):
            return ("placeholder", f.column_id)
        return ("other", type(f).__name__)

    def _spy_recompose(self):
        calls: list[str] = []
        original = self.ab.KanbanApp._recompose_column

        def wrapper(app, col_widget):
            calls.append(col_widget.col_id)
            return original(app, col_widget)

        patcher = mock.patch.object(self.ab.KanbanApp, "_recompose_column", wrapper)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    def _spy_child_index(self):
        calls: list[int] = []
        original = self.ab.KanbanApp._children_by_parent

        def wrapper(app):
            calls.append(1)
            return original(app)

        patcher = mock.patch.object(self.ab.KanbanApp, "_children_by_parent", wrapper)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    def _spy_group_move(self, destination=None):
        """Record `_apply_group_move` calls; return `destination` from the seam."""
        calls: list[tuple] = []
        original = self.ab.KanbanApp._apply_group_move  # noqa: F841 (kept for symmetry)

        async def wrapper(app, header, members, axis, direction):
            calls.append((header.column_id, header.slug,
                          [m.filename for m in members], axis, direction))
            return destination

        patcher = mock.patch.object(self.ab.KanbanApp, "_apply_group_move", wrapper)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    def _spy_refocus_header(self):
        """Record `_refocus_group_header(col_id, slug)` requests.

        The FOCUS CONTRACT is what t1243_9 owns: "after a block move, focus the
        header in the destination". Asserting the resulting `screen.focused`
        instead would be unexecutable until t1243_11 lands — the seam moves
        nothing, so no destination header exists to focus. This spy states the
        contract in terms this child can actually deliver, and keeps passing
        unchanged once the seam is real.
        """
        calls: list[tuple] = []
        original = self.ab.KanbanApp._refocus_group_header

        def wrapper(app, col_id, slug):
            calls.append((col_id, slug))
            return original(app, col_id, slug)

        patcher = mock.patch.object(
            self.ab.KanbanApp, "_refocus_group_header", wrapper)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    def _spy_push_screen(self):
        calls: list[str] = []
        original = self.ab.KanbanApp.push_screen

        def wrapper(app, screen, *a, **kw):
            calls.append(type(screen).__name__)
            return original(app, screen, *a, **kw)

        patcher = mock.patch.object(self.ab.KanbanApp, "push_screen", wrapper)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls


# --- 1-4: rendering ----------------------------------------------------------


class GroupRenderingTests(_GroupFocusBase, unittest.TestCase):

    def test_fixture_facts(self):
        """Preconditions the rest of this class depends on."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                mgr = app.manager
                seen["c0"] = [t.filename for t in mgr.get_column_tasks("c0")]
                seen["c1"] = [t.filename for t in mgr.get_column_tasks("c1")]
                seen["c2"] = [t.filename for t in mgr.get_column_tasks("c2")]
                seen["c3"] = [t.filename for t in mgr.get_column_tasks("c3")]
                seen["children"] = [
                    c.filename for c in mgr.get_child_tasks_for_parent("t9000")]

        self._run(go())
        self.assertEqual(seen["c0"], [P_9000, P_9003, P_9004],
                         "c0 must hold two perf_work members then an ungrouped card")
        self.assertEqual(seen["c1"], [P_9010, P_9011],
                         "c1 must hold ONLY the alpha_grp members")
        self.assertEqual(seen["c2"], [P_9020], "c2 must hold one single-member group")
        self.assertEqual(seen["c3"], [P_9030, P_9031, P_9032],
                         "c3 must be ungrouped — it is the negative-control column")
        self.assertEqual(seen["children"], [C_9000_1, C_9000_2],
                         "t9000 must have children so .child-wrapper rows compose")

    def test_group_header_renders_glyph_title_and_count(self):
        """Case 1: `▾ perf work (2)` expanded, `▸ perf work (2)` collapsed."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                seen["expanded"] = self._header(app, "c0", PERF).render().plain
            app2 = self.KanbanApp()
            app2.collapsed_groups.add(f"c0/{PERF}")
            async with app2.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                seen["collapsed"] = self._header(app2, "c0", PERF).render().plain

        self._run(go())
        self.assertEqual(seen["expanded"], "▾ perf work (2)")
        self.assertEqual(seen["collapsed"], "▸ perf work (2)",
                         "collapsed must flip the glyph, not the title or count")

    def test_single_member_group_renders_as_a_plain_card(self):
        """Case 2: a one-member group draws no header.

        Control: the two-member group in the SAME board does draw one, so an
        assertion of absence is not just "headers never render here".
        """
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                seen["c2_header"] = self._header(app, "c2", SOLO)
                seen["c2_units"] = self._dom_units(app, "c2")
                seen["c0_header"] = self._header(app, "c0", PERF)

        self._run(go())
        self.assertIsNone(seen["c2_header"],
                          "a single-member group must render as a plain card")
        self.assertEqual(seen["c2_units"], [P_9020])
        self.assertIsNotNone(seen["c0_header"],
                             "control: the 2-member group DOES render a header")

    def test_dom_unit_order_matches_the_model_derivation(self):
        """Case 3: header and members are flat siblings in INV-R order."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                seen["dom"] = self._dom_units(app, "c0")
                seen["model"] = self._model_units(app, "c0")

        self._run(go())
        self.assertEqual(seen["dom"], [("group", PERF), P_9000, P_9003, P_9004])
        self.assertEqual(seen["dom"], seen["model"],
                         "the DOM must match the independent model derivation")

    def test_unit_selector_yields_dom_order(self):
        """Case 4: pins the Textual comma-selector assumption `_get_column_units` rests on."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                units = app._get_column_units("c0")
                seen["query"] = [("group", w.slug) if isinstance(w, self.GroupHeader)
                                 else w.task_data.filename for w in units]
                seen["dom"] = []
                for w in self._column(app, "c0").children:
                    if isinstance(w, self.GroupHeader):
                        seen["dom"].append(("group", w.slug))
                    elif isinstance(w, self.TaskCard):
                        seen["dom"].append(w.task_data.filename)

        self._run(go())
        self.assertEqual(seen["query"], seen["dom"],
                         "a comma selector must yield headers and cards interleaved "
                         "in DOM order — two separate queries could not")
        self.assertIn(("group", PERF), seen["query"])


# --- 5-9: focus and navigation ----------------------------------------------


class GroupFocusNavigationTests(_GroupFocusBase, unittest.TestCase):

    def _collapsed_c1_app(self):
        app = self.KanbanApp()
        app.collapsed_groups.add(f"c1/{ALPHA}")
        return app

    def test_fixture_facts(self):
        """c1 collapsed must genuinely mount a header and zero cards."""
        seen = {}

        async def go():
            app = self._collapsed_c1_app()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                seen["cards"] = [c.task_data.filename
                                 for c in app._get_column_cards("c1")]
                seen["units"] = len(app._get_column_units("c1"))

        self._run(go())
        self.assertEqual(seen["cards"], [],
                         "a collapsed group must mount NO member cards")
        self.assertEqual(seen["units"], 1, "…but exactly one unit: its header")

    def test_column_of_only_collapsed_groups_keeps_a_focus_anchor(self):
        """Case 5: the motivating bug. Control shows the card-only query is empty."""
        seen = {}

        async def go():
            app = self._collapsed_c1_app()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                target = app._column_focus_target("c1")
                seen["is_header"] = isinstance(target, self.GroupHeader)
                # The negative control: the pre-t1243_9 card-only source of this
                # decision is EMPTY here, so returning a header is not incidental.
                seen["visible_cards"] = len(app._visible_column_cards("c1"))
                seen["visible_units"] = len(app._visible_column_units("c1"))
                app._refocus_column("c1")
                await self._settle(pilot)
                seen["focus"] = self._focus_id(app)
                seen["col"] = app._get_focused_col_id()

        self._run(go())
        self.assertTrue(seen["is_header"], "_column_focus_target must return the header")
        self.assertEqual(seen["visible_cards"], 0,
                         "control: the card-only query the old code used is empty — "
                         "it is what made _column_focus_target return None")
        self.assertEqual(seen["visible_units"], 1)
        self.assertEqual(seen["focus"], ("group", "c1", ALPHA),
                         "_refocus_column must land on the header, not lose focus")
        self.assertEqual(seen["col"], "c1",
                         "_get_focused_col_id must resolve the column from a header")

    def test_collapsed_group_column_keeps_its_placeholder_hidden(self):
        """Case 6: exactly ONE focus anchor — the header, not also the placeholder."""
        seen = {}

        async def go():
            app = self._collapsed_c1_app()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                seen["placeholder"] = self._placeholder(app, "c1").styles.display
                seen["header"] = self._header(app, "c1", ALPHA).styles.display

        self._run(go())
        self.assertEqual(seen["placeholder"], "none",
                         "a visible header is column content — the empty "
                         "placeholder must stay hidden or the column owns two anchors")
        self.assertNotEqual(seen["header"], "none")

    def test_down_and_up_walk_header_member_children_next_unit(self):
        """Case 7: the integration sequence, and its exact reverse."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            app.expanded_tasks.add(P_9000)
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._focus(pilot, app, self._header(app, "c0", PERF))
                order = [self._focus_id(app)]
                for _ in range(5):
                    await pilot.press("down")
                    await self._settle(pilot)
                    order.append(self._focus_id(app))
                seen["down"] = order
                back = [self._focus_id(app)]
                for _ in range(5):
                    await pilot.press("up")
                    await self._settle(pilot)
                    back.append(self._focus_id(app))
                seen["up"] = back

        self._run(go())
        self.assertEqual(seen["down"], [
            ("group", "c0", PERF),
            ("card", P_9000),
            ("card", C_9000_1),
            ("card", C_9000_2),
            ("card", P_9003),
            ("card", P_9004),
        ], "↓ must walk header → member → its children → next member → next unit")
        self.assertEqual(seen["up"], list(reversed(seen["down"])),
                         "↑ must be the exact reverse of ↓")

    def test_lateral_preserves_the_positional_index_over_units(self):
        """Case 8: `→` keeps the index, counting the header as a stop."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                # c0 position 2 is the second member (header, 9000, 9003, 9004).
                await self._focus(pilot, app, self._card(app, P_9003))
                seen["start_pos"] = [
                    i for i, u in enumerate(app._visible_column_units("c0"))
                    if u is app.screen.focused][0]
                await pilot.press("right")
                await self._settle(pilot)
                seen["after"] = self._focus_id(app)
                seen["after_pos"] = [
                    i for i, u in enumerate(app._visible_column_units("c1"))
                    if u is app.screen.focused]

        self._run(go())
        self.assertEqual(seen["start_pos"], 2)
        self.assertEqual(seen["after"], ("card", P_9011),
                         "→ must land on the same positional index in c1 "
                         "(header, 9010, 9011)")
        self.assertEqual(seen["after_pos"], [2])

    def test_column_actions_resolve_from_a_focused_header(self):
        """Case 9 + 20: `ctrl+left` and `X` still resolve the column from a header."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                app.manager.save_metadata = lambda: None
                # c1, not c0: `_shift_column(-1)` early-returns on the leftmost
                # column, which would make this assertion vacuous.
                await self._focus(pilot, app, self._header(app, "c1", ALPHA))
                before = list(app.manager.column_order)
                app.action_move_col_left()
                await self._settle(pilot)
                seen["order_before"] = before
                seen["order_after"] = list(app.manager.column_order)
                seen["col"] = app._get_focused_col_id()
                # The other widened-seam consumer: `X` resolves its column too.
                await self._focus(pilot, app, self._header(app, "c1", ALPHA))
                app.action_toggle_column_collapsed()
                await self._settle(pilot)
                seen["collapsed"] = app.manager.is_column_collapsed("c1")

        self._run(go())
        self.assertEqual(seen["order_before"], ["c0", "c1", "c2", "c3", "c4"])
        self.assertEqual(seen["order_after"], ["c1", "c0", "c2", "c3", "c4"],
                         "ctrl+left must reorder the column a header names")
        self.assertEqual(seen["col"], "c1", "focus must survive the post-move refresh")
        self.assertTrue(seen["collapsed"],
                        "`X` must collapse the column a header names")


# --- 10-11: collapse ---------------------------------------------------------


class GroupCollapseTests(_GroupFocusBase, unittest.TestCase):

    def test_fixture_facts(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            app.expanded_tasks.add(P_9000)
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                seen["children_mounted"] = self._child_card(app, C_9000_1) is not None
                seen["collapsed_groups"] = set(app.collapsed_groups)

        self._run(go())
        self.assertTrue(seen["children_mounted"],
                        "the expanded member's child rows must be mounted")
        self.assertEqual(seen["collapsed_groups"], set(),
                         "collapse state must start empty — an already-collapsed "
                         "fixture would make the toggle assertions vacuous")

    def test_x_on_a_header_collapses_members_and_children_and_keeps_focus(self):
        """Case 10: `x` collapses; members AND their `↳` rows go; focus stays."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            app.expanded_tasks.add(P_9000)
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._focus(pilot, app, self._header(app, "c0", PERF))
                await pilot.press("x")
                await self._settle(pilot)
                seen["state"] = set(app.collapsed_groups)
                seen["member"] = self._card(app, P_9003)
                seen["child"] = self._child_card(app, C_9000_1)
                seen["ungrouped"] = self._card(app, P_9004)
                seen["focus"] = self._focus_id(app)
                seen["glyph"] = self._header(app, "c0", PERF).render().plain
                # Control: pressing `x` again must restore everything.
                await pilot.press("x")
                await self._settle(pilot)
                seen["reexpanded_member"] = self._card(app, P_9003) is not None
                seen["reexpanded_child"] = self._child_card(app, C_9000_1) is not None
                seen["state_after"] = set(app.collapsed_groups)

        self._run(go())
        self.assertEqual(seen["state"], {f"c0/{PERF}"})
        self.assertIsNone(seen["member"], "members must unmount")
        self.assertIsNone(seen["child"], "a member's `↳` child rows must unmount too")
        self.assertIsNotNone(seen["ungrouped"],
                             "control: the ungrouped card in the same column stays")
        self.assertEqual(seen["focus"], ("group", "c0", PERF),
                         "focus must land on the header, never on an unmounted member")
        self.assertEqual(seen["glyph"], "▸ perf work (2)")
        self.assertTrue(seen["reexpanded_member"], "control: `x` again re-expands")
        self.assertTrue(seen["reexpanded_child"])
        self.assertEqual(seen["state_after"], set())

    def test_collapse_refocuses_the_header_even_when_it_is_not_first(self):
        """The explicit post-collapse refocus, in the only shape that shows it.

        In a column whose group is the FIRST unit, `_column_focus_target` returns
        the header anyway and the explicit refocus is unobservable. c4 puts an
        ungrouped card ahead of the group, so the generic path would land on that
        card instead — which is exactly what "never leave focus on an unmounted
        member" has to beat.
        """
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                seen["units_before"] = [
                    ("group", w.slug) if isinstance(w, self.GroupHeader)
                    else w.task_data.filename
                    for w in app._get_column_units("c4")]
                await self._focus(pilot, app, self._header(app, "c4", BETA))
                await pilot.press("x")
                await self._settle(pilot)
                seen["focus"] = self._focus_id(app)
                # What the GENERIC path would have chosen, for contrast.
                seen["generic"] = type(app._column_focus_target("c4")).__name__

        self._run(go())
        self.assertEqual(seen["units_before"][0], P_9040,
                         "c4's first unit must be the UNGROUPED card, or this "
                         "case cannot discriminate")
        self.assertEqual(seen["focus"], ("group", "c4", BETA),
                         "collapse must refocus the header explicitly")
        self.assertEqual(seen["generic"], "TaskCard",
                         "control: the generic column focus target is the leading "
                         "card — so the assertion above is not free")

    def test_toggle_group_invoked_directly_with_a_card_focused_is_inert(self):
        """The palette path is inert with a card focused.

        `action_*` is reachable without the BINDING gate (command palette, direct
        call), so `action_toggle_group` carries TWO guards: the `check_action`
        re-assert (the idiom `action_toggle_children` uses) and an
        `isinstance(header, GroupHeader)` re-resolve.

        They are deliberately redundant, and measurably so: negative controls
        confirmed that removing EITHER one alone leaves this test green, because
        the other still refuses. No single-fault control can distinguish them —
        that is what defence in depth means here, not a gap in this case. Both
        are kept because the failure they prevent is an AttributeError raised
        into Textual's message pump, which takes the whole app down rather than
        misbehaving locally.
        """
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._focus(pilot, app, self._card(app, P_9030))
                app.action_toggle_group()
                await self._settle(pilot)
                seen["state"] = set(app.collapsed_groups)
                seen["alive"] = self._card(app, P_9030) is not None
                # Control: on a header the same direct call DOES collapse.
                await self._focus(pilot, app, self._header(app, "c0", PERF))
                app.action_toggle_group()
                await self._settle(pilot)
                seen["state_header"] = set(app.collapsed_groups)

        self._run(go())
        self.assertEqual(seen["state"], set(),
                         "a focused card must leave collapse state untouched")
        self.assertTrue(seen["alive"], "…and must not crash the app")
        self.assertEqual(seen["state_header"], {f"c0/{PERF}"},
                         "control: the same direct call on a header does collapse")

    def test_footer_advertises_the_right_half_of_the_x_pair(self):
        """Case 11: `x` resolves to the truthful label for what holds focus.

        Scope note: `screen.active_bindings` is keyed by KEY, so a duplicate-key
        pair can never yield two entries for `x` — "both labels shown" is not
        expressible through this API, and asserting it would be unfalsifiable.
        What this pins is which half `x` RESOLVES to, which is the user-visible
        behaviour: a `toggle_group` that wrongly returned False would leave `x`
        absent from a focused header entirely (verified by negative control).
        """
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)

                def actions():
                    return {a.binding.action
                            for a in app.screen.active_bindings.values()}

                await self._focus(pilot, app, self._header(app, "c0", PERF))
                seen["on_header"] = actions() & {"toggle_children", "toggle_group"}
                await self._focus(pilot, app, self._card(app, P_9000))
                seen["on_card"] = actions() & {"toggle_children", "toggle_group"}

        self._run(go())
        self.assertEqual(seen["on_header"], {"toggle_group"},
                         "a focused header advertises Toggle Group only")
        self.assertEqual(seen["on_card"], {"toggle_children"},
                         "control: a parent card with children still advertises "
                         "Toggle Children only")


# --- 12-14c: filtering -------------------------------------------------------


class GroupFilteringTests(_GroupFocusBase, unittest.TestCase):

    def test_fixture_facts(self):
        """The child's text must be absent from its parent's search corpus.

        This is the precondition the child-only-match case rests on; if it ever
        becomes false that case stops discriminating.
        """
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                parent = app.manager.task_datas[P_9000]
                child = app.manager.child_task_datas[C_9000_1]
                seen["parent_has"] = "childone" in parent.search_haystack
                seen["child_has"] = "childone" in child.search_haystack

        self._run(go())
        self.assertFalse(seen["parent_has"],
                         "a parent's haystack must NOT contain its child's text — "
                         "that is why the header rule has to be child-aware")
        self.assertTrue(seen["child_has"])

    def test_header_visibility_follows_member_matches(self):
        """Case 12: matched member keeps the header; no match hides it."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                app.search_filter = "gamma"
                app.apply_filter()
                await self._settle(pilot)
                seen["match_header"] = self._header(app, "c0", PERF).styles.display
                seen["match_placeholder"] = self._placeholder(app, "c0").styles.display

                app.search_filter = "zzz_no_such_task_zzz"
                app.apply_filter()
                await self._settle(pilot)
                seen["nomatch_header"] = self._header(app, "c0", PERF).styles.display
                seen["nomatch_placeholder"] = self._placeholder(app, "c0").styles.display

        self._run(go())
        self.assertNotEqual(seen["match_header"], "none")
        self.assertEqual(seen["match_placeholder"], "none",
                         "a visible header counts as column content")
        self.assertEqual(seen["nomatch_header"], "none",
                         "control: with nothing matching, the header hides")
        self.assertNotEqual(seen["nomatch_placeholder"], "none",
                            "…and only then does the empty placeholder appear")

    def test_child_only_match_keeps_the_header_visible(self):
        """Case 14b: no header hidden above a still-visible `↳` row.

        The control is the parent card: it IS hidden by this same search, which
        proves a member-only rule would have hidden the header too.
        """
        seen = {}

        async def go():
            app = self.KanbanApp()
            app.expanded_tasks.add(P_9000)
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                app.search_filter = "childone"
                app.apply_filter()
                await self._settle(pilot)
                seen["child"] = self._child_card(app, C_9000_1).styles.display
                seen["parent"] = self._card(app, P_9000).styles.display
                seen["header"] = self._header(app, "c0", PERF).styles.display

        self._run(go())
        self.assertNotEqual(seen["child"], "none", "the matching child stays visible")
        self.assertEqual(seen["parent"], "none",
                         "control: the parent does NOT match — a member-only header "
                         "rule would therefore have hidden the header")
        self.assertNotEqual(seen["header"], "none",
                            "the header must stay visible above its visible child")

    def test_focus_is_rescued_off_a_hidden_header(self):
        """Case 13."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._focus(pilot, app, self._header(app, "c1", ALPHA))
                seen["before"] = self._focus_id(app)
                app.search_filter = "zzz_no_such_task_zzz"
                app.apply_filter()
                await self._settle(pilot)
                seen["after"] = self._focus_id(app)

        self._run(go())
        self.assertEqual(seen["before"], ("group", "c1", ALPHA))
        self.assertEqual(seen["after"], ("placeholder", "c1"),
                         "focus must not rest on a header the pass just hid")

    def test_scoped_pass_reaches_only_the_named_columns(self):
        """Case 14: `apply_filter({col})` flips that column's header only."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                app.search_filter = "zzz_no_such_task_zzz"
                app.apply_filter({"c0"})
                await self._settle(pilot)
                seen["scoped"] = self._header(app, "c0", PERF).styles.display
                seen["untouched"] = self._header(app, "c1", ALPHA).styles.display

        self._run(go())
        self.assertEqual(seen["scoped"], "none")
        self.assertNotEqual(seen["untouched"], "none",
                            "a scoped pass must not flip an untouched column's header")

    def test_child_index_is_built_once_per_pass_and_not_at_all_without_headers(self):
        """Case 14c: the per-keystroke hot path stays O(children), not O(members x children)."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                calls = self._spy_child_index()
                # Worst case: every member fails the search, so every one of them
                # reaches the child lookup.
                app.search_filter = "zzz_no_such_task_zzz"
                calls.clear()
                app.apply_filter()
                await self._settle(pilot)
                seen["one_pass"] = len(calls)
                app.apply_filter()
                await self._settle(pilot)
                seen["two_passes"] = len(calls)
                # Control: a scope with no header in it must not build the index.
                calls.clear()
                app.apply_filter({"c3"})
                await self._settle(pilot)
                seen["no_headers"] = len(calls)

        self._run(go())
        self.assertEqual(seen["one_pass"], 1,
                         "the index must be built ONCE per pass, not once per member")
        self.assertEqual(seen["two_passes"], 2,
                         "control: a second pass raises the count — a '1' above was "
                         "not a dead spy")
        self.assertEqual(seen["no_headers"], 0,
                         "control: with no header in scope the index is never built, "
                         "so today's ungrouped boards pay nothing")


# --- 15-19, 21-22: movement and action gateways ------------------------------


class GroupMovementDispatchTests(_GroupFocusBase, unittest.TestCase):

    def test_fixture_facts(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                has = app._column_widget_has_group
                seen["c0_grouped"] = has(self._column(app, "c0"))
                seen["c3_grouped"] = has(self._column(app, "c3"))
                seen["c2_grouped"] = has(self._column(app, "c2"))

        self._run(go())
        self.assertTrue(seen["c0_grouped"])
        self.assertFalse(seen["c3_grouped"], "c3 is the ungrouped control column")
        self.assertFalse(seen["c2_grouped"],
                         "a single-member group draws no header, so it is not "
                         "a grouped column for DOM purposes")

    def test_ungrouped_move_derives_no_units(self):
        """The recompose decision must not put model derivation on the hot path.

        `_move_needs_recompose` originally answered "is this column grouped?" with
        `build_column_units(get_column_tasks(col))`, which filters every task on
        the board and then sorts TWICE — for up to two columns, on every lateral
        move, even when no task carries `boardgroup`. That silently regressed the
        card-only path t1243_5 measured. It now reads the column widget's own
        children instead, so an ungrouped move derives nothing at all.

        Asserted as a call count rather than a duration: a wall-clock threshold on
        a shared box is a flake, while "zero derivations" is exact and is the
        property that actually bounds the cost.
        """
        seen = {}

        async def go():
            import board_groups
            calls: list[int] = []
            real = board_groups.build_column_units

            def counting(tasks):
                calls.append(1)
                return real(tasks)

            with mock.patch.object(self.ab, "build_column_units", counting):
                app = self.KanbanApp()
                async with app.run_test(size=(200, 60)) as pilot:
                    await self._settle(pilot)

                    # Ungrouped column, ungrouped task: the fast path.
                    calls.clear()
                    await self._focus(pilot, app, self._card(app, P_9031))
                    await pilot.press("shift+down")
                    await self._settle(pilot)
                    seen["vertical"] = len(calls)

                    # LEFT, not right: c3's right neighbour is c4, which holds a
                    # group — that move correctly falls back and would derive.
                    # c2's single-member group draws no header, so c3 -> c2 is a
                    # genuinely ungrouped lateral on both sides.
                    calls.clear()
                    await self._focus(pilot, app, self._card(app, P_9030))
                    await pilot.press("shift+left")
                    await self._settle(pilot)
                    seen["lateral"] = len(calls)
                    seen["lateral_col"] = app.manager.task_datas[P_9030].board_col

                    # Control: a grouped move DOES derive — via the recompose it
                    # correctly falls back to. A zero above is therefore evidence
                    # of a cheap decision, not of a dead spy.
                    calls.clear()
                    await self._focus(pilot, app, self._card(app, P_9004))
                    await pilot.press("shift+up")
                    await self._settle(pilot)
                    seen["grouped"] = len(calls)

        self._run(go())
        self.assertEqual(seen["vertical"], 0,
                         "an ungrouped vertical move must derive no units")
        self.assertEqual(seen["lateral_col"], "c2",
                         "precondition: the lateral move must actually have "
                         "happened, or the count below is vacuous")
        self.assertEqual(seen["lateral"], 0,
                         "an ungrouped lateral move must derive no units for "
                         "EITHER column")
        self.assertGreater(seen["grouped"], 0,
                           "control: the grouped move recomposes, which does "
                           "derive — so the spy is live")

    def test_movement_from_a_header_dispatches_the_block_move(self):
        """Case 15: the dispatch contract t1243_11 fills in.

        Control: the spy is cleared and a CARD is moved, proving an empty record
        is evidence of absence rather than a blind spy.
        """
        seen = {}

        async def go():
            app = self.KanbanApp()
            calls = self._spy_group_move(destination="c1")
            refocus = self._spy_refocus_header()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._focus(pilot, app, self._header(app, "c0", PERF))
                refocus.clear()
                await pilot.press("shift+right")
                await self._settle(pilot)
                seen["lateral"] = list(calls)
                seen["refocus"] = list(refocus)

                calls.clear()
                await self._focus(pilot, app, self._header(app, "c0", PERF))
                await pilot.press("shift+down")
                await self._settle(pilot)
                seen["vertical"] = list(calls)

                calls.clear()
                await self._focus(pilot, app, self._header(app, "c0", PERF))
                await pilot.press("ctrl+up")
                await self._settle(pilot)
                seen["extreme"] = list(calls)

                # Control: a focused CARD must not reach the group seam.
                calls.clear()
                await self._focus(pilot, app, self._card(app, P_9030))
                await pilot.press("shift+down")
                await self._settle(pilot)
                seen["card_control"] = list(calls)

            # Control on the focus contract: when the seam declines the move
            # (returns None — its real behaviour until t1243_11), no refocus is
            # requested. Without this, "refocus was called" could just mean the
            # router always calls it.
            app2 = self.KanbanApp()
            self._spy_group_move(destination=None)
            refocus2 = self._spy_refocus_header()
            async with app2.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._focus(pilot, app2, self._header(app2, "c0", PERF))
                refocus2.clear()
                await pilot.press("shift+right")
                await self._settle(pilot)
                seen["declined_refocus"] = list(refocus2)

        self._run(go())
        self.assertEqual(seen["lateral"],
                         [("c0", PERF, [P_9000, P_9003], "lateral", 1)],
                         "the router must pass the group's members, in order")
        self.assertEqual(seen["vertical"],
                         [("c0", PERF, [P_9000, P_9003], "vertical", 1)])
        self.assertEqual(seen["extreme"],
                         [("c0", PERF, [P_9000, P_9003], "extreme", -1)])
        self.assertEqual(seen["card_control"], [],
                         "control: moving a card must never call the group seam")
        self.assertEqual(seen["refocus"], [("c1", PERF)],
                         "the focus contract: after a committed block move, the "
                         "header is refocused in the DESTINATION column")
        self.assertEqual(seen["declined_refocus"], [],
                         "control: a declined move requests no refocus, so the "
                         "assertion above is not just 'always called'")

    def test_member_move_writes_only_that_member(self):
        """Case 16: exact changed-path set."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                before = bf.snapshot(self.tree)
                await self._focus(pilot, app, self._card(app, P_9003))
                await pilot.press("shift+right")
                await self._settle(pilot)
                seen["diff"] = bf.diff_snapshots(before, bf.snapshot(self.tree))
                seen["col"] = app.manager.task_datas[P_9003].board_col

        self._run(go())
        self.assertEqual(seen["diff"]["changed"], {f"aitasks/{P_9003}"},
                         "a member's lateral move must write exactly its own file")
        self.assertEqual(seen["diff"]["added"], set())
        self.assertEqual(seen["col"], "c1")

    def test_child_card_movement_is_refused(self):
        """Case 17."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            app.expanded_tasks.add(P_9000)
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                before = bf.snapshot(self.tree)
                await self._focus(pilot, app, self._child_card(app, C_9000_1))
                await pilot.press("shift+right")
                await self._settle(pilot)
                seen["diff"] = bf.diff_snapshots(before, bf.snapshot(self.tree))

        self._run(go())
        self.assertEqual(seen["diff"]["changed"], set(),
                         "a child card must remain unmovable")

    def test_space_on_a_header_is_inert(self):
        """Case 18: pins the t1243_12 boundary."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._focus(pilot, app, self._header(app, "c0", PERF))
                await pilot.press("space")
                await self._settle(pilot)
                seen["header_marks"] = len(app.marked)
                # Control: `space` on a parent card DOES mark.
                await self._focus(pilot, app, self._card(app, P_9030))
                await pilot.press("space")
                await self._settle(pilot)
                seen["card_marks"] = len(app.marked)

        self._run(go())
        self.assertEqual(seen["header_marks"], 0,
                         "group marking is t1243_12 — `space` on a header does nothing")
        self.assertEqual(seen["card_marks"], 1, "control: `space` on a card marks it")

    def test_grouped_column_recomposes_while_ungrouped_keeps_the_fast_path(self):
        """Case 19: BOTH directions of `_move_needs_recompose`.

        A one-sided assertion would pass a predicate that always returns True,
        silently forfeiting the in-place DOM win on every board.
        """
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                calls = self._spy_recompose()

                # Ungrouped column: the in-place swap, no recompose.
                calls.clear()
                await self._focus(pilot, app, self._card(app, P_9031))
                await pilot.press("shift+down")
                await self._settle(pilot)
                seen["ungrouped"] = list(calls)

                # Grouped column: recompose.
                calls.clear()
                await self._focus(pilot, app, self._card(app, P_9004))
                await pilot.press("shift+up")
                await self._settle(pilot)
                seen["grouped"] = list(calls)

        self._run(go())
        self.assertEqual(seen["ungrouped"], [],
                         "an ungrouped column must keep the in-place DOM fast path")
        self.assertIn("c0", seen["grouped"],
                      "a grouped column must recompose so the DOM follows INV-R")

    def test_move_to_column_refuses_a_focused_header(self):
        """Cases 21-22: the palette bypasses check_action, so the action guards itself."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                pushed = self._spy_push_screen()

                # Direct call = the command-palette path.
                await self._focus(pilot, app, self._header(app, "c0", PERF))
                seen["gate"] = app.check_action("move_to_column", None)
                pushed.clear()
                app.action_move_to_column()
                await self._settle(pilot)
                seen["header_pushed"] = list(pushed)

                # Control (a): a PLACEHOLDER still gets the column-scoped review,
                # so the guard did not simply disable the branch.
                app.search_filter = "zzz_no_such_task_zzz"
                app.apply_filter()
                await self._settle(pilot)
                await self._focus(pilot, app, self._placeholder(app, "c3"))
                pushed.clear()
                app.action_move_to_column()
                await self._settle(pilot)
                seen["placeholder_pushed"] = list(pushed)
                app.search_filter = ""
                app.apply_filter()
                await self._settle(pilot)
                if app.screen_stack[1:]:
                    app.pop_screen()
                    await self._settle(pilot)

                # Control (b): a header focused WITH marks must still act on the
                # marks — `m`'s marks-win-over-focus contract.
                app.marked.toggle(P_9030)
                await self._focus(pilot, app, self._header(app, "c0", PERF))
                seen["gate_with_marks"] = app.check_action("move_to_column", None)
                pushed.clear()
                app.action_move_to_column()
                await self._settle(pilot)
                seen["marked_pushed"] = list(pushed)

        self._run(go())
        self.assertFalse(seen["gate"],
                         "the footer must not advertise `m` on a header")
        self.assertEqual(seen["header_pushed"], [],
                         "a focused header must not open a whole-column review")
        self.assertTrue(seen["placeholder_pushed"],
                        "control: a placeholder still opens the column-scoped review")
        self.assertTrue(seen["gate_with_marks"],
                        "marks win over focus — the gate stays True")
        self.assertTrue(seen["marked_pushed"],
                        "control: with marks, `m` still acts on the marked set")


if __name__ == "__main__":
    unittest.main()
