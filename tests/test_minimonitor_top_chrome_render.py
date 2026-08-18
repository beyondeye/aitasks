"""Minimonitor's top chrome must actually reach the screen (t1499, t1566).

Four widgets — ``#mini-session-bar``, ``#mini-own-agent``, ``#mini-shadow-stale``
and ``#mini-loop-status`` — all carried ``dock: top``.
Textual places same-edge docked siblings at the SAME offset instead of stacking
them, so all four were assigned ``Region(0, 0, 40, 1)`` and only the last in DOM
order was composited. The other three never rendered in any state, while each
still reported ``display=True``, ``visible=True`` and a plausible region.

t1566 then reordered them (the followed agent leads; the advisory banners flow
below it), replaced the own panel's guessed ``max-height: 4`` with the derived
``_OWN_PANEL_MAX_ROWS``, made the banners one and two rows, and shipped the
session bar hidden. The budget those changes are accountable to is the pane
list's floor: **advisory chrome yields before the list loses its last row** —
see ``PaneListFloorTests``.

That is why every assertion here is on **rendered geometry and composited
text**. The DOM-free seams (``_shadow_stale_banner_text`` /
``_loop_banner_text``), ``widget.display``, ``widget.visible`` and a lone
``region`` all stayed green through the entire life of the defect — asserting
on them is exactly what let it ship. Same bug class and same guard idiom as the
board's ``#filter_area`` (t1278, ``tests/test_board_bytrail_view._screen_rows``).

Chrome is driven through the **production** code paths, never mounted by hand:
the panel comes from the real ``_maybe_build_own_agent_panel`` (which owns the
``panel.display = True`` line this guard exists to protect) and the banners go
through the real setters, carrying real ``format_shadow_stale_banner`` output.
"""

import asyncio
import os
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts"))
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts" / "monitor")
)

import minimonitor_app as mm  # noqa: E402
import monitor_core as mc  # noqa: E402
import monitor_shared as ms  # noqa: E402
from textual.widgets import Static  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

#: DOM order of the flowed top chrome, top to bottom. The pane list and the
#: docked hints follow it.
CHROME_IDS = list(mm._TOP_CHROME)

#: Single-spaced on purpose: `_flatten` collapses whitespace runs, so a
#: probe carrying a double space could never match the flattened frame.
SESSION_TEXT = "probe-session 7 agents 2 awaiting"

#: From the production formatter rather than a marker literal, and through the
#: `narrow=True` arm the minimonitor's two call sites actually use (t1566) — so
#: a wording change that no longer fits one row fails here.
_NOW = 1_000_000.0
STALE_TEXT = ms.format_shadow_stale_banner(
    True,
    mc.BlockAge(True, True, _NOW - 7500, _NOW - 100),
    SimpleNamespace(round=12),
    _NOW - 93.0,
    _NOW,
    narrow=True,
)
#: Longest of the four literals `_set_loop_banner` is ever called with,
#: glyph included (U+27F3, not the similar-looking U+21BB). 39 cells — the one
#: that needs a second row at 40 columns, which is what sizes the 2-row cap.
LOOP_TEXT = "⟳ recheck #12 sent — waiting for shadow"

#: The height both short-mode directions are probed at. Chosen so ONE variable
#: — whether the banners are live — flips the outcome. Re-derived for t1566's
#: budget, which is 3 rows tighter than t1499's (the session bar is hidden by
#: default and the banners now cap at 1 + 2): with the banners the chrome
#: occupies 6 rows (6 + 10 hint rows + a 3-row list floor > 18, so the hints
#: yield); without them it occupies 3 (3 + 10 + 3 <= 18, so they do not).
#: 20 no longer discriminates — BOTH cases stay off there — which is exactly
#: the way a stale probe height turns a pair of tests into a tautology.
SHORT_PROBE_HEIGHT = 18

STALE_PROBE = "shadow feedback is stale"
#: Kept inside the panel's 36-column name budget (see
#: test_minimonitor_own_mark.CompositedWidthTests) — a longer name is
#: truncated on screen and the probe could never match.
OWN_WINDOW = "agent-t1499-chrome"

