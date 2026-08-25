"""Tests for minimonitor's list scroll preservation across refresh ticks (t1539).

`MiniMonitorApp._rebuild_pane_list` tears every `MiniPaneCard` down and remounts
it on every status tick. While the container is childless its `max_scroll_y` is
0, so Textual's `validate_scroll_y` clamps `scroll_y` to 0 and the user's
mouse-wheel / scrollbar position is discarded. Measured live in a real 40-column
tmux pane before the fix — `scroll_y` went `8.0 -> 0` between the
`remove_children()` and the end of `mount_all()`, on EVERY tick.

The fix has three parts, and this module covers each:

* `pick_scroll_anchor` / `resolve_anchor_target` — pure, so the anchor rules
  (topmost-visible, sub-card remainder, killed-anchor neighbour fallback) are
  testable without booting an app.
* `MiniPaneList.scroll_to_region` — refuses UNINVITED scrolls while the rebuild
  lock is held. Every one of them (focus's `scroll_visible`, its deferred
  re-post, `Screen.set_focus`'s `scroll_to_center`, the focus Textual re-homes
  when the focused card is torn down) reaches the container through
  `Screen.scroll_to_widget`, which calls `scroll_to_region` on each ancestor.
* `MiniPaneList._scroll_to` — treats any non-`force` arrival as a real user
  gesture and retires the pending restore. No user gesture touches
  `scroll_to_region`, so the two classes are disjoint and neither override needs
  an allowlist of Textual's private `_on_*` handler names.

NEGATIVE CONTROLS. Each is ONE mutation of the source and names the tests that
must fail; all three were run against this file and confirmed failing:

1. Remove the whole scroll-preservation wiring from `_refresh_data` (the
   `_capture_list_scroll()` call, the lock + fail-safe arming, and the trailing
   `call_after_refresh(self._restore_list_scroll, ...)`) — i.e. the pre-fix
   code. `RestoreAcrossRefreshTests.test_mid_list_position_survives_a_refresh_tick`
   then fails with `0 != 6`: the tick discards the position and snaps to the
   top, which IS the reported symptom. Its two siblings and
   `LockLifecycleTests.test_failsafe_unlocks_and_retires_when_the_restore_never_runs`
   fail with it.
2. Delete the `if not force: ... abandon()` body from `MiniPaneList._scroll_to`,
   so no gesture retires the restore. All four
   `UserGestureSupersedesTests` gesture cases fail — including
   `test_thumb_drag_supersedes_pending_restore`, the path an
   enumerate-the-handlers design misses.
3. Delete the `if not kwargs.get("force") and self._locked(): return Offset()`
   body from `MiniPaneList.scroll_to_region`, so uninvited scrolls are no longer
   refused. `LockRefusesUninvitedScrollTests.test_focus_does_not_scroll_while_locked`
   then fails.

Run: python3 tests/test_minimonitor_scroll_preservation.py
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
# pane the suite runs in (t1240).
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from textual import events  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from textual.scrollbar import ScrollDown, ScrollTo  # noqa: E402

from monitor import minimonitor_app as mm  # noqa: E402
from monitor.monitor_core import PaneCategory  # noqa: E402

# Re-exported by minimonitor_app itself; import it from there so this module
# does not pin an internal module path the app is free to change.
TmuxControlState = mm.TmuxControlState


# ---------------------------------------------------------------------------
# Pure anchor math
# ---------------------------------------------------------------------------

class PickScrollAnchorTests(unittest.TestCase):
    """`pick_scroll_anchor` picks the topmost visible card and its remainder."""

    # A section divider occupies y=0, so the cards start at y=1 — the real
    # layout `_rebuild_pane_list` produces in multi-session mode.
    OFFSETS = [("%1", 1), ("%2", 3), ("%3", 5), ("%4", 7)]

    def test_picks_the_last_card_at_or_above_the_offset(self):
        self.assertEqual(mm.pick_scroll_anchor(self.OFFSETS, 5), ("%3", 0))

    def test_remainder_survives_a_position_inside_a_card(self):
        pane_id, delta = mm.pick_scroll_anchor(self.OFFSETS, 6)
        self.assertEqual((pane_id, delta), ("%3", 1))

    def test_offset_above_every_card_anchors_on_the_first(self):
        # Negative delta is deliberate: it is what puts the divider back on
        # screen instead of scrolling it off.
        self.assertEqual(mm.pick_scroll_anchor(self.OFFSETS, 0), ("%1", -1))

    def test_offset_past_the_last_card_anchors_on_the_last(self):
        self.assertEqual(mm.pick_scroll_anchor(self.OFFSETS, 9), ("%4", 2))

    def test_empty_list_has_no_anchor(self):
        self.assertIsNone(mm.pick_scroll_anchor([], 4))

    def test_round_trips_when_nothing_moved(self):
        for scroll_y in range(0, 10):
            pane_id, delta = mm.pick_scroll_anchor(self.OFFSETS, scroll_y)
            top = dict(self.OFFSETS)[pane_id]
            self.assertEqual(top + delta, scroll_y, f"scroll_y={scroll_y}")


class ResolveAnchorTargetTests(unittest.TestCase):
    """`resolve_anchor_target` survives an agent killed between two refreshes."""

    ORDER = ["%1", "%2", "%3", "%4", "%5"]

    def test_surviving_anchor_returns_its_new_offset(self):
        live = {"%1": 0, "%2": 2, "%3": 4}
        self.assertEqual(mm.resolve_anchor_target(self.ORDER, "%3", live), 4)

    def test_killed_anchor_falls_back_to_the_nearest_neighbour_above(self):
        # %3 is gone; %2 (one above) and %4 (one below) are both alive — the
        # above one wins, so the list reads as having closed up.
        live = {"%1": 0, "%2": 2, "%4": 4, "%5": 6}
        self.assertEqual(mm.resolve_anchor_target(self.ORDER, "%3", live), 2)

    def test_falls_through_to_a_farther_survivor(self):
        live = {"%5": 3}
        self.assertEqual(mm.resolve_anchor_target(self.ORDER, "%2", live), 3)

    def test_nothing_survived_returns_none(self):
        self.assertIsNone(mm.resolve_anchor_target(self.ORDER, "%2", {"%9": 1}))

    def test_anchor_absent_from_the_recorded_order_returns_none(self):
        self.assertIsNone(mm.resolve_anchor_target(self.ORDER, "%9", {"%1": 0}))


class ListLayoutPendingTests(unittest.TestCase):
    """`list_layout_pending` — the shared readiness gate for both restore paths."""

    def test_all_cards_at_zero_is_pending(self):
        self.assertTrue(mm.list_layout_pending([0, 0, 0, 0]))

    def test_distinct_offsets_are_ready(self):
        self.assertFalse(mm.list_layout_pending([1, 3, 5, 7]))

    def test_first_card_at_zero_is_still_ready(self):
        # A laid-out list whose first card sits at 0 must NOT read as pending,
        # or the restore would burn its whole retry budget every tick.
        self.assertFalse(mm.list_layout_pending([0, 2, 4]))

    def test_single_card_is_never_pending(self):
        # One card legitimately sits at 0 and there is nothing to scroll.
        self.assertFalse(mm.list_layout_pending([0]))

    def test_empty_is_never_pending(self):
        self.assertFalse(mm.list_layout_pending([]))


# ---------------------------------------------------------------------------
# Behavioural — a real MiniPaneList with real MiniPaneCards
# ---------------------------------------------------------------------------

CARD_IDS = [f"%{i}" for i in range(20)]


async def _async_empty_mapping():
    """`get_session_to_project_mapping_async` stand-in (t1598).

    The refresh path moved onto the async gateway, so the sync sibling is no
    longer called and a `lambda: {}` here would be silently dead.
    """
    return {}


class _ListHost(mm.MiniMonitorApp):
    """The REAL `MiniMonitorApp`, with only its boot sequence neutralised.

    Subclassing rather than standing up a look-alike `App` is deliberate: the
    lock flag, the generation counter and `_abandon_scroll_restore` are what is
    under test, and a host that merely *resembles* the app would pass while the
    production class regressed (a bare `App` silently has no
    `_abandon_scroll_restore` at all, so `MiniPaneList._scroll_to`'s `getattr`
    finds nothing and every gesture assertion goes vacuous).

    The real `on_mount` still runs and is NOT overridden — Textual invokes the
    handler on every class in the MRO, so a subclass override would not suppress
    it anyway. It is neutralised honestly instead: with `TMUX` scrubbed from the
    environment above it takes its own "Not inside tmux" early return, before any
    tmux detection, pane-marker stamping or refresh timer.

    `compose` and `CSS` are NOT overridden either, so the list sits in the real
    40-column layout with the real chrome above it. Only `__init__` is narrowed,
    to the two arguments that have no default.
    """

    def __init__(self) -> None:
        super().__init__(session="t1539", project_root=REPO_ROOT)


def _cards(pane_ids):
    return [mm.MiniPaneCard(pid, f"card {pid}\nsecond line") for pid in pane_ids]


async def _settle(pilot, frames=12):
    for _ in range(frames):
        await pilot.pause()


class _ListCase(unittest.TestCase):
    """Drives a real host app; subclasses implement `scenario`."""

    def run_scenario(self, scenario):
        async def go():
            app = _ListHost()
            async with app.run_test(size=(40, 12)) as pilot:
                container = app.query_one("#mini-pane-list", mm.MiniPaneList)
                await container.mount_all(_cards(CARD_IDS))
                await _settle(pilot, 4)
                return await scenario(app, container, pilot)
        return asyncio.run(go())


class LockRefusesUninvitedScrollTests(_ListCase):
    """The lock turns Textual's own scrolls away; nothing else does."""

    def test_focus_does_not_scroll_while_locked(self):
        # NEGATIVE CONTROL 2 targets this test.
        async def scenario(app, container, pilot):
            container.scroll_to(y=14, animate=False, force=True)
            await _settle(pilot, 3)
            app._list_scroll_lock = True
            list(container.query(mm.MiniPaneCard))[0].focus()
            await _settle(pilot)
            return container.scroll_y

        self.assertEqual(
            self.run_scenario(scenario), 14,
            "focusing the first card scrolled the list while the rebuild lock "
            "was held — the anchor restore is no longer authoritative",
        )

    def test_focus_scrolls_normally_once_unlocked(self):
        """The refusal is scoped to the lock — an active gesture still scrolls.

        Without this the test above would pass vacuously against a container
        that simply never scrolls to a focused card.
        """
        async def scenario(app, container, pilot):
            container.scroll_to(y=14, animate=False, force=True)
            await _settle(pilot, 3)
            app._list_scroll_lock = False
            list(container.query(mm.MiniPaneCard))[0].focus()
            await _settle(pilot)
            return container.scroll_y

        self.assertEqual(self.run_scenario(scenario), 0)

    def test_forced_scroll_passes_through_the_lock(self):
        """The restore's own `force=True` must not be refused by its own lock."""
        async def scenario(app, container, pilot):
            app._list_scroll_lock = True
            container.scroll_to(y=9, animate=False, immediate=True, force=True)
            await _settle(pilot, 4)
            return container.scroll_y

        self.assertEqual(self.run_scenario(scenario), 9)


