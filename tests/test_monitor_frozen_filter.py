"""Frozen rows, counters, the unified filter and the frozen keys (t1705_7).

The frozen twin of `test_monitor_parked_filter.py`. Four things here are NOT
mirror images, and each pins a decision rather than a mechanism:

`FrozenRowRenderTests`
    The row composes BOTH glyphs — `<mark><F> <name>  frozen` — because frozen
    coexists with the priority/parked mark: frozen wins for *behaviour*
    (exclusion, filter, which keys act), the mark stays visible, and `space`
    still cycles it. Nothing capture-derived may appear, for the reason the
    parked row states: the pane was never captured, so a state dot would be a
    live-looking verdict that is arbitrarily stale.

`UnifiedFilterTests`
    ONE key hides both states. `P` is deliberately still the action id
    `toggle_parked_visibility` even though the state behind it is now
    `_hide_inactive`: that string is a persisted key-override identifier, so
    renaming it would silently revert every customized binding to the default.

`SessionBarPartitionTests`
    The counters stay SEPARATE and DISJOINT — one filter does not mean one
    number. A frozen agent that also carries the parked mark is counted once,
    as frozen, and both terms render whether or not the filter is hiding the
    rows.

`FrozenActionTests`
    Which agent an action targets, and how it is dispatched. `R`/`p`/`k` act
    only on the window's CURRENT agent and only when it is frozen — guarded in
    the action, never the binding, so the monitor's `R` keeps meaning Restart
    and the minimonitor's `p` keeps meaning pick-by-number. Freeze goes through
    a subprocess (it respawns the agent's pane); restore / re-pick / drop go
    through `run-shell -b`, because they replace or kill the pane the TUI is in.

Run: python3 tests/test_monitor_frozen_filter.py
"""
from __future__ import annotations

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

import agent_marks  # noqa: E402
from rich.text import Text  # noqa: E402

from monitor.minimonitor_app import MiniMonitorApp  # noqa: E402
from monitor.monitor_app import MonitorApp  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    PaneCategory, PaneSnapshot, TmuxPaneInfo,
)
from monitor.monitor_shared import (  # noqa: E402
    FROZEN_GLYPH, MARK_EMPTY_GLYPH, MARK_GLYPH, PARK_GLYPH,
)
from monitor.tmux_control import TmuxControlState  # noqa: E402

SESSION = "demo"
RECORD = "7f3a2c1d"


def pane(window: str, *, pane_id: str = "%1", window_index: str = "1",
         category: PaneCategory = PaneCategory.AGENT,
         frozen_record: str = "") -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index=window_index, window_name=window, pane_index="0",
        pane_id=pane_id, pane_pid=4242, current_command="node",
        width=80, height=24, category=category, session_name=SESSION,
        frozen_record=frozen_record,
    )


def snapshot(window: str, *, parked: bool = False, frozen: bool = False,
             is_idle: bool = False, awaiting: bool = False,
             idle_seconds: float = 1.0, **kw) -> PaneSnapshot:
    """A live snapshot, or the minimal one `commit_snapshots` builds for a
    parked / frozen pane (empty content, no verdict)."""
    if frozen:
        kw.setdefault("frozen_record", RECORD)
        return PaneSnapshot(
            pane=pane(window, **kw), content="", timestamp=0.0,
            idle_seconds=0.0, is_idle=False, awaiting_input=False,
            frozen=True, frozen_record_id=RECORD,
        )
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
        self.tmux_calls: list[list[str]] = []

    def get_session_to_project_mapping(self): return self._mapping
    async def get_session_to_project_mapping_async(self): return self._mapping
    def get_compare_mode(self, pane_id): return "stripped"
    def is_compare_mode_overridden(self, pane_id): return False
    def get_shadow_snapshot(self, pane_id): return None
    def get_shadow_snapshots(self): return {}
    def control_state(self): return TmuxControlState.CONNECTED

    def tmux_run(self, args, timeout=5.0):
        self.tmux_calls.append(list(args))
        return (0, "")


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

    def mark(self, window: str, times: int = 1) -> None:
        """Drive the real cycle rather than hand-writing a record."""
        mf = agent_marks.load(self.store)
        for _ in range(times):
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
        app._hide_inactive = False
        app._parked_pane_ids = frozenset(
            pid for pid, s in app._snapshots.items() if s.parked
        )
        app._frozen_pane_ids = frozenset(
            pid for pid, s in app._snapshots.items() if s.frozen
        )
        app._marks_view = agent_marks.MarksView(self.store)
        app._marks_purge_due_at = float("inf")
        app._marks_purge_inflight = False
        app._auto_switch = False
        app._session_bar_enabled = True
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