#: Vertical-scrollbar glyphs Textual paints in a `VerticalScroll`'s last column
#: (U+2581-U+2588). Asserting on the composited glyph rather than on
#: `show_vertical_scrollbar` is the whole point: the DOM property was TRUE
#: throughout the t1499 defect while the screen said nothing.
SCROLLBAR_GLYPHS = "▁▂▃▄▅▆▇█"

#: A task title long enough to need the panel's full two wrapped rows at 40
#: columns, so the "renders every row" case exercises the real worst case.
OWN_TITLE = "chrome order own panel height and the session bar default visibility"
OWN_PHASE = "implement 2/4"
#: Longer than any plausible tmux window name. Folds the identity block to its
#: full height, which is what makes the panel reach `_OWN_PANEL_MAX_ROWS` — the
#: worst case the floor sweep must be measured against.
OWN_WINDOW_PATHOLOGICAL = "agent-" + "x" * 120


def _own_snapshot(window: str = OWN_WINDOW):
    """A followed-window snapshot `_maybe_build_own_agent_panel` accepts."""
    pane = SimpleNamespace(
        category=mm.PaneCategory.AGENT,
        session_name="probe-session",
        window_index="1",
        pane_index="0",
        pane_id="%9",
        window_name=window,
    )
    return SimpleNamespace(pane=pane, is_idle=False, idle_seconds=0.0)


class _TitleCache:
    """Minimal `TaskInfoCache` stand-in that yields a wrapping task title.

    The fixture's default own panel carries no task, so it renders 3 rows and
    could never show the clipping this module now guards. Cases that care about
    the panel's real height install this instead.
    """

    def get_task_id_for_pane(self, pane):
        return "9999"

    def get_task_info(self, task_id, session_name):
        return SimpleNamespace(title=OWN_TITLE)


def _flatten(app) -> str:
    """The composited frame with wrapping folded out.

    Every string this module asserts on wraps at 38 usable columns, so a
    per-row ``in`` check silently never matches. Joining the rows and
    collapsing runs of whitespace is what makes a wrapped phrase assertable —
    the same problem `_dialog_text` solves for centred modals (t1366).
    """
    rows = [
        strip.text
        for strip in app.screen._compositor.render_strips(app.screen.size)
    ]
    return re.sub(r"\s+", " ", " ".join(rows))


def _rows(app) -> list[str]:
    return [
        strip.text
        for strip in app.screen._compositor.render_strips(app.screen.size)
    ]


class _ChromeFixture(unittest.TestCase):
    """Boots the real ``MiniMonitorApp`` with no tmux around it.

    With ``TMUX`` unset, ``on_mount`` writes the "Not inside tmux" bar and
    returns **before** ``_start_monitoring()`` — a real-app boot with no tmux
    I/O, no refresh timer and no in-flight ``@work`` worker at block exit (the
    t1487 teardown hazard).
    """

    def setUp(self):
        self._saved_env = {
            k: os.environ.pop(k, None) for k in ("TMUX", "TMUX_PANE")
        }

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is not None:
                os.environ[key] = value

    def _app(self, width=40):
        return mm.MiniMonitorApp(
            session="probe-session",
            project_root=REPO_ROOT,
            refresh_seconds=999,
            target_width=width,
        )

    async def _populate(self, app, pilot, *, banners=True, own=True,
                        session=True, window=OWN_WINDOW):
        """Drive chrome through the production write sites only.

        ``own`` is tri-state: ``False`` builds no panel, ``True`` builds the
        fixture's minimal one (no task ⇒ 3 rows), and ``"full"`` installs
        `_TitleCache` and a phase so the panel renders every row it ever can.

        ``session`` is tri-state too, because the bar now ships
        ``display: none`` and a raw ``update()`` can no longer reveal it
        (t1566):

        * ``True``  — enabled, revealed through the real `_rebuild_session_bar`;
        * ``False`` — the production in-tmux default: `_rebuild_session_bar`
          runs with the flag off and HIDES the bar, undoing the reveal
          `on_mount` performed for its "Not inside tmux" error;
        * ``None``  — leave `on_mount`'s state alone (only the not-inside-tmux
          case wants that).
        """
        if own:
            if own == "full":
                app._task_cache = _TitleCache()
                app._own_phase_text = lambda snap: OWN_PHASE
            app._find_own_window_snapshot = lambda: _own_snapshot(window)
            app._is_marked = lambda snap: True
            await app._maybe_build_own_agent_panel()
        if session is not None:
            # The real reveal/hide site, not a raw `display` poke — this is what
            # the config key ultimately drives.
            app._session_bar_enabled = bool(session)
            app._snapshots = {}
            app._completed_pane_ids = frozenset()
            app._rebuild_session_bar()
            if session:
                # Production supplies its own counter text; pin a stable probe
                # over it so the assertion does not track the formatter.
                app.query_one("#mini-session-bar", Static).update(SESSION_TEXT)
        if banners:
            app._set_shadow_stale_banner(STALE_TEXT)
            app._set_loop_banner(LOOP_TEXT)
        await pilot.pause()

    def _run(self, size, *, banners=True, own=True, session=True, after=None,
             window=OWN_WINDOW):
        """Boot, populate, and hand the live app to ``after``."""
        result = {}

        async def runner():
            app = self._app(width=size[0])
            async with app.run_test(size=size) as pilot:
                await self._populate(app, pilot, banners=banners, own=own,
                                     session=session, window=window)
                result["regions"] = {
                    sel: app.query_one(sel).region
                    for sel in CHROME_IDS + ["#mini-pane-list", "#mini-key-hints"]
                }
                result["flat"] = _flatten(app)
                result["rows"] = _rows(app)
                result["short"] = "short" in app.classes
                if after is not None:
                    await after(app, pilot, result)

        asyncio.run(runner())
        return result

    def _scrollbar_in(self, result, sel="#mini-own-agent"):
        """True if a scrollbar glyph is composited inside ``sel``'s region."""
        region = result["regions"][sel]
        band = result["rows"][region.y:region.y + region.height]
        return any(ch in SCROLLBAR_GLYPHS for row in band for ch in row)


