"""Tests for minimonitor's in-place list updates (t2183).

`MiniMonitorApp._refresh_data` used to tear every `MiniPaneCard` down and
remount it on every 3 s tick, whether or not anything had changed — about 80 %
of a live minimonitor's CPU was Textual render/dispatch (t2034_1). The list now
takes one of three routes per tick, chosen by `_plan_in_place_list_update`:

* **unchanged** — same card set, same texts: nothing is touched, and neither
  the t1539/t1653 scroll capture/restore nor a focus restore runs;
* **in place** — same card set (the `(kind, key)` sequence of cards, dividers
  and the `other (N)` header), some texts differ: only the changed cards get
  `update()`. `layout=False` is used only when the card's height provably
  cannot change: same newline count AND both the old and new text fit the
  card's ACTUAL content width. The configured `_target_width` is not that proof:
  the real pane can be narrower, and `Static` wraps;
* **full rebuild** — the set changed (or a recorded card was removed out from
  under the record): `_rebuild_pane_list`, exactly as before.

Whenever any card's geometry may change (an in-place `layout=True` update, or a
rebuild) the existing scroll-preservation sequence runs around it.

Focus: the user's selection is read at RESTORE time, not snapshotted at the top
of the tick — a click during the tick's awaits (`capture_all_async` can take
seconds on a loaded tmux server) must survive the tick on both paths. That is
the "current intent" half of t2201's fix direction; t2201 still owns the
deferred-`focus()` race and the remaining cases (see its task file).

`tests/test_minimonitor_scroll_preservation.py` and
`tests/test_minimonitor_bottom_pin.py` pin the FULL-REBUILD path through the
`_IN_PLACE_LIST_UPDATES = False` seam on `_ListHost`, so their t1539/t1653
negative controls stay meaningful; this module turns the seam back on.

NEGATIVE CONTROLS. Each is ONE mutation of `minimonitor_app.py` and names the
tests that must fail; all were run against this file and confirmed failing
(results recorded in aiplans/archived/p2183_*.md):

(a) `_plan_in_place_list_update` returns `[]` instead of its updates →
    `test_same_height_change_updates_only_that_card_without_layout`,
    `test_line_count_change_uses_layout_and_keeps_the_mid_list_anchor`.
(b) `_card_height_stable` drops the fit check (newline count only) →
    `test_narrow_pane_wrap_change_uses_layout`.
(c) `layout` forced to False →
    `test_line_count_change_uses_layout_and_keeps_the_mid_list_anchor`.
(d) the `is_attached` / `parent is container` check removed →
    `test_externally_removed_card_forces_a_full_rebuild`.
(e) the in-place branch restores the top-of-tick focus snapshot
    unconditionally → `test_click_during_suspended_capture_survives_in_place_tick`.

Run: python3 tests/test_minimonitor_incremental_list.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / "tests"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from textual.widgets import Static  # noqa: E402

from monitor import minimonitor_app as mm  # noqa: E402
from test_minimonitor_scroll_preservation import (  # noqa: E402
    CARD_IDS, _RefreshHost, _settle,
)
from test_minimonitor_bottom_pin import _thumb_drag_to  # noqa: E402


class _IncHost(_RefreshHost):
    """`_RefreshHost` on the production (in-place) path, with controllable text.

    `_agent_card_text` is replaced so each test states exactly which card's text
    changes and how; everything else on the refresh path is the real code.
    `capture_gate` / `capture_entered` suspend a tick inside its capture await,
    which is where a real click races the tick.
    """

    _IN_PLACE_LIST_UPDATES = True

    def __init__(self, pane_ids) -> None:
        super().__init__(pane_ids)
        self.texts: dict[str, str] = {}
        self.parked_ids: set[str] = set()
        self.capture_gate: asyncio.Event | None = None
        self.capture_entered: asyncio.Event | None = None

    def _agent_card_text(self, snap) -> str:
        pid = snap.pane.pane_id
        return self.texts.get(pid, f"card {pid}\nline two")

    async def _capture_all_async(self):
        if self.capture_entered is not None:
            self.capture_entered.set()
        if self.capture_gate is not None:
            await self.capture_gate.wait()
        snaps = await super()._capture_all_async()
        for pid in self.parked_ids:
            if pid in snaps:
                snaps[pid].parked = True
        return snaps


def _boot(scenario, size=(40, 14), pane_ids=CARD_IDS):
    async def go():
        app = _IncHost(list(pane_ids))
        async with app.run_test(size=size) as pilot:
            await app._refresh_data()
            await _settle(pilot)
            container = app.query_one("#mini-pane-list", mm.MiniPaneList)
            if container.max_scroll_y <= 0:
                raise AssertionError(
                    "fixture does not overflow — max_scroll_y="
                    f"{container.max_scroll_y}; the test would be vacuous")
            return await scenario(app, container, pilot)
    return asyncio.run(go())


def _cards(container) -> dict:
    return {c.pane_id: c for c in container.query(mm.MiniPaneCard)}


def _identities(container) -> dict:
    """The card OBJECTS by pane id — held, not `id()`s. A rebuild frees the old
    cards, and CPython then reuses their addresses for the new ones, so an
    `id()` comparison reads a remount as "the same card" (observed)."""
    return dict(_cards(container))


@contextmanager
def _spy_card_updates():
    """Record every `MiniPaneCard.update` as `(pane_id, layout)`, then delegate."""
    calls: list[tuple[str, bool]] = []
    orig = mm.MiniPaneCard.update

    def spy(self, content="", *, layout=True):
        calls.append((self.pane_id, layout))
        return orig(self, content, layout=layout)

    with mock.patch.object(mm.MiniPaneCard, "update", spy):
        yield calls


async def _tick(app, pilot):
    await app._refresh_data()
    await _settle(pilot)


class UnchangedTickTests(unittest.TestCase):

    def test_unchanged_tick_touches_nothing(self):
        async def scenario(app, container, pilot):
            container.scroll_to(y=6, animate=False, immediate=True, force=True)
            await _settle(pilot, 4)
            target = _cards(container)["%4"]
            app.set_focus(target, scroll_visible=False)
            await _settle(pilot, 2)
            before = _identities(container)
            with _spy_card_updates() as calls:
                await _tick(app, pilot)
            return (before, _identities(container), calls, container.scroll_y,
                    app.focused is target)

        before, after, calls, scroll_y, focused = _boot(scenario)
        self.assertEqual(before, after, "an unchanged tick remounted cards")
        self.assertEqual(calls, [], "an unchanged tick updated cards")
        self.assertEqual(scroll_y, 6)
        self.assertTrue(focused, "an unchanged tick moved focus")


class InPlaceUpdateTests(unittest.TestCase):

    def test_same_height_change_updates_only_that_card_without_layout(self):
        async def scenario(app, container, pilot):
            before = _identities(container)
            app.texts["%3"] = "card %3 changed\nline two"
            with _spy_card_updates() as calls:
                await _tick(app, pilot)
            return before, _identities(container), calls, _cards(container)["%3"]

        before, after, calls, card = _boot(scenario)
        self.assertEqual(before, after, "a text change remounted cards")
        self.assertEqual(calls, [("%3", False)])
        self.assertEqual(card.content, "card %3 changed\nline two")

    def test_line_count_change_uses_layout_and_keeps_the_mid_list_anchor(self):
        async def scenario(app, container, pilot):
            anchor = _cards(container)["%3"]
            # Scroll to the anchor card's own top (a session divider shifts the
            # cards down in multi-session mode, so no constant is assumed).
            container.scroll_to(y=anchor.virtual_region.y, animate=False,
                                immediate=True, force=True)
            await _settle(pilot, 4)
            row_before = anchor.virtual_region.y - container.scroll_y
            before = _identities(container)
            # A card ABOVE the anchor grows by one row.
            app.texts["%1"] = "card %1\nline two\nline three"
            with _spy_card_updates() as calls:
                await _tick(app, pilot)
            row_after = anchor.virtual_region.y - container.scroll_y
            return (before, _identities(container), calls,
                    _cards(container)["%1"].size.height, row_before, row_after)

        before, after, calls, height, row_before, row_after = _boot(scenario)
        self.assertEqual(before, after, "a line-count change remounted cards")
        self.assertEqual(calls, [("%1", True)])
        self.assertEqual(height, 3, "the grown card kept its old height")
        self.assertEqual(row_before, 0, "fixture: anchor must start at the top")
        self.assertEqual(
            row_after, row_before,
            "the mid-list anchor moved on screen when a card above it grew")

    def test_narrow_pane_wrap_change_uses_layout(self):
        """Same newline count, but the new text wraps at the ACTUAL width."""
        long_line = "card %3 " + "x" * 24

        async def scenario(app, container, pilot):
            card = _cards(container)["%3"]
            width = card.content_size.width
            app.texts["%3"] = f"{long_line}\nline two"
            with _spy_card_updates() as calls:
                await _tick(app, pilot)
            return width, calls, _cards(container)["%3"].size.height

        width, calls, height = _boot(scenario, size=(20, 14))
        self.assertGreater(width, 0)
        self.assertGreater(
            len(long_line), width,
            "fixture: the new line must not fit the actual width (vacuous)")
        self.assertLess(width, mm.MiniMonitorApp._target_width,
                        "fixture: the pane must be narrower than the target")
        self.assertEqual(calls, [("%3", True)])
        self.assertGreater(height, 2, "the wrapped card kept its unwrapped height")

    def test_bottom_pinned_list_stays_pinned_when_a_card_grows_in_place(self):
        async def scenario(app, container, pilot):
            await _thumb_drag_to(container, pilot, container.max_scroll_y + 50)
            pinned = container.is_bottom_pinned
            max_before = container.max_scroll_y
            before = _identities(container)
            app.texts["%1"] = "card %1\nline two\nthree\nfour"
            await _tick(app, pilot)
            return (pinned, before, _identities(container), max_before,
                    container.max_scroll_y, container.scroll_y)

        pinned, before, after, max_before, max_after, scroll_y = _boot(scenario)
        self.assertTrue(pinned, "fixture: the drag did not arm the pin")
        self.assertEqual(before, after)
        self.assertGreater(max_after, max_before, "fixture: content did not grow")
        self.assertEqual(scroll_y, max_after, "the bottom pin was lost")


class FullRebuildTests(unittest.TestCase):
    """A changed card SET rebuilds — every surviving card is a new object."""

    def _assert_rebuilt(self, before, after):
        common = set(before) & set(after)
        self.assertTrue(common, "fixture: no surviving cards to compare")
        same = sorted(p for p in common if before[p] is after[p])
        self.assertEqual(same, [], "cards survived a structural change")

    def _run_change(self, change):
        async def scenario(app, container, pilot):
            before = _identities(container)
            await change(app, container, pilot)
            await _tick(app, pilot)
            return before, _identities(container)
        return _boot(scenario)

    def test_removed_pane_rebuilds(self):
        async def change(app, container, pilot):
            app.set_panes([p for p in CARD_IDS if p != "%19"])
        before, after = self._run_change(change)
        self._assert_rebuilt(before, after)
        self.assertNotIn("%19", after)

    def test_added_pane_rebuilds(self):
        async def change(app, container, pilot):
            app.set_panes(CARD_IDS + ["%20"])
        before, after = self._run_change(change)
        self._assert_rebuilt(before, after)
        self.assertIn("%20", after)

    def test_reorder_rebuilds(self):
        async def change(app, container, pilot):
            app.set_panes(list(reversed(CARD_IDS)))
        self._assert_rebuilt(*self._run_change(change))

    def test_hide_inactive_toggle_rebuilds(self):
        async def change(app, container, pilot):
            app.parked_ids = {"%5"}
            await _tick(app, pilot)            # parked but shown: same set
            app._hide_inactive = True
        before, after = self._run_change(change)
        self._assert_rebuilt(before, after)
        self.assertNotIn("%5", after)

    def test_multi_session_toggle_rebuilds(self):
        async def change(app, container, pilot):
            # Flipped, not set: `__init__` defaults it to True, so assigning
            # True would change nothing (and did, in this test's first draft).
            app._multi_session = not app._multi_session
            # Single-session mode projects to the app's OWN session; the
            # fixture's panes all live in "s1" (`_ListHost` is "t1539").
            app._session = "s1"
        before, after = self._run_change(change)
        self._assert_rebuilt(before, after)

    def test_externally_removed_card_forces_a_full_rebuild(self):
        async def change(app, container, pilot):
            await _cards(container)["%7"].remove()
            await _settle(pilot, 2)
        before, after = self._run_change(change)
        self._assert_rebuilt(before, after)
        self.assertIn("%7", after, "the removed card was not restored")


class ClickDuringTickTests(unittest.TestCase):
    """A click while the tick is suspended in capture must survive the tick."""

    def _run_click(self, structural: bool):
        async def scenario(app, container, pilot):
            visible = [c for c in container.query(mm.MiniPaneCard)
                       if c.region.height > 0]
            if len(visible) < 2:
                raise AssertionError("fixture: fewer than two visible cards")
            first, clicked = visible[0], visible[1]
            app.set_focus(first, scroll_visible=False)
            await _settle(pilot, 2)
            if app._focused_pane_id != first.pane_id:
                raise AssertionError("fixture: initial focus not recorded")
            app.capture_entered = asyncio.Event()
            app.capture_gate = asyncio.Event()
            if structural:
                app.set_panes(CARD_IDS + ["%20"])
            task = asyncio.create_task(app._refresh_data())
            await asyncio.wait_for(app.capture_entered.wait(), 5)
            await pilot.click(clicked)
            await _settle(pilot, 2)
            landed = app.focused is clicked
            app.capture_gate.set()
            await asyncio.wait_for(task, 10)
            await _settle(pilot)
            focused_id = getattr(app.focused, "pane_id", None)
            return clicked.pane_id, landed, app._focused_pane_id, focused_id

        clicked_id, landed, recorded, focused_id = _boot(scenario)
        self.assertTrue(landed, "fixture: the click did not focus its card")
        self.assertEqual(recorded, clicked_id,
                         "the tick reverted the recorded selection")
        self.assertEqual(focused_id, clicked_id,
                         "the tick moved focus off the clicked card")

    def test_click_during_suspended_capture_survives_in_place_tick(self):
        self._run_click(structural=False)

    def test_click_during_suspended_capture_survives_full_rebuild(self):
        self._run_click(structural=True)


class SessionBarTests(unittest.TestCase):

    def test_unchanged_session_bar_text_is_not_updated(self):
        async def scenario(app, container, pilot):
            bar = app.query_one("#mini-session-bar", Static)
            calls = []
            orig = bar.update

            def spy(*args, **kwargs):
                calls.append(args)
                return orig(*args, **kwargs)

            bar.update = spy
            app._rebuild_session_bar(desync="")
            app._rebuild_session_bar(desync="")
            unchanged = len(calls)
            app.set_panes(CARD_IDS[:-1])
            app._snapshots = await app._capture_all_async()
            app._rebuild_session_bar(desync="")
            return unchanged, len(calls)

        unchanged, total = _boot(scenario)
        self.assertEqual(unchanged, 0, "an unchanged bar text was re-rendered")
        self.assertEqual(total, 1, "a changed bar text was not rendered")


if __name__ == "__main__":
    unittest.main()
