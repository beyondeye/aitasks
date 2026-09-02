"""Terminal focus-in must not steal the click that came with it (t1683).

When the minimonitor pane is NOT the active tmux pane, the first click on an
agent card did not select the card under the cursor — the user had to click
twice. Reported live on a 40x61 pane with ~20 agent cards; invisible on a short,
unscrollable list.

`MiniMonitorApp.on_app_focus` fired on EVERY terminal focus-in and
unconditionally called `_auto_select_own_window`, i.e. `list_cards[0].focus()`.
Two Textual facts turned that into the defect:

* `Widget.focus()` is DEFERRED — `widget.py` posts an `events.Callback` via
  `app.call_later`, onto the app's own FIFO. Click-focus is SYNCHRONOUS:
  `Screen._forward_event` calls `set_focus(focusable_widget,
  scroll_visible=False)` inline.
* `focus()` defaults to `scroll_visible=True`, so the deferred call also
  scrolled `#mini-pane-list` back to the top.

Dispatch order compounds it. `MessagePump._get_dispatch_methods` walks
`self.__class__.__mro__` SUBCLASS FIRST, so `MiniMonitorApp.on_app_focus` runs
before `App._on_app_focus`. Textual's own `_watch_app_focus` then restores
`_last_focused_on_app_blur` with `scroll_visible=False` — and the queued card-0
focus lands after that and overwrites it. Both interleavings with the click were
broken, and both are covered below.

THE FIX HAS TWO HALVES, AND EACH NEEDS ITS OWN COVERAGE:

1. `_auto_select_own_window` focuses with `scroll_visible=False`. Unconditional,
   because its only caller (`_restore_focus`'s fallback) runs inside a passive
   refresh where the captured anchor is authoritative (t1539).
2. `on_app_focus` only SCHEDULES; `_auto_select_after_focus_in` makes the
   decision, bails when anything is focused, and settles focus with
   `set_focus` — not `Widget.focus()`, which would defer a second time and land
   after a click still queued behind it.

NEGATIVE CONTROLS. Two mutations of the source, each naming the tests that must
fail; both were run against this file and confirmed failing as stated.

1. Revert BOTH halves to the pre-fix source (`_auto_select_own_window` back to
   `list_cards[0].focus()`, `on_app_focus` back to a direct
   `self._auto_select_own_window()`). ALL SEVEN tests fail, with the focused
   card / `scroll_y` pairs in the `pre-fix` column of the table below.

2. Keep half 1 (`scroll_visible=False`) and drop half 2 — restore `on_app_focus`
   to an unconditional `self._auto_select_own_window()`. Then
   `test_click_queued_with_the_focus_in_wins`,
   `test_focus_in_alone_preserves_the_focused_card_and_scroll`,
   `test_focus_in_without_a_preceding_blur_preserves_focus` and
   `test_focus_in_does_not_steal_focus_from_another_widget` fail; the other
   three PASS. This control is the reason the two no-click cases exist:
   `test_click_after_the_callback_lands_on_the_aimed_card` passes against a
   guard-less build, because the later click re-focuses the aimed card and hides
   the missing guard.

Measured matrix (focused pane_id / `scroll_y`), fixture below, all three columns
observed rather than predicted:

| case                                   | pre-fix  | no guard | fixed             |
|----------------------------------------|----------|----------|-------------------|
| click queued with the focus-in         | %0 / 0   | %0 / 14  | %10 / 14          |
| click after the callback flushed       | %3 / 0   | %10 / 14 | %10 / 14          |
| focus-in alone (blur -> focus)         | %0 / 0   | %0 / 14  | %10 / 14          |
| focus-in with no preceding blur        | %0 / 0   | %0 / 14  | %10 / 14          |
| nothing focused                        | %0 / 0   | %0 / 14  | %0 / 14           |
| another widget focused                 | %0 / 0   | %0 / 14  | #mini-own-agent/14|
| `_restore_focus` fallback              | %0 / 0   | %0 / 14  | %0 / 14           |

`pilot.click` is deliberately NOT used. It `await`s a `pause()` before each
mouse event and calls `screen._forward_event` directly, so it drains the pending
focus-in callback first — which makes the "mouse already queued" interleaving
unreachable. The click is posted as a real `events.MouseDown` onto the app's
queue instead, which is the production path (`App.on_event` forwards it to
`screen._forward_event`).

Run: python3 tests/test_minimonitor_focus_in_click.py
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
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# MiniMonitorApp only renames its tmux window when built by the production
# launcher, but scrub the ambient tmux env anyway so nothing here can touch the
# pane the suite runs in (t1240). This is ALSO what neutralises the real
# `on_mount`: with TMUX unset it takes its "Not inside tmux" early return before
# any detection, pane-marker stamping or refresh timer.
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from textual import events  # noqa: E402

from monitor import minimonitor_app as mm  # noqa: E402

# Enough cards that `#mini-pane-list` scrolls at size=(40, 12); the defect is
# invisible on an unscrollable list.
CARD_IDS = [f"%{i}" for i in range(20)]

# A mid-list scroll offset and a card that is neither card 0 nor off screen at
# that offset. Both are load-bearing: card 0 would make "the click won" and "the
# auto-select won" indistinguishable, and scroll_y 0 would hide the scroll half
# of the defect entirely.
SCROLL_Y = 14
TARGET_INDEX = 10
TARGET_ID = CARD_IDS[TARGET_INDEX]


class _FocusHost(mm.MiniMonitorApp):
    """The REAL `MiniMonitorApp`, with only its boot sequence neutralised.

    Subclassing rather than standing up a look-alike `App` is deliberate: the
    handler under test IS `MiniMonitorApp.on_app_focus`, and Textual dispatches
    `on_*` handlers on EVERY class in the MRO — so a host that merely resembles
    the app would not exercise it at all, and (worse) an override here would not
    suppress the production one either. `compose` and `CSS` are untouched, so
    the list sits in the real 40-column layout with the real chrome above it.
    Only `__init__` is narrowed, to the two arguments that have no default.
    """

    def __init__(self) -> None:
        super().__init__(session="t1683", project_root=REPO_ROOT)


def _cards(pane_ids):
    return [mm.MiniPaneCard(pid, f"card {pid}\nsecond line") for pid in pane_ids]


async def _settle(pilot, frames=12):
    for _ in range(frames):
        await pilot.pause()


def _mouse_down_kwargs(card, dx=1, dy=0):
    """A `MouseDown` aimed at `card`, in SCREEN coordinates.

    `Screen._forward_event` resolves the target with `get_focusable_widget_at(
    event.x, event.y)` at PROCESSING time, which is exactly the point: the
    coordinates are captured before the focus-in, and a build that scrolls the
    list will therefore resolve them to a different card — the reported "you
    select an agent you did not aim at" symptom.
    """
    region = card.region
    x, y = region.x + dx, region.y + dy
    return dict(widget=None, x=x, y=y, delta_x=0, delta_y=0, button=1,
                shift=False, meta=False, ctrl=False, screen_x=x, screen_y=y)


def _focus_key(app):
    """Identify the focused widget by pane_id (cards) or DOM id (everything
    else), so a case can assert "the own-agent panel kept focus" as precisely as
    it asserts "card %10 kept focus"."""
    focused = app.focused
    if focused is None:
        return None
    return getattr(focused, "pane_id", None) or focused.id


class _FocusCase(unittest.TestCase):
    """Drives a real host app; subclasses implement `scenario`.

    Every scenario starts from the same arranged state — list scrolled to
    `SCROLL_Y`, `TARGET_ID` focused — and returns `(focus_key, scroll_y)`.
    """

    def run_scenario(self, scenario):
        async def go():
            app = _FocusHost()
            async with app.run_test(size=(40, 12)) as pilot:
                container = app.query_one("#mini-pane-list", mm.MiniPaneList)
                await container.mount_all(_cards(CARD_IDS))
                await _settle(pilot, 4)
                cards = list(container.query(mm.MiniPaneCard))
                container.scroll_to(y=SCROLL_Y, animate=False,
                                    immediate=True, force=True)
                await _settle(pilot, 3)
                # scroll_visible=False so the arrangement itself cannot move the
                # list and quietly invalidate the SCROLL_Y precondition.
                cards[TARGET_INDEX].focus(scroll_visible=False)
                await _settle(pilot, 3)
                self.assertEqual(
                    (_focus_key(app), container.scroll_y), (TARGET_ID, SCROLL_Y),
                    "fixture precondition broken before the scenario ran",
                )
                await scenario(app, container, cards, pilot)
                await _settle(pilot, 12)
                return _focus_key(app), container.scroll_y
        return asyncio.run(go())


class FocusInVersusClickTests(_FocusCase):
    """The two interleavings of a focus-in with the click that produced it."""

    def test_click_queued_with_the_focus_in_wins(self):
        """Mouse bytes already queued when `AppFocus` is dispatched.

        Production order is [AppFocus, MouseDown]: the focus-in handler queues
        its callback BEHIND the click, the click focuses the right card
        synchronously, and pre-fix the callback then focused card 0 and scrolled
        to the top — silently undoing the click. NEGATIVE CONTROLS 1 AND 2 both
        target this test.
        """
        async def scenario(app, container, cards, pilot):
            kwargs = _mouse_down_kwargs(cards[TARGET_INDEX])
            app.post_message(events.AppBlur())
            await _settle(pilot, 4)
            # No pause between these two: the click must still be in the queue
            # when the focus-in is dispatched.
            app.post_message(events.AppFocus())
            app.post_message(events.MouseDown(**kwargs))

        self.assertEqual(
            self.run_scenario(scenario), (TARGET_ID, SCROLL_Y),
            "the focus-in callback overwrote the click that arrived with it",
        )

    def test_click_after_the_callback_lands_on_the_aimed_card(self):
        """Mouse bytes arrive in a later read.

        The focus-in callback runs first. Pre-fix it scrolled the list to the
        top, so the click — at the same screen y — landed over a DIFFERENT card
        (%3 rather than %10): the user selects an agent they did not aim at.

        NOTE this test passes against NEGATIVE CONTROL 2 (guard removed, scroll
        fix kept): the later click re-focuses %10 either way. That is why the two
        no-click cases below exist.
        """
        async def scenario(app, container, cards, pilot):
            kwargs = _mouse_down_kwargs(cards[TARGET_INDEX])
            app.post_message(events.AppBlur())
            await _settle(pilot, 4)
            app.post_message(events.AppFocus())
            await _settle(pilot, 10)      # let the focus-in callback flush
            app.post_message(events.MouseDown(**kwargs))

        self.assertEqual(
            self.run_scenario(scenario), (TARGET_ID, SCROLL_Y),
            "the focus-in scrolled the list, so the click landed on the wrong "
            "card at the same screen position",
        )


class FocusInAloneTests(_FocusCase):
    """The stated invariant, with no click involved at all: a terminal focus-in
    never moves the selection or the scroll position when something is already
    focused."""

    def test_focus_in_alone_preserves_the_focused_card_and_scroll(self):
        """The alt-tab round trip — `AppBlur`, then `AppFocus`, no click.

        `AppBlur` clears focus and stores the card in
        `_last_focused_on_app_blur`; `App._watch_app_focus` restores it
        non-scrolling. The guard must leave that restore alone. NEGATIVE
        CONTROLS 1 AND 2 both target this test.
        """
        async def scenario(app, container, cards, pilot):
            app.post_message(events.AppBlur())
            await _settle(pilot, 4)
            app.post_message(events.AppFocus())

        self.assertEqual(
            self.run_scenario(scenario), (TARGET_ID, SCROLL_Y),
            "an alt-tab back into the terminal reset the selection / scroll",
        )

    def test_focus_in_without_a_preceding_blur_preserves_focus(self):
        """A bare `AppFocus` with the card still focused.

        `app_focus` is already True, so the reactive does not change and
        `App._watch_app_focus` never fires: Textual's restore contributes
        nothing here and the guard is the ONLY thing standing between the
        focused card and card 0. NEGATIVE CONTROLS 1 AND 2 both target this
        test.
        """
        async def scenario(app, container, cards, pilot):
            app.post_message(events.AppFocus())

        self.assertEqual(
            self.run_scenario(scenario), (TARGET_ID, SCROLL_Y),
            "a focus-in stole the selection even though the card was focused "
            "throughout — the guard is not being evaluated",
        )


class FocusInFallbackTests(_FocusCase):
    """The fallback is kept, not deleted — but it is narrow and never scrolls."""

    def test_nothing_focused_selects_card_zero_without_scrolling(self):
        """Non-vacuity control for the guard: with nothing focused the fallback
        MUST still fire, so deleting `on_app_focus` outright fails here. It also
        pins the non-scrolling half — pre-fix this snapped the list to the top.
        """
        async def scenario(app, container, cards, pilot):
            app.screen.set_focus(None)
            await _settle(pilot, 3)
            app.post_message(events.AppFocus())

        self.assertEqual(
            self.run_scenario(scenario), (CARD_IDS[0], SCROLL_Y),
            "the focus-in fallback either did not fire or scrolled the list",
        )

    def test_focus_in_does_not_steal_focus_from_another_widget(self):
        """The guard is `self.focused is not None`, not a card-only check.

        `#mini-own-agent` stands in for any non-card focus owner — including an
        open dialog's control, which the pre-fix handler yanked focus out of on
        every alt-tab. NEGATIVE CONTROLS 1 AND 2 both target this test.
        """
        async def scenario(app, container, cards, pilot):
            app.set_focus(app.query_one("#mini-own-agent"), scroll_visible=False)
            await _settle(pilot, 3)
            app.post_message(events.AppFocus())

        self.assertEqual(
            self.run_scenario(scenario), ("mini-own-agent", SCROLL_Y),
            "the focus-in stole focus from a non-card widget",
        )


class RestoreFocusFallbackTests(_FocusCase):
    """The sibling call site: `_restore_focus`'s fallback, reached on every
    refresh tick whose saved card no longer resolves."""

    def test_restore_focus_fallback_does_not_scroll(self):
        """Both halves of the fallback's contract, in one assertion.

        It must STILL focus card 0 (so a later change cannot satisfy "does not
        scroll" by becoming a no-op) and must no longer drag a mid-list reader
        back to the top. The rebuild lock is deliberately clear here — that is
        the state in which the pre-fix `scroll_visible=True` actually landed.
        """
        async def scenario(app, container, cards, pilot):
            app.screen.set_focus(None)
            await _settle(pilot, 3)
            self.assertFalse(
                app._list_scroll_lock,
                "the lock would refuse the scroll on its own, making this "
                "assertion vacuous",
            )
            app._restore_focus(None)

        self.assertEqual(
            self.run_scenario(scenario), (CARD_IDS[0], SCROLL_Y),
            "the passive-refresh fallback did not select card 0, or scrolled "
            "the list away from the anchor the restore owns (t1539)",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