class TopChromeGeometryTests(_ChromeFixture):
    def test_top_chrome_widgets_do_not_share_a_region(self):
        r = self._run((40, 30))["regions"]
        # Every one of the four is checked — never filtered to "the visible
        # ones", or the test would degenerate to a tautology the moment one of
        # them is hidden, which is the very failure being guarded.
        self.assertEqual(len(CHROME_IDS), 4)
        ordered = [(sel, r[sel]) for sel in CHROME_IDS]
        for (earlier_id, earlier), (later_id, later) in zip(
            ordered, ordered[1:]
        ):
            self.assertLessEqual(
                earlier.y + earlier.height, later.y,
                f"{earlier_id} {earlier} overlaps {later_id} {later} — "
                "same-edge docked siblings again (t1499)",
            )
        last_id, last = ordered[-1]
        self.assertLessEqual(
            last.y + last.height, r["#mini-pane-list"].y,
            f"{last_id} {last} overlaps the pane list",
        )

    def test_chrome_text_reaches_the_composited_frame(self):
        flat = self._run((40, 30))["flat"]
        for label, probe in (
            ("session bar", SESSION_TEXT),
            ("staleness banner", STALE_PROBE),
            ("loop banner", "recheck #12 sent"),
            ("own-agent panel", OWN_WINDOW),
        ):
            self.assertIn(
                probe, flat, f"{label} never reached the screen: {flat!r}"
            )

    def test_the_gated_banner_gives_its_row_back(self):
        """t1573's AC4, on the composited frame rather than on the seam.

        The banner is first driven live (rows > 0, text on screen), then the
        **production gate** is driven with a block-free capture — the
        `agent-pick-1566` case, an explain-only shadow with nothing to be stale
        about. `#mini-shadow-stale` must go back to occupying zero rows.

        Distinct from `test_empty_chrome_costs_no_rows`, which only covers a
        banner that was NEVER set: the row is reclaimed by
        `_set_shadow_stale_banner`'s `display` toggle, and a suppression that
        cleared the text without turning the widget off would keep its row
        forever while every seam assertion stayed green (t1499's bug class).
        """
        async def after(app, pilot, result):
            live = app.query_one("#mini-shadow-stale").region
            self.assertGreaterEqual(
                live.height, 1, "precondition: the banner must be on screen"
            )
            self.assertIn(STALE_PROBE, _flatten(app))
            # The real per-tick write site, with a capture carrying no block.
            app._refresh_shadow_stale_banner(
                _own_snapshot(), "%99", "just agent prose\n$ "
            )
            await pilot.pause()
            gated = app.query_one("#mini-shadow-stale").region
            self.assertEqual(
                gated.height, 0,
                f"#mini-shadow-stale kept rows while carrying no warning: "
                f"{gated}",
            )
            self.assertNotIn(STALE_PROBE, _flatten(app))
            self.assertEqual(app._shadow_stale_banner_text, "")

        self._run((40, 30), after=after)

    def test_own_agent_panel_is_visible_and_flows_above_the_banners(self):
        """Fails if `panel.display = True` is ever dropped.

        Without this the whole module would pass with the followed-agent panel
        permanently hidden: the geometry test's pairs still order correctly
        around a zero-height widget, and no other assertion names its text.

        The ordering assertion INVERTED at t1566: the followed agent is this
        pane's primary identity surface, so it now leads and the two advisory
        banners flow below it.
        """
        out = self._run((40, 30))
        panel = out["regions"]["#mini-own-agent"]
        self.assertGreaterEqual(
            panel.height, 1, "#mini-own-agent composited zero rows"
        )
        for banner in ("#mini-shadow-stale", "#mini-loop-status"):
            self.assertLess(
                panel.y, out["regions"][banner].y,
                f"#mini-own-agent did not flow above {banner} — the followed "
                "agent must lead the chrome (t1566)",
            )
        self.assertIn(OWN_WINDOW, out["flat"])

    def test_not_inside_tmux_error_is_visible(self):
        """The on_mount error a user launching outside tmux must see.

        ``session=None`` leaves `on_mount`'s state untouched on purpose: the bar
        ships hidden, and this error is the one thing that reveals it without
        the config key. Passing ``session=False`` here would hide the bar again
        through `_rebuild_session_bar` and the error would vanish — which is
        exactly the regression this guards.
        """
        out = self._run((40, 30), banners=False, own=False, session=None)
        self.assertIn("Not inside tmux", out["flat"])
        self.assertGreaterEqual(
            out["regions"]["#mini-session-bar"].height, 1,
            "the not-inside-tmux error composited zero rows",
        )

    def test_empty_chrome_costs_no_rows(self):
        """Steady state costs the pane list nothing at all.

        The session bar joined the collapsible set at t1566, so the one row it
        used to own unconditionally is now the pane list's: with nothing to say,
        all FOUR chrome widgets are zero and the list starts at y=0.
        """
        out = self._run((40, 30), banners=False, own=False, session=False)
        r = out["regions"]
        for sel in CHROME_IDS:
            self.assertEqual(
                r[sel].height, 0, f"{sel} cost rows while empty: {r[sel]}"
            )
        self.assertEqual((r["#mini-pane-list"].y, r["#mini-pane-list"].height),
                         (0, 20))
        self.assertEqual(r["#mini-key-hints"].y, 20)

    def test_pane_list_keeps_a_row_at_every_pane_height(self):
        """The floor: the list never vanishes and never runs into the hints.

        Before short mode this bottomed out at 12 rows (1 session bar + 1 list
        row + 10 hint rows) and the list hit zero at 11. With the hints
        yielding it degrades all the way down, so the contract is stated as an
        invariant over the whole range rather than as a single magic height.
        """
        for height in (30, 20, 14, 13, 12, 8, 5, 4):
            with self.subTest(height=height):
                r = self._run((40, height), banners=False, own=False,
                              session=False)["regions"]
                lst, hints = r["#mini-pane-list"], r["#mini-key-hints"]
                self.assertGreaterEqual(
                    lst.height, 1, f"pane list vanished at height {height}"
                )
                self.assertLessEqual(
                    lst.y + lst.height, hints.y,
                    f"pane list {lst} ran into the hints {hints} at "
                    f"height {height}",
                )


