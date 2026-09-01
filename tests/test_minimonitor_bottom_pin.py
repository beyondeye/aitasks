"""minimonitor's bottom-of-list pin survives the per-tick rebuild (t1653).

`_rebuild_pane_list` tears the whole agent list down and remounts it on every
status tick, and while the container is childless `validate_scroll_y` clamps
`scroll_y` to 0. Since t1539 the position was put back by `_restore_list_scroll`,
which decided "is the user at the bottom?" from a PRE-REBUILD geometry snapshot
(`at_bottom = max_y <= 0 or scroll_y >= max_y - 1`) and applied it once
afterwards with `scroll_end(immediate=True)`.

That snapshot is stale by construction. Card heights change out of band with the
refresh tick — a gate phase row, a concern row or a mark glyph arriving between
refreshes — so `max_scroll_y` moves while no rebuild and no restore is running.
Measured live at 40 agents in a 40x40 pane, the content height swung between 76
and 176 rows several times a second. Once anything left the position more than
one row below the bottom, `at_bottom` read False for ever, the mid-list anchor
branch took over, and it faithfully froze the wrong offset: the live trace shows
the gap growing to 146 rows and the view drifting to the top.

THE FIX, and what each part is backed by:

* **Textual's anchor does the pinning.** `MiniPaneList.on_mount` arms it once and
  releases it, so the list opens at the top but `_anchored` is true and Textual's
  own `_check_anchor` can re-arm from any gesture that reaches the bottom. While
  armed, the compositor recomputes the offset from `total_region.bottom` inside
  the arrange pass (`_compositor.py:609`) — the one moment the new geometry is
  final. `_capture_list_scroll` therefore records a live MODE
  (`is_bottom_pinned`) instead of a measurement, and `_restore_list_scroll` does
  nothing at all for a pinned list.
* **`_check_anchor` refuses the degenerate mid-rebuild re-arm**, which would
  otherwise drag a mid-list reader to the bottom every tick.
* **`_reconcile_anchor` suspends the anchor for a degenerate range**, because the
  compositor's container-branch write is unclamped.

WHAT THIS MODULE CAN AND CANNOT DISCRIMINATE — stated because a negative control
that silently passes is worse than none, and two of these did exactly that
against an earlier draft.

Discriminated here (each is ONE mutation of `minimonitor_app.py`, run and
confirmed failing):

1. Delete the `if self._locked() or self.max_scroll_y <= 0: return` guard from
   `MiniPaneList._check_anchor`.
   `ArmingTests.test_rebuild_lock_refuses_the_spurious_rearm` fails (and
   `DegenerateRangeTests` with it).
2. Drop the degenerate-range suspension from `MiniPaneList._reconcile_anchor`.
   `DegenerateRangeTests.test_pinned_list_that_stops_overflowing_never_goes_negative`
   fails with a negative offset (measured: -2 here, -8 on a bare
   `VerticalScroll`).

NOT discriminated here, and the reason:

3. Restoring the old `at_bottom = max_y <= 0 or scroll_y >= max_y - 1` snapshot in
   `_capture_list_scroll` still passes — headlessly AND live. With the anchor
   armed the compositor holds the offset regardless of what the app's restore
   decides, so the snapshot is merely redundant rather than harmful in the states
   a test can construct. It is still replaced: two mechanisms owning the bottom
   is how the mid-list branch's `scroll_to()` — which calls `release_anchor()` —
   could silently unpin the list.
4. The whole *arming* mechanism is pinned only by
   `tests/test_minimonitor_bottom_pin_live.py`, whose negative control clears
   `_anchored` and reproduces the reported drift (gap up to 146 rows). Nothing
   headless can stand in for it: `App.run_test` settles layout synchronously, so
   a drag always lands exactly on `max_scroll_y` and Textual re-arms on its own.

Run: python3 tests/test_minimonitor_bottom_pin.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from textual import events  # noqa: E402
from textual.geometry import Offset  # noqa: E402
from textual.scrollbar import ScrollTo  # noqa: E402

from monitor import minimonitor_app as mm  # noqa: E402

# The real host: `MiniMonitorApp` with only its tmux-facing collaborators
# stubbed. Imported rather than restated so a change to `_refresh_data`'s
# collaborators cannot leave this module testing a divergent look-alike.
from test_minimonitor_scroll_preservation import (  # noqa: E402
    CARD_IDS, _RefreshHost, _settle,
)


class _PinCase(unittest.TestCase):
    """Boots the real host and runs one scenario against real refresh ticks."""

    #: 14 rows of list against 20 two-row cards — the same shape
    #: `_RefreshCase` uses, chosen so the fixture overflows by a wide margin.
    SIZE = (40, 14)

    def _run(self, scenario, pane_ids=CARD_IDS):
        async def go():
            app = _RefreshHost(list(pane_ids))
            async with app.run_test(size=self.SIZE) as pilot:
                await app._refresh_data()
                await _settle(pilot)
                container = app.query_one("#mini-pane-list", mm.MiniPaneList)
                if container.max_scroll_y <= 0:
                    raise AssertionError(
                        "fixture does not overflow — max_scroll_y="
                        f"{container.max_scroll_y}; the test would be vacuous")
                return await scenario(app, container, pilot)
        return asyncio.run(go())


def _regrow_cards(container, rows):
    """Change every mounted card's ROW COUNT in place, out of band.

    This is the mechanism the whole bug turns on, and a test that omits it is
    vacuous: measured on the live fixture, card heights change BETWEEN refreshes
    (a gate phase row, a concern row or a mark glyph arriving), so `max_scroll_y`
    moves while no rebuild and no restore is running. Growing content through
    `_rebuild_pane_list` instead would leave the restore looking at final
    geometry every time — which is exactly why both negative controls PASSED
    against the first draft of this module.
    """
    for card in container.query(mm.MiniPaneCard):
        card.update("\n".join(f"row {i}" for i in range(rows)))


async def _thumb_drag_to(container, pilot, y, grow_to=None):
    """Deliver a thumb drag that REQUESTS `y`, then release it.

    Faithful to the real path rather than to a convenient one: a drag is a
    `ScrollTo` message posted by `ScrollBar._on_mouse_move` (which is why
    `_on_scroll_to` is where the intent is recorded), followed by a
    `MouseRelease` handled by the scrollbar (which is why the app owns the
    scrollbar subclass). Calling `_check_anchor` directly would bypass both
    seams and prove nothing about how they are wired.

    `grow_to` grows the content BETWEEN the request and the release, reproducing
    what the live fixture measured: a drag aimed at the trough end landed at
    20.98 of an eventual 50, because `max_scroll_y` moved under it. Textual
    re-arms during the drag rather than at the release, so the pin survives that
    — which is the measurement that justified deleting an app-owned
    thumb-release seam instead of shipping it.
    """
    container.post_message(ScrollTo(x=None, y=y))
    await _settle(pilot, 4)
    if grow_to is not None:
        _regrow_cards(container, grow_to)
        await _settle(pilot, 6)
    container.vertical_scrollbar._on_mouse_release(events.MouseRelease(Offset(0, 0)))
    await _settle(pilot, 4)


class ArmingTests(_PinCase):
    """Who may arm the pin, and who may not."""

    def test_list_opens_armed_but_released(self):
        """`_anchored` must be true (or `watch_scroll_y` never even calls
        `_check_anchor`), and `_anchor_released` must be true so the list opens
        at the TOP rather than tailing like a log."""
        async def scenario(app, container, pilot):
            return (container.is_anchored, container.is_bottom_pinned,
                    container.scroll_y)

        anchored, pinned, scroll_y = self._run(scenario)
        self.assertTrue(anchored, "on_mount never armed the anchor")
        self.assertFalse(pinned, "the list opened pinned to the bottom")
        self.assertEqual(scroll_y, 0, "the list did not open at the top")

    def test_thumb_drag_to_the_end_arms_the_pin(self):
        """A drag to the trough end pins the list, and CONTENT GROWING UNDER THE
        DRAG does not cost it the pin.

        The requested position deliberately exceeds `max_scroll_y`, which is what
        a drag to the trough end produces, and the content then grows before the
        release. This is the positive control every other case here depends on:
        without it they could all pass against a list that simply never pins.
        """
        async def scenario(app, container, pilot):
            before_release = {}

            async def run():
                await _thumb_drag_to(
                    container, pilot, container.max_scroll_y + 50, grow_to=6)
            await run()
            return (container.is_bottom_pinned, container.scroll_y,
                    container.max_scroll_y, before_release)

        pinned, scroll_y, max_y, _ = self._run(scenario)
        self.assertTrue(
            pinned,
            "a drag to the end did not arm the bottom pin — with the content "
            "grown under the drag, Textual's own scroll_y >= max_scroll_y can "
            "never fire, so only the recorded intent can arm it")
        self.assertGreater(max_y, 0, "the fixture stopped overflowing — vacuous")
        self.assertEqual(scroll_y, max_y)

    def test_drag_that_did_not_reach_the_end_does_not_arm(self):
        """The boundary, pinned from the other side: a drag that stopped mid-list
        must leave the list unpinned, even though it travels the identical code
        path. Without this the test above could pass against an arming rule that
        fires on any drag at all."""
        async def scenario(app, container, pilot):
            await _thumb_drag_to(container, pilot, 3)
            return container.is_bottom_pinned, container.scroll_y

        pinned, scroll_y = self._run(scenario)
        self.assertFalse(
            pinned,
            "a drag that stopped mid-list armed the bottom pin — the release "
            "flag is arming unconditionally instead of on recorded intent")
        self.assertEqual(scroll_y, 3)

    def test_rebuild_lock_refuses_the_spurious_rearm(self):
        """NEGATIVE CONTROL 1 targets this test.

        Mid-rebuild the container is childless, so `max_scroll_y` is 0 and the
        clamp has already put `scroll_y` at 0 — Textual's `0 >= 0` is trivially
        true and would re-pin a mid-list reader on EVERY tick.
        """
        async def scenario(app, container, pilot):
            container.scroll_to(y=6, animate=False, immediate=True, force=True)
            await _settle(pilot, 3)
            app._list_scroll_lock = True
            # Exactly the state a rebuild passes through.
            await container.remove_children()
            await _settle(pilot, 2)
            container._check_anchor()
            refused = container.is_bottom_pinned
            # And the converse, so the refusal is not vacuous: once the rebuild
            # is over, a real gesture still arms.
            app._list_scroll_lock = False
            await app._refresh_data()
            await _settle(pilot)
            await _thumb_drag_to(container, pilot, container.max_scroll_y + 50)
            return refused, container.is_bottom_pinned

        refused, armed_after = self._run(scenario)
        self.assertFalse(
            refused,
            "the childless mid-rebuild container re-armed the bottom pin — a "
            "mid-list reader would be dragged to the bottom on every tick")
        self.assertTrue(
            armed_after,
            "the list never armed even after the rebuild finished, so the "
            "refusal above proves nothing")


class PinSurvivesRefreshTests(_PinCase):
    """AC1 / AC2 — the pin holds across ticks, with and without a gesture."""

    TICKS = 10

    async def _churn_and_measure(self, app, container, pilot):
        """Run TICKS refreshes with card heights AND the agent set changing."""
        gaps = []
        for i in range(self.TICKS):
            if i == 4:                      # an agent dies, no user gesture
                app.set_panes([p for p in CARD_IDS if p != "%1"])
            await app._refresh_data()
            await _settle(pilot)
            # OUT OF BAND with the tick — see `_regrow_cards`. This is what makes
            # the pre-fix snapshot go stale, and what a rebuild-synchronised
            # churn cannot reproduce.
            _regrow_cards(container, 2 + (i % 4))
            await _settle(pilot, 6)
            gaps.append((i, container.max_scroll_y - container.scroll_y,
                         container.max_scroll_y))
        return gaps

    def test_pin_survives_ticks_with_card_height_churn(self):
        """AC1 — the pin holds while card heights change OUT OF BAND with the
        tick, which is the mechanism the whole bug turns on. See the module
        docstring for why this cannot discriminate the capture-mode change on its
        own; the live module's control is what covers the arming."""
        async def scenario(app, container, pilot):
            await _thumb_drag_to(container, pilot, container.max_scroll_y + 50)
            return await self._churn_and_measure(app, container, pilot)

        for i, gap, max_y in self._run(scenario):
            self.assertGreater(
                max_y, 0, f"tick {i}: fixture stopped overflowing — vacuous")
            self.assertEqual(
                gap, 0,
                f"tick {i}: the bottom-pinned list drifted {gap} rows off the "
                f"bottom (max_scroll_y was {max_y})")

    def test_pin_survives_the_list_growing_and_shrinking(self):
        """AC2 — no user gesture at all after the initial drag."""
        async def scenario(app, container, pilot):
            await _thumb_drag_to(container, pilot, container.max_scroll_y + 50)
            out = []
            for i in range(8):
                app.set_panes(CARD_IDS[: 8 + (i % 5) * 3])
                await app._refresh_data()
                await _settle(pilot)
                out.append((i, container.max_scroll_y - container.scroll_y,
                            container.max_scroll_y))
            return out

        for i, gap, max_y in self._run(scenario):
            if max_y <= 0:
                continue        # legitimately stopped overflowing this tick
            self.assertEqual(
                gap, 0, f"tick {i}: pin lost while the list resized (max={max_y})")

    def test_user_scroll_away_is_not_repinned(self):
        """AC3 — the `UserGestureSupersedesTests` contract, at the pin level."""
        async def scenario(app, container, pilot):
            await _thumb_drag_to(container, pilot, container.max_scroll_y + 50)
            self.assertTrue(container.is_bottom_pinned)
            # A real wheel gesture away from the bottom.
            container.post_message(events.MouseScrollUp(
                widget=container, x=5, y=5, delta_x=0, delta_y=-1, button=0,
                screen_x=5, screen_y=5, shift=False, meta=False, ctrl=False))
            await _settle(pilot, 4)
            after_gesture = container.scroll_y
            max_at_gesture = container.max_scroll_y
            for _ in range(3):
                await app._refresh_data()
                await _settle(pilot)
            return (after_gesture, max_at_gesture, container.scroll_y,
                    container.is_bottom_pinned)

        after_gesture, max_at_gesture, final, pinned = self._run(scenario)
        self.assertLess(
            after_gesture, max_at_gesture,
            "the wheel gesture did not actually move the list off the bottom "
            f"(scroll_y={after_gesture}, max_scroll_y={max_at_gesture}), so "
            "everything below would pass without the contract being exercised")
        self.assertFalse(
            pinned, "the list re-pinned itself after the user scrolled away")
        self.assertEqual(
            final, after_gesture,
            "the refresh ticks moved the user away from the position they "
            "scrolled to")


