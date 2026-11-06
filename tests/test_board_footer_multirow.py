#!/usr/bin/env python3
"""Board adoption of the multi-row footer (t1418).

`tests/test_multirow_footer.py` covers the widget itself. This module covers the
board's side of the change: that it mounts the widget at all, that the four keys
hidden only for lack of footer room are now footer-visible, that the keys the
`ViewSelector` already surfaces stayed hidden, and that `check_action` gating
still reaches the rendered footer.

Footer assertions are keyed by **action**, not by key, so a user's shortcut remap
cannot break them — the same rule `tests/test_syncer_rows.py` follows.

Mounted footer reads go through `_board_ready` / `_footer_ready` — a sentinel
ordered on the footer's own pump, recompose counters, a trigger witness and a
non-empty *settled* footer — never a bare `pilot.pause()`, which waits only for
CPU idleness and under load can read a footer that is unbuilt, mid-recompose or
stale (t2218).
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402
from multirow_footer import MultiRowFooter, OverflowHint  # noqa: E402
from textual.widgets._footer import FooterKey  # noqa: E402

#: Hidden by t1243_7 and friends *only* because the single-row footer was full.
UNHIDDEN = {
    "move_to_column",
    "toggle_column_collapsed",
    "move_task_top",
    "move_task_bottom",
}

#: Already rendered by the ViewSelector filter row — a footer entry would
#: duplicate, not reveal.
STAY_HIDDEN = {
    "view_all",
    "view_locked",
    "view_free",
    "view_inflight",
    "view_bytopic",
    "view_bytrail",
    "view_git",
    "view_type",
}


# -- Footer readiness (t2218) --------------------------------------------------
#
# Textual's Footer composes nothing until `bindings_updated` fires; its handler
# then queues `recompose` on the footer's own pump (call_after_refresh), and the
# recompose itself is async (remove, then mount). `MultiRowFooter.on_resize`
# queues one more after a height change. A focus change, a blur or a view switch
# restarts the chain. One `pilot.pause()` covers none of that by ordering.

_SETTLE_TIMEOUT = 10.0
_QUIET_ROUNDS = 2
_ORIG_RECOMPOSE = MultiRowFooter.recompose


# Mirrors `_until` in tests/test_monitor_shadow_zone.py (t2210), verbatim.
async def _until(pilot, predicate, what, *, timeout=_SETTLE_TIMEOUT,
                 deadline=None):
    """Pump the app until `predicate()` holds, all within the budget.

    The budget is `timeout` seconds from now, or an absolute loop-time
    `deadline` shared with a caller (`_settle` passes its whole-call deadline,
    so several waits draw on one budget). It bounds each pump as well as the
    loop: `pilot.pause()` can block for up to 30s on its own
    (`Pilot._wait_for_screen`), so an unbounded pump would overrun the
    deadline, and a predicate turning true during it would report success
    after the budget had already been spent. A success observed past the
    deadline is therefore rejected too.
    """
    loop = asyncio.get_running_loop()
    start = loop.time()
    if deadline is None:
        deadline = start + timeout

    def _late(reason: str) -> AssertionError:
        return AssertionError(
            f"{reason} after {loop.time() - start:.3f}s "
            f"(budget left at entry {deadline - start:.3f}s) waiting for {what}")

    while True:
        if predicate():
            if loop.time() > deadline:
                raise _late("condition held only past the deadline")
            return
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise _late("timed out")
        try:
            await asyncio.wait_for(pilot.pause(), remaining)
        except asyncio.TimeoutError:
            raise _late("pilot.pause() overran the remaining budget") from None


async def _counting_recompose(self):
    """`MultiRowFooter.recompose`, counting starts and completions."""
    self._test_recompose_started = getattr(self, "_test_recompose_started", 0) + 1
    try:
        await _ORIG_RECOMPOSE(self)
    finally:
        self._test_recompose_finished = (
            getattr(self, "_test_recompose_finished", 0) + 1)


def _started(app) -> int:
    return getattr(app.query_one(MultiRowFooter), "_test_recompose_started", 0)


def _finished(app) -> int:
    return getattr(app.query_one(MultiRowFooter), "_test_recompose_finished", 0)


async def _footer_ready(app, pilot, *, since=None, timeout=_SETTLE_TIMEOUT,
                        _on_pending=None):
    """Return only once the footer is settled, witnessed and non-empty.

    - **quiet**: for `_QUIET_ROUNDS` consecutive rounds no recompose started or
      was in flight. Each round's sentinel is posted through the FOOTER's pump,
      so FIFO puts it behind any recompose already queued there, and screen
      after-refresh callbacks are awaited in order — so a queued recompose has
      finished by the time the sentinel fires, and so has the repaint after it.
    - **witnessed**: a recompose started after the caller's trigger snapshot
      `since` (None = no trigger to witness). Quiet rounds alone cannot tell
      "drained" from "the producer has not run yet".
    - **non-empty**: FooterKeys are present in the SETTLED state, so a recompose
      that empties a populated footer is reported, never passed vacuously.

    Every failure route — including a timeout inside a sentinel wait — raises
    one `footer not ready (...)` error carrying the live state. `_on_pending` is
    a test-only observer, called only on rounds that declined to return.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    footer = app.query_one(MultiRowFooter)
    quiet, witnessed = 0, since is None

    def _not_ready(reason: str) -> AssertionError:
        keys_now = bool(list(app.query(FooterKey)))
        return AssertionError(
            f"footer not ready ({reason}): quiet={quiet} witnessed={witnessed} "
            f"keys={keys_now} started={_started(app)} "
            f"finished={_finished(app)} since={since}")

    while True:
        before = _started(app)
        fired: list[bool] = []
        footer.call_after_refresh(fired.append, True)
        try:
            await _until(pilot, lambda: bool(fired),
                         "footer after-refresh sentinel", deadline=deadline)
        except AssertionError as exc:
            raise _not_ready(f"sentinel wait: {exc}") from exc
        started, finished = _started(app), _finished(app)
        quiet = quiet + 1 if (started == before and finished == started) else 0
        witnessed = since is None or started > since
        keys = bool(list(app.query(FooterKey)))
        if quiet >= _QUIET_ROUNDS and witnessed and keys:
            if loop.time() > deadline:
                raise _not_ready("ready only past the deadline")
            return
        if _on_pending is not None:
            _on_pending(quiet=quiet, witnessed=witnessed, keys=keys)
        if loop.time() > deadline:
            raise _not_ready("timed out")


