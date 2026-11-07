"""The minimonitor follows the agent beside it by PANE ID, not window index (t2227).

Symptom (observed live, more than once): a pick launched from a window while that
origin window was being killed showed the ORIGIN agent's name in the new
minimonitor's docked "this agent" panel — permanently — while its phase line
already belonged to the real agent. Mechanism:

1. the new pick window opens at index N+1, after the origin at N;
2. the origin is killed and ``renumber-windows`` moves the new window to N;
3. the minimonitor's tick reads its own index as N, but the snapshots come from
   a scan taken before the kill, where the origin agent is still at N;
4. the index-keyed lookup resolves the origin, and the one-shot panel freezes it.

Every case here drives the REAL ``MiniMonitorApp`` / ``TmuxMonitor`` methods over
scripted tmux answers — nothing re-implements the lookup it asserts (the
anti-pattern t1693 retired from ``test_multi_session_minimonitor.sh``).

**Pre-fix control.** The fixtures also answer the pre-fix query shape (the
``display-message`` reply) and keep ``_own_window_index`` set, so the same file
run against the pre-fix source reaches the old behaviour instead of crashing in
setup. To run it as a baseline, copy this file into a checkout of the old tree's
``tests/`` and run it there with ``AITASK_TEST_ASSERT_BASELINE=<that tree>`` —
the guard below then refuses to run unless both modules really load from it,
so a baseline run can never silently test the fixed code.

Run: python3 tests/test_minimonitor_own_identity_renumber.py
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# Nothing here may touch the pane the suite runs in (t1240).
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from monitor import minimonitor_app as mm  # noqa: E402
from monitor import monitor_core as mc  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    PaneCategory, PaneSnapshot, TmuxPaneInfo,
)

_BASELINE = os.environ.get("AITASK_TEST_ASSERT_BASELINE")
if _BASELINE:
    _root = os.path.realpath(_BASELINE) + os.sep
    for _mod in (mm, mc):
        if not os.path.realpath(_mod.__file__).startswith(_root):
            raise SystemExit(
                f"baseline guard: {_mod.__name__} loaded from {_mod.__file__}, "
                f"not from {_BASELINE} — this run would not test the baseline")

SESSION = "aitasks"


def snap(pane_id: str, window_index: str, window_name: str, *,
         pane_index: str = "0",
         category: PaneCategory = PaneCategory.AGENT) -> PaneSnapshot:
    return PaneSnapshot(
        pane=TmuxPaneInfo(
            window_index=window_index, window_name=window_name,
            pane_index=pane_index, pane_id=pane_id, pane_pid=4000,
            current_command="claude", width=80, height=24,
            category=category, session_name=SESSION,
        ),
        content="", timestamp=0.0, idle_seconds=0.0, is_idle=False,
    )


class _Tmux:
    """Scripted tmux: the CURRENT truth about this pane's window.

    ``window`` is ``(window_id, window_index, window_name, members)`` as tmux
    would report it now; ``None`` makes every query fail (a tmux hiccup). Both
    the post-fix ``list-panes -t $TMUX_PANE`` listing and the pre-fix
    ``display-message`` reply are answered from it, so a baseline run reaches
    the old code's behaviour.
    """

    def __init__(self, window):
        self.window = window
        self.calls: list[list[str]] = []
        self.sent: list[tuple[str, str]] = []
        self.killed: list[str] = []

    def _answer(self, args):
        self.calls.append(list(args))
        if self.window is None:
            return 1, ""
        wid, widx, wname, members = self.window
        if args[0] == "display-message":
            return 0, f"{wid}\t{widx}\t{wname}\n"
        if args[0] == "list-panes":
            fmt = args[args.index("-F") + 1]
            target = args[args.index("-t") + 1]
            if target not in members and target != wid:
                return 1, ""
            if fmt == mm.FROZEN_AWARE_PANE_FORMAT:
                # id, pid, shadow, kind, frozen, dead, scratch — all plain.
                return 0, "".join(f"{p}\t4000\t\t\t\t0\t\n" for p in members)
            fields = {"#{pane_id}": None, "#{window_id}": wid,
                      "#{window_index}": widx, "#{window_name}": wname}
            rows = []
            for p in members:
                rows.append("\t".join(
                    p if spec == "#{pane_id}" else fields[spec]
                    for spec in fmt.split("\t")))
            return 0, "\n".join(rows) + "\n"
        return 1, ""

    async def tmux_run_async(self, args, timeout=None):
        return self._answer(args)

    def tmux_run(self, args, timeout=None):
        return self._answer(args)

    def send_keys(self, pane_id, key):
        self.sent.append((pane_id, key))
        return True

    def kill_agent_pane_smart(self, pane_id, **kw):
        self.killed.append(pane_id)
        return True, False


class _FakePanel:
    def __init__(self) -> None:
        self.mounted: list = []
        self.removals = 0
        self.display = False
        self.styles = SimpleNamespace(max_height=None)

    async def remove_children(self):
        self.removals += 1

    async def mount_all(self, widgets):
        self.mounted = list(widgets)


def make_app(own_pane: str, snapshots, tmux: _Tmux):
    panel = _FakePanel()
    app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
    app.query_one = lambda *a, **k: panel
    app._monitor = tmux
    app._session = SESSION
    app._snapshots = {s.pane.pane_id: s for s in snapshots}
    app._own_window_id = None
    app._own_window_index = None
    app._own_window_name = None
    app._own_identity_confirmed = False
    app._own_panel_built = False
    app._own_card = None
    app._own_identity_text = ""
    app._own_mark_state = None
    app._target_width = 40
    app._focused_pane_id = None
    app._task_cache = SimpleNamespace(
        get_task_id_for_pane=lambda p: None,
        get_task_info=lambda t, s=None: None,
    )
    app._init_agent_marks()
    app._kill_target_state = lambda pane_id: "live"
    app.pushed: list = []
    app.push_screen = lambda screen, callback=None: app.pushed.append(
        (screen, callback))
    app.notes: list[str] = []
    app.notify = lambda msg, **kw: app.notes.append(str(msg))
    app.call_later = lambda *a, **k: None
    app.own_pane = own_pane
    app.panel = panel
    return app


def tick(app) -> None:
    """The identity half of `_refresh_data`: the flag is reset, then set from the
    real query's return value — the exact two lines the tick runs."""
    app._own_identity_confirmed = False
    with patch.dict(os.environ, {"TMUX_PANE": app.own_pane}):
        app._own_identity_confirmed = asyncio.run(app._update_own_window_info())


