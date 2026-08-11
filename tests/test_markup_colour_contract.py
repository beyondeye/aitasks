"""The markup colour contract: ratified values, and proof they paint (t1453).

Two tiers, answering different questions. Neither substitutes for the other:

===============  ==========================================  ==================
tier             question                                    fails when
===============  ==========================================  ==================
ratification     is this the value we chose?                  someone changes a
                                                              shade without
                                                              deciding to
composited       does that value actually *paint*?            the value is
                                                              syntactically
                                                              inert
===============  ==========================================  ==================

The composited tier exists because Textual's markup parser fails silently on an
unknown token: ``Content.from_markup`` stores the style string in the span
verbatim, so ``render().spans`` assertions pass while the compositor paints the
default foreground and drops bold/dim/strike. Four styles shipped inert for
months that way. The static half of the same guard is
``test_textual_markup_colours.py``.

**Why not ``assertNotEqual(painted, "#e0e0e0")``.** That is the existing idiom in
``test_monitor_session_divider.py``, and it does not generalise: the fallback is
whatever CSS supplies for *that* widget, not the theme default. Measured on the
real ``_TuiListItem``, the three inert runs painted ``#ddedf9`` (the ListView
item colour) — so a ``!= "#e0e0e0"`` assertion would have passed on all three
live defects. Every composited test here instead mounts two reference controls
in the *same* CSS context and asserts the target matches the live reference and
that the live reference differs from an unstyled run. That decomposes cleanly:
the first assertion says *the call site uses the constant*, the second says
*the constant is live*.

Run: python3 tests/test_markup_colour_contract.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from rich.style import Style as RichStyle  # noqa: E402
from rich.table import Table as RichTable  # noqa: E402
from rich.text import Text as RichText  # noqa: E402
from textual.app import App  # noqa: E402
from textual.widgets import ListView, Static  # noqa: E402

import tui_switcher as ts  # noqa: E402
from tui_switcher import TUI_KEY_HINT_STYLE, TUI_RUNNING_STYLE  # noqa: E402

from monitor.monitor_shared import (  # noqa: E402
    STATE_STYLE_ACTIVE, STATE_STYLE_DONE, STATE_STYLE_IDLE, STATE_STYLE_PROMPT,
    format_pane_status, format_state_dot,
)
from monitor.monitor_core import (  # noqa: E402
    PaneCategory, PaneSnapshot, TmuxPaneInfo,
)
from brainstorm.widgets import OperationRow  # noqa: E402

#: Payload of an unstyled reference run, and of a styled one. Distinct ASCII so
#: the segment walk can find each without matching production glyphs.
_REF_PLAIN = "ZZPLAIN"
_REF_LIVE = "ZZLIVE"


def _pane(pane_id="%1"):
    return TmuxPaneInfo(
        window_index="1", window_name="agent-pick-42", pane_index="0",
        pane_id=pane_id, pane_pid=1001, current_command="bash",
        width=80, height=24, category=PaneCategory.AGENT, session_name="demo",
    )


class _FakeMonitor:
    """Duck-typed monitor, as in test_monitor_completed_status.py."""

    multi_session = False

    def get_compare_mode(self, pane_id):
        return "stripped"

    def is_compare_mode_overridden(self, pane_id):
        return False

    def get_shadow_snapshot(self, followed_pane_id):
        return None

    def get_session_to_project_mapping(self):
        return {}

    def control_state(self):
        from monitor.monitor_core import TmuxControlState
        return TmuxControlState.CONNECTED


class _FakeTaskCache:
    def get_task_id_for_pane(self, pane):
        return "42"

    def get_task_info(self, task_id, session_name=""):
        return None

    def update_session_mapping(self, mapping):
        pass


def _snapshot(*, awaiting=False, idle=False) -> PaneSnapshot:
    return PaneSnapshot(
        pane=_pane(), content="x", timestamp=0.0,
        idle_seconds=412.0 if idle else 0.0, is_idle=idle,
        awaiting_input=awaiting,
        awaiting_input_kind="claude_proceed" if awaiting else "",
    )


def segments(app) -> list[tuple[str, object]]:
    """Every non-blank (text, style) pair on screen, IN ORDER, with duplicates.

    Order and duplicates both matter. A dict keyed by stripped text silently
    collapses repeated glyphs — the monitor legend renders four identical ●, so
    a dict keeps only the first (`active`) one and any assertion about the DONE
    dot would actually be reading the active dot.
    """
    out: list[tuple[str, object]] = []
    for strip in app.screen._compositor.render_strips():
        for segment in strip:
            text = segment.text.strip()
            if text and segment.style is not None:
                out.append((text, segment.style))
    return out


def hex_of(style) -> str | None:
    if style is None or style.color is None:
        return None
    return style.color.get_truecolor().hex.lower()


def painted(app) -> dict[str, str]:
    """{stripped segment text: resolved foreground hex}, first occurrence wins.

    Segment walk lifted from tests/test_monitor_session_divider.py's
    CompositedColourTests: the compositor is the only layer at which a style
    string has actually been resolved. Safe only where the payload text is
    unique on screen — use segments() when it is not.
    """
    out: dict[str, str] = {}
    for text, style in segments(app):
        colour = hex_of(style)
        if colour is not None:
            out.setdefault(text, colour)
    return out


def glyph_before(pairs: list[tuple[str, object]], needle: str, glyph: str = "●"):
    """The style of the last *glyph* appearing before the run containing *needle*.

    Identifies one of several identical glyphs by its position relative to the
    label that follows it, which is how the legend distinguishes its four dots.
    """
    for index, (text, _style) in enumerate(pairs):
        if needle in text:
            for back in range(index - 1, -1, -1):
                if pairs[back][0] == glyph:
                    return pairs[back][1]
            raise AssertionError(f"no {glyph!r} found before {needle!r}")
    raise AssertionError(f"{needle!r} not on screen: {[t for t, _ in pairs]}")


def styles_of(app) -> dict[str, object]:
    """{stripped segment text: the full resolved Style} — for attribute checks."""
    out: dict[str, object] = {}
    for strip in app.screen._compositor.render_strips():
        for segment in strip:
            text = segment.text.strip()
            if text and segment.style is not None:
                out.setdefault(text, segment.style)
    return out


# ===========================================================================
# 1. Ratification
# ===========================================================================
class RatifiedStylesTests(unittest.TestCase):
    """The single place a colour literal appears in the suite.

    Every other test derives from these constants, so changing a shade is one
    deliberate, reviewable edit here rather than a scatter of mechanical ones.
    Same shape as test_monitor_session_divider.test_style_is_not_dim.
    """

    def test_done_state_style_is_the_ratified_value(self):
        self.assertEqual(STATE_STYLE_DONE, "bold #1e90ff")

    def test_the_other_three_state_styles_are_the_ratified_values(self):
        self.assertEqual(STATE_STYLE_PROMPT, "bold magenta")
        self.assertEqual(STATE_STYLE_IDLE, "yellow")
        self.assertEqual(STATE_STYLE_ACTIVE, "green")

    def test_tui_key_hint_style_is_the_ratified_value(self):
        self.assertEqual(TUI_KEY_HINT_STYLE, "bold cyan")

    def test_tui_running_style_is_the_ratified_value(self):
        self.assertEqual(TUI_RUNNING_STYLE, "#00ff00")

    def test_the_running_style_is_a_hex_literal_not_an_ansi_name(self):
        """`ansi_bright_green` parses but is theme-dependent, so unpinnable.

        It carries an ANSI flag that remaps through the theme's palette at
        render time: #98e024 under textual-dark, #60cb00 under textual-light —
        a chartreuse either way, not the bright green the name implies.
        """
        self.assertTrue(TUI_RUNNING_STYLE.startswith("#"))
        self.assertNotIn("ansi", TUI_RUNNING_STYLE)

    def test_disabled_operation_row_is_dim_and_struck(self):
        """The disabled row has no named constant; ratify the markup itself."""
        markup = OperationRow("k", "Label", "desc", disabled=True).render()
        self.assertIn("[dim strike]", markup)
        # Rich's spelling. Textual does not know it and drops the whole span,
        # so a disabled row rendered identically to an enabled one.
        self.assertNotIn("strikethrough", markup)

    def test_an_enabled_operation_row_is_not_struck(self):
        markup = OperationRow("k", "Label", "desc", disabled=False).render()
        self.assertNotIn("strike", markup)


# ===========================================================================
# 2. Composited liveness
# ===========================================================================
class _MarkupHost(App):
    """Mounts arbitrary markup strings plus the two reference controls."""

    def __init__(self, markups: list[str], reference_style: str) -> None:
        self._markups = markups
        self._reference_style = reference_style
        super().__init__()

    def compose(self):
        for markup in self._markups:
            yield Static(markup)
        yield Static(f"[{self._reference_style}]{_REF_LIVE}[/]")
        yield Static(_REF_PLAIN)


class _CompositedCase(unittest.TestCase):
    """Shared assertion: target matches a live reference in the same context."""

    def assert_painted_with(self, colours, target: str, where: str) -> None:
        for key in (target, _REF_LIVE, _REF_PLAIN):
            self.assertIn(key, colours, f"{where}: {key!r} not on screen")
        self.assertNotEqual(
            colours[_REF_LIVE], colours[_REF_PLAIN],
            f"{where}: the style itself is inert — it paints the same as "
            f"unstyled text ({colours[_REF_LIVE]})",
        )
        self.assertEqual(
            colours[target], colours[_REF_LIVE],
            f"{where}: {target!r} paints {colours[target]}, but the style "
            f"resolves to {colours[_REF_LIVE]}",
        )


class MonitorStatePaintingTests(_CompositedCase):
    """monitor_shared's pure formatters, composited."""

    def _run(self, markups: list[str], reference_style: str) -> dict[str, str]:
        result: dict[str, str] = {}

        async def runner():
            app = _MarkupHost(markups, reference_style)
            async with app.run_test(size=(80, 12)) as pilot:
                await pilot.pause()
                result.update(painted(app))

        asyncio.run(runner())
        return result

    def test_the_done_badge_paints_the_done_style(self):
        snap = _snapshot(idle=True)
        colours = self._run(
            [format_pane_status(snap, True), format_state_dot(snap, True)],
            STATE_STYLE_DONE,
        )
        self.assert_painted_with(colours, "DONE 412s", "format_pane_status(completed)")

    def test_the_idle_badge_paints_the_idle_style(self):
        snap = _snapshot(idle=True)
        colours = self._run([format_pane_status(snap, False)], STATE_STYLE_IDLE)
        self.assert_painted_with(colours, "IDLE 412s", "format_pane_status(idle)")

    def test_the_prompt_badge_paints_the_prompt_style(self):
        snap = _snapshot(awaiting=True, idle=True)
        colours = self._run([format_pane_status(snap, True)], STATE_STYLE_PROMPT)
        self.assert_painted_with(colours, "PROMPT 412s", "format_pane_status(prompt)")

    def test_the_active_badge_paints_the_active_style(self):
        colours = self._run([format_pane_status(_snapshot(), False)], STATE_STYLE_ACTIVE)
        self.assert_painted_with(colours, "Active", "format_pane_status(active)")

    def test_the_done_badge_keeps_its_bold(self):
        """The dropped `bold` is half the defect signature, not a detail."""
        styles: dict[str, object] = {}

        async def runner():
            app = _MarkupHost(
                [format_pane_status(_snapshot(idle=True), True)], STATE_STYLE_DONE
            )
            async with app.run_test(size=(80, 12)) as pilot:
                await pilot.pause()
                styles.update(styles_of(app))

        asyncio.run(runner())
        self.assertTrue(styles["DONE 412s"].bold)