class LiveChromeOverrunTests(_ChromeFixture):
    """Worst-case chrome must never overrun the bottom-docked hints."""

    def test_live_chrome_never_overruns_the_docked_key_hints(self):
        for size in ((40, 30), (40, 24), (40, 20), (40, 16)):
            with self.subTest(size=size):
                out = self._run(size)
                r = out["regions"]
                lst, hints = r["#mini-pane-list"], r["#mini-key-hints"]
                self.assertLessEqual(
                    lst.y + lst.height, hints.y,
                    f"pane list {lst} ran into the docked hints {hints} — "
                    "the agent list is painted off the screen (t1499)",
                )
                self.assertGreaterEqual(lst.height, 1, f"pane list {lst}")
                for probe in (SESSION_TEXT, STALE_PROBE, "recheck #12 sent",
                              OWN_WINDOW):
                    self.assertIn(probe, out["flat"], f"missing at {size}")


class ShortModeTests(_ChromeFixture):
    """Both directions of the hint-compaction toggle, own panel always built."""

    def test_short_mode_engages_with_live_banners(self):
        out = self._run((40, SHORT_PROBE_HEIGHT), session=False)
        self.assertTrue(out["short"], "short mode did not engage")
        self.assertEqual(
            out["regions"]["#mini-key-hints"].height, mm._SHORT_HINT_ROWS
        )

    def test_short_mode_stays_off_for_the_own_panel_alone(self):
        """The discriminating cell.

        A predicate keyed on "is any collapsible widget displayed?" gets this
        wrong: the panel is built once and stays displayed for the rest of the
        session, so this pane would lose eight hint lines for nothing — at the
        very same height where live banners legitimately do compact them.
        """
        out = self._run((40, SHORT_PROBE_HEIGHT), banners=False,
                        session=False)
        self.assertGreaterEqual(out["regions"]["#mini-own-agent"].height, 1)
        self.assertFalse(
            out["short"],
            "short mode engaged with only the own panel live — the predicate "
            "is using a worst-case budget instead of occupied height",
        )
        self.assertEqual(
            out["regions"]["#mini-key-hints"].height, mm._KEY_HINTS_ROWS
        )

    def test_short_mode_releases_when_the_banners_clear(self):
        """Driven in ONE app instance: a class stuck on would pass otherwise."""
        seen = {}

        async def after(app, pilot, result):
            seen["engaged"] = "short" in app.classes
            app._set_shadow_stale_banner("")
            app._set_loop_banner("")
            await pilot.pause()
            await pilot.pause()
            seen["released"] = "short" not in app.classes
            seen["hints"] = app.query_one("#mini-key-hints").region.height

        self._run((40, SHORT_PROBE_HEIGHT), session=False, after=after)
        self.assertTrue(seen["engaged"], "short mode never engaged")
        self.assertTrue(seen["released"], "short mode stuck on after clearing")
        self.assertEqual(seen["hints"], mm._KEY_HINTS_ROWS)

    def test_short_mode_predicate_converges(self):
        """No oscillation — the class must not feed back into its own input."""
        passes = []

        async def after(app, pilot, result):
            for _ in range(3):
                app._refresh_short_mode()
                await pilot.pause()
                passes.append((
                    "short" in app.classes,
                    sum(app.query_one(s).region.height for s in CHROME_IDS),
                ))

        self._run((40, SHORT_PROBE_HEIGHT), session=False, after=after)
        self.assertEqual(len(set(passes)), 1, f"predicate oscillated: {passes}")


