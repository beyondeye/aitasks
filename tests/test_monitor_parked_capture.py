"""Parked agents are never captured or classified (t1685).

Parking an agent is the one mark state that costs nothing: the pane is excluded
from `capture_pane_content_async`'s gather and from the `_classify_batch`
payload, yet it must still render a row when the `P` filter is off and must stay
in discovery so the mark purge cannot reap its own mark.

The three properties are asserted on **call arguments and returned state**, never
inferred from timing:

- exclusion — the pane id is absent from the recorded capture calls and from the
  batch handed to `_classify_batch`;
- survival — `commit_snapshots` still emits a snapshot for it, flagged `parked`,
  built without touching the idle clock;
- discovery — `last_discovered_agents()` still names it, with a negative control
  proving the same purge drops it once the window is genuinely gone.

CHARACTERIZATION (pre-phase, t1685 risk mitigation
`characterize_capture_failure_drop`): `CaptureFailureDropTests` below pins the
PRE-EXISTING `if result is None: continue` behaviour of `commit_snapshots`. The
parked branch lands immediately beside that drop, so the drop's own semantics are
pinned first and separately — a parked pane must not be routed down the
failed-capture path, and a failed capture must not start looking parked.

NEGATIVE CONTROL for the characterization: make `commit_snapshots` emit a
snapshot for a `result is None` entry -> `test_a_failed_capture_produces_no_
snapshot` fails. Make it drop the pane id from the `_clean_stale` set ->
`test_a_failed_capture_still_counts_as_present_for_clean_stale` fails.
"""
from __future__ import annotations

import contextlib
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from unittest.mock import patch  # noqa: E402

import agent_marks  # noqa: E402
from monitor import monitor_core  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    ClassifyResult, PaneCategory, TmuxMonitor, TmuxPaneInfo,
)


def pane(session: str, window: str, pane_id: str,
         category: PaneCategory = PaneCategory.AGENT) -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index="1", window_name=window, pane_index="0", pane_id=pane_id,
        pane_pid=4242, current_command="node", width=80, height=24,
        category=category, session_name=session,
    )


def _monitor() -> TmuxMonitor:
    return TmuxMonitor(session="demo", multi_session=False)


class CaptureFailureDropTests(unittest.TestCase):
    """Pre-existing behaviour of the `result is None` branch in
    `commit_snapshots`, pinned before the parked branch is written beside it."""

    def test_a_failed_capture_produces_no_snapshot(self):
        mon = _monitor()
        ok = pane("demo", "agent-ok", "%1")
        bad = pane("demo", "agent-bad", "%2")
        gen = mon._next_generation()
        snaps = mon.commit_snapshots(gen, [
            (ok, "hello", ClassifyResult(compare_value="hello")),
            (bad, None, None),
        ])
        self.assertIsNotNone(snaps)
        self.assertIn("%1", snaps)
        self.assertNotIn(
            "%2", snaps,
            "a pane whose capture failed must produce no snapshot this tick",
        )

    def test_a_failed_capture_leaves_prior_content_untouched(self):
        """The drop is what preserves `_last_content` across a transient fault.

        `_apply_bookkeeping` is the only writer of that dict, and the dropped
        entry never reaches it, so the pane's idle clock keeps running off the
        content it last actually had.
        """
        mon = _monitor()
        p = pane("demo", "agent-a", "%1")
        gen = mon._next_generation()
        mon.commit_snapshots(gen, [(p, "first", ClassifyResult(compare_value="first"))])
        self.assertEqual(mon._last_content["%1"], "first")

        gen = mon._next_generation()
        mon.commit_snapshots(gen, [(p, None, None)])
        self.assertEqual(
            mon._last_content["%1"], "first",
            "a failed capture must not overwrite the pane's last known content",
        )

    def test_a_failed_capture_still_counts_as_present_for_clean_stale(self):
        """A dropped pane is still in `classified`, so `_clean_stale` keeps it.

        Without this, one failed capture would evict the pane's bookkeeping and
        the next successful tick would restart its idle clock from zero.
        """
        mon = _monitor()
        a = pane("demo", "agent-a", "%1")
        b = pane("demo", "agent-b", "%2")
        gen = mon._next_generation()
        mon.commit_snapshots(gen, [
            (a, "aaa", ClassifyResult(compare_value="aaa")),
            (b, "bbb", ClassifyResult(compare_value="bbb")),
        ])
        self.assertEqual(set(mon._last_content), {"%1", "%2"})

        # %2 fails this tick; %1 succeeds. Both are still in `classified`.
        gen = mon._next_generation()
        mon.commit_snapshots(gen, [
            (a, "aaa2", ClassifyResult(compare_value="aaa2")),
            (b, None, None),
        ])
        self.assertEqual(
            set(mon._last_content), {"%1", "%2"},
            "the failed pane was swept as stale — its idle clock will restart",
        )

        # A pane genuinely absent from `classified` IS swept: the positive
        # control that makes the assertion above discriminating.
        gen = mon._next_generation()
        mon.commit_snapshots(gen, [(a, "aaa3", ClassifyResult(compare_value="aaa3"))])
        self.assertEqual(set(mon._last_content), {"%1"})

    def test_a_superseded_generation_commits_nothing(self):
        """The guard the parked branch must land *after*, not before."""
        mon = _monitor()
        p = pane("demo", "agent-a", "%1")
        stale_gen = mon._next_generation()
        mon._next_generation()  # a newer capture reserves
        self.assertIsNone(
            mon.commit_snapshots(
                stale_gen, [(p, "x", ClassifyResult(compare_value="x"))]
            )
        )
        self.assertEqual(mon._last_content, {})



