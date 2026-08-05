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
import re
import sys
import unittest
import unittest.mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Label  # noqa: E402

from tui_layout import NARROW_TERMINAL_WIDTH, is_narrow_terminal  # noqa: E402

from monitor.concern_parser import Concern  # noqa: E402
from monitor import monitor_shared  # noqa: E402
from monitor.monitor_shared import (  # noqa: E402
    ConcernBlockInspectModal, ConcernPickerModal, _ConcernRow,
)


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
        stale: bool = False, unrecovered: tuple[str, ...] = (),
        raw_block: str = "",
    ) -> None:
        super().__init__()
        self._concerns = concerns
        self._narrow = narrow
        self._stale = stale
        self._unrecovered = unrecovered
        self._raw_block = raw_block
        self.result = self._UNSET

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        def _capture(value) -> None:
            self.result = value

        self.push_screen(
            ConcernPickerModal(
                self._concerns, narrow=self._narrow, stale=self._stale,
                unrecovered=self._unrecovered, raw_block=self._raw_block,
            ),
            _capture,
        )


def _screen_rows(app: App) -> list[str]:
    """The composited screen row by row (t1293).

    The list form is what the clipping assertions need: "is this row's last
    column still the dialog border" is a per-row question that a single joined
    string cannot answer.
    """
    return [strip.text for strip in app.screen._compositor.render_strips()]


def _screen_text(app: App) -> str:
    """The COMPOSITED screen, as the user sees it — not a widget's render string.

    Load-bearing for the narrow-layout tests: the failure being guarded is that
    Rich *drops* an overflowing segment during fold, so a `render()` string that
    contains the body proves nothing about whether the body reached the screen.
    """
    return "\n".join(_screen_rows(app))


#: The thick-border glyph the picker dialog is drawn with.
_BORDER = "█"


def _flat_text(rows: list[str]) -> str:
    """Composited rows with borders removed and all whitespace collapsed.

    Needed for any assertion about a *phrase*: the compact help line wraps, so
    `u raw` is split across two rows and is not a contiguous substring of the
    screen even though the user plainly reads it as one (t1293).
    """
    stripped = " ".join(row.replace(_BORDER, " ") for row in rows)
    return " ".join(stripped.split())


