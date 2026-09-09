#!/usr/bin/env python3
"""The session store's maintenance pass and the shared observation file (t1705_7).

Two pieces of `monitor_shared` that keep the frozen-agent store from rotting
while a monitor is open, and one property of the file they share.

`ObservationFileTests`
    ONE file serves BOTH purges. `PANE` rows are a backward-compatible superset:
    `agent_marks._read_observed` skips them, `agent_sessions` requires them for
    its `dead_pane` rule. The fail-closed direction is the point — omitting the
    rows yields exactly the old file, which the session store then treats as
    pane-incomplete, so `dead_window` still applies and `dead_pane` does not. A
    missing pane can therefore never be mistaken for a dead one.

`SessionsPurgeTests`
    The pass is DISPATCHED, never awaited by the render path, and it is
    scheduled on its own flag so a wedged sessions wrapper cannot stop marks
    being purged (or the reverse). It runs two commands — the store's liveness
    purge and `aitask_frozen.sh reconcile` — because retirement must not depend
    on a TUI being open, and this is the opportunistic half of that.

Everything is driven through the mixin directly: the seams are named methods for
exactly this reason, so no Textual worker outlives the test (see
`aidocs/framework/testing_conventions.md`).

Run: python3 tests/test_monitor_sessions_purge.py
"""

from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts"))
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "lib"))

os.environ.pop("TMUX", None)

import agent_marks  # noqa: E402
from monitor import monitor_shared  # noqa: E402
from monitor.monitor_shared import AgentMarksMixin  # noqa: E402


class _Host(AgentMarksMixin):
    """The minimum an app must provide, plus recorders for both seams."""

    def __init__(self, panes=None, panes_raise=False):
        self.ran: list[tuple[str, tuple, float | None]] = []
        self._monitor = _Mon(panes, panes_raise)
        self._snapshots = {}
        self._marks_purge_inflight = False
        self._marks_purge_due_at = float("inf")   # marks purge stays quiet
        self._sessions_purge_inflight = False
        self._sessions_purge_due_at = 0.0         # sessions purge is due now
        self.notes: list[str] = []

    async def _run_marks_cmd(self, args, *, script=None, timeout=None):
        name = Path(str(script)).name if script else "aitask_agent_marks.sh"
        self.ran.append((name, tuple(args), timeout))
        return 0, ""

    def _collect_marks_observation(self):
        return ({"/repo": {"agent-a"}}, {"/repo"}, True)

    def _root_for_session(self, session):
        """The mapping the purge uses to re-key panes before writing them."""
        return {"demo": "/repo"}.get(session)

    def notify(self, msg, **kw):
        self.notes.append(str(msg))

    def call_later(self, fn, *a):
        pass

    def _refresh_data(self):
        pass


class _Mon:
    def __init__(self, panes, panes_raise):
        self._panes = panes
        self._raise = panes_raise

    def last_discovered_panes(self):
        if self._raise:
            raise RuntimeError("tmux unreachable")
        return self._panes or {}


class ObservationFileTests(unittest.TestCase):
    """The shared file's shape."""

    def _write(self, panes=None):
        host = _Host()
        path = host._write_observation_file(
            {"/repo": {"agent-a"}}, {"/repo"}, True, panes=panes)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        return Path(path).read_text(encoding="utf-8")

    def test_without_panes_it_is_byte_for_byte_the_old_file(self):
        """The backward-compatible half: the marks purge's file is unchanged."""
        self.assertEqual(
            self._write(),
            "ROOT\t/repo\nWINDOW\t/repo\tagent-a\n",
        )

    def test_pane_rows_follow_their_window_row(self):
        text = self._write({("/repo", "agent-a"): [("%1", 4242, False)]})
        self.assertEqual(
            text,
            "ROOT\t/repo\n"
            "WINDOW\t/repo\tagent-a\n"
            "PANE\t/repo\tagent-a\t%1\t4242\t0\n",
        )

    def test_a_dead_pane_is_recorded_as_1(self):
        text = self._write({("/repo", "agent-a"): [("%1", 4242, True)]})
        self.assertIn("PANE\t/repo\tagent-a\t%1\t4242\t1\n", text)

    def test_panes_of_an_unobserved_window_are_not_emitted(self):
        """A `PANE` row without its `WINDOW` row would claim a pane in a window
        the sweep never saw — the session store reads that as evidence."""
        text = self._write({("/repo", "agent-other"): [("%9", 1, False)]})
        self.assertNotIn("%9", text)

    def test_panes_are_keyed_by_root_not_by_window_name_alone(self):
        """Two projects can share a window name. Keying on the name alone would
        list each one's panes under the other's root, and the store would then
        read a pane in project A as evidence that project B's record is alive."""
        host = _Host()
        path = host._write_observation_file(
            {"/repo": {"agent-a"}, "/other": {"agent-a"}},
            {"/repo", "/other"}, True,
            panes={("/repo", "agent-a"): [("%1", 4242, False)],
                   ("/other", "agent-a"): [("%2", 5555, False)]},
        )
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        text = Path(path).read_text(encoding="utf-8")
        self.assertIn("PANE\t/repo\tagent-a\t%1\t4242\t0\n", text)
        self.assertIn("PANE\t/other\tagent-a\t%2\t5555\t0\n", text)
        self.assertNotIn("PANE\t/repo\tagent-a\t%2", text)
        self.assertNotIn("PANE\t/other\tagent-a\t%1", text)

    def test_the_marks_reader_still_parses_it(self):
        """The compatibility claim, checked against the real reader rather than
        asserted in prose: `agent_marks` must SKIP `PANE` rows, not choke."""
        host = _Host()
        path = host._write_observation_file(
            {"/repo": {"agent-a"}}, {"/repo"}, True,
            panes={("/repo", "agent-a"): [("%1", 4242, False)]})
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        observed, sweepable, complete = agent_marks._read_observed(path)
        self.assertEqual(observed, {"/repo": {"agent-a"}})
        self.assertEqual(sweepable, {"/repo"})
        self.assertTrue(complete)

    def test_incomplete_still_leads(self):
        host = _Host()
        path = host._write_observation_file({}, set(), False, panes=None)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        self.assertTrue(
            Path(path).read_text(encoding="utf-8").startswith("INCOMPLETE\n"))


