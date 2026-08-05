#!/usr/bin/env python3
"""Tests for the shared multi-row footer widget (t1418).

Two layers:

* Pure-function tests for ``plan_footer_rows`` — no mounting, no event loop.
* Render-level tests that mount the real widget in ``run_test(size=(w, h))`` and
  assert on actual geometry, per ``feedback_tui_render_level_verification``.
  Internal bookkeeping is deliberately NOT the subject: the failure this widget
  exists to prevent is "key is off-screen", which only geometry can show.
"""

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from rich.cells import cell_len  # noqa: E402
from textual.app import App  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.widgets import Footer, Static  # noqa: E402
from textual.widgets._footer import FooterKey, FooterLabel, KeyGroup  # noqa: E402

import multirow_footer  # noqa: E402
from multirow_footer import (  # noqa: E402
    DEFAULT_MAX_ROWS,
    MultiRowFooter,
    OverflowHint,
    footer_item_width,
    plan_footer_rows,
    refresh_max_rows,
)

# The board's shown key set as of t1418 (27 pre-existing + the 4 un-hidden).
# Kept here rather than imported so this module stays a widget test: it boots in
# milliseconds and does not depend on the board's fixture tree.
BOARD_KEYS = [
    ("?", "open_shortcuts_editor", "Keys"),
    ("q", "quit", "Quit"),
    ("shift+right", "move_task_right", "Task >"),
    ("shift+left", "move_task_left", "< Task"),
    ("shift+up", "move_task_up", "Task Up"),
    ("shift+down", "move_task_down", "Task Down"),
    ("ctrl+up", "move_task_top", "Task Top"),
    ("ctrl+down", "move_task_bottom", "Task Btm"),
    ("enter", "view_details", "View/Edit"),
    ("o", "sort_topic", "Sort Order"),
    ("r", "refresh_board", "Refresh"),
    ("R", "trail_refresh_agent", "Agent Refresh"),
    ("d", "trail_refresh_drift", "Freshness"),
    ("s", "sync_remote", "Sync"),
    ("S", "trail_sync", "Sync"),
    ("c", "commit_selected", "Commit"),
    ("C", "commit_all", "Commit All"),
    ("n", "create_task", "New Task"),
    ("p", "pick_task", "Pick"),
    ("w", "work_report", "Work Report"),
    ("b", "brainstorm_task", "Brainstorm"),
    ("T", "trail_task", "Trail"),
    ("#", "open_cross_repo", "Cross-repo"),
    ("x", "toggle_children", "Toggle Children"),
    ("space", "toggle_mark", "Mark"),
    ("m", "move_to_column", "Move to Col"),
    ("ctrl+right", "move_col_right", "Move Col >"),
    ("ctrl+left", "move_col_left", "< Move Col"),
    ("X", "toggle_column_collapsed", "Collapse Col"),
    ("O", "open_settings", "Options"),
]
#: 30 declared keys + Textual's command-palette key.
TOTAL_FOOTER_KEYS = len(BOARD_KEYS) + 1


def _host(footer_factory, bindings=None):
    """An App mounting one footer, built fresh per size (run_test pins size)."""

    class _Host(App):
        BINDINGS = [Binding(k, a, d) for k, a, d in (bindings or BOARD_KEYS)]

        def compose(self):
            yield Static("body")
            yield footer_factory()

    return _Host()


def _real_width(widget) -> int:
    """Columns the widget actually occupies: outer size PLUS its margins.

    ``outer_size`` excludes margins, so comparing a predicted cost against it
    alone would pass while the row overflows by exactly the margin.
    """
    margin = widget.styles.margin
    return widget.outer_size.width + margin.left + margin.right


