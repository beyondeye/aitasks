"""Tests for the shadow concern-picker modal (t1037_3).

Exercises ConcernPickerModal's pure-UI contract (no clipboard backend):
- N concerns render as N focusable rows, first focused;
- space toggles a row's selection (□ ↔ ✓, from lib/mark_glyphs.py);
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

from mark_glyphs import MARK_CHECKED, MARK_UNCHECKED  # noqa: E402

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Label, TextArea  # noqa: E402

from tui_layout import NARROW_TERMINAL_WIDTH, is_narrow_terminal  # noqa: E402

from monitor.concern_parser import (  # noqa: E402
    BlockMeta, Concern, build_clipboard_payload, has_impact_vector,
)
from monitor import monitor_shared  # noqa: E402
from monitor.monitor_shared import (  # noqa: E402
    ConcernBlockInspectModal, ConcernPayloadEditModal, ConcernPickerModal,
    ConcernPickResult, RejectedEntry, RejectedStoreModal, _ConcernRow,
    _RejectedRow, format_block_meta, trade_profile, trade_profile_rungs,
)
from monitor.concern_dimensions import (  # noqa: E402
    CONCERN_DIMENSIONS, label_for,
)
from rich.cells import cell_len  # noqa: E402


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
        rejected_entries: tuple[RejectedEntry, ...] = (),
        store_unavailable: bool = False,
        block_meta=None,
        stale_detail: str = "",
    ) -> None:
        super().__init__()
        self._concerns = concerns
        self._narrow = narrow
        self._stale = stale
        self._unrecovered = unrecovered
        self._raw_block = raw_block
        self._rejected_entries = rejected_entries
        self._store_unavailable = store_unavailable
        self._block_meta = block_meta
        self._stale_detail = stale_detail
        self.result = self._UNSET
        self.notifications: list[tuple[str, str]] = []

    def compose(self) -> ComposeResult:
        yield Label("host")

    def notify(self, message: str, *args, severity: str = "information", **kwargs):
        self.notifications.append((message, severity))
        return super().notify(message, *args, severity=severity, **kwargs)

    def on_mount(self) -> None:
        def _capture(value) -> None:
            self.result = value

        self.push_screen(
            ConcernPickerModal(
                self._concerns, narrow=self._narrow, stale=self._stale,
                unrecovered=self._unrecovered, raw_block=self._raw_block,
                rejected_entries=self._rejected_entries,
                store_unavailable=self._store_unavailable,
                block_meta=self._block_meta,
                stale_detail=self._stale_detail,
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
                self.assertIn(MARK_UNCHECKED, row.render())

                await pilot.press("space")
                await pilot.pause()
                self.assertTrue(row.selected)
                self.assertIn(MARK_CHECKED, row.render())

                await pilot.press("space")
                await pilot.pause()
                self.assertFalse(row.selected)
                self.assertIn(MARK_UNCHECKED, row.render())

        self._run(runner())

    def test_r_toggles_the_reject_glyph_and_class(self):
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                row = list(app.screen.query(_ConcernRow))[0]
                self.assertEqual(row.state, "none")

                await pilot.press("r")
                await pilot.pause()
                self.assertEqual(row.state, "rejected")
                self.assertIn("✗", row.render())
                self.assertIn("rejected", row.classes)

                await pilot.press("r")
                await pilot.pause()
                self.assertEqual(row.state, "none")
                self.assertIn(MARK_UNCHECKED, row.render())
                self.assertNotIn("rejected", row.classes)

        self._run(runner())

    def test_t_toggles_the_spinoff_glyph(self):
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                row = list(app.screen.query(_ConcernRow))[0]
                self.assertEqual(row.state, "none")

                await pilot.press("t")
                await pilot.pause()
                self.assertEqual(row.state, "spinoff")
                self.assertTrue(row.spun_off)
                self.assertIn("»", row.render())
                # A spin-off KEEPS the concern (elsewhere), so unlike a
                # rejection it must not be dimmed as struck-through.
                self.assertNotIn("rejected", row.classes)

                await pilot.press("t")
                await pilot.pause()
                self.assertEqual(row.state, "none")
                self.assertFalse(row.spun_off)
                self.assertIn(MARK_UNCHECKED, row.render())

        self._run(runner())

    def test_all_four_states_are_mutually_exclusive(self):
        """Every key clears the other two. A row carrying two dispositions
        would forward AND park the same concern."""
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                row = list(app.screen.query(_ConcernRow))[0]

                for key, state, glyph in (
                    ("space", "forward", MARK_CHECKED),
                    ("r", "rejected", "✗"),
                    ("t", "spinoff", "»"),
                    ("space", "forward", MARK_CHECKED),
                    ("t", "spinoff", "»"),
                    ("r", "rejected", "✗"),
                ):
                    await pilot.press(key)
                    await pilot.pause()
                    self.assertEqual(row.state, state)
                    rendered = row.render()
                    self.assertIn(glyph, rendered)
                    for other in (MARK_CHECKED, "✗", "»"):
                        if other != glyph:
                            self.assertNotIn(other, rendered)

        self._run(runner())

    def test_spun_off_concerns_keep_their_input_order(self):
        """Partitioning reorders the DOM, so the result must be restored by
        `original_index` — not by DOM position."""
        async def runner():
            app = _Host(_mixed_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                rows = list(app.screen.query(_ConcernRow))
                # Mark in REVERSE presentation order; the result must still
                # come back in the modal's input order.
                for row in reversed(rows):
                    row.focus()
                    await pilot.pause()
                    await pilot.press("t")
                    await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()

                spun = app.result.spun_off
                self.assertEqual(len(spun), 3)
                self.assertEqual(
                    [c.body for c in spun],
                    [c.body for c in _mixed_concerns()],
                )

        self._run(runner())

    def test_a_spinoff_only_confirm_is_not_a_cancel(self):
        """All-empty-but-one is a legitimate result; only None is a cancel."""
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("t")
                await pilot.press("enter")
                await pilot.pause()
                self.assertIsNotNone(app.result)
                self.assertEqual(len(app.result.spun_off), 1)
                self.assertEqual(app.result.forwarded, [])
                self.assertEqual(app.result.rejected, [])

        self._run(runner())

    def test_forward_and_reject_are_mutually_exclusive(self):
        """Neither key ever leaves a row in both states — the whole point of
        removing the bulk keys was that rejection must not be overwritten."""
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                row = list(app.screen.query(_ConcernRow))[0]

                await pilot.press("space")
                await pilot.pause()
                self.assertEqual(row.state, "forward")

                # reject over a forward: forward must clear, not coexist
                await pilot.press("r")
                await pilot.pause()
                self.assertEqual(row.state, "rejected")
                self.assertFalse(row.selected)
                self.assertIn("✗", row.render())
                self.assertNotIn(MARK_CHECKED, row.render())

                # and back the other way
                await pilot.press("space")
                await pilot.pause()
                self.assertEqual(row.state, "forward")
                self.assertFalse(row.rejected)
                self.assertIn(MARK_CHECKED, row.render())
                self.assertNotIn("✗", row.render())

        self._run(runner())

    def test_every_mark_is_single_width(self):
        """_NARROW_PREFIX_COLS budgets the prefix in COLUMNS, so a double-width
        glyph would silently eat region text at the widths with none to spare.

        Kept covering all four marks even though the two mark_glyphs ones are
        also pinned by tests/test_mark_glyphs_single_source.py: the subject here
        is the _CONCERN_MARKS dict as this modal consumes it, and dropping half
        of it would leave `✗` and `»` as the only glyphs checked against a budget
        that all four spend from.
        """
        import unicodedata
        for state, markup in monitor_shared._CONCERN_MARKS.items():
            glyph = re.sub(r"\[/?[^\]]*\]", "", markup)
            self.assertEqual(len(glyph), 1, f"{state} is not one codepoint")
            self.assertNotIn(
                unicodedata.east_asian_width(glyph), ("W", "F"),
                f"{state} mark {glyph!r} is double-width",
            )

    def test_ok_dismisses_with_a_partitioned_result_in_order(self):
        async def runner():
            concerns = _sample_concerns()
            app = _Host(concerns)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                # Forward row 0, reject row 1, leave row 2 alone.
                await pilot.press("space")   # row 0 forwarded (focused on mount)
                await pilot.press("down")    # focus row 1
                await pilot.press("r")       # row 1 rejected
                await pilot.press("enter")   # confirm
                await pilot.pause()
                self.assertIsInstance(app.result, ConcernPickResult)
                self.assertEqual(app.result.forwarded, [concerns[0]])
                self.assertEqual(app.result.rejected, [concerns[1]])
                self.assertEqual(app.result.unrejected, ())

        self._run(runner())

    def test_confirming_nothing_is_an_empty_result_not_none(self):
        """The cancel signal is `None` ALONE. An all-empty result means the user
        confirmed without marking anything, and consumers branch on `is None`."""
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                self.assertIsNotNone(app.result)
                self.assertEqual(
                    app.result, ConcernPickResult([], [], (), [])
                )

        self._run(runner())

    def test_the_removed_bulk_keys_do_nothing(self):
        """`a`/`A` were removed outright (t1427_2). Pressing them must not
        select anything — a bulk sweep would overwrite a rejection."""
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                rows = list(app.screen.query(_ConcernRow))
                await pilot.press("r")       # reject row 0
                await pilot.press("a")
                await pilot.press("A")
                await pilot.pause()
                self.assertEqual(rows[0].state, "rejected")
                self.assertTrue(all(r.state == "none" for r in rows[1:]))

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

    def test_an_informational_concern_can_be_rejected_like_any_other(self):
        """The bulk keys used to treat informational rows specially (`a` skipped
        them). With per-row actions only, every row is equally actionable — an
        informational concern the user never wants to see again is exactly the
        case rejection exists for."""
        async def runner():
            concerns = _mixed_concerns()
            app = _Host(concerns)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                by_index = {
                    r.original_index: r for r in app.screen.query(_ConcernRow)
                }
                informational = by_index[1]
                self.assertIn("informational", informational.classes)
                informational.focus()
                await pilot.pause()
                await pilot.press("r")
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.result.rejected, [concerns[1]])
                self.assertEqual(app.result.forwarded, [])

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
                by_index[1].set_state("forward")
                by_index[2].set_state("forward")
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.result.forwarded, [concerns[1], concerns[2]])

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
                rows[1].set_state("forward")
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.result.forwarded, [same])

        self._run(runner())

    def test_duplicate_valued_concerns_are_rejected_positionally(self):
        """The same positional-identity rule on the REJECT channel.

        Rejection is persisted, so forwarding the wrong one of a duplicate pair
        is recoverable while rejecting the wrong one suppresses a concern the
        user never dismissed.
        """
        async def runner():
            same = Concern("high", "dup", "identical body.", "blocking", "CONFIRMED")
            concerns = [same, same, Concern("low", "other", "different body.")]
            app = _Host(concerns)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                rows = list(app.screen.query(_ConcernRow))
                rows[1].set_state("rejected")
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.result.rejected, [same])
                self.assertEqual(app.result.forwarded, [])

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

        **Re-expressed at t1636_4, not retired.** This used to obtain the
        one-line form via ``narrow=False``, but the layout is measured now: at 40
        columns a ``narrow=False`` row is 20 cells wide and correctly *chooses*
        multi-line, so the old route would make this test pass while proving
        nothing. The mutation is therefore applied directly — one patch, forcing
        ``_use_multiline`` off — the same single-mutation shape
        ``test_without_the_tier_the_narrow_widths_break`` uses on
        ``_PICKER_NARROW_MIN_WIDTH``. What it guards is unchanged: the multi-line
        layout is what rescues the region and the body.
        """
        with unittest.mock.patch.object(
            _ConcernRow, "_use_multiline", lambda self, *a, **k: False
        ):
            screen = self._render_at_40(self.COMPLIANT_REGION, narrow=True)
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