class _FooterReadinessBase(bf.FixtureBoardTestBase, unittest.TestCase):
    """Fixture board + recompose counters + the board-level readiness waits."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KanbanApp = cls.ab.KanbanApp
        cls.TaskCard = cls.ab.TaskCard
        cls.TopicColumn = cls.ab.TopicColumn

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(
            MultiRowFooter, "recompose", _counting_recompose)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _run(self, coro):
        return asyncio.run(coro)

    async def _board_ready(self, app, pilot):
        """Cards mounted, startup focus landed, footer built and settled.

        `BoardScreen.AUTO_FOCUS` is "", so a non-None focus is the startup
        claim (`call_after_refresh(_claim_startup_focus)` → `focus()` →
        `call_later`) having landed — it can no longer override a test's own
        focus or blur afterwards.
        """
        await _until(pilot, lambda: list(app.query(self.TaskCard)),
                     "task cards to mount")
        await _until(pilot, lambda: app.focused is not None,
                     "board startup focus to land")
        await _footer_ready(app, pilot, since=0)

    async def _focus_and_settle(self, app, pilot, widget):
        """Focus `widget` (None = blur), wait for it to land, settle the footer."""
        was = app.focused
        snap = _started(app)
        if widget is None:
            app.screen.set_focus(None)
        else:
            widget.focus()
        await _until(pilot, lambda: app.focused is widget,
                     f"focus to land on {widget!r}")
        # Unchanged focus publishes nothing, so there is no recompose to witness.
        await _footer_ready(app, pilot,
                            since=snap if was is not widget else None)


class BoardMultiRowFooterTests(_FooterReadinessBase):

    @staticmethod
    def _rendered_actions(app) -> set[str]:
        """Actions with a FooterKey actually mounted in the footer."""
        return {key.action for key in app.query(FooterKey)}

    def _declared(self, action):
        return next(
            b
            for b in self.KanbanApp.BINDINGS
            if getattr(b, "action", None) == action
        )

    def test_fixture_facts(self):
        """Preconditions, so the assertions below cannot pass vacuously."""

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 48)) as pilot:
                await self._board_ready(app, pilot)
                self.assertTrue(
                    list(app.query(self.TaskCard)),
                    "fixture must render at least one task card",
                )
                self.assertTrue(
                    list(app.query(FooterKey)),
                    "fixture must render footer keys",
                )

        self._run(go())

    def test_the_board_mounts_the_multi_row_footer(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 48)) as pilot:
                await pilot.pause()
                footer = app.query_one(MultiRowFooter)
                self.assertFalse(footer.can_focus)

        self._run(go())

    def test_the_footer_wraps_at_200_columns(self):
        """The whole point: the board's key set no longer fits on one row."""

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 48)) as pilot:
                await self._board_ready(app, pilot)
                self.assertGreater(app.query_one(MultiRowFooter).size.height, 1)

        self._run(go())

    def test_no_footer_key_is_clipped(self):
        async def go():
            for width in (200, 160, 120):
                app = self.KanbanApp()
                async with app.run_test(size=(width, 48)) as pilot:
                    await self._board_ready(app, pilot)
                    for key in app.query(FooterKey):
                        self.assertLessEqual(
                            key.region.right,
                            width,
                            f"{key.key} clipped at {width} cols",
                        )

        self._run(go())

    def test_the_four_previously_hidden_keys_are_declared_shown(self):
        for action in UNHIDDEN:
            self.assertTrue(
                self._declared(action).show,
                f"{action} should be footer-visible after t1418",
            )

    def test_the_four_previously_hidden_keys_reach_the_rendered_footer(self):
        """Declared `show=True` is necessary but not sufficient — check render.

        `move_to_column` is gated by `check_action` on a focused card, so focus
        one first; the other three are ungated.
        """

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 48)) as pilot:
                await self._board_ready(app, pilot)
                card = next(c for c in app.query(self.TaskCard) if not c.is_child)
                await self._focus_and_settle(app, pilot, card)
                rendered = self._rendered_actions(app)
                for action in sorted(UNHIDDEN):
                    self.assertIn(action, rendered, f"{action} missing from footer")

        self._run(go())

    def test_view_filter_keys_stay_hidden(self):
        """The ViewSelector renders these; a footer copy would duplicate."""
        for action in STAY_HIDDEN:
            self.assertFalse(
                self._declared(action).show,
                f"{action} is surfaced by ViewSelector and must stay hidden",
            )

    def test_plain_navigation_keys_stay_hidden(self):
        for action in ("nav_up", "nav_down", "nav_left", "nav_right",
                       "focus_search", "focus_board"):
            self.assertFalse(self._declared(action).show, f"{action} should stay hidden")

    def test_check_action_gating_still_reaches_the_footer(self):
        """A shown binding must still disappear when its gate says False.

        Assert the hidden half FIRST: a gate that never hides anything would let
        the "shown" half pass on its own.
        """

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 48)) as pilot:
                await self._board_ready(app, pilot)
                # Blur explicitly to reach the no-focused-card case. It used to
                # be the boot state, but since t1491 the board claims startup
                # focus, so relying on boot would silently test the SHOWN half
                # twice and never exercise the gate's False branch.
                await self._focus_and_settle(app, pilot, None)
                self.assertNotIn("move_to_column", self._rendered_actions(app))

                card = next(c for c in app.query(self.TaskCard) if not c.is_child)
                await self._focus_and_settle(app, pilot, card)
                self.assertIn("move_to_column", self._rendered_actions(app))

                # `base_filter` is assigned synchronously, so it orders
                # nothing. The view chain ends with refresh_board's queued
                # `_refocus_card` landing on a card inside a TopicColumn
                # (`apply_filter` runs before it in the same FIFO); the
                # switch's own `refresh_bindings()` is the witnessed trigger.
                snap = _started(app)
                app._set_base_filter("bytopic")
                await _until(
                    pilot,
                    lambda: isinstance(app.focused, self.TaskCard) and any(
                        isinstance(a, self.TopicColumn)
                        for a in app.focused.ancestors),
                    "bytopic refocus to land")
                await _footer_ready(app, pilot, since=snap)
                self.assertNotIn("move_to_column", self._rendered_actions(app))

        self._run(go())

    def test_the_overflow_hint_names_the_editor_key_the_footer_shows(self):
        """The hint must agree with the rendered editor binding, whatever it is.

        Asserted as an *agreement* between two surfaces rather than against the
        literal `?`, so it stays true under a rebind. The widget derives the
        display from the composed binding (Textual already resolved it through
        `app.get_key_display`); a `resolve_key("board", "open_shortcuts_editor")`
        lookup could not, because that action is registered under the `shared`
        scope and is deliberately not shadowed into the app scope.
        """

        async def go():
            app = self.KanbanApp()
            # 70 rather than 80: wide enough to still render the editor key,
            # narrow enough that the hint survives a key or two leaving the
            # board's shown set, so this test fails for its own reason only.
            async with app.run_test(size=(70, 48)) as pilot:
                await self._board_ready(app, pilot)
                hints = list(app.query(OverflowHint))
                self.assertTrue(hints, "expected an overflow hint at 70 cols")
                editor = [
                    k
                    for k in app.query(FooterKey)
                    if k.action == "open_shortcuts_editor"
                ]
                self.assertTrue(editor, "editor binding must be footer-visible")
                self.assertIn(f"({editor[0].key_display})", str(hints[0].content))

        self._run(go())


