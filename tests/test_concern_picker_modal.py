"""Tests for the shadow concern-picker modal (t1037_3).

Exercises ConcernPickerModal's pure-UI contract (no clipboard backend):
- N concerns render as N focusable rows, first focused;
- space toggles a row's selection (☐ ↔ ☑);
- ``a`` selects all / deselects all;
- OK / Enter dismiss with exactly the selected Concerns, in order;
- ``A`` (copy ALL) dismisses with every concern regardless of toggles;
- Esc / Cancel dismiss with ``None``.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m unittest tests.test_concern_picker_modal
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Label  # noqa: E402

from monitor.concern_parser import Concern  # noqa: E402
from monitor.monitor_shared import ConcernPickerModal, _ConcernRow  # noqa: E402


def _sample_concerns() -> list[Concern]:
    return [
        Concern("high", "Step 7 ownership guard", "Guard double-commits the lock."),
        Concern("medium", "parser module", "Multi-block accumulation is undefined."),
        Concern("low", "docs", "A stray [bracket] in the body must not break markup."),
    ]


class _Host(App):
    """Minimal host App that pushes the modal and captures its dismiss value."""

    _UNSET = object()

    def __init__(
        self, concerns: list[Concern], narrow: bool = False,
        stale: bool = False, unrecovered: int = 0,
    ) -> None:
        super().__init__()
        self._concerns = concerns
        self._narrow = narrow
        self._stale = stale
        self._unrecovered = unrecovered
        self.result = self._UNSET

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        def _capture(value) -> None:
            self.result = value

        self.push_screen(
            ConcernPickerModal(
                self._concerns, narrow=self._narrow, stale=self._stale,
                unrecovered=self._unrecovered,
            ),
            _capture,
        )


def _screen_text(app: App) -> str:
    """The COMPOSITED screen, as the user sees it — not a widget's render string.

    Load-bearing for the narrow-layout tests: the failure being guarded is that
    Rich *drops* an overflowing segment during fold, so a `render()` string that
    contains the body proves nothing about whether the body reached the screen.
    """
    return "\n".join(
        strip.text for strip in app.screen._compositor.render_strips()
    )


class ConcernPickerModalTests(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_rows_rendered_and_first_focused(self):
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                rows = list(app.screen.query(_ConcernRow))
                self.assertEqual(len(rows), 3)
                self.assertIsInstance(app.screen.focused, _ConcernRow)
                self.assertIs(app.screen.focused, rows[0])

        self._run(runner())

    def test_space_toggles_focused_row_glyph(self):
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                row = list(app.screen.query(_ConcernRow))[0]
                self.assertFalse(row.selected)
                self.assertIn("☐", row.render())

                await pilot.press("space")
                await pilot.pause()
                self.assertTrue(row.selected)
                self.assertIn("☑", row.render())

                await pilot.press("space")
                await pilot.pause()
                self.assertFalse(row.selected)
                self.assertIn("☐", row.render())

        self._run(runner())

    def test_select_all_toggles_every_row(self):
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                rows = list(app.screen.query(_ConcernRow))

                await pilot.press("a")
                await pilot.pause()
                self.assertTrue(all(r.selected for r in rows))

                await pilot.press("a")
                await pilot.pause()
                self.assertTrue(not any(r.selected for r in rows))

        self._run(runner())

    def test_ok_dismisses_with_selected_in_order(self):
        async def runner():
            concerns = _sample_concerns()
            app = _Host(concerns)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                # Select row 0, skip row 1, select row 2.
                await pilot.press("space")   # row 0 selected (focused on mount)
                await pilot.press("down")    # focus row 1
                await pilot.press("down")    # focus row 2
                await pilot.press("space")   # row 2 selected
                await pilot.press("enter")   # confirm
                await pilot.pause()
                self.assertEqual(app.result, [concerns[0], concerns[2]])

        self._run(runner())

    def test_copy_all_dismisses_with_every_concern(self):
        async def runner():
            concerns = _sample_concerns()
            app = _Host(concerns)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                # Toggle one row on first to prove "copy ALL" ignores prior state.
                await pilot.press("space")
                await pilot.press("A")       # copy ALL
                await pilot.pause()
                self.assertEqual(app.result, concerns)

        self._run(runner())

    def test_escape_dismisses_with_none(self):
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()
                self.assertIsNone(app.result)

        self._run(runner())

    def test_stale_banner_shown_when_stale(self):
        async def runner():
            app = _Host(_sample_concerns(), stale=True)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                banners = list(app.screen.query("#concern-stale"))
                self.assertEqual(len(banners), 1)
                self.assertIn("stale", banners[0].render().plain.lower())

        self._run(runner())

    def test_no_stale_banner_by_default(self):
        async def runner():
            app = _Host(_sample_concerns())  # stale defaults to False
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                self.assertEqual(len(list(app.screen.query("#concern-stale"))), 0)

        self._run(runner())


def _mixed_concerns() -> list[Concern]:
    """Two actionable concerns around one informational — input order preserved."""
    return [
        Concern("high", "x.py:12", "AAA a blocking one.", "blocking", "CONFIRMED"),
        Concern("low", "accepted risk", "BBB an informational one.",
                "informational", "CONFIRMED"),
        Concern("medium", "y.py:34", "CCC a follow-up one.", "follow-up", "PLAUSIBLE"),
    ]


class ConcernPickerPartitionTests(unittest.TestCase):
    """The picker separates concerns that need action from informational ones (t1274)."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_sections_shown_and_input_order_preserved_within_them(self):
        async def runner():
            app = _Host(_mixed_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                headers = [
                    s.render().plain if hasattr(s.render(), "plain") else str(s.render())
                    for s in app.screen.query(".concern-section")
                ]
                self.assertEqual(len(headers), 2)
                self.assertIn("Needs addressing", headers[0])
                self.assertIn("Informational", headers[1])
                # Actionable pair first, in input order; informational last.
                rows = list(app.screen.query(_ConcernRow))
                self.assertEqual([r.original_index for r in rows], [0, 2, 1])

        self._run(runner())

    def test_no_headers_when_every_concern_is_in_one_partition(self):
        """A plan-review block (no disposition trailer) looks exactly as before."""
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                self.assertEqual(len(list(app.screen.query(".concern-section"))), 0)
                rows = list(app.screen.query(_ConcernRow))
                self.assertEqual([r.original_index for r in rows], [0, 1, 2])

        self._run(runner())

    def test_informational_row_carries_the_dim_class(self):
        async def runner():
            app = _Host(_mixed_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                by_index = {
                    r.original_index: r for r in app.screen.query(_ConcernRow)
                }
                self.assertTrue(by_index[1].has_class("informational"))
                self.assertFalse(by_index[0].has_class("informational"))
                self.assertFalse(by_index[2].has_class("informational"))

        self._run(runner())

    def test_select_all_skips_informational_but_copy_all_includes_it(self):
        async def runner():
            concerns = _mixed_concerns()
            app = _Host(concerns)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("a")
                await pilot.pause()
                by_index = {
                    r.original_index: r for r in app.screen.query(_ConcernRow)
                }
                self.assertTrue(by_index[0].selected)
                self.assertTrue(by_index[2].selected)
                self.assertFalse(by_index[1].selected)

                await pilot.press("A")
                await pilot.pause()
                self.assertEqual(app.result, concerns)

        self._run(runner())

    def test_context_line_names_the_split(self):
        async def runner():
            app = _Host(_mixed_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                context = list(app.screen.query("#concern-context"))[0]
                text = context.render()
                text = text.plain if hasattr(text, "plain") else str(text)
                self.assertIn("2 to address", text)
                self.assertIn("1 informational", text)

        self._run(runner())

    def test_selection_is_returned_in_original_order_after_partitioning(self):
        async def runner():
            concerns = _mixed_concerns()
            app = _Host(concerns)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                # DOM order is [0, 2, 1] after partitioning. Tick indexes 1 and
                # 2 — the pair whose DOM order (2, 1) is the REVERSE of their
                # input order, so a DOM-ordered result is detectably wrong.
                by_index = {
                    r.original_index: r for r in app.screen.query(_ConcernRow)
                }
                by_index[1].set_selected(True)
                by_index[2].set_selected(True)
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.result, [concerns[1], concerns[2]])

        self._run(runner())

    def test_duplicate_valued_concerns_are_selected_positionally(self):
        """`Concern` is a NamedTuple: two equal ones cannot be told apart by value.

        Selecting only the second must forward exactly one — not both, and not
        the wrong one.
        """
        async def runner():
            same = Concern("high", "dup", "identical body.", "blocking", "CONFIRMED")
            concerns = [same, same, Concern("low", "other", "different body.")]
            app = _Host(concerns)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                rows = list(app.screen.query(_ConcernRow))
                self.assertEqual([r.original_index for r in rows], [0, 1, 2])
                rows[1].set_selected(True)
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.result, [same])

        self._run(runner())

    def test_unrecovered_banner_shown_only_when_lines_were_lost(self):
        async def runner():
            app = _Host(_sample_concerns(), unrecovered=2)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                banners = list(app.screen.query("#concern-unrecovered"))
                self.assertEqual(len(banners), 1)
                self.assertIn("2 line(s)", banners[0].render().plain)

            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                self.assertEqual(
                    len(list(app.screen.query("#concern-unrecovered"))), 0
                )

        self._run(runner())


class ConcernPickerNarrowLayoutTests(unittest.TestCase):
    """A narrow row must still show its title AND its body (t1274).

    At the minimonitor companion width (~40 cols) the laid-out row gets ~28
    columns. On one line, Rich's fold drops the overflowing segment **whole**, so
    a region past ~19 characters erased the region *and* the body and the row
    rendered as a bare priority badge — the user-reported "concerns shown without
    a title". The two-line narrow layout is the fix.

    These assert the **composited screen**, not `render()`: the string always
    contained the body even when the screen did not.
    """

    #: A real region captured from a live shadow pane — and fully compliant with
    #: the producer's ≤30-char rule, which is why this was hit routinely.
    COMPLIANT_REGION = "authoring-conv.md:103"
    #: A real over-long region from another live pane (53 chars).
    LONG_REGION = "aiplans/archived/p40_dev_mirror_prod_test_account.md:565"

    def _run(self, coro):
        return asyncio.run(coro)

    def _render_at_40(self, region: str, narrow: bool) -> str:
        async def runner():
            app = _Host(
                [Concern("high", region, "BODYMARKER the body text.")], narrow=narrow
            )
            async with app.run_test(size=(40, 30)) as pilot:
                await pilot.pause()
                await pilot.pause()
                return _screen_text(app)

        return self._run(runner())

    def test_compliant_long_region_keeps_title_and_body_visible(self):
        screen = self._render_at_40(self.COMPLIANT_REGION, narrow=True)
        self.assertIn("authoring-conv", screen)
        self.assertIn("BODYMARKER", screen)

    def test_over_long_region_keeps_title_and_body_visible(self):
        screen = self._render_at_40(self.LONG_REGION, narrow=True)
        self.assertIn("aiplans/archived", screen)  # ellipsized, but present
        self.assertIn("BODYMARKER", screen)

    def test_single_line_layout_is_what_lost_them(self):
        """Negative control: prove the assertion above can fail.

        The same concern rendered on ONE line at the same width loses both — if
        this ever starts passing, the tests above have stopped discriminating.
        """
        screen = self._render_at_40(self.COMPLIANT_REGION, narrow=False)
        self.assertNotIn("authoring-conv", screen)
        self.assertNotIn("BODYMARKER", screen)

    def test_empty_region_renders_a_visible_placeholder(self):
        screen = self._render_at_40("", narrow=True)
        self.assertIn("(no region)", screen)
        self.assertIn("BODYMARKER", screen)

    def test_display_body_hides_the_trailer_from_the_row(self):
        """The row shows prose; the clipboard payload keeps the metadata."""
        async def runner():
            concern = Concern(
                "high", "x.py:1",
                "Real prose. Disposition: blocking. Verified: CONFIRMED.",
                "blocking", "CONFIRMED",
            )
            app = _Host([concern], narrow=True)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                rendered = list(app.screen.query(_ConcernRow))[0].render()
                self.assertIn("Real prose.", rendered)
                self.assertNotIn("Disposition:", rendered)
                self.assertNotIn("Verified:", rendered)

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
