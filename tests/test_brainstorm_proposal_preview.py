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

from brainstorm.brainstorm_app import (  # noqa: E402
    ProposalPreviewPane,
    _NumberedProposal,
)
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
    """Exercise the ratio_* class toggling used by alt+w (cycle width)."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_apply_ratio_toggles_classes_on_both_panes(self):
        async def runner():
            # t983_11: _apply_preview_ratio moved to ActionsWizardScreen.
            from brainstorm.brainstorm_app import ActionsWizardScreen

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
                apply = ActionsWizardScreen._apply_preview_ratio

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
        # t983_11: the focus-ring helpers moved to ActionsWizardScreen.
        from brainstorm.brainstorm_app import ActionsWizardScreen

        class _RingHost(App):
            # Borrow the real focus-ring logic so the test exercises shipping code.
            _preview_focus_ring = ActionsWizardScreen._preview_focus_ring
            _cycle_preview_focus = ActionsWizardScreen._cycle_preview_focus

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

    def test_ring_targets_numbered_view_when_toggled(self):
        # t954: in numbered mode the ring drops the minimap and ends on the
        # numbered source view instead of the markdown pane.
        async def runner():
            app = self._host()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                await pilot.pause()
                pane.toggle_numbered()
                await pilot.pause()
                ring = app._preview_focus_ring()
                self.assertEqual(ring[-1].id, "preview_proposal_numbered")
                self.assertFalse(
                    any("preview_proposal_minimap" in w.classes for w in ring)
                )
                self.assertFalse(
                    any(w.id == "preview_proposal_content" for w in ring)
                )

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


class NumberedViewTests(unittest.TestCase):
    """The alt+n numbered source-line view (t954).

    The numbered view renders the *raw* proposal source with a line-number
    gutter, one Rich Table row per source line, so numbers stay anchored even
    when a long line wraps on a narrow terminal.
    """

    # No trailing newline: raw line count == Syntax.highlight line count (the
    # highlighter drops the empty line after a final newline), so the expected
    # row count is simply len(split).
    PROPOSAL = (
        "# Goal\n"
        "\n"
        "Add a settings screen that lets users configure notification "
        "preferences and the theme; this line is intentionally long so it "
        "wraps on a narrow terminal.\n"
        "Short tail line."
    )

    def _run(self, coro):
        return asyncio.run(coro)

    def _numbered(self, pane: ProposalPreviewPane) -> _NumberedProposal:
        return pane.query_one("#preview_proposal_numbered", _NumberedProposal)

    def test_toggle_numbered_swaps_visible_widget(self):
        async def runner():
            app = _HostApp()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                await pilot.pause()
                md = _content(pane)
                num = self._numbered(pane)
                minimap = pane.query_one(".preview_proposal_minimap")
                # Default: markdown + minimap visible, numbered hidden.
                self.assertTrue(md.display)
                self.assertFalse(num.display)
                self.assertTrue(minimap.display)

                self.assertTrue(pane.toggle_numbered())
                await pilot.pause()
                self.assertTrue(num.display)
                self.assertFalse(md.display)
                self.assertFalse(minimap.display)

                # Toggle back → markdown returns; minimap reappears (sections).
                self.assertFalse(pane.toggle_numbered())
                await pilot.pause()
                self.assertTrue(md.display)
                self.assertFalse(num.display)
                self.assertTrue(minimap.display)

        self._run(runner())

    def test_toggle_back_keeps_minimap_hidden_without_sections(self):
        async def runner():
            app = _HostApp()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_NO_SECTIONS)
                await pilot.pause()
                minimap = pane.query_one(".preview_proposal_minimap")
                self.assertFalse(minimap.display)
                pane.toggle_numbered()
                await pilot.pause()
                pane.toggle_numbered()  # back to markdown
                await pilot.pause()
                # No sections → minimap stays hidden after the round-trip.
                self.assertFalse(minimap.display)

        self._run(runner())

    def test_populate_resets_to_markdown_mode(self):
        async def runner():
            app = _HostApp()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                await pilot.pause()
                pane.toggle_numbered()
                await pilot.pause()
                self.assertTrue(pane._numbered)
                # Re-populating (e.g. a fresh config step) snaps back to md.
                pane.populate(PROPOSAL_WITH_SECTIONS)
                await pilot.pause()
                self.assertFalse(pane._numbered)
                self.assertTrue(_content(pane).display)
                self.assertFalse(self._numbered(pane).display)

        self._run(runner())

    def test_one_table_row_per_source_line(self):
        async def runner():
            app = _HostApp()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(self.PROPOSAL)
                await pilot.pause()
                num = self._numbered(pane)
                expected = len(self.PROPOSAL.split("\n"))
                self.assertEqual(len(num._text.split("\n")), expected)
                # One Rich Table row per source line — the gutter numbering basis.
                self.assertEqual(num._table.row_count, expected)

        self._run(runner())

    def test_numbered_view_is_syntax_highlighted(self):
        # t954 follow-up: the numbered view markdown-highlights the source (Rich
        # Syntax), like codebrowser — so the per-line Text carries style spans.
        async def runner():
            app = _HostApp()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(self.PROPOSAL)
                await pilot.pause()
                num = self._numbered(pane)
                self.assertTrue(any(line.spans for line in num._lines))

        self._run(runner())

    def test_line_numbers_survive_narrow_width(self):
        async def runner():
            app = _HostApp()
            async with app.run_test(size=(40, 12)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(self.PROPOSAL)
                pane.toggle_numbered()
                await pilot.pause()
                num = self._numbered(pane)
                # Force a rebuild at the narrow width (where the long line wraps).
                num.set_text(self.PROPOSAL)
                await pilot.pause()
                expected = len(self.PROPOSAL.split("\n"))
                # Row count == logical source lines regardless of wrapping:
                # numbers track source lines, not wrapped terminal rows.
                self.assertEqual(num._table.row_count, expected)

        self._run(runner())


class PreviewKeyDispatchTests(unittest.TestCase):
    """Real key-dispatch coverage for the wizard preview keys.

    History: ``ctrl+shift+b`` / ``ctrl+shift+l`` (undeliverable chords) →
    ``alt+w`` / ``alt+n`` (t1018_1) → plain ``w`` / ``l`` (t1047). t1047 made
    them single keys, shown in the footer and context-scoped (via
    ``ActionsWizardScreen.check_action``) to when the proposal/minimap is
    focused — so a focused Mandate ``TextArea`` keeps ``w``/``l`` as typed text.

    The host borrows ``ActionsWizardScreen.BINDINGS`` and the two preview action
    methods verbatim and reproduces the config-with-preview layout, so the test
    exercises the shipping bindings + actions, not a copy of the key strings.
    These tests focus the proposal content before pressing (where the bindings
    apply); the TextArea-focused case below proves the bare key is typed there.
    """

    def _run(self, coro):
        return asyncio.run(coro)

    def _host(self):
        from textual.containers import Horizontal
        from textual.widgets import TextArea
        from brainstorm.brainstorm_app import ActionsWizardScreen

        class _KeyHost(App):
            # Borrow the shipping bindings + actions verbatim: pressing the bound
            # key here proves the real binding string is actually deliverable.
            BINDINGS = ActionsWizardScreen.BINDINGS
            action_cycle_preview_ratio = (
                ActionsWizardScreen.action_cycle_preview_ratio
            )
            action_toggle_preview_numbered = (
                ActionsWizardScreen.action_toggle_preview_numbered
            )
            # action_cycle_preview_ratio delegates to this helper.
            _apply_preview_ratio = ActionsWizardScreen._apply_preview_ratio

            def compose(self) -> ComposeResult:
                yield Horizontal(
                    VerticalScroll(
                        TextArea("", id="ta"),
                        classes="config_preview_left",
                    ),
                    ProposalPreviewPane(classes="config_preview_pane"),
                    classes="config_preview_split",
                )

        return _KeyHost()

    def test_w_press_cycles_preview_ratio(self):
        async def runner():
            app = self._host()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                left = app.query_one(".config_preview_left")
                app.query_one("#preview_proposal_content").focus()
                await pilot.pause()
                # balanced (0): no ratio class yet
                self.assertFalse(left.has_class("ratio_proposal_wide"))
                # w advances balanced -> proposal-wide (real key dispatch)
                await pilot.press("w")
                await pilot.pause()
                self.assertTrue(left.has_class("ratio_proposal_wide"))
                self.assertTrue(pane.has_class("ratio_proposal_wide"))

        self._run(runner())

    def test_l_press_toggles_numbered_view(self):
        async def runner():
            app = self._host()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                app.query_one("#preview_proposal_content").focus()
                await pilot.pause()
                self.assertFalse(getattr(pane, "_numbered", False))
                await pilot.press("l")
                await pilot.pause()
                self.assertTrue(pane._numbered)

        self._run(runner())

    def test_bare_key_typed_into_focused_textarea_does_not_toggle(self):
        # t1047 rationale for gating w/l to a focused proposal: while the Mandate
        # TextArea has focus, a bare letter is INSERTED as text and the screen
        # binding does NOT fire. (The wizard's check_action enforces this scope
        # in the real app; this host just shows the underlying key behaviour.)
        async def runner():
            app = self._host()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                left = app.query_one(".config_preview_left")
                ta = app.query_one("#ta")
                ta.focus()
                await pilot.pause()
                await pilot.press("w")
                await pilot.pause()
                # The key landed in the TextArea as text ...
                self.assertEqual(ta.text, "w")
                # ... and the preview binding did NOT fire.
                self.assertFalse(left.has_class("ratio_proposal_wide"))

        self._run(runner())

    def test_plain_letter_is_swallowed_by_focused_textarea(self):
        # Contrast with the above: a bare printable letter IS consumed as text
        # by the focused TextArea and never reaches the binding — which is
        # exactly why a plain letter could not be reused as the preview key.
        async def runner():
            app = self._host()
            async with app.run_test(size=(80, 24)) as pilot:
                pane = app.query_one(ProposalPreviewPane)
                pane.populate(PROPOSAL_WITH_SECTIONS)
                left = app.query_one(".config_preview_left")
                ta = app.query_one("#ta")
                ta.focus()
                await pilot.pause()
                await pilot.press("w")
                await pilot.pause()
                # Typed into the TextArea ...
                self.assertEqual(ta.text, "w")
                # ... and the ratio action did NOT fire.
                self.assertFalse(left.has_class("ratio_proposal_wide"))

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