class ConcernContextLineBudgetTests(unittest.TestCase):
    """The context line's actionable counts survive the xnarrow tier (t1159_1).

    Characterization first: the two-partition line already runs ~48 characters
    (`"2 to address  ·  1 informational  ·  forward or reject"`), and the round
    suffix adds ~20 more at a tier as narrow as ``_PICKER_NARROW_MIN_WIDTH``.
    These pin the *composited strips* — the line wraps inside the dialog, so a
    `render()` string that contains the counts proves nothing about the screen
    (same rationale as :class:`ConcernPickerNarrowLayoutTests`).
    """

    def _run(self, coro):
        return asyncio.run(coro)

    def _flat_at(self, width: int, height: int = 30, **host_kwargs) -> str:
        async def runner():
            app = _Host(_mixed_concerns(), narrow=True, **host_kwargs)
            async with app.run_test(size=(width, height)) as pilot:
                await pilot.pause()
                await pilot.pause()
                return _flat_text(_screen_rows(app))

        return self._run(runner())

    #: A realistic header's meta — the widest suffix shape (round + clock).
    META = BlockMeta(2, "2026-08-11T14:03:27Z")

    def test_counts_visible_at_the_xnarrow_tier(self):
        """Pre-change characterization: both counts reach the screen at the
        tier boundary, wrapped or not."""
        flat = self._flat_at(monitor_shared._PICKER_NARROW_MIN_WIDTH)
        self.assertIn("2 to address", flat)
        self.assertIn("1 informational", flat)

    def test_counts_visible_at_the_supported_floor(self):
        flat = self._flat_at(monitor_shared._PICKER_MIN_COLS)
        self.assertIn("2 to address", flat)
        self.assertIn("1 informational", flat)

    def test_counts_still_visible_with_the_round_suffix(self):
        """The round suffix must not push the actionable counts off screen at
        either narrow width (the t1159_1 pre-phase acceptance)."""
        for width in (monitor_shared._PICKER_NARROW_MIN_WIDTH,
                      monitor_shared._PICKER_MIN_COLS):
            with self.subTest(width=width):
                flat = self._flat_at(width, block_meta=self.META)
                self.assertIn("2 to address", flat)
                self.assertIn("1 informational", flat)

    def test_round_suffix_reaches_the_screen_when_it_fits(self):
        """At a comfortable width the round is visible, not merely returned."""
        flat = self._flat_at(80, block_meta=self.META)
        self.assertIn("round 2", flat)
        self.assertIn("14:03:27Z", flat)


class ConcernHelpLineBudgetTests(unittest.TestCase):
    """The help line survives the xnarrow tier with a fourth key (t1159_3).

    Pre-phase characterization for the spin-off arm. ``_CONCERN_HELP_COMPACT``
    exists *because* the full line wraps to five rows at this tier and evicts
    the OK/Cancel buttons — its own comment records that — so it is already
    tuned to roughly 50 columns and a fourth key spends budget documented as
    scarce.

    These assert the **composited strips**, not the constant: the line wraps
    inside the dialog, so a constant containing the token proves nothing about
    what reached the screen (the :class:`ConcernContextLineBudgetTests`
    rationale, and `_flat_text` exists for exactly this wrapping).

    What is pinned is *every* key reaching the screen and the concern rows
    surviving alongside it — the two things a fourth key could push off.
    """

    def _flat_at(self, width: int, height: int = 30) -> str:
        async def runner():
            app = _Host(_mixed_concerns(), narrow=True)
            async with app.run_test(size=(width, height)) as pilot:
                await pilot.pause()
                await pilot.pause()
                return _flat_text(_screen_rows(app))

        return asyncio.run(runner())

    #: Every key the compact help names, as it appears once whitespace is
    #: collapsed. Each must reach the screen at the narrowest supported width.
    #: `spin` is the t1159_3 addition — the acceptance half of that pre-phase:
    #: the fourth key must reach the screen without evicting the other seven.
    #: `edit` is the t1582 addition, the ninth key, and the acceptance half of
    #: ITS pre-phase: adding it to this tuple is what turns "the line still
    #: renders" into "the new key actually reached the screen".
    COMPACT_TOKENS = (
        "move", "fwd", "rej", "spin", "edit", "list", "raw", "ok", "esc",
    )

    def test_every_compact_help_key_reaches_the_screen(self):
        for width in (monitor_shared._PICKER_NARROW_MIN_WIDTH,
                      monitor_shared._PICKER_MIN_COLS):
            flat = self._flat_at(width)
            for token in self.COMPACT_TOKENS:
                with self.subTest(width=width, token=token):
                    self.assertIn(token, flat)

    def test_concern_rows_survive_beside_the_help_line(self):
        """The help line must not evict the rows it describes.

        A body marker per concern, so this fails if the help grew enough to
        push the list off a 24-row screen rather than merely wrapping.
        """
        for width in (monitor_shared._PICKER_NARROW_MIN_WIDTH,
                      monitor_shared._PICKER_MIN_COLS):
            flat = self._flat_at(width)
            for marker in ("AAA", "BBB", "CCC"):
                with self.subTest(width=width, marker=marker):
                    self.assertIn(marker, flat)

    def test_full_help_names_every_key_at_a_comfortable_width(self):
        flat = self._flat_at(100)
        for token in ("navigate", "forward", "reject", "spin off",
                      "edit payload", "rejected list", "unparsed", "confirm",
                      "cancel"):
            with self.subTest(token=token):
                self.assertIn(token, flat)


class FormatBlockMetaTests(unittest.TestCase):
    """`format_block_meta` is pure, plain-text, and total over garbage."""

    def test_none_is_empty(self):
        self.assertEqual(format_block_meta(None), "")

    def test_iso_timestamp_is_shortened_to_the_clock(self):
        self.assertEqual(
            format_block_meta(BlockMeta(2, "2026-08-11T14:03:27Z")),
            "  ·  round 2, 14:03:27Z",
        )

    def test_empty_reviewed_at_shows_the_round_alone(self):
        self.assertEqual(format_block_meta(BlockMeta(2, "")), "  ·  round 2")

    def test_garbage_reviewed_at_never_raises(self):
        for garbage in ("[/]", "[bold red]x", "]", "no-iso-shape-here" * 20):
            with self.subTest(garbage=garbage):
                suffix = format_block_meta(BlockMeta(2, garbage))
                self.assertTrue(suffix.startswith("  ·  round 2"))


class ConcernContextMetaTests(unittest.TestCase):
    """The context line carries the round on BOTH partition shapes, and
    markup-shaped garbage in `reviewed_at` renders instead of crashing.

    The crash being guarded fires at RENDER time (`MarkupError` on an
    unescaped `[/]` in a markup-enabled Static), so these drive the composited
    render — a `_context_line()` return-value assertion would pass while the
    modal went down.
    """

    def _run(self, coro):
        return asyncio.run(coro)

    def _flat(self, concerns: list[Concern], block_meta) -> str:
        async def runner():
            app = _Host(concerns, block_meta=block_meta)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.pause()
                return _flat_text(_screen_rows(app))

        return self._run(runner())

    def test_single_partition_line_carries_the_round(self):
        flat = self._flat(
            _sample_concerns(), BlockMeta(2, "2026-08-11T14:03:27Z")
        )
        self.assertIn("3 concern(s)", flat)
        self.assertIn("round 2, 14:03:27Z", flat)

    def test_two_partition_line_carries_the_round(self):
        flat = self._flat(
            _mixed_concerns(), BlockMeta(2, "2026-08-11T14:03:27Z")
        )
        self.assertIn("2 to address", flat)
        self.assertIn("round 2, 14:03:27Z", flat)

    def test_no_meta_renders_exactly_the_pre_round_line(self):
        flat = self._flat(_mixed_concerns(), None)
        # The wording is fixture (t1159_3 added ", or spin off"); the GUARD is
        # the assertNotIn below, and this line is what keeps it non-vacuous by
        # proving the context line reached the screen at all.
        self.assertIn("1 informational · forward, reject, or spin off", flat)
        self.assertNotIn("round", flat)

    def test_markup_shaped_reviewed_at_renders_instead_of_crashing(self):
        """`reviewed_at` is verbatim untrusted producer text on a markup
        surface — an unescaped `[/]` raises MarkupError and takes the modal
        down. The escape must let it render as literal text."""
        for garbage in ("[/]", "[bold red]x", "]"):
            with self.subTest(garbage=garbage):
                flat = self._flat(
                    _mixed_concerns(), BlockMeta(2, garbage)
                )
                # The modal composed and its context line reached the screen.
                self.assertIn("2 to address", flat)
                self.assertIn("round 2", flat)


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


def _sample_entries() -> tuple[RejectedEntry, ...]:
    return (
        RejectedEntry(
            "r1", "2026-08-05T14:02:11Z", "plan-challenge",
            "- [high | Step 7 guard] The guard double-commits the lock.",
        ),
        RejectedEntry(
            "r3", "2026-08-05T14:09:40Z", "impl-challenge",
            "- [medium | parser] Multi-block accumulation is undefined.",
        ),
    )