class SessionsPurgeTests(unittest.IsolatedAsyncioTestCase):
    """The maintenance pass itself."""

    async def test_it_runs_the_purge_then_the_reconcile(self):
        host = _Host(panes={("demo", "agent-a"): [("%1", 4242, False)]})
        await host._maybe_purge_sessions()
        names = [(n, a[0]) for n, a, _t in host.ran]
        self.assertEqual(
            names,
            [("aitask_agent_sessions.sh", "purge"),
             ("aitask_frozen.sh", "reconcile")],
            "reconcile must run too — retirement cannot depend on a TUI being "
            "open, and this is the opportunistic half of that",
        )

    async def test_it_rekeys_the_monitors_panes_from_session_to_root(self):
        """`last_discovered_panes()` is keyed by SESSION; the file is keyed by
        ROOT. The re-key happens here, where the session→root map lives — and an
        unattributable session is dropped rather than filed under a guess."""
        written = {}
        host = _Host(panes={("demo", "agent-a"): [("%1", 4242, False)],
                            ("unknown", "agent-a"): [("%9", 1, False)]})
        real = host._write_observation_file

        def spy(observed, sweepable, complete, panes=None):
            written["panes"] = panes
            return real(observed, sweepable, complete, panes=panes)

        host._write_observation_file = spy
        await host._maybe_purge_sessions()
        self.assertEqual(written["panes"],
                         {("/repo", "agent-a"): [("%1", 4242, False)]})

    async def test_the_purge_is_given_the_observation_file(self):
        host = _Host(panes={("demo", "agent-a"): [("%1", 4242, False)]})
        await host._maybe_purge_sessions()
        _name, args, _t = host.ran[0]
        self.assertEqual(args[:2], ("purge", "--observed"))
        self.assertFalse(
            os.path.exists(args[2]),
            "the temp observation file was left behind",
        )

    async def test_it_does_not_run_before_the_startup_grace(self):
        """A blocking subprocess on the mount tick is what t1598 removed; the
        sessions purge inherits that deferral rather than re-introducing it."""
        host = _Host()
        host._sessions_purge_due_at = time.monotonic() + 1000
        await host._maybe_purge_sessions()
        self.assertEqual(host.ran, [])

    async def test_an_inflight_pass_is_never_stacked(self):
        host = _Host()
        host._sessions_purge_inflight = True
        await host._maybe_purge_sessions()
        self.assertEqual(host.ran, [])

    async def test_the_inflight_flag_is_cleared_even_when_a_command_raises(self):
        """In a `finally`, so a hung or raising wrapper cannot wedge every later
        tick's maintenance — the same rule `_maybe_purge_marks` states."""
        host = _Host()

        async def boom(*a, **k):
            raise RuntimeError("wrapper exploded")

        host._run_marks_cmd = boom
        await host._maybe_purge_sessions()
        self.assertFalse(host._sessions_purge_inflight)
        self.assertGreater(host._sessions_purge_due_at, 0.0)

    async def test_it_is_scheduled_independently_of_the_marks_purge(self):
        """Separate flags: a wedged sessions wrapper must not stop marks being
        purged, or the reverse."""
        host = _Host()
        host._marks_purge_inflight = True          # marks is stuck
        await host._maybe_purge_sessions()
        self.assertEqual(len(host.ran), 2, "the sessions purge was blocked by "
                                          "the marks purge's flag")

    async def test_an_unreadable_monitor_still_purges_fail_closed(self):
        """No `PANE` rows makes the file pane-incomplete for that root, so
        `dead_window` still applies and `dead_pane` does not — a missing pane can
        never be read as a dead one."""
        host = _Host(panes_raise=True)
        await host._maybe_purge_sessions()
        self.assertEqual(len(host.ran), 2)

    async def test_the_freeze_budget_is_used_not_the_marks_budget(self):
        """Reconcile can respawn a stand-in, so the 20s marks ceiling would kill
        it mid-transaction."""
        host = _Host()
        await host._maybe_purge_sessions()
        _n, _a, reconcile_timeout = host.ran[1]
        self.assertEqual(reconcile_timeout, monitor_shared._FREEZE_ONE_TIMEOUT)


class MaintenanceDispatchTests(unittest.TestCase):
    """It is reached from the tick's trailing worker, and never awaited there."""

    def test_the_maintenance_worker_awaits_the_sessions_purge(self):
        import inspect
        src = inspect.getsource(
            AgentMarksMixin._dispatch_refresh_maintenance)
        self.assertIn("_maybe_purge_sessions()", src)
        self.assertIn("run_worker(", src,
                      "maintenance must be DISPATCHED, not awaited by the "
                      "render path — a wedged wrapper would freeze the tick")

    def test_the_render_path_never_awaits_it_directly(self):
        """The seam is a sync method on purpose (t1598): tests stub *it* and
        assert the work was requested, rather than letting a real worker outlive
        an `App.run_test` block."""
        import inspect
        self.assertFalse(
            inspect.iscoroutinefunction(
                AgentMarksMixin._dispatch_refresh_maintenance))


if __name__ == "__main__":
    unittest.main(verbosity=2)