class UserGestureSupersedesTests(_ListCase):
    """Every user-driven scroll lands AND retires the pending restore."""

    def _gesture_case(self, deliver):
        async def scenario(app, container, pilot):
            app._list_scroll_lock = True
            app._pending_scroll_state = (False, "%0", 0.0, list(CARD_IDS))
            app._scroll_restore_gen = 7
            container.scroll_to(y=14, animate=False, immediate=True, force=True)
            await _settle(pilot, 3)
            await deliver(app, container, pilot)
            await _settle(pilot)
            return container.scroll_y, app._scroll_restore_gen, \
                app._pending_scroll_state, app._list_scroll_lock

        scroll_y, gen, pending, locked = self.run_scenario(scenario)
        self.assertNotEqual(
            scroll_y, 14, "the gesture did not move the list at all")
        self.assertNotEqual(
            gen, 7,
            "the restore generation was not retired — a pending "
            "_restore_list_scroll would still pass its guard and overwrite the "
            "position the user just chose",
        )
        self.assertIsNone(pending, "the stale snapshot was not dropped")
        self.assertFalse(locked, "the lock outlived the superseding gesture")

    def test_thumb_drag_supersedes_pending_restore(self):
        """Scrollbar thumb drag — a `ScrollTo` message, NOT a `_on_mouse_*`
        event. NEGATIVE CONTROL 1 targets this test: it is the path an
        enumerate-the-handlers design misses."""
        async def deliver(app, container, pilot):
            container.post_message(ScrollTo(x=None, y=3.0))
        self._gesture_case(deliver)

    def test_wheel_supersedes_pending_restore(self):
        async def deliver(app, container, pilot):
            container.post_message(events.MouseScrollDown(
                widget=container, x=5, y=5, delta_x=0, delta_y=1, button=0,
                screen_x=5, screen_y=5, shift=False, meta=False, ctrl=False))
        self._gesture_case(deliver)

    def test_scrollbar_trough_click_supersedes_pending_restore(self):
        async def deliver(app, container, pilot):
            container.post_message(ScrollDown())
        self._gesture_case(deliver)

    def test_scroll_key_binding_supersedes_pending_restore(self):
        async def deliver(app, container, pilot):
            container.action_scroll_down()
        self._gesture_case(deliver)

    def test_forced_restore_does_not_retire_its_own_generation(self):
        """The converse: our own restore must not look like a user gesture."""
        async def scenario(app, container, pilot):
            app._scroll_restore_gen = 7
            app._pending_scroll_state = (False, "%0", 0.0, list(CARD_IDS))
            container.scroll_to(y=9, animate=False, immediate=True, force=True)
            container.scroll_end(animate=False, immediate=True, force=True)
            await _settle(pilot, 4)
            return app._scroll_restore_gen, app._pending_scroll_state

        gen, pending = self.run_scenario(scenario)
        self.assertEqual(gen, 7)
        self.assertIsNotNone(pending)



