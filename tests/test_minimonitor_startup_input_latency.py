"""The first refresh must not run on the App's message pump (t1598).

`ait minimonitor` spawned beside a freshly launched agent was **dead to input for
~10 seconds** after boot: the list rendered, a card was highlighted, and clicks
and keypresses did nothing. It never recurred on later ticks.

**t1622 extends this file one step earlier, to `on_mount` itself.** The same
suite owns it because it is the same property by a different route: the mount
path's own `subprocess.run(["tmux", ...], timeout=5)` held the App before the
first refresh was even dispatched, so a wedged tmux server bought a five-second
dead TUI without the message pump being involved at all. It is now a
`run_worker`-dispatched `_seed_own_window_info`. Deferring it also makes
"own window not detected yet" an ordinary sub-second state, which
`OwnWindowNotYetSeededTests` pins. Nothing here spawns a real `tmux` — the
probe's gateway client is patched out wholesale.

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

**Dispatch is asserted as a COUNT OF EVENT-LOOP TURNS, never as wall-clock time**
(t1660). The wall-clock form did not survive: `assertLess(latency, 500ms)` around
`pilot.press("j")` failed in the `-n 4 --dist loadfile` lane at 822 ms and 595 ms
while passing standalone. It was never measuring input latency. Two harness terms
dominated it, and neither is dispatch:

* `Pilot.press` -> `App._press_keys` awaits `wait_for_idle(0)` **twice per key**
  (textual 8.2.7), plus `animator.wait_until_complete()` twice. `wait_for_idle`
  compares `process_time()` against wall clock in 20 ms sleep granules — a >=20 ms
  floor per call and a `max_sleep=1` cap, so >=40 ms and up to **2 s** per key,
  decided by the scheduler rather than by this code. Measured on an **idle** box:
  208 ms of a 215 ms `press`.
* `j` is not inert. It is bound to `action_tui_switcher`, which pushes a
  **65-widget** `TuiSwitcherOverlay`; `Pilot._wait_for_screen()` then posts a
  `call_later` to every one of them and waits. The timed region therefore included
  mounting the screen the keypress opens.

The property itself — `driver.send_message` reaching `App.on_event` — cost
**0.23 ms**. So the budget was ~43 % consumed by the harness with zero contention,
and any lane load tipped it over. A turn count cannot be tipped over: contention
changes how long a turn takes, never how many are needed (measured identical, 3-4,
idle and under 24-way CPU load). On the broken code the key never arrives at all,
so the failure is turn exhaustion — deterministic, and in sub-millisecond time
rather than after a 1 s timeout.

Positive controls (run by hand; each must FAIL this suite):

| mutation | must fail |
|---|---|
| `_start_monitoring` back to `self.call_later(self._refresh_data)` | `test_a_keypress_is_dispatched_while_the_first_refresh_is_stalled`, by TURN EXHAUSTION |
| `self.set_timer(0, self._refresh_data)` instead of `run_worker` | the same test, but at the `mon.entered.wait()` timeout — `set_timer` wraps the callback in `call_next`, which drains inline and JUMPS the queue, and under it the first refresh does not run at all within the 5 s window, so the test dies before the dispatch observation. Verified unchanged by t1660: it failed the same way against the pre-t1660 test file |
| `_refresh_inflight` reset moved out of its `finally` | `test_a_failed_refresh_does_not_wedge_every_later_refresh` |
| drop the `_backend_gen` guard in `start_control_client` | `test_a_teardown_during_a_blocked_start_installs_nothing` |
| re-seed `_marks_purge_due_at = 0.0` | `test_the_first_purge_is_deferred_past_startup` |
| `on_mount`'s window probe back to `subprocess.run` | `test_mount_returns_while_the_window_probe_is_still_blocked` (the fake is never consulted, so `entered` times out — NOT turn exhaustion; the dispatch observation is never reached) **and** `test_on_mount_issues_no_synchronous_subprocess`, by name |
| `on_mount`'s `run_worker(…, name="own_window_seed", …)` -> `self.call_later(lambda: self._seed_own_window_info())` | `test_mount_returns_while_the_window_probe_is_still_blocked`, by TURN EXHAUSTION — see below |
| a bare `TmuxClient()` in `_seed_own_window_info` | `test_the_seed_queries_the_ambient_server_for_its_own_pane` |
| drop the `is None` guards from `_seed_own_window_info` | `test_the_seed_never_overwrites_a_field_the_tick_already_set` |
| re-merge the two `_find_sibling_pane_id` refusals | `test_the_sibling_refusal_names_the_real_reason` |

**The two `on_mount` rows are not interchangeable, and neither is redundant.** The
`subprocess.run` mutation never lets the stalled fake be consulted, so `entered` is
never set and the test dies at `asyncio.wait_for(entered.wait(), timeout=5)` —
*before* the dispatch observation is ever reached. It therefore cannot exercise the
turn-count instrument at all. The `call_later` mutation is the one that can: it posts
an `events.Callback` to the **App's own queue**, which `MessagePump.on_callback`
awaits INLINE in the App's message loop, so the probe runs, sets `entered`, and then
holds the pump while it awaits the gate. `entered.wait()` succeeds from the test's
own task and the key is never dispatched. (The `lambda` is required: `call_later`
takes a **callable**, not a coroutine — passing the coroutine directly raises
`TypeError: the first argument must be callable`, which would be a control that
fails for the wrong reason.) Reproduced while planning t1660: the fixed code
dispatched at turn 3-4 in every trial; this mutation hit the 200-turn cap with
`handled == []` in every trial.

Run: python3 tests/test_minimonitor_startup_input_latency.py
or:  bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import ast
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

import monitor.minimonitor_app as mm  # noqa: E402
from monitor.minimonitor_app import MiniMonitorApp  # noqa: E402
from monitor.monitor_app import MonitorApp  # noqa: E402
from monitor.monitor_core import TmuxMonitor  # noqa: E402
from monitor.monitor_shared import (  # noqa: E402
    _MARKS_CMD_TIMEOUT,
    _MARKS_PURGE_INTERVAL,
    _MARKS_PURGE_STARTUP_GRACE,
)
from monitor.tmux_control import TmuxControlState  # noqa: E402
from textual import events  # noqa: E402
from tmux_exec import (  # noqa: E402
    AIT_DEDICATED_SOCKET, TMUX_SOCKET_ENV, tmux_socket_args,
)

SESSION = "demo"

#: Hard ceiling for the SYNCHRONOUS `on_mount()` region. The acceptance criterion
#: is "well under 1s"; the fixed code lands in single-digit ms.
#:
#: This is the one wall-clock budget the suite keeps, and only because what it
#: wraps is a plain synchronous call — no event loop, no `Pilot`, no
#: `wait_for_idle`. Measured 0.18-0.26 ms idle and 0.47-8.8 ms under 24-way CPU
#: load: a >=57x margin at the worst loaded sample. The press-side budget that
#: used to share this constant is gone; see the module docstring (t1660).
INPUT_BUDGET_S = 1.0


#: Event-loop turns allowed for a key to reach `App.on_event`. A COUNT, not a
#: duration: contention changes how long a turn takes, never how many are needed.
#: Measured 3-4 turns identically on an idle box and under 24-way CPU load; with
#: the probe awaited inline on the App pump the key never arrives at all, so the
#: cap is exhausted instead. 200 is ~50x the observed cost.
_DISPATCH_TURNS = 200

#: Optional path; when set, each dispatch observation appends one TSV line
#: `<test name>\t<turns or "EXHAUSTED">\t<mount_elapsed_ms or "">`. Off by
#: default, so the suite is unchanged. The contention control in
#: `aiplans/archived/p1660_*.md` sets it, and compares a loaded run's turn counts
#: against an idle baseline captured the same way.
_DISPATCH_LOG_ENV = "AIT_MINIMON_DISPATCH_LOG"


def _log_dispatch(name: str, turn: int | None,
                  mount_ms: float | None = None) -> None:
    """Append one machine-readable observation, when the env var asks for it."""
    path = os.environ.get(_DISPATCH_LOG_ENV)
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"{name}\t{turn if turn is not None else 'EXHAUSTED'}\t"
                 f"{'' if mount_ms is None else f'{mount_ms:.2f}'}\n")


async def _press_and_observe(app, key: str, seen: list) -> int | None:
    """Send `key` as Textual's own Pilot does, and count TURNS to dispatch.

    Returns the 1-based event-loop turn on which `seen` became non-empty, or
    `None` if it never did within `_DISPATCH_TURNS`.

    Deliberately NOT `pilot.press()`. In textual 8.2.7 `Pilot.press` ->
    `App._press_keys` awaits `wait_for_idle(0)` TWICE per key (a >=20 ms floor
    each, capped at 1 s each) plus `animator.wait_until_complete()`, and then
    `Pilot._wait_for_screen()` posts a `call_later` to every widget on screen and
    waits for all of them — 65 of them once `j` pushes `TuiSwitcherOverlay`.
    Measured on an IDLE box, that harness cost was 208 ms of a 215 ms `press`,
    against what was then a 500 ms budget, while the property under test — send
    to `App.on_event` — cost 0.23 ms. Timing `press` measured the harness (t1660).

    `driver.send_message` is the same call `_press_keys` makes; only the idle
    sampling around it is dropped. `asyncio.sleep(0)` yields one loop iteration,
    so the loop count is the scheduler-invariant part of "how promptly was this
    dispatched".
    """
    event = events.Key(key, key if len(key) == 1 else None)
    event.set_sender(app)
    app._driver.send_message(event)
    for turn in range(1, _DISPATCH_TURNS + 1):
        if seen:
            return turn
        await asyncio.sleep(0)
    return None


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
                    turn = await _press_and_observe(app, "j", handled)
                    _log_dispatch(self.id().rsplit(".", 1)[-1], turn)

                    # `>= 1`, not `== 1`: a Key reaches `App.on_event` both on
                    # dispatch and again as it bubbles back up from the focused
                    # widget. The count is not the contract — reaching the App at
                    # all, while the first refresh is suspended, is.
                    # The turn assertion goes FIRST so a positive control reports
                    # turn exhaustion by name rather than the older, vaguer
                    # "never reached App.on_event" — both describe the same
                    # failure, but only this one names the instrument.
                    self.assertIsNotNone(
                        turn,
                        f"the keypress never reached App.on_event within "
                        f"{_DISPATCH_TURNS} event-loop turns while the first "
                        f"refresh was in flight — it is back on the message pump",
                    )
                    self.assertIn(
                        "j", handled,
                        "the keypress never reached App.on_event while the first "
                        "refresh was in flight — it is back on the message pump",
                    )

                finally:
                    mon.gate.set()
                    # Drain the queued key BEFORE this block can exit, on the
                    # FAILURE path too — hence inside the `finally` (t1660).
                    # `App.on_key` reads `self.screen`, so a Key still queued when
                    # `run_test` tears the screen down raises `ScreenStackError`
                    # from the pump, and `run_test`'s `raise self._exception`
                    # then MASKS the real assertion with a traceback nowhere near
                    # it. Measured: the `call_later` positive control reported
                    # exactly that instead of its own message.
                    await pilot.pause()

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

                    # Resolved BEFORE the capture since t1685 (the parked set is
                    # derived from it and must be published before the tick
                    # captures). Answered here so the RuntimeError below still
                    # comes from the capture, which is what this test is about.
                    async def get_session_to_project_mapping_async(_self):
                        return {}

                    def set_parked_agents(_self, pairs):
                        pass

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



# ---------------------------------------------------------------------------
# t1622 — the mount path's own blocking probe
# ---------------------------------------------------------------------------

#: A distinctive `TMUX_PANE` so the target assertion cannot be satisfied by a
#: hardcoded or stale value that happens to look pane-shaped.
PROBE_PANE = "%4242"
PROBE_REPLY = "@7\t3\tagent-demo"


class _RecordingTmuxClient:
    """Stand-in for the gateway client `_seed_own_window_info` constructs.

    Records the constructor kwargs **and resolves the argv the real client
    would build** (`["tmux", *socket_args, *args]`). Asserting on the argv
    rather than on the kwargs alone is what makes `socket_args=None` fail: it
    is not a wrong *value*, it is the absence of one, and it resolves silently
    to the dedicated `-L ait` socket — the wrong server for a self-probe.
    """

    instances: list["_RecordingTmuxClient"] = []
    reply = PROBE_REPLY
    rc = 0

    def __init__(self, socket_args=None):
        # Mirror TmuxClient.__init__ exactly, including its None branch.
        self.socket_args = (
            list(socket_args) if socket_args is not None else tmux_socket_args()
        )
        self.calls: list[tuple[list[str], float]] = []
        _RecordingTmuxClient.instances.append(self)

    def argv(self, args) -> list[str]:
        return ["tmux", *self.socket_args, *args]

    async def run_async(self, args, timeout=5.0):
        self.calls.append((list(args), timeout))
        return (self.rc, self.reply)

    @classmethod
    def install(cls, testcase, *, reply=PROBE_REPLY, rc=0):
        cls.instances = []
        cls.reply, cls.rc = reply, rc
        real, mm.TmuxClient = mm.TmuxClient, cls
        testcase.addCleanup(lambda: setattr(mm, "TmuxClient", real))
        return cls


class _StalledTmuxClient(_RecordingTmuxClient):
    """Answers only when the test releases it — the wedged-tmux stand-in."""

    gate: asyncio.Event
    entered: asyncio.Event

    async def run_async(self, args, timeout=5.0):
        self.calls.append((list(args), timeout))
        type(self).entered.set()
        await type(self).gate.wait()
        return (self.rc, self.reply)


def _in_tmux(testcase, pane: str = PROBE_PANE) -> None:
    """Restore `TMUX` / `TMUX_PANE` for one test — the module pops them at import."""
    saved = {k: os.environ.get(k) for k in ("TMUX", "TMUX_PANE")}

    def restore():
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    testcase.addCleanup(restore)
    os.environ["TMUX"] = "/tmp/tmux-1000/default,1,0"
    os.environ["TMUX_PANE"] = pane


class MountWindowProbeTests(unittest.TestCase):
    """`on_mount` must dispatch the own-window probe, never await it."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _app(self) -> MiniMonitorApp:
        return MiniMonitorApp(
            session=SESSION, project_root=Path(self._tmp.name),
            refresh_seconds=999,
        )

    def test_the_mount_window_probe_is_dispatched_as_a_worker(self):
        """Structural pin on the dispatch mechanism, as for the first refresh.

        `await`ing the coroutine inline would satisfy "the fields got set" while
        reinstating the stall, so assert on HOW it was requested.
        """
        async def scenario():
            _RecordingTmuxClient.install(self)
            app = self._app()
            started: list[str] = []
            # NOT before `run_test`: its own mount would then take the in-tmux
            # path with the real `TmuxMonitor` still installed, building a live
            # control client. Set it only for the explicit `on_mount()` below,
            # which runs under the stub.
            async with app.run_test(size=(60, 24)):
                original = app.run_worker

                def record(work, *a, **kw):
                    started.append(kw.get("name") or getattr(work, "__name__", "?"))
                    return original(work, *a, **kw)

                app.run_worker = record
                _in_tmux(self)
                real_ctor, mm.TmuxMonitor = mm.TmuxMonitor, lambda **kw: _StalledMonitor()
                try:
                    app.on_mount()
                finally:
                    mm.TmuxMonitor = real_ctor
                if app._refresh_timer is not None:
                    app._refresh_timer.stop()

            self.assertIn(
                "own_window_seed", started,
                "the own-window probe was not dispatched via run_worker — an "
                "inline await puts it back on the mount path",
            )

        asyncio.run(scenario())

    def test_mount_returns_while_the_window_probe_is_still_blocked(self):
        """The behavioral contract: a wedged tmux must not hold the mount.

        Reverting to `subprocess.run` fails here by TimeoutError — the fake is
        never consulted, so `entered` is never set.
        """
        async def scenario():
            _StalledTmuxClient.install(self)
            _StalledTmuxClient.gate = asyncio.Event()
            _StalledTmuxClient.entered = asyncio.Event()
            app = self._app()

            async with app.run_test(size=(60, 24)) as pilot:
                handled: list[str] = []
                original = app.on_event

                async def spy(event):
                    if event.__class__.__name__ == "Key":
                        handled.append(getattr(event, "key", "?"))
                    return await original(event)

                app.on_event = spy

                quiet = _StalledMonitor()
                quiet.gate.set()          # the monitor is not what stalls here
                # Set the tmux env only now — see the note in the worker-dispatch
                # test above.
                _in_tmux(self)
                real_ctor, mm.TmuxMonitor = mm.TmuxMonitor, lambda **kw: quiet
                try:
                    t0 = time.perf_counter()
                    app.on_mount()
                    mount_elapsed = time.perf_counter() - t0
                finally:
                    mm.TmuxMonitor = real_ctor
                if app._refresh_timer is not None:
                    app._refresh_timer.stop()

                await asyncio.wait_for(_StalledTmuxClient.entered.wait(), timeout=5)

                # try/finally around every assertion: on failure the gate must
                # STILL be released, or `run_test`'s teardown waits forever on
                # the blocked worker and the suite hangs instead of failing.
                try:
                    # The one surviving wall-clock budget in this suite, and only
                    # because `app.on_mount()` above is a plain SYNCHRONOUS call —
                    # no event loop, no `Pilot`, no `wait_for_idle`. Measured
                    # 0.18-0.26 ms idle and 0.47-8.8 ms under 24-way CPU load, so
                    # the margin here is >=57x at the worst loaded sample. The
                    # press-side budget had no such margin and is gone (t1660).
                    self.assertLess(
                        mount_elapsed, INPUT_BUDGET_S / 2,
                        f"on_mount took {mount_elapsed*1000:.1f}ms with the "
                        f"probe still blocked — it awaited it",
                    )
                    turn = await _press_and_observe(app, "j", handled)
                    _log_dispatch(self.id().rsplit(".", 1)[-1], turn,
                                  mount_elapsed * 1000)
                    # Turn assertion first — see the sibling test for why.
                    self.assertIsNotNone(
                        turn,
                        f"the keypress never reached App.on_event within "
                        f"{_DISPATCH_TURNS} event-loop turns while the mount "
                        f"probe was in flight — it is back on the message pump",
                    )
                    self.assertIn(
                        "j", handled,
                        "the keypress never reached App.on_event while the "
                        "mount probe was in flight",
                    )
                finally:
                    _StalledTmuxClient.gate.set()
                    # Untimed settle, inside the `finally` so it runs on the
                    # FAILURE path too. Two things need it: `j` pushes the
                    # 65-widget `TuiSwitcherOverlay`, and the dispatch observation
                    # returns as soon as the Key reaches `App.on_event` — long
                    # before either finishes. A Key left queued at teardown reaches
                    # `App.on_key`, which reads `self.screen` and raises
                    # `ScreenStackError`, masking the real assertion (t1660).
                    await pilot.pause()

        asyncio.run(scenario())

    def test_the_seed_queries_the_ambient_server_for_its_own_pane(self):
        """The socket + target contract — silent when wrong, so pinned explicitly.

        A bare `TmuxClient()` resolves to `-L ait`; against a pane on any other
        server that returns rc != 0 and all three fields stay `None`, disabling
        auto-close and the `m` / `k` handoffs with no error anywhere.
        """
        _in_tmux(self)
        # Control the socket default, or this assertion is vacuous: under an
        # `AITASKS_TMUX_SOCKET` that already resolves to no flag (the test
        # isolation harness sets exactly that), `TmuxClient()` and
        # `TmuxClient(socket_args=[])` build identical argv and the mutation
        # this test exists to catch would slip through unnoticed.
        saved_sock = os.environ.pop(TMUX_SOCKET_ENV, None)
        self.addCleanup(
            lambda: os.environ.__setitem__(TMUX_SOCKET_ENV, saved_sock)
            if saved_sock is not None else None
        )
        self.assertNotEqual(
            tmux_socket_args(), [],
            "the production default no longer pins a socket — this test can no "
            "longer distinguish an ambient client from a defaulted one",
        )

        _RecordingTmuxClient.install(self)
        app = MiniMonitorApp(
            session=SESSION, project_root=Path(self._tmp.name), refresh_seconds=999,
        )
        asyncio.run(app._seed_own_window_info())

        self.assertEqual(
            len(_RecordingTmuxClient.instances), 1,
            "the seed did not go through the tmux gateway",
        )
        client = _RecordingTmuxClient.instances[0]
        self.assertEqual(len(client.calls), 1)
        args, timeout = client.calls[0]
        argv = client.argv(args)

        self.assertNotIn(
            "-L", argv,
            f"the seed pinned itself to a named socket ({argv!r}) — this probe "
            f"must follow ambient $TMUX resolution, because the pane it asks "
            f"about lives on whatever server we are attached to",
        )
        self.assertNotIn(AIT_DEDICATED_SOCKET, argv)
        self.assertEqual(
            args,
            ["display-message", "-p", "-t", PROBE_PANE,
             "#{window_id}\t#{window_index}\t#{window_name}"],
            "the probe did not target this pane, or changed its format string",
        )
        self.assertEqual(timeout, 2, "the seed should not outwait the tick that supersedes it")

    def test_the_seed_never_overwrites_a_field_the_tick_already_set(self):
        """Both directions: the tick owns current values, the seed fills blanks.

        The seed and the per-tick `_update_own_window_info` write the same three
        fields and can land in either order, so the `is None` guards are what
        make them order-independent.
        """
        _in_tmux(self)
        _RecordingTmuxClient.install(self)
        app = MiniMonitorApp(
            session=SESSION, project_root=Path(self._tmp.name), refresh_seconds=999,
        )
        app._own_window_id = "@99"          # as if a tick already answered
        asyncio.run(app._seed_own_window_info())

        self.assertEqual(
            app._own_window_id, "@99",
            "the seed clobbered a value the refresh tick had already written",
        )
        self.assertEqual(app._own_window_index, "3", "a blank field was not seeded")
        self.assertEqual(app._own_window_name, "agent-demo", "a blank field was not seeded")

    def test_a_failed_probe_leaves_every_field_alone(self):
        _in_tmux(self)
        _RecordingTmuxClient.install(self, reply="", rc=1)
        app = MiniMonitorApp(
            session=SESSION, project_root=Path(self._tmp.name), refresh_seconds=999,
        )
        asyncio.run(app._seed_own_window_info())
        self.assertIsNone(app._own_window_id)
        self.assertIsNone(app._own_window_index)
        self.assertIsNone(app._own_window_name)

    def test_on_mount_issues_no_synchronous_subprocess(self):
        """Scoped structural guard — `test_no_raw_tmux.sh` cannot provide it.

        That script allowlists this whole file (its `_detect_tmux_session`
        legitimately spawns raw tmux before the App exists), so a revert to
        `subprocess.run(["tmux", ...])` inside `on_mount` passes it untouched.
        Parsed with `ast`, not grepped: a grep for `subprocess.run` matches the
        comment that explains why it is gone.
        """
        source = Path(mm.__file__).read_text()
        tree = ast.parse(source)
        on_mount = None
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == "MiniMonitorApp":
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "on_mount":
                        on_mount = item
        self.assertIsNotNone(
            on_mount, "MiniMonitorApp.on_mount not found — this guard is inert"
        )

        offenders = []
        for node in ast.walk(on_mount):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if (
                isinstance(fn, ast.Attribute)
                and isinstance(fn.value, ast.Name)
                and fn.value.id == "subprocess"
            ):
                offenders.append(f"subprocess.{fn.attr} (line {node.lineno})")
        self.assertEqual(
            offenders, [],
            f"on_mount spawns a synchronous subprocess: {offenders} — that is "
            f"the mount stall t1622 removed; dispatch it as a worker instead",
        )


