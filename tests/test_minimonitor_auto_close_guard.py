"""minimonitor auto-close must never fire on an unverifiable observation (t1446).

On 2026-08-06 a machine-wide stall pushed the 5 s tmux timeout over the edge in
every `ait minimonitor` companion at once and they all quit within the same
second, abandoning the agents they were watching. Nothing killed them:
`TmuxClient.run` returned `(-1, "")`, `discover_window_panes` collapsed any
`rc != 0` into `[]`, and `_check_auto_close` read that `[]` as "no other panes
remain in my window".

Three layers, deliberately separated so each negative control breaks exactly one:

1. **Contract** — the real `TmuxMonitor.discover_window_panes` with only
   `tmux_run` faked. `observed` is `True` only when tmux answered AND every
   non-blank record parsed; a dropped record matters because a truncated sibling
   row leaves a listing that looks exactly like solitude.
2. **Decision** — the real `MiniMonitorApp._check_auto_close` against a real
   `TmuxMonitor` whose `tmux_run` is scripted, so the whole `rc` → exit chain is
   under test rather than a replica. `exit` is recorded, never really called.
3. **Wiring** — a mounted app driving the real `_refresh_data` tick. Layer 2
   would pass with the `_check_auto_close()` call missing from `_refresh_data`,
   or with the streak reset on every tick. Note this layer deliberately does NOT
   clear `_own_window_id` (the way `test_minimonitor_own_mark.py` does to keep
   auto-close out of its way) — clearing it here would make the suite pass
   vacuously.

Negative controls (one mutation each; a PASSING negative control means the test
is wrong):

| mutation | must fail |
|---|---|
| `discover_window_panes` back to `if rc != 0: return []` (+ caller back to `if not other_panes: self.exit()`) | `test_transport_failure_is_not_an_empty_window`, `test_repeated_transport_failure_never_exits`, `test_stalled_tmux_tick_does_not_close_the_app` |
| restore the bare `continue`s (drop the completeness flag) | `test_truncated_sibling_row_makes_the_listing_unverifiable`, `test_dropped_sibling_row_never_exits` |
| `AUTO_CLOSE_CONFIRMATIONS = 1` | `test_exit_requires_two_consecutive_verified_empty` |

Mock-based apart from layer 3's mounted app; no live tmux, no real subprocess.

Run: python3 tests/test_minimonitor_auto_close_guard.py
or:  bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
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
from monitor.minimonitor_app import (  # noqa: E402
    AUTO_CLOSE_CONFIRMATIONS,
    MiniMonitorApp,
)
from monitor.monitor_core import TmuxMonitor  # noqa: E402
from monitor.tmux_control import TmuxControlState  # noqa: E402
from monitor.tmux_monitor import (  # noqa: E402
    PaneCategory,
    PaneSnapshot,
    TmuxPaneInfo,
)

SESSION = "demo"
OWN_WINDOW_INDEX = "1"
OWN_WINDOW_ID = "@7"
OWN_WINDOW = "agent-followed"
OWN_PANE = "%1"
SIBLING_PANE = "%2"


# --- listing fixtures -------------------------------------------------------
#
# `discover_window_panes` asks for 8 tab-separated fields:
#   window_index, window_name, pane_index, pane_id, pane_pid,
#   pane_current_command, pane_width, pane_height

def row(pane_id: str, *, command: str = "node", pid: str = "4242") -> str:
    return "\t".join([
        OWN_WINDOW_INDEX, OWN_WINDOW, "0", pane_id, pid, command, "80", "24",
    ])


def truncated_row(pane_id: str) -> str:
    """A record that lost its trailing field — 7 columns, silently dropped."""
    return "\t".join([
        OWN_WINDOW_INDEX, OWN_WINDOW, "0", pane_id, "4242", "node", "80",
    ])


def bad_pid_row(pane_id: str) -> str:
    """8 columns, but `pane_pid` is not an integer — also silently dropped."""
    return row(pane_id, pid="not-a-pid")


ALONE = row(OWN_PANE) + "\n"
WITH_SIBLING = row(OWN_PANE) + "\n" + row(SIBLING_PANE) + "\n"
OWN_PLUS_TRUNCATED_SIBLING = row(OWN_PANE) + "\n" + truncated_row(SIBLING_PANE) + "\n"
OWN_PLUS_BAD_PID_SIBLING = row(OWN_PANE) + "\n" + bad_pid_row(SIBLING_PANE) + "\n"
WITHOUT_OWN = row(SIBLING_PANE) + "\n"


def monitor_replying(*replies: tuple[int, str]) -> TmuxMonitor:
    """A real TmuxMonitor whose only faked seam is the tmux round-trip.

    Each call consumes the next reply; the last one repeats forever, so a test
    can drive N identical ticks with a single entry.
    """
    mon = TmuxMonitor(session=SESSION, multi_session=False)
    queue = list(replies)

    def fake_tmux_run(args, timeout=5.0):
        return queue.pop(0) if len(queue) > 1 else queue[0]

    mon.tmux_run = fake_tmux_run
    return mon


# ---------------------------------------------------------------------------
# Layer 1 — the contract: what counts as an observation
# ---------------------------------------------------------------------------

class DiscoverWindowPanesContractTests(unittest.TestCase):
    def observe(self, rc: int, stdout: str):
        return monitor_replying((rc, stdout)).discover_window_panes(OWN_WINDOW_ID)

    def test_transport_failure_is_not_an_empty_window(self):
        """rc == -1 (timeout / OSError) — the t1446 trigger."""
        observed, panes = self.observe(-1, "")
        self.assertFalse(
            observed,
            "a timed-out tmux query reported itself as a successful observation",
        )
        self.assertEqual(panes, [])

    def test_tmux_command_error_is_not_an_empty_window(self):
        observed, panes = self.observe(1, "")
        self.assertFalse(observed)
        self.assertEqual(panes, [])

    def test_successful_listing_is_observed(self):
        observed, panes = self.observe(0, WITH_SIBLING)
        self.assertTrue(observed)
        self.assertEqual([p.pane_id for p in panes], [OWN_PANE, SIBLING_PANE])

    def test_successful_empty_listing_is_observed(self):
        observed, panes = self.observe(0, "")
        self.assertTrue(observed, "tmux answered — that IS an observation")
        self.assertEqual(panes, [])

    def test_truncated_sibling_row_makes_the_listing_unverifiable(self):
        """Our row parses, the sibling's does not — this must not read as solitude."""
        observed, panes = self.observe(0, OWN_PLUS_TRUNCATED_SIBLING)
        self.assertFalse(
            observed,
            "a dropped record left the listing flagged complete, so a lost "
            "sibling row is indistinguishable from an empty window",
        )
        self.assertEqual(
            [p.pane_id for p in panes], [OWN_PANE],
            "the records that DID parse should still be returned",
        )

    def test_unparseable_pid_makes_the_listing_unverifiable(self):
        observed, panes = self.observe(0, OWN_PLUS_BAD_PID_SIBLING)
        self.assertFalse(observed)
        self.assertEqual([p.pane_id for p in panes], [OWN_PANE])

    def test_blank_lines_do_not_make_a_listing_unverifiable(self):
        observed, panes = self.observe(
            0, row(OWN_PANE) + "\n\n" + row(SIBLING_PANE) + "\n"
        )
        self.assertTrue(observed, "a blank line is not a dropped record")
        self.assertEqual(len(panes), 2)