class FooterReadinessHelperTests(_FooterReadinessBase):
    """Pin `_footer_ready`'s exit conditions, not just argue them (t2218)."""

    def test_readiness_rejects_a_footer_emptied_after_it_was_populated(self):
        """A populated → empty recompose must raise, never return empty."""

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 48)) as pilot:
                await self._board_ready(app, pilot)
                footer = app.query_one(MultiRowFooter)
                # `compose(node)` calls `node.compose()`, so the instance
                # attribute shadows the class method for the next recompose.
                footer.compose = lambda: iter(())
                snap = _started(app)
                footer.call_after_refresh(footer.recompose)
                with self.assertRaisesRegex(
                        AssertionError, r"footer not ready .*keys=False"):
                    await _footer_ready(app, pilot, since=snap, timeout=1.5)
                # Not vacuous: the emptying recompose really completed.
                self.assertGreater(_finished(app), snap)

        self._run(go())

    def test_readiness_stays_pending_while_the_bindings_update_is_withheld(self):
        """The trigger witness, not quiet-round timing, carries the ordering.

        The producer is coordinated explicitly: the update is withheld until the
        helper has declined to return on two quiet, non-empty, unwitnessed
        rounds, then released. No timer, so the outcome does not depend on how
        fast the pumps run.
        """

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 48)) as pilot:
                await self._board_ready(app, pilot)
                snap = _started(app)
                pending = asyncio.Event()
                seen: list[dict] = []

                def on_pending(**state):
                    seen.append(state)
                    blocked_only_by_witness = [
                        s for s in seen
                        if s["quiet"] >= _QUIET_ROUNDS and s["keys"]
                        and not s["witnessed"]]
                    if len(blocked_only_by_witness) >= 2:
                        pending.set()

                task = asyncio.create_task(_footer_ready(
                    app, pilot, since=snap, _on_pending=on_pending))
                waiter = asyncio.create_task(pending.wait())
                try:
                    done, _ = await asyncio.wait(
                        {task, waiter}, timeout=_SETTLE_TIMEOUT,
                        return_when=asyncio.FIRST_COMPLETED)
                    self.assertNotIn(
                        task, done,
                        "readiness returned while the update was withheld")
                    self.assertTrue(pending.is_set(), f"never pending: {seen}")
                    self.assertEqual(_started(app), snap)

                    app.refresh_bindings()  # release the withheld update
                    await asyncio.wait_for(task, _SETTLE_TIMEOUT)
                    self.assertGreater(_started(app), snap)
                    self.assertEqual(_finished(app), _started(app))
                finally:
                    waiter.cancel()
                    if not task.done():
                        task.cancel()

        self._run(go())


if __name__ == "__main__":
    unittest.main(verbosity=2)