class CaptureExclusionTests(unittest.IsolatedAsyncioTestCase):
    """AC5 — a parked agent reaches neither the capture gather nor the batch.

    Asserted on the recorded CALL ARGUMENTS, never inferred from timing: a
    timing-based check would pass for an implementation that captured the pane
    and threw the result away, which is the whole cost this feature exists to
    avoid.
    """

    def _monitor(self, panes, shadows=()):
        mon = _monitor()
        self.captured: list[str] = []
        self.batched: list[str] = []

        async def fake_discover(enum_sink=None):
            if enum_sink is not None:
                enum_sink.append(frozenset({"demo"}))
            return list(panes), list(shadows)

        async def fake_capture(pane_id, pane=None):
            self.captured.append(pane_id)
            return (pane_id, f"content-of-{pane_id}")

        async def run_offloaded(fn):
            return fn()

        mon.discover_panes_with_shadows_async = fake_discover
        mon.capture_pane_content_async = fake_capture
        mon._run_offloaded = run_offloaded
        return mon

    async def _run(self, mon):
        real_batch = monitor_core._classify_batch

        def spy(items, patterns):
            self.batched.extend(p.pane_id for p, _, _ in items)
            return real_batch(items, patterns)

        with patch.object(monitor_core, "_classify_batch", spy):
            gen, classified = await mon.capture_all_classified_async()
        return gen, classified

    async def test_a_parked_pane_is_never_captured_or_classified(self):
        live = pane("demo", "agent-live", "%1")
        parked = pane("demo", "agent-parked", "%2")
        mon = self._monitor([live, parked])
        mon.set_parked_agents({("demo", "agent-parked")})

        gen, classified = await self._run(mon)

        self.assertEqual(self.captured, ["%1"])
        self.assertEqual(self.batched, ["%1"])
        self.assertNotIn("%2", self.captured)
        self.assertNotIn("%2", self.batched)

    async def test_the_control_shows_the_exclusion_is_what_removes_it(self):
        """NEGATIVE CONTROL: with nothing parked, the same pane IS captured and
        classified — so the assertions above discriminate on the parked set."""
        live = pane("demo", "agent-live", "%1")
        other = pane("demo", "agent-parked", "%2")
        mon = self._monitor([live, other])
        mon.set_parked_agents(set())

        await self._run(mon)

        self.assertEqual(sorted(self.captured), ["%1", "%2"])
        self.assertEqual(sorted(self.batched), ["%1", "%2"])

    async def test_a_parked_pane_still_commits_a_snapshot(self):
        """It must render when the filter is off, so it cannot be routed down
        the `result is None` path that `CaptureFailureDropTests` pins."""
        live = pane("demo", "agent-live", "%1")
        parked = pane("demo", "agent-parked", "%2")
        mon = self._monitor([live, parked])
        mon.set_parked_agents({("demo", "agent-parked")})

        gen, classified = await self._run(mon)
        snaps = mon.commit_snapshots(gen, classified)

        self.assertIn("%2", snaps, "the parked row vanished from the snapshots")
        parked_snap = snaps["%2"]
        self.assertTrue(parked_snap.parked)
        self.assertEqual(parked_snap.content, "")
        self.assertFalse(parked_snap.is_idle)
        self.assertFalse(parked_snap.awaiting_input)
        self.assertNotIn(
            "%2", mon._last_content,
            "a parked pane reached _apply_bookkeeping and touched the idle "
            "clock — it will read as freshly-changed the moment it is unparked",
        )

    async def test_only_agent_panes_are_parkable(self):
        """A shell or TUI window sharing a parked agent's name must not be
        skipped: the mark vocabulary is agent-scoped."""
        other = pane("demo", "agent-parked", "%3", PaneCategory.OTHER)
        mon = self._monitor([other])
        mon.set_parked_agents({("demo", "agent-parked")})
        await self._run(mon)
        self.assertEqual(self.captured, ["%3"])

    async def test_a_shadow_pane_is_never_filtered(self):
        """A minimonitor following a parked agent keeps its shadow working."""
        parked = pane("demo", "agent-parked", "%2")
        shadow = pane("demo", "agent-parked", "%9")
        object.__setattr__(shadow, "shadow_target", "agent-parked")
        mon = self._monitor([parked], [shadow])
        mon.set_parked_agents({("demo", "agent-parked")})
        await self._run(mon)
        self.assertIn("%9", self.captured)
        self.assertNotIn("%2", self.captured)


