"""The TUI switcher fits a pane narrower than its dialog (t2340).

The switcher dialog is 44 columns wide; minimonitor's usual split is 40. Before
t2340 the dialog spilled past the pane: its right border was missing on every
row and the widest hint rows ended ``(S)etting`` / ``(G)i``.

The fix caps the dialog to the screen and, whenever the cap engages (screen
narrower than the dialog, any host), compacts it — vertical paddings dropped,
list minimum one row, and the highlighted row scrolled into view after layout
and on every resize. Each test below pins one way the cap alone went wrong:

- the hint and the border must be inside the pane;
- a long agent-window name wraps inside the border (Textual breaks a single
  long token mid-word, so it is rebuilt from the item's rows, not searched);
- in short panes the docked hint must not cover the selected list row —
  initially, after Down/Up navigation, and after a resize with no key press;
- a wide host (Monitor) in a narrow pane gets the same compaction;
- at 44+ columns the layout is exactly today's, and widening reverts it.

These assert the COMPOSITED screen (``_compositor.render_strips``): a widget's
own render would not show what the docked footer covers.

Run: python3 tests/test_tui_switcher_narrow_fit.py
"""

from __future__ import annotations

import asyncio
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from textual.app import App  # noqa: E402
from textual.content import Content  # noqa: E402
from textual.widgets import Static  # noqa: E402

import tui_switcher as ts  # noqa: E402
from agent_launch_utils import AitasksSession  # noqa: E402
from shortcut_labels import display_form  # noqa: E402

#: A realistic desync line — the summary is almost never empty in real use
#: (``clean`` at minimum), so its row always takes space.
DESYNC = "main: 1↑/0↓ · aitask-data: 0↑/3↓"

LONG_AGENT = "agent-t2340_fix_tui_switcher_clipped_in_minimonitor_pane"

COMPACT = "-compact"


def _sessions(n: int) -> list[AitasksSession]:
    return [
        AitasksSession(f"s{i}", Path(f"/tmp/aitasks_t2340_s{i}"), f"s{i}")
        for i in range(1, n + 1)
    ]


class _Host(App):
    def compose(self):
        yield Static("host")


def _run(size, body, *, host="minimonitor", sessions=1, windows=(),
         companion=False):
    """Mount the real overlay in a host App of ``size`` and await ``body``.

    ``narrow`` follows the host exactly as the TUIs pass it (True only for
    minimonitor), so a Monitor case exercises the width-driven path alone.
    """
    async def go():
        app = _Host()
        async with app.run_test(size=size) as pilot:
            with patch.object(ts, "discover_aitasks_sessions",
                              return_value=_sessions(sessions)), \
                    patch.object(ts, "_session_windows",
                                 return_value=list(windows)), \
                    patch.object(ts.TuiSwitcherOverlay,
                                 "_compute_desync_summary",
                                 return_value=DESYNC), \
                    patch.object(ts.TuiSwitcherOverlay,
                                 "_resolve_companion_target",
                                 return_value=object() if companion else None):
                overlay = ts.TuiSwitcherOverlay(
                    session="s1", current_tui=host,
                    narrow=(host == "minimonitor"),
                )
                await app.push_screen(overlay)
                await pilot.pause()
                await pilot.pause()
                await body(app, pilot, overlay)

    asyncio.run(go())


def _rows(app) -> list[str]:
    return [strip.text
            for strip in app.screen._compositor.render_strips(app.screen.size)]


def _hint_phrases(*, multi: bool, companion: bool) -> list[str]:
    """Every phrase the footer must show, key included, derived from source.

    The structural phrases carry their key (``Enter switch``, ``←/→ session``,
    ``J/Esc close``), so a footer that lost a key label fails even though the
    action word is still on screen.
    """
    phrases = [
        Content.from_markup(ts._hint_segment(action_id, label, key)).plain
        for action_id, label, key in ts._HINT_ITEMS
    ]
    if companion:
        phrases.append(Content.from_markup(ts._hint_segment(
            "spawn_minimonitor", "minimonitor", "M", spell_shift=True)).plain)
    close_key = (f"{display_form(ts._OVERLAY_OPEN_KEY)}/Esc"
                 if ts._OVERLAY_TOGGLE_CLOSES else "Esc")
    phrases.append("Enter switch")
    if multi:
        phrases.append("←/→ session")
    phrases.append(f"{close_key} close")
    return phrases