class OwnWindowNotYetSeededTests(unittest.TestCase):
    """The window the seed makes reachable: all three fields still `None`.

    Deferring the probe turns "own window not detected" from a near-impossible
    state into an ordinary sub-second one, so the three keypress consumers must
    refuse *visibly* — never crash, and never resolve some other pane. A wrong
    sibling here is exactly the shadow-pane hazard t1382 documents.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    class _RecordingMonitor(_StalledMonitor):
        def __init__(self) -> None:
            super().__init__()
            self.gate.set()
            self.sync_calls: list[tuple[str, ...]] = []

        def tmux_run(self, args, timeout=5.0):
            self.sync_calls.append(tuple(args))
            return (0, "%1\n%2\n")

    async def _app(self, pilot_body):
        app = MiniMonitorApp(
            session=SESSION, project_root=Path(self._tmp.name), refresh_seconds=999,
        )
        async with app.run_test(size=(60, 24)):
            mon = self._RecordingMonitor()
            app._monitor = mon
            notes: list[str] = []
            app.notify = lambda msg, **kw: notes.append(str(msg))
            # The state under test: nothing has been seeded yet.
            app._own_window_id = None
            app._own_window_index = None
            app._own_window_name = None
            await pilot_body(app, mon, notes)

    def test_the_own_window_snapshot_resolves_to_nothing(self):
        async def body(app, mon, notes):
            self.assertIsNone(app._find_own_window_snapshot())
            self.assertIsNone(app._find_own_agent_snapshot())

        asyncio.run(self._app(body))

    def test_the_sibling_lookup_refuses_instead_of_picking_a_pane(self):
        """Never a pane id: the raw `list-panes` fallback can select the shadow."""
        async def body(app, mon, notes):
            _in_tmux(self)
            self.assertIsNone(
                app._find_sibling_pane_id(),
                "a sibling pane was resolved from an unseeded window — the "
                "fallback can select the shadow pane (t1382)",
            )
            self.assertTrue(notes, "the refusal was silent")

        asyncio.run(self._app(body))

    def test_the_sibling_refusal_names_the_real_reason(self):
        """"Not inside tmux" sent users after the wrong problem (t1622).

        The two refusals are distinct states and must read as distinct.
        """
        async def body(app, mon, notes):
            _in_tmux(self)
            app._find_sibling_pane_id()
            self.assertIn(
                "Own window not detected yet", notes,
                f"the unseeded-window refusal still reports a tmux problem: "
                f"{notes!r}",
            )

        asyncio.run(self._app(body))

    def test_the_no_tmux_pane_refusal_is_unchanged(self):
        """The other direction — the genuine case keeps its own message."""
        async def body(app, mon, notes):
            saved = os.environ.pop("TMUX_PANE", None)
            self.addCleanup(
                lambda: os.environ.__setitem__("TMUX_PANE", saved)
                if saved is not None else None
            )
            self.assertIsNone(app._find_sibling_pane_id())
            self.assertIn("Not inside tmux", notes)

        asyncio.run(self._app(body))

    def test_switch_to_monitor_refuses_without_touching_tmux(self):
        async def body(app, mon, notes):
            _in_tmux(self)
            app.action_switch_to_monitor()
            self.assertIn("Own window not detected yet", notes)
            self.assertEqual(
                mon.sync_calls, [],
                "a tmux command was issued for a window we cannot name — "
                "`set-environment` would publish a bogus focus request",
            )

        asyncio.run(self._app(body))


if __name__ == "__main__":
    unittest.main(verbosity=2)
