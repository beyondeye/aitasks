"""Minimonitor's top chrome must actually reach the screen (t1499).

Four widgets — ``#mini-session-bar``, ``#mini-shadow-stale``,
``#mini-loop-status`` and ``#mini-own-agent`` — all carried ``dock: top``.
Textual places same-edge docked siblings at the SAME offset instead of stacking
them, so all four were assigned ``Region(0, 0, 40, 1)`` and only the last in DOM
order was composited. The other three never rendered in any state, while each
still reported ``display=True``, ``visible=True`` and a plausible region.

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

#: The real worst case, from the production formatter rather than a short
#: marker literal — it is the branch that wraps to three rows at 40 columns.
_NOW = 1_000_000.0
STALE_TEXT = ms.format_shadow_stale_banner(
    True,
    mc.BlockAge(True, True, _NOW - 7500, _NOW - 100),
    SimpleNamespace(round=12),
    _NOW - 93.0,
    _NOW,
)
#: Longest of the four literals `_set_loop_banner` is ever called with.
LOOP_TEXT = "↻ recheck #12 sent — waiting for shadow"

#: The height both short-mode directions are probed at. Chosen so ONE variable
#: — whether the banners are live — flips the outcome: with them the chrome
#: occupies 9 rows (9 + 10 hint rows + a 3-row list floor > 20, so the hints
#: yield); without them it occupies 4 (4 + 10 + 3 <= 20, so they do not). A
#: height where both cases agree would make the pair non-discriminating.
SHORT_PROBE_HEIGHT = 20

STALE_PROBE = "shadow feedback is stale"
#: Kept inside the panel's 36-column name budget (see
#: test_minimonitor_own_mark.CompositedWidthTests) — a longer name is
#: truncated on screen and the probe could never match.
OWN_WINDOW = "agent-t1499-chrome"


def _own_snapshot():
    """A followed-window snapshot `_maybe_build_own_agent_panel` accepts."""
    pane = SimpleNamespace(
        category=mm.PaneCategory.AGENT,
        session_name="probe-session",
        window_index="1",
        pane_index="0",
        pane_id="%9",
        window_name=OWN_WINDOW,
    )
    return SimpleNamespace(pane=pane, is_idle=False, idle_seconds=0.0)


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

    def _app(self):
        return mm.MiniMonitorApp(
            session="probe-session",
            project_root=REPO_ROOT,
            refresh_seconds=999,
        )

    async def _populate(self, app, pilot, *, banners=True, own=True,
                        session=True):
        """Drive chrome through the production write sites only."""
        if own:
            app._find_own_window_snapshot = lambda: _own_snapshot()
            app._is_marked = lambda snap: True
            await app._maybe_build_own_agent_panel()
        if session:
            app.query_one("#mini-session-bar", Static).update(SESSION_TEXT)
        if banners:
            app._set_shadow_stale_banner(STALE_TEXT)
            app._set_loop_banner(LOOP_TEXT)
        await pilot.pause()

    def _run(self, size, *, banners=True, own=True, session=True, after=None):
        """Boot, populate, and hand the live app to ``after``."""
        result = {}

        async def runner():
            app = self._app()
            async with app.run_test(size=size) as pilot:
                await self._populate(app, pilot, banners=banners, own=own,
                                     session=session)
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

    def test_own_agent_panel_is_visible_and_flows_below_the_banners(self):
        """Fails if `panel.display = True` is ever dropped.

        Without this the whole module would pass with the followed-agent panel
        permanently hidden: the geometry test's pairs still order correctly
        around a zero-height widget, and no other assertion names its text.
        """
        out = self._run((40, 30))
        panel = out["regions"]["#mini-own-agent"]
        self.assertGreaterEqual(
            panel.height, 1, "#mini-own-agent composited zero rows"
        )
        self.assertGreater(
            panel.y, out["regions"]["#mini-loop-status"].y,
            "#mini-own-agent did not flow below the loop banner",
        )
        self.assertIn(OWN_WINDOW, out["flat"])

    def test_not_inside_tmux_error_is_visible(self):
        """The on_mount error a user launching outside tmux must see."""
        out = self._run((40, 30), banners=False, own=False, session=False)
        self.assertIn("Not inside tmux", out["flat"])

    def test_empty_chrome_costs_no_rows(self):
        """Steady state is byte-identical to the pre-fix row budget.

        Before t1499 the collapsed dock group occupied exactly the one row the
        session bar now owns, so restoring three dead surfaces costs the pane
        list nothing until they have something to say.
        """
        out = self._run((40, 30), banners=False, own=False)
        r = out["regions"]
        for sel in ("#mini-shadow-stale", "#mini-loop-status", "#mini-own-agent"):
            self.assertEqual(
                r[sel].height, 0, f"{sel} cost rows while empty: {r[sel]}"
            )
        self.assertEqual((r["#mini-pane-list"].y, r["#mini-pane-list"].height),
                         (1, 19))
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
                r = self._run((40, height), banners=False, own=False)["regions"]
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
        out = self._run((40, SHORT_PROBE_HEIGHT))
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
        out = self._run((40, SHORT_PROBE_HEIGHT), banners=False)
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

        self._run((40, SHORT_PROBE_HEIGHT), after=after)
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

        self._run((40, SHORT_PROBE_HEIGHT), after=after)
        self.assertEqual(len(set(passes)), 1, f"predicate oscillated: {passes}")


class KeyHintsBudgetTests(_ChromeFixture):
    def test_key_hints_occupy_one_row_per_line(self):
        """Pins the derived `_KEY_HINTS_ROWS` against the rendered height.

        The short-mode threshold is computed from this constant, so a future
        hint line long enough to wrap at 40 columns must fail here rather than
        silently shifting the point at which the hints compact.
        """
        out = self._run((40, 30), banners=False, own=False)
        self.assertEqual(
            out["regions"]["#mini-key-hints"].height, mm._KEY_HINTS_ROWS,
            "a hint line wraps at 40 columns — _KEY_HINTS_ROWS no longer "
            "describes the rendered height",
        )


class CollapseToggleContractTests(_ChromeFixture):
    """Both directions of the display toggle the collapse contract rests on."""

    def test_collapsible_chrome_returns_to_zero_rows_when_cleared(self):
        seen = {}

        async def after(app, pilot, result):
            seen["set"] = {
                sel: app.query_one(sel).region.height
                for sel in ("#mini-shadow-stale", "#mini-loop-status")
            }
            seen["set_flat"] = _flatten(app)
            app._set_shadow_stale_banner("")
            app._set_loop_banner("")
            await pilot.pause()
            seen["cleared"] = {
                sel: app.query_one(sel).region.height
                for sel in ("#mini-shadow-stale", "#mini-loop-status")
            }
            seen["cleared_flat"] = _flatten(app)

        self._run((40, 30), after=after)
        for sel, height in seen["set"].items():
            self.assertGreaterEqual(height, 1, f"{sel} never took a row")
        self.assertIn(STALE_PROBE, seen["set_flat"])
        self.assertIn("recheck #12 sent", seen["set_flat"])

        for sel, height in seen["cleared"].items():
            self.assertEqual(
                height, 0, f"{sel} kept rows after its text was cleared"
            )
        self.assertNotIn(STALE_PROBE, seen["cleared_flat"])
        self.assertNotIn("recheck #12 sent", seen["cleared_flat"])


if __name__ == "__main__":
    unittest.main()
