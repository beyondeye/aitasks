"""Real key-routing tests for the `space` mark binding (t1326).

Calling `action_toggle_mark()` directly proves nothing about how Textual
*routes* the key, so these tests drive `pilot.press("space")` against a mounted
app. Every negative assertion is paired with a positive control, because a test
that never routes the key at all would "pass" the negative case for entirely the
wrong reason.

WHAT ACTUALLY PROTECTS THE MODAL CASE. Measured, not assumed: Textual does
**not** dispatch App-level `BINDINGS` while a `ModalScreen` is active, so
`space` never reaches the toggle action from inside a dialog. The live-focus
guard in `action_toggle_mark` is NOT what saves this case — replacing
`_get_focused_pane_id()` with the cached `_focused_pane_id` leaves the modal
tests green. That guard earns its place elsewhere (focus moved off the card
without a modal — see `test_space_with_focus_off_the_card_does_not_toggle`,
which the same mutation DOES break).

The modal tests are therefore a regression pin on Textual's screen-scoped
dispatch, guarding against a version change or a key-forwarding modal
reintroducing the hazard — not a test of our own guard. Stating it the other way
round would misattribute the protection and invite someone to delete the real
one.

THE TWO APPS ARE NO LONGER SYMMETRIC (t1383). The minimonitor retargeted
`space` at the agent it *follows*, so it does not consult focus at all: the
live-focus guard — and the focus-off test that justifies it — now belong to the
full monitor alone, and the minimonitor's counterpart asserts the opposite
(no focus, still toggles). That also makes the modal pin *more* load-bearing on
the minimonitor side: there is no focus guard left behind it, so Textual's
screen-scoped dispatch is the only thing keeping `space` out of a dialog.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from textual.app import ComposeResult  # noqa: E402
from textual.screen import ModalScreen  # noqa: E402
from textual.widgets import Static  # noqa: E402

import agent_marks  # noqa: E402
from monitor.minimonitor_app import MiniMonitorApp  # noqa: E402
from monitor.monitor_app import MonitorApp  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    PaneCategory, PaneSnapshot, TmuxPaneInfo,
)

SESSION = "demo"


class _PlainModal(ModalScreen):
    """A modal with NO space handler — the risky shape this test guards."""

    def compose(self) -> ComposeResult:
        yield Static("a dialog that does not handle space", id="plain-modal-body")


class _FakeMonitor:
    """Enough surface that a stray refresh tick is a harmless no-op.

    The refresh timer is stopped during instrumentation, but `on_mount` also
    schedules one immediate `call_later(self._refresh_data)` whose bound method
    is already captured — so the capture path must be safe to enter rather than
    merely unscheduled.
    """

    multi_session = False

    def __init__(self, root): self._mapping = {SESSION: root}
    def get_session_to_project_mapping(self): return self._mapping
    async def get_session_to_project_mapping_async(self): return self._mapping
    def get_compare_mode(self, pane_id): return "stripped"
    def is_compare_mode_overridden(self, pane_id): return False
    def get_shadow_snapshot(self, pane_id): return None
    def get_shadow_snapshots(self): return {}
    capture_generation = 0
    async def capture_all_classified_async(self): return (0, [])
    def commit_snapshots(self, gen, classified): return None
    async def capture_all_async(self): return None
    def invalidate_sessions_cache(self): pass
    def discover_window_panes(self, window_id): return []


def snapshot(window="agent-t1", pane_id="%1", window_index="1") -> PaneSnapshot:
    return PaneSnapshot(
        pane=TmuxPaneInfo(
            window_index=window_index, window_name=window, pane_index="0",
            pane_id=pane_id, pane_pid=4242, current_command="node",
            width=80, height=24, category=PaneCategory.AGENT,
            session_name=SESSION,
        ),
        content="x", timestamp=0.0, idle_seconds=1.0, is_idle=False,
    )


class SpaceDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.store = self.tmp / "marks.json"
        self.root = self.tmp / "repo"
        self.root.mkdir()

    def _instrument(self, app, calls: list[list[str]]) -> None:
        """Wire the app to an isolated store and record writer invocations.

        The real refresh timer is stopped first: this suite is about key
        routing, and letting the live capture pipeline run against a stub
        monitor would only add unrelated failures.
        """
        async def fake_cmd(args):
            calls.append(list(args))
            return (0, "MARKED:x|y")

        if getattr(app, "_refresh_timer", None) is not None:
            app._refresh_timer.stop()
            app._refresh_timer = None
        app._monitor = _FakeMonitor(self.root)
        app._marks_view = agent_marks.MarksView(self.store)
        app._marks_purge_due_at = float("inf")  # keep the purge out of the way
        app._marks_purge_inflight = False
        app._run_marks_cmd = fake_cmd
        app._set_session_root_map(app._monitor.get_session_to_project_mapping())
        # Two agents: `%1` in window 1 (the minimonitor's own window, so it is
        # the FOLLOWED agent and is excluded from the list) and `%2` in window 2
        # (a selectable list card). The minimonitor needs both since t1383 —
        # `space` targets the followed agent while a *different* card holds
        # focus, so a single snapshot could not tell the two resolutions apart.
        app._snapshots = {"%1": snapshot(), "%2": snapshot(
            window="agent-t2", pane_id="%2", window_index="2")}
        app._session = SESSION
        app._own_window_index = "1"

    # -- minimonitor -------------------------------------------------------

    def test_minimonitor_space_toggles_the_followed_agent(self):
        """POSITIVE CONTROL. If this fails, the negative test below is vacuous.

        Also pins the t1383 routing at the real key level: a *different* card
        holds focus, and the write still targets the followed agent.
        """
        calls: list[list[str]] = []

        async def runner():
            app = MiniMonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=(40, 30)) as pilot:
                self._instrument(app, calls)
                await app._rebuild_pane_list()
                await pilot.pause()
                cards = list(app.query("#mini-pane-list MiniPaneCard"))
                self.assertTrue(cards, "no MiniPaneCard mounted")
                cards[0].focus()
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()

        asyncio.run(runner())
        self.assertEqual(len(calls), 1, "space must reach the toggle action")
        self.assertEqual(calls[0][0], "toggle")
        self.assertEqual(
            calls[0][2], "agent-t1",
            "space must target the followed agent, not the focused card",
        )

    def test_minimonitor_space_inside_a_modal_does_not_toggle(self):
        calls: list[list[str]] = []

        async def runner():
            app = MiniMonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=(40, 30)) as pilot:
                self._instrument(app, calls)
                await app._rebuild_pane_list()
                await pilot.pause()
                cards = list(app.query("#mini-pane-list MiniPaneCard"))
                cards[0].focus()
                await pilot.pause()
                app.push_screen(_PlainModal())
                await pilot.pause()
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()

        asyncio.run(runner())
        self.assertEqual(
            calls, [],
            "space leaked through a pushed modal and toggled a mark invisibly",
        )

    # -- full monitor ------------------------------------------------------

    def test_monitor_space_toggles_when_a_card_is_focused(self):
        """POSITIVE CONTROL for the full monitor."""
        calls: list[list[str]] = []

        async def runner():
            app = MonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=(100, 30)) as pilot:
                self._instrument(app, calls)
                app._rebuild_pane_list()
                await pilot.pause()
                cards = list(app.query("#pane-list PaneCard"))
                self.assertTrue(cards, "no PaneCard mounted")
                cards[0].focus()
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()

        asyncio.run(runner())
        self.assertEqual(len(calls), 1, "space must reach the toggle action")

    def test_monitor_space_inside_a_modal_does_not_toggle(self):
        calls: list[list[str]] = []

        async def runner():
            app = MonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=(100, 30)) as pilot:
                self._instrument(app, calls)
                app._rebuild_pane_list()
                await pilot.pause()
                cards = list(app.query("#pane-list PaneCard"))
                cards[0].focus()
                await pilot.pause()
                app.push_screen(_PlainModal())
                await pilot.pause()
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()

        asyncio.run(runner())
        self.assertEqual(
            calls, [],
            "space leaked through a pushed modal and toggled a mark invisibly",
        )

    def test_monitor_space_with_focus_off_the_card_does_not_toggle(self):
        """THIS is what the live-focus guard buys — in the full monitor.

        No modal — focus has simply moved to another widget. The cached
        `_focused_pane_id` still holds the last card (it is only updated by
        `on_descendant_focus`, which never fires for a non-card widget), so an
        implementation reading the cached field would toggle a mark the user is
        no longer pointing at. Swapping `_get_focused_pane_id()` for
        `self._focused_pane_id` makes this test fail — unlike the modal tests.

        Asserted against the monitor since t1383: the minimonitor no longer
        consults focus at all, so it cannot exhibit this failure (and the
        opposite is now correct there — see the next test).
        """
        calls: list[list[str]] = []

        async def runner():
            app = MonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=(100, 30)) as pilot:
                self._instrument(app, calls)
                app._rebuild_pane_list()
                await pilot.pause()
                cards = list(app.query("#pane-list PaneCard"))
                self.assertTrue(cards, "no PaneCard mounted")
                cards[0].focus()
                await pilot.pause()
                self.assertEqual(app._focused_pane_id, "%1")
                # Move focus off the card; the cached field deliberately stays.
                app.set_focus(None)
                await pilot.pause()
                self.assertEqual(
                    app._focused_pane_id, "%1",
                    "cached field is expected to be stale here — that is the point",
                )
                await pilot.press("space")
                await pilot.pause()

        asyncio.run(runner())
        self.assertEqual(
            calls, [], "toggled a mark for a card that no longer has focus"
        )

    def test_minimonitor_space_with_no_focus_still_toggles_the_followed_agent(self):
        """The t1383 inversion, at the real key level.

        Focus is irrelevant in the minimonitor, so "nothing focused" is not a
        reason to do nothing — it still marks the agent this pane follows.
        Together with the modal test above this also shows the modal pin is now
        MORE load-bearing here: there is no focus guard left behind it.
        """
        calls: list[list[str]] = []

        async def runner():
            app = MiniMonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=(40, 30)) as pilot:
                self._instrument(app, calls)
                await app._rebuild_pane_list()
                await pilot.pause()
                app.set_focus(None)
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()

        asyncio.run(runner())
        self.assertEqual(len(calls), 1, "space must reach the toggle action")
        self.assertEqual(calls[0][2], "agent-t1")

    def test_monitor_space_outside_the_pane_list_zone_does_not_toggle(self):
        """check_action gates pane-list bindings by zone, so `space` keeps being
        forwarded to the tmux pane in the preview zone, as it was before t1326."""
        from monitor.monitor_app import Zone
        calls: list[list[str]] = []

        async def runner():
            app = MonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=(100, 30)) as pilot:
                self._instrument(app, calls)
                app._rebuild_pane_list()
                await pilot.pause()
                app._active_zone = Zone.PREVIEW
                app.refresh_bindings()
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()

        asyncio.run(runner())
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