class RejectedStoreViewTests(unittest.TestCase):
    """`R` — the persisted rejection list and its un-reject toggle (t1427_2)."""

    def _run(self, coro):
        asyncio.run(coro)

    def test_R_opens_the_view_over_an_intact_picker(self):
        async def runner():
            app = _Host(_sample_concerns(), rejected_entries=_sample_entries())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("space")     # forward row 0 first
                await pilot.press("R")
                await pilot.pause()
                await pilot.pause()
                self.assertIsInstance(app.screen, RejectedStoreModal)
                self.assertIn("Rejected concerns (2)", _screen_text(app))
                # Both stored markers are visible, brackets and all.
                self.assertIn("Step 7 guard", _screen_text(app))

                await pilot.press("escape")
                await pilot.pause()
                await pilot.pause()
                # Picker still open, and the earlier selection survived.
                self.assertIsInstance(app.screen, ConcernPickerModal)
                self.assertTrue(list(app.screen.query(_ConcernRow))[0].selected)
                self.assertIs(app.result, _Host._UNSET)

        self._run(runner())

    def test_marker_brackets_are_not_eaten_as_markup(self):
        """A marker literally reads `- [high | region]`; interpreted as Rich
        markup the bracket disappears and the view corrupts what it exists to
        show — the same rule ConcernBlockInspectModal states."""
        async def runner():
            app = _Host(_sample_concerns(), rejected_entries=_sample_entries())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("R")
                await pilot.pause()
                await pilot.pause()
                text = _screen_text(app)
                self.assertIn("[high | Step 7 guard]", text)
                self.assertIn("[medium | parser]", text)

        self._run(runner())

    def test_un_rejected_ids_travel_back_in_the_result(self):
        async def runner():
            app = _Host(_sample_concerns(), rejected_entries=_sample_entries())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("R")
                await pilot.pause()
                await pilot.pause()
                # Mark the SECOND entry only — proves the id comes from the row
                # rather than from position-in-store or a blanket "all".
                rows = list(app.screen.query(_RejectedRow))
                rows[1].toggle()
                await pilot.press("enter")     # apply un-rejection
                await pilot.pause()
                await pilot.pause()
                await pilot.press("enter")     # confirm the picker
                await pilot.pause()
                self.assertEqual(app.result.unrejected, ("r3",))
                self.assertEqual(app.result.forwarded, [])
                self.assertEqual(app.result.rejected, [])

        self._run(runner())

    def test_escaping_the_view_un_rejects_nothing(self):
        async def runner():
            app = _Host(_sample_concerns(), rejected_entries=_sample_entries())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("R")
                await pilot.pause()
                await pilot.pause()
                list(app.screen.query(_RejectedRow))[0].toggle()
                await pilot.press("escape")    # cancel, not apply
                await pilot.pause()
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.result.unrejected, ())

        self._run(runner())

    def test_two_visits_accumulate_rather_than_replace(self):
        """The view can be opened more than once before confirming; a second
        visit must not discard the first visit's choices."""
        async def runner():
            app = _Host(_sample_concerns(), rejected_entries=_sample_entries())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                for index in (0, 1):
                    await pilot.press("R")
                    await pilot.pause()
                    await pilot.pause()
                    list(app.screen.query(_RejectedRow))[index].toggle()
                    await pilot.press("enter")
                    await pilot.pause()
                    await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.result.unrejected, ("r1", "r3"))

        self._run(runner())

    def test_no_task_id_says_so_instead_of_opening_an_empty_view(self):
        """"Store unavailable" and "store empty" are different facts and the
        user needs the first one BEFORE confirming a rejection that will be
        refused."""
        async def runner():
            app = _Host(_sample_concerns(), store_unavailable=True)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("R")
                await pilot.pause()
                await pilot.pause()
                self.assertIsInstance(app.screen, ConcernPickerModal)
                message, severity = app.notifications[-1]
                self.assertIn("no task id", message.lower())
                self.assertEqual(severity, "warning")

        self._run(runner())

    def test_empty_store_says_empty_not_unavailable(self):
        async def runner():
            app = _Host(_sample_concerns(), rejected_entries=())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("R")
                await pilot.pause()
                await pilot.pause()
                self.assertIsInstance(app.screen, ConcernPickerModal)
                message, severity = app.notifications[-1]
                self.assertIn("no previously rejected", message.lower())
                self.assertNotIn("task id", message.lower())
                self.assertEqual(severity, "information")

        self._run(runner())


class ConcernStaleTriStateTests(unittest.TestCase):
    """`stale` is tri-state since t1493: True / False / **None**.

    `None` means the freshness could not be established (a pre-round-header
    block, an unreadable stamp). Rendering nothing for it would present
    unverified concerns as current — the exact false confidence this task
    removes — so it gets its own banner.

    Driven through the composited render rather than `render().plain`: the
    detail carries verbatim producer text onto a markup-enabled Static, and a
    MarkupError there fires at render time and takes the modal down.
    """

    def _run(self, coro):
        return asyncio.run(coro)

    def _banners(self, **host_kwargs):
        async def runner():
            app = _Host(_sample_concerns(), **host_kwargs)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.pause()
                return (
                    [w.render().plain for w in app.screen.query("#concern-stale")],
                    [w.render().plain
                     for w in app.screen.query("#concern-stale-unknown")],
                    _flat_text(_screen_rows(app)),
                )

        return self._run(runner())

    def test_true_renders_only_the_stale_banner(self):
        stale, unknown, _ = self._banners(stale=True)
        self.assertEqual(len(stale), 1)
        self.assertEqual(len(unknown), 0)
        self.assertIn("stale", stale[0].lower())

    def test_none_renders_only_the_unknown_banner(self):
        stale, unknown, flat = self._banners(stale=None)
        self.assertEqual(len(stale), 0)
        self.assertEqual(len(unknown), 1)
        self.assertIn("unknown", unknown[0].lower())
        # And it is actually on screen, not merely mounted.
        self.assertIn("Freshness unknown", flat)

    def test_false_renders_neither(self):
        stale, unknown, _ = self._banners(stale=False)
        self.assertEqual(stale, [])
        self.assertEqual(unknown, [])

    def test_default_is_still_not_stale(self):
        stale, unknown, _ = self._banners()
        self.assertEqual(stale, [])
        self.assertEqual(unknown, [])

    def test_exactly_one_banner_per_state(self):
        """No state may mount both — they say contradictory things."""
        for value in (True, False, None):
            with self.subTest(stale=value):
                stale, unknown, _ = self._banners(stale=value)
                self.assertLessEqual(len(stale) + len(unknown), 1)

    def test_detail_is_appended_to_the_stale_banner(self):
        _, _, flat = self._banners(
            stale=True,
            stale_detail=" — round 2 was produced 5m00s before the agent's "
                         "latest change",
        )
        self.assertIn("round 2 was produced 5m00s", flat)

    def test_markup_shaped_detail_renders_instead_of_crashing(self):
        """The detail is built from `reviewed_at`-derived text, which is
        verbatim producer output — an unescaped `[/]` would raise MarkupError
        at render and take the modal down."""
        for garbage in (" — [/]", " — [bold red]x", " — ]"):
            with self.subTest(garbage=garbage):
                stale, _, flat = self._banners(stale=True, stale_detail=garbage)
                self.assertEqual(len(stale), 1)
                self.assertIn("stale", flat.lower())

    def test_unknown_banner_does_not_evict_the_counts_at_narrow_widths(self):
        """Budget the surface: visible is not readable (t1493 post-phase)."""
        detail = " — round 12 was produced 1h04m before the agent's latest change"
        for width in (monitor_shared._PICKER_NARROW_MIN_WIDTH,
                      monitor_shared._PICKER_MIN_COLS):
            for value in (True, None):
                with self.subTest(width=width, stale=value):
                    async def runner():
                        app = _Host(_mixed_concerns(), narrow=True,
                                    stale=value, stale_detail=detail)
                        async with app.run_test(size=(width, 30)) as pilot:
                            await pilot.pause()
                            await pilot.pause()
                            return _flat_text(_screen_rows(app))

                    flat = self._run(runner())
                    self.assertIn("2 to address", flat)
                    self.assertIn("1 informational", flat)


# ---------------------------------------------------------------------------
# t1582 — edit the outgoing payload before it reaches the clipboard
# ---------------------------------------------------------------------------


async def _open_editor(pilot, app):
    """Press `e` and settle; returns the editor screen (or the picker on refusal)."""
    await pilot.press("e")
    await pilot.pause()
    await pilot.pause()
    return app.screen


def _editor_text(app) -> str:
    return app.screen.query_one("#payload-edit-text", TextArea).text


class ConcernPayloadEditAffordanceTests(unittest.TestCase):
    """`e` opens the payload editor OVER the picker, seeded with the real payload.

    The modal-over-modal contract mirrors ``u`` / ``R`` (t1293, t1427_2): the
    picker is never dismissed, so cancelling lands on an intact selection.
    """

    def _run(self, coro):
        return asyncio.run(coro)

    def test_e_with_nothing_forwarded_is_refused_with_a_notify(self):
        """The empty case says which one it hit, exactly as `u` and `R` do.

        Opening an empty box with no explanation is the failure being avoided.
        """
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                screen = await _open_editor(pilot, app)
                self.assertIsInstance(screen, ConcernPickerModal)
                self.assertIn(
                    ("Nothing marked for forwarding — press Space on a row first",
                     "information"),
                    app.notifications,
                )

        self._run(runner())

    def test_editor_is_seeded_byte_for_byte_with_the_clipboard_payload(self):
        """WYSIWYG: what is in the box is what would land on the clipboard.

        Asserted against ``build_clipboard_payload`` itself rather than a
        hand-written literal, so a change to the preamble or the marker grammar
        cannot make this pass while the box shows something else.
        """
        async def runner():
            concerns = _sample_concerns()
            app = _Host(concerns)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("space")          # forward row 0
                await pilot.press("down")
                await pilot.press("space")          # forward row 1
                await pilot.pause()
                screen = await _open_editor(pilot, app)
                self.assertIsInstance(screen, ConcernPayloadEditModal)
                self.assertEqual(
                    _editor_text(app),
                    build_clipboard_payload([concerns[0], concerns[1]]),
                )
                # And the picker is still underneath, undismissed.
                self.assertIs(app.result, _Host._UNSET)

        self._run(runner())

    def test_escape_returns_to_an_intact_selection(self):
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("space")
                await pilot.press("down")           # focus row 1
                await pilot.pause()
                await _open_editor(pilot, app)
                await pilot.press("escape")
                await pilot.pause()
                await pilot.pause()
                picker = app.screen
                self.assertIsInstance(picker, ConcernPickerModal)
                rows = list(picker.query(_ConcernRow))
                self.assertTrue(rows[0].selected)
                self.assertFalse(rows[1].selected)
                self.assertIs(picker.focused, rows[1])
                self.assertIsNone(picker._payload_override)
                self.assertIs(app.result, _Host._UNSET)

        self._run(runner())

    def test_cancelling_does_not_clear_a_previously_saved_edit(self):
        """A cancel abandons THIS visit, not the last saved one."""
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await _open_editor(pilot, app)
                app.screen.query_one("#payload-edit-text", TextArea).load_text("KEPT")
                await pilot.press("ctrl+s")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app.screen._payload_override, "KEPT")
                # Reopen and cancel out.
                await _open_editor(pilot, app)
                await pilot.press("escape")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app.screen._payload_override, "KEPT")

        self._run(runner())

    def test_saving_an_empty_buffer_is_refused_not_dismissed(self):
        """An emptied box must never fall back to the generated payload.

        Refusing keeps the editor open and says why; Esc is still the way out.
        """
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await _open_editor(pilot, app)
                app.screen.query_one("#payload-edit-text", TextArea).load_text("   \n\n")
                await pilot.press("ctrl+s")
                await pilot.pause()
                await pilot.pause()
                self.assertIsInstance(app.screen, ConcernPayloadEditModal)
                self.assertIn(
                    "Editor is empty",
                    " ".join(m for m, _ in app.notifications),
                )
                self.assertEqual(
                    [s for m, s in app.notifications if "Editor is empty" in m],
                    ["warning"],
                )

        self._run(runner())