# ---------------------------------------------------------------------------
# End-to-end: the real `_refresh_data`, i.e. the actual reset the bug reports
# ---------------------------------------------------------------------------

def _snap(pane_id: str, window_index: str):
    """Minimal PaneSnapshot stand-in — `_rebuild_pane_list` reads `.pane` only."""
    pane = SimpleNamespace(
        pane_id=pane_id,
        session_name="s1",
        window_index=window_index,
        pane_index="0",
        window_name=f"agent-pick-{window_index}",
        category=PaneCategory.AGENT,
        current_command="python",
    )
    return SimpleNamespace(pane=pane, is_idle=False, idle_seconds=0.0)


class _RefreshHost(_ListHost):
    """`_ListHost` with the tmux-facing collaborators of `_refresh_data` stubbed.

    ONLY the data sources are replaced. `_capture_list_scroll`, the lock/timer
    arming, `_rebuild_pane_list`, `_restore_focus` and `_restore_list_scroll` all
    run for real, which is the point: this drives the very code path that loses
    the offset in production, rather than a hand-copied imitation of it that
    could drift from `_refresh_data`.
    """

    def __init__(self, pane_ids) -> None:
        super().__init__()
        self.set_panes(pane_ids)
        self._monitor = SimpleNamespace(
            multi_session=False,
            capture_all_async=self._capture_all_async,
            get_session_to_project_mapping_async=_async_empty_mapping,
            get_compare_mode=lambda pid: "stripped",
            is_compare_mode_overridden=lambda pid: False,
            get_shadow_snapshot=lambda pid: None,
            control_state=lambda: TmuxControlState.CONNECTED,
        )
        self._task_cache = SimpleNamespace(
            get_task_id=lambda w: None,
            get_task_id_for_pane=lambda p: None,
            get_task_info=lambda t, s=None: None,
            update_session_mapping=lambda m: None,
        )
        self._gate_cache = SimpleNamespace(summary_for=lambda i: None,
                                           clear=lambda: None)

    def set_panes(self, pane_ids) -> None:
        self._pane_ids = list(pane_ids)

    async def _capture_all_async(self):
        return {pid: _snap(pid, str(i + 2))
                for i, pid in enumerate(self._pane_ids)}

    # Tmux-facing no-ops (each hits the real tmux gateway in production).
    def _refresh_marks(self): return None
    def _compute_completed_panes(self): return frozenset()
    async def _update_own_window_info(self): return None
    async def _check_auto_close(self): return None
    def _find_own_window_snapshot(self): return None
    async def _maybe_offer_concerns(self): return None
    async def _maybe_purge_marks(self): return None
    async def _maybe_build_own_agent_panel(self): return None
    def _refresh_own_live_state(self): return None
    def _is_marked(self, snap): return False