class DiscoverySurvivalTests(unittest.IsolatedAsyncioTestCase):
    """AC6 — parking skips CAPTURE only; discovery must still see the agent.

    This is the load-bearing correctness fact of the feature. `sweep_liveness`
    keys on discovery, so a parked agent that dropped out of it would have its
    own mark deleted by the next purge — the feature would un-park what it
    parked, silently, within ten minutes.
    """

    async def _capture(self, parked_names=()):
        mon = _monitor()
        panes = [pane("demo", "agent-live", "%1"),
                 pane("demo", "agent-parked", "%2")]

        async def fake_discover(enum_sink=None):
            if enum_sink is not None:
                enum_sink.append(frozenset({"demo"}))
            return list(panes), []

        async def fake_capture(pane_id, pane=None):
            return (pane_id, "x")

        async def run_offloaded(fn):
            return fn()

        mon.discover_panes_with_shadows_async = fake_discover
        mon.capture_pane_content_async = fake_capture
        mon._run_offloaded = run_offloaded
        mon.set_parked_agents({("demo", n) for n in parked_names})
        gen, classified = await mon.capture_all_classified_async()
        mon.commit_snapshots(gen, classified)
        return mon

    async def test_a_parked_agent_stays_in_discovery(self):
        mon = await self._capture(parked_names=["agent-parked"])
        self.assertIn(
            ("demo", "agent-parked"), mon.last_discovered_agents(),
            "the parked agent left discovery — the next purge will delete the "
            "very mark that parked it",
        )

    async def test_a_purge_run_while_parked_keeps_the_mark(self):
        mon = await self._capture(parked_names=["agent-parked"])
        root = "/repo/a"
        mf = agent_marks.MarksFile(version=agent_marks.SCHEMA_VERSION, marks=[])
        agent_marks.cycle(mf, root, "agent-parked")
        agent_marks.cycle(mf, root, "agent-parked")  # -> parked

        observed = {root: {w for _, w in mon.last_discovered_agents()}}
        dropped = agent_marks.sweep_liveness(mf, observed, {root})

        self.assertEqual(dropped, [])
        self.assertEqual(len(mf.marks), 1)

    async def test_the_negative_control_drops_it_when_the_window_is_gone(self):
        """Without this, the test above proves nothing: a sweep that never drops
        anything would pass it too."""
        mon = await self._capture(parked_names=["agent-parked"])
        root = "/repo/a"
        mf = agent_marks.MarksFile(version=agent_marks.SCHEMA_VERSION, marks=[])
        agent_marks.cycle(mf, root, "agent-parked")
        agent_marks.cycle(mf, root, "agent-parked")

        # Same purge, same parked mark — but the agent is genuinely absent from
        # this tick's discovery.
        observed = {root: {"agent-live"}}
        dropped = agent_marks.sweep_liveness(mf, observed, {root})

        self.assertEqual([d.window for d in dropped], ["agent-parked"])
        self.assertEqual(mf.marks, [])

