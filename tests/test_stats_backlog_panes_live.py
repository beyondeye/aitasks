"""Live-render tests for the stats TUI backlog panes (t1544_5).

[smoke_render_backlog_panes_live] — the inline post-phase risk mitigation.

`tests/test_stats_backlog_panes.py` covers the pure row derivation and a bare
package import. Neither ever mounts a widget, so neither can catch:

  * `DataTable.add_columns` failing on a really-mounted table;
  * the net-flow pane's two-widget composite overlapping or clipping inside
    `#content`, which is a plain `Container` with **no scrollbar**;
  * `render_chart` silently taking its `plotext`-missing fallback — that path
    mounts a `Static` and returns early, so success and failure are BOTH
    "one `Static`" and a type-only assertion cannot tell them apart.

This uses `App.run_test` (headless, in-process). It is deliberately **not** in
`SERIAL_CARVE_OUT`: that carve-out exists for modules that boot a real TUI in a
**tmux pane** under a hard wall-clock boot budget, which a loaded worker pool
turns into a flake. `App.run_test` involves no tmux and no boot budget, and 90+
existing modules use it inside the parallel pool.
"""

from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_DIR / ".aitask-scripts"
for _p in (str(SCRIPTS), str(SCRIPTS / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from textual.containers import Container  # noqa: E402
from textual.widgets import DataTable, Static  # noqa: E402

from stats.panes import backlog as bk  # noqa: E402
from stats.stats_app import StatsApp  # noqa: E402

from test_stats_backlog_panes import _stats  # noqa: E402  (shared fixture builder)

#: Explicit terminal size — every geometry assertion below is meaningless
#: without one, and the default `run_test` size is not the target.
TERMINAL = (120, 40)


def _fixture():
    """A corpus with both blocks populated and real flow in every direction."""
    arrivals = {
        ("type:feature", 5): 12,
        ("type:bug", 5): 7,
        ("type:chore", 4): 3,
        ("kind:manual_verification", 5): 9,
        ("kind:risk_mitigation", 4): 4,
        ("kind:docs_gap", 3): 3,
    }
    departures = {
        ("type:feature", 3): 5,
        ("kind:manual_verification", 2): 2,
        ("kind:docs_gap", 3): 3,
    }
    return _stats(
        arrivals=arrivals,
        departures=departures,
        scope_arrivals={("parent", 5): 24, ("child", 5): 4, ("child", 4): 7, ("parent", 3): 3},
        scope_departures={("parent", 3): 5, ("child", 2): 2},
        excluded=Counter({"no_frontmatter": 3, "folded": 5}),
    )


class TestBacklogPanesRenderLive(unittest.IsolatedAsyncioTestCase):
    async def _mount_pane(self, pane_id):
        """Boot the real app, swap in the fixture, render `pane_id`.

        Returns the widgets the pane mounted into `#content`, each one's
        rendered text, the lines each one WANTS, and the rows `#content` has.

        `Static.render()` resolves its content against the active app, so the
        text must be extracted INSIDE the `run_test` block — outside it the call
        raises `NoActiveAppError`.
        """
        app = StatsApp()
        async with app.run_test(size=TERMINAL) as pilot:
            app.stats_data = _fixture()
            app._show_pane(pane_id)
            await pilot.pause()
            content = app.query_one("#content", Container)
            children = list(content.children)
            texts = [
                w.render().plain if isinstance(w, Static) else "" for w in children
            ]
            # Lines each widget WANTS, and the rows `#content` actually has.
            # Textual clips a child's `region` to its parent, so comparing
            # regions can never detect an overflow — the wanted-vs-available
            # line count is the question a non-scrolling container poses.
            wanted = [
                len(t.splitlines()) if isinstance(w, Static) else w.region.height
                for w, t in zip(children, texts)
            ]
            available = content.container_size.height
        return children, texts, wanted, available

    async def test_level_pane_mounts_a_populated_datatable(self):
        children, _texts, _wanted, _avail = await self._mount_pane("backlog.level")

        tables = [w for w in children if isinstance(w, DataTable)]
        self.assertEqual(len(tables), 1, f"expected one DataTable, got {children!r}")
        table = tables[0]
        # "Category" + Now + the horizon weeks.
        self.assertEqual(len(table.columns), 1 + bk.BACKLOG_WEEKS_DEFAULT)
        self.assertGreater(table.row_count, 0)

    async def test_level_pane_mounts_its_diagnostic_line(self):
        """The fixture excludes 8 tasks, so the tally must be on screen."""
        children, texts, _wanted, _avail = await self._mount_pane("backlog.level")

        statics = [t for w, t in zip(children, texts) if isinstance(w, Static)]
        self.assertEqual(len(statics), 1, f"expected one diagnostic Static, got {children!r}")
        self.assertIn("8 task(s)", statics[0])

    async def test_empty_level_pane_explains_itself_rather_than_saying_no_data(self):
        """An all-excluded corpus. The CLI prints the tally here because it is
        the EXPLANATION for the table's absence, not a footnote — a generic
        "No data" would report nothing where the CLI reports a data problem.

        This drives `_render_level`'s empty branch, which the pure-function
        tests cannot reach: they assert on `_level_rows`' return value, which
        stays correct even if the render path throws the message away.
        """
        app = StatsApp()
        async with app.run_test(size=TERMINAL) as pilot:
            app.stats_data = _stats(excluded=Counter({"no_frontmatter": 3, "folded": 5}))
            app._show_pane("backlog.level")
            await pilot.pause()
            content = app.query_one("#content", Container)
            children = list(content.children)
            texts = [w.render().plain for w in children if isinstance(w, Static)]

        self.assertEqual(len(children), 1, f"expected one Static, got {children!r}")
        self.assertNotIn(type(children[0]), (DataTable,))
        rendered = texts[0]
        self.assertIn("No open tasks could be placed in the backlog series.", rendered)
        self.assertIn("8 task(s)", rendered)
        self.assertIn("no_frontmatter: 3", rendered)

    async def test_empty_and_unexcluded_level_pane_says_no_open_tasks(self):
        """The other half of the CLI's two-branch empty message."""
        app = StatsApp()
        async with app.run_test(size=TERMINAL) as pilot:
            app.stats_data = _stats()
            app._show_pane("backlog.level")
            await pilot.pause()
            content = app.query_one("#content", Container)
            rendered = [
                w.render().plain for w in content.children if isinstance(w, Static)
            ][0]

        self.assertIn("No open tasks found.", rendered)
        self.assertNotIn("could not be placed", rendered)
        self.assertNotIn("task(s)", rendered)

    async def test_netflow_pane_mounts_exactly_two_widgets(self):
        children, _texts, _wanted, _avail = await self._mount_pane("backlog.netflow")
        self.assertEqual(len(children), 2, f"expected strip + chart, got {children!r}")
        self.assertTrue(all(isinstance(w, Static) for w in children))

    async def test_netflow_chart_is_a_real_chart_not_the_fallback(self):
        """`render_chart` mounts a Static and returns early when plotext is
        missing, so the two paths are indistinguishable by type."""
        _children, texts, _wanted, _avail = await self._mount_pane("backlog.netflow")
        rendered = texts[1]

        self.assertNotIn("plotext not installed", rendered)
        self.assertIn("Backlog Net Flow by Category", rendered)
        self.assertIn("█", rendered)

    async def test_netflow_strip_carries_the_totals_rows(self):
        _children, texts, _wanted, _avail = await self._mount_pane("backlog.netflow")
        rendered = texts[0]

        for row in ("ARRIVALS", "DEPARTURES", "NET"):
            self.assertIn(row, rendered)
        self.assertIn("Now*", rendered)

    async def _assert_fits(self, pane_id):
        """Everything the pane wants to draw fits the rows `#content` has.

        `#content` is a plain `Container` with no scrollbar, so a widget that
        wants more lines than are available is simply invisible below the fold.
        Textual clips a child's `region` to its parent, so a region-vs-region
        comparison can NEVER report an overflow — it is the wanted line count
        that has to be budgeted.
        """
        children, _texts, wanted, available = await self._mount_pane(pane_id)
        self.assertGreater(available, 0)
        self.assertLessEqual(
            sum(wanted),
            available,
            f"{pane_id} wants {sum(wanted)} rows "
            f"({list(zip((type(w).__name__ for w in children), wanted))}) "
            f"but #content has {available}",
        )

    async def test_netflow_fits_the_content_budget(self):
        await self._assert_fits("backlog.netflow")

    async def test_level_fits_the_content_budget(self):
        await self._assert_fits("backlog.level")


if __name__ == "__main__":
    unittest.main()