class KeyHintsBudgetTests(_ChromeFixture):
    def test_key_hints_occupy_one_row_per_line(self):
        """Pins the derived `_KEY_HINTS_ROWS` against the rendered height.

        The short-mode threshold is computed from this constant, so a future
        hint line long enough to wrap at 40 columns must fail here rather than
        silently shifting the point at which the hints compact.
        """
        out = self._run((40, 30), banners=False, own=False, session=False)
        self.assertEqual(
            out["regions"]["#mini-key-hints"].height, mm._KEY_HINTS_ROWS,
            "a hint line wraps at 40 columns — _KEY_HINTS_ROWS no longer "
            "describes the rendered height",
        )


class CollapseToggleContractTests(_ChromeFixture):
    """Both directions of the display toggle the collapse contract rests on."""

    def test_collapsible_chrome_returns_to_zero_rows_when_cleared(self):
        seen = {}

        collapsible = ("#mini-session-bar", "#mini-shadow-stale",
                       "#mini-loop-status")

        async def after(app, pilot, result):
            seen["set"] = {
                sel: app.query_one(sel).region.height for sel in collapsible
            }
            seen["set_flat"] = _flatten(app)
            app._set_shadow_stale_banner("")
            app._set_loop_banner("")
            # The bar's "clear" is the config flag going off, applied by the
            # same production site that turned it on.
            app._session_bar_enabled = False
            app._rebuild_session_bar()
            await pilot.pause()
            seen["cleared"] = {
                sel: app.query_one(sel).region.height for sel in collapsible
            }
            seen["cleared_flat"] = _flatten(app)

        self._run((40, 30), after=after)
        for sel, height in seen["set"].items():
            self.assertGreaterEqual(height, 1, f"{sel} never took a row")
        self.assertIn(STALE_PROBE, seen["set_flat"])
        self.assertIn("recheck #12 sent", seen["set_flat"])
        self.assertIn(SESSION_TEXT, seen["set_flat"])

        for sel, height in seen["cleared"].items():
            self.assertEqual(
                height, 0, f"{sel} kept rows after its text was cleared"
            )
        self.assertNotIn(STALE_PROBE, seen["cleared_flat"])
        self.assertNotIn("recheck #12 sent", seen["cleared_flat"])
        self.assertNotIn(SESSION_TEXT, seen["cleared_flat"])