def _footer_text(app, overlay) -> str:
    """The footer as drawn, inside the hint's region only, wraps stitched.

    Each row of the hint region is sliced to the region's columns, so text
    drawn past the screen edge is simply absent; rows are joined with a space
    and whitespace collapsed, so a phrase the label wrapped between two words
    still reads whole.
    """
    hint = overlay.query_one("#switcher_hint").region
    rows = _rows(app)
    lines = [rows[y][hint.x:hint.x + hint.width]
             for y in range(hint.y, min(hint.bottom, len(rows)))]
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


class _Asserts(unittest.TestCase):

    def _assert_fits(self, app, overlay):
        dialog = overlay.query_one("#switcher_dialog").region
        width = app.screen.size.width
        self.assertGreaterEqual(dialog.x, 0)
        self.assertLessEqual(dialog.x + dialog.width, width,
                             f"dialog {dialog} spills past a {width}-col screen")

    def _assert_right_border(self, app, overlay, ys=None):
        dialog = overlay.query_one("#switcher_dialog").region
        rows = _rows(app)
        col = dialog.x + dialog.width - 1
        for y in ys if ys is not None else range(dialog.y, dialog.bottom):
            row = rows[y]
            self.assertLess(col, len(row), f"border column off-screen on row {y}")
            self.assertNotEqual(row[col], " ",
                                f"right border missing on row {y}: {row!r}")

    def _assert_hint_words(self, app, overlay, *, multi=False, companion=False):
        footer = _footer_text(app, overlay)
        for phrase in _hint_phrases(multi=multi, companion=companion):
            with self.subTest(phrase=phrase):
                self.assertRegex(
                    footer, r"(?<!\S)" + re.escape(phrase) + r"(?!\S)",
                    f"footer phrase {phrase!r} is cut or missing",
                )

    def _assert_selection_drawn(self, app, overlay, where=""):
        lv = overlay.query_one("#switcher_list")
        hint = overlay.query_one("#switcher_hint").region
        item = lv.highlighted_child
        self.assertIsNotNone(item, where)
        label = getattr(item, "tui_label", None) or item.window_name
        region = item.region
        self.assertGreater(region.height, 0,
                           f"{where}: {label!r} is scrolled out of view")
        self.assertLess(region.y, hint.y,
                        f"{where}: {label!r} at y={region.y} is under the "
                        f"footer (hint starts at y={hint.y})")
        rows = _rows(app)
        drawn = [y for y in range(lv.region.y, min(hint.y, len(rows)))
                 if label in rows[y]]
        self.assertTrue(drawn, f"{where}: {label!r} is not drawn above the footer")


class NarrowWidthTests(_Asserts):

    def test_dialog_fits_narrow_screen(self):
        for width in (40, 34):
            with self.subTest(width=width):
                async def body(app, pilot, ov):
                    self._assert_fits(app, ov)
                _run((width, 40), body)

    def test_right_border_drawn_on_every_dialog_row(self):
        async def body(app, pilot, ov):
            self._assert_right_border(app, ov)
        _run((40, 40), body)

    def test_every_hint_word_is_on_screen(self):
        for width in (40, 34):
            for n in (1, 2):
                with self.subTest(width=width, sessions=n):
                    async def body(app, pilot, ov, n=n):
                        self._assert_hint_words(app, ov, multi=n > 1)
                    _run((width, 40), body, sessions=n)

    def test_long_agent_window_name_stays_inside(self):
        async def body(app, pilot, ov):
            lv = ov.query_one("#switcher_list")
            idx, item = next(
                (i, c) for i, c in enumerate(lv.children)
                if isinstance(c, ts._WindowListItem)
            )
            lv.index = idx
            lv.scroll_to_widget(item, animate=False)
            await pilot.pause()
            await pilot.pause()
            region = item.region
            self.assertGreater(region.height, 0)
            rows = _rows(app)
            ys = range(region.y, region.bottom)
            visible = "".join(
                rows[y][region.x:region.x + region.width].strip() for y in ys
            )
            self.assertIn(LONG_AGENT, visible)
            self._assert_right_border(app, ov, ys=ys)
        _run((40, 40), body, windows=[("@9", 9, LONG_AGENT)])