class ConcernPayloadEditButtonTests(unittest.TestCase):
    """The Save / Cancel buttons do what the keys do.

    They render at every width above the xnarrow tier, so a keyboard-only
    implementation would leave a mouse user clicking a dead control. Each case
    asserts against the SAME expectation as its keyboard twin, so the two paths
    cannot drift.
    """

    def _run(self, coro):
        return asyncio.run(coro)

    async def _editor(self, pilot, app):
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        return await _open_editor(pilot, app)

    def test_clicking_save_commits_the_edit_like_ctrl_s(self):
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await self._editor(pilot, app)
                app.screen.query_one("#payload-edit-text", TextArea).load_text("BY MOUSE")
                await pilot.click("#btn-payload-save")
                await pilot.pause()
                await pilot.pause()
                self.assertIsInstance(app.screen, ConcernPickerModal)
                self.assertEqual(app.screen._payload_override, "BY MOUSE")

        self._run(runner())

    def test_clicking_cancel_abandons_the_visit_like_escape(self):
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await self._editor(pilot, app)
                app.screen.query_one("#payload-edit-text", TextArea).load_text("DISCARD")
                await pilot.click("#btn-payload-cancel")
                await pilot.pause()
                await pilot.pause()
                self.assertIsInstance(app.screen, ConcernPickerModal)
                self.assertIsNone(app.screen._payload_override)

        self._run(runner())

    def test_clicking_save_on_an_empty_buffer_inherits_the_refusal(self):
        """The test that fails if ``on_button_pressed`` grows its own body.

        The empty-buffer rule lives in ``action_save``; the click path is only
        correct because it delegates there rather than re-implementing a save.
        """
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await self._editor(pilot, app)
                app.screen.query_one("#payload-edit-text", TextArea).load_text("")
                await pilot.click("#btn-payload-save")
                await pilot.pause()
                await pilot.pause()
                self.assertIsInstance(app.screen, ConcernPayloadEditModal)
                self.assertIn(
                    "Editor is empty",
                    " ".join(m for m, _ in app.notifications),
                )

        self._run(runner())

    def test_buttons_are_absent_at_the_extra_narrow_tier(self):
        """Not merely hidden from the eye — gone from the composited screen.

        So the click path above is not silently expected to work at 24 columns,
        where ctrl+s / Esc (named by the compact help) are the whole interface.
        """
        async def runner():
            app = _Host(_sample_concerns(), narrow=True)
            async with app.run_test(
                size=(monitor_shared._PICKER_MIN_COLS, 20)
            ) as pilot:
                await self._editor(pilot, app)
                flat = _flat_text(_screen_rows(app))
                self.assertNotIn("Save", flat)
                self.assertNotIn("Cancel", flat)

        self._run(runner())


class ConcernPayloadReopenTests(unittest.TestCase):
    """Pressing `e` a second time resumes the user's text, not a fresh build.

    The editor is a place to iterate. Reseeding from the canonical payload would
    throw the previous edit away exactly when the user came back to revise it.
    """

    def _run(self, coro):
        return asyncio.run(coro)

    async def _save(self, pilot, app, text):
        await _open_editor(pilot, app)
        app.screen.query_one("#payload-edit-text", TextArea).load_text(text)
        await pilot.press("ctrl+s")
        await pilot.pause()
        await pilot.pause()

    def test_reopening_shows_the_saved_edit_not_the_regenerated_payload(self):
        async def runner():
            concerns = _sample_concerns()
            app = _Host(concerns)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await self._save(pilot, app, "MY OWN WORDS")
                await _open_editor(pilot, app)
                shown = _editor_text(app)
                # Named both ways round so a failure says WHICH one it showed.
                self.assertEqual(shown, "MY OWN WORDS")
                self.assertNotEqual(shown, build_clipboard_payload([concerns[0]]))

        self._run(runner())

    def test_a_second_edit_is_what_confirm_carries(self):
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await self._save(pilot, app, "FIRST")
                await self._save(pilot, app, "SECOND")
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.result.payload_override, "SECOND")

        self._run(runner())

    def test_the_seed_stays_canonical_after_a_save(self):
        """The direct pin that one field is not doing two jobs.

        If ``_payload_seed`` were overwritten with the edited text, every later
        comparison would trivially match and staleness would be undetectable.
        """
        async def runner():
            concerns = _sample_concerns()
            app = _Host(concerns)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await self._save(pilot, app, "REWRITTEN ENTIRELY")
                self.assertEqual(
                    app.screen._payload_seed,
                    build_clipboard_payload([concerns[0]]),
                )

        self._run(runner())

    def test_reopening_after_a_selection_change_drops_the_stale_edit_once(self):
        """The stale rule applies at BOTH entry points, and warns exactly once.

        A second warning at confirm would mean the two call sites disagreed
        about which text was live.
        """
        async def runner():
            concerns = _sample_concerns()
            app = _Host(concerns)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await self._save(pilot, app, "STALE SOON")
                await pilot.press("down")
                await pilot.press("space")        # forward a second row
                await pilot.pause()
                await _open_editor(pilot, app)
                self.assertEqual(
                    _editor_text(app),
                    build_clipboard_payload([concerns[0], concerns[1]]),
                )
                warnings = [m for m, s in app.notifications if s == "warning"]
                self.assertEqual(len(warnings), 1, warnings)
                self.assertIn("Selection changed since your last edit", warnings[0])
                # Confirming now must NOT warn a second time.
                await pilot.press("escape")       # leave the editor
                await pilot.pause()
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(
                    len([m for m, s in app.notifications if s == "warning"]), 1
                )

        self._run(runner())


class ConcernPayloadStaleOverrideTests(unittest.TestCase):
    """The settled stale rule, pinned in BOTH directions.

    Dropping either half — never discarding, or always discarding — fails here.
    """

    def _run(self, coro):
        return asyncio.run(coro)

    async def _edit(self, pilot, app, text="EDITED"):
        await _open_editor(pilot, app)
        app.screen.query_one("#payload-edit-text", TextArea).load_text(text)
        await pilot.press("ctrl+s")
        await pilot.pause()
        await pilot.pause()

    def test_an_untouched_selection_carries_the_edit_through(self):
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await self._edit(pilot, app)
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.result.payload_override, "EDITED")
                self.assertEqual(
                    [m for m, s in app.notifications if s == "warning"], []
                )

        self._run(runner())

    def test_changing_a_row_after_editing_discards_the_edit_with_a_warning(self):
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await self._edit(pilot, app)
                await pilot.press("down")
                await pilot.press("space")
                await pilot.press("enter")
                await pilot.pause()
                self.assertIsNone(app.result.payload_override)
                warnings = [m for m, s in app.notifications if s == "warning"]
                self.assertEqual(len(warnings), 1, warnings)
                self.assertIn("your edit was discarded", warnings[0])

        self._run(runner())

    def test_toggling_a_row_off_and_back_on_keeps_the_edit(self):
        """A payload comparison, not a "touched" flag — the net change is nil."""
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await self._edit(pilot, app)
                await pilot.press("down")
                await pilot.press("space")        # forward row 1
                await pilot.press("space")        # …and un-forward it
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.result.payload_override, "EDITED")

        self._run(runner())

    def test_un_rejecting_an_entry_does_not_invalidate_the_edit(self):
        """Un-rejection is a different channel — it never changes `forwarded`."""
        async def runner():
            entries = (RejectedEntry("r1", "2026-01-01T00:00:00Z", "picker",
                                     "- [high | old] a previously rejected one"),)
            app = _Host(_sample_concerns(), rejected_entries=entries)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await self._edit(pilot, app)
                await pilot.press("R")            # rejected-store view
                await pilot.pause()
                await pilot.pause()
                await pilot.press("space")        # mark r1 for un-rejection
                await pilot.press("enter")        # back to the picker
                await pilot.pause()
                await pilot.pause()
                await pilot.press("enter")        # confirm the picker
                await pilot.pause()
                self.assertEqual(app.result.unrejected, ("r1",))
                self.assertEqual(app.result.payload_override, "EDITED")

        self._run(runner())