class _RefreshCase(unittest.TestCase):
    """Boots `_RefreshHost` and runs one scenario against a real refresh tick."""

    def _run(self, scenario, pane_ids=CARD_IDS):
        async def go():
            app = _RefreshHost(pane_ids)
            async with app.run_test(size=(40, 14)) as pilot:
                await app._refresh_data()
                await _settle(pilot)
                container = app.query_one("#mini-pane-list", mm.MiniPaneList)
                if container.max_scroll_y <= 0:
                    raise AssertionError(
                        "fixture does not overflow — max_scroll_y="
                        f"{container.max_scroll_y}; the test would be vacuous")
                return await scenario(app, container, pilot)
        return asyncio.run(go())


class RestoreAcrossRefreshTests(_RefreshCase):
    """The offset survives a real `_refresh_data` tick — the reported bug."""

    def test_mid_list_position_survives_a_refresh_tick(self):
        async def scenario(app, container, pilot):
            container.scroll_to(y=6, animate=False, immediate=True, force=True)
            await _settle(pilot, 4)
            before = container.scroll_y
            await app._refresh_data()
            await _settle(pilot)
            return before, container.scroll_y

        before, after = self._run(scenario)
        self.assertEqual(before, 6)
        self.assertEqual(
            after, 6,
            "the refresh tick discarded the scroll position — this is the "
            "reported symptom (validate_scroll_y clamps to 0 while the "
            "container is childless)",
        )

    def test_bottom_pinned_list_stays_pinned_when_an_agent_disappears(self):
        async def scenario(app, container, pilot):
            container.scroll_end(animate=False, immediate=True, force=True)
            await _settle(pilot, 4)
            # An agent above the fold is killed between ticks.
            app.set_panes([p for p in CARD_IDS if p != "%1"])
            await app._refresh_data()
            await _settle(pilot)
            return container.scroll_y, container.max_scroll_y

        scroll_y, max_y = self._run(scenario)
        self.assertGreater(max_y, 0)
        self.assertEqual(
            scroll_y, max_y,
            "a bottom-pinned list did not stay pinned after an agent above the "
            "fold was killed",
        )

    def test_killed_anchor_lands_on_a_neighbour_not_at_the_top(self):
        async def scenario(app, container, pilot):
            container.scroll_to(y=6, animate=False, immediate=True, force=True)
            await _settle(pilot, 4)
            # Whichever card is the anchor right now is the one we kill.
            app._capture_list_scroll()
            anchor_id = app._pending_scroll_state[1]
            app._pending_scroll_state = None      # let the tick capture afresh
            app.set_panes([p for p in CARD_IDS if p != anchor_id])
            await app._refresh_data()
            await _settle(pilot)
            return anchor_id, container.scroll_y

        anchor_id, scroll_y = self._run(scenario)
        self.assertNotEqual(
            scroll_y, 0,
            f"killing the anchor card {anchor_id} snapped the list back to the "
            "top instead of settling on its nearest surviving neighbour",
        )
        # One card is two rows tall, so the neighbour fallback lands within a
        # card of where the user was.
        self.assertGreaterEqual(scroll_y, 4)