class OwnPanelSizingTests(_ChromeFixture):
    """The followed-agent panel must show its data, not a scrollbar (t1566).

    ``max-height: 4`` was smaller than the panel's real content, so the second
    wrapped title row and the advisory phase line were dropped in favour of a
    scrollbar thumb. The cap is now ``_OWN_PANEL_MAX_ROWS``, derived row-by-row,
    and the content is pre-wrapped so that derivation holds at every pane width.
    """

    def test_own_agent_panel_renders_every_row_without_a_scrollbar(self):
        """The defect, stated as its symptom: all rows on screen, no thumb.

        Fails on the pre-t1566 build — under ``max-height: 4`` the panel
        composites 4 rows and the title's second line and the phase line never
        reach the frame.
        """
        out = self._run((40, 30), own="full")
        panel = out["regions"]["#mini-own-agent"]
        flat = out["flat"]

        self.assertFalse(
            self._scrollbar_in(out),
            f"#mini-own-agent painted a scrollbar instead of its data: "
            f"{out['rows'][panel.y:panel.y + panel.height]!r}",
        )
        # Every row the panel can carry, named individually — a bare height
        # check would pass on a panel that is tall but clipped mid-content.
        self.assertIn("this agent", flat, "the header row is missing")
        self.assertIn(OWN_WINDOW, flat, "the identity row is missing")
        self.assertIn(OWN_PHASE, flat, "the advisory phase row is missing")
        for fragment in OWN_TITLE.split():
            self.assertIn(
                fragment, flat,
                f"task title word {fragment!r} never reached the screen — the "
                "title is still being clipped",
            )

    def test_the_scrollbar_detector_can_actually_fire(self):
        """POSITIVE CONTROL for every ``assertFalse(scrollbar)`` above.

        Those assertions hold *structurally* — the panel carries
        ``overflow-y: hidden``, so it can never paint a thumb. That makes them
        regression guards on the stylesheet rather than observations, and it
        makes this control mandatory: without it, a `SCROLLBAR_GLYPHS` set that
        no longer matched what Textual paints would leave them passing
        vacuously and nobody would know.

        Restore ``auto`` and shrink the cap under the content — the same probe
        must then find a glyph.
        """
        seen = {}

        async def after(app, pilot, result):
            panel = app.query_one("#mini-own-agent")
            panel.styles.overflow_y = "auto"
            panel.styles.max_height = 4
            await pilot.pause()
            await pilot.pause()
            region = panel.region
            rows = _rows(app)[region.y:region.y + region.height]
            seen["glyph"] = any(
                ch in SCROLLBAR_GLYPHS for row in rows for ch in row
            )
            seen["rows"] = rows

        self._run((40, 30), own="full", after=after)
        self.assertTrue(
            seen["glyph"],
            "the scrollbar detector never fired on a panel deliberately given "
            f"back `overflow-y: auto` and a cap under its content — "
            f"{SCROLLBAR_GLYPHS!r} no longer describes what Textual paints, so "
            f"the no-scrollbar assertions prove nothing. Rows: {seen['rows']!r}",
        )

    def test_the_panel_never_offers_a_scrollbar_it_cannot_honour(self):
        """`overflow-y: hidden` is a decision, so pin it as one.

        The panel mounts plain Statics and sits outside the focus ring, so a
        thumb would advertise rows the user has no way to reach — and letting it
        reserve columns re-wraps the name into a taller panel that then keeps
        the thumb (measured at 22 columns). Both reasons are in the stylesheet;
        this is what fails if someone restores `auto`.
        """
        seen = {}

        async def after(app, pilot, result):
            seen["overflow_y"] = app.query_one("#mini-own-agent").styles.overflow_y

        self._run((40, 30), own="full", after=after)
        self.assertEqual(seen["overflow_y"], "hidden")

    def test_own_panel_holds_its_cap_at_every_pane_width(self):
        """The row budget must not be an artifact of 40 columns.

        Before t1566 the window name was handed to Rich unwrapped, so it folded
        over as many rows as the width demanded and the panel's worst case grew
        as the pane narrowed. Both blocks are pre-wrapped to two lines now, so
        the same cap holds all the way down.
        """
        for width in (40, 30, 26, 22):
            for window in (OWN_WINDOW, OWN_WINDOW_PATHOLOGICAL):
                with self.subTest(width=width, name=len(window)):
                    out = self._run((width, 30), own="full", window=window)
                    panel = out["regions"]["#mini-own-agent"]
                    self.assertGreaterEqual(panel.height, 1)
                    self.assertLessEqual(
                        panel.height, mm._OWN_PANEL_MAX_ROWS,
                        f"panel overran its cap at width {width}: {panel}",
                    )
                    self.assertFalse(
                        self._scrollbar_in(out),
                        f"panel scrolled at width {width} with a "
                        f"{len(window)}-char window name",
                    )

    def test_the_cap_is_applied_at_the_reveal_site(self):
        """`panel.styles.max_height` is load-bearing, so prove it is set.

        The cap lives in Python rather than the stylesheet (so the number sits
        beside its derivation), which means nothing in the CSS would fail if the
        line were dropped — the panel would simply grow unbounded and push the
        pane list off the screen. Read the resolved style back after the real
        `_maybe_build_own_agent_panel` ran.
        """
        seen = {}

        async def after(app, pilot, result):
            seen["max_height"] = app.query_one("#mini-own-agent").styles.max_height

        self._run((40, 30), own="full", after=after)
        self.assertIsNotNone(
            seen["max_height"],
            "#mini-own-agent has no max-height — _maybe_build_own_agent_panel "
            "no longer applies _OWN_PANEL_MAX_ROWS and the chrome is unbounded",
        )
        self.assertEqual(seen["max_height"].value, mm._OWN_PANEL_MAX_ROWS)


