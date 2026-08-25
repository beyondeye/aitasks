"""The first refresh must not run on the App's message pump (t1598).

`ait minimonitor` spawned beside a freshly launched agent was **dead to input for
~10 seconds** after boot: the list rendered, a card was highlighted, and clicks
and keypresses did nothing. It never recurred on later ticks.

Three things composed, and only the first was the trigger:

1. `AgentMarksMixin._init_agent_marks` seeded `_marks_purge_due_at = 0.0`, so the
   first refresh tick materialized a marks purge;
2. that purge shells out to `aitask_agent_marks.sh`, which can burn a full lock
   timeout on a wedged mutex;
3. **the structural amplifier** — `_start_monitoring` dispatched the first tick
   with `self.call_later(self._refresh_data)`. In Textual 8.2.7 `call_later`
   posts an `events.Callback` to the App's OWN queue and `MessagePump.on_callback`
   awaits it INLINE in the App's message loop — the same serialized queue
   `App.on_event` dispatches key and mouse events from. Ticks 2+ come from
   `set_interval`, which passes its callback unwrapped so `Timer._tick` runs it
   in the timer's own task; that asymmetry is exactly why the bug was
   startup-only.

**Why this suite stalls on an `asyncio.Event` rather than a real subprocess.**
The event loop stays completely free for the whole stall, so the only thing that
decides whether a keypress is dispatched is whether the first refresh occupies
the App pump. That isolates the structural property — and it is why a plain
event-loop lag probe cannot find this bug at all: measured during a real boot, a
loop-lag probe saw zero stalls above 150 ms, because the App pump is serialized
independently of loop responsiveness. **Assert on input dispatch, never on loop
lag.**

The budget is a hard `asyncio.wait_for`, not a millisecond comparison: on the
fixed code the key is handled in single-digit ms, and on the broken code the gate
can only be released by this test, so the failure is a deterministic `TimeoutError`
rather than something a loaded CI can lose.

Positive controls (run by hand; each must FAIL this suite):

| mutation | must fail |
|---|---|
| `_start_monitoring` back to `self.call_later(self._refresh_data)` | `test_a_keypress_is_dispatched_while_the_first_refresh_is_stalled` |
| `self.set_timer(0, self._refresh_data)` instead of `run_worker` | the same test — `set_timer` wraps the callback in `call_next`, which drains inline and JUMPS the queue, so it is strictly worse than `call_later` |
| `_refresh_inflight` reset moved out of its `finally` | `test_a_failed_refresh_does_not_wedge_every_later_refresh` |
| drop the `_backend_gen` guard in `start_control_client` | `test_a_teardown_during_a_blocked_start_installs_nothing` |
| re-seed `_marks_purge_due_at = 0.0` | `test_the_first_purge_is_deferred_past_startup` |

Run: python3 tests/test_minimonitor_startup_input_latency.py
or:  bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from monitor.minimonitor_app import MiniMonitorApp  # noqa: E402
from monitor.monitor_app import MonitorApp  # noqa: E402
from monitor.monitor_core import TmuxMonitor  # noqa: E402
from monitor.monitor_shared import (  # noqa: E402
    _MARKS_CMD_TIMEOUT,
    _MARKS_PURGE_INTERVAL,
    _MARKS_PURGE_STARTUP_GRACE,
)
from monitor.tmux_control import TmuxControlState  # noqa: E402

SESSION = "demo"

#: Hard ceiling for the whole press→handled region. The acceptance criterion is
#: "well under 1s"; the fixed code lands in single-digit ms.
INPUT_BUDGET_S = 1.0


class _StalledMonitor:
    """Tick surface whose capture blocks until the test releases it.

    Only `capture_all_async` stalls — everything else answers immediately — so
    the first `_refresh_data` is suspended inside its very first await, which is
    where the real purge stall sat relative to input dispatch.
    """

    multi_session = False

    def __init__(self) -> None:
        self.gate = asyncio.Event()
        self.entered = asyncio.Event()

    async def capture_all_async(self):
        self.entered.set()
        await self.gate.wait()
        return {}

    async def get_session_to_project_mapping_async(self): return {}
    async def tmux_run_async(self, args, timeout=5.0): return (1, "")
    async def discover_window_panes_async(self, window_id): return (False, [])
    def get_compare_mode(self, pane_id): return "stripped"
    def is_compare_mode_overridden(self, pane_id): return False
    def get_shadow_snapshot(self, pane_id): return None
    def get_shadow_snapshots(self): return {}
    def control_state(self): return TmuxControlState.CONNECTED


class FirstRefreshDispatchTests(unittest.TestCase):
    """The load-bearing suite: input must survive a stalled first refresh."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _app(self) -> MiniMonitorApp:
        return MiniMonitorApp(
            session=SESSION, project_root=Path(self._tmp.name),
            refresh_seconds=999,
        )

    def test_a_keypress_is_dispatched_while_the_first_refresh_is_stalled(self):
        async def scenario():
            app = self._app()
            mon = _StalledMonitor()
            async with app.run_test(size=(60, 24)) as pilot:
                app._monitor = mon
                handled: list[str] = []

                # Instrument the App's own key dispatch. This is what the defect
                # starved — not the loop, not painting.
                original = app.on_event

                async def spy(event):
                    if event.__class__.__name__ == "Key":
                        handled.append(getattr(event, "key", "?"))
                    return await original(event)

                app.on_event = spy

                # Drive the PRODUCTION dispatch path — `_start_monitoring` —
                # not a hand-rolled `run_worker`. Dispatching the worker here
                # ourselves would make this test pass even with the defect
                # restored, because the mutation lives in `_start_monitoring`.
                # Verified: with `_start_monitoring` reverted to `call_later`,
                # this test must fail by TimeoutError.
                import monitor.minimonitor_app as mm
                real_ctor, mm.TmuxMonitor = mm.TmuxMonitor, lambda **kw: mon
                try:
                    app._start_monitoring()
                finally:
                    mm.TmuxMonitor = real_ctor
                app._refresh_timer.stop()     # no second tick mid-assertion
                await asyncio.wait_for(mon.entered.wait(), timeout=5)

                # try/finally around every assertion: on failure the gate must
                # STILL be released, or `run_test`'s teardown waits forever on
                # the blocked pump and the suite hangs instead of failing.
                # Measured: without this, the `call_later` positive control hung
                # rather than reporting — a hanging regression test is worse
                # than no regression test.
                try:
                    t0 = time.perf_counter()
                    # NEVER pilot.pause() in a timed region: Textual 8.2.7's
                    # wait_for_idle(0) always sleeps at least one SLEEP_GRANULARITY
                    # (1/50 s), a synthetic floor that would dominate the reading.
                    await asyncio.wait_for(pilot.press("j"), timeout=INPUT_BUDGET_S)
                    latency = time.perf_counter() - t0

                    # `>= 1`, not `== 1`: a Key reaches `App.on_event` both on
                    # dispatch and again as it bubbles back up from the focused
                    # widget. The count is not the contract — reaching the App at
                    # all, while the first refresh is suspended, is.
                    self.assertIn(
                        "j", handled,
                        "the keypress never reached App.on_event while the first "
                        "refresh was in flight — it is back on the message pump",
                    )
                    self.assertLess(
                        latency, INPUT_BUDGET_S / 2,
                        f"key took {latency*1000:.1f}ms with the loop otherwise "
                        f"idle; 'well under 1s' means nowhere near the budget",
                    )

                finally:
                    mon.gate.set()

                # Prove the refresh really did run, so the test cannot pass by
                # never refreshing at all.
                await pilot.pause()
                self.assertFalse(
                    app._refresh_inflight,
                    "the refresh never completed after the gate was released",
                )

        asyncio.run(scenario())

    def test_the_first_refresh_is_requested_as_a_worker(self):
        """Structural pin on the dispatch mechanism itself.

        `call_later` / `set_timer` would satisfy "a refresh happened" while
        reintroducing the defect, so assert on HOW it was requested.
        """
        async def scenario():
            app = self._app()
            started: list[str] = []
            async with app.run_test(size=(60, 24)):
                original = app.run_worker

                def record(work, *a, **kw):
                    started.append(kw.get("name") or getattr(work, "__name__", "?"))
                    return original(work, *a, **kw)

                app.run_worker = record
                app._monitor = None          # keep the refresh itself a no-op
                app._start_monitoring()
                app._refresh_timer.stop()

            self.assertIn(
                "first_refresh", started,
                "the first refresh was not dispatched via run_worker — "
                "call_later and set_timer both run it on the App message pump",
            )

        asyncio.run(scenario())


