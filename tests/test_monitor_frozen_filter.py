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

import asyncio
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
from monitor import monitor_shared  # noqa: E402
from monitor.monitor_shared import (  # noqa: E402
    FROZEN_GLYPH, MARK_EMPTY_GLYPH, MARK_GLYPH, PARK_GLYPH,
    FreezeConfirmDialog, _FREEZE_ONE_TIMEOUT, _MARKS_CMD_TIMEOUT,
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


class _FakeContainer:
    """Captures what minimonitor's `_rebuild_pane_list` mounts."""

    def __init__(self) -> None:
        self.mounted: list = []
        self.display = False

    async def remove_children(self):
        pass

    async def mount_all(self, widgets):
        self.mounted = list(widgets)


class _FakeGateCache:
    def summary_for(self, task_id): return None
    def clear(self): pass


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

    def _listed(self, cls, snaps, *, hide: bool) -> list[str]:
        """Pane ids the app's REAL rebuild mounts, in order.

        Re-stating the filter condition in the test instead would be asserting
        the implementation against itself: a copy of
        ``not (hide and (parked or frozen))`` stays green even when the
        production rebuild never runs — it was, and this suite's first draft
        shipped exactly that. Both branches here go through the app's own
        ``_rebuild_pane_list`` and read the widgets it produced.
        """
        if cls is MiniMonitorApp:
            return self._listed_mini(snaps, hide=hide)
        return self._listed_monitor(snaps, hide=hide)

    def _listed_mini(self, snaps, *, hide: bool) -> list[str]:
        container = _FakeContainer()
        app = self.app(MiniMonitorApp, snaps)
        app.query_one = lambda *a, **k: container
        app._own_window_index = None
        app._gate_cache = _FakeGateCache()
        app._hide_inactive = hide
        asyncio.run(app._rebuild_pane_list())
        from monitor.minimonitor_app import MiniPaneCard
        return [w.pane_id for w in container.mounted
                if isinstance(w, MiniPaneCard)]

    def _listed_monitor(self, snaps, *, hide: bool) -> list[str]:
        got: list[str] = []

        async def runner():
            app = MonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=(100, 30)) as pilot:
                app._monitor = _FakeMonitor(self.root)
                app._marks_view = agent_marks.MarksView(self.store)
                app._set_session_root_map(
                    app._monitor.get_session_to_project_mapping())
                app._refresh_marks()
                app._snapshots = {s.pane.pane_id: s for s in snaps}
                app._parked_pane_ids = frozenset(
                    pid for pid, s in app._snapshots.items() if s.parked)
                app._frozen_pane_ids = frozenset(
                    pid for pid, s in app._snapshots.items() if s.frozen)
                app._hide_inactive = hide
                app._rebuild_pane_list()
                await pilot.pause()
                got.extend(c.pane_id
                           for c in app.query("#pane-list PaneCard"))

        asyncio.run(runner())
        return got

    def test_the_filter_hides_both_states(self):
        snaps = [snapshot("agent-live"),
                 snapshot("agent-p", parked=True, pane_id="%2",
                          window_index="2"),
                 snapshot("agent-f", frozen=True, pane_id="%3",
                          window_index="3")]
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                self.assertEqual(self._listed(cls, snaps, hide=True), ["%1"])

    def test_with_the_filter_off_every_row_survives(self):
        """The other half, and the control: the rows exist, so the assertion
        above is about the FILTER and not about the rebuild mounting nothing."""
        snaps = [snapshot("agent-live"),
                 snapshot("agent-p", parked=True, pane_id="%2",
                          window_index="2"),
                 snapshot("agent-f", frozen=True, pane_id="%3",
                          window_index="3")]
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                self.assertEqual(
                    sorted(self._listed(cls, snaps, hide=False)),
                    ["%1", "%2", "%3"])

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