class PaneListFloorTests(_ChromeFixture):
    """The budget every cap in this module is accountable to (t1566).

    The rule the caps exist to serve: **advisory chrome yields before the pane
    list loses its last row.** Growing the own panel is only safe because the
    banners were capped to one and two rows in the same change, and this is
    where that trade is proven rather than asserted in prose.
    """

    #: Lowest pane height at which the list still keeps a row, in the WORST
    #: configuration: session bar enabled, own panel at its full cap (a folding
    #: window name), and both banners live.
    #:
    #:     chrome = _MAX_CHROME_ROWS                  = 11
    #:     hints  = _SHORT_HINT_ROWS                  =  2
    #:                                                  --
    #:                                                  13  -> 1 row left at 14
    #:
    #: Derived, never a second literal — a raised cap moves this automatically
    #: and the sweep re-probes the new boundary. Below it there is nothing left
    #: to give without a third layout tier.
    FLOOR_HEIGHT = mm._MAX_CHROME_ROWS + mm._SHORT_HINT_ROWS + 1

    def test_pane_list_keeps_a_row_under_full_live_chrome(self):
        """Full chrome at every height down to the floor.

        ``window=OWN_WINDOW_PATHOLOGICAL`` is what makes this the worst case
        rather than the typical one: a name that folds pushes the panel to its
        full ``_OWN_PANEL_MAX_ROWS``, where a name that fits leaves it a row
        short and the sweep would under-report the chrome by one.
        """
        for height in (30, 20, 16, 15, self.FLOOR_HEIGHT):
            with self.subTest(height=height):
                out = self._run((40, height), own="full",
                                window=OWN_WINDOW_PATHOLOGICAL)
                r = out["regions"]
                lst, hints = r["#mini-pane-list"], r["#mini-key-hints"]
                self.assertGreaterEqual(
                    lst.height, 1,
                    f"the pane list vanished at height {height} under full "
                    "chrome — advisory chrome must yield first",
                )
                self.assertLessEqual(
                    lst.y + lst.height, hints.y,
                    f"pane list {lst} ran into the docked hints {hints} at "
                    f"height {height}",
                )

    def test_worst_case_chrome_fits_the_documented_ceiling(self):
        """Pins the ceiling the floor above was computed from.

        A cap raised without raising ``_MAX_CHROME_ROWS`` fails here, at review,
        instead of silently costing the pane list its last row on somebody's
        short pane.
        """
        self.assertEqual(
            mm._MAX_CHROME_ROWS,
            mm._SESSION_BAR_ROWS + mm._OWN_PANEL_MAX_ROWS
            + mm._SHADOW_STALE_ROWS + mm._LOOP_STATUS_ROWS,
        )
        # And the ceiling must describe the SCREEN, not just the arithmetic: in
        # the worst configuration the four widgets really do occupy it. A
        # constant that drifted above what the widgets can render would inflate
        # FLOOR_HEIGHT and quietly stop the sweep probing the real boundary.
        r = self._run((40, 30), own="full",
                      window=OWN_WINDOW_PATHOLOGICAL)["regions"]
        self.assertEqual(
            sum(r[sel].height for sel in CHROME_IDS), mm._MAX_CHROME_ROWS,
            "worst-case chrome does not occupy _MAX_CHROME_ROWS on screen — "
            "the ceiling and the widgets disagree",
        )

    def test_the_floor_is_the_real_boundary(self):
        """NEGATIVE CONTROL: one row below FLOOR_HEIGHT the list is gone.

        Without this, FLOOR_HEIGHT could drift far below the true boundary and
        the sweep above would still pass while claiming a bound it never tested.
        """
        r = self._run((40, self.FLOOR_HEIGHT - 1), own="full",
                      window=OWN_WINDOW_PATHOLOGICAL)["regions"]
        lst, hints = r["#mini-pane-list"], r["#mini-key-hints"]
        self.assertGreater(
            lst.y + lst.height, hints.y,
            f"the pane list still fits at height {self.FLOOR_HEIGHT - 1} — "
            "FLOOR_HEIGHT is too conservative and the sweep is not probing the "
            "real boundary",
        )


