"""`MonitorClient` against the REAL status server lifecycle (t2037_2).

[live_client_reconnect] The in-process client tests use a fake `ensure`; this
file proves the real path end to end on an isolated tmux server: `ensure_server`
called from the client's worker thread under a running loop, spawning the real
detached `serve` process; and "reconnect when the server restarts" — the server
is SIGTERMed, the client falls back to its in-process `TmuxMonitor`, and its
reconnect loop starts a new server and subscribes again.

Isolation: the server live test's `LiveCase` gives a scratch `-L` tmux socket,
`TMUX_TMPDIR`, `XDG_RUNTIME_DIR`, `HOME` and marks file. The client runs in a
**driver subprocess** started with that environment, never in this process:
`agent_launch_utils._TMUX` is a module-level `TmuxClient` that resolves its
socket at import, so an in-process client would aim its fallback discovery at
whatever tmux server this test process was started under.

Skip only when `tmux` is missing. Cleanup signals only server pids reported by
this test's own driver whose command line names the scratch directory, and
kills the tmux server by its explicit `-L` name (`LiveCase._cleanup`).

Run:
  python3 tests/test_monitor_status_client_live.py
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

import test_monitor_status_server_live as live  # noqa: E402  (module alias only)

SCRIPTS = TESTS.parent / ".aitask-scripts"
DEADLINE = 30.0

#: Runs the client; prints one JSON event per line; exits after the second
#: subscription (or on its own deadline).
DRIVER = r"""
import asyncio, json, sys, time
sys.path[:0] = [sys.argv[1], sys.argv[1] + "/lib"]
from monitor import status_client as sc
from monitor.monitor_core import TmuxMonitor

def emit(**kw):
    print(json.dumps(kw), flush=True)

async def wait_mode(c, mode, deadline):
    end = time.monotonic() + deadline
    while c.mode is not mode:
        if time.monotonic() > end:
            emit(event="timeout", waiting_for=mode.value, mode=c.mode.value,
                 last_error=c.last_error)
            return False
        await asyncio.sleep(0.05)
    return True

async def panes_with(c, pane_id, deadline):
    end = time.monotonic() + deadline
    while True:
        snaps = await c.capture_all_async() or {}
        if pane_id in snaps or time.monotonic() > end:
            return sorted(snaps)
        await asyncio.sleep(0.2)

async def main():
    session, pane_id, deadline = sys.argv[2], sys.argv[3], float(sys.argv[4])
    c = sc.MonitorClient(TmuxMonitor(session=session), kind="test-live", session=session,
                         connect_deadline=deadline, backoff=(0.0, 0.5, 1.0))
    try:
        await c.start()
        if not await wait_mode(c, sc.ClientMode.SERVER, deadline):
            return
        emit(event="server", pid=c.server_info.get("pid"),
             panes=await panes_with(c, pane_id, deadline))
        line = await asyncio.to_thread(sys.stdin.readline)   # the test killed the server
        if not await wait_mode(c, sc.ClientMode.FALLBACK, deadline):
            return
        emit(event="fallback", last_error=c.last_error,
             panes=await panes_with(c, pane_id, deadline))
        if not await wait_mode(c, sc.ClientMode.SERVER, deadline):
            return
        emit(event="server", pid=c.server_info.get("pid"),
             panes=await panes_with(c, pane_id, deadline))
    finally:
        await c.close()

asyncio.run(main())
"""


class ClientReconnectLiveTests(live.LiveCase):

    def setUp(self):
        super().setUp()
        self.sock_name = self.sock_name.replace("t2037_1", "t2037_2")
        self.env["AITASKS_TMUX_SOCKET"] = self.sock_name

    def read_event(self, proc) -> dict:
        line = proc.stdout.readline()
        if not line:
            raise AssertionError(f"driver exited early: {proc.stderr.read()}")
        event = json.loads(line)
        if event["event"] == "timeout":
            raise AssertionError(f"driver timed out: {event}")
        if event.get("pid"):
            self.pids.add(event["pid"])
        return event

    def test_server_killed_falls_back_then_reconnects(self):
        root = self.project("proj")
        session = "aitasks"
        pane_id = self.session(
            session, root, "agent-pick-1",
            "sh -c 'while :; do date +%s%N; sleep 0.2; done'")

        proc = subprocess.Popen(
            [sys.executable, "-c", DRIVER, str(SCRIPTS), session, pane_id, str(DEADLINE)],
            env=self.env, cwd=str(root), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        try:
            first = self.read_event(proc)
            self.assertEqual(first["event"], "server")
            self.assertIn(pane_id, first["panes"])
            pid = first["pid"]
            self.assertTrue(pid)
            self.assertIn(str(self.base), live._cmdline(pid),
                          "only a server this test started is signalled")
            os.kill(pid, signal.SIGTERM)
            self.assertTrue(self.wait_gone(pid), "server did not exit on SIGTERM")
            proc.stdin.write("killed\n")
            proc.stdin.flush()

            fallback = self.read_event(proc)
            self.assertEqual(fallback["event"], "fallback")
            self.assertIn(pane_id, fallback["panes"], "in-process capture keeps working")

            second = self.read_event(proc)
            self.assertEqual(second["event"], "server")
            self.assertNotEqual(second["pid"], pid, "a new server was started")
            self.assertIn(pane_id, second["panes"])
            proc.wait(timeout=DEADLINE)
            self.assertEqual(proc.returncode, 0, proc.stderr.read())
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                stream.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