class FreezeAllOfferTests(_Fixture):
    """`Z` — where the confirmation's number comes from, and what confirming
    actually dispatches.

    The count is the whole point of this path. `freeze --all` spans EVERY
    aitasks session on the machine and does not exclude parked agents, while
    either app may be in single-session mode and its live set excludes parked —
    so a snapshot-derived number would understate a destructive operation at
    exactly the moment the user is deciding. It therefore comes from the
    operation's own enumeration (`--dry-run`), and these tests pin that it does.
    """

    def _armed(self, cls, *, dry_out="FREEZE_ELIGIBLE:5", rc=0, snaps=None):
        app = self.app(cls, snaps or [])
        self.notes: list[str] = []
        self.cmds: list[tuple[list[str], float | None]] = []
        self.shown: list[tuple[object, object]] = []
        self.dispatched: list[tuple[list[str], float, bool]] = []
        app.notify = lambda msg, **kw: self.notes.append(str(msg))
        app.call_later = lambda fn, *a: None
        app._refresh_data = lambda: None

        async def fake_cmd(args, *, timeout=None):
            self.cmds.append((list(args), timeout))
            return rc, dry_out

        app._run_frozen_cmd = fake_cmd
        app.push_screen = lambda screen, cb=None: self.shown.append((screen, cb))
        # Recorded rather than run: `_dispatch_freeze` has its own suite below,
        # and a real coroutine handed to a stubbed `run_worker` is never awaited.
        app._dispatch_freeze = lambda argv, *, timeout, batch: (
            self.dispatched.append((list(argv), timeout, batch)))
        app.run_worker = lambda work, **kw: None
        return app

    def _offer(self, app):
        asyncio.run(app._offer_freeze_all())

    def test_the_count_comes_from_the_dry_run_not_from_the_snapshot_map(self):
        """THE assertion. Two agents are visible; the operation would freeze
        five. The dialog must say five."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                app = self._armed(cls, snaps=[
                    snapshot("agent-a"),
                    snapshot("agent-b", pane_id="%2", window_index="2")])
                self._offer(app)
                self.assertEqual(len(self.shown), 1, "no confirmation offered")
                title = self.shown[0][0]._title
                self.assertIn("5", title)
                self.assertNotIn("2 agent(s)?", title)

    def test_the_dry_run_is_the_first_thing_it_runs(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                self._offer(self._armed(cls))
                self.assertEqual(self.cmds[0][0],
                                 ["freeze", "--all", "--dry-run"])

    def test_the_dry_run_gets_the_freeze_budget_never_the_marks_budget(self):
        """A dry run enumerates every session on the machine, which is the same
        tmux work a real batch's first pass does — 20s would kill it."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                self._offer(self._armed(cls))
                self.assertEqual(self.cmds[0][1], _FREEZE_ONE_TIMEOUT)
                self.assertNotEqual(self.cmds[0][1], _MARKS_CMD_TIMEOUT)

    def test_the_body_states_the_wider_scope_in_words(self):
        """A bare number still reads as "the agents I can see"."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                self._offer(self._armed(cls, snaps=[snapshot("agent-a")]))
                body = self.shown[0][0]._body
                self.assertIn("every aitasks session on this machine", body)
                self.assertIn("parked", body)
                self.assertIn("other projects", body)

    def test_the_local_number_counts_agents_not_panes(self):
        """It is compared against the dry-run count by eye, so it must count the
        same KIND of thing. Counting `_snapshots` would include TUI and OTHER
        panes and make the two numbers incomparable."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                app = self._armed(cls, snaps=[
                    snapshot("agent-a"),
                    snapshot("board", pane_id="%8", window_index="8",
                             category=PaneCategory.TUI),
                    snapshot("scratch", pane_id="%9", window_index="9",
                             category=PaneCategory.OTHER)])
                self._offer(app)
                self.assertIn("not just the 1 agent(s) shown here",
                              self.shown[0][0]._body)

    def test_confirming_dispatches_freeze_all_on_a_count_scaled_budget(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                app = self._armed(cls)
                self._offer(app)
                self.shown[0][1](True)
                self.assertEqual(
                    self.dispatched,
                    [(["freeze", "--all"], _FREEZE_ONE_TIMEOUT * 5, True)])

    def test_cancelling_dispatches_nothing(self):
        for cls in BOTH_APPS:
            for answer in (False, None):
                with self.subTest(app=cls.__name__, answer=answer):
                    self.setUp()
                    app = self._armed(cls)
                    self._offer(app)
                    self.shown[0][1](answer)
                    self.assertEqual(self.dispatched, [])

    def test_a_failed_dry_run_refuses_rather_than_guessing(self):
        """Fail closed: without a trustworthy count there is no honest
        confirmation to show, and freezing anyway would act on a number the user
        never saw."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                app = self._armed(cls, rc=1, dry_out="ERROR:cannot run")
                self._offer(app)
                self.assertEqual(self.shown, [])
                self.assertEqual(self.dispatched, [])
                self.assertTrue(any("not freezing" in n for n in self.notes),
                                self.notes)

    def test_a_dry_run_without_the_count_line_refuses_too(self):
        """rc 0 is not enough — an engine that printed the pane lines but no
        `FREEZE_ELIGIBLE:` would otherwise confirm with `None` agents."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                app = self._armed(cls, dry_out="WOULD_FREEZE:%1|demo|agent-a")
                self._offer(app)
                self.assertEqual(self.shown, [])
                self.assertEqual(self.dispatched, [])

    def test_an_unparseable_count_refuses(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                app = self._armed(cls, dry_out="FREEZE_ELIGIBLE:lots")
                self._offer(app)
                self.assertEqual(self.shown, [])
                self.assertEqual(self.dispatched, [])

    def test_zero_eligible_says_so_and_asks_nothing(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                app = self._armed(cls, dry_out="FREEZE_ELIGIBLE:0")
                self._offer(app)
                self.assertEqual(self.shown, [],
                                 "confirmed a batch with nothing in it")
                self.assertTrue(any("No agents to freeze" in n
                                    for n in self.notes), self.notes)

    def test_the_key_hands_the_offer_to_a_worker(self):
        """`action_freeze_all` must not block the keypress on a dry run that
        enumerates every tmux session on the machine."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                app = self._armed(cls)
                work = []
                app.run_worker = lambda w, **kw: work.append(w)
                app.action_freeze_all()
                self.assertEqual(len(work), 1)
                self.assertEqual(self.cmds, [],
                                 "the dry run ran on the keypress thread")
                work[0].close()          # never awaited; do not warn


class DispatchFreezeTests(_Fixture):
    """`_dispatch_freeze` — the budget it asks for, and how it reads the result.

    `freeze --all` emits NO summary line (unlike `restore --all`), so the tally
    is built here from the per-pane lines. And a timeout is PARTIAL, never
    failure: the runner kills the child, but a killed freeze leaves a `freezing`
    record that reconcile settles, and some agents are already frozen.
    """

    def _armed(self, cls, out, rc=0):
        app = self.app(cls, [])
        self.notes: list[tuple[str, str]] = []
        self.cmds: list[tuple[list[str], float | None]] = []
        app.notify = lambda msg, **kw: self.notes.append(
            (str(msg), kw.get("severity", "information")))
        app.call_later = lambda fn, *a: None
        app._refresh_data = lambda: None

        async def fake_cmd(args, *, timeout=None):
            self.cmds.append((list(args), timeout))
            return rc, out

        app._run_frozen_cmd = fake_cmd
        return app

    def _run(self, app, argv, *, timeout, batch):
        asyncio.run(app._dispatch_freeze(argv, timeout=timeout, batch=batch))

    def test_a_single_freeze_asks_for_the_freeze_budget(self):
        """One freeze spends up to 30s in `capture-pane` alone plus two 20s
        store calls, so the 20s marks budget would kill a legitimate one."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                snap = snapshot("agent-live")
                app = self._armed(cls, "FROZEN:%1|demo|agent-live")
                if cls is MiniMonitorApp:
                    app._find_own_agent_snapshot = lambda: snap
                else:
                    app._get_focused_pane_id = lambda: "%1"
                app._snapshots = {"%1": snap}
                app.run_worker = lambda w, **kw: (asyncio.run(w), None)[1]
                cb = []
                app.push_screen = lambda screen, callback=None: cb.append(
                    callback)
                app.action_freeze_current()
                cb[0](True)
                self.assertEqual(self.cmds[0][1], _FREEZE_ONE_TIMEOUT)
                self.assertGreater(_FREEZE_ONE_TIMEOUT, _MARKS_CMD_TIMEOUT)

    def test_a_slow_but_successful_freeze_is_reported_as_success(self):
        """The budget exists to let a slow freeze FINISH. Proven against the
        real runner in `RunnerBudgetTests` below; here the point is that a
        success arriving late is read as success, not as a timeout."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                app = self._armed(cls, "FROZEN:%1|demo|agent-a")
                self._run(app, ["freeze", "%1"], timeout=_FREEZE_ONE_TIMEOUT,
                          batch=False)
                msg, sev = self.notes[-1]
                self.assertIn("Frozen", msg)
                self.assertNotIn("timed out", msg)
                self.assertEqual(sev, "information")

    def test_a_timeout_is_reported_as_partial_not_as_failure(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                app = self._armed(
                    cls, "ERROR:aitask_frozen.sh timed out after 90.0s", rc=1)
                self._run(app, ["freeze", "--all"], timeout=90.0, batch=True)
                msg, sev = self.notes[-1]
                self.assertIn("some agents may be frozen", msg)
                self.assertIn("reconcile", msg)
                self.assertNotIn("failed", msg.lower())
                self.assertEqual(sev, "warning")

    def test_a_runner_error_says_nothing_was_frozen(self):
        """Distinct from a timeout: the wrapper never started, so there is no
        partial state and no reconcile to suggest."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                app = self._armed(
                    cls, "ERROR:cannot run aitask_frozen.sh: [Errno 2]", rc=1)
                self._run(app, ["freeze", "--all"], timeout=90.0, batch=True)
                msg, sev = self.notes[-1]
                self.assertIn("could not run", msg.lower())
                self.assertNotIn("reconcile", msg)
                self.assertEqual(sev, "error")

    def test_the_batch_tally_is_counted_from_the_result_lines(self):
        """There is no summary line to read — `freeze --all` emits one line per
        pane and nothing else."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                app = self._armed(cls, "\n".join([
                    "FROZEN:%1|demo|agent-a",
                    "FROZEN:%2|demo|agent-b",
                    "FREEZE_SKIPPED:%3|already frozen",
                    "FREEZE_FAILED:%4|respawn refused",
                ]))
                self._run(app, ["freeze", "--all"], timeout=90.0, batch=True)
                msg, sev = self.notes[-1]
                self.assertIn("Froze 2/4 agent(s)", msg)
                self.assertIn("1 already frozen", msg)
                self.assertEqual(sev, "warning", "a failure must not read as "
                                                 "an ordinary success")

    def test_a_clean_batch_is_not_a_warning(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                app = self._armed(cls, "FROZEN:%1|demo|agent-a")
                self._run(app, ["freeze", "--all"], timeout=90.0, batch=True)
                self.assertEqual(self.notes[-1],
                                 ("Froze 1/1 agent(s)", "information"))

    def test_a_single_freeze_failure_is_named(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                app = self._armed(cls, "FREEZE_FAILED:%1|respawn refused")
                self._run(app, ["freeze", "%1"], timeout=_FREEZE_ONE_TIMEOUT,
                          batch=False)
                msg, sev = self.notes[-1]
                self.assertIn("respawn refused", msg)
                self.assertEqual(sev, "error")

    def test_silence_from_the_engine_is_surfaced(self):
        """rc 0 and no lines is not success — it means the engine did nothing
        and said nothing, which the user must not read as "frozen"."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                app = self._armed(cls, "")
                self._run(app, ["freeze", "%1"], timeout=_FREEZE_ONE_TIMEOUT,
                          batch=False)
                msg, sev = self.notes[-1]
                self.assertIn("no result", msg)
                self.assertEqual(sev, "warning")


class RunnerBudgetTests(_Fixture):
    """The budget against the REAL runner, with a real (fake) script.

    Everything above stubs `_run_frozen_cmd`, so none of it proves the timeout
    argument reaches `asyncio.wait_for` — the claim that a slow freeze is
    allowed to finish. This does, with a script that sleeps.
    """

    def _script(self, body: str):
        path = self.tmp / "fake_frozen.sh"
        path.write_text("#!/usr/bin/env bash\n" + body + "\n")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def test_a_slow_child_finishes_when_the_budget_allows_it(self):
        app = self.app(MonitorApp, [])
        script = self._script("sleep 0.4; echo 'FROZEN:%1|demo|agent-a'")
        rc, out = asyncio.run(
            app._run_marks_cmd(["freeze", "%1"], script=script, timeout=10.0))
        self.assertEqual(rc, 0)
        self.assertIn("FROZEN:", out)

    def test_the_same_child_is_killed_when_it_does_not(self):
        """The control: the timeout is real, so the test above is about the
        BUDGET and not about the script being fast."""
        app = self.app(MonitorApp, [])
        script = self._script("sleep 5; echo 'FROZEN:%1|demo|agent-a'")
        rc, out = asyncio.run(
            app._run_marks_cmd(["freeze", "%1"], script=script, timeout=0.3))
        self.assertEqual(rc, 1)
        self.assertIn("timed out", out)

    def test_frozen_cmd_defaults_to_the_freeze_budget(self):
        app = self.app(MonitorApp, [])
        seen = {}

        async def spy(args, *, script=None, timeout=None):
            seen["timeout"] = timeout
            return 0, ""

        app._run_marks_cmd = spy
        asyncio.run(app._run_frozen_cmd(["reconcile"]))
        self.assertEqual(seen["timeout"], _FREEZE_ONE_TIMEOUT)


class ConfirmDialogTests(_Fixture):
    """The dialog itself — its affirmative button, and whether it fits.

    Both of these are about the WIDGET, not about the callers' wiring: the
    caller tests above pass a `_title`/`_body` and never mount anything, so a
    dialog whose button says the wrong word or falls off a 40-column screen
    would sail through all of them.
    """

    NARROW = (40, 20)          # the minimonitor's normal width

    def _drop_dialog(self, cls):
        snap = snapshot("agent-f", frozen=True)
        app = self.app(cls, [snap])
        shown = []
        app.push_screen = lambda screen, cb=None: shown.append((screen, cb))
        app._drop_frozen = lambda s: shown.append(("DROPPED", s))
        app._confirm_drop_frozen(snap)
        return app, snap, shown

    def test_the_drop_dialog_does_not_offer_a_freeze_button(self):
        """THE defect this class exists for. One screen serves two verbs; the
        button is what the user reads before clicking, and "Freeze" on the drop
        dialog names the reversible operation while deleting the only copy of
        the agent's captured output."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                _app, _snap, shown = self._drop_dialog(cls)
                dialog = shown[0][0]
                self.assertEqual(dialog._confirm_label, "Drop")
                self.assertTrue(dialog._destructive)

    def test_the_freeze_dialog_is_still_the_reassuring_one(self):
        """Negative control: freezing keeps the output, so it must NOT borrow
        the destructive styling."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                snap = snapshot("agent-live")
                app = self.app(cls, [snap])
                if cls is MiniMonitorApp:
                    app._find_own_agent_snapshot = lambda: snap
                else:
                    app._get_focused_pane_id = lambda: "%1"
                shown = []
                app.push_screen = lambda screen, cb=None: shown.append(screen)
                app.action_freeze_current()
                self.assertEqual(shown[0]._confirm_label, "Freeze")
                self.assertFalse(shown[0]._destructive)

    def test_confirming_the_drop_dialog_actually_drops(self):
        """The callback wiring, end to end: the affirmative button's id must be
        the one `on_button_pressed` maps to True, and the caller's callback must
        run `_drop_frozen`. Asserting the label alone would pass even if the
        button dismissed with False."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                _app, snap, shown = self._drop_dialog(cls)
                dialog, callback = shown[0]
                results = []
                dialog.dismiss = lambda value: results.append(value)
                dialog.on_button_pressed(
                    _ButtonPressed(_FakeButton("btn-confirm")))
                self.assertEqual(results, [True])
                callback(results[0])
                self.assertIn(("DROPPED", snap), shown)

    def test_cancelling_the_drop_dialog_drops_nothing(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                _app, snap, shown = self._drop_dialog(cls)
                dialog, callback = shown[0]
                results = []
                dialog.dismiss = lambda value: results.append(value)
                dialog.on_button_pressed(
                    _ButtonPressed(_FakeButton("btn-cancel")))
                self.assertEqual(results, [False])
                callback(results[0])
                self.assertNotIn(("DROPPED", snap), shown)

    def test_escape_never_returns_a_truthy_result(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.setUp()
                _app, _snap, shown = self._drop_dialog(cls)
                dialog = shown[0][0]
                results = []
                dialog.dismiss = lambda value: results.append(value)
                dialog.action_dismiss_dialog()
                self.assertEqual(results, [False])

    def _mount_at(self, dialog, size):
        """Mount the dialog alone and report each button's on-screen region."""
        regions = {}

        async def runner():
            app = MonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=size) as pilot:
                app._monitor = _FakeMonitor(self.root)
                await app.push_screen(dialog)
                await pilot.pause()
                for btn in dialog.query("Button"):
                    regions[str(btn.id)] = btn.region

        asyncio.run(runner())
        return regions

    def test_both_buttons_fit_inside_a_forty_column_screen(self):
        """The minimonitor hosts this at 40 columns. Textual's `Button` defaults
        to `min-width: 16`, which put two side-by-side buttons plus margins past
        the right edge — the second one rendered but could not be clicked, so
        the only way out of a destructive confirmation was Escape."""
        dialog = FreezeConfirmDialog("Drop this frozen agent?", "body",
                                     confirm_label="Drop", destructive=True)
        regions = self._mount_at(dialog, self.NARROW)
        self.assertEqual(set(regions), {"btn-confirm", "btn-cancel"})
        for name, region in regions.items():
            self.assertGreater(region.width, 0, f"{name} has no width")
            self.assertLessEqual(
                region.right, self.NARROW[0],
                f"{name} extends past the {self.NARROW[0]}-column screen "
                f"(region={region}) — it renders but cannot be clicked")
            self.assertGreaterEqual(region.x, 0, f"{name} starts off-screen")

    def test_the_destructive_styling_actually_reaches_the_widgets(self):
        """The label alone is only half the signal. Asserting `_destructive` is
        asserting the flag, not the appearance — this reads the mounted widgets,
        so the docstring's claim that the border and header re-colour is checked
        rather than asserted in prose."""
        dialog = FreezeConfirmDialog("Drop this frozen agent?", "body",
                                     confirm_label="Drop", destructive=True)
        seen = {}

        async def runner():
            app = MonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=self.NARROW) as pilot:
                app._monitor = _FakeMonitor(self.root)
                await app.push_screen(dialog)
                await pilot.pause()
                seen["class"] = dialog.has_class("-destructive")
                btn = dialog.query_one("#btn-confirm")
                seen["label"] = str(btn.label)
                seen["variant"] = btn.variant
                seen["border"] = str(
                    dialog.query_one("#freeze-dialog").styles.border_top)
                seen["header"] = str(
                    dialog.query_one("#freeze-header").styles.color)

        asyncio.run(runner())
        self.assertTrue(seen["class"])
        self.assertEqual(seen["label"], "Drop")
        self.assertEqual(seen["variant"], "error")
        self.assertNotEqual(seen["border"], "", "the dialog has no border")
        seen["error_border"] = seen["border"]

        # …and the freeze dialog, mounted the same way, must NOT look like it.
        plain = FreezeConfirmDialog("Freeze this agent?", "body")
        other = {}

        async def runner2():
            app = MonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=self.NARROW) as pilot:
                app._monitor = _FakeMonitor(self.root)
                await app.push_screen(plain)
                await pilot.pause()
                other["border"] = str(
                    plain.query_one("#freeze-dialog").styles.border_top)
                other["header"] = str(
                    plain.query_one("#freeze-header").styles.color)
                other["variant"] = plain.query_one("#btn-confirm").variant

        asyncio.run(runner2())
        self.assertEqual(other["variant"], "primary")
        self.assertNotEqual(
            other["border"], seen["error_border"],
            "the destructive dialog is styled exactly like the reassuring one")
        self.assertNotEqual(
            other["header"], seen["header"],
            "the destructive header is styled exactly like the reassuring one")

    def test_the_buttons_do_not_overlap_at_that_width(self):
        dialog = FreezeConfirmDialog("Freeze all 5 agent(s)?", "body")
        regions = self._mount_at(dialog, self.NARROW)
        a, b = regions["btn-confirm"], regions["btn-cancel"]
        self.assertLessEqual(a.right, b.x, f"buttons overlap: {a} / {b}")

    def _centre_click_at_forty_columns(self, button_id):
        """Mount at 40 columns and click the button's CENTRE, as a user would.

        The offset must be computed and passed explicitly. `pilot.click`'s
        default offset is ``(0, 0)`` — the widget's TOP-LEFT corner, not its
        centre — and a clipped button keeps its top-left, so the default aims at
        the one part of a broken layout that still works. Measured against the
        old 70% / `min-width: 16` layout: Cancel's region was
        ``x=27 width=16`` on a 40-column screen, a default click landed and
        dismissed, and a centre click at ``(8, 1)`` — screen x=35, past the
        dialog's own clip at x=34 — returned ``False`` and dismissed nothing, so
        the only way out of a destructive confirmation was Escape.

        Returns `(landed, dismissals)`: `landed` is `pilot.click`'s own verdict
        on whether the selected widget was actually under the mouse.
        """
        results = []
        landed = {}
        dialog = FreezeConfirmDialog("Drop this frozen agent?", "body",
                                     confirm_label="Drop", destructive=True)

        async def runner():
            app = MonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=self.NARROW) as pilot:
                app._monitor = _FakeMonitor(self.root)
                dialog.dismiss = lambda value: results.append(value)
                await app.push_screen(dialog)
                await pilot.pause()
                region = dialog.query_one(f"#{button_id}").region
                landed["ok"] = await pilot.click(
                    f"#{button_id}",
                    offset=(region.width // 2, region.height // 2))
                await pilot.pause()

        asyncio.run(runner())
        return landed["ok"], results

    def test_a_centre_click_on_cancel_at_forty_columns_dismisses(self):
        """THE reachability assertion, and the one the region arithmetic cannot
        make: a button can be fully on screen and still not be under the mouse
        where the user aims."""
        ok, results = self._centre_click_at_forty_columns("btn-cancel")
        self.assertTrue(ok, "a centre click missed the Cancel button entirely")
        self.assertEqual(results, [False],
                         "the Cancel button did not dismiss the dialog")

    def test_a_centre_click_on_the_affirmative_confirms(self):
        """The positive control: both buttons are reachable at the centre, so
        the assertion above is about Cancel and not about clicks being inert."""
        ok, results = self._centre_click_at_forty_columns("btn-confirm")
        self.assertTrue(ok)
        self.assertEqual(results, [True])

    def test_a_long_title_does_not_push_a_button_off_screen(self):
        """The freeze-all title carries a count and the drop body a sentence, so
        the layout must not be sized by its content."""
        dialog = FreezeConfirmDialog(
            "Freeze all 127 agent(s) across every session?",
            "This affects every aitasks session on this machine, including "
            "parked agents and agents in other projects.")
        regions = self._mount_at(dialog, self.NARROW)
        for name, region in regions.items():
            self.assertLessEqual(region.right, self.NARROW[0], name)


class _FakeButton:
    def __init__(self, ident): self.id = ident


class _ButtonPressed:
    def __init__(self, button): self.button = button


class RestorePollDeadlineTests(_Fixture):
    """How long the monitor watches a dispatched restore before crying stall.

    The deadline belongs to the COORDINATOR, not to the watcher:
    `agent_restore` gives a `restoring` record up to the project's
    `frozen.restore_ack_grace` to be acknowledged by its replacement agent's
    SessionStart hook before it may be liveness-confirmed instead. A watcher
    with a shorter fixed deadline warns and stops its timer while the restore is
    still legitimately in flight — so a project that raised the grace would see
    a spurious "still restoring" on every successful restore, and never the
    success.
    """

    def _timeouts(self, cls, record):
        """Every `settle_timeout` the poll hands the verdict, driving the real
        `_poll_frozen_outcome` with a captured timer."""
        seen: list[float] = []
        app = self.app(cls, [])
        app.notify = lambda msg, **kw: None
        app.call_later = lambda fn, *a: None
        app._refresh_data = lambda: None
        ticks: list = []
        app.set_interval = lambda interval, fn: ticks.append(fn) or _FakeTimer()

        class _View:
            def invalidate(self): pass
            def by_id(self, rid): return record

        def spy(rec, prev, elapsed, *, dispatch_grace, settle_timeout):
            seen.append(settle_timeout)
            return False, "", False

        # `monitor_shared.agent_sessions` IS the shared module object, so these
        # must be scoped patches rather than assignments — a raw assignment
        # leaks into every other module in the same suite process.
        sessions = monitor_shared.agent_sessions
        with patch.object(sessions, "SessionsView", lambda *a, **k: _View()), \
                patch.object(sessions, "restore_verdict", spy):
            app._poll_frozen_outcome(RECORD, "restore", 0)
            ticks[0]()
        return seen

    def test_the_deadline_follows_the_projects_configured_grace(self):
        """THE defect: a 60s grace with a 40s watcher means every successful
        restore is reported as a stall."""
        cfg = self.root / "aitasks" / "metadata"
        cfg.mkdir(parents=True)
        (cfg / "project_config.yaml").write_text(
            "frozen:\n  restore_ack_grace: 60\n")
        rec = _FakeRecord(str(self.root))
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                seen = self._timeouts(cls, rec)
                self.assertTrue(seen)
                self.assertGreater(
                    seen[0], 60.0,
                    "the watcher gives up before the coordinator does")

    def test_the_default_grace_keeps_the_value_the_viewer_shipped(self):
        """Negative control, and a compatibility pin: at the default grace this
        is still 10 dispatch + 20 ack + 10 slack. The old constant was right for
        the default and wrong as a constant."""
        rec = _FakeRecord(str(self.root))
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.assertEqual(self._timeouts(cls, rec)[0], 40.0)

    def test_the_grace_is_read_from_the_records_root_not_the_apps(self):
        """`freeze --all` spans projects, so a monitor can be watching a record
        that belongs to another repo with another config."""
        other = self.tmp / "other-repo"
        (other / "aitasks" / "metadata").mkdir(parents=True)
        (other / "aitasks" / "metadata" / "project_config.yaml").write_text(
            "frozen:\n  restore_ack_grace: 90\n")
        rec = _FakeRecord(str(other))
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                self.assertGreater(self._timeouts(cls, rec)[0], 90.0)

    def test_a_missing_record_still_produces_a_finite_deadline(self):
        """Pre-begin the record does not exist yet; the poll must still arm a
        deadline rather than raising on the keypress."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                seen = self._timeouts(cls, None)
                self.assertEqual(seen[0], 40.0)


class _FakeRecord:
    def __init__(self, root): self.root = root
    restore_attempts = 0


class _FakeTimer:
    def stop(self): pass


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