def _clipped_rows(rows: list[str], width: int) -> list[str]:
    """Dialog rows whose right border fell off the screen (t1293).

    A row that *starts* with the border glyph is a dialog row; if it does not
    also end with one at column ``width - 1`` the dialog is wider than the
    screen and its rightmost columns — border and content alike — were cut.
    Empty for a correctly-sized dialog at any width.
    """
    return [
        row for row in rows
        if row.startswith(_BORDER)
        and not (len(row) >= width and row[width - 1] == _BORDER)
    ]


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
            app = _Host(
                _sample_concerns(),
                unrecovered=("- [ | region] no priority", "- [low | aaaa"),
            )
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                banners = list(app.screen.query("#concern-unrecovered"))
                self.assertEqual(len(banners), 1)
                banner = banners[0].render().plain
                # Count is DERIVED from the lines — it cannot disagree with what
                # the inspect view shows (t1293).
                self.assertIn("2 line(s)", banner)
                # The affordance must be named, with its bracket intact: an
                # unescaped `[u]` is Rich's underline tag and renders as nothing.
                self.assertIn("[u] inspect", banner)

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

    #: Every width the picker is supported at, read from the production
    #: constants so a retune cannot leave the sweep testing stale numbers: 40 is
    #: the measured minimonitor companion width (t1274), the middle entry is
    #: where the `.narrow` dialog's own minimum starts to bind, and the last is
    #: the tested floor (t1293).
    SUPPORTED_WIDTHS = (
        40,
        monitor_shared._PICKER_NARROW_MIN_WIDTH,
        monitor_shared._PICKER_MIN_COLS,
    )

    def _run(self, coro):
        return asyncio.run(coro)

    def _rows_at(self, width: int, region: str, narrow: bool,
                 height: int = 30) -> list[str]:
        async def runner():
            app = _Host(
                [Concern("high", region, "BODYMARKER the body text.")], narrow=narrow
            )
            async with app.run_test(size=(width, height)) as pilot:
                await pilot.pause()
                await pilot.pause()
                return _screen_rows(app)

        return self._run(runner())

    def _render_at(self, width: int, region: str, narrow: bool) -> str:
        return "\n".join(self._rows_at(width, region, narrow))

    def _render_at_40(self, region: str, narrow: bool) -> str:
        return self._render_at(40, region, narrow)

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

    def test_title_and_body_survive_at_every_supported_width(self):
        """The t1274 invariant, now pinned below 40 columns too (t1293).

        The region prefix shortens with the width (24 columns leaves room for
        `authoring…`), so the assertion uses the prefix that survives everywhere.
        Under the failure being guarded the region vanishes *entirely*, so a
        shorter prefix loses no discrimination — proven by
        `test_single_line_layout_is_what_lost_them`.
        """
        for width in self.SUPPORTED_WIDTHS:
            with self.subTest(width=width):
                screen = self._render_at(width, self.COMPLIANT_REGION, narrow=True)
                self.assertIn("authoring", screen)  # ellipsized, but present
                self.assertIn("BODYMARKER", screen)

    def test_dialog_is_never_clipped_at_a_supported_width(self):
        """No dialog row may lose its right border to the screen edge.

        This is the `min-width: 30` defect: at 24 columns the pre-t1293 dialog
        was 30 wide on a 24-wide screen, so every row was cut mid-word
        (`HIGH authoring-co`, `[Spac`) with no right border at all.
        """
        for width in self.SUPPORTED_WIDTHS:
            with self.subTest(width=width):
                rows = self._rows_at(width, self.COMPLIANT_REGION, narrow=True)
                self.assertEqual(_clipped_rows(rows, width), [])

    def test_keys_stay_readable_at_every_supported_width(self):
        """`Esc`/confirm and the `u` affordance must be named on screen.

        At the xnarrow tier the OK/Cancel buttons are dropped (they cannot fit
        without either clipping a label or evicting this line), so the help line
        is the ONLY place the confirm/cancel keys are stated — it must survive.
        """
        for width in self.SUPPORTED_WIDTHS:
            with self.subTest(width=width):
                rows = self._rows_at(width, self.COMPLIANT_REGION, narrow=True)
                flat = _flat_text(rows)
                self.assertIn("esc", flat.lower())
                if width <= monitor_shared._PICKER_NARROW_MIN_WIDTH:
                    self.assertIn("u raw", flat)
                    self.assertNotIn("Cancel", flat)
                else:
                    self.assertIn("[u] unparsed", flat)
                    self.assertIn("Cancel", flat)

    def test_short_pane_keeps_the_row_and_the_help(self):
        """24x20 — the narrowest supported width at a short companion height."""
        rows = self._rows_at(24, self.COMPLIANT_REGION, narrow=True, height=20)
        flat = _flat_text(rows)
        self.assertIn("authoring", flat)
        self.assertIn("BODYMARKER", flat)
        self.assertIn("u raw", flat)
        self.assertEqual(_clipped_rows(rows, 24), [])

    def test_without_the_tier_the_narrow_widths_break(self):
        """Negative control for the three tests above (t1293).

        ONE mutation: the tier threshold is patched to 0 so `_apply_width_tier`
        never fires and the pre-t1293 `.narrow` chrome applies at every width.
        The clipping assertion must then fail at 24, and the help line must lose
        its compact form at 30 — if either still passes, the assertions are not
        measuring what they claim to.
        """
        with unittest.mock.patch.object(
            monitor_shared, "_PICKER_NARROW_MIN_WIDTH", 0
        ):
            rows_24 = self._rows_at(24, self.COMPLIANT_REGION, narrow=True)
            self.assertNotEqual(
                _clipped_rows(rows_24, 24), [],
                "expected the un-tiered dialog to overflow a 24-column screen",
            )
            flat_30 = _flat_text(self._rows_at(30, self.COMPLIANT_REGION, True))
            self.assertNotIn("u raw", flat_30)

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


