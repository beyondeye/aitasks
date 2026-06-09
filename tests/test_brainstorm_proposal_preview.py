"""Pilot tests for the reusable ProposalPreviewPane (t945_1, t945_2).

The pane is the shared side-by-side proposal viewer that the explore (t945_2)
and module-decompose (t945_3) wizard config steps mount next to their free-text
input. This is the "internal harness": it drives the widget directly
(populate / minimap build / scroll-to-section / reflow-stable scroll / ratio
class toggling) without wiring it into a wizard.

t945_2 refactored the pane from an inline minimap (mounted inside the scroll)
to a **fixed minimap pane beside a scrollable SectionAwareMarkdown** — the
minimap stays visible while the proposal scrolls, and section navigation routes
through ``SectionAwareMarkdown.request_scroll_to_section`` (exact rendered-heading
scroll, no overshoot). The tests below assert against that layout: the minimap
is composed once and toggled via ``display``; scrolling happens on the inner
``#preview_proposal_content`` content widget.
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
from section_viewer import SectionRow, SectionAwareMarkdown  # noqa: E402


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


def _content(pane: ProposalPreviewPane) -> SectionAwareMarkdown:
    return pane.query_one("#preview_proposal_content", SectionAwareMarkdown)


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
                # Minimap is a visible sibling pane (not inlined in the scroll).
                minimap = pane.query_one(".preview_proposal_minimap")
                self.assertTrue(minimap.display)

        self._run(runner())

    def test_populate_without_sections_hides_minimap(self):
        async def runner():
            app = _HostApp()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_NO_SECTIONS)
                await pilot.pause()
                self.assertEqual(len(list(pane.query(SectionRow))), 0)
                # The minimap widget still exists (composed once) but is hidden
                # so the proposal takes the full pane width.
                minimap = pane.query_one(".preview_proposal_minimap")
                self.assertFalse(minimap.display)
                self.assertIsNone(pane._parsed)

        self._run(runner())

    def test_repopulate_toggles_minimap_visibility(self):
        async def runner():
            app = _HostApp()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                await pilot.pause()
                self.assertEqual(len(list(pane.query(SectionRow))), 3)
                self.assertTrue(
                    pane.query_one(".preview_proposal_minimap").display
                )
                # Re-populate with section-less content hides the minimap and
                # clears its rows.
                pane.populate(PROPOSAL_NO_SECTIONS)
                await pilot.pause()
                self.assertEqual(len(list(pane.query(SectionRow))), 0)
                self.assertFalse(
                    pane.query_one(".preview_proposal_minimap").display
                )

        self._run(runner())

    def test_scroll_to_section_scrolls_down_for_later_section(self):
        async def runner():
            app = _HostApp()
            # Narrow + short so the long proposal is definitely scrollable.
            async with app.run_test(size=(40, 12)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                content = _content(pane)
                # Let the markdown render (async) so it becomes scrollable.
                for _ in range(8):
                    await pilot.pause()
                self.assertGreater(content.max_scroll_y, 0)
                start = content.scroll_offset.y
                pane.scroll_to_section("telemetry")
                for _ in range(6):
                    await pilot.pause()
                self.assertGreater(content.scroll_offset.y, start)

        self._run(runner())

    def test_scroll_to_section_unknown_is_noop(self):
        async def runner():
            app = _HostApp()
            async with app.run_test(size=(40, 12)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                content = _content(pane)
                for _ in range(8):
                    await pilot.pause()
                start = content.scroll_offset.y
                pane.scroll_to_section("does_not_exist")  # must not raise
                for _ in range(3):
                    await pilot.pause()
                self.assertEqual(content.scroll_offset.y, start)

        self._run(runner())

    def test_on_ratio_change_preserves_top_line_after_width_reflow(self):
        async def runner():
            app = _HostApp()
            async with app.run_test(size=(40, 12)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                content = _content(pane)
                for _ in range(8):
                    await pilot.pause()
                self.assertGreater(content.max_scroll_y, 0)
                # Scroll roughly to the middle of the content pane.
                mid = content.max_scroll_y // 2
                content.scroll_to(y=mid, animate=False)
                await pilot.pause()
                total = pane._text.count("\n") + 1
                top_line_before = round(
                    content.scroll_offset.y / content.max_scroll_y * total
                )
                # Capture, then force a reflow by widening the whole pane.
                pane.on_ratio_change()
                pane.styles.width = 90
                for _ in range(6):
                    await pilot.pause()
                if content.max_scroll_y > 0:
                    top_line_after = round(
                        content.scroll_offset.y / content.max_scroll_y * total
                    )
                    # Reflow changes wrapping/heights; allow a small tolerance.
                    self.assertLessEqual(
                        abs(top_line_after - top_line_before), 3
                    )

        self._run(runner())


class ApplyPreviewRatioTests(unittest.TestCase):
    """Exercise the ratio_* class toggling used by ctrl+shift+b (cycle width)."""

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


class PreviewFocusRingTests(unittest.TestCase):
    """Tab focus cycle across inputs → minimap → proposal markdown (t945_3).

    Drives ``BrainstormApp._preview_focus_ring`` / ``_cycle_preview_focus``
    against a host that reproduces the config-with-preview layout (a
    ``.config_preview_split`` holding the ``.config_preview_left`` inputs and the
    ``ProposalPreviewPane``). Both wizards (explore + decompose) share this path,
    so one set of tests covers both.
    """

    def _run(self, coro):
        return asyncio.run(coro)

    def _host(self):
        from textual.containers import Horizontal
        from textual.widgets import TextArea
        from brainstorm.brainstorm_app import BrainstormApp

        class _RingHost(App):
            # Borrow the real focus-ring logic so the test exercises shipping code.
            _preview_focus_ring = BrainstormApp._preview_focus_ring
            _cycle_preview_focus = BrainstormApp._cycle_preview_focus

            def compose(self) -> ComposeResult:
                yield Horizontal(
                    VerticalScroll(
                        TextArea("", id="in1"),
                        TextArea("", id="in2"),
                        classes="config_preview_left",
                    ),
                    ProposalPreviewPane(classes="config_preview_pane"),
                    classes="config_preview_split",
                )

        return _RingHost()

    def test_ring_order_inputs_then_minimap_then_content(self):
        async def runner():
            app = self._host()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                await pilot.pause()
                ring = app._preview_focus_ring()
                self.assertEqual(ring[0].id, "in1")
                self.assertEqual(ring[1].id, "in2")
                self.assertIn("preview_proposal_minimap", ring[2].classes)
                self.assertEqual(ring[3].id, "preview_proposal_content")

        self._run(runner())

    def test_cycle_steps_through_ring_and_wraps(self):
        async def runner():
            app = self._host()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                await pilot.pause()
                app.query_one("#in1").focus()
                await pilot.pause()

                app._cycle_preview_focus(forward=True)
                await pilot.pause()
                self.assertEqual(app.focused.id, "in2")

                app._cycle_preview_focus(forward=True)
                await pilot.pause()
                # Minimap zone: focus lands on its first section row.
                self.assertIsInstance(app.focused, SectionRow)

                app._cycle_preview_focus(forward=True)
                await pilot.pause()
                self.assertEqual(app.focused.id, "preview_proposal_content")

                app._cycle_preview_focus(forward=True)
                await pilot.pause()
                self.assertEqual(app.focused.id, "in1")  # wrapped

        self._run(runner())

    def test_reverse_cycle_from_first_input_wraps_to_content(self):
        async def runner():
            app = self._host()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                await pilot.pause()
                app.query_one("#in1").focus()
                await pilot.pause()
                app._cycle_preview_focus(forward=False)
                await pilot.pause()
                self.assertEqual(app.focused.id, "preview_proposal_content")

        self._run(runner())

    def test_tab_on_minimap_row_advances_to_proposal(self):
        # Regression: the minimap keeps SectionMinimap's priority `tab` binding
        # (BINDINGS merge across the MRO), so a real Tab press on a minimap row
        # fires ToggleFocus rather than reaching the app Tab router. The
        # on_section_minimap_toggle_focus handler must route it onward to the
        # markdown pane instead of leaving focus stuck on the minimap.
        async def runner():
            app = self._host()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                await pilot.pause()
                pane.query_one(".preview_proposal_minimap").focus_first_row()
                await pilot.pause()
                self.assertIsInstance(app.focused, SectionRow)
                await pilot.press("tab")
                await pilot.pause()
                self.assertEqual(app.focused.id, "preview_proposal_content")

        self._run(runner())

    def test_minimap_absent_from_ring_when_no_sections(self):
        async def runner():
            app = self._host()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_NO_SECTIONS)
                await pilot.pause()
                ring = app._preview_focus_ring()
                self.assertFalse(
                    any("preview_proposal_minimap" in w.classes for w in ring)
                )
                # Ring is inputs + the markdown content only.
                self.assertEqual(ring[-1].id, "preview_proposal_content")

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