# ---------------------------------------------------------------------------
# Layer 2 — the decision: real _check_auto_close, real rc plumbing
# ---------------------------------------------------------------------------

class AutoCloseDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._env = patch.dict(os.environ, {"TMUX_PANE": OWN_PANE})
        self._env.start()
        self.addCleanup(self._env.stop)

    def app(self, *replies: tuple[int, str]):
        """A real MiniMonitorApp (real `__init__`) with `exit` recorded."""
        app = MiniMonitorApp(session=SESSION, project_root=Path(self._tmp.name))
        app._monitor = monitor_replying(*replies)
        app._own_window_id = OWN_WINDOW_ID
        exits: list[bool] = []
        app.exit = lambda *a, **kw: exits.append(True)
        return app, exits

    def test_init_starts_the_streak_at_zero(self):
        app, _ = self.app((0, ALONE))
        self.assertEqual(app._empty_window_streak, 0)

    def test_repeated_transport_failure_never_exits(self):
        """The incident: every tick times out, for as long as the stall lasts."""
        app, exits = self.app((-1, ""))
        for _ in range(5):
            app._check_auto_close()
        self.assertEqual(
            exits, [],
            "the companion quit on an observation it could not make — t1446",
        )
        self.assertEqual(app._empty_window_streak, 0)

    def test_repeated_tmux_error_never_exits(self):
        app, exits = self.app((1, ""))
        for _ in range(5):
            app._check_auto_close()
        self.assertEqual(exits, [])

    def test_dropped_sibling_row_never_exits(self):
        """A self-sighting rule alone would wave this through: our row is there."""
        app, exits = self.app((0, OWN_PLUS_TRUNCATED_SIBLING))
        for _ in range(5):
            app._check_auto_close()
        self.assertEqual(
            exits, [],
            "a truncated sibling row was treated as a verified empty window",
        )

    def test_exit_requires_two_consecutive_verified_empty(self):
        app, exits = self.app((0, ALONE))
        app._check_auto_close()
        self.assertEqual(exits, [], "exited on a single verified-empty observation")
        self.assertEqual(app._empty_window_streak, 1)
        app._check_auto_close()
        self.assertEqual(len(exits), 1)

    def test_an_unverifiable_tick_resets_the_streak(self):
        app, exits = self.app(
            (0, ALONE), (-1, ""), (0, ALONE), (0, ALONE),
        )
        app._check_auto_close()          # streak 1
        app._check_auto_close()          # tmux stalled -> streak 0
        self.assertEqual(app._empty_window_streak, 0)
        app._check_auto_close()          # streak 1 again
        self.assertEqual(
            exits, [],
            "the streak survived a failed observation — two verified-empty "
            "sightings must be CONSECUTIVE",
        )
        app._check_auto_close()          # streak 2
        self.assertEqual(len(exits), 1)

    def test_a_live_sibling_resets_the_streak(self):
        app, exits = self.app((0, ALONE), (0, WITH_SIBLING), (0, ALONE))
        for _ in range(3):
            app._check_auto_close()
        self.assertEqual(exits, [])
        self.assertEqual(app._empty_window_streak, 1)

    def test_a_sibling_pane_never_exits(self):
        app, exits = self.app((0, WITH_SIBLING))
        for _ in range(5):
            app._check_auto_close()
        self.assertEqual(exits, [])

    def test_a_listing_without_our_own_pane_never_exits(self):
        app, exits = self.app((0, WITHOUT_OWN))
        for _ in range(5):
            app._check_auto_close()
        self.assertEqual(
            exits, [],
            "a listing that does not mention us is not a self-sighting",
        )

    def test_no_tmux_pane_in_the_environment_never_exits(self):
        app, exits = self.app((0, ALONE))
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TMUX_PANE", None)
            for _ in range(5):
                app._check_auto_close()
        self.assertEqual(exits, [])

    def test_the_confirmation_count_is_the_module_constant(self):
        """Pin the wiring, so bumping the constant cannot silently no-op."""
        app, exits = self.app((0, ALONE))
        for _ in range(AUTO_CLOSE_CONFIRMATIONS - 1):
            app._check_auto_close()
        self.assertEqual(exits, [])
        app._check_auto_close()
        self.assertEqual(len(exits), 1)