class ConcernPayloadEditWidthTierTests(unittest.TestCase):
    """The editor renders intact and stays usable at every supported width.

    Same shape as :class:`ConcernPickerWidthTierTests`: widths read from the
    production constants, the composited strips as the assertion surface, and a
    one-mutation negative control proving the tier is what buys it.
    """

    def _run(self, coro):
        return asyncio.run(coro)

    SUPPORTED_WIDTHS = (
        80,
        40,
        monitor_shared._PAYLOAD_EDIT_NARROW_MIN_WIDTH,
        monitor_shared._PICKER_MIN_COLS,
    )

    def _rows_at(self, width: int, height: int = 30, narrow: bool = True):
        async def runner():
            app = _Host([Concern("high", "x.py:1", "BODYMARKER the body.")],
                        narrow=narrow)
            async with app.run_test(size=(width, height)) as pilot:
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await _open_editor(pilot, app)
                return _screen_rows(app)

        return self._run(runner())

    def test_dialog_is_never_clipped_at_a_supported_width(self):
        for width in self.SUPPORTED_WIDTHS:
            with self.subTest(width=width):
                rows = self._rows_at(width)
                self.assertEqual(_clipped_rows(rows, width), [])

    def test_the_help_names_save_and_cancel_at_every_width(self):
        """The keys that commit or abandon the edit are named at every tier.

        At the xnarrow tier the buttons are gone, so this line is the only place
        they appear at all.
        """
        for width in self.SUPPORTED_WIDTHS:
            with self.subTest(width=width):
                flat = _flat_text(self._rows_at(width)).lower()
                self.assertTrue(
                    "ctrl+s" in flat or "^s" in flat, f"no save key at {width}"
                )
                self.assertIn("esc", flat)

    def test_editor_is_usable_in_a_real_companion_pane(self):
        """24x20 — the actual minimonitor geometry, not a roomier 24x30.

        Height is what the help-line budget is about, and ten spare rows are
        exactly the slack that would hide a regression here. "Renders" is not
        the claim: the box must have a real height, hold focus, and accept a
        keystroke.
        """
        width, height = monitor_shared._PICKER_MIN_COLS, 20

        async def runner():
            app = _Host([Concern("high", "x.py:1", "BODYMARKER the body.")],
                        narrow=True)
            async with app.run_test(size=(width, height)) as pilot:
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await _open_editor(pilot, app)
                rows = _screen_rows(app)
                self.assertEqual(_clipped_rows(rows, width), [])
                flat = _flat_text(rows).lower()
                self.assertIn("^s", flat)
                self.assertIn("esc", flat)
                area = app.screen.query_one("#payload-edit-text", TextArea)
                self.assertGreater(area.size.height, 0)
                self.assertIs(app.screen.focused, area)
                before = area.text
                await pilot.press("x")
                await pilot.pause()
                self.assertNotEqual(area.text, before)

        self._run(runner())

    def test_tier_threshold_is_derived_from_the_declared_min_width(self):
        """The constant mirrors the stylesheet; retuning one moves the other."""
        match = re.search(
            r"ConcernPayloadEditModal\.narrow #payload-edit-dialog\s*\{[^}]*"
            r"min-width:\s*(\d+)",
            ConcernPayloadEditModal.DEFAULT_CSS,
        )
        self.assertIsNotNone(match, "no .narrow min-width in DEFAULT_CSS")
        self.assertEqual(
            int(match.group(1)), monitor_shared._PAYLOAD_EDIT_NARROW_MIN_WIDTH
        )

    def test_narrow_class_is_applied_and_is_not_the_measured_tier(self):
        """`narrow` (caller's hint) and `xnarrow` (measured) are separate knobs.

        Also the guard against dormant CSS: a `.narrow` rule that nothing ever
        activates is invisible to a reading of the stylesheet alone.
        """
        async def runner():
            for narrow in (True, False):
                app = _Host([Concern("high", "x.py:1", "body")], narrow=narrow)
                async with app.run_test(size=(40, 30)) as pilot:
                    await pilot.pause()
                    await pilot.press("space")
                    await pilot.pause()
                    await _open_editor(pilot, app)
                    with self.subTest(narrow=narrow):
                        self.assertEqual(app.screen.has_class("narrow"), narrow)
                        self.assertFalse(app.screen.has_class("xnarrow"))

        self._run(runner())

    def test_the_narrow_class_actually_widens_the_dialog(self):
        """Pinned on GEOMETRY, not on a class name.

        `has_class("narrow")` would still pass if the CSS selector were wrong or
        the rule were deleted; a measured width would not.
        """
        async def runner():
            widths = {}
            for narrow in (True, False):
                app = _Host([Concern("high", "x.py:1", "body")], narrow=narrow)
                async with app.run_test(size=(40, 30)) as pilot:
                    await pilot.pause()
                    await pilot.press("space")
                    await pilot.pause()
                    await _open_editor(pilot, app)
                    widths[narrow] = app.screen.query_one(
                        "#payload-edit-dialog"
                    ).size.width
            return widths

        widths = self._run(runner())
        self.assertGreater(widths[True], widths[False], widths)

    def test_without_the_tier_the_narrow_widths_break(self):
        """ONE mutation: the tier threshold is patched to 0.

        The negative control proving the clipping assertion above is not
        vacuous — without the tier, `min-width: 30` overflows a 24-column
        screen and takes the right border with it.
        """
        with unittest.mock.patch.object(
            monitor_shared, "_PAYLOAD_EDIT_NARROW_MIN_WIDTH", 0
        ):
            rows = self._rows_at(monitor_shared._PICKER_MIN_COLS)
            self.assertNotEqual(
                _clipped_rows(rows, monitor_shared._PICKER_MIN_COLS), [],
                "expected the un-tiered editor to overflow a 24-column screen",
            )

    def test_tier_is_reapplied_on_resize(self):
        """Textual has no media queries — `on_resize` is what keeps it live."""
        async def runner():
            app = _Host([Concern("high", "x.py:1", "body")], narrow=True)
            async with app.run_test(size=(80, 30)) as pilot:
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await _open_editor(pilot, app)
                self.assertFalse(app.screen.has_class("xnarrow"))
                await pilot.resize_terminal(24, 30)
                await pilot.pause()
                await pilot.pause()
                self.assertTrue(app.screen.has_class("xnarrow"))

        self._run(runner())


class ConcernPayloadEditEditingTests(unittest.TestCase):
    """Editing behaviour through the REAL widget, not a stand-in.

    The whole design rests on `TextArea` already providing selection, overwrite
    and arrow navigation; these assert that against the pinned Textual, so a
    version bump that changed it fails here rather than in the field.
    """

    def _run(self, coro):
        return asyncio.run(coro)

    async def _editor(self, pilot, app, text):
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        await _open_editor(pilot, app)
        area = app.screen.query_one("#payload-edit-text", TextArea)
        area.load_text(text)
        await pilot.pause()
        return area

    def test_selecting_a_span_and_typing_replaces_it(self):
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                area = await self._editor(pilot, app, "abcdef")
                area.move_cursor((0, 0))
                await pilot.pause()
                for _ in range(3):
                    await pilot.press("shift+right")
                await pilot.pause()
                self.assertEqual(area.selected_text, "abc")
                await pilot.press("Z")
                await pilot.pause()
                self.assertEqual(area.text, "Zdef")

        self._run(runner())

    def test_arrow_keys_move_the_cursor(self):
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                area = await self._editor(pilot, app, "line one\nline two")
                area.move_cursor((0, 0))
                await pilot.pause()
                await pilot.press("right")
                await pilot.pause()
                self.assertEqual(area.cursor_location, (0, 1))
                await pilot.press("down")
                await pilot.pause()
                self.assertEqual(area.cursor_location, (1, 1))

        self._run(runner())

    def test_ctrl_s_and_escape_are_not_swallowed_by_the_focused_editor(self):
        """The binding-availability pin the whole key choice rests on.

        Neither key is in ``TextArea.BINDINGS`` on the pinned Textual, so both
        bubble to the screen with no `priority=True`. If a future version bound
        either, `ctrl+s` would insert nothing and `Esc` would stop cancelling —
        silently. Asserted on the widget's own binding table AND on the
        behaviour, because either alone could pass while the other broke.
        """
        keys = set()
        for binding in TextArea.BINDINGS:
            keys.update(k.strip() for k in binding.key.split(","))
        self.assertNotIn("ctrl+s", keys)
        self.assertNotIn("escape", keys)

        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                area = await self._editor(pilot, app, "payload text")
                self.assertIs(app.screen.focused, area)
                await pilot.press("ctrl+s")
                await pilot.pause()
                await pilot.pause()
                # It reached the screen's action, not the buffer.
                self.assertIsInstance(app.screen, ConcernPickerModal)
                self.assertEqual(app.screen._payload_override, "payload text")

        self._run(runner())


class LegacyRowRenderCharacterizationTests(unittest.TestCase):
    """P1 (`characterize_legacy_row_render`) — pin what t1636_4 must NOT change.

    Written BEFORE `_ConcernRow.__init__` / `render` / the CSS are touched. The
    trade-profile work edits the **shared** row path — layout selection, the
    prefix, and region truncation all become measured — so a vector-only feature
    can regress every legacy plan-review block. These are the pins that fail if
    it does.

    Composited assertions, never `render()` alone, for the t1274 reason: Rich
    drops an overflowing segment whole, so a string containing the body proves
    nothing about the screen. The one `render()` assertion below is deliberate
    and additional — it pins the exact legacy *template*, which the composited
    view cannot show once the text has been folded.
    """

    LEGACY = Concern("high", "authoring-conv.md:103", "BODYMARKER the body text.")

    def _run(self, coro):
        return asyncio.run(coro)

    async def _row(self, width, height=30, narrow=True, concern=None):
        app = _Host([concern or self.LEGACY], narrow=narrow)
        async with app.run_test(size=(width, height)) as pilot:
            await pilot.pause()
            await pilot.pause()
            row = list(app.screen.query(_ConcernRow))[0]
            return row, _flat_text(_screen_rows(app)), row.render()

    def test_narrow_legacy_row_is_two_line_and_keeps_region_and_body(self):
        """The t1274 contract, at every supported width."""
        for width in ConcernPickerNarrowLayoutTests.SUPPORTED_WIDTHS:
            with self.subTest(width=width):
                row, flat, _ = self._run(self._row(width))
                self.assertTrue(row.has_class("two-line"))
                self.assertFalse(row.has_class("three-line"))
                self.assertIn("authoring", flat)
                self.assertIn("BODYMARKER", flat)

    def test_wide_legacy_row_is_intact_at_a_comfortable_width(self):
        """The `narrow=False` path at 80 columns, where one line is correct.

        The measured-layout change must leave this untouched: 80 columns is
        comfortably above the fallback threshold, so the monitor keeps its
        single-line row exactly as today.
        """
        row, flat, rendered = self._run(self._row(80, narrow=False))
        self.assertFalse(row.has_class("two-line"))
        self.assertFalse(row.has_class("three-line"))
        self.assertIn("authoring-conv.md:103", flat)
        self.assertIn("BODYMARKER", flat)
        self.assertNotIn("\n", rendered)

    def test_legacy_render_template_is_unchanged(self):
        """The exact legacy strings, so a template edit is visible.

        `render()` here on purpose (see the class docstring): this pins the
        newline placement and the two-space separators that the composited view
        cannot report once folding has happened.
        """
        # MARK_UNCHECKED comes from lib/mark_glyphs (the canonical authority),
        # not from monitor_shared - so the mark half of this pin is independent
        # of the module under test rather than tautological.
        mark = f"[#6272A4]{MARK_UNCHECKED}[/]"
        _, _, narrow_render = self._run(self._row(40))
        self.assertEqual(
            narrow_render,
            # Row width 28 - _NARROW_PREFIX_COLS 8 = a 20-cell region budget, so
            # the 21-char region ellipsizes. That is the legacy behaviour.
            f"{mark}  [bold red]HIGH[/] [dim]authoring-conv.md:1\u2026[/]"
            "\n   BODYMARKER the body text.",
        )
        _, _, wide_render = self._run(self._row(80, narrow=False))
        self.assertEqual(
            wide_render,
            # The wide form's fixed 40-cell region budget leaves it untouched.
            f"{mark}  [bold red]HIGH[/] [dim]authoring-conv.md:103[/]"
            "  BODYMARKER the body text.",
        )

    def test_ascii_region_ellipsizes_at_the_legacy_boundary(self):
        """The truncation baseline the cell-aware rewrite must reproduce.

        `_region_label` currently ellipsizes on `len()`. Step 4 replaces that
        with a cell measurement; for pure-ASCII input the two agree, and this is
        the pin that says so — an off-by-one in `set_cell_size` shows up here.
        """
        row = _ConcernRow(Concern("low", "a" * 30, "body"))
        for budget, expected in (
            (10, "a" * 9 + "\u2026"),
            (30, "a" * 30),          # exactly at budget: no ellipsis
            (31, "a" * 30),          # under budget: untouched
        ):
            with self.subTest(budget=budget):
                self.assertEqual(row._region_label(budget), f"[dim]{expected}[/]")

    def test_empty_region_placeholder_is_unchanged(self):
        row = _ConcernRow(Concern("low", "", "body"))
        self.assertEqual(row._region_label(20), "[dim italic](no region)[/]")

    def test_negative_control_a_three_line_class_would_break_the_pin(self):
        """One mutation: force `three-line` on. The class pin must then fail.

        Without this, `test_narrow_legacy_row_is_two_line_...` could be passing
        because the class assertions are vacuous rather than because the legacy
        layout survived.
        """
        # Patch `_sync_layout_classes`, not `__init__`: since t1636_4 the class
        # is re-derived on every resize, so a mutation applied at construction is
        # simply undone before the assertion runs — which this control detected.
        def patched(self):
            self.set_class(True, "three-line")

        with unittest.mock.patch.object(_ConcernRow, "_sync_layout_classes", patched):
            row, _, _ = self._run(self._row(40))
            self.assertTrue(
                row.has_class("three-line"),
                "the mutation did not land - the negative control proves nothing",
            )