class RefreshGuardTests(unittest.TestCase):
    """`_refresh_inflight` must never survive a failed or cancelled refresh."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_a_failed_refresh_does_not_wedge_every_later_refresh(self):
        async def scenario():
            app = MiniMonitorApp(
                session=SESSION, project_root=Path(self._tmp.name),
                refresh_seconds=999,
            )
            async with app.run_test(size=(60, 24)):
                calls = {"n": 0}

                class _Boom:
                    multi_session = False

                    async def capture_all_async(_self):
                        calls["n"] += 1
                        if calls["n"] == 1:
                            raise RuntimeError("tmux exploded")
                        return None      # second call: clean early return

                app._monitor = _Boom()

                with self.assertRaises(RuntimeError):
                    await app._refresh_data()
                self.assertFalse(
                    app._refresh_inflight,
                    "a raising refresh left the guard set — every later timer "
                    "and keypress refresh becomes a permanent no-op",
                )

                await app._refresh_data()
                self.assertEqual(
                    calls["n"], 2,
                    "the refresh after a failure never ran: the guard wedged",
                )

        asyncio.run(scenario())

    def test_a_cancelled_refresh_does_not_wedge_every_later_refresh(self):
        async def scenario():
            app = MiniMonitorApp(
                session=SESSION, project_root=Path(self._tmp.name),
                refresh_seconds=999,
            )
            async with app.run_test(size=(60, 24)):
                mon = _StalledMonitor()
                app._monitor = mon

                task = asyncio.create_task(app._refresh_data())
                await asyncio.wait_for(mon.entered.wait(), timeout=5)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task

                self.assertFalse(
                    app._refresh_inflight,
                    "CancelledError propagated past the guard's reset",
                )

        asyncio.run(scenario())


class PurgeSchedulingSeedTests(unittest.TestCase):
    """The `0.0` seed itself had no pin — the existing suites set it by hand."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_the_first_purge_is_deferred_past_startup(self):
        for cls in (MiniMonitorApp, MonitorApp):
            with self.subTest(app=cls.__name__):
                t0 = time.monotonic()
                app = cls(session=SESSION, project_root=Path(self._tmp.name))
                self.assertGreaterEqual(
                    app._marks_purge_due_at,
                    t0 + _MARKS_PURGE_STARTUP_GRACE - 1.0,
                    "the first refresh tick would materialize a purge — that is "
                    "a subprocess on the mount tick",
                )

    def test_the_purge_is_deferred_not_deleted(self):
        """Executable form of the acceptance criterion."""
        self.assertEqual(
            _MARKS_PURGE_INTERVAL, 600.0,
            "the recurrence interval must be unchanged",
        )
        self.assertLess(
            _MARKS_PURGE_STARTUP_GRACE, _MARKS_PURGE_INTERVAL,
            "a grace at or above the interval would delete the purge, not "
            "defer it",
        )
        self.assertGreater(
            _MARKS_PURGE_STARTUP_GRACE, _MARKS_CMD_TIMEOUT,
            "a maximally-stalled first attempt must fit inside the grace "
            "window rather than straddling it",
        )


