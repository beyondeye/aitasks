#!/usr/bin/env python3
"""The monitor's sitrep-refresh maintenance job (t2175_3).

`AgentMarksMixin._maybe_refresh_sitrep` runs `aitask_sitrep_refresh.sh` once
per distinct project root of the tick's sessions that already HAS a sitrep
store (a root without one spawns nothing -- the refresh never creates a store).
It shares the sessions purge's scheduling contract: dispatched from the
trailing maintenance worker, never stacked, its flag cleared in a `finally`,
failures swallowed. Its budget/timeout pair is the script's caller contract:
the hard timeout must be at least budget + 15 s, so the runner's kill can never
land inside a healthy run's write.

Driven through the mixin directly, with `_run_marks_cmd` recorded, so no
subprocess or Textual worker outlives a test
(`aidocs/framework/testing_conventions.md`).

Run: python3 tests/test_monitor_sitrep_refresh.py
"""

from __future__ import annotations

import inspect
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts"))
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "lib"))
os.environ.pop("TMUX", None)

from monitor import monitor_shared  # noqa: E402
from monitor.monitor_shared import AgentMarksMixin  # noqa: E402


class _Host(AgentMarksMixin):
    def __init__(self, session_roots: dict):
        self.ran: list = []
        self._session_root_map = dict(session_roots)
        self._sitrep_refresh_inflight = False
        self._sitrep_refresh_due_at = 0.0     # due now
        self._roots = dict(session_roots)

    def _root_for_session(self, session):
        return self._roots.get(session)

    async def _run_marks_cmd(self, args, *, script=None, timeout=None):
        self.ran.append((Path(str(script)).name, tuple(args), timeout))
        return 0, "REFRESHED:checked=0|changed=0|stale=0|kept=0|unknown=0"


def _store(root: str) -> None:
    os.makedirs(os.path.join(root, ".aitask-sitrep"), exist_ok=True)
    with open(os.path.join(root, ".aitask-sitrep", "store.init"), "w") as fh:
        fh.write("format=1")


class SitrepRefreshJobTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = self._tmp.name
        self.with_store = os.path.join(base, "repo_a")
        self.with_store_b = os.path.join(base, "repo_b")
        self.without = os.path.join(base, "repo_c")
        for r in (self.with_store, self.with_store_b, self.without):
            os.makedirs(r)
        _store(self.with_store)
        _store(self.with_store_b)

    def tearDown(self):
        self._tmp.cleanup()

    async def test_runs_once_per_distinct_root_with_a_store_only(self):
        host = _Host({"s1": self.with_store, "s2": self.with_store,
                      "s3": self.without, "s4": self.with_store_b, "s5": None})
        await host._maybe_refresh_sitrep()
        self.assertEqual(
            [(n, a) for n, a, _t in host.ran],
            [("aitask_sitrep_refresh.sh", ("--root", r, "--budget", "60"))
             for r in sorted([self.with_store, self.with_store_b])])

    async def test_a_root_without_a_store_spawns_nothing(self):
        host = _Host({"s3": self.without})
        await host._maybe_refresh_sitrep()
        self.assertEqual(host.ran, [])

    async def test_the_caller_timeout_covers_budget_plus_margin(self):
        host = _Host({"s1": self.with_store})
        await host._maybe_refresh_sitrep()
        _n, args, timeout = host.ran[0]
        budget = float(args[args.index("--budget") + 1])
        self.assertEqual(budget, monitor_shared._SITREP_REFRESH_BUDGET)
        self.assertGreaterEqual(timeout, budget + 15.0)
        self.assertEqual(timeout, monitor_shared._SITREP_REFRESH_TIMEOUT)

    async def test_it_does_not_run_before_it_is_due(self):
        host = _Host({"s1": self.with_store})
        host._sitrep_refresh_due_at = time.monotonic() + 1000
        await host._maybe_refresh_sitrep()
        self.assertEqual(host.ran, [])

    async def test_cadence_reschedules_after_a_pass(self):
        host = _Host({"s1": self.with_store})
        before = time.monotonic()
        await host._maybe_refresh_sitrep()
        self.assertGreaterEqual(host._sitrep_refresh_due_at,
                                before + monitor_shared._MARKS_PURGE_INTERVAL)
        await host._maybe_refresh_sitrep()
        self.assertEqual(len(host.ran), 1, "a second pass ran before it was due")

    async def test_an_inflight_pass_is_never_stacked(self):
        host = _Host({"s1": self.with_store})
        host._sitrep_refresh_inflight = True
        await host._maybe_refresh_sitrep()
        self.assertEqual(host.ran, [])

    async def test_the_flag_is_cleared_and_other_roots_still_run_when_a_command_raises(self):
        host = _Host({"s1": self.with_store, "s4": self.with_store_b})
        calls = []

        async def boom(args, *, script=None, timeout=None):
            calls.append(args[1])
            raise RuntimeError("wrapper exploded")

        host._run_marks_cmd = boom
        await host._maybe_refresh_sitrep()
        self.assertFalse(host._sitrep_refresh_inflight)
        self.assertGreater(host._sitrep_refresh_due_at, 0.0)
        self.assertEqual(len(calls), 2, "one failing root stopped the others")

    async def test_independent_of_the_sessions_purge_flag(self):
        host = _Host({"s1": self.with_store})
        host._sessions_purge_inflight = True
        await host._maybe_refresh_sitrep()
        self.assertEqual(len(host.ran), 1)


class DispatchTests(unittest.TestCase):
    def test_the_maintenance_worker_awaits_it_after_the_sessions_purge(self):
        src = inspect.getsource(AgentMarksMixin._dispatch_refresh_maintenance)
        self.assertIn("_maybe_refresh_sitrep()", src)
        self.assertLess(src.index("_maybe_purge_sessions()"),
                        src.index("_maybe_refresh_sitrep()"))

    def test_class_level_floors_exist_for_new_built_hosts(self):
        host = AgentMarksMixin.__new__(AgentMarksMixin)
        self.assertFalse(host._sitrep_refresh_inflight)
        self.assertEqual(host._sitrep_refresh_due_at, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