class ConcernRowVectorPackingTests(unittest.TestCase):
    """P2 / `pin_narrow_row_width_budget` — the trade profile's width budget.

    **Stage 1** (this class's first two methods, written and observed passing
    BEFORE `_ConcernRow.render` was touched): region and body reach the
    composited output at every supported width, and the row's own measured
    geometry is pinned.

    The geometry guard is the assertion whose absence let a wrong budget ship in
    t1636_1. `check_label_widths.__doc__` derived the profile budget as "24
    columns - 3 indent = 21 cells", but 24 is the **screen** width; the row is
    nested inside the dialog border, the dialog padding and its own padding, so
    at a 24-column screen it is **18** cells wide and the indented profile line
    has 15. Nothing measured that, so nothing caught it.

    Stage 2 (`ConcernTradeProfilePackingTests`) extends this to the vector core.
    """

    #: Measured row content widths at `SUPPORTED_WIDTHS`, narrow layout.
    #: Screen -> `_ConcernRow.size.width`. Pinned, not derived: these numbers ARE
    #: the profile budget, so a CSS change that shifts them must fail loudly here
    #: rather than silently clip the effort scalar off the end of the line.
    ROW_WIDTHS = {40: 28, 30: 24, 24: 18}

    def _run(self, coro):
        return asyncio.run(coro)

    async def _at(self, width, narrow=True, concern=None, height=30):
        app = _Host(
            [concern or Concern("high", "authoring-conv.md:103", "BODYMARKER body.")],
            narrow=narrow,
        )
        async with app.run_test(size=(width, height)) as pilot:
            await pilot.pause()
            await pilot.pause()
            rows = list(app.screen.query(_ConcernRow))
            # `size` must be sampled INSIDE the context manager: once the app
            # shuts down every widget reports 0x0, and a geometry guard reading
            # a torn-down widget would pin zeros instead of the real layout.
            return rows[0].size.width, _flat_text(_screen_rows(app))

    def test_region_and_body_reach_the_screen_at_every_supported_width(self):
        for width in ConcernPickerNarrowLayoutTests.SUPPORTED_WIDTHS:
            with self.subTest(width=width):
                _, flat = self._run(self._at(width))
                self.assertIn("authoring", flat)
                self.assertIn("BODYMARKER", flat)

    def test_row_geometry_is_pinned_at_every_supported_width(self):
        """Drift guard: the row's measured width IS the profile budget.

        `SUPPORTED_WIDTHS` is read from the production constants, so this cannot
        drift onto stale screen widths; `ROW_WIDTHS` then pins what those screens
        actually give the row.
        """
        for width in ConcernPickerNarrowLayoutTests.SUPPORTED_WIDTHS:
            with self.subTest(width=width):
                row_width, _ = self._run(self._at(width))
                self.assertEqual(
                    row_width, self.ROW_WIDTHS[width],
                    f"row geometry moved at screen {width}: the trade-profile "
                    f"budget is derived from this number",
                )

    def test_a_long_body_does_not_evict_the_profile_line(self):
        """A wrapping body must not consume the profile's row.

        **Found in a real 40x24 tmux pane, not here.** Every composited fixture
        in this file used a body short enough to fit one row, so the three-line
        row was never actually exercised: a 36-cell body wrapped to two rows and
        pushed the trade profile out of the `height: 3` box entirely. The profile
        rendered nowhere at all while every test stayed green.

        The body is therefore clipped to one row on a three-line row — and this
        is the assertion that says so, with a body long enough to wrap at every
        supported width.
        """
        concern = Concern(
            "high", "monitor_shared.py:2797",
            "Row folds the body away at narrow widths and this body is "
            "deliberately far too long to fit on a single row.",
            improves=(("correctness", "high"),),
            worsens=(("simplicity", "low"),), effort="medium",
        )
        for width in ConcernPickerNarrowLayoutTests.SUPPORTED_WIDTHS:
            with self.subTest(width=width):
                _, flat = self._run(self._at(width, concern=concern))
                self.assertIn("corr", flat)
                self.assertIn("simpl", flat)
                self.assertIn("E:md", flat)
                self.assertIn("Row folds", flat)

    def test_a_long_body_still_wraps_on_a_legacy_two_line_row(self):
        """Negative control / scope guard: the clip is three-line only.

        A no-vector row keeps its verbatim body — the clip exists to protect the
        profile, so applying it where there is no profile would be an unrelated
        behaviour change to every legacy block.
        """
        long_body = "x" * 200
        row = _ConcernRow(Concern("high", "r", long_body), narrow=True)
        self.assertIn(long_body, row.render())

    def test_the_indented_profile_line_has_three_fewer_cells(self):
        """The narrow continuation line is indented 3, so its budget is width-3.

        Pinned as its own fact because the ladder in `trade_profile` spends
        exactly this: at screen 24 it is 15 cells, which is less than the
        20-cell worst-case core - which is why the indent is a rung.
        """
        for width, row_width in self.ROW_WIDTHS.items():
            with self.subTest(width=width):
                self.assertEqual(row_width - len("   "), row_width - 3)
        self.assertEqual(self.ROW_WIDTHS[24] - 3, 15)



class _PrefixTemplateTests(unittest.TestCase):
    """The prefix is ONE template, measured on rendered text (t1636_4).

    Two failures this pins, both of which shipped in a draft of this task:

    * measuring the **markup** — the `HIGH` + `≠` prefix is 42 cells raw and 9
      rendered, so a raw measurement classifies almost every row as too wide;
    * restating the width as prose arithmetic — the `≠` spacing drifted between
      9 and 10 cells across a plan, and only an **exact** assertion catches that
      (a `<= _NARROW_PREFIX_COLS + 1` bound would have passed both).
    """

    #: The layout contract: `≠` appended directly to the badge, no separating
    #: space. Every prefix budget in `_ConcernRow` derives from these widths.
    EXPECTED = {
        ("high", False): ("□  HIGH ", 8),
        ("high", True): ("□  HIGH≠ ", 9),
        ("medium", False): ("□  MED ", 7),
        ("medium", True): ("□  MED≠ ", 8),
        ("low", False): ("□  LOW ", 7),
        ("low", True): ("□  LOW≠ ", 8),
    }

    #: (dimension, magnitude) whose `derive_priority` gives each badge level.
    _IMPROVES = {"high": (("correctness", "high"),),
                 "medium": (("correctness", "medium"),),
                 "low": (("correctness", "low"),)}

    def _row(self, derived, mismatch):
        marker = "low" if mismatch and derived != "low" else derived
        if mismatch and derived == "low":
            marker = "high"
        return _ConcernRow(Concern(
            marker, "r", "b",
            improves=self._IMPROVES[derived],
            worsens=(("simplicity", "low"),),
            effort="low",
        ))

    def test_every_prefix_state_has_its_exact_pinned_width(self):
        for (derived, mismatch), (plain, cells) in self.EXPECTED.items():
            with self.subTest(badge=derived, mismatch=mismatch):
                seg = self._row(derived, mismatch)._prefix_seg()
                self.assertEqual(seg.plain, plain)
                self.assertEqual(seg.cells, cells)

    def test_the_widest_prefix_exceeds_the_legacy_constant(self):
        """`_NARROW_PREFIX_COLS` is a legacy bound, not the budget.

        This is the finding the constant's own comment got wrong: it claims the
        widest prefix is `HIGH` at 8 cells. With the mismatch marker it is 9, and
        budgeting 8 admits a one-line row that renders one cell wider than it
        measured.
        """
        widest = max(cells for _, cells in self.EXPECTED.values())
        self.assertEqual(widest, monitor_shared._NARROW_PREFIX_COLS + 1)

    def test_measuring_the_markup_instead_would_be_wildly_wrong(self):
        """The `_Seg` split is load-bearing, not stylistic.

        Asserts the two measurements **differ** as well as pinning the plain one
        — without the inequality half this passes vacuously on unstyled text, and
        the whole hazard is that the styled case looks the same to `cell_len`.
        """
        seg = self._row("high", True)._prefix_seg()
        self.assertEqual(seg.cells, 9)
        self.assertEqual(cell_len(seg.markup), 42)
        self.assertNotEqual(cell_len(seg.markup), cell_len(seg.plain))

    def test_the_mismatch_marker_is_single_width(self):
        self.assertEqual(cell_len("≠"), 1)