class PlanFooterRowsTests(unittest.TestCase):
    """The pure planner. No Textual, no event loop."""

    def test_content_that_fits_stays_on_one_row(self):
        rows, dropped = plan_footer_rows([10, 10, 10], 100, 3)
        self.assertEqual(rows, [[0, 1, 2]])
        self.assertEqual(dropped, 0)

    def test_it_wraps_when_content_exceeds_the_width(self):
        rows, dropped = plan_footer_rows([10] * 6, 25, 3)
        self.assertEqual(rows, [[0, 1], [2, 3], [4, 5]])
        self.assertEqual(dropped, 0)

    def test_declaration_order_is_preserved(self):
        rows, dropped = plan_footer_rows([7] * 9, 25, 3)
        self.assertEqual(dropped, 0)
        self.assertEqual([i for row in rows for i in row], list(range(9)))

    def test_order_is_preserved_among_survivors_when_dropping(self):
        rows, dropped = plan_footer_rows([7] * 9, 20, 3)
        self.assertGreater(dropped, 0)
        survivors = [i for row in rows for i in row]
        self.assertEqual(survivors, sorted(survivors))
        self.assertEqual(survivors, list(range(len(survivors))), "dropped from tail")

    def test_it_is_deterministic(self):
        first = plan_footer_rows([9, 4, 12, 7, 3, 15], 30, 3)
        for _ in range(5):
            self.assertEqual(plan_footer_rows([9, 4, 12, 7, 3, 15], 30, 3), first)

    def test_it_never_exceeds_max_rows(self):
        rows, dropped = plan_footer_rows([10] * 40, 25, 3)
        self.assertEqual(len(rows), 3)
        self.assertGreater(dropped, 0)

    def test_max_rows_one_reproduces_single_row_behaviour(self):
        rows, dropped = plan_footer_rows([10] * 6, 25, 1)
        self.assertEqual(len(rows), 1)
        self.assertGreater(dropped, 0)

    def test_the_pinned_tail_is_never_dropped(self):
        costs = [10] * 20 + [12]
        rows, dropped = plan_footer_rows(
            costs, 30, 2, hint_cost=14, pinned_tail=1
        )
        self.assertGreater(dropped, 0)
        self.assertIn(len(costs) - 1, rows[-1], "palette key must survive")

    def test_the_last_row_leaves_room_for_the_hint_and_the_pinned_tail(self):
        costs = [10] * 20 + [12]
        rows, dropped = plan_footer_rows(
            costs, 30, 2, hint_cost=14, pinned_tail=1
        )
        used = sum(costs[i] for i in rows[-1])
        self.assertLessEqual(used + 14, 30)

    def test_the_pinned_tail_shares_the_last_content_row(self):
        """It must not sit alone on a row while the row above has content."""
        costs = [10] * 8 + [12]
        rows, dropped = plan_footer_rows(costs, 60, 3, hint_cost=14, pinned_tail=1)
        self.assertEqual(dropped, 0)
        self.assertGreater(len(rows[-1]), 1, f"palette alone on its row: {rows}")

    def test_coverage_wins_over_tidiness_when_reserving_would_drop_keys(self):
        """The reserve pass is skipped when it costs visible keys."""
        costs = [10] * 9 + [12]
        reserved, _ = plan_footer_rows(costs, 40, 3, hint_cost=14, pinned_tail=1)
        self.assertEqual(sum(len(r) for r in reserved), len(costs))

    def test_empty_input(self):
        self.assertEqual(plan_footer_rows([], 80, 3), ([], 0))

    def test_non_positive_width_degrades_to_one_row(self):
        rows, dropped = plan_footer_rows([10, 10], 0, 3)
        self.assertEqual(rows, [[0, 1]])
        self.assertEqual(dropped, 0)

    def test_zero_max_rows_degrades_to_one_row(self):
        rows, dropped = plan_footer_rows([10, 10], 50, 0)
        self.assertEqual(rows, [[0, 1]])
        self.assertEqual(dropped, 0)