class ConcernPickerWidthTierTests(unittest.TestCase):
    """The chrome tier is MEASURED, not inherited from `narrow` (t1293).

    Two knobs that both mean "small" are easy to conflate: `narrow` is the
    caller's hint and owns only the two-line row layout; `xnarrow` is derived
    from the modal's own width and owns only the dialog chrome. A full-width
    monitor (`narrow=False`) run in a 24-column terminal must still get the
    chrome, and a wide minimonitor (`narrow=True`) must not.
    """

    def _run(self, coro):
        return asyncio.run(coro)

    def _has_tier(self, width: int, narrow: bool) -> bool:
        async def runner():
            app = _Host([Concern("high", "x.py:1", "body")], narrow=narrow)
            async with app.run_test(size=(width, 30)) as pilot:
                await pilot.pause()
                await pilot.pause()
                return app.screen.has_class("xnarrow")

        return self._run(runner())

    def test_tier_follows_width_not_the_narrow_flag(self):
        # narrow=False (the monitor) in a tiny terminal still gets the chrome…
        self.assertTrue(self._has_tier(24, narrow=False))
        # …and narrow=True (minimonitor) in a wide one does not.
        self.assertFalse(self._has_tier(80, narrow=True))

    def test_tier_boundary_is_inclusive(self):
        """Both defects already bite AT the minimum, so it is inside the tier."""
        bound = monitor_shared._PICKER_NARROW_MIN_WIDTH
        self.assertTrue(self._has_tier(bound, narrow=True))
        self.assertFalse(self._has_tier(bound + 1, narrow=True))

    def test_tier_threshold_is_derived_from_the_declared_min_width(self):
        """Drift guard: the threshold IS the `.narrow` dialog's own minimum.

        `tui_conventions.md` rule 4 prefers a derived threshold over a chosen
        constant. The tier exists precisely because a dialog with `min-width: N`
        cannot fit a screen of N columns or fewer, so N is the boundary — not a
        number picked to match today's stylesheet. Retuning the CSS must move the
        tier, and this fails if the two ever disagree.
        """
        declared = re.search(
            r"ConcernPickerModal\.narrow\s+#concern-dialog\s*\{[^}]*?min-width:\s*(\d+)",
            ConcernPickerModal.DEFAULT_CSS,
            re.DOTALL,
        )
        self.assertIsNotNone(declared, "`.narrow` must still declare a min-width")
        self.assertEqual(
            int(declared.group(1)), monitor_shared._PICKER_NARROW_MIN_WIDTH
        )

    def test_threshold_is_a_component_floor_not_a_terminal_tier(self):
        """It must NOT be routed through `lib/tui_layout` (t1293).

        Every width this modal distinguishes (24 / 30 / 40) sits inside the one
        NARROW terminal tier, whose boundary is 80 columns — so
        `is_narrow_terminal` answers True for all of them and cannot express the
        decision. Reusing the tier constant here would apply the stripped chrome
        at 79 columns, where the dialog fits perfectly well. This pins that the
        two concepts stay separate, per `tui_conventions.md` rule 3.
        """
        self.assertTrue(is_narrow_terminal(79))
        self.assertFalse(self._has_tier(79, narrow=True))
        self.assertLess(
            monitor_shared._PICKER_NARROW_MIN_WIDTH, NARROW_TERMINAL_WIDTH
        )

    def test_tier_is_reapplied_on_resize(self):
        """Textual has no media queries — `on_resize` is what keeps it live."""
        async def runner():
            app = _Host([Concern("high", "x.py:1", "body")], narrow=True)
            async with app.run_test(size=(80, 30)) as pilot:
                await pilot.pause()
                self.assertFalse(app.screen.has_class("xnarrow"))
                await pilot.resize_terminal(24, 30)
                await pilot.pause()
                await pilot.pause()
                self.assertTrue(app.screen.has_class("xnarrow"))

        self._run(runner())