class ConcernTradeProfilePackingTests(unittest.TestCase):
    """Stage 2 of `pin_narrow_row_width_budget` — the vector core always fits.

    Exhaustive over the pure builder, because a packing claim checked on one
    lucky pair passes while `maint?` + `simpl?` + `E:hi` clips. The builder is
    Textual-free, so the full sweep is cheap; a sampled subset is then driven
    through the real modal to prove the composited screen agrees.
    """

    #: The measured row widths from `ConcernRowVectorPackingTests.ROW_WIDTHS`.
    BUDGETS = (28, 24, 18)
    MAGNITUDES = ("high", "medium", "low", "")
    EFFORTS = ("high", "medium", "low", "")

    def _profile(self, improve_dim, improve_mag, worsen_dim, worsen_mag, effort):
        return Concern(
            "low", "r", "b",
            improves=((improve_dim, improve_mag),),
            worsens=((worsen_dim, worsen_mag),),
            effort=effort,
        )

    def test_the_core_fits_every_budget_for_every_combination(self):
        dims = list(CONCERN_DIMENSIONS)
        checked = 0
        for i_dim in dims:
            for w_dim in dims:
                for i_mag in self.MAGNITUDES:
                    for w_mag in self.MAGNITUDES:
                        for effort in self.EFFORTS:
                            concern = self._profile(i_dim, i_mag, w_dim, w_mag, effort)
                            for budget in self.BUDGETS:
                                seg = trade_profile(concern, budget)
                                checked += 1
                                self.assertLessEqual(
                                    seg.cells, budget,
                                    f"{seg.plain!r} overflows {budget} cells",
                                )
                                # The core: both labels and the effort scalar.
                                self.assertIn(label_for(i_dim), seg.plain)
                                self.assertIn(label_for(w_dim), seg.plain)
                                self.assertIn(
                                    monitor_shared._EFFORT_TOKENS[effort], seg.plain
                                )
        self.assertEqual(checked, len(dims) ** 2 * 4 * 4 * 4 * len(self.BUDGETS))

    def test_the_worst_case_is_an_exact_fit_at_the_floor(self):
        """`▲maint ▼simpl E:hi` is 18 of 18 cells — stated, not discovered."""
        concern = self._profile("maintainability", "", "simplicity", "", "high")
        seg = trade_profile(concern, 18)
        self.assertEqual(seg.plain, "▲maint ▼simpl E:hi")
        self.assertEqual(seg.cells, 18)

    def test_wider_budgets_keep_the_indent_and_the_magnitude_markers(self):
        concern = self._profile("maintainability", "", "simplicity", "", "high")
        for budget in (28, 24):
            with self.subTest(budget=budget):
                seg = trade_profile(concern, budget)
                self.assertEqual(seg.plain, "   ▲maint? ▼simpl? E:hi")
                self.assertEqual(seg.cells, 23)

    def test_negative_control_forcing_the_indent_breaks_the_floor(self):
        """One mutation: keep the indent unconditionally. 18 cells must fail.

        Without this the sweep could be passing because every rung happens to be
        short, rather than because the ladder actually degrades.
        """
        concern = self._profile("maintainability", "", "simplicity", "", "high")
        rungs = trade_profile_rungs(concern)
        indented = [r for r in rungs if r.plain.startswith(" ")]
        self.assertTrue(indented, "expected at least one indented rung")
        self.assertTrue(
            all(r.cells > 18 for r in indented),
            "an indented rung fits 18 cells - the indent rung is not load-bearing",
        )



class ConcernVectorTriStateTests(unittest.TestCase):
    """The states the parser keeps distinct must survive TO THE SCREEN (t1636_4).

    The dimension x magnitude x effort sweep says nothing about these: it only
    ever builds a fully-populated vector. But `Concern` deliberately
    distinguishes ``worsens=None`` (never priced) from ``worsens=()``
    (`Worsens: nothing.` — priced, and the price is zero), and that distinction
    IS the anti-overengineering mechanism t1636 exists to add. A compacting
    refactor that collapsed the two would keep every combination test green
    while deleting the feature.

    So each case asserts the token **and its intentional absence**. The picker is
    the only place a human can act on the difference, so proving it survives here
    is what makes the parser's three-state contract worth anything.
    """

    def _plain(self, **kwargs):
        return trade_profile(Concern("low", "r", "b", **kwargs), 28).plain

    def test_priced_nothing_renders_a_visible_token(self):
        plain = self._plain(improves=(("goal", "high"),), worsens=(), effort="low")
        self.assertIn("▼–", plain)
        self.assertIn("▲goal", plain)

    def test_an_unpriced_worsen_side_renders_no_worsen_token_at_all(self):
        """The other half of the pair — absence is the assertion."""
        plain = self._plain(improves=(("goal", "high"),), worsens=None, effort="low")
        self.assertNotIn("▼", plain)
        self.assertIn("▲goal", plain)

    def test_priced_nothing_and_unpriced_are_not_the_same_rendering(self):
        """Stated directly, so a collapse cannot pass both tests above."""
        priced = self._plain(improves=(("goal", "high"),), worsens=(), effort="low")
        unpriced = self._plain(improves=(("goal", "high"),), worsens=None, effort="low")
        self.assertNotEqual(priced, unpriced)

    def test_an_absent_improve_side_renders_no_improve_token(self):
        plain = self._plain(improves=None, worsens=(("simplicity", "high"),), effort="low")
        self.assertNotIn("▲", plain)
        self.assertIn("▼simpl", plain)

    def test_an_effort_only_trailer_is_still_a_vector(self):
        concern = Concern("low", "r", "b", effort="low")
        self.assertTrue(has_impact_vector(concern))
        plain = trade_profile(concern, 28).plain
        self.assertIn("E:lo", plain)
        self.assertNotIn("▲", plain)
        self.assertNotIn("▼", plain)

    def test_a_concern_with_no_vector_at_all_renders_nothing(self):
        self.assertEqual(self._plain(), "")
        self.assertFalse(has_impact_vector(Concern("low", "r", "b")))

    def test_unspecified_effort_renders_the_question_token(self):
        plain = self._plain(improves=(("goal", "high"),), worsens=(), effort="")
        self.assertIn("E:?", plain)

    def test_the_question_mark_marks_only_an_unspecified_magnitude(self):
        known = self._plain(improves=(("goal", "high"),), worsens=(), effort="low")
        self.assertNotIn("goal?", known)
        unknown = self._plain(improves=(("goal", ""),), worsens=(), effort="low")
        self.assertIn("goal?", unknown)

    def test_a_worsen_only_concern_derives_low_and_flags_the_mismatch(self):
        """`derive_priority(None)` is `low`, so a `high` marker disagrees.

        The badge shows the derived value and the disagreement is flagged — never
        silently reconciled, which is the consumer-side rule `concern-format.md`
        states.
        """
        row = _ConcernRow(Concern(
            "high", "r", "b", worsens=(("simplicity", "high"),), effort="low",
        ))
        seg = row._prefix_seg()
        self.assertEqual(seg.plain, "□  LOW≠ ")

    def test_a_legacy_concern_keeps_its_marker_priority_untouched(self):
        row = _ConcernRow(Concern("high", "r", "b"))
        self.assertEqual(row._prefix_seg().plain, "□  HIGH ")


class ConcernRegionCellWidthTests(unittest.TestCase):
    """Region truncation is measured in CELLS, not characters (t1636_4).

    The marker grammar is ``[^\\]]*``, so a region is free text and wide
    characters are parser-valid. ``插件配置模块.py:12`` is 12 characters and **18
    cells**: under the old ``len()`` check it passed the budget unellipsized,
    overflowed line 1 and folded the body away at screens 30 and 24 — the t1274
    failure, on input the producer is entitled to emit.

    Every case is paired with an ASCII control of the same ``len()``. The control
    passed before this fix and the wide-character case did not, which is what
    proves these fixtures measure cells rather than characters.
    """

    WIDE = "插件配置模块.py:12"      # len 12, 18 cells
    ASCII = "authoring-con"          # len 13, 13 cells

    def _run(self, coro):
        return asyncio.run(coro)

    async def _flat(self, width, region, narrow=True):
        app = _Host([Concern("high", region, "BODYMARKER the body.")], narrow=narrow)
        async with app.run_test(size=(width, 30)) as pilot:
            await pilot.pause()
            await pilot.pause()
            return _flat_text(_screen_rows(app))

    def test_the_measurement_itself_disagrees_with_len(self):
        """The premise, stated — otherwise the fixtures below prove nothing."""
        self.assertEqual(len(self.WIDE), 12)
        self.assertEqual(cell_len(self.WIDE), 18)

    def test_a_wide_region_keeps_the_body_at_every_supported_width(self):
        for width in ConcernPickerNarrowLayoutTests.SUPPORTED_WIDTHS:
            with self.subTest(width=width):
                flat = self._run(self._flat(width, self.WIDE))
                self.assertIn("BODYMARKER", flat)
                self.assertIn("插件", flat)

    def test_the_ascii_control_behaves_the_same(self):
        for width in ConcernPickerNarrowLayoutTests.SUPPORTED_WIDTHS:
            with self.subTest(width=width):
                flat = self._run(self._flat(width, self.ASCII))
                self.assertIn("BODYMARKER", flat)
                self.assertIn("authoring", flat)

    def test_a_wide_region_survives_the_responsive_one_line_path(self):
        flat = self._run(self._flat(100, self.WIDE, narrow=False))
        self.assertIn("插件", flat)
        self.assertIn("BODYMARKER", flat)

    def test_truncation_never_splits_a_wide_glyph(self):
        """`set_cell_size` cuts on a cell boundary, so the result fits exactly."""
        row = _ConcernRow(Concern("low", self.WIDE, "b"))
        for budget in range(4, 20):
            with self.subTest(budget=budget):
                self.assertLessEqual(cell_len(row._region_seg(budget).plain), budget)



def _vector_concerns():
    """Three vector-bearing concerns — every row is the taller three-line form."""
    return [
        Concern("high", "x.py:12", "AAA a blocking one.", "blocking", "CONFIRMED",
                improves=(("correctness", "high"),),
                worsens=(("simplicity", "low"),), effort="low"),
        Concern("low", "accepted risk", "BBB an informational one.",
                "informational", "CONFIRMED",
                improves=(("maintainability", "low"),), worsens=(), effort="low"),
        Concern("medium", "y.py:34", "CCC a follow-up one.", "follow-up", "PLAUSIBLE",
                improves=(("verification", "medium"),),
                worsens=(("simplicity", "medium"),), effort="medium"),
    ]


