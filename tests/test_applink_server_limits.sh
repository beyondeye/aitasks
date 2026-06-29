#!/usr/bin/env bash
# test_applink_server_limits.sh — DoS admission control for AppLinkServer (t985).
#
# Drives the REAL AppLinkServer._handle against fake websockets (no sockets, no
# TLS) to assert: global connection cap, per-IP cap, the pre-auth frame budget,
# and the pre-auth idle watchdog. Run:
#   bash tests/test_applink_server_limits.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

if ! "$PYTHON" -c "import yaml" 2>/dev/null; then
    echo "SKIP: pyyaml not installed (run 'ait setup' first)"
    exit 0
fi

"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import asyncio
import logging
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

import server as SV
from server import AppLinkServer
from router import ConnState

PASS = 0
def check(label, cond):
    global PASS
    assert cond, f"FAIL: {label}"
    PASS += 1
    print(f"ok - {label}")


class FakeWS:
    """Async-iterable fake websocket. Yields `frames`, then optionally blocks
    until closed (to model an idle, never-authenticating client)."""
    def __init__(self, frames=None, block=False, ip="10.0.0.5"):
        self.remote_address = (ip, 5555)
        self._frames = list(frames or [])
        self._block = block
        self.closed = False
        self._evt = asyncio.Event()

    async def __aiter__(self):
        for f in self._frames:
            if self.closed:
                return
            yield f
        if self._block:
            await self._evt.wait()

    async def send(self, data):
        pass

    async def close(self):
        self.closed = True
        self._evt.set()


class FakeRouter:
    """Never binds a session — every frame stays unauthenticated."""
    def handle(self, env, conn):
        return {"v": 1, "id": "x", "kind": "err", "verb": None,
                "payload": {"code": "AUTH_FAILED", "message": "no"}}


def new_server():
    srv = AppLinkServer.__new__(AppLinkServer)
    srv._conns = set()
    srv._live = {}
    srv._pushers = {}
    srv._conns_by_ip = {}
    srv._on_change = None
    srv._sessions = object()
    srv._router = FakeRouter()
    cap = logging.getLogger(f"applink.audit.srvtest.{id(srv)}")
    cap.handlers.clear()
    cap.setLevel(logging.INFO)
    msgs = []
    class H(logging.Handler):
        def emit(self, rec): msgs.append(rec.getMessage())
    cap.addHandler(H())
    srv._audit = cap
    return srv, msgs