class MonitorHeaderPaintingTests(_CompositedCase):
    """The legend and both session bars — the three app-side DONE call sites.

    None of these boots the real app: each drives the production builder on an
    unmounted instance (the harness test_monitor_completed_status.py uses) and
    mounts the markup string it returns.
    """

    def _mount(self, markup: str, reference_style: str):
        """Returns (ordered segments, {text: colour}) for *markup*."""
        captured: dict[str, object] = {}

        async def runner():
            app = _MarkupHost([markup], reference_style)
            async with app.run_test(size=(140, 12)) as pilot:
                await pilot.pause()
                captured["pairs"] = segments(app)
                captured["colours"] = painted(app)

        asyncio.run(runner())
        return captured["pairs"], captured["colours"]

    # -- builders ----------------------------------------------------------

    def _monitor_app(self):
        from monitor.monitor_app import MonitorApp
        app = MonitorApp(session="demo", project_root=REPO_ROOT)
        app._auto_switch = False
        return app

    def _session_bar_markup(self, app_cls):
        """Drive the real bar builder with one completed agent."""
        app = app_cls(session="demo", project_root=REPO_ROOT)
        app._monitor = _FakeMonitor()
        app._task_cache = _FakeTaskCache()
        app._snapshots = {"%1": _snapshot(idle=True)}
        app._completed_pane_ids = frozenset({"%1"})
        captured: dict[str, str] = {}

        class _Bar:
            def update(self, text):
                captured["text"] = text

        app.query_one = lambda *a, **k: _Bar()
        app._auto_switch = False
        app._session = "demo"
        app._rebuild_session_bar()
        return captured["text"]

    # -- the three call sites ----------------------------------------------

    def test_the_legend_done_dot_paints_the_done_style(self):
        """monitor_app.py's legend — the *fourth* dot, not the first.

        The legend renders `● active ● prompt ● idle ● done)`, four identical
        glyphs. This locates the one preceding the word "done" by position, so
        the assertion cannot be satisfied by the `active` dot.
        """
        pairs, colours = self._mount(
            self._monitor_app()._agents_header_text(3), STATE_STYLE_DONE
        )
        done_dot = hex_of(glyph_before(pairs, "done"))
        self.assertNotEqual(
            colours[_REF_LIVE], colours[_REF_PLAIN],
            "STATE_STYLE_DONE is inert — it paints as unstyled text",
        )
        self.assertEqual(
            done_dot, colours[_REF_LIVE],
            f"the legend's done dot paints {done_dot}, but STATE_STYLE_DONE "
            f"resolves to {colours[_REF_LIVE]}",
        )

    def test_the_legend_done_dot_is_not_the_active_dot(self):
        """Proves the positional lookup discriminates.

        If glyph_before() were returning the first ● the test above would be
        reading the `active` dot, and would pass while the legend stayed inert.
        """
        pairs, _ = self._mount(
            self._monitor_app()._agents_header_text(3), STATE_STYLE_DONE
        )
        self.assertNotEqual(
            hex_of(glyph_before(pairs, "done")),
            hex_of(glyph_before(pairs, "active")),
        )

    def test_the_monitor_session_bar_done_count_paints_the_done_style(self):
        from monitor.monitor_app import MonitorApp
        markup = self._session_bar_markup(MonitorApp)
        self.assertIn("1 done", markup)
        _pairs, colours = self._mount(markup, STATE_STYLE_DONE)
        self.assert_painted_with(colours, "1 done", "monitor session bar")

    def test_the_minimonitor_session_bar_done_count_paints_the_done_style(self):
        from monitor.minimonitor_app import MiniMonitorApp
        markup = self._session_bar_markup(MiniMonitorApp)
        self.assertIn("1d", markup)
        _pairs, colours = self._mount(markup, STATE_STYLE_DONE)
        self.assert_painted_with(colours, "1d", "minimonitor session bar")


