"""applink on a REAL status server and a REAL tmux server (t2037_4).

The task's live acceptance, with a scripted phone instead of a paired device:
a connection through the real `AppLinkServer._handle` and `FrameRouter`
subscribes to every pane, keeps receiving `pane_status` for both agent panes
across several server ticks, and sends keys that reach the pane — while the
status comes from the shared status server, so the client's own local
`TmuxMonitor` runs **zero** `capture-pane`. Closing the connection releases the
client.

The control is the same driver with `AITASKS_MONITOR_SERVER=0`: the push loop
then scans in-process, and the counter sees `capture-pane` on every pass. That
proves the server-mode zero is not vacuous.

**What it does not prove.** No TLS / websocket transport and no real phone: the
socket is a scripted stand-in (the TLS round-trip is
`test_applink_headless_live.sh`, kept in-process; a real-device check is a
separate manual verification).

Isolation, skip and cleanup are `test_monitor_status_server_live.LiveCase`'s: a
scratch `-L` socket, `TMUX_TMPDIR`, `XDG_RUNTIME_DIR`, `HOME` and marks file;
only server pids the driver reported, whose command line names the scratch
directory, are signalled. `applink.paths.project_root` is pointed at the scratch
project, so no audit log or session file lands in this repository. The server
runs in a driver subprocess because `agent_launch_utils._TMUX` resolves its
socket at import.

Run:
  python3 tests/test_applink_status_subscribe_live.py
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
PROFILES = TESTS.parent / "aitasks" / "metadata" / "applink_profiles"
DEADLINE = 30.0
WATCH_SECONDS = 4.5
MARKER = "applink_t2037_4_marker"

DRIVER = r"""
import asyncio, json, sys, time
from pathlib import Path
scripts, root, profiles, marker, watch = (sys.argv[1], sys.argv[2], sys.argv[3],
                                          sys.argv[4], float(sys.argv[5]))
sys.path[:0] = [scripts + "/applink", scripts, scripts + "/lib"]
import paths
paths.project_root = lambda: Path(root)
import server as SV
import sessions as S
import profiles as P
from monitor.monitor_core import TmuxMonitor

def counted(local, box):
    orig_async, orig_sync = local._tmux_async, local.tmux_run
    async def _tmux_async(args, timeout=5.0):
        if args and args[0] == "capture-pane":
            box["captures"] += 1
        return await orig_async(args, timeout=timeout)
    def tmux_run(args, *a, **kw):
        if args and args[0] == "capture-pane":
            box["captures"] += 1
        return orig_sync(args, *a, **kw)
    local._tmux_async, local.tmux_run = _tmux_async, tmux_run
    return local

class WS:
    remote_address = ("127.0.0.1", 1)
    def __init__(self):
        self.q = asyncio.Queue(); self.sent = []; self.closed = False
    def __aiter__(self): return self
    async def __anext__(self):
        item = await self.q.get()
        if item is None: raise StopAsyncIteration
        return item
    async def send(self, data):
        if self.closed: raise ConnectionError
        self.sent.append(data)
    async def close(self):
        self.closed = True; self.q.put_nowait(None)
    def push(self, frame): self.q.put_nowait(json.dumps(frame))
    def texts(self): return [json.loads(d) for d in self.sent if isinstance(d, str)]