def build_panel(app) -> None:
    asyncio.run(app._maybe_build_own_agent_panel())


def panel_name(app) -> str:
    return app.panel.mounted[1].render().plain


def press_kill(app) -> list[str]:
    """`k` for real: the dialog is recorded, then its callback is confirmed."""
    app._monitor.killed.clear()
    app.pushed.clear()
    app.action_kill_own_agent()
    for _screen, callback in app.pushed:
        callback(True)
    return list(app._monitor.killed)


def press_enter(app) -> list[tuple[str, str]]:
    app._monitor.sent.clear()
    with patch.dict(os.environ, {"TMUX_PANE": app.own_pane}), \
            patch.object(mc, "_is_companion_process", lambda pid: False):
        app._send_enter_to_sibling()
    return list(app._monitor.sent)


# -- Fixture A: the 1981_3 sighting -------------------------------------------
# Own minimonitor %10 beside agent %9 (`agent-pick-1981_3`, window @5). An
# earlier window closed: @5 is now index 11. The snapshots predate the shift —
# %9 still carries 12, and the NEIGHBOUR %20 (`agent-pick-1893_6`) carries 11.

def fixture_a():
    tmux = _Tmux(("@5", "11", "agent-pick-1981_3", ["%9", "%10"]))
    snaps = [snap("%9", "12", "agent-pick-1981_3"),
             snap("%20", "11", "agent-pick-1893_6")]
    return make_app("%10", snaps, tmux), "%9", "agent-pick-1981_3", \
        "agent-pick-1893_6"


# -- Fixture B: the confirmed trigger, origin window killed at launch ----------
# The pick window (agent %513 + minimonitor %514) opened at index 11 after its
# origin `agent-explore-1` (%400) at 10; the origin was killed, so the pick
# window is now 10 — but the pre-kill scan still has the origin at 10.

def fixture_b():
    tmux = _Tmux(("@227", "10", "agent-pick-2227", ["%513", "%514"]))
    snaps = [snap("%400", "10", "agent-explore-1"),
             snap("%513", "11", "agent-pick-2227")]
    return make_app("%514", snaps, tmux), "%513", "agent-pick-2227", \
        "agent-explore-1"