class ShortPaneTests(_Asserts):

    async def _walk(self, app, pilot, ov, where):
        self._assert_selection_drawn(app, ov, f"{where} initial")
        for i in range(3):
            await pilot.press("down")
            await pilot.pause()
            self._assert_selection_drawn(app, ov, f"{where} down#{i + 1}")
        # Back up to the first selectable row and past it — wraps to the last.
        for i in range(4):
            await pilot.press("up")
            await pilot.pause()
            self._assert_selection_drawn(app, ov, f"{where} up#{i + 1}")

    def test_short_pane_keeps_selection_drawn_while_navigating(self):
        cases = [((40, 18), 2), ((40, 17), 2), ((34, 18), 2), ((40, 14), 1)]
        for size, n in cases:
            with self.subTest(size=size, sessions=n):
                async def body(app, pilot, ov, size=size, n=n):
                    if size == (40, 18):
                        self._assert_hint_words(app, ov, multi=True)
                    await self._walk(app, pilot, ov, f"{size} sessions={n}")
                _run(size, body, sessions=n)

    def test_selection_stays_drawn_after_resize(self):
        async def body(app, pilot, ov):
            self._assert_selection_drawn(app, ov, "40x18")
            await pilot.resize_terminal(34, 18)
            await pilot.pause()
            await pilot.pause()
            self._assert_selection_drawn(app, ov, "resized to 34x18, no key")
            for i in range(2):
                await pilot.press("down")
                await pilot.pause()
                self._assert_selection_drawn(app, ov, f"34x18 down#{i + 1}")
        _run((40, 18), body, sessions=2)

    def test_narrow_monitor_host_gets_the_same_compaction(self):
        async def body(app, pilot, ov):
            self._assert_fits(app, ov)
            self.assertTrue(
                ov.query_one("#switcher_dialog").has_class(COMPACT))
            self._assert_hint_words(app, ov, multi=True, companion=True)
            self._assert_selection_drawn(app, ov, "monitor 34x20 initial")
            for i in range(2):
                await pilot.press("down")
                await pilot.pause()
                self._assert_selection_drawn(app, ov, f"monitor down#{i + 1}")
        _run((34, 20), body, host="monitor", sessions=2, companion=True)


class WideLayoutTests(_Asserts):

    def _assert_wide(self, ov):
        dialog = ov.query_one("#switcher_dialog")
        self.assertEqual(dialog.region.width, 44)
        self.assertFalse(dialog.has_class(COMPACT))
        self.assertEqual(tuple(dialog.styles.padding), (1, 2, 1, 2))
        self.assertEqual(
            tuple(ov.query_one("#switcher_title").styles.padding), (0, 0, 1, 0))
        self.assertEqual(
            tuple(ov.query_one("#switcher_hint").styles.padding), (1, 0, 0, 0))

    def test_wide_layout_unchanged(self):
        for host in ("minimonitor", "board"):
            for size in ((120, 40), (44, 18)):
                with self.subTest(host=host, size=size):
                    async def body(app, pilot, ov):
                        self._assert_wide(ov)
                    _run(size, body, host=host)

    def test_compaction_reverts_when_widened(self):
        async def body(app, pilot, ov):
            await pilot.resize_terminal(50, 18)
            await pilot.pause()
            await pilot.pause()
            self._assert_wide(ov)
        _run((40, 18), body, sessions=2)


if __name__ == "__main__":
    unittest.main()