async def main():
    st = S.SessionTable(Path(root) / "applink_sessions", persist=False)
    srv = SV.AppLinkServer(session_table=st, profile_gate=P.ProfileGate.load(Path(profiles)),
                           ssl_context=None, port=0)
    base_box, client_box = {"captures": 0}, {"captures": 0}
    counted(srv._monitor, base_box)
    srv._local_factory = lambda: counted(TmuxMonitor(**srv._client_config), client_box)
    bearer = st.issue_bearer("monitor_control").bearer
    def req(i, verb, payload):
        return {"v": 1, "id": i, "kind": "req", "verb": verb, "payload": payload, "auth": bearer}
    ws = WS()
    handle = asyncio.create_task(srv._handle(ws))
    ws.push(req("s1", "subscribe", {"panes": [], "cadence_idle_ms": 1000}))
    end = time.monotonic() + 15.0
    while time.monotonic() < end and not any(f.get("id") == "s1" for f in ws.texts()):
        await asyncio.sleep(0.05)
    sub = next((f for f in ws.texts() if f.get("id") == "s1"), None)
    await asyncio.sleep(watch)
    client = srv._client
    mode = client.mode.value if client is not None else None
    pid = ((client.server_info or {}).get("pid") if client is not None else None)
    panes = (sub or {}).get("payload", {}).get("panes", [])
    target = panes[0] if panes else None
    if target:
        ws.push(req("k1", "send_keys", {"pane_id": target, "keys": marker, "literal": True}))
        await asyncio.sleep(1.0)
    statuses = {}
    for f in ws.texts():
        if f.get("verb") == "pane_status":
            statuses.setdefault(f["payload"]["pane_id"], 0)
            statuses[f["payload"]["pane_id"]] += 1
    keys = next((f for f in ws.texts() if f.get("id") == "k1"), None)
    await ws.close()
    await asyncio.wait_for(handle, 20.0)
    print(json.dumps({
        "subscribed": panes, "mode": mode, "pid": pid, "statuses": statuses,
        "keys": keys, "client_captures": client_box["captures"],
        "base_captures": base_box["captures"],
        "client_after_close": srv._client is not None,
        "client_closed": bool(client is not None and client._closed),
    }), flush=True)

asyncio.run(main())
"""


class AppLinkStatusLiveTests(live.LiveCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            import msgpack  # noqa: F401, PLC0415
            import yaml  # noqa: F401, PLC0415
            import websockets  # noqa: F401, PLC0415
        except ImportError as exc:
            raise unittest.SkipTest(f"applink deps missing: {exc}")

    def setUp(self):
        super().setUp()
        self.sock_name = self.sock_name.replace("t2037_1", "t2037_4")
        self.env["AITASKS_TMUX_SOCKET"] = self.sock_name

    def _run(self, *, server: bool) -> tuple[dict, list]:
        root = self.project("proj", "    refresh_seconds: 1\n")
        session = "aitasks"
        loop = "sh -c 'while :; do date +%s%N; sleep 0.3; done'"
        a = self.session(session, root, "agent-pick-1", loop)
        b = self.window(session, root, "agent-pick-2", loop)
        env = dict(self.env, AITASKS_MONITOR_SERVER="1" if server else "0")
        out = subprocess.run(
            [sys.executable, "-c", DRIVER, str(SCRIPTS), str(root), str(PROFILES),
             MARKER, str(WATCH_SECONDS)],
            env=env, cwd=str(root), capture_output=True, text=True, timeout=DEADLINE * 3)
        if out.returncode != 0 or not out.stdout.strip():
            raise AssertionError(f"driver failed ({out.returncode}): {out.stderr}")
        result = json.loads(out.stdout.strip().splitlines()[-1])
        if result.get("pid"):
            self.pids.add(result["pid"])
        return result, [a, b]

    def test_status_from_the_server_and_keys_still_reach_the_pane(self):
        result, agents = self._run(server=True)
        self.assertEqual(result["mode"], "server", result)
        self.assertIn(str(self.base), live._cmdline(result["pid"]),
                      "the status server is this test's own")
        for pane_id in agents:
            self.assertIn(pane_id, result["subscribed"])
            self.assertGreaterEqual(result["statuses"].get(pane_id, 0), 3,
                                    f"{pane_id}: too few pane_status pushes: {result}")
        self.assertEqual(result["keys"]["payload"], {"ok": True}, result["keys"])
        target = result["subscribed"][0]
        captured = self.tmux("capture-pane", "-p", "-t", target)
        self.assertIn(MARKER, captured, "send_keys did not reach the pane")
        self.assertEqual(result["client_captures"], 0,
                         "the client's local instance ran its own capture-pane")
        self.assertFalse(result["client_after_close"], "the client outlived the connection")
        self.assertTrue(result["client_closed"])

    def test_control_in_process_push_loop_captures(self):
        result, agents = self._run(server=False)
        self.assertIsNone(result["mode"], "no client when the status server is disabled")
        for pane_id in agents:
            self.assertGreaterEqual(result["statuses"].get(pane_id, 0), 3, result)
        self.assertGreaterEqual(
            result["base_captures"], 3,
            f"the in-process loop captured only {result['base_captures']} times — "
            f"the counter does not see captures")


if __name__ == "__main__":
    unittest.main(verbosity=2)