class EarlyRestoreCallbackTests(_RefreshCase):
    """The restore must survive its callback firing before the layout lands.

    `call_after_refresh` can run before the newly mounted cards have geometry:
    measured live, the container spends part of every tick with
    `max_scroll_y == 0` and EVERY card reporting `virtual_region.y == 0` (320 of
    488 sampled ticks). A restore issued in that window is clamped to 0 by
    `validate_scroll_y` — reproducing the very bug — and because the `finally`
    clears the snapshot and unlocks, no later layout can put the view back.

    The window is made deterministic by running only the FIRST restore callback
    synchronously, at exactly that un-laid-out moment; any retry it schedules is
    deferred normally. That is faithful to the real failure and, unlike faking
    `max_scroll_y`, does not corrupt the scroll arithmetic Textual itself does
    against that property every frame.

    The bottom-pinned path is the one that regressed: its readiness test compared
    `max_scroll_y` against itself, which is vacuously false, so it never retried.
    """

    def _with_early_first_restore(self, scenario):
        async def wrapped(app, container, pilot):
            real_cafr = app.call_after_refresh
            state = {"armed": False, "fired": False}

            def call_after_refresh(callback, *args, **kwargs):
                if (state["armed"] and not state["fired"]
                        and callback == app._restore_list_scroll):
                    state["fired"] = True
                    return callback(*args, **kwargs)
                return real_cafr(callback, *args, **kwargs)

            app.call_after_refresh = call_after_refresh
            try:
                return await scenario(app, container, pilot, state)
            finally:
                app.call_after_refresh = real_cafr

        return self._run(wrapped)

    def test_bottom_pin_survives_an_early_restore_callback(self):
        async def scenario(app, container, pilot, state):
            container.scroll_end(animate=False, immediate=True, force=True)
            await _settle(pilot, 4)
            state["armed"] = True
            await app._refresh_data()
            await _settle(pilot)
            return container.scroll_y, container.max_scroll_y, state["fired"]

        scroll_y, max_y, fired = self._with_early_first_restore(scenario)
        self.assertTrue(fired, "the early callback never fired — test is vacuous")
        self.assertGreater(max_y, 0)
        self.assertEqual(
            scroll_y, max_y,
            "the bottom-pinned list was restored before the rebuilt list had a "
            "scroll range, so scroll_end clamped it to 0 and the cleared "
            "snapshot left nothing to re-pin it",
        )

    def test_anchor_restore_survives_an_early_restore_callback(self):
        async def scenario(app, container, pilot, state):
            container.scroll_to(y=6, animate=False, immediate=True, force=True)
            await _settle(pilot, 4)
            state["armed"] = True
            await app._refresh_data()
            await _settle(pilot)
            return container.scroll_y, state["fired"]

        scroll_y, fired = self._with_early_first_restore(scenario)
        self.assertTrue(fired, "the early callback never fired — test is vacuous")
        self.assertEqual(scroll_y, 6)