class RefreshOrderingTests(unittest.IsolatedAsyncioTestCase):
    """The parked set must be published BEFORE the tick's capture (t1685 §4.1).

    This is the case the pre-t1685 ordering leaks. `_refresh_data` used to
    capture first and resolve the session→root map and the marks afterwards, so
    on the FIRST tick the monitor knew about no parked agents at all — an
    already-parked agent was captured and classified once on every launch, which
    is a permanent per-launch cost and a direct violation of AC5.

    Asserted on the ORDER of the recorded calls, because the leak is invisible in
    any steady-state assertion: from tick two onward the previous tick's publish
    is already in place and the wrong ordering looks correct.
    """

    async def _run_one_refresh(self, cls):
        import tempfile
        from monitor.monitor_shared import AgentMarksMixin

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "repo"
        root.mkdir()
        store = Path(tmp.name) / "marks.json"

        # A mark that is ALREADY parked before the app ever refreshes.
        mf = agent_marks.load(store)
        agent_marks.cycle(mf, root, "agent-parked")
        agent_marks.cycle(mf, root, "agent-parked")
        agent_marks.dump(mf, store)

        order: list[str] = []
        published: list[frozenset] = []

        class _Mon:
            multi_session = False
            capture_generation = 1

            def set_parked_agents(self, pairs):
                order.append("publish")
                published.append(frozenset(pairs))

            async def capture_all_classified_async(self):
                order.append("capture")
                return 1, []

            async def capture_all_async(self):
                order.append("capture")
                return {}

            def commit_snapshots(self, gen, classified):
                return {}

            async def get_session_to_project_mapping_async(self):
                return {"demo": root}

            def get_session_to_project_mapping(self):
                return {"demo": root}

            def control_state(self):
                return None

            def get_shadow_snapshots(self):
                return {}

        app = cls.__new__(cls)
        app._monitor = _Mon()
        app._session = "demo"
        app._project_root = root
        app._marks_view = agent_marks.MarksView(store)
        app._marks_purge_due_at = float("inf")
        app._marks_purge_inflight = False
        app._maintenance_inflight = False
        app._refresh_inflight = False
        app._session_root_map = {}
        app._hide_parked = False
        app._snapshots = {}
        app._task_cache = _FakeCache()
        app._completed_pane_ids = frozenset()
        app._own_window_name = "agent-followed"
        app._own_identity_confirmed = False
        app._focused_pane_id = None
        app._active_zone = None
        app._parked_pane_ids = frozenset()
        # Stop the refresh right after the capture — everything below it is DOM
        # work this ordering test has no opinion about.
        app._compute_completed_panes = lambda: frozenset()
        return app, order, published, root

    async def test_the_monitor_publishes_before_it_captures(self):
        from monitor.monitor_app import MonitorApp

        app, order, published, root = await self._run_one_refresh(MonitorApp)
        with contextlib.suppress(Exception):
            await app._refresh_data()

        self.assertEqual(
            order[:2], ["publish", "capture"],
            "the parked set reached the monitor AFTER the capture — every "
            "already-parked agent is captured once on every launch",
        )
        self.assertIn(
            ("demo", "agent-parked"), published[0],
            "the very first publish must already carry the parked agent; it is "
            "derived from the mark store, not from snapshots that do not exist "
            "yet",
        )

    async def test_the_minimonitor_publishes_before_it_captures(self):
        from monitor.minimonitor_app import MiniMonitorApp

        app, order, published, root = await self._run_one_refresh(MiniMonitorApp)
        app._gate_cache = _FakeGateCache()

        async def own_info():
            app._own_window_name = "agent-followed"
            return True

        app._update_own_window_info = own_info
        with contextlib.suppress(Exception):
            await app._refresh_data()

        self.assertEqual(order[:2], ["publish", "capture"])
        self.assertIn(("demo", "agent-parked"), published[0])


class _FakeCache:
    def update_session_mapping(self, mapping): pass
    def get_task_id_for_pane(self, pane): return None
    def get_task_info(self, task_id, session=None): return None


class _FakeGateCache:
    def clear(self): pass


if __name__ == "__main__":
    unittest.main()
