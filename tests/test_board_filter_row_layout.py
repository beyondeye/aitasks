"""Filter-row geometry guards for the board (t1247).

The base-filter row (`[a All | l Locked | ... | z · By-Trail]  g Git  t Type`)
used to live inside `#view_col { width: 78 }` — a hardcoded column count that
was hand-bumped on every filter addition (26 -> 36 -> 48 -> 62 -> 78) and was
missed when By-Trail landed, truncating the row by 12 cells and leaving the
search box sitting where the missing segments should be.

The column is now auto-width, sized from `ViewSelector.content_width()` — the
same one-pass layout that produces the click-target offsets. These tests pin
that invariant (the row is never truncated) independently of the reflow
threshold, which is a UX knob rather than a correctness property.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_filter_row_layout.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from rich.cells import cell_len
from rich.text import Text

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

# Comfortably wider than the filter row + search box, so the non-reflowed
# layout is exercised.
WIDE = (160, 48)
# Below the reflow threshold (content 88 + 2 padding + 30 search = 120).
NARROW = (100, 48)

# View-col padding contributed by `#view_selector { padding: 0 1 }`.
SELECTOR_PADDING = 2


class BoardFilterRowLayoutTests(unittest.TestCase):
    """Drives the real KanbanApp via Pilot against the live `aitasks/` repo."""

    @classmethod
    def setUpClass(cls):
        cls._orig_cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        from aitask_board import KanbanApp, ViewSelector  # noqa: E402
        cls.KanbanApp = KanbanApp
        cls.ViewSelector = ViewSelector

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)

    def _run(self, coro):
        return asyncio.run(coro)

    async def _settle(self, pilot, times=2):
        for _ in range(times):
            await pilot.pause()

    def _assert_row_fits(self, app, where=""):
        """The filter row must be allocated at least its rendered width."""
        selector = app.query_one("#view_selector", self.ViewSelector)
        view_col = app.query_one("#view_col")
        needed = selector.content_width() + SELECTOR_PADDING
        self.assertGreaterEqual(
            view_col.region.width, needed,
            f"filter row truncated{where}: #view_col is {view_col.region.width} "
            f"cells but the selector needs {needed} "
            f"({selector.content_width()} content + {SELECTOR_PADDING} padding)")

    # --- 1. Pure unit: one width, no running app -------------------------

    def test_content_width_matches_rendered_cells(self):
        """content_width() equals the actual rendered width, with no app.

        This is the contract that lets layout and click hit-testing share a
        single number — if they ever diverge, clicks land on the wrong filter.
        """
        selector = self.ViewSelector("all", False, False)
        plain = Text.from_markup(selector.render()).plain
        self.assertEqual(selector.content_width(), cell_len(plain))

    def test_click_targets_end_at_content_width(self):
        """The last click target ends exactly at the reported width."""
        selector = self.ViewSelector("all", False, False)
        selector.render()  # populates _click_targets
        self.assertTrue(selector._click_targets, "expected click targets")
        self.assertEqual(selector._click_targets[-1][1], selector.content_width())

    def test_content_width_is_stable_across_active_state(self):
        """Highlighting a different base must not change the geometry."""
        widths = {
            self.ViewSelector(base, git, typ).content_width()
            for base in ("all", "locked", "free", "inflight", "bytopic", "bytrail")
            for git, typ in ((False, False), (True, True))
        }
        self.assertEqual(len(widths), 1, f"width varies with active state: {widths}")

    # --- 2. Live-surface guard: the row is not truncated ------------------

    def test_filter_row_not_truncated(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=WIDE) as pilot:
                await self._settle(pilot)
                self._assert_row_fits(app)
        self._run(go())

    def test_every_base_filter_segment_is_visible(self):
        """Each labelled segment lies inside the allocated column."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=WIDE) as pilot:
                await self._settle(pilot)
                selector = app.query_one("#view_selector", self.ViewSelector)
                selector.render()
                drawn = app.query_one("#view_col").region.width - SELECTOR_PADDING
                for start, end, target in selector._click_targets:
                    self.assertLessEqual(
                        end, drawn,
                        f"segment {target!r} spans [{start},{end}) but only "
                        f"{drawn} cells are drawn")
        self._run(go())

    # --- 3. Negative controls: the guard must actually discriminate -------

    def test_guard_holds_when_a_base_filter_is_added(self):
        """Adding a seventh filter must not truncate the row.

        Against the pre-fix hardcoded `width: 78` this fails, which is what
        proves the guard is load-bearing rather than incidentally satisfied.
        """
        async def go():
            extra = ("view_all", "Synthetic-Extra-Filter", "all")
            original = self.ViewSelector.BASES
            self.ViewSelector.BASES = list(original) + [extra]
            try:
                app = self.KanbanApp()
                async with app.run_test(size=WIDE) as pilot:
                    await self._settle(pilot)
                    selector = app.query_one("#view_selector", self.ViewSelector)
                    self.assertGreater(
                        selector.content_width(), 88,
                        "synthetic filter should have widened the row")
                    self._assert_row_fits(app, " with an extra base filter")
            finally:
                self.ViewSelector.BASES = original
        self._run(go())

    def test_guard_holds_when_a_label_widens(self):
        """A longer label (as a non-first-letter rebind produces) still fits."""
        async def go():
            original = self.ViewSelector.BASES
            # `z` is not the first letter of this label, so render_label emits
            # the wider `z · <label>` form.
            self.ViewSelector.BASES = [
                (a, ("Quite-A-Lot-Longer" if b == "By-Trail" else b), c)
                for a, b, c in original
            ]
            try:
                app = self.KanbanApp()
                async with app.run_test(size=WIDE) as pilot:
                    await self._settle(pilot)
                    self._assert_row_fits(app, " with a widened label")
            finally:
                self.ViewSelector.BASES = original
        self._run(go())

    def test_long_type_summary_does_not_widen_the_column(self):
        """The type-filter summary must not drive the auto-width."""
        async def go():
            from textual.widgets import Static
            app = self.KanbanApp()
            async with app.run_test(size=WIDE) as pilot:
                await self._settle(pilot)
                before = app.query_one("#view_col").region.width
                summary = app.query_one("#type_filter_summary", Static)
                summary.remove_class("hidden")
                summary.update("types: " + ", ".join(
                    ["bug", "feature", "enhancement", "chore", "documentation",
                     "performance", "refactor", "style", "test"] * 3))
                await self._settle(pilot, 3)
                self.assertEqual(app.query_one("#view_col").region.width, before)
                self._assert_row_fits(app, " with a long type summary")
        self._run(go())

    # --- 4. Reflow --------------------------------------------------------

    def test_wide_terminal_keeps_search_box_beside_filters(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=WIDE) as pilot:
                await self._settle(pilot)
                self.assertFalse(app.query_one("#filter_area").has_class("narrow"))
                search = app.query_one("#search_box")
                view_col = app.query_one("#view_col")
                # Side by side: the search box starts after the filter column.
                self.assertGreaterEqual(search.region.x, view_col.region.right)
                self.assertGreaterEqual(
                    search.outer_size.width, app.FILTER_SEARCH_MIN_WIDTH)
        self._run(go())

    def test_narrow_terminal_reflows_search_box_below(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=NARROW) as pilot:
                await self._settle(pilot)
                self.assertTrue(app.query_one("#filter_area").has_class("narrow"))
                search = app.query_one("#search_box")
                view_col = app.query_one("#view_col")
                # Stacked: the search box is below, not beside.
                self.assertGreaterEqual(search.region.y, view_col.region.bottom)
                self.assertGreaterEqual(
                    search.outer_size.width, app.FILTER_SEARCH_MIN_WIDTH)
        self._run(go())

    def test_reflow_threshold_tracks_the_selector_width(self):
        """The breakpoint is derived, not hardcoded: a wider row reflows sooner."""
        async def go():
            async def measure_at(width):
                app = self.KanbanApp()
                async with app.run_test(size=(width, 48)) as pilot:
                    await self._settle(pilot)
                    self._assert_row_fits(app, f" at width {width}")
                    return (app.query_one("#filter_area").has_class("narrow"),
                            app.query_one("#search_box").outer_size.width)

            app = self.KanbanApp()
            async with app.run_test(size=WIDE) as pilot:
                await self._settle(pilot)
                floor = app.FILTER_SEARCH_MIN_WIDTH
                threshold = (app.query_one("#view_selector", self.ViewSelector)
                             .content_width() + SELECTOR_PADDING + floor)

            # At the bound: still side by side, and the search box is exactly at
            # its floor — this is what makes the floor real without a duplicated
            # CSS `min-width`.
            at_narrow, at_search = await measure_at(threshold)
            self.assertFalse(at_narrow, "at threshold: side by side")
            self.assertGreaterEqual(
                at_search, floor,
                f"at threshold the search box got {at_search} cells, below the "
                f"{floor}-cell floor")

            # One cell over the bound: reflowed, search box spans the row.
            below_narrow, below_search = await measure_at(threshold - 1)
            self.assertTrue(below_narrow, "below threshold: reflowed")
            self.assertGreaterEqual(below_search, floor)
        self._run(go())

    # --- 5. Click targeting still lands on the right filter ---------------

    def test_click_dispatches_to_the_expected_base_filter(self):
        """Clicking a segment's midpoint selects that filter, in both layouts."""
        async def go():
            for size in (WIDE, NARROW):
                app = self.KanbanApp()
                async with app.run_test(size=size) as pilot:
                    await self._settle(pilot)
                    selector = app.query_one("#view_selector", self.ViewSelector)
                    selector.render()
                    targets = {t: (s, e) for s, e, t in selector._click_targets}
                    # Restrict to filters whose activation is cheap and has no
                    # dialog / worker side effects.
                    for base in ("locked", "free", "all"):
                        start, end = targets[base]
                        # +1 undoes the `padding: 0 1` offset on_click subtracts.
                        x = (start + end) // 2 + 1
                        selector.on_click(SimpleNamespace(x=x))
                        await self._settle(pilot)
                        self.assertEqual(
                            app.base_filter, base,
                            f"click at x={x} (size={size}) selected "
                            f"{app.base_filter!r}, expected {base!r}")
        self._run(go())


if __name__ == "__main__":
    unittest.main()