# ---------------------------------------------------------------------------
# Layer 3 — wiring, proven through real refresh cycles
# ---------------------------------------------------------------------------

def _pane_snapshot(window: str, pane_id: str, window_index: str) -> PaneSnapshot:
    return PaneSnapshot(
        pane=TmuxPaneInfo(
            window_index=window_index, window_name=window, pane_index="0",
            pane_id=pane_id, pane_pid=4242, current_command="node",
            width=80, height=24, category=PaneCategory.AGENT,
            session_name=SESSION,
        ),
        content="x", timestamp=0.0, idle_seconds=1.0, is_idle=False,
    )


class _TickMonitor:
    """Tick surface for `_refresh_data`, with the REAL window discovery.

    `discover_window_panes` is `TmuxMonitor`'s own implementation bound to a
    real instance whose `tmux_run` is scripted — so layer 3 exercises the same
    rc → decision chain as layer 2, through a real refresh cycle.
    """

    multi_session = False

    def __init__(self, root: Path, *replies: tuple[int, str]) -> None:
        self._mapping = {SESSION: root}
        self._real = monitor_replying(*replies)
        self.snaps = [
            _pane_snapshot(OWN_WINDOW, OWN_PANE, OWN_WINDOW_INDEX),
            _pane_snapshot("agent-elsewhere", "%9", "2"),
        ]

    def discover_window_panes(self, window_id):
        return self._real.discover_window_panes(window_id)

    # `_update_own_window_info` runs for real; a failed query makes it keep the
    # window id it already has, which is what happens during a stall.
    def tmux_run(self, args, timeout=5.0): return (1, "")

    async def capture_all_async(self):
        return {s.pane.pane_id: s for s in self.snaps}

    def get_session_to_project_mapping(self): return self._mapping
    def get_compare_mode(self, pane_id): return "stripped"
    def is_compare_mode_overridden(self, pane_id): return False
    def get_shadow_snapshot(self, pane_id): return None
    def get_shadow_snapshots(self): return {}
    def control_state(self): return TmuxControlState.CONNECTED