class TuiSwitcherPaintingTests(_CompositedCase):
    """The switcher's own widgets, mounted in a bare ListView.

    Mounting the real classes brings TuiSwitcherOverlay's DEFAULT_CSS along —
    which is exactly what makes the reference-control pattern necessary: inert
    runs here paint the ListView item colour, not the theme default.
    """

    def _run(self):
        colours: dict[str, str] = {}

        class Host(App):
            def compose(self):
                yield ListView(
                    ts._TuiListItem("monitor", "MONITOR", running=True,
                                    is_current=False),
                    ts._WindowListItem("shellwin", "3"),
                )
                yield Static(f"[{TUI_KEY_HINT_STYLE}]{_REF_LIVE}[/]")
                yield Static(f"[{TUI_RUNNING_STYLE}]ZZRUN[/]")
                yield Static(_REF_PLAIN)

        async def runner():
            app = Host()
            async with app.run_test(size=(80, 14)) as pilot:
                await pilot.pause()
                colours.update(painted(app))

        asyncio.run(runner())
        return colours

    def test_the_key_hint_paints_the_key_hint_style(self):
        colours = self._run()
        self.assert_painted_with(colours, "(M)", "_TuiListItem key hint")

    def test_the_running_indicator_paints_the_running_style(self):
        colours = self._run()
        self.assertNotEqual(
            colours["ZZRUN"], colours[_REF_PLAIN],
            "TUI_RUNNING_STYLE is inert — it paints the same as unstyled text",
        )
        self.assertEqual(colours["●"], colours["ZZRUN"])

    def test_the_window_name_beside_the_glyph_is_unstyled(self):
        """A zero-cost in-context control.

        _WindowListItem yields ONE Static holding both the ● and the window
        name, so these two runs share a widget and CSS context. If the glyph's
        style were inert they would paint identically.
        """
        colours = self._run()
        self.assertNotEqual(colours["●"], colours["shellwin"])

    # Deliberately NOT asserted here: that ZZRUN paints the literal string
    # `#00ff00` on screen. The composited tier compares runs against each other
    # and never against a literal — the resolved truecolor a compositor reports
    # depends on the environment (colour depth, palette quantisation), so a
    # literal makes the test pass or fail on where it runs rather than on
    # whether the style is live. The *value* is ratified in
    # RatifiedStylesTests.test_tui_running_style_is_the_ratified_value, which is
    # a pure string comparison and therefore deterministic everywhere.


