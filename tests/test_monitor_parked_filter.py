"""The `P` parked-visibility filter and its consumers (t1685).

Parking an agent has to be honoured by every surface that partitions agents, or
the surfaces disagree with each other: the pane list stops showing a row while
the session bar still counts it as idle, or auto-switch focuses a card that is
not rendered. This module pins the whole set in one place:

- the row render (`P` + `parked`, and NO state dot),
- the list filter and its rebuild trigger,
- focus handoff when the focused card is the one being hidden — including the
  reachable single-agent case where NO card remains,
- the preview, which must say "parked" rather than render an empty capture,
- the session bar's four-way partition,
- auto-switch, in both its awaiting and its idle branch.

Mock-based on unmounted apps, plus one mounted-widget check for the row so the
render assertion is not made only against a string the app never displays.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import PropertyMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import agent_marks  # noqa: E402
from rich.text import Text  # noqa: E402

from monitor.minimonitor_app import MiniMonitorApp  # noqa: E402
from monitor.monitor_app import MonitorApp, PaneCard, Zone  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    PaneCategory, PaneSnapshot, TmuxPaneInfo,
)
from monitor.monitor_shared import (  # noqa: E402
    MARK_EMPTY_GLYPH, MARK_GLYPH, PARK_GLYPH,
)
from monitor.tmux_control import TmuxControlState  # noqa: E402

SESSION = "demo"


def pane(window: str, *, pane_id: str = "%1", window_index: str = "1",
         category: PaneCategory = PaneCategory.AGENT) -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index=window_index, window_name=window, pane_index="0",
        pane_id=pane_id, pane_pid=4242, current_command="node",
        width=80, height=24, category=category, session_name=SESSION,
    )


def snapshot(window: str, *, parked: bool = False, is_idle: bool = False,
             awaiting: bool = False, idle_seconds: float = 1.0,
             **kw) -> PaneSnapshot:
    """A live snapshot, or the minimal one `commit_snapshots` builds for a
    parked pane (empty content, no verdict)."""
    if parked:
        return PaneSnapshot(
            pane=pane(window, **kw), content="", timestamp=0.0,
            idle_seconds=0.0, is_idle=False, awaiting_input=False, parked=True,
        )
    return PaneSnapshot(
        pane=pane(window, **kw), content="hello", timestamp=0.0,
        idle_seconds=idle_seconds, is_idle=is_idle, awaiting_input=awaiting,
    )


class _FakeMonitor:
    multi_session = False

    def __init__(self, root: Path) -> None:
        self._mapping = {SESSION: root}

    def get_session_to_project_mapping(self): return self._mapping
    async def get_session_to_project_mapping_async(self): return self._mapping
    def get_compare_mode(self, pane_id): return "stripped"
    def is_compare_mode_overridden(self, pane_id): return False
    def get_shadow_snapshot(self, pane_id): return None
    def get_shadow_snapshots(self): return {}
    def control_state(self): return TmuxControlState.CONNECTED


class _FakeTaskCache:
    def get_task_id_for_pane(self, pane): return None
    def get_task_info(self, task_id, session=None): return None
    def update_session_mapping(self, mapping): pass


class _Fixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.store = self.tmp / "marks.json"
        self.root = self.tmp / "repo"
        self.root.mkdir()

    def park(self, window: str) -> None:
        """Drive the real cycle to `parked` rather than hand-writing a record."""
        mf = agent_marks.load(self.store)
        agent_marks.cycle(mf, self.root, window)
        agent_marks.cycle(mf, self.root, window)
        agent_marks.dump(mf, self.store)

    def app(self, cls, snaps=None):
        app = cls.__new__(cls)
        app._monitor = _FakeMonitor(self.root)
        app._session = SESSION
        app._project_root = self.root
        app._task_cache = _FakeTaskCache()
        app._completed_pane_ids = frozenset()
        app._has_fresh_concerns = lambda pane_id: False
        app._snapshots = {s.pane.pane_id: s for s in (snaps or [])}
        app._focused_pane_id = None
        app._selected_card_pane_id = None
        app._hide_parked = False
        app._parked_pane_ids = frozenset(
            pid for pid, s in app._snapshots.items() if s.parked
        )
        app._marks_view = agent_marks.MarksView(self.store)
        app._marks_purge_due_at = float("inf")
        app._marks_purge_inflight = False
        app._set_session_root_map(app._monitor.get_session_to_project_mapping())
        app._refresh_marks()
        return app

    @staticmethod
    def row(app, snap) -> str:
        builder = (
            app._agent_card_text if isinstance(app, MiniMonitorApp)
            else app._format_agent_card_text
        )
        return Text.from_markup(builder(snap)).plain


BOTH_APPS = (MonitorApp, MiniMonitorApp)


class ParkedRowRenderTests(_Fixture):
    """AC2 — the placeholder, and what must NOT be on the row."""

    def test_parked_row_shows_the_glyph_and_the_marker(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.park("agent-p")
                snap = snapshot("agent-p", parked=True)
                plain = self.row(self.app(cls, [snap]), snap)
                self.assertIn(PARK_GLYPH, plain)
                self.assertIn("agent-p", plain)
                self.assertIn("parked", plain)

    def test_parked_row_has_no_state_dot_and_no_status(self):
        """A frozen ● would read as a live idle/active verdict that is in fact
        arbitrarily stale — the pane was never captured."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.park("agent-p")
                snap = snapshot("agent-p", parked=True)
                plain = self.row(self.app(cls, [snap]), snap)
                for forbidden in ("●", "◆", "≈", "=", "IDLE", "PROMPT",
                                  "Active", MARK_GLYPH, MARK_EMPTY_GLYPH):
                    self.assertNotIn(forbidden, plain, forbidden)

    def test_an_unparked_row_still_carries_the_dot(self):
        """Positive control: the assertions above discriminate on `parked`,
        not on the fixture happening to render nothing."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                snap = snapshot("agent-live")
                plain = self.row(self.app(cls, [snap]), snap)
                self.assertIn("●", plain)
                self.assertIn(MARK_EMPTY_GLYPH, plain)


class MountedParkedRowTests(_Fixture):
    """The same row, read off a MOUNTED widget rather than the builder.

    The builder assertions above would pass for a string the app never puts on
    screen; this drives the real `_rebuild_pane_list` and reads the composited
    card, which is also what proves the filter-off path still renders the row.
    """

    def test_the_mounted_card_renders_the_parked_placeholder(self):
        self.park("agent-p")

        async def runner():
            app = MonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=(100, 30)) as pilot:
                app._monitor = _FakeMonitor(self.root)
                app._marks_view = agent_marks.MarksView(self.store)
                app._set_session_root_map(
                    app._monitor.get_session_to_project_mapping()
                )
                app._refresh_marks()
                app._snapshots = {
                    "%1": snapshot("agent-p", parked=True),
                    "%2": snapshot("agent-live", pane_id="%2",
                                   window_index="2"),
                }
                app._parked_pane_ids = frozenset({"%1"})
                app._hide_parked = False
                app._rebuild_pane_list()
                await pilot.pause()
                cards = list(app.query("#pane-list PaneCard"))
                self.assertEqual(len(cards), 2, "the parked row was dropped "
                                                "even with the filter OFF")
                joined = "\n".join(
                    getattr(c.render(), "plain",
                            Text.from_markup(str(c.render())).plain)
                    for c in cards
                )
                self.assertIn(PARK_GLYPH, joined)
                self.assertIn("parked", joined)

                # ... and with the filter ON the parked card is gone, while the
                # live one stays.
                app._hide_parked = True
                app._rebuild_pane_list()
                await pilot.pause()
                cards = list(app.query("#pane-list PaneCard"))
                self.assertEqual([c.pane_id for c in cards], ["%2"])

        asyncio.run(runner())


class ListFilterTests(_Fixture):
    """AC3 — `P` hides and re-shows, in both apps, in memory."""

    def _agents_in_list(self, app) -> list[str]:
        """Re-run the partition `_rebuild_pane_list` performs, without a DOM."""
        return [
            s.pane.window_name
            for s in app._snapshots.values()
            if s.pane.category == PaneCategory.AGENT
            and not (app._hide_parked and s.parked)
        ]

    def test_the_filter_hides_and_reshows(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.park("agent-p")
                app = self.app(cls, [
                    snapshot("agent-live"),
                    snapshot("agent-p", parked=True, pane_id="%2",
                             window_index="2"),
                ])
                self.assertEqual(
                    sorted(self._agents_in_list(app)),
                    ["agent-live", "agent-p"],
                )
                app._hide_parked = True
                self.assertEqual(self._agents_in_list(app), ["agent-live"])
                app._hide_parked = False
                self.assertEqual(
                    sorted(self._agents_in_list(app)),
                    ["agent-live", "agent-p"],
                )

    def test_the_filter_state_is_per_instance_and_starts_off(self):
        """In-memory and per app: it is a view toggle, not a preference, and a
        forgotten `P` must not hide agents across restarts."""
        a = self.app(MonitorApp, [snapshot("agent-a")])
        b = self.app(MonitorApp, [snapshot("agent-a")])
        self.assertFalse(a._hide_parked)
        a._hide_parked = True
        self.assertFalse(b._hide_parked)

    def test_p_is_bound_in_both_apps_and_free_of_a_collision(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                pairs = [(b.key, b.action) for b in cls.BINDINGS]
                self.assertIn(("P", "toggle_parked_visibility"), pairs)
                self.assertEqual(
                    [k for k, _ in pairs].count("P"), 1,
                    "P is bound twice — one of them is unreachable",
                )

    def test_the_minimonitor_hint_row_exists(self):
        """Minimonitor renders no Footer, so its hints ARE its binding surface;
        the parity audit in test_minimonitor_concern_action fails a binding
        without one. Pinned here too so the reason travels with the feature."""
        from monitor import minimonitor_app as mm
        self.assertIn("P:", mm.KEY_HINTS_TEXT)
        self.assertIn("parked", mm.KEY_HINTS_TEXT)


class FocusHandoffTests(_Fixture):
    """AC4 — parking the focused card with the filter on must not strand focus."""

    def _monitor_with_cards(self, snaps, focused):
        app = self.app(MonitorApp, snaps)
        app._hide_parked = True
        app._focused_pane_id = focused
        app._selected_card_pane_id = focused
        app._active_zone = Zone.PANE_LIST
        cards = [PaneCard(s.pane.pane_id, s.pane.window_name) for s in snaps]
        app._pane_cards = {c.pane_id: c for c in cards}
        app._cards_for_test = cards
        app._visible_pane_cards = lambda: list(app._cards_for_test)
        app._focus_calls: list[str] = []
        for c in cards:
            c.focus = (lambda cid: lambda **kw: app._focus_calls.append(cid))(
                c.pane_id
            )
        app.set_focus = lambda w: app._focus_calls.append("CLEARED")
        app._update_content_preview = lambda: None
        app._update_shadow_preview = lambda: None
        return app

    def test_focus_moves_to_the_next_visible_card(self):
        snaps = [
            snapshot("agent-a", pane_id="%1", window_index="1"),
            snapshot("agent-p", pane_id="%2", window_index="2", parked=True),
            snapshot("agent-b", pane_id="%3", window_index="3"),
        ]
        app = self._monitor_with_cards(snaps, "%2")
        app._focus_next_visible_card("%2")
        self.assertEqual(app._focused_pane_id, "%3")
        self.assertEqual(app._focus_calls, ["%3"])

    def test_focus_falls_back_to_the_previous_card_at_the_tail(self):
        snaps = [
            snapshot("agent-a", pane_id="%1", window_index="1"),
            snapshot("agent-p", pane_id="%2", window_index="2", parked=True),
        ]
        app = self._monitor_with_cards(snaps, "%2")
        app._focus_next_visible_card("%2")
        self.assertEqual(app._focused_pane_id, "%1")

    def test_parking_the_only_agent_clears_selection_coherently(self):
        """The reachable zero-card case. Returning early instead would leave
        `_focused_pane_id` naming a pane with no card, and `space` / `k` / `n` /
        the preview would all keep resolving against it."""
        snaps = [snapshot("agent-p", pane_id="%1", parked=True)]
        app = self._monitor_with_cards(snaps, "%1")
        app._focus_next_visible_card("%1")
        self.assertIsNone(app._focused_pane_id)
        self.assertIsNone(app._selected_card_pane_id)
        self.assertIn("CLEARED", app._focus_calls)
        self.assertEqual(
            app._active_zone, Zone.PANE_LIST,
            "the zone must stay PANE_LIST or `P` stops being dispatchable — "
            "check_action gates on the zone, not on a selection",
        )

    def test_the_preview_is_rerendered_when_selection_clears(self):
        """NEGATIVE CONTROL for the clear: without the re-render the preview
        keeps showing the pane that just disappeared."""
        snaps = [snapshot("agent-p", pane_id="%1", parked=True)]
        app = self._monitor_with_cards(snaps, "%1")
        rendered: list[str] = []
        app._update_content_preview = lambda: rendered.append("content")
        app._update_shadow_preview = lambda: rendered.append("shadow")
        app._focus_next_visible_card("%1")
        self.assertEqual(rendered, ["content", "shadow"])

    def test_toggling_the_filter_on_hands_focus_off_a_parked_card(self):
        snaps = [
            snapshot("agent-p", pane_id="%1", parked=True),
            snapshot("agent-b", pane_id="%2", window_index="2"),
        ]
        app = self._monitor_with_cards(snaps, "%1")
        app._hide_parked = False
        app._hand_off_focus_before_hiding()
        self.assertEqual(app._focused_pane_id, "%2")

    def test_the_hook_leaves_a_live_focused_card_alone(self):
        """Positive control: the handoff fires on parked cards only."""
        snaps = [
            snapshot("agent-a", pane_id="%1"),
            snapshot("agent-b", pane_id="%2", window_index="2"),
        ]
        app = self._monitor_with_cards(snaps, "%1")
        app._hand_off_focus_before_hiding()
        self.assertEqual(app._focused_pane_id, "%1")
        self.assertEqual(app._focus_calls, [])

    def test_restore_focus_anchors_when_the_saved_card_is_gone(self):
        """The structural net behind the deliberate handoff: a future call site
        that forgets to hand off must still not leave focus off the list."""
        snaps = [snapshot("agent-b", pane_id="%2", window_index="2")]
        app = self._monitor_with_cards(snaps, "%1")
        app._pane_cards = {}          # the parked card was filtered out
        app._update_selected_card_indicator = lambda full=False: None
        with patch.object(MonitorApp, "focused",
                          new_callable=PropertyMock, return_value=None):
            app._restore_focus("%1", Zone.PANE_LIST)
        self.assertEqual(app._focused_pane_id, "%2")

    def test_restore_focus_clears_when_no_card_remains(self):
        app = self._monitor_with_cards([], None)
        app._pane_cards = {}
        app._focused_pane_id = "%1"
        app._selected_card_pane_id = "%1"
        app._cards_for_test = []
        app._update_selected_card_indicator = lambda full=False: None
        with patch.object(MonitorApp, "focused",
                          new_callable=PropertyMock, return_value=None):
            app._restore_focus("%1", Zone.PANE_LIST)
        self.assertIsNone(app._focused_pane_id)
        self.assertIsNone(app._selected_card_pane_id)


class ParkedPreviewTests(_Fixture):
    """A parked pane IS in `_snapshots`, so the empty-state guard passes and the
    preview would render its empty `content` as if it were captured output."""

    def _preview_app(self, snap):
        app = self.app(MonitorApp, [snap])
        app._focused_pane_id = snap.pane.pane_id
        app._preview_render_gen = 0
        app._preview_rendered_lines = []
        app._last_preview_pane_id = None
        captured: dict[str, str] = {}

        class _Stub:
            def __init__(self, key):
                self._key = key
                self.styles = type("S", (), {"min_width": 0})()

            def update(self, text):
                captured[self._key] = str(text)

        widgets = {
            "#content-preview": _Stub("preview"),
            "#content-header": _Stub("header"),
            "#preview-scroll": _Stub("scroll"),
        }
        app.query_one = lambda sel, *a: widgets[sel]
        return app, captured

    def test_a_parked_pane_says_so_instead_of_rendering_blank(self):
        app, captured = self._preview_app(snapshot("agent-p", parked=True))
        app._update_content_preview()
        self.assertIn("parked", captured["preview"].lower())
        self.assertIn("Space", captured["preview"])

    def test_an_unfocused_app_still_gets_the_ordinary_empty_state(self):
        """Positive control: the parked branch must not swallow the pre-existing
        no-selection case."""
        app, captured = self._preview_app(snapshot("agent-p", parked=True))
        app._focused_pane_id = None
        app._update_content_preview()
        self.assertIn("Focus an agent", captured["preview"])


class SessionBarPartitionTests(_Fixture):
    """AC9 — the three live counters partition the NON-parked agents exactly,
    and parked agents get their own always-shown term."""

    def _bar_text(self, cls, snaps, completed=frozenset()):
        app = self.app(cls, snaps)
        app._completed_pane_ids = completed
        app._auto_switch = False
        app._session_bar_enabled = True
        captured: dict[str, str] = {}

        class _Bar:
            display = False

            def update(self, text):
                captured["t"] = str(text)

        app.query_one = lambda sel, *a: _Bar()
        if cls is MonitorApp:
            app._rebuild_session_bar(None, desync="")
        else:
            app._rebuild_session_bar(desync="")
        return captured["t"]

    def _snaps(self):
        return [
            snapshot("agent-await", pane_id="%1", awaiting=True),
            snapshot("agent-idle", pane_id="%2", window_index="2", is_idle=True),
            snapshot("agent-p1", pane_id="%3", window_index="3", parked=True),
            snapshot("agent-p2", pane_id="%4", window_index="4", parked=True),
        ]

    def test_parked_agents_leave_every_live_bucket(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.park("agent-p1")
                self.park("agent-p2")
                text = self._bar_text(cls, self._snaps())
                self.assertIn("1 awaiting", text)
                self.assertIn("1 idle", text)
                self.assertNotIn("3 idle", text)
                self.assertNotIn("2 awaiting", text)

    def test_the_bar_carries_a_parked_term(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                text = Text.from_markup(
                    self._bar_text(cls, self._snaps())
                ).plain
                self.assertRegex(text, r"2\s*p")

    def test_the_parked_term_is_absent_with_no_parked_agents(self):
        """Negative control: the term is conditional, like the other three."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                text = Text.from_markup(self._bar_text(cls, [
                    snapshot("agent-idle", is_idle=True),
                ])).plain
                self.assertNotIn("parked", text)
                self.assertNotIn("0p", text)

    def test_the_term_does_not_depend_on_the_filter(self):
        """A count that appeared and disappeared with a view toggle would be
        worse than no count: the bar is the one place a hidden agent is still
        accounted for."""
        snaps = self._snaps()
        shown = self._bar_text(MonitorApp, snaps)
        app = self.app(MonitorApp, snaps)
        app._hide_parked = True
        hidden = self._bar_text(MonitorApp, snaps)
        self.assertEqual(shown, hidden)

    def test_completed_skips_parked_agents(self):
        """`_compute_completed_panes` must not bucket a parked agent either, or
        the `done` counter re-admits what the partition just excluded."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                app = self.app(cls, [snapshot("agent-p", parked=True)])
                app._task_cache = _FakeTaskCache()
                self.assertEqual(app._compute_completed_panes(), frozenset())


class AutoSwitchTests(_Fixture):
    """AC10 — auto-switch never focuses a parked agent, in either branch."""

    def _app(self, snaps, focused):
        app = self.app(MonitorApp, snaps)
        app._focused_pane_id = focused
        return app

    def test_the_awaiting_branch_skips_parked(self):
        snaps = [
            snapshot("agent-active", pane_id="%1"),
            snapshot("agent-p", pane_id="%2", window_index="2", parked=True),
        ]
        app = self._app(snaps, "%1")
        self.assertFalse(
            app._maybe_auto_switch(),
            "a parked agent was offered as awaiting attention",
        )
        self.assertEqual(app._focused_pane_id, "%1")

    def test_the_idle_branch_skips_parked(self):
        snaps = [
            snapshot("agent-active", pane_id="%1"),
            snapshot("agent-p", pane_id="%2", window_index="2", parked=True,
                     is_idle=True),
        ]
        app = self._app(snaps, "%1")
        self.assertFalse(app._maybe_auto_switch())

    def test_a_live_idle_agent_is_still_chosen(self):
        """Positive control: the two tests above discriminate on `parked`, not
        on auto-switch having stopped working."""
        snaps = [
            snapshot("agent-active", pane_id="%1"),
            snapshot("agent-idle", pane_id="%2", window_index="2",
                     is_idle=True, idle_seconds=99.0),
        ]
        app = self._app(snaps, "%1")
        self.assertTrue(app._maybe_auto_switch())
        self.assertEqual(app._focused_pane_id, "%2")

    def test_a_parked_focused_agent_does_not_hold_focus(self):
        """A parked pane has no verdict to need attention with, so auto-switch
        must be free to move off it rather than treating it as 'already needs
        attention'."""
        snaps = [
            snapshot("agent-p", pane_id="%1", parked=True),
            snapshot("agent-idle", pane_id="%2", window_index="2",
                     is_idle=True, idle_seconds=99.0),
        ]
        app = self._app(snaps, "%1")
        self.assertTrue(app._maybe_auto_switch())
        self.assertEqual(app._focused_pane_id, "%2")


class VisibilityActionTests(_Fixture):
    def test_the_action_flips_notifies_and_repaints(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                app = self.app(cls, [snapshot("agent-p", parked=True)])
                notes: list[str] = []
                later: list = []
                app.notify = lambda msg, **kw: notes.append(msg)
                app.call_later = lambda fn, *a: later.append(fn)
                app._refresh_data = lambda: None
                app.action_toggle_parked_visibility()
                self.assertTrue(app._hide_parked)
                self.assertIn("hidden", notes[0].lower())
                self.assertEqual(len(later), 1)

                app.action_toggle_parked_visibility()
                self.assertFalse(app._hide_parked)
                self.assertIn("shown", notes[1].lower())

    def test_minimonitor_needs_no_focus_handoff(self):
        """Its list rows are read-only and its followed agent lives in a docked
        panel, so the mixin default (a no-op) is correct there — asserted rather
        than assumed, because the monitor overrides it."""
        app = self.app(MiniMonitorApp, [snapshot("agent-p", parked=True)])
        self.assertIsNone(app._hand_off_focus_before_hiding())


if __name__ == "__main__":
    unittest.main()