class _FakeTaskCache:
    def get_task_id_for_pane(self, pane): return None
    def get_task_info(self, task_id, session=None): return None
    def update_session_mapping(self, mapping): pass
    def invalidate(self, task_id, session=None): pass


async def _noop_async():
    return None


class RefreshCycleWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "repo"
        self.root.mkdir()
        self.store = self.tmp / "marks.json"
        self._env = patch.dict(os.environ, {"TMUX_PANE": OWN_PANE})
        self._env.start()
        self.addCleanup(self._env.stop)

    def _instrument(self, app, *replies: tuple[int, str]) -> list[bool]:
        """Isolate everything EXCEPT the auto-close path under test.

        `_own_window_id` stays set and `_check_auto_close` stays real — those
        are the subject. Only the mark machinery and the concern probe (which
        would touch disk / spawn subprocesses) are stubbed.
        """
        if getattr(app, "_refresh_timer", None) is not None:
            app._refresh_timer.stop()
            app._refresh_timer = None
        app._monitor = _TickMonitor(self.root, *replies)
        app._task_cache = _FakeTaskCache()
        app._session = SESSION
        app._own_window_index = OWN_WINDOW_INDEX
        app._own_window_id = OWN_WINDOW_ID
        app._maybe_offer_concerns = _noop_async
        app._marks_view = agent_marks.MarksView(self.store)
        app._marks_purge_due_at = float("inf")
        app._marks_purge_inflight = False
        # Past the 5 s post-mount grace, so the tick reaches the check at all.
        app._mount_time = time.monotonic() - 60.0
        exits: list[bool] = []
        app.exit = lambda *a, **kw: exits.append(True)
        return exits

    def test_stalled_tmux_tick_does_not_close_the_app(self):
        """Three real refresh cycles under a tmux that answers nothing."""
        seen: list = []

        async def runner():
            app = MiniMonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=(40, 30)) as pilot:
                exits = self._instrument(app, (-1, ""))
                for _ in range(3):
                    await app._refresh_data()
                    await pilot.pause()
                seen.append((list(exits), app.is_running, app._empty_window_streak))

        asyncio.run(runner())
        exits, running, streak = seen[0]
        self.assertEqual(
            exits, [],
            "a stalled tmux closed the companion through a real refresh tick",
        )
        self.assertTrue(running)
        self.assertEqual(streak, 0)

    def test_a_verified_empty_window_closes_the_app_after_two_ticks(self):
        """The companion must still do its job — auto-close is not disabled."""
        seen: list = []

        async def runner():
            app = MiniMonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=(40, 30)) as pilot:
                exits = self._instrument(app, (0, ALONE))
                await app._refresh_data()
                await pilot.pause()
                seen.append(list(exits))
                await app._refresh_data()
                await pilot.pause()
                seen.append(list(exits))

        asyncio.run(runner())
        self.assertEqual(seen[0], [], "closed on a single tick")
        self.assertEqual(len(seen[1]), 1,
                         "auto-close never fired through a real refresh cycle")

    def test_a_stall_between_two_empty_ticks_defers_the_close(self):
        """The streak must be reset by the tick, not just by a direct call."""
        seen: list = []

        async def runner():
            app = MiniMonitorApp(session=SESSION, project_root=self.root)
            async with app.run_test(size=(40, 30)) as pilot:
                exits = self._instrument(
                    app, (0, ALONE), (-1, ""), (0, ALONE), (0, ALONE),
                )
                for _ in range(3):
                    await app._refresh_data()
                    await pilot.pause()
                seen.append(list(exits))
                await app._refresh_data()
                await pilot.pause()
                seen.append(list(exits))

        asyncio.run(runner())
        self.assertEqual(seen[0], [], "a stalled tick did not reset the streak")
        self.assertEqual(len(seen[1]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