class BannerRowBudgetTests(_ChromeFixture):
    """Each advisory banner must fit the rows its cap allows (t1566)."""

    def test_shadow_stale_banner_occupies_exactly_one_row(self):
        """One row AND uncut — the cap is sized to the text, not clipping it."""
        out = self._run((40, 30))
        self.assertEqual(
            out["regions"]["#mini-shadow-stale"].height, 1,
            "the staleness banner is no longer a one-row surface",
        )
        # The narrow wording, whole. A cap that clipped would still measure 1.
        plain = re.sub(r"\[/?[^]]*\]", "", STALE_TEXT)
        self.assertIn(
            re.sub(r"\s+", " ", plain).strip(), out["flat"],
            "the one-row cap is CLIPPING the banner rather than fitting it — "
            "the narrow wording grew past 38 cells",
        )

    def test_loop_banner_longest_literal_fits_two_rows(self):
        """The 39-cell literal is what sizes the 2-row cap — pin it there.

        Asserted against the real string `_set_loop_banner` is called with, not
        a replica, so a reworded banner that needs a third row fails here.
        """
        out = self._run((40, 30))
        self.assertLessEqual(
            out["regions"]["#mini-loop-status"].height, mm._LOOP_STATUS_ROWS
        )
        self.assertIn("recheck #12 sent", out["flat"])
        self.assertIn("waiting for shadow", out["flat"])


if __name__ == "__main__":
    unittest.main()