class DegenerateRangeTests(_PinCase):
    """The compositor's container-branch anchor write is unclamped."""

    def test_pinned_list_that_stops_overflowing_never_goes_negative(self):
        """NEGATIVE CONTROL 2 targets this test.

        `_compositor.py:609` writes `total_region.bottom - container_height`
        through `set_reactive`, bypassing `validate_scroll_y` — unlike the
        non-container branch at `:693`, which uses the reactive setter and does
        clamp. Measured on a bare `VerticalScroll`: `scroll_y = -8` at
        `max_scroll_y = 0`, persisting on every arrange until content regrew.
        """
        async def scenario(app, container, pilot):
            await _thumb_drag_to(container, pilot, container.max_scroll_y + 50)
            self.assertTrue(container.is_bottom_pinned)
            app.set_panes(CARD_IDS[:2])       # far shorter than the viewport
            await app._refresh_data()
            await _settle(pilot)
            shrunk = (container.scroll_y, container.max_scroll_y,
                      container.is_bottom_pinned)
            app.set_panes(CARD_IDS)           # and back
            await app._refresh_data()
            await _settle(pilot)
            return shrunk, (container.scroll_y, container.max_scroll_y)

        (scroll_y, max_y, pinned), (regrown_y, regrown_max) = self._run(scenario)
        self.assertLessEqual(max_y, 0, "the fixture still overflowed — vacuous")
        self.assertGreaterEqual(
            scroll_y, 0,
            "a pinned list that stopped overflowing held a NEGATIVE scroll "
            "offset; the compositor's unclamped write was not corrected")
        self.assertTrue(
            pinned,
            "correcting the degenerate offset released the pin — it must be "
            "written through the reactive setter, not scroll_to()")
        self.assertEqual(
            regrown_y, regrown_max,
            "the pin did not re-engage when the list grew back")


if __name__ == "__main__":
    unittest.main(verbosity=2)
