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

SECOND CAPTURE ROUTE (t1769): `FastPreviewRouteTests` and
`FastPreviewAppRouteTests` pin the same no-capture rule on
`capture_pane_classified_async` + `commit_snapshot`, the single-pane route
`_fast_preview_refresh` uses and then writes into `_snapshots` unconditionally.
Without the guard, focusing a parked card replaced its `parked=True` snapshot.
The two `FastPreviewAppRouteTests` race tests pin why no commit-time re-check
is needed: a fast capture that was already in flight when the agent was parked
is either rejected by the generation guard, because the full refresh that
delivers the park reserved a newer generation, or commits first and is then
overwritten by that refresh.

NEGATIVE CONTROL for the characterization: make `commit_snapshots` emit a
snapshot for a `result is None` entry -> `test_a_failed_capture_produces_no_
snapshot` fails. Make it drop the pane id from the `_clean_stale` set ->
`test_a_failed_capture_still_counts_as_present_for_clean_stale` fails.
"""
from __future__ import annotations

import asyncio
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
        app._hide_inactive = False
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


class FastPreviewRouteTests(unittest.IsolatedAsyncioTestCase):
    """The SECOND capture route must honour the no-capture rule (t1769).

    `capture_pane_classified_async` + `commit_snapshot` is what
    `monitor_app._fast_preview_refresh` uses, and it had no parked branch — the
    bulk route's exclusion never applied to the focused pane.
    """

    def _monitor(self, p, parked=()):
        mon = _monitor()
        self.captured: list[str] = []

        async def fake_capture(pane_id, capture_lines=None, pane=None):
            self.captured.append(pane_id)
            return (p, "content")

        async def run_offloaded(fn):
            return fn()

        mon._pane_cache[p.pane_id] = p
        mon.capture_pane_content_async = fake_capture
        mon._run_offloaded = run_offloaded
        mon.set_parked_agents(set(parked))
        return mon

    async def test_a_parked_pane_is_not_captured_on_the_fast_route(self):
        p = pane("demo", "agent-parked", "%2")
        mon = self._monitor(p, parked={("demo", "agent-parked")})

        gen, got, content, result = await mon.capture_pane_classified_async("%2")

        self.assertEqual(self.captured, [],
                         "the parked pane reached capture_pane_content_async")
        self.assertIs(got, p)
        self.assertEqual(content, "")
        self.assertTrue(result.parked)
        self.assertFalse(result.frozen)

    async def test_the_control_shows_a_live_pane_is_still_captured(self):
        """NEGATIVE CONTROL: an unparked pane, and one whose window is not the
        parked pair, are captured exactly as before."""
        p = pane("demo", "agent-live", "%1")
        mon = self._monitor(p)
        await mon.capture_pane_classified_async("%1")
        self.assertEqual(self.captured, ["%1"])

        other = pane("demo", "agent-live", "%3")
        mon = self._monitor(other, parked={("demo", "agent-other")})
        _, _, _, result = await mon.capture_pane_classified_async("%3")
        self.assertEqual(self.captured, ["%3"])
        self.assertFalse(result.parked)

    async def test_the_single_pane_commit_returns_a_parked_snapshot(self):
        p = pane("demo", "agent-parked", "%2")
        mon = self._monitor(p, parked={("demo", "agent-parked")})

        gen, got, content, result = await mon.capture_pane_classified_async("%2")
        snap = mon.commit_snapshot(gen, got, content, result)

        self.assertTrue(snap.parked)
        self.assertFalse(snap.frozen)
        self.assertEqual(snap.content, "")

    async def test_the_single_pane_commit_bypasses_the_idle_clock(self):
        p = pane("demo", "agent-parked", "%2")
        mon = self._monitor(p, parked={("demo", "agent-parked")})

        gen, got, content, result = await mon.capture_pane_classified_async("%2")
        mon.commit_snapshot(gen, got, content, result)

        self.assertNotIn("%2", mon._last_content)

    async def test_a_superseded_generation_still_commits_nothing(self):
        """The parked branch lands after the generation guard, not before it."""
        p = pane("demo", "agent-parked", "%2")
        mon = self._monitor(p, parked={("demo", "agent-parked")})

        gen, got, content, result = await mon.capture_pane_classified_async("%2")
        mon._next_generation()          # a newer capture reserves
        self.assertIsNone(mon.commit_snapshot(gen, got, content, result))


class FastPreviewAppRouteTests(unittest.IsolatedAsyncioTestCase):
    """The same route, driven through the mounted APP that uses it (t1769).

    The defect is visible as a reverting preview, not as a core call, so the
    core tests above are not sufficient on their own: `_fast_preview_refresh`
    writes `self._snapshots[pane_id] = snap` unconditionally and repaints.
    """

    LIVE = "LIVE CONTENT FROM THE CAPTURE"

    async def _app(self, p, barrier: bool = False):
        from monitor.monitor_app import MonitorApp

        mon = _monitor()
        self.captured: list[str] = []
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

        async def fake_capture(pane_id, capture_lines=None, pane=None):
            self.captured.append(pane_id)
            if barrier:
                self.entered.set()
                await self.release.wait()
            return (p, self.LIVE)

        async def fake_discover(enum_sink=None):
            if enum_sink is not None:
                enum_sink.append(frozenset({"demo"}))
            return [p], []

        async def run_offloaded(fn):
            return fn()

        mon._pane_cache[p.pane_id] = p
        mon.capture_pane_content_async = fake_capture
        mon.discover_panes_with_shadows_async = fake_discover
        mon._run_offloaded = run_offloaded

        app = MonitorApp(session="demo", project_root=REPO_ROOT)
        return app, mon

    @staticmethod
    def _parked_snap(p):
        return monitor_core.PaneSnapshot(
            pane=p, content="", timestamp=0.0, idle_seconds=0.0,
            is_idle=False, awaiting_input=False, parked=True)

    @staticmethod
    async def _full_refresh_commit(app, mon):
        """The full refresh's capture-and-commit half, as `_refresh_data` runs
        it: what delivers a park to a fast capture that was already in flight
        (a capture started after the park commits parked on its own)."""
        gen, classified = await mon.capture_all_classified_async()
        if mon.capture_generation != gen:
            return
        snaps = mon.commit_snapshots(gen, classified)
        if snaps is not None:
            app._snapshots = snaps

    async def test_focusing_a_parked_pane_does_not_overwrite_its_snapshot(self):
        """THE defect, at the layer it is visible."""
        p = pane("demo", "agent-parked", "%2")
        app, mon = await self._app(p)
        async with app.run_test(size=(120, 40)):
            app._monitor = mon
            mon.set_parked_agents({("demo", "agent-parked")})
            app._focused_pane_id = "%2"
            app._snapshots["%2"] = self._parked_snap(p)

            await app._fast_preview_refresh()

            self.assertEqual(self.captured, [], "the app captured a parked pane")
            snap = app._snapshots["%2"]
            self.assertTrue(snap.parked, "the parked flag was overwritten")
            self.assertEqual(snap.content, "")

    async def test_the_preview_shows_the_parked_placeholder_not_stale_output(
            self):
        p = pane("demo", "agent-parked", "%2")
        app, mon = await self._app(p)
        async with app.run_test(size=(120, 40)) as pilot:
            app._monitor = mon
            mon.set_parked_agents({("demo", "agent-parked")})
            app._focused_pane_id = "%2"
            app._snapshots["%2"] = self._parked_snap(p)

            await app._fast_preview_refresh()
            await pilot.pause()

            rendered = app.query_one("#content-preview").render()
            plain = getattr(rendered, "plain", str(rendered))
            self.assertIn("parked", plain)
            self.assertNotIn(self.LIVE, plain)

    async def test_the_control_shows_a_live_focused_pane_is_still_captured(
            self):
        """NEGATIVE CONTROL: without it the assertions above would pass for an
        app whose fast preview had simply stopped working."""
        p = pane("demo", "agent-live", "%1")
        app, mon = await self._app(p)
        async with app.run_test(size=(120, 40)):
            app._monitor = mon
            app._focused_pane_id = "%1"

            await app._fast_preview_refresh()

            self.assertEqual(self.captured, ["%1"])
            self.assertFalse(app._snapshots["%1"].parked)
            self.assertEqual(app._snapshots["%1"].content, self.LIVE)

    async def test_a_park_during_an_in_flight_fast_refresh_stays_parked(self):
        """Barrier-controlled race: the fast capture checks "not parked", the
        agent is parked and a full refresh commits while the capture is still
        in flight, then the capture returns. The generation guard must reject
        it — the parked check is deliberately not repeated at commit time."""
        p = pane("demo", "agent-racy", "%2")
        app, mon = await self._app(p, barrier=True)
        async with app.run_test(size=(120, 40)):
            app._monitor = mon
            app._focused_pane_id = "%2"

            task = asyncio.create_task(app._fast_preview_refresh())
            await asyncio.wait_for(self.entered.wait(), timeout=5)

            mon.set_parked_agents({("demo", "agent-racy")})
            await self._full_refresh_commit(app, mon)
            self.assertTrue(app._snapshots["%2"].parked)

            self.release.set()
            await asyncio.wait_for(task, timeout=5)

            self.assertEqual(self.captured, ["%2"],
                             "the full refresh captured the parked pane")
            snap = app._snapshots["%2"]
            self.assertTrue(snap.parked,
                            "the in-flight fast capture overwrote the parked "
                            "snapshot")
            self.assertEqual(snap.content, "")

    async def test_a_park_after_the_fast_commit_ends_parked_too(self):
        """The other interleaving: the fast capture commits before the full
        refresh. It only overwrote an ordinary snapshot, and the refresh then
        writes the parked one."""
        p = pane("demo", "agent-racy", "%2")
        app, mon = await self._app(p, barrier=True)
        async with app.run_test(size=(120, 40)):
            app._monitor = mon
            app._focused_pane_id = "%2"

            task = asyncio.create_task(app._fast_preview_refresh())
            await asyncio.wait_for(self.entered.wait(), timeout=5)
            mon.set_parked_agents({("demo", "agent-racy")})
            self.release.set()
            await asyncio.wait_for(task, timeout=5)
            self.assertFalse(app._snapshots["%2"].parked)
            self.assertEqual(app._snapshots["%2"].content, self.LIVE)

            await self._full_refresh_commit(app, mon)

            self.assertTrue(app._snapshots["%2"].parked)
            self.assertEqual(app._snapshots["%2"].content, "")


class _FakeCache:
    def update_session_mapping(self, mapping): pass
    def get_task_id_for_pane(self, pane): return None
    def get_task_info(self, task_id, session=None): return None


class _FakeGateCache:
    def clear(self): pass


if __name__ == "__main__":
    unittest.main()
