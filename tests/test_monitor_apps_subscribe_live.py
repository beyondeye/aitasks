"""Several clients share ONE scan against a REAL status server (t2037_3).

The task's live acceptance: with N minimonitor-shaped clients subscribed, the
clients themselves perform no `capture-pane` at all (the shared server scans
once per tick for everyone), and every client reports the same last-change time
for each agent pane — one idle clock, read from the same server record.

The control is the same driver with `AITASKS_MONITOR_SERVER=0`: every client
scans in-process and its own counter sees `capture-pane` calls on every round.
That proves the counter observes real captures, so the server-mode zero is not
vacuous.

Each client is built through the apps' own seam,
`monitor_shared.build_monitor_client`, over a real `TmuxMonitor` whose tmux
seam (`_tmux_async`, through which every capture — control client or
subprocess — goes) counts `capture-pane`.

**What it does not prove.** It does not count the shared producer's captures —
the server is another process — and it does not mount the apps. The apps'
interval wiring against a producer's full-scan count is
`test_monitor_apps_subscribe.AppTimerTests`; a live check of several mounted
apps against the real server's scan count is a separate follow-up.

Isolation, skip and cleanup rules are `test_monitor_status_server_live.LiveCase`'s:
a scratch `-L` socket, `TMUX_TMPDIR`, `XDG_RUNTIME_DIR`, `HOME` and marks file;
skip only when `tmux` is missing; only server pids this test's driver reported,
whose command line names the scratch directory, are signalled. The clients run
in a driver subprocess for the same reason as `test_monitor_status_client_live`
(`agent_launch_utils._TMUX` resolves its socket at import).

Run:
  python3 tests/test_monitor_apps_subscribe_live.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

import test_monitor_status_server_live as live  # noqa: E402  (module alias only)

SCRIPTS = TESTS.parent / ".aitask-scripts"
DEADLINE = 30.0
CLIENTS = 3
ROUNDS = 4

#: Builds CLIENTS clients, reads ROUNDS rounds one second apart, then prints one
#: JSON line with the modes, each client's own capture-pane count and the
#: last-change wall time of every agent pane as each client sees it.
DRIVER = r"""
import asyncio, json, sys, time
sys.path[:0] = [sys.argv[1], sys.argv[1] + "/lib"]
from monitor.monitor_core import TmuxMonitor
from monitor.monitor_shared import build_monitor_client
from monitor.status_client import ClientMode

session, root, n, rounds, deadline = (sys.argv[2], sys.argv[3], int(sys.argv[4]),
                                      int(sys.argv[5]), float(sys.argv[6]))

def counted(local, box):
    orig = local._tmux_async
    async def _tmux_async(args, timeout=5.0):
        if args and args[0] == "capture-pane":
            box["captures"] += 1
        return await orig(args, timeout=timeout)
    local._tmux_async = _tmux_async

async def main():
    clients, boxes = [], []
    for _ in range(n):
        local = TmuxMonitor(session=session)
        box = {"captures": 0}
        counted(local, box)
        c = build_monitor_client(local, kind="minimonitor", own_pane=None,
                                 session=session, project_root=root, pins=frozenset())
        c._connect_deadline = deadline
        clients.append(c)
        boxes.append(box)
    try:
        for c in clients:
            await c.start()
        panes = []
        for _ in range(rounds):
            for c in clients:
                snaps = await c.capture_all_async() or {}
                panes.append(sorted(p for p, s in snaps.items()
                                    if s.pane.category.value == "agent"))
            await asyncio.sleep(1.0)
        # Read the idle clocks once every client applied the same generation.
        end = time.monotonic() + deadline
        while True:
            gens = [c._state.gen if c._state is not None else None for c in clients]
            if len(set(gens)) == 1 or time.monotonic() > end:
                break
            await asyncio.sleep(0.05)
        agent_ids = sorted(set(panes[-1]))
        print(json.dumps({
            "modes": [c.mode.value for c in clients],
            "pids": [(c.server_info or {}).get("pid") for c in clients],
            "captures": [b["captures"] for b in boxes],
            "panes": panes,
            "gens": gens,
            "last_change": {p: [c.get_last_change_wall(p) for c in clients]
                            for p in agent_ids},
        }), flush=True)
    finally:
        for c in clients:
            await c.close()

asyncio.run(main())
"""


class SharedScanLiveTests(live.LiveCase):

    def setUp(self):
        super().setUp()
        self.sock_name = self.sock_name.replace("t2037_1", "t2037_3")
        self.env["AITASKS_TMUX_SOCKET"] = self.sock_name

    def _run(self, *, server: bool) -> tuple[dict, list]:
        # A 1 s server tick (the clamp floor) so the read window spans ticks.
        root = self.project("proj", "    refresh_seconds: 1\n")
        session = "aitasks"
        loop = "sh -c 'while :; do date +%s%N; sleep 0.3; done'"
        a = self.session(session, root, "agent-pick-1", loop)
        b = self.window(session, root, "agent-pick-2", loop)
        env = dict(self.env, AITASKS_MONITOR_SERVER="1" if server else "0")
        out = subprocess.run(
            [sys.executable, "-c", DRIVER, str(SCRIPTS), session, str(root),
             str(CLIENTS), str(ROUNDS), str(DEADLINE)],
            env=env, cwd=str(root), capture_output=True, text=True,
            timeout=DEADLINE * 3)
        if out.returncode != 0 or not out.stdout.strip():
            raise AssertionError(f"driver failed ({out.returncode}): {out.stderr}")
        result = json.loads(out.stdout.strip().splitlines()[-1])
        for pid in result["pids"]:
            if pid:
                self.pids.add(pid)
        return result, [a, b]

    def test_clients_share_one_scan_and_one_idle_clock(self):
        result, agents = self._run(server=True)
        self.assertEqual(result["modes"], ["server"] * CLIENTS, result)
        self.assertEqual(len(set(result["pids"])), 1, "the clients share one server")
        self.assertIn(str(self.base), live._cmdline(result["pids"][0]),
                      "the server is this test's own")
        for seen in result["panes"]:
            self.assertEqual(sorted(seen), sorted(agents), result["panes"])
        self.assertEqual(result["captures"], [0] * CLIENTS,
                         "a subscribed client ran its own capture-pane")
        self.assertEqual(len(set(result["gens"])), 1, result["gens"])
        self.assertEqual(sorted(result["last_change"]), sorted(agents))
        for pane_id, walls in result["last_change"].items():
            self.assertIsNotNone(walls[0], f"{pane_id}: no last change — the "
                                           f"agreement below would be vacuous")
            self.assertEqual(len(set(walls)), 1,
                             f"{pane_id}: the clients disagree on last change: {walls}")

    def test_control_in_process_clients_each_capture(self):
        result, agents = self._run(server=False)
        self.assertEqual(result["modes"], ["fallback"] * CLIENTS, result)
        for count in result["captures"]:
            self.assertGreaterEqual(
                count, ROUNDS,
                f"an in-process client captured only {count} times in {ROUNDS} "
                f"rounds — the counter does not see captures: {result['captures']}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