class ConcernInspectAffordanceTests(unittest.TestCase):
    """`u` shows WHAT was lost, not just how much (t1293).

    t1274 surfaced a count; without the lines themselves an over-bound split
    marker and a producer typo are indistinguishable, so neither can be reported
    as a real bug against the shadow procedure.
    """

    #: An over-bound split marker (4 rows — past `_MAX_MARKER_JOIN_ROWS`) plus a
    #: priority-less bracket. Both are real, documented unrecoverable shapes.
    LOST_LINES = ("- [ | region] no priority", "- [low | aaaa")
    #: Contains the two shapes Rich would destroy if markup were enabled: the
    #: canonical marker `- [high | x.py:1] …` (consumed as a style tag, leaving
    #: `-  a good one`) and a bare `[/]` (a closing tag with nothing to close,
    #: which raises MarkupError and takes the whole modal down).
    RAW_BLOCK = (
        "- [high | x.py:1] a good one\n"
        "- [ | region] no priority\n"
        "- [medium | fmt] prefer [/] over a bare reset\n"
        "- [low | aaaa\nbbbb\ncccc\ndddd] over-bound split"
    )

    def _run(self, coro):
        return asyncio.run(coro)

    def _picker(self, **kwargs) -> _Host:
        return _Host([Concern("high", "x.py:1", "a good one")], **kwargs)

    def test_u_opens_the_inspect_view_with_lines_and_raw_block(self):
        async def runner():
            app = self._picker(
                unrecovered=self.LOST_LINES, raw_block=self.RAW_BLOCK
            )
            async with app.run_test(size=(60, 24)) as pilot:
                await pilot.pause()
                await pilot.press("u")
                await pilot.pause()
                await pilot.pause()
                self.assertIsInstance(app.screen, ConcernBlockInspectModal)
                screen = _screen_text(app)
                self.assertIn("Unparsed concern lines (2)", screen)
                # The lost lines themselves…
                self.assertIn("no priority", screen)
                # …and the raw region, which is the only thing that shows an
                # over-bound split for what it is: a marker whose continuation
                # rows exceeded the join envelope.
                self.assertIn("dddd] over-bound split", screen)

        self._run(runner())

    def test_inspect_view_does_not_eat_marker_brackets_as_markup(self):
        """A concern marker is literally `- [high | region]`.

        Rendered as Rich markup that bracket is consumed as a style tag — the
        canonical marker collapses to `-  a good one` — and a bare `[/]` in a
        body raises MarkupError and takes the whole modal down. `markup=False`
        is what prevents both, on text that is by definition uncontrolled.
        """
        async def runner():
            app = self._picker(
                unrecovered=self.LOST_LINES, raw_block=self.RAW_BLOCK
            )
            async with app.run_test(size=(72, 24)) as pilot:
                await pilot.pause()
                await pilot.press("u")
                await pilot.pause()
                await pilot.pause()
                screen = _screen_text(app)
                self.assertIn("- [ | region] no priority", screen)
                # Would render as "-  a good one" under markup.
                self.assertIn("- [high | x.py:1] a good one", screen)
                # Would raise MarkupError under markup.
                self.assertIn("prefer [/] over a bare reset", screen)

        self._run(runner())

    def test_u_does_nothing_when_no_line_was_lost(self):
        """Negative control: the guard, and proof the assertions above discriminate.

        A screen that always showed the inspect view would pass every assertion
        in this class; this one fails in exactly that case.
        """
        async def runner():
            app = self._picker()
            async with app.run_test(size=(60, 24)) as pilot:
                await pilot.pause()
                await pilot.press("u")
                await pilot.pause()
                await pilot.pause()
                self.assertIsInstance(app.screen, ConcernPickerModal)

        self._run(runner())

    def test_closing_the_inspect_view_returns_to_an_intact_selection(self):
        """The picker is pushed *under* the inspect view, never dismissed."""
        async def runner():
            app = self._picker(
                unrecovered=self.LOST_LINES, raw_block=self.RAW_BLOCK
            )
            async with app.run_test(size=(60, 24)) as pilot:
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await pilot.press("u")
                await pilot.pause()
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()
                await pilot.pause()
                self.assertIsInstance(app.screen, ConcernPickerModal)
                rows = list(app.screen.query(_ConcernRow))
                self.assertTrue(rows[0].selected)
                # And the picker itself has not dismissed.
                self.assertIs(app.result, _Host._UNSET)

        self._run(runner())

    def test_raw_block_placeholder_when_the_region_is_unavailable(self):
        async def runner():
            app = self._picker(unrecovered=self.LOST_LINES, raw_block="")
            async with app.run_test(size=(60, 24)) as pilot:
                await pilot.pause()
                await pilot.press("u")
                await pilot.pause()
                await pilot.pause()
                self.assertIn("(block region unavailable)", _screen_text(app))

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
