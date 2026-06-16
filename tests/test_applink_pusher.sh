#!/usr/bin/env bash
# test_applink_pusher.sh — async unit tests for the applink data-plane push
# scheduler (t822_8). Drives PushScheduler against a fake WebSocket and a fake
# monitor (no sockets, no tmux), asserting: a forced pass emits a binary
# keyframe + a pane_status push; an idle pass emits zero binary frames; a resize
# emits dim-then-keyframe; and stop() tears the loop task down cleanly.
# Run: bash tests/test_applink_pusher.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

if ! "$PYTHON" -c "import msgpack" 2>/dev/null; then
    echo "SKIP: msgpack not installed (run 'ait setup' first)"
    exit 0
fi

"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import asyncio
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

import msgpack
import content as C
from pusher import PushScheduler

PASS = 0
def check(label, cond):
    global PASS
    assert cond, f"FAIL: {label}"
    PASS += 1
    print(f"ok - {label}")


class FakeCategory:
    value = "agent"


class FakePane:
    def __init__(self, pane_id, width=80, height=24):
        self.pane_id = pane_id
        self.width = width
        self.height = height
        self.window_name = "agent-pick-100"
        self.session_name = "aitasks"
        self.category = FakeCategory()


class FakeSnap:
    def __init__(self, pane, content):
        self.pane = pane
        self.content = content
        self.idle_seconds = 1.0
        self.is_idle = False
        self.awaiting_input = False
        self.awaiting_input_kind = ""


class FakeMonitor:
    def __init__(self):
        self.snaps = {}
        self.cursor = (2, 3, True, 0)
    async def capture_all_async(self):
        return dict(self.snaps)
    async def capture_cursor_async(self, pane_id):
        return self.cursor


class FakeWS:
    def __init__(self):
        self.sent = []
        self.transport = None
    async def send(self, data):
        self.sent.append(data)


class FakeConn:
    def __init__(self, sub):
        self.subscription = sub


def binaries(ws):
    return [m for m in ws.sent if isinstance(m, (bytes, bytearray))]

def texts(ws):
    return [m for m in ws.sent if isinstance(m, str)]


async def main():
    now = {"t": 1000.0}
    clock = lambda: now["t"]

    sub = C.Subscription()
    sub.apply_subscribe({"panes": ["%1"], "cadence_idle_ms": 1000, "cadence_focused_ms": 300})
    ws = FakeWS()
    mon = FakeMonitor()
    pane = FakePane("%1")
    mon.snaps["%1"] = FakeSnap(pane, "line1\nline2\n")
    sched = PushScheduler(FakeConn(sub), ws, mon, clock=clock)

    # --- emit: a forced pane -> binary keyframe + pane_status push ----------
    await sched._run_once()
    bins = binaries(ws)
    check("forced pass -> exactly one binary frame", len(bins) == 1)
    check("binary frame is a keyframe (0x01)", bins[0][0] == C.FRAME_KEYFRAME)
    dec = msgpack.unpackb(bins[0][1:], raw=False, strict_map_key=False)
    check("keyframe carries pane id + dims + cursor",
          dec[0] == "%1" and dec[2] == 80 and dec[3] == 24 and dec[4] == [2, 3, True, 0])
    ps = [json.loads(t) for t in texts(ws)]
    check("pane_status push emitted", any(p.get("verb") == "pane_status" for p in ps))
    check("pane_status carries derived task_id + kind",
          ps[0]["kind"] == "push" and ps[0]["payload"]["task_id"] == "100")
    check("force set cleared after keyframe", "%1" not in sub.force)

    # --- idle: unchanged content within keyframe interval -> zero binary ----
    now["t"] += 2.0          # past the 1s cadence, but content is unchanged
    ws.sent.clear()
    await sched._run_once()
    check("idle pane -> zero binary frames between changes", len(binaries(ws)) == 0)

    # --- resize: dims change -> dim (0x05) then a fresh keyframe (0x01) -----
    now["t"] += 2.0
    pane.width = 100
    ws.sent.clear()
    await sched._run_once()
    tags = [b[0] for b in binaries(ws)]
    check("resize -> dim then keyframe", tags == [C.FRAME_DIM, C.FRAME_KEYFRAME])

    # --- lifecycle teardown -------------------------------------------------
    sub2 = C.Subscription()
    sub2.apply_subscribe({"panes": ["%1"], "cadence_idle_ms": 1000})
    ws2 = FakeWS()
    sched2 = PushScheduler(FakeConn(sub2), ws2, mon, clock=clock)
    sched2.start()
    check("start() creates a loop task", sched2._task is not None)
    sched2.wake()
    await asyncio.sleep(0.05)          # let one pass run
    check("woken loop emitted a keyframe", any(b[0] == C.FRAME_KEYFRAME for b in binaries(ws2)))
    await sched2.stop()
    check("stop() clears the loop task (no leak)", sched2._task is None)
    count_before = len(ws2.sent)
    sched2.wake()
    await asyncio.sleep(0.02)
    check("post-stop wake() triggers no further sends", len(ws2.sent) == count_before)

    print(f"\nALL PASSED ({PASS} checks)")


asyncio.run(main())
PYEOF