class BrainstormOperationRowPaintingTests(unittest.TestCase):
    """The disabled operation row — the defect this task's own scan found."""

    def _styles(self, disabled: bool):
        styles: dict[str, object] = {}

        class Host(App):
            def compose(self):
                yield OperationRow("k", "ZZLABEL", "ZZDESC", disabled=disabled)

        async def runner():
            app = Host()
            async with app.run_test(size=(80, 8)) as pilot:
                await pilot.pause()
                styles.update(styles_of(app))

        asyncio.run(runner())
        return styles

    def test_a_disabled_row_actually_renders_struck(self):
        style = self._styles(disabled=True)["ZZLABEL"]
        self.assertTrue(
            style.strike,
            "the disabled label is not struck through — the markup is inert",
        )

    def test_an_enabled_row_is_not_struck(self):
        self.assertFalse(bool(self._styles(disabled=False)["ZZLABEL"].strike))


class CrossSurfaceAgreementTests(unittest.TestCase):
    """Every DONE surface must emit the one shared style.

    The DONE literal was previously duplicated across five call sites in three
    files, which is how one wrong colour name spread through both monitors.
    """

    def test_every_done_surface_emits_the_shared_style(self):
        from monitor.monitor_app import MonitorApp
        snap = _snapshot(idle=True)
        app = MonitorApp(session="demo", project_root=REPO_ROOT)
        app._auto_switch = False
        surfaces = {
            "format_pane_status": format_pane_status(snap, True),
            "format_state_dot": format_state_dot(snap, True),
            "monitor legend": app._agents_header_text(3),
        }
        for name, markup in surfaces.items():
            with self.subTest(surface=name):
                self.assertIn(f"[{STATE_STYLE_DONE}]", markup)