class ConcernGuidanceContractTests(unittest.TestCase):
    """The help line's key names outrank the decision guidance (t1636_4).

    The precedence is one-directional and absolute: once the OK/Cancel buttons
    are dropped the help line is the ONLY place `r` / `t` / `R` / `u` / Esc are
    named, whereas the guidance restates a rubric the per-row vector already
    encodes.

    **Why this is pinned per geometry rather than as one blanket "no worse".**
    At 40x20 the keys are already evicted before this task touches anything —
    `_CONCERN_HELP_FULL` wraps to six rows at 40 columns because the compact swap
    is keyed at <=30 — so that geometry *cannot* detect a regression. At 40x24
    the baseline does show them, and four extra rows of chrome removes all three.
    Only the second geometry can hold the contract, so it is asserted there and
    the first gets a weaker, honest guard.
    """

    #: Named on the help line and nowhere else once the buttons are gone. The
    #: wording differs by tier — `_CONCERN_HELP_COMPACT` applies only at or below
    #: `_PICKER_NARROW_MIN_WIDTH` (30), so 40 columns renders the FULL line. A
    #: single token set would silently test the wrong string at one of the two
    #: geometries this contract cares about.
    KEY_TOKENS_FULL = ("esc", "reject", "spin off", "rejected list", "unparsed")
    KEY_TOKENS_COMPACT = ("esc", "r rej", "t spin", "R list", "u raw")

    def _run(self, coro):
        return asyncio.run(coro)

    async def _at(self, width, height, concerns=None, narrow=True):
        app = _Host(concerns or _vector_concerns(), narrow=narrow)
        async with app.run_test(size=(width, height)) as pilot:
            await pilot.pause()
            await pilot.pause()
            guidance = list(app.screen.query("#concern-guidance"))
            visible = bool(guidance) and guidance[0].display
            return (_flat_text(_screen_rows(app)),
                    visible,
                    app.screen.has_class("xnarrow"))

    def _keys_visible(self, flat, xnarrow):
        tokens = self.KEY_TOKENS_COMPACT if xnarrow else self.KEY_TOKENS_FULL
        lowered = flat.lower()
        return all(token.lower() in lowered for token in tokens)

    def test_baseline_shows_the_keys_at_40x24(self):
        """The premise this contract rests on — measured, not assumed."""
        flat, _, xn = self._run(self._at(40, 24, concerns=_mixed_concerns()))
        self.assertTrue(self._keys_visible(flat, xn))

    def test_keys_survive_at_40x24_with_vector_rows(self):
        flat, guidance, xn = self._run(self._at(40, 24))
        self.assertTrue(
            self._keys_visible(flat, xn),
            "three-line vector rows evicted the help line's key names",
        )
        self.assertFalse(guidance, "guidance must yield to the keys at 40 columns")

    def test_keys_survive_at_40x30_with_vector_rows(self):
        flat, guidance, xn = self._run(self._at(40, 30))
        self.assertTrue(self._keys_visible(flat, xn))
        self.assertFalse(guidance)

    def test_40x20_is_no_worse_than_its_baseline(self):
        """The keys are already gone here before this task — so guard the rest.

        Claiming the contract at this geometry would be false; claiming nothing
        would miss a real regression. What is actually assertable is that the
        vector row still renders and the guidance stays out of the way.
        """
        base_flat, _, xn = self._run(self._at(40, 20, concerns=_mixed_concerns()))
        self.assertFalse(self._keys_visible(base_flat, xn))  # pre-existing, not ours
        flat, guidance, _ = self._run(self._at(40, 20))
        self.assertFalse(guidance)
        self.assertIn("AAA", flat)
        self.assertIn("corr", flat)          # the profile core still reaches the screen
        self.assertIn("E:lo", flat)

    def test_guidance_appears_where_there_is_genuinely_room(self):
        flat, guidance, xn = self._run(self._at(100, 30, narrow=False))
        self.assertTrue(guidance)
        self.assertIn("fwd:", flat)
        self.assertIn("rej:", flat)
        self.assertTrue(self._keys_visible(flat, xn))

    def test_a_legacy_block_composes_no_guidance_at_all(self):
        _, guidance, _ = self._run(self._at(100, 30, concerns=_mixed_concerns(),
                                            narrow=False))
        self.assertFalse(guidance)

    def test_negative_control_forcing_guidance_on_breaks_40x24(self):
        """One mutation: show the guidance unconditionally.

        Without this, `test_keys_survive_at_40x24_with_vector_rows` could be
        passing because the gate happens to hide guidance for an unrelated
        reason rather than because the precedence rule works.
        """
        with unittest.mock.patch.object(
            monitor_shared, "_GUIDANCE_MIN_WIDTH", 0
        ), unittest.mock.patch.object(
            monitor_shared, "_GUIDANCE_MIN_HEIGHT", 0
        ):
            flat, guidance, xn = self._run(self._at(40, 24))
        self.assertTrue(guidance, "the mutation did not land")
        self.assertFalse(
            self._keys_visible(flat, xn),
            "forcing the guidance on did NOT cost the keys - the contract test "
            "at 40x24 is not discriminating",
        )


class ConcernOneLineBoundaryTests(unittest.TestCase):
    """The measured prefix decides the layout, at the exact boundary (t1636_4).

    A `narrow=False` row with a priority mismatch renders a **9**-cell prefix
    (`□  HIGH≠ `) where the legacy constant reserves 8. At a width where one
    extra cell decides the layout, budgeting the constant admits a one-line row
    that renders wider than it measured — and Rich folds the overflowing segment
    whole rather than truncating it.
    """

    def _run(self, coro):
        return asyncio.run(coro)

    #: Marker `low` while `Improves: correctness(high)` derives `high` — so the
    #: badge reads HIGH and carries the mismatch marker.
    MISMATCH = Concern("low", "authoring-conv.md:103", "BODYMARKER the body.",
                       improves=(("correctness", "high"),),
                       worsens=(("simplicity", "low"),), effort="low")
    CONTROL = Concern("high", "authoring-conv.md:103", "BODYMARKER the body.",
                      improves=(("correctness", "high"),),
                      worsens=(("simplicity", "low"),), effort="low")

    async def _at(self, width, concern):
        app = _Host([concern], narrow=False)
        async with app.run_test(size=(width, 30)) as pilot:
            await pilot.pause()
            await pilot.pause()
            return _flat_text(_screen_rows(app))

    def test_the_two_fixtures_differ_only_by_one_prefix_cell(self):
        """The discriminating fact, pinned before it is relied on."""
        self.assertEqual(_ConcernRow(self.MISMATCH)._prefix_seg().cells, 9)
        self.assertEqual(_ConcernRow(self.CONTROL)._prefix_seg().cells, 8)

    def test_region_profile_core_and_body_all_survive_a_mismatched_row(self):
        for width in (100, 120):
            with self.subTest(width=width):
                flat = self._run(self._at(width, self.MISMATCH))
                self.assertIn("authoring-conv", flat)
                self.assertIn("corr", flat)
                self.assertIn("simpl", flat)
                self.assertIn("E:lo", flat)
                self.assertIn("BODYMARKER", flat)

    def test_the_control_survives_at_the_same_widths(self):
        for width in (100, 120):
            with self.subTest(width=width):
                flat = self._run(self._at(width, self.CONTROL))
                self.assertIn("authoring-conv", flat)
                self.assertIn("E:lo", flat)
                self.assertIn("BODYMARKER", flat)

    def test_the_mismatch_marker_reaches_the_screen(self):
        flat = self._run(self._at(120, self.MISMATCH))
        self.assertIn("≠", flat)
        self.assertIn("HIGH", flat)



class ConcernRowMarkupSafetyTests(unittest.TestCase):
    """Free text can never be read as markup by the row (t1636_4).

    ``rich.markup.escape`` is tag-aware and leaves a **bare** ``[`` alone — safe
    while the body was the last thing on the render string, fatal once the trade
    profile added markup on a following line. Rich scans forward from the stray
    bracket, swallows the profile's first tag, and the next ``[/]`` has nothing
    to close::

        MarkupError: auto closing tag ('[/]') has nothing to close

    Reproduced in the real modal at 40, 30 and 24 columns before the fix, with a
    body as ordinary as ``x[``. A shadow agent writes concern bodies as free
    text, so this is reachable input, and the failure takes down the whole modal
    rather than degrading one row.
    """

    HOSTILE = ("x[", "[", "a [ b", "[dim]", "[/]", "[bold]x[/]", "100[0]",
               "unclosed [tag and more text", "[[", "\\")

    def _run(self, coro):
        return asyncio.run(coro)

    def _vector(self, body, region="r.py:1"):
        return Concern("high", region, body,
                       improves=(("correctness", "high"),),
                       worsens=(("simplicity", "low"),), effort="medium")

    async def _screen(self, width, concern, narrow=True):
        app = _Host([concern], narrow=narrow)
        async with app.run_test(size=(width, 30)) as pilot:
            await pilot.pause()
            await pilot.pause()
            return _flat_text(_screen_rows(app))

    def test_a_hostile_body_never_crashes_a_vector_row(self):
        for body in self.HOSTILE:
            for width in ConcernPickerNarrowLayoutTests.SUPPORTED_WIDTHS:
                with self.subTest(body=body, width=width):
                    self._run(self._screen(width, self._vector(body)))

    def test_a_hostile_body_never_crashes_the_narrow_false_path(self):
        """`narrow=False` goes multi-line below ~60 columns, so it is affected too."""
        for body in self.HOSTILE:
            for width in (100, 60, 40, 24):
                with self.subTest(body=body, width=width):
                    self._run(self._screen(width, self._vector(body), narrow=False))

    def test_a_hostile_region_never_crashes_a_vector_row(self):
        """The region survives today only by where it sits in the string.

        It is escaped the same way regardless, so the safety does not depend on
        Rich's tag regex happening not to match.
        """
        for region in self.HOSTILE:
            for width in ConcernPickerNarrowLayoutTests.SUPPORTED_WIDTHS:
                with self.subTest(region=region, width=width):
                    self._run(self._screen(width, self._vector("body", region)))

    def test_a_bracket_landing_exactly_at_the_clip_boundary(self):
        """The clip cuts PLAIN text, so it can never split an escape sequence.

        Sweeps the bracket across the truncation point one cell at a time: if the
        row escaped first and clipped second, some offset would cut a `\\[` pair
        in half and leave a bare bracket behind.
        """
        for width in ConcernPickerNarrowLayoutTests.SUPPORTED_WIDTHS:
            for pad in range(0, 32):
                body = "a" * pad + "[dim]" + "b" * 30
                with self.subTest(width=width, pad=pad):
                    self._run(self._screen(width, self._vector(body)))

    def test_the_bracket_still_reaches_the_screen_as_a_literal(self):
        """Escaping must hide the brackets from the parser, not from the user."""
        flat = self._run(self._screen(40, self._vector("keep [ me")))
        self.assertIn("keep [ me", flat)

    def test_negative_control_the_tag_aware_escape_alone_would_crash(self):
        """One mutation: fall back to `escape()`. The vector row must then die.

        Without this the tests above could be passing because the composition
        happens to be benign rather than because `_escape_markup` is doing work.
        """
        from rich.markup import escape as tag_aware
        with unittest.mock.patch.object(monitor_shared, "_escape_markup", tag_aware):
            with self.assertRaises(Exception):
                self._run(self._screen(40, self._vector("x[")))


if __name__ == "__main__":
    unittest.main()