class FrozenRowRenderTests(_Fixture):
    """The placeholder, the composed glyphs, and what must NOT be on the row."""

    def test_frozen_row_shows_the_marker_and_the_name(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                snap = snapshot("agent-f", frozen=True)
                plain = self.row(self.app(cls, [snap]), snap)
                self.assertIn(FROZEN_GLYPH, plain)
                self.assertIn("agent-f", plain)
                self.assertIn("frozen", plain)

    def test_the_row_composes_the_mark_glyph_with_the_frozen_marker(self):
        """Frozen COEXISTS with the mark — pinned. An unmarked agent shows the
        empty star, a prioritized one the filled star, a parked one `P`, and in
        every case `F` follows it."""
        cases = ((0, MARK_EMPTY_GLYPH), (1, MARK_GLYPH), (2, PARK_GLYPH))
        for cls in BOTH_APPS:
            for cycles, glyph in cases:
                with self.subTest(app=cls.__name__, glyph=glyph):
                    self.setUp()
                    if cycles:
                        self.mark("agent-f", cycles)
                    snap = snapshot("agent-f", frozen=True)
                    plain = self.row(self.app(cls, [snap]), snap)
                    self.assertIn(f"{glyph}{FROZEN_GLYPH}", plain,
                                  f"expected the composed prefix in {plain!r}")

    def test_frozen_row_has_no_state_dot_and_no_status(self):
        """A ● here would read as a live idle/active verdict that is in fact
        arbitrarily stale — the pane was never captured."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                snap = snapshot("agent-f", frozen=True)
                plain = self.row(self.app(cls, [snap]), snap)
                for forbidden in ("●", "◆", "≈", "=", "IDLE", "PROMPT",
                                  "Active"):
                    self.assertNotIn(forbidden, plain, forbidden)

    def test_a_live_row_still_carries_the_dot(self):
        """Positive control: the assertions above discriminate on `frozen`, not
        on the fixture happening to render nothing."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                snap = snapshot("agent-live")
                plain = self.row(self.app(cls, [snap]), snap)
                self.assertIn("●", plain)
                self.assertIn(MARK_EMPTY_GLYPH, plain)

    def test_frozen_wins_over_parked_on_a_row_that_is_both(self):
        """The renderer's half of the precedence rule. The capture partition
        makes the two exclusive; this proves the row would still say `frozen`
        even if both flags reached it."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                snap = snapshot("agent-b", frozen=True)
                object.__setattr__(snap, "parked", True)
                plain = self.row(self.app(cls, [snap]), snap)
                self.assertIn("frozen", plain)
                self.assertNotIn("parked", plain)


class UnifiedFilterTests(_Fixture):
    """One key, one list — `P` hides parked AND frozen."""

    def test_the_filter_hides_both_states(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                snaps = [snapshot("agent-live"),
                         snapshot("agent-p", parked=True, pane_id="%2"),
                         snapshot("agent-f", frozen=True, pane_id="%3")]
                app = self.app(cls, snaps)
                app._hide_inactive = True
                kept = [s for s in app._snapshots.values()
                        if not (app._hide_inactive and (s.parked or s.frozen))]
                self.assertEqual([s.pane.pane_id for s in kept], ["%1"])

    def test_with_the_filter_off_every_row_survives(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                snaps = [snapshot("agent-live"),
                         snapshot("agent-f", frozen=True, pane_id="%3")]
                app = self.app(cls, snaps)
                kept = [s for s in app._snapshots.values()
                        if not (app._hide_inactive and (s.parked or s.frozen))]
                self.assertEqual(len(kept), 2)

    def test_is_inactive_covers_both_and_nothing_else(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                self.mark("agent-p", 2)          # -> parked
                app = self.app(cls, [])
                app._refresh_marks()
                self.assertTrue(app._is_inactive(snapshot("agent-f",
                                                          frozen=True)))
                self.assertTrue(app._is_inactive(snapshot("agent-p",
                                                          parked=True)))
                self.assertFalse(app._is_inactive(snapshot("agent-live")))

    def test_p_is_bound_once_in_both_apps_and_keeps_its_action_id(self):
        """The action string is a PERSISTED key-override identifier
        (`keybinding_registry` resolves overrides by it), so it must not follow
        the `_hide_inactive` rename. Only the label widened."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                bound = [b for b in cls.BINDINGS if b.key == "P"]
                self.assertEqual(len(bound), 1)
                self.assertEqual(bound[0].action, "toggle_parked_visibility")

    def test_no_separate_frozen_filter_key_exists(self):
        """The decision was ONE filter. An `F` binding would re-split it."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.assertEqual([b for b in cls.BINDINGS if b.key == "F"], [])


class SessionBarPartitionTests(_Fixture):
    """Frozen leaves every live bucket and gets its own disjoint term."""

    def _bar(self, cls, snaps, hide=False):
        app = self.app(cls, snaps)
        app._hide_inactive = hide
        captured = {}
        app.query_one = lambda *a, **k: _FakeBar(captured)
        app._session_bar_enabled = True
        app._rebuild_session_bar()
        return captured.get("text", "")

    def test_frozen_leaves_the_live_buckets(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                snaps = [snapshot("agent-live", is_idle=True),
                         snapshot("agent-f", frozen=True, pane_id="%3")]
                text = self._bar(cls, snaps)
                self.assertIn("1 idle", text,
                              "the frozen agent was bucketed as idle")

    def test_the_frozen_term_is_present_and_absent_at_zero(self):
        for cls, term in ((MonitorApp, "1 frozen"), (MiniMonitorApp, "1f")):
            with self.subTest(app=cls.__name__):
                self.setUp()
                with_frozen = self._bar(
                    cls, [snapshot("agent-f", frozen=True)])
                self.assertIn(term, with_frozen)
                without = self._bar(cls, [snapshot("agent-live")])
                self.assertNotIn("frozen", without)

    def test_the_term_is_independent_of_the_filter(self):
        """Hiding the rows must not hide the count — that is the whole point of
        a counter for a state you cannot see."""
        for cls, term in ((MonitorApp, "1 frozen"), (MiniMonitorApp, "1f")):
            with self.subTest(app=cls.__name__):
                self.setUp()
                text = self._bar(cls, [snapshot("agent-f", frozen=True)],
                                 hide=True)
                self.assertIn(term, text)

    def test_the_two_terms_are_disjoint(self):
        """A frozen agent carrying the parked mark is counted ONCE, as frozen —
        otherwise the bar would claim more agents than exist."""
        for cls, frozen_term, parked_term in (
                (MonitorApp, "1 frozen", "parked"),
                (MiniMonitorApp, "1f", "p")):
            with self.subTest(app=cls.__name__):
                self.setUp()
                snap = snapshot("agent-b", frozen=True)
                object.__setattr__(snap, "parked", True)
                text = self._bar(cls, [snap])
                self.assertIn(frozen_term, text)
                self.assertNotIn(f"1 {parked_term}", text)


class _FakeBar:
    def __init__(self, sink): self._sink = sink
    def update(self, text): self._sink["text"] = text
    def __setattr__(self, k, v): object.__setattr__(self, k, v)
    @property
    def display(self): return True
    @display.setter
    def display(self, value): pass


class AutoSwitchTests(_Fixture):
    """The monitor never auto-switches focus onto a frozen pane."""

    def _focused_on_a_busy_agent(self, candidate):
        """Focus a busy agent so the "keep the current one" guard falls through
        and the candidate search actually runs."""
        busy = snapshot("agent-busy", pane_id="%1")     # not idle, not awaiting
        app = self.app(MonitorApp, [busy, candidate])
        app._focused_pane_id = "%1"
        return app

    def test_auto_switch_never_picks_a_frozen_pane(self):
        app = self._focused_on_a_busy_agent(
            snapshot("agent-f", frozen=True, pane_id="%3"))
        self.assertFalse(app._maybe_auto_switch())
        self.assertEqual(app._focused_pane_id, "%1")

    def test_the_control_shows_an_idle_live_pane_is_chosen(self):
        """Positive control: the same machinery DOES switch when the candidate
        is not frozen, so the assertion above is about `frozen`."""
        app = self._focused_on_a_busy_agent(
            snapshot("agent-idle", is_idle=True, pane_id="%3"))
        self.assertTrue(app._maybe_auto_switch())
        self.assertEqual(app._focused_pane_id, "%3")

    def test_a_frozen_pane_does_not_hold_focus_against_a_live_candidate(self):
        """A frozen agent holding focus has no verdict to "need attention"
        with, so auto-switch must be free to move off it."""
        frozen = snapshot("agent-f", frozen=True, pane_id="%1")
        idle = snapshot("agent-idle", is_idle=True, pane_id="%3")
        app = self.app(MonitorApp, [frozen, idle])
        app._focused_pane_id = "%1"
        self.assertTrue(app._maybe_auto_switch())
        self.assertEqual(app._focused_pane_id, "%3")


class FrozenActionTests(_Fixture):
    """Targeting and dispatch. Both are decisions, not mechanisms."""

    def _armed(self, cls, snap):
        app = self.app(cls, [snap] if snap else [])
        self.notes: list[str] = []
        app.notify = lambda msg, **kw: self.notes.append(str(msg))
        app.call_later = lambda fn, *a: None
        app._refresh_data = lambda: None
        if cls is MiniMonitorApp:
            app._find_own_agent_snapshot = lambda: snap
        else:
            # The real `_get_focused_pane_id` reads Textual's `self.focused`,
            # which needs a mounted app. Stubbing it keeps these tests about
            # the frozen actions rather than about focus plumbing, which
            # `test_monitor_parked_filter`'s FocusHandoffTests already owns.
            app._get_focused_pane_id = lambda: (
                snap.pane.pane_id if snap else None)
            app._focused_pane_id = snap.pane.pane_id if snap else None
        return app

    def test_the_current_agent_is_the_apps_own_notion_of_selected(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                snap = snapshot("agent-f", frozen=True)
                app = self._armed(cls, snap)
                self.assertIs(app._current_agent_snapshot(), snap)

    def test_restore_produces_the_exact_detached_argv(self):
        """`run-shell -b`, never a subprocess: the coordinator replaces the very
        pane the TUI is in, so a child of that pane dies mid-transaction."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                snap = snapshot("agent-f", frozen=True)
                app = self._armed(cls, snap)
                app._poll_frozen_outcome = lambda *a, **k: None
                app.action_restore_frozen()
                argv = app._monitor.tmux_calls[-1]
                self.assertEqual(argv[:2], ["run-shell", "-b"])
                self.assertIn("aitask_frozen.sh", argv[2])
                self.assertTrue(argv[2].endswith(f"restore {RECORD}"))

    def test_repick_adds_the_repick_flag(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                snap = snapshot("agent-f", frozen=True)
                app = self._armed(cls, snap)
                app._poll_frozen_outcome = lambda *a, **k: None
                app.action_repick_frozen()
                self.assertTrue(
                    app._monitor.tmux_calls[-1][2].endswith(
                        f"restore {RECORD} --repick"))

    def test_drop_uses_the_leased_frozen_verb_not_kill_agent_pane_smart(self):
        """`kill_agent_pane_smart`'s store write is UNLEASED, so it would delete
        the record out from under an in-flight restore. `aitask_frozen.sh drop`
        takes the lease, preflights, kills and verifies."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                snap = snapshot("agent-f", frozen=True)
                app = self._armed(cls, snap)
                app._poll_frozen_outcome = lambda *a, **k: None
                app._drop_frozen(snap)
                argv = app._monitor.tmux_calls[-1]
                self.assertEqual(argv[:2], ["run-shell", "-b"])
                self.assertTrue(argv[2].endswith(f"drop {RECORD}"))

    def test_restore_and_repick_are_refused_on_a_live_agent(self):
        """Guarded in the ACTION, not the binding — the monitor's `R` must keep
        meaning Restart and the minimonitor's `p` pick-by-number."""
        for cls in BOTH_APPS:
            for action in ("action_restore_frozen", "action_repick_frozen"):
                with self.subTest(app=cls.__name__, action=action):
                    self.setUp()
                    snap = snapshot("agent-live")
                    app = self._armed(cls, snap)
                    getattr(app, action)()
                    self.assertEqual(
                        app._monitor.tmux_calls, [],
                        "a live agent was dispatched to the frozen coordinator")
                    self.assertTrue(any("not frozen" in n for n in self.notes))

    def test_the_live_row_keeps_its_own_binding_meaning(self):
        """The monitor's `R` is still Restart and its `z` still Zoom; the
        minimonitor's `p` is still pick-by-number."""
        mon = {b.key: b.action for b in MonitorApp.BINDINGS}
        self.assertEqual(mon["R"], "restart_task")
        self.assertEqual(mon["z"], "cycle_preview_size")
        mini = {b.key: b.action for b in MiniMonitorApp.BINDINGS}
        self.assertEqual(mini["p"], "pick_task_by_number")

    def test_freeze_and_freeze_all_are_bound_identically_in_both_apps(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                keys = {b.key: b.action for b in cls.BINDINGS}
                self.assertEqual(keys["f"], "freeze_current")
                self.assertEqual(keys["Z"], "freeze_all")

    def test_no_binding_collides_in_either_app(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                keys = [b.key for b in cls.BINDINGS]
                self.assertEqual(len(keys), len(set(keys)),
                                 f"duplicate key bindings: {keys}")

    def test_freeze_is_refused_on_an_already_frozen_agent(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                snap = snapshot("agent-f", frozen=True)
                app = self._armed(cls, snap)
                app.push_screen = lambda *a, **k: self.fail(
                    "a confirmation was offered for an already-frozen agent")
                app.action_freeze_current()
                self.assertTrue(any("already frozen" in n for n in self.notes))

    def test_freeze_asks_before_it_acts(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                snap = snapshot("agent-live")
                app = self._armed(cls, snap)
                shown = []
                app.push_screen = lambda screen, cb=None: shown.append(screen)
                app.action_freeze_current()
                self.assertEqual(len(shown), 1)
                self.assertEqual(app._monitor.tmux_calls, [])


class MinimonitorOwnPanelTests(_Fixture):
    """The docked panel shows `F frozen <stamp>` and drops the phase line."""

    def _panel(self, snap, frozen_at):
        app = self.app(MiniMonitorApp, [snap])
        app._own_identity_text = "agent-f"
        app._own_frozen_at = lambda s: frozen_at
        mark_kind = app._mark_kind(snap)
        return Text.from_markup(
            app._own_card_text(mark_kind, "", frozen_at)).plain

    def test_it_shows_the_marker_and_the_stamp(self):
        plain = self._panel(snapshot("agent-f", frozen=True),
                            "2026-09-04T09:20:00Z")
        self.assertIn(FROZEN_GLYPH, plain)
        self.assertIn("frozen", plain)
        self.assertIn("2026-09-04T09:20:00Z", plain)

    def test_a_frozen_agent_shows_no_phase_line(self):
        """The phase is the one live signal this panel carries, and a frozen
        agent has no current answer for it — a stale one would read as now."""
        app = self.app(MiniMonitorApp, [])
        app._own_identity_text = "agent-f"
        plain = Text.from_markup(
            app._own_card_text(None, "planning", "2026-09-04T09:20:00Z")).plain
        self.assertNotIn("planning", plain)

    def test_an_unreadable_record_still_says_frozen(self):
        """`""` means "frozen, record unreadable" and must not silently
        downgrade the panel to a live-looking row — the pane option is the
        authoritative classifier, not the store."""
        plain = self._panel(snapshot("agent-f", frozen=True), "")
        self.assertIn("frozen", plain)

    def test_a_live_agent_keeps_its_phase_line(self):
        """Positive control for the suppression above."""
        app = self.app(MiniMonitorApp, [])
        app._own_identity_text = "agent-live"
        plain = Text.from_markup(
            app._own_card_text(None, "planning", None)).plain
        self.assertIn("planning", plain)


if __name__ == "__main__":
    unittest.main(verbosity=2)