FIXTURES = {"renumber_1981_3": fixture_a, "origin_killed_at_launch": fixture_b}


class RenumberRaceTests(unittest.TestCase):
    """(a) panel identity, (b) lookups, (b2) real action handlers."""

    def test_a_the_panel_names_the_followed_agent(self):
        for label, make in FIXTURES.items():
            with self.subTest(fixture=label):
                app, _own, own_name, neighbour = make()
                tick(app)
                build_panel(app)
                name = panel_name(app)
                self.assertIn(own_name, name)
                self.assertNotIn(neighbour, name,
                                 f"the panel froze the neighbour {neighbour}")

    def test_b_lookups_resolve_the_followed_pane(self):
        for label, make in FIXTURES.items():
            with self.subTest(fixture=label):
                app, own, _n, _nb = make()
                tick(app)
                agent = app._find_own_agent_snapshot()
                self.assertIsNotNone(agent)
                self.assertEqual(agent.pane.pane_id, own)
                with patch.dict(os.environ, {"TMUX_PANE": app.own_pane}):
                    self.assertEqual(app._find_sibling_pane_id(), own)

    def test_b2_kill_targets_the_followed_pane(self):
        for label, make in FIXTURES.items():
            with self.subTest(fixture=label):
                app, own, _n, _nb = make()
                tick(app)
                self.assertEqual(press_kill(app), [own],
                                 "`k` dispatched the kill to another pane")

    def test_b2_enter_reaches_the_followed_pane(self):
        for label, make in FIXTURES.items():
            with self.subTest(fixture=label):
                app, own, _n, _nb = make()
                tick(app)
                self.assertEqual(press_enter(app), [(own, "Enter")])


class UnconfirmedIdentityTests(unittest.TestCase):
    """(c) a failed first query with a seeded window id; (c2) moved + failed."""

    def test_c_failed_first_query_refuses_every_action(self):
        app, _own, _n, _nb = fixture_a()
        # The mount seed answered (it fills only empty fields)…
        app._own_window_id, app._own_window_index = "@5", "11"
        # …but the first tick's query fails.
        app._monitor.window = None
        tick(app)
        self.assertIsNone(app._find_own_agent_snapshot())
        self.assertEqual(press_kill(app), [], "k acted on an unconfirmed identity")
        self.assertEqual(app.pushed, [], "k even opened a dialog")
        self.assertEqual(press_enter(app), [])

    def test_c_the_fallback_confirms_for_itself_and_never_reads_the_seed(self):
        app, own, _n, _nb = fixture_a()
        app._own_window_id = "@5"          # seeded, unconfirmed
        app._monitor.window = ("@5", "11", "agent-pick-1981_3", ["%9", "%10"])
        # No confirmed tick yet: rung 1 must refuse, rung 2 lists $TMUX_PANE.
        self.assertEqual(press_enter(app), [(own, "Enter")])
        listing = [c for c in app._monitor.calls if c[0] == "list-panes"]
        self.assertTrue(listing)
        self.assertEqual(listing[-1][:3], ["list-panes", "-t", "%10"])
        self.assertNotIn("@5", listing[-1])

    def test_c_the_fallback_refuses_a_listing_without_this_pane(self):
        app, _own, _n, _nb = fixture_a()
        app._own_window_id = "@5"
        # A listing that answers but does not contain %10: not OUR window.
        app._monitor.window = ("@5", "11", "agent-pick-1981_3", ["%9"])
        app._monitor.tmux_run = lambda args, timeout=None: (
            0, "%9\t4000\t\t\t\t0\t\n")
        self.assertEqual(press_enter(app), [])
        self.assertIn("Own window not confirmed", app.notes)

    def test_c2_confirmed_then_moved_then_failed(self):
        app, _own, _n, _nb = fixture_a()
        tick(app)                                          # tick 1: {%9, %10}
        build_panel(app)
        self.assertIn("agent-pick-1981_3", panel_name(app))
        # swap-pane: %9 leaves for another window, %40 arrives in ours.
        app._snapshots["%40"] = snap("%40", "11", "agent-pick-77")
        app._monitor.window = None                         # tick 2 fails
        tick(app)
        self.assertEqual(press_kill(app), [],
                         "a stale cached membership steered a kill")
        self.assertEqual(press_enter(app), [])
        # Display keeps the last validated set: no flicker, no teardown.
        shown = app._find_own_window_snapshot()
        self.assertIsNotNone(shown)
        self.assertEqual(shown.pane.pane_id, "%9")
        removals = app.panel.removals
        build_panel(app)
        self.assertEqual(app.panel.removals, removals)
        # Tick 3 validates the new truth: actions and panel follow %40.
        app._monitor.window = ("@5", "11", "agent-pick-77", ["%40", "%10"])
        tick(app)
        self.assertEqual(press_kill(app), ["%40"])
        build_panel(app)
        self.assertIn("agent-pick-77", panel_name(app))