# ===========================================================================
# 3. Waiver pins — named by RICH_RENDERER_WAIVERS in test_textual_markup_colours
# ===========================================================================
class RichConsumedSitePins(unittest.TestCase):
    """Proof for the waivers granted to codebrowser/code_viewer.py.

    Those waivers claim the Rich-only names there are resolved by *Rich*, not
    Textual. The claim depends on a construction detail in a different file
    (lib/numbered_source_view.py builds a rich Table), so it is pinned here
    behaviourally rather than left as prose.
    """

    def _painted(self, build) -> dict[str, str]:
        colours: dict[str, str] = {}

        class Host(App):
            def compose(self):
                yield Static(id="target")
                yield Static(_REF_PLAIN)

            def on_mount(self) -> None:
                self.query_one("#target", Static).update(build())

        async def runner():
            app = Host()
            async with app.run_test(size=(80, 10)) as pilot:
                await pilot.pause()
                colours.update(painted(app))

        asyncio.run(runner())
        return colours

    def test_rich_table_cells_resolve_rich_only_names(self):
        """code_viewer's ANNOTATION_COLORS path: Text cells inside a Table.

        Nesting is load-bearing. The SAME Text passed to Static.update() on its
        own is resolved by Textual and comes out inert — see the contrast test
        below.
        """
        def build():
            table = RichTable(box=None, show_header=False, padding=0)
            table.add_column()
            table.add_row(RichText("ZZCELL", style="bright_cyan"))
            return table

        colours = self._painted(build)
        self.assertNotEqual(
            colours["ZZCELL"], colours[_REF_PLAIN],
            "a Rich-only name inside a rich Table no longer resolves — the "
            "code_viewer waivers in test_textual_markup_colours.py are void",
        )

    def test_rich_style_objects_resolve_rich_only_names(self):
        """code_viewer's CURSOR_STYLE / SELECTION_STYLE path: Style objects."""
        def build():
            return RichText("ZZOBJ", style=RichStyle(color="bright_green"))

        colours = self._painted(build)
        self.assertNotEqual(
            colours["ZZOBJ"], colours[_REF_PLAIN],
            "a rich.style.Style object no longer resolves its colour name — "
            "the code_viewer waivers are void",
        )

    def test_a_top_level_rich_text_string_style_does_NOT_resolve(self):
        """The contrast that makes the two waivers above narrow rather than broad.

        This is why the scan cannot decide 'is this file Rich-consumed?' per
        file: the same name in the same module is fine nested in a container and
        inert at top level.
        """
        colours = self._painted(lambda: RichText("ZZTOP", style="bright_cyan"))
        self.assertEqual(colours["ZZTOP"], colours[_REF_PLAIN])


if __name__ == "__main__":
    unittest.main(verbosity=2)