class _RenderTestBase(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    async def _mount(self, pilot, app):
        await pilot.pause()
        return app.query_one(MultiRowFooter)

    def _keys(self, app):
        return list(app.query(FooterKey))

    def _palette(self, app):
        return next(
            k for k in self._keys(app) if k.has_class("-command-palette")
        )

    def _rows(self, app):
        rows = {}
        for key in self._keys(app):
            rows.setdefault(key.region.y, []).append(key)
        return [rows[y] for y in sorted(rows)]


class GeometryTests(_RenderTestBase):
    """The measured behaviour table from the t1418 plan, pinned."""

    # width -> (rows, keys placed). Measured against textual 8.2.7.
    EXPECTED = {
        460: (1, 31),
        440: (1, 31),
        400: (2, 31),
        240: (2, 31),
        200: (3, 31),
        160: (3, 31),
        120: (3, 26),
        100: (3, 22),
        80: (3, 15),
    }

    def test_row_count_and_key_count_per_width(self):
        async def runner():
            for width, (rows, placed) in self.EXPECTED.items():
                app = _host(
                    lambda: MultiRowFooter(
                        max_rows=3, hint_action="open_shortcuts_editor"
                    )
                )
                async with app.run_test(size=(width, 24)) as pilot:
                    footer = await self._mount(pilot, app)
                    self.assertEqual(
                        footer.size.height, rows, f"row count at {width} cols"
                    )
                    self.assertEqual(
                        len(self._keys(app)), placed, f"keys shown at {width} cols"
                    )

        self._run(runner())

    def test_no_key_is_ever_clipped(self):
        async def runner():
            for width in self.EXPECTED:
                app = _host(lambda: MultiRowFooter(max_rows=3))
                async with app.run_test(size=(width, 24)) as pilot:
                    await self._mount(pilot, app)
                    for key in self._keys(app):
                        self.assertLessEqual(
                            key.region.right,
                            width,
                            f"{key.key} runs off the right edge at {width} cols",
                        )

        self._run(runner())

    def test_nothing_overlaps_the_command_palette_key(self):
        async def runner():
            for width in self.EXPECTED:
                app = _host(lambda: MultiRowFooter(max_rows=3))
                async with app.run_test(size=(width, 24)) as pilot:
                    await self._mount(pilot, app)
                    palette = self._palette(app)
                    for key in self._keys(app):
                        if key is palette or key.region.y != palette.region.y:
                            continue
                        self.assertLessEqual(
                            key.region.right,
                            palette.region.x,
                            f"{key.key} overlaps ctrl+p at {width} cols",
                        )

        self._run(runner())

    def test_the_palette_key_anchors_the_last_row_and_is_not_alone(self):
        async def runner():
            for width in self.EXPECTED:
                app = _host(lambda: MultiRowFooter(max_rows=3))
                async with app.run_test(size=(width, 24)) as pilot:
                    await self._mount(pilot, app)
                    rows = self._rows(app)
                    palette = self._palette(app)
                    self.assertIn(
                        palette, rows[-1], f"ctrl+p not on the last row at {width}"
                    )
                    if len(rows) > 1:
                        self.assertGreater(
                            len(rows[-1]),
                            1,
                            f"ctrl+p sits alone on its row at {width} cols",
                        )

        self._run(runner())

    def test_per_row_membership_at_160(self):
        """One width pinned key-by-key, so a reflow regression is legible."""

        async def runner():
            app = _host(lambda: MultiRowFooter(max_rows=3))
            async with app.run_test(size=(160, 24)) as pilot:
                await self._mount(pilot, app)
                rows = [[k.key for k in row] for row in self._rows(app)]
                self.assertEqual(len(rows), 3)
                self.assertEqual(rows[0][0], "question_mark")
                self.assertEqual(rows[-1][-1], "ctrl+p")
                flat = [k for row in rows for k in row]
                self.assertEqual(len(flat), TOTAL_FOOTER_KEYS)
                self.assertEqual(len(set(flat)), len(flat), "a key was duplicated")

        self._run(runner())


class OverflowHintTests(_RenderTestBase):
    def test_the_hint_appears_only_when_keys_were_dropped(self):
        """Guards a spurious `+N more` while the row still has room."""

        async def runner():
            for width, expected in ((200, False), (160, False), (120, True)):
                app = _host(
                    lambda: MultiRowFooter(
                        max_rows=3, hint_action="open_shortcuts_editor"
                    )
                )
                async with app.run_test(size=(width, 24)) as pilot:
                    await self._mount(pilot, app)
                    hints = list(app.query(OverflowHint))
                    self.assertEqual(
                        bool(hints), expected, f"hint presence at {width} cols"
                    )

        self._run(runner())

    def test_the_hint_counts_exactly_the_dropped_keys(self):
        async def runner():
            app = _host(
                lambda: MultiRowFooter(
                    max_rows=3, hint_action="open_shortcuts_editor"
                )
            )
            async with app.run_test(size=(120, 24)) as pilot:
                await self._mount(pilot, app)
                hint = app.query_one(OverflowHint)
                shown = len(self._keys(app))
                self.assertEqual(
                    str(hint.content), f"+{TOTAL_FOOTER_KEYS - shown} more (?)"
                )

        self._run(runner())

    def test_the_hint_names_a_remapped_key_not_a_hardcoded_one(self):
        """The affordance must point at the key that actually opens the editor.

        Resolving via ``resolve_key(<app scope>, "open_shortcuts_editor")``
        cannot do this: the action is registered under the ``shared`` scope and
        is deliberately not shadowed into the app scope, so the lookup returns
        None and any literal fallback goes stale for exactly the users who
        rebound it.
        """

        async def runner():
            remapped = [
                ("f1" if action == "open_shortcuts_editor" else key, action, desc)
                for key, action, desc in BOARD_KEYS
            ]
            app = _host(
                lambda: MultiRowFooter(
                    max_rows=3, hint_action="open_shortcuts_editor"
                ),
                bindings=remapped,
            )
            async with app.run_test(size=(120, 24)) as pilot:
                await self._mount(pilot, app)
                hint = app.query_one(OverflowHint)
                self.assertIn("(f1)", str(hint.content))
                self.assertNotIn("(?)", str(hint.content))

        self._run(runner())

    def test_the_hint_degrades_when_the_action_has_no_binding(self):
        async def runner():
            app = _host(lambda: MultiRowFooter(max_rows=3, hint_action="nope"))
            async with app.run_test(size=(120, 24)) as pilot:
                await self._mount(pilot, app)
                hint = app.query_one(OverflowHint)
                self.assertNotIn("(", str(hint.content))
                self.assertTrue(str(hint.content).endswith("more"))

        self._run(runner())

    def test_the_hint_itself_never_overflows_the_row(self):
        async def runner():
            for width in (120, 100, 80):
                app = _host(
                    lambda: MultiRowFooter(
                        max_rows=3, hint_action="open_shortcuts_editor"
                    )
                )
                async with app.run_test(size=(width, 24)) as pilot:
                    await self._mount(pilot, app)
                    hint = app.query_one(OverflowHint)
                    self.assertLessEqual(hint.region.right, width)

        self._run(runner())


class WidthModelGroundTruthTests(_RenderTestBase):
    """``footer_item_width`` vs the geometry Textual actually produced.

    This is the tripwire for the model's coupling to Textual's private padding /
    margin constants: a version bump that shifts any of them fails here loudly
    instead of silently clipping keys off the right edge.

    Every *planner input* is covered, not just plain keys — group captions,
    both KeyGroup flavours and the command-palette key each follow a different
    rule, and each is checked in compact and non-compact fingering.
    """

    NAV = Binding.Group(description="Nav", compact=False)
    ZOOM = Binding.Group(description="Zoom", compact=True)
    MIXED = [
        ("a", "alpha", "Alpha"),
        ("ctrl+s", "save", "Save All"),
    ]

    def _bindings(self):
        return [Binding(k, a, d) for k, a, d in self.MIXED] + [
            Binding("left", "nav_left", "Left", group=self.NAV),
            Binding("right", "nav_right", "Right", group=self.NAV),
            Binding("plus", "zoom_in", "In", group=self.ZOOM),
            Binding("minus", "zoom_out", "Out", group=self.ZOOM),
        ]

    def _measure(self, compact):
        """Measure every composed row item AFTER mount.

        Widths are read post-layout and reduced to plain data inside the running
        app: ``HorizontalGroup(*children)`` keeps its children *pending* until
        mount, so a compose-time capture sees an empty list, and reading geometry
        off widgets after the app has exited is not meaningful either.
        """

        async def runner():
            class _Host(App):
                BINDINGS = self._bindings()

                def compose(self):
                    yield Static("body")
                    yield MultiRowFooter(max_rows=3, compact=compact)

            app = _Host()
            async with app.run_test(size=(200, 24)) as pilot:
                await pilot.pause()
                footer = app.query_one(MultiRowFooter)
                measured = []
                for row in footer.children:
                    for item in row.children:
                        measured.append(
                            {
                                "kind": type(item).__name__,
                                "predicted": footer_item_width(
                                    item, footer_compact=compact
                                ),
                                "real": _real_width(item),
                                "group_compact": item.has_class("-compact"),
                                "palette": item.has_class("-command-palette"),
                                "children_naive": sum(
                                    _real_width(c) for c in item.children
                                ),
                            }
                        )
                return measured

        return self._run(runner())

    def test_every_composed_item_matches_its_real_width(self):
        for compact in (False, True):
            items = self._measure(compact)
            kinds = {item["kind"] for item in items}
            # Fail loudly rather than pass vacuously if the fixture stops
            # producing one of the shapes this test exists to cover.
            self.assertTrue(
                {"FooterKey", "KeyGroup", "FooterLabel"} <= kinds,
                f"fixture did not produce every item kind: {kinds}",
            )
            for item in items:
                self.assertEqual(
                    item["predicted"],
                    item["real"],
                    f"{item['kind']} width wrong (compact={compact})",
                )

    def test_both_key_group_flavours_are_exercised(self):
        groups = [i for i in self._measure(False) if i["kind"] == "KeyGroup"]
        self.assertEqual(len(groups), 2)
        self.assertTrue(any(g["group_compact"] for g in groups))
        self.assertTrue(any(not g["group_compact"] for g in groups))

    def test_grouped_child_margins_collapse(self):
        """Two 1-cell children measure 5, not 6 — the term a naive sum misses."""
        group = next(
            g
            for g in self._measure(False)
            if g["kind"] == "KeyGroup" and not g["group_compact"]
        )
        self.assertEqual(group["real"], 5)
        self.assertGreater(
            group["children_naive"], group["real"], "margins did not collapse"
        )

    def test_the_command_palette_key_is_covered(self):
        for compact in (False, True):
            palette = next(p for p in self._measure(compact) if p["palette"])
            self.assertEqual(palette["predicted"], palette["real"])


class WideCharacterTests(_RenderTestBase):
    """Cells, not characters.

    A ``len()``-based cost is a *silently* clipping bug rather than a failing
    one. Measured before the fix: with ``len()`` costs and CJK labels at 40
    columns, two keys rendered at x-right 48 and 60 — entirely off-screen.
    """

    WIDE = [
        ("a", "save", "保存文件"),
        ("b", "open", "打开项目"),
        ("c", "close", "关闭窗口"),
        ("d", "refresh", "刷新列表"),
        ("e", "settings", "设置选项"),
    ]

    def test_wide_descriptions_are_measured_in_cells(self):
        async def runner():
            app = _host(lambda: MultiRowFooter(max_rows=3), bindings=self.WIDE)
            async with app.run_test(size=(200, 24)) as pilot:
                await self._mount(pilot, app)
                key = next(k for k in self._keys(app) if k.key == "a")
                self.assertEqual(cell_len(key.description), 8)
                self.assertEqual(footer_item_width(key), _real_width(key))
                self.assertEqual(footer_item_width(key), 12)

        self._run(runner())

    def test_a_wide_group_caption_is_measured_in_cells(self):
        async def runner():
            group = Binding.Group(description="导航栏", compact=False)

            class _Host(App):
                BINDINGS = [
                    Binding("left", "nav_left", "L", group=group),
                    Binding("right", "nav_right", "R", group=group),
                ]

                def compose(self):
                    yield Static("body")
                    yield MultiRowFooter(max_rows=3)

            app = _Host()
            async with app.run_test(size=(200, 24)) as pilot:
                await pilot.pause()
                footer = app.query_one(MultiRowFooter)
                labels = [
                    item
                    for row in footer.children
                    for item in row.children
                    if isinstance(item, FooterLabel)
                ]
                self.assertEqual(len(labels), 1, "fixture produced no group caption")
                label = labels[0]
                self.assertEqual(cell_len(str(label.content)), 6)
                self.assertEqual(footer_item_width(label), _real_width(label))
                self.assertEqual(footer_item_width(label), 7)

        self._run(runner())

    def test_wide_labels_do_not_overflow_a_narrow_row(self):
        """Sweep widths, because most of them cannot discriminate.

        A character-based cost underestimates each of these keys by 4 columns,
        but the width reserved for the palette key absorbs the error at most
        widths — at 40 columns a ``len()`` build packs 3 keys per row and still
        fits. Verified against a ``cell_len = len`` mutation: 42 and 48 pass
        regardless, while 44/46 push `d` to x-right 48 and 52/56 push `e` to 60.
        Keep the discriminating widths in this list.
        """

        async def runner():
            for width in (40, 44, 46, 52, 56, 60):
                app = _host(lambda: MultiRowFooter(max_rows=3), bindings=self.WIDE)
                async with app.run_test(size=(width, 24)) as pilot:
                    await self._mount(pilot, app)
                    for key in self._keys(app):
                        self.assertLessEqual(
                            key.region.right,
                            width,
                            f"{key.key} overflows at {width} cols with wide labels",
                        )

        self._run(runner())


class ResizeSettlingTests(_RenderTestBase):
    """A resize must reflow, and the reflow must terminate.

    The footer's ``height: auto`` changes when the row count changes, which emits
    a second ``Resize`` on the footer, which recomposes again: a real feedback
    path. It has to converge rather than flicker on a live terminal, so the
    envelope is asserted rather than assumed.
    """

    def _counting_footer(self):
        counter = {"compose": 0}

        class _Counting(MultiRowFooter):
            def compose(self):
                counter["compose"] += 1
                yield from super().compose()

        return _Counting, counter

    def test_a_resize_changes_the_row_count(self):
        async def runner():
            app = _host(lambda: MultiRowFooter(max_rows=3))
            async with app.run_test(size=(460, 24)) as pilot:
                footer = await self._mount(pilot, app)
                self.assertEqual(footer.size.height, 1)
                await pilot.resize_terminal(160, 24)
                for _ in range(4):
                    await pilot.pause()
                self.assertEqual(footer.size.height, 3)
                self.assertEqual(len(self._keys(app)), TOTAL_FOOTER_KEYS)

        self._run(runner())

    def test_recomposition_is_bounded_and_settles(self):
        async def runner():
            cls, counter = self._counting_footer()
            app = _host(lambda: cls(max_rows=3))
            async with app.run_test(size=(460, 24)) as pilot:
                for _ in range(6):
                    await pilot.pause()
                boot = counter["compose"]
                self.assertLessEqual(boot, 6, "boot recomposed excessively")

                for target, changes_rows in ((160, True), (100, False)):
                    before = counter["compose"]
                    await pilot.resize_terminal(target, 24)
                    for _ in range(8):
                        await pilot.pause()
                    delta = counter["compose"] - before
                    self.assertLessEqual(
                        delta,
                        2,
                        f"resize to {target} recomposed {delta}x "
                        f"(row count {'changed' if changes_rows else 'stable'})",
                    )
                    self.assertGreaterEqual(delta, 1, "resize did not reflow")

                    settled = counter["compose"]
                    for _ in range(10):
                        await pilot.pause()
                    self.assertEqual(
                        counter["compose"],
                        settled,
                        f"still recomposing while idle after resize to {target}",
                    )

        self._run(runner())


class NegativeControlTests(_RenderTestBase):
    """Proof that the coverage assertions discriminate.

    If these ever pass against the stock ``Footer``, the geometry tests above are
    no longer evidence of anything and must be re-derived.
    """

    def test_the_stock_footer_clips_at_200_columns(self):
        async def runner():
            width = 200
            app = _host(Footer)
            async with app.run_test(size=(width, 24)) as pilot:
                await pilot.pause()
                keys = list(app.query(FooterKey))
                clipped = [k for k in keys if k.region.right > width]
                self.assertTrue(
                    clipped,
                    "stock Footer no longer clips at 200 cols — the multi-row "
                    "coverage tests are no longer discriminating",
                )

        self._run(runner())

    def test_the_stock_footer_stays_one_row(self):
        async def runner():
            app = _host(Footer)
            async with app.run_test(size=(160, 24)) as pilot:
                await pilot.pause()
                self.assertEqual(app.query_one(Footer).size.height, 1)

        self._run(runner())


class MaxRowsConfigTests(unittest.TestCase):
    """``footer_max_rows`` from userconfig.yaml, mirroring test_shortcut_label_case."""

    def setUp(self):
        refresh_max_rows()
        self._prev_cwd = os.getcwd()
        self._prev_task_dir = os.environ.get("TASK_DIR")
        self._tmp = tempfile.TemporaryDirectory()
        self._meta = Path(self._tmp.name) / "aitasks" / "metadata"
        self._meta.mkdir(parents=True, exist_ok=True)
        os.chdir(self._tmp.name)

    def tearDown(self):
        os.chdir(self._prev_cwd)
        if self._prev_task_dir is None:
            os.environ.pop("TASK_DIR", None)
        else:
            os.environ["TASK_DIR"] = self._prev_task_dir
        self._tmp.cleanup()
        refresh_max_rows()

    def _write(self, body):
        (self._meta / "userconfig.yaml").write_text(body, encoding="utf-8")
        refresh_max_rows()

    def test_missing_file_uses_the_default(self):
        self.assertEqual(multirow_footer._resolve_max_rows(), DEFAULT_MAX_ROWS)

    def test_an_explicit_value_is_honored(self):
        self._write("footer_max_rows: 2\n")
        self.assertEqual(multirow_footer._resolve_max_rows(), 2)

    def test_one_row_is_allowed(self):
        self._write("footer_max_rows: 1\n")
        self.assertEqual(multirow_footer._resolve_max_rows(), 1)

    def test_unrelated_keys_leave_the_default(self):
        self._write("email: someone@example.com\n")
        self.assertEqual(multirow_footer._resolve_max_rows(), DEFAULT_MAX_ROWS)

    def test_out_of_range_falls_back(self):
        for value in ("0", "-3", "99"):
            self._write(f"footer_max_rows: {value}\n")
            self.assertEqual(multirow_footer._resolve_max_rows(), DEFAULT_MAX_ROWS)

    def test_non_numeric_falls_back(self):
        self._write("footer_max_rows: banana\n")
        self.assertEqual(multirow_footer._resolve_max_rows(), DEFAULT_MAX_ROWS)

    def test_a_bool_falls_back_rather_than_meaning_one_row(self):
        """YAML `true` is an int subclass; int(True) would silently mean 1 row."""
        self._write("footer_max_rows: true\n")
        self.assertEqual(multirow_footer._resolve_max_rows(), DEFAULT_MAX_ROWS)

    def test_malformed_yaml_fails_soft(self):
        """A gitignored userconfig must not crash every TUI at compose time."""
        self._write("footer_max_rows: [unclosed\n")
        self.assertEqual(multirow_footer._resolve_max_rows(), DEFAULT_MAX_ROWS)

    def test_the_value_is_cached_until_refresh(self):
        self._write("footer_max_rows: 2\n")
        self.assertEqual(multirow_footer._resolve_max_rows(), 2)
        (self._meta / "userconfig.yaml").write_text(
            "footer_max_rows: 1\n", encoding="utf-8"
        )
        self.assertEqual(multirow_footer._resolve_max_rows(), 2)
        refresh_max_rows()
        self.assertEqual(multirow_footer._resolve_max_rows(), 1)

    def test_task_dir_override_is_honored(self):
        (self._meta / "userconfig.yaml").write_text(
            "footer_max_rows: 1\n", encoding="utf-8"
        )
        scratch = Path(self._tmp.name) / "scratch" / "metadata"
        scratch.mkdir(parents=True, exist_ok=True)
        (scratch / "userconfig.yaml").write_text(
            "footer_max_rows: 2\n", encoding="utf-8"
        )
        os.environ["TASK_DIR"] = "scratch"
        refresh_max_rows()
        self.assertEqual(multirow_footer._resolve_max_rows(), 2)

    def test_an_explicit_max_rows_argument_wins_over_config(self):
        self._write("footer_max_rows: 1\n")
        self.assertEqual(MultiRowFooter(max_rows=3).max_rows, 3)
        self.assertEqual(MultiRowFooter().max_rows, 1)


class ConfiguredMaxRowsRenderTests(_RenderTestBase):
    """The setting reaches real geometry, not just the resolver."""

    def test_max_rows_caps_the_rendered_row_count(self):
        async def runner():
            # width -> {max_rows: (rows, keys)} measured at 200 columns.
            for max_rows, rows, keys in ((1, 1, 13), (2, 2, 29), (3, 3, 31)):
                app = _host(
                    lambda mr=max_rows: MultiRowFooter(
                        max_rows=mr, hint_action="open_shortcuts_editor"
                    )
                )
                async with app.run_test(size=(200, 24)) as pilot:
                    footer = await self._mount(pilot, app)
                    self.assertEqual(footer.size.height, rows)
                    self.assertEqual(len(self._keys(app)), keys)

        self._run(runner())

    def test_one_row_still_announces_what_it_hid(self):
        """The opt-out is honest: stock clips silently, this says `+N more`."""

        async def runner():
            app = _host(
                lambda: MultiRowFooter(
                    max_rows=1, hint_action="open_shortcuts_editor"
                )
            )
            async with app.run_test(size=(200, 24)) as pilot:
                await self._mount(pilot, app)
                self.assertEqual(
                    str(app.query_one(OverflowHint).content), "+18 more (?)"
                )

        self._run(runner())


if __name__ == "__main__":
    unittest.main(verbosity=2)