class RefreshWithdrawsConfirmationTests(unittest.TestCase):
    """The REAL `_refresh_data` withdraws confirmation before its first await.

    `tick()` above resets the flag itself, so it cannot see where the real
    refresh does. This drives `_refresh_data` and holds it suspended in its
    first await — the session mapping — exactly where a `swap-pane` landing
    mid-refresh would leave the previous tick's confirmation standing if the
    reset sat after it. A user action in that window must refuse.
    """

    def test_an_action_during_a_suspended_refresh_refuses(self):
        app, _own, _n, _nb = fixture_a()
        tick(app)                                   # tick 1 validated {%9, %10}
        self.assertTrue(app._own_identity_confirmed, "precondition")
        app._refresh_inflight = False
        app._scan_rerun = False
        # %9 is moved out (swap-pane) while the next refresh is in flight.
        app._monitor.window = ("@5", "11", "agent-pick-77", ["%40", "%10"])
        reached, release = asyncio.Event(), asyncio.Event()

        async def held_mapping():
            reached.set()
            await release.wait()
            return {}

        app._monitor.get_session_to_project_mapping_async = held_mapping
        seen: dict = {}

        async def runner():
            refresh = asyncio.create_task(app._refresh_data(scan=False))
            await reached.wait()                    # suspended at its 1st await
            seen["confirmed"] = app._own_identity_confirmed
            seen["killed"] = press_kill(app)
            seen["sent"] = press_enter_no_listing(app)
            refresh.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await refresh

        asyncio.run(runner())
        self.assertFalse(seen["confirmed"],
                         "the previous tick's confirmation survived into the "
                         "suspended refresh")
        self.assertEqual(seen["killed"], [],
                         "`k` acted on a membership the refresh was re-checking")
        self.assertEqual(seen["sent"], [])
        self.assertFalse(app._refresh_inflight,
                         "the cancelled refresh stranded the in-flight flag")


def press_enter_no_listing(app) -> list[tuple[str, str]]:
    """Enter while rung 2's own listing also fails (tmux unavailable): with
    confirmation withdrawn, nothing may be dispatched at all."""
    saved = app._monitor.tmux_run
    app._monitor.tmux_run = lambda args, timeout=None: (1, "")
    try:
        return press_enter(app)
    finally:
        app._monitor.tmux_run = saved


class PanelRebuildTests(unittest.TestCase):
    """(d) a different resolved pane rebuilds; (e) a rename of the same does not."""

    def test_d_a_different_resolved_pane_rebuilds_the_panel(self):
        app, _own, _n, _nb = fixture_a()
        tick(app)
        build_panel(app)
        app._snapshots["%30"] = snap("%30", "11", "agent-pick-30")
        app._monitor.window = ("@5", "11", "agent-pick-30", ["%30", "%10"])
        tick(app)
        build_panel(app)
        self.assertIn("agent-pick-30", panel_name(app),
                      "the panel kept a pane that is no longer beside it")

    def test_e_a_rename_of_the_same_pane_keeps_the_built_panel(self):
        app, _own, _n, _nb = fixture_a()
        tick(app)
        build_panel(app)
        removals = app.panel.removals
        app._snapshots["%9"] = snap("%9", "11", "agent-renamed")
        tick(app)
        build_panel(app)
        self.assertEqual(app.panel.removals, removals)
        self.assertIn("agent-pick-1981_3", panel_name(app))