class LockLifecycleTests(_RefreshCase):
    """Post-phase mitigation `assert_lock_never_sticks` (t1539).

    A lock that sticks silently kills scroll-into-view for the rest of the
    session, so the two ways it could stick are asserted directly rather than
    inferred from the happy path.
    """

    def test_lock_and_snapshot_clear_after_every_tick(self):
        async def scenario(app, container, pilot):
            observed = []
            for _ in range(4):
                await app._refresh_data()
                await _settle(pilot)
                observed.append(
                    (app._list_scroll_lock, app._pending_scroll_state))
            return observed

        for i, (locked, pending) in enumerate(self._run(scenario)):
            self.assertFalse(locked, f"lock still held after tick {i}")
            self.assertIsNone(pending, f"snapshot still pending after tick {i}")

    def test_failsafe_unlocks_and_retires_when_the_restore_never_runs(self):
        """The fail-safe is armed on the ACQUISITION line, not inside the
        restore — so a restore that never completes still releases the lock.

        DEVIATION from the plan, which said to make `_restore_list_scroll`
        *raise*. Raising is the less faithful model AND untestable here:
        `Screen._invoke_and_clear_callbacks` has no per-callback `try`, so the
        real consequence of an exception in that batch is that the restore is
        never invoked at all — and a raise inside the batch is stored on the app
        and re-raised by `run_test` on exit, failing the test regardless of the
        behaviour under examination. A restore that silently never completes
        reproduces the exact state the fail-safe exists for.
        """
        async def scenario(app, container, pilot):
            app._restore_list_scroll = lambda gen, attempt=0: None
            gen_before = app._scroll_restore_gen
            await app._refresh_data()
            await _settle(pilot, 4)
            locked_immediately = app._list_scroll_lock
            # Wait past the acquisition-line fail-safe.
            await asyncio.sleep(app._SCROLL_LOCK_TIMEOUT + 0.3)
            await _settle(pilot, 4)
            return (gen_before, locked_immediately, app._list_scroll_lock,
                    app._pending_scroll_state, app._scroll_restore_gen)

        gen_before, locked_now, locked_after, pending, gen_after = \
            self._run(scenario)
        self.assertTrue(
            locked_now, "the lock was never taken — the test proves nothing")
        self.assertFalse(
            locked_after,
            "the fail-safe did not release the lock after a restore that never "
            "completed; scroll-into-view is dead for the rest of the session",
        )
        self.assertIsNone(pending)
        self.assertGreater(
            gen_after, gen_before + 1,
            "the fail-safe unlocked but did not RETIRE the generation — a late "
            "_restore_list_scroll would still pass its own guard",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