async def main():
    # --- global connection cap --------------------------------------------
    srv, msgs = new_server()
    srv._conns = {ConnState() for _ in range(SV.MAX_CONNECTIONS)}
    ws = FakeWS(frames=['{}'])
    await srv._handle(ws)
    check("global cap: over-limit socket is closed", ws.closed is True)
    check("global cap: connection set not grown", len(srv._conns) == SV.MAX_CONNECTIONS)
    check("global cap: audited", any("global_cap" in m for m in msgs))

    # --- per-IP cap -------------------------------------------------------
    srv, msgs = new_server()
    srv._conns_by_ip = {"10.0.0.5": SV.MAX_PER_IP}
    ws = FakeWS(frames=['{}'], ip="10.0.0.5")
    await srv._handle(ws)
    check("per-IP cap: over-limit socket is closed", ws.closed is True)
    check("per-IP cap: audited", any("per_ip_cap" in m for m in msgs))
    # A different IP is still admitted (one host can't starve the others) and
    # its per-IP count is released on disconnect.
    srv2, msgs2 = new_server()
    srv2._conns_by_ip = {"10.0.0.5": SV.MAX_PER_IP}
    ws2 = FakeWS(frames=['{}'], ip="10.0.0.9")
    await srv2._handle(ws2)
    check("per-IP cap: a different IP is admitted (accepted, not rejected)",
          any("CONN_ACCEPT ip=10.0.0.9" in m for m in msgs2)
          and not any("per_ip_cap" in m for m in msgs2))
    check("per-IP cap: admitted IP's count released on disconnect",
          "10.0.0.9" not in srv2._conns_by_ip)

    # --- pre-auth frame budget --------------------------------------------
    srv, msgs = new_server()
    flood = ['{}'] * (SV.MAX_PREAUTH_FRAMES + 5)
    ws = FakeWS(frames=flood)
    await srv._handle(ws)
    check("frame budget: unauth flood is dropped", ws.closed is True)
    check("frame budget: audited", any("preauth_flood" in m for m in msgs))
    check("frame budget: connection cleaned up", len(srv._conns) == 0 and srv._conns_by_ip == {})

    # --- pre-auth idle watchdog -------------------------------------------
    orig = SV.PREAUTH_TIMEOUT
    SV.PREAUTH_TIMEOUT = 0.05
    try:
        srv, msgs = new_server()
        ws = FakeWS(frames=[], block=True)   # opens, then sends nothing
        await asyncio.wait_for(srv._handle(ws), timeout=2.0)
    finally:
        SV.PREAUTH_TIMEOUT = orig
    check("idle watchdog: silent unauth socket is closed", ws.closed is True)
    check("idle watchdog: audited", any("preauth_timeout" in m for m in msgs))
    check("idle watchdog: connection cleaned up", len(srv._conns) == 0)

    # --- (t1007) decode-bomb: _route_raw degrades to BAD_PAYLOAD, never raises --
    # A JSON nested deep enough to raise RecursionError needs ~200 KB; the transport
    # max_size (64 KB) already rejects that, so this is defense-in-depth, exercised
    # here by calling _route_raw directly (bypassing the cap). The FakeRouter returns
    # AUTH_FAILED for any *decoded* frame, so a BAD_PAYLOAD reply proves the
    # RecursionError catch fired rather than the bomb parsing through.
    srv, _ = new_server()
    bomb = "[" * 200000 + "]" * 200000
    reply = srv._route_raw(bomb, ConnState())
    check("decode bomb -> BAD_PAYLOAD frame (no raise, no connection drop)",
          isinstance(reply, dict) and reply.get("kind") == "err"
          and reply["payload"]["code"] == "BAD_PAYLOAD")

    # --- (t1092) applink history-capture config: load + clamp + threading -----
    # Pins the exact YAML path (tmux.applink.history_capture_lines), the clamp,
    # and the graceful-fallback so a nesting/path typo fails here instead of
    # silently leaving the server on the default.
    import tempfile
    from pusher import PushScheduler, DEFAULT_HISTORY_CAPTURE_LINES

    def _cfg(td, body):
        meta = Path(td) / "aitasks" / "metadata"
        meta.mkdir(parents=True, exist_ok=True)
        (meta / "project_config.yaml").write_text(body)
        return td

    with tempfile.TemporaryDirectory() as td:                      # missing applink key
        _cfg(td, "tmux:\n  monitor:\n    capture_lines: 200\n")
        check("load_applink_config: missing tmux.applink -> default 2000",
              SV.load_applink_config(td)["history_capture_lines"] == 2000)
    with tempfile.TemporaryDirectory() as td:                      # missing file entirely
        check("load_applink_config: missing config file -> default 2000",
              SV.load_applink_config(td)["history_capture_lines"] == 2000)
    with tempfile.TemporaryDirectory() as td:                      # configured value
        _cfg(td, "tmux:\n  applink:\n    history_capture_lines: 3000\n")
        check("load_applink_config: configured value honored (3000)",
              SV.load_applink_config(td)["history_capture_lines"] == 3000)
    with tempfile.TemporaryDirectory() as td:                      # over-ceiling clamp
        _cfg(td, "tmux:\n  applink:\n    history_capture_lines: 999999\n")
        check("load_applink_config: over-ceiling clamped to HARD_MAX (10000)",
              SV.load_applink_config(td)["history_capture_lines"]
              == SV.HARD_MAX_HISTORY_CAPTURE_LINES == 10000)
    for bad in ('"abc"', "-5", "0", "null", "[1, 2]"):            # malformed -> default
        with tempfile.TemporaryDirectory() as td:
            _cfg(td, f"tmux:\n  applink:\n    history_capture_lines: {bad}\n")
            check(f"load_applink_config: malformed ({bad}) -> safe default 2000",
                  SV.load_applink_config(td)["history_capture_lines"] == 2000)

    # threading: the loaded value reaches the scheduler verbatim
    ps = PushScheduler(ConnState(), FakeWS(), object(), history_capture_lines=4242)
    check("PushScheduler threads history_capture_lines verbatim (4242)",
          ps._history_capture_lines == 4242)
    ps_def = PushScheduler(ConnState(), FakeWS(), object())
    check("PushScheduler default ceiling == DEFAULT_HISTORY_CAPTURE_LINES (2000)",
          ps_def._history_capture_lines == DEFAULT_HISTORY_CAPTURE_LINES == 2000)

asyncio.run(main())
print(f"\nALL PASSED ({PASS} checks)")
PYEOF