class OwnWindowListingParserTests(unittest.TestCase):
    """`parse_own_window_listing` — the whole-listing validation."""

    def parse(self, stdout, own="%7"):
        return mm.parse_own_window_listing(stdout, own)

    def test_a_valid_listing(self):
        self.assertEqual(
            self.parse("%6\t@1\t3\tw\n%7\t@1\t3\tw\n"),
            ("@1", "3", "w", frozenset({"%6", "%7"})))

    def test_blank_lines_are_not_records(self):
        self.assertIsNotNone(self.parse("\n%7\t@1\t3\tw\n\n"))

    def test_refusals(self):
        for label, stdout in {
            "empty": "",
            "own pane missing": "%6\t@1\t3\tw\n",
            "two windows": "%6\t@2\t4\tx\n%7\t@1\t3\tw\n",
            "short record": "%7\t@1\t3\n",
            "pane id not %-prefixed": "7\t@1\t3\tw\n",
            "window id not @-prefixed": "%7\t1\t3\tw\n",
        }.items():
            with self.subTest(label):
                self.assertIsNone(self.parse(stdout))

    def test_a_tab_in_the_name_stays_in_the_name(self):
        self.assertEqual(self.parse("%7\t@1\t3\ta\tb\n")[2], "a\tb")

    def test_no_own_pane_refuses(self):
        self.assertIsNone(self.parse("%7\t@1\t3\tw\n", own=""))


class CollapseDecisionRenumberTests(unittest.TestCase):
    """monitor_core: the kill's window collapse lists the pane's CURRENT window.

    The cache holds %7 at index 4 (stale). After a renumber, index 4 is the
    neighbouring window — holding only a shadow helper — while %7's real window
    still holds a second live agent %8. Listing the stale index reads "no other
    agent" and collapses the WRONG decision into `kill-window`.
    """

    def monitor(self):
        mon = mc.TmuxMonitor.__new__(mc.TmuxMonitor)
        mon.session = "s1"
        mon._pane_cache = {"%7": TmuxPaneInfo(
            window_index="4", window_name="agent-pick-7", pane_index="0",
            pane_id="%7", pane_pid=1, current_command="claude", width=80,
            height=24, category=PaneCategory.AGENT, session_name="s1")}
        mon._last_content, mon._last_change_time = {}, {}
        mon.calls = []

        def tmux_run(args, timeout=5.0):
            mon.calls.append(list(args))
            if args[0] == "list-panes":
                target = args[args.index("-t") + 1]
                if target == "%7":                 # its real window, now
                    return 0, "%7\t1\t\t\t\t0\t\n%8\t2\t\t\t\t0\t\n"
                if target == "=s1:4":              # the neighbour, post-renumber
                    return 0, "%50\t3\t%51\t\t\t0\t\n"
                return 1, ""
            return 0, ""

        mon.tmux_run = tmux_run
        mon._drop_session_record = lambda rid: True
        return mon

    def test_collapse_reads_the_panes_current_window(self):
        mon = self.monitor()
        with patch.object(mc, "_is_companion_process", lambda pid: False):
            self.assertIs(mon._collapse_window_for("%7"), False)

    def test_a_sibling_agent_keeps_the_kill_to_the_one_pane(self):
        mon = self.monitor()
        with patch.object(mc, "_is_companion_process", lambda pid: False), \
                patch.object(mc.TmuxMonitor, "_kill_bound_helpers",
                             lambda self, pane_id: []):
            mon.kill_agent_pane_smart("%7")
        self.assertIn(["kill-pane", "-t", "%7"], mon.calls)
        self.assertFalse(any(c[0] == "kill-window" for c in mon.calls),
                         "the stale index collapsed a window with a live agent")

    def test_switch_selects_and_searches_the_panes_current_window(self):
        """`switch_to_pane` (and its companion lookup) target the pane id, so a
        stale cached index cannot select the neighbouring window."""
        mon = self.monitor()
        with patch.object(mc, "_is_companion_process", lambda pid: False):
            self.assertTrue(mon.switch_to_pane("%7", prefer_companion=True))
        self.assertIn(["select-window", "-t", "%7"], mon.calls)
        listings = [c for c in mon.calls if c[0] == "list-panes"]
        self.assertEqual([c[2] for c in listings], ["%7"])
        self.assertFalse(any("=s1:4" in c for c in mon.calls),
                         "the cached index was used as a tmux target")


if __name__ == "__main__":
    unittest.main(verbosity=2)
