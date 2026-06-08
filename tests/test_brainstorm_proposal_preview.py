"""Pilot tests for the reusable ProposalPreviewPane (t945_1).

The pane is the shared side-by-side proposal viewer that the explore (t945_2)
and module-decompose (t945_3) wizard config steps mount next to their free-text
input. This is the "internal harness" for t945_1: it drives the widget directly
(populate / minimap build / scroll-to-section / reflow-stable scroll / ratio
class toggling) without wiring it into a wizard. End-to-end in-TUI behavior is
verified manually and exercised for real once t945_2 lands.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from textual.app import App, ComposeResult  # noqa: E402
from textual.containers import VerticalScroll  # noqa: E402

from brainstorm.brainstorm_app import ProposalPreviewPane  # noqa: E402
from section_viewer import SectionRow  # noqa: E402


PROPOSAL_WITH_SECTIONS = """\
# Proposal

<!-- section: auth -->
""" + "Use JWT.\n" * 40 + """\
<!-- /section: auth -->

<!-- section: storage -->
""" + "Postgres.\n" * 40 + """\
<!-- /section: storage -->

<!-- section: telemetry -->
""" + "OpenTelemetry.\n" * 40 + """\
<!-- /section: telemetry -->
"""

PROPOSAL_NO_SECTIONS = "# Proposal\n\nJust prose, no section markers.\n"


class _HostApp(App):
    """Minimal host that mounts a single ProposalPreviewPane."""

    def compose(self) -> ComposeResult:
        yield ProposalPreviewPane(id="pane")


class ProposalPreviewPaneTests(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_populate_builds_minimap_rows_per_section(self):
        async def runner():
            app = _HostApp()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                await pilot.pause()
                rows = list(pane.query(SectionRow))
                self.assertEqual(
                    [r.section_name for r in rows],
                    ["auth", "storage", "telemetry"],
                )

        self._run(runner())

    def test_populate_without_sections_mounts_no_minimap(self):
        async def runner():
            app = _HostApp()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_NO_SECTIONS)
                await pilot.pause()
                self.assertEqual(len(list(pane.query(SectionRow))), 0)
                self.assertEqual(
                    len(list(pane.query(".preview_proposal_minimap"))), 0
                )
                self.assertIsNone(pane._parsed)

        self._run(runner())

    def test_repopulate_replaces_minimap(self):
        async def runner():
            app = _HostApp()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                await pilot.pause()
                self.assertEqual(len(list(pane.query(SectionRow))), 3)
                # Re-populate with section-less content drops the old minimap.
                pane.populate(PROPOSAL_NO_SECTIONS)
                await pilot.pause()
                self.assertEqual(len(list(pane.query(SectionRow))), 0)
                self.assertEqual(
                    len(list(pane.query(".preview_proposal_minimap"))), 0
                )

        self._run(runner())

    def test_scroll_to_section_scrolls_down_for_later_section(self):
        async def runner():
            app = _HostApp()
            # Narrow + short so the long proposal is definitely scrollable.
            async with app.run_test(size=(40, 12)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                for _ in range(4):
                    await pilot.pause()
                self.assertGreater(pane.max_scroll_y, 0)
                start = pane.scroll_offset.y
                pane.scroll_to_section("telemetry")
                for _ in range(3):
                    await pilot.pause()
                self.assertGreater(pane.scroll_offset.y, start)

        self._run(runner())

    def test_scroll_to_section_unknown_is_noop(self):
        async def runner():
            app = _HostApp()
            async with app.run_test(size=(40, 12)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                for _ in range(4):
                    await pilot.pause()
                start = pane.scroll_offset.y
                pane.scroll_to_section("does_not_exist")  # must not raise
                await pilot.pause()
                self.assertEqual(pane.scroll_offset.y, start)

        self._run(runner())

    def test_on_ratio_change_preserves_top_line_after_width_reflow(self):
        async def runner():
            app = _HostApp()
            async with app.run_test(size=(40, 12)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                for _ in range(4):
                    await pilot.pause()
                self.assertGreater(pane.max_scroll_y, 0)
                # Scroll roughly to the middle.
                mid = pane.max_scroll_y // 2
                pane.scroll_to(y=mid, animate=False)
                await pilot.pause()
                total = pane._text.count("\n") + 1
                top_line_before = round(
                    pane.scroll_offset.y / pane.max_scroll_y * total
                )
                # Capture, then force a reflow by widening the pane.
                pane.on_ratio_change()
                pane.styles.width = 90
                for _ in range(4):
                    await pilot.pause()
                if pane.max_scroll_y > 0:
                    top_line_after = round(
                        pane.scroll_offset.y / pane.max_scroll_y * total
                    )
                    # Reflow changes wrapping/heights; allow a small tolerance.
                    self.assertLessEqual(
                        abs(top_line_after - top_line_before), 3
                    )

        self._run(runner())


class ApplyPreviewRatioTests(unittest.TestCase):
    """Exercise the ratio_* class toggling used by ctrl+b (cycle width)."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_apply_ratio_toggles_classes_on_both_panes(self):
        async def runner():
            from brainstorm.brainstorm_app import BrainstormApp

            class _RatioHost(App):
                def compose(self) -> ComposeResult:
                    yield VerticalScroll(
                        VerticalScroll(classes="config_preview_left"),
                        ProposalPreviewPane(classes="config_preview_pane"),
                    )

            app = _RatioHost()
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                left = app.query_one(".config_preview_left")
                pane = app.query_one(ProposalPreviewPane)
                apply = BrainstormApp._apply_preview_ratio

                # balanced (0): no ratio class
                apply(app, left, pane, 0)
                self.assertFalse(left.has_class("ratio_proposal_wide"))
                self.assertFalse(left.has_class("ratio_input_wide"))

                # proposal-wide (1)
                apply(app, left, pane, 1)
                self.assertTrue(left.has_class("ratio_proposal_wide"))
                self.assertTrue(pane.has_class("ratio_proposal_wide"))
                self.assertFalse(left.has_class("ratio_input_wide"))

                # input-wide (2): previous class cleared
                apply(app, left, pane, 2)
                self.assertTrue(left.has_class("ratio_input_wide"))
                self.assertTrue(pane.has_class("ratio_input_wide"))
                self.assertFalse(left.has_class("ratio_proposal_wide"))

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