class ControlClientLifecycleTests(unittest.TestCase):
    """`asyncio.to_thread` created an interleaving point that did not exist."""

    def test_a_teardown_during_a_blocked_start_installs_nothing(self):
        async def scenario():
            mon = TmuxMonitor(session=SESSION, multi_session=False)
            release = threading.Event()
            stopped: list[str] = []

            class _Backend:
                def __init__(self, session=None): pass
                def start(_self):
                    release.wait(timeout=5)
                    return True
                def stop(_self):
                    stopped.append("stop")

            import monitor.monitor_core as core
            original, core.TmuxControlBackend = core.TmuxControlBackend, _Backend
            try:
                task = asyncio.create_task(mon.start_control_client())
                await asyncio.sleep(0)          # let it reach the to_thread hop
                await mon.close_control_client()
                release.set()
                started = await task
            finally:
                core.TmuxControlBackend = original

            self.assertFalse(
                started,
                "start_control_client reported success after the app was torn "
                "down — it installed a live backend on a closed app",
            )
            self.assertFalse(
                mon.has_control_client(),
                "a backend was installed despite the teardown",
            )
            self.assertIn(
                "stop", stopped,
                "the backend started during teardown was never stopped — its "
                "`tmux -C attach` and thread leak",
            )

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main(verbosity=2)
