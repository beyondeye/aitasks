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
import logging
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

import msgpack
import content as C
from pusher import PushScheduler, HIGH_WATER_BYTES
from server import AppLinkServer

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
    def __init__(self, sub, paused=False):
        self.subscription = sub
        self.paused = paused   # t1055: when True, PushScheduler halts all pushes


def binaries(ws):
    return [m for m in ws.sent if isinstance(m, (bytes, bytearray))]

def texts(ws):
    return [m for m in ws.sent if isinstance(m, str)]


class FakeTransport:
    """Controllable write-buffer size so the back-pressure high-water guard
    (_over_high_water) can be driven deterministically."""
    def __init__(self, size=0):
        self.size = size
    def get_write_buffer_size(self):
        return self.size


class ConnClosed(Exception):
    """Stand-in for websockets.ConnectionClosed — production _send/_handle catch
    bare Exception, so a plain subclass exercises the same paths with no dep."""


class RaisingWS:
    """A WebSocket whose send() always raises (abrupt disconnect mid-send)."""
    def __init__(self):
        self.sent = []          # only successful sends would land here (none do)
        self.transport = None   # _over_high_water -> False
    async def send(self, data):
        raise ConnClosed("send after abrupt disconnect")


class HandleWS:
    """Async-iterator WebSocket for driving AppLinkServer._handle: yields a fixed
    list of inbound frames, then raises ConnClosed on the next read (abrupt
    disconnect). send() also raises (abrupt mid-send)."""
    def __init__(self, frames):
        self._frames = list(frames)
        self._i = 0
        self.closed = False
    def __aiter__(self):
        return self
    async def __anext__(self):
        if self._i < len(self._frames):
            f = self._frames[self._i]
            self._i += 1
            return f
        raise ConnClosed("read after abrupt disconnect")
    async def send(self, data):
        raise ConnClosed("send after abrupt disconnect")
    async def close(self):
        self.closed = True


class FakeRouter:
    """Minimal stand-in for FrameRouter: any frame seeds a one-pane subscription
    on the conn (so _handle starts the real pusher) and returns no reply."""
    def __init__(self, monitor):
        self._monitor = monitor
    def handle(self, env, conn):
        sub = C.Subscription()
        sub.apply_subscribe({"panes": ["%1"], "cadence_idle_ms": 1000})
        conn.subscription = sub
        return None
    def set_pair_profile(self, profile):
        pass


async def main():
    # Capture any "Task exception was never retrieved" / unhandled-callback
    # events so the disconnect cases can assert none leaked (task Verification).
    loop_excs = []
    asyncio.get_running_loop().set_exception_handler(
        lambda _loop, ctx: loop_excs.append(ctx))

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

    # === t822_9 delta engine ===============================================
    # INDEPENDENT in-test client: reconstruct the pane buffer ONLY by decoding the
    # actual wire bytes, and compare to a DIRECT parse of the content (truth) —
    # never to another pusher-produced frame. A systematic bug (row order, frame
    # threading, encode layout) then can't pass by corrupting both sides alike.
    def decode_apply(client, frame):
        tag = frame[0]
        body = msgpack.unpackb(frame[1:], raw=False, strict_map_key=False)
        if tag == C.FRAME_KEYFRAME:          # [pane,fid,cols,rows,cursor,rowlist,osc8?]
            client.clear()
            for rid, spans in body[5]:
                if spans:
                    client[rid] = spans
        elif tag == C.FRAME_DELTA:           # [pane,fid,prev,cursor,rowlist,osc8?]
            for rid, spans in body[4]:
                if spans:
                    client[rid] = spans
                else:
                    client.pop(rid, None)    # empty spans clears the row
        return tag, body

    def truth(text):                          # ground truth: a direct full parse
        return {rid: spans for rid, spans in C.snapshot_to_rows(text)[0] if spans}

    subd = C.Subscription()
    subd.apply_subscribe({"panes": ["%1"], "cadence_idle_ms": 1000, "cadence_focused_ms": 300})
    wsd, mond, paned = FakeWS(), FakeMonitor(), FakePane("%1")
    mond.snaps["%1"] = FakeSnap(paned, "line0\nline1\nline2\n")
    nd = {"t": 5000.0}
    schedd = PushScheduler(FakeConn(subd), wsd, mond, clock=lambda: nd["t"])
    client = {}

    # pass 1: subscribe-seeded force -> keyframe
    await schedd._run_once()
    kb = binaries(wsd)
    check("delta block: first frame is a keyframe", len(kb) == 1 and kb[0][0] == C.FRAME_KEYFRAME)
    _kt, kf_body = decode_apply(client, kb[0])
    kf_fid = kf_body[1]
    check("post-keyframe client == direct parse", client == truth("line0\nline1\nline2\n"))

    # pass 2: change one row -> a delta against the keyframe's frame_id
    nd["t"] += 2.0; wsd.sent.clear()
    mond.snaps["%1"] = FakeSnap(paned, "line0\nCHANGED\nline2\n")
    await schedd._run_once()
    db = binaries(wsd)
    check("content change -> exactly one binary frame", len(db) == 1)
    check("frame is a delta (0x02)", db[0][0] == C.FRAME_DELTA)
    _dt, dbody = decode_apply(client, db[0])
    check("delta prev_frame_id == previous keyframe frame_id", dbody[2] == kf_fid)
    check("delta frame_id == prev + 1", dbody[1] == kf_fid + 1)
    check("delta carries only the changed row", [r[0] for r in dbody[4]] == [1])
    check("CONVERGENCE: wire-decoded client == direct content parse",
          client == truth("line0\nCHANGED\nline2\n"))

    # single-row delta is smaller than the equivalent full keyframe
    kf_equiv = C.encode_keyframe("%1", 99, paned.width, paned.height, list(mond.cursor),
                                 [[r, s] for r, s, _u in C.parse_snapshot("line0\nCHANGED\nline2\n")], None)
    check("single-row delta < equivalent keyframe", len(db[0]) < len(kf_equiv))

    # second delta chains on the first; convergence holds
    nd["t"] += 2.0; wsd.sent.clear()
    mond.snaps["%1"] = FakeSnap(paned, "line0\nCHANGED\nLINE2X\n")
    await schedd._run_once()
    _d2t, d2body = decode_apply(client, binaries(wsd)[0])
    check("second delta chains on the first", d2body[2] == dbody[1])
    check("convergence holds after second delta", client == truth("line0\nCHANGED\nLINE2X\n"))

    # removed row -> [row_id, []] clears it; convergence still holds
    nd["t"] += 2.0; wsd.sent.clear()
    mond.snaps["%1"] = FakeSnap(paned, "line0\nCHANGED\n")    # row 2 dropped at fixed dims
    await schedd._run_once()
    _d3t, d3body = decode_apply(client, binaries(wsd)[0])
    check("removed row emitted as blank [row_id, []]", [2, []] in d3body[4])
    check("convergence after removed-row clear", client == truth("line0\nCHANGED\n"))

    # recovery: request_keyframe -> a fresh keyframe rebuilds full state
    nd["t"] += 2.0; wsd.sent.clear()
    subd.request_keyframe("%1")
    await schedd._run_once()
    rb = binaries(wsd)
    check("request_keyframe -> recovery keyframe (0x01)", rb[0][0] == C.FRAME_KEYFRAME)
    fresh = {}
    decode_apply(fresh, rb[0])
    check("recovery keyframe alone reconstructs full state", fresh == truth("line0\nCHANGED\n"))

    # cost fallback: every row changes -> a keyframe, not a delta
    nd["t"] += 2.0; wsd.sent.clear()
    mond.snaps["%1"] = FakeSnap(paned, "AAA\nBBB\n")
    await schedd._run_once()
    check("all-rows-changed -> keyframe (cost fallback)", binaries(wsd)[0][0] == C.FRAME_KEYFRAME)

    # === t822_10 append fast path =========================================
    # Positional in-test client (rows by viewport position), reconstructed ONLY
    # from wire bytes and compared to a DIRECT parse of the content. The append
    # shift semantics (drop k top, append k bottom) are applied by the test
    # client itself — never copied from a pusher artifact (the t822_9 discipline,
    # adapted to append).
    def apply_kf_list(frame):
        body = msgpack.unpackb(frame[1:], raw=False, strict_map_key=False)
        return [spans for _rid, spans in body[5]]            # full grid, in order
    def apply_append_list(buf, frame):
        body = msgpack.unpackb(frame[1:], raw=False, strict_map_key=False)
        newrows = [spans for _rid, spans in body[2]]         # append rowlist
        return buf[len(newrows):] + newrows                  # drop k top, append k bottom
    def truth_list(text):
        rows = dict(C.snapshot_to_rows(text)[0])
        return [rows[i] for i in range(len(rows))]

    # Pane height MUST match the parsed row count or cursor[0] (== 2) never equals
    # bottom_row (dims[1]-1); detect_append keys off len(new_sigs), the gate off dims.
    subA = C.Subscription()
    subA.apply_subscribe({"panes": ["%1"], "cadence_idle_ms": 1000, "cadence_focused_ms": 300})
    wsA, monA, paneA = FakeWS(), FakeMonitor(), FakePane("%1", height=3)
    monA.cursor = (2, 0, True, 0)                            # at bottom row 2, col 0
    monA.snaps["%1"] = FakeSnap(paneA, "a\nb\nc\n")          # exactly 3 parsed rows
    nA = {"t": 8000.0}
    schedA = PushScheduler(FakeConn(subA), wsA, monA, clock=lambda: nA["t"])

    # pass 1: subscribe-seeded force -> keyframe; positional client == truth
    await schedA._run_once()
    kbA = binaries(wsA)
    check("append block: first frame is a keyframe", len(kbA) == 1 and kbA[0][0] == C.FRAME_KEYFRAME)
    buf = apply_kf_list(kbA[0])
    check("append block: post-keyframe client == direct parse", buf == truth_list("a\nb\nc\n"))

    # pass 2: scroll by 1 (append "d") -> a 0x03 append frame
    nA["t"] += 2.0; wsA.sent.clear()
    monA.snaps["%1"] = FakeSnap(paneA, "b\nc\nd\n")
    await schedA._run_once()
    abins = binaries(wsA)
    check("scroll-by-1 -> exactly one binary frame", len(abins) == 1)
    check("frame is an append (0x03)", abins[0][0] == C.FRAME_APPEND)
    abody = msgpack.unpackb(abins[0][1:], raw=False, strict_map_key=False)
    check("append carries no cursor/prev/osc8 (exactly 3 elements)", len(abody) == 3)
    check("append carries exactly the one new bottom row", [r[0] for r in abody[2]] == [2])
    buf = apply_append_list(buf, abins[0])
    check("CONVERGENCE: wire-decoded client == direct content parse after append",
          buf == truth_list("b\nc\nd\n"))

    # pass 3: scroll again (append "e") -> chains; convergence holds; frame_id monotonic
    nA["t"] += 2.0; wsA.sent.clear()
    monA.snaps["%1"] = FakeSnap(paneA, "c\nd\ne\n")
    await schedA._run_once()
    a2 = binaries(wsA)[0]
    check("second scroll -> append again (0x03)", a2[0] == C.FRAME_APPEND)
    a2body = msgpack.unpackb(a2[1:], raw=False, strict_map_key=False)
    check("append frame_id monotonic (prev + 1)", a2body[1] == abody[1] + 1)
    buf = apply_append_list(buf, a2)
    check("convergence holds after second append", buf == truth_list("c\nd\ne\n"))

    # delta-after-append chains: a mid-screen edit -> a delta whose prev_frame_id
    # equals the last append's frame_id (the client adopts the append's frame_id
    # despite append carrying no prev_frame_id of its own).
    nA["t"] += 2.0; wsA.sent.clear()
    monA.snaps["%1"] = FakeSnap(paneA, "c\nX\ne\n")
    await schedA._run_once()
    dpost = binaries(wsA)[0]
    check("mid-screen edit after appends -> a delta (0x02), not an append", dpost[0] == C.FRAME_DELTA)
    dpostbody = msgpack.unpackb(dpost[1:], raw=False, strict_map_key=False)
    check("delta-after-append chains on the last append's frame_id", dpostbody[2] == a2body[1])

    # cursor moved (same row, different column) -> NOT an append (full-tuple gate).
    subB = C.Subscription()
    subB.apply_subscribe({"panes": ["%1"], "cadence_idle_ms": 1000, "cadence_focused_ms": 300})
    wsB, monB, paneB = FakeWS(), FakeMonitor(), FakePane("%1", height=3)
    monB.cursor = (2, 0, True, 0)
    monB.snaps["%1"] = FakeSnap(paneB, "a\nb\nc\n")
    nB = {"t": 9000.0}
    schedB = PushScheduler(FakeConn(subB), wsB, monB, clock=lambda: nB["t"])
    await schedB._run_once()                                 # keyframe seed (last_cursor=[2,0,True,0])
    nB["t"] += 2.0; wsB.sent.clear()
    monB.cursor = (2, 5, True, 0)                            # same row, different column
    monB.snaps["%1"] = FakeSnap(paneB, "b\nc\nd\n")          # a clean scroll
    await schedB._run_once()
    check("cursor moved (col) on a scroll -> NOT an append (full cursor-tuple gate)",
          binaries(wsB)[0][0] != C.FRAME_APPEND)

    # cursor not at the bottom row -> NOT an append (row gate).
    subC = C.Subscription()
    subC.apply_subscribe({"panes": ["%1"], "cadence_idle_ms": 1000, "cadence_focused_ms": 300})
    wsC, monC, paneC = FakeWS(), FakeMonitor(), FakePane("%1", height=3)
    monC.cursor = (0, 0, True, 0)                            # NOT at bottom row 2
    monC.snaps["%1"] = FakeSnap(paneC, "a\nb\nc\n")
    nC = {"t": 9500.0}
    schedC = PushScheduler(FakeConn(subC), wsC, monC, clock=lambda: nC["t"])
    await schedC._run_once()
    nC["t"] += 2.0; wsC.sent.clear()
    monC.snaps["%1"] = FakeSnap(paneC, "b\nc\nd\n")
    await schedC._run_once()
    check("cursor not at bottom on a scroll -> NOT an append (row gate)",
          binaries(wsC)[0][0] != C.FRAME_APPEND)

    # hyperlink in the appended row -> NOT an append (append has no osc8 sidecar);
    # the scroll makes every absolute row change, so the fallback is a keyframe.
    subH = C.Subscription()
    subH.apply_subscribe({"panes": ["%1"], "cadence_idle_ms": 1000, "cadence_focused_ms": 300})
    wsH, monH, paneH = FakeWS(), FakeMonitor(), FakePane("%1", height=3)
    monH.cursor = (2, 0, True, 0)
    monH.snaps["%1"] = FakeSnap(paneH, "a\nb\nc\n")
    nH = {"t": 9800.0}
    schedH = PushScheduler(FakeConn(subH), wsH, monH, clock=lambda: nH["t"])
    await schedH._run_once()                                 # keyframe seed
    nH["t"] += 2.0; wsH.sent.clear()
    monH.snaps["%1"] = FakeSnap(paneH, "b\nc\n\x1b]8;;https://x\x1b\\link\x1b]8;;\x1b\\\n")
    await schedH._run_once()
    check("hyperlink in appended row on a scroll -> NOT an append (no osc8)",
          binaries(wsH)[0][0] != C.FRAME_APPEND)

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

    # === t822_14 resilience: back-pressure (skip-tick, coalesce) ============
    # Gap 1. The landed design realizes the spec's "coalesce -> drop cursor ->
    # skip tick" as skip-tick-and-recapture: while over the high-water mark the
    # whole tick is skipped with the force set intact (coalesce is structural —
    # no send queue; drop-cursor is moot — no standalone cursor frames). Drive
    # _over_high_water deterministically via a fake transport.
    subbp = C.Subscription()
    subbp.apply_subscribe({"panes": ["%1"], "cadence_idle_ms": 1000})
    wsbp, monbp, panebp = FakeWS(), FakeMonitor(), FakePane("%1")
    wsbp.transport = FakeTransport(size=300 * 1024)  # over the 256 KB high-water
    monbp.snaps["%1"] = FakeSnap(panebp, "alpha\n")
    nbp = {"t": 12000.0}
    schedbp = PushScheduler(FakeConn(subbp), wsbp, monbp, clock=lambda: nbp["t"])

    # back-pressured tick: zero bytes sent, forced keyframe preserved in `force`
    await schedbp._run_once()
    check("back-pressure: skipped tick sends zero binary frames", len(binaries(wsbp)) == 0)
    check("back-pressure: skipped tick sends nothing at all", len(wsbp.sent) == 0)
    check("back-pressure: forced keyframe preserved in force during skip", "%1" in subbp.force)

    # buffer drains; two content changes occurred while back-pressured -> the
    # next un-pressured tick coalesces to exactly ONE keyframe of the LATEST state
    nbp["t"] += 2.0
    monbp.snaps["%1"] = FakeSnap(panebp, "beta\n")     # change 1
    monbp.snaps["%1"] = FakeSnap(panebp, "gamma\n")    # change 2 (latest wins)
    wsbp.transport.size = 0                              # under high-water again
    await schedbp._run_once()
    bbp = binaries(wsbp)
    check("back-pressure: drain -> exactly one binary keyframe (coalesced)",
          len(bbp) == 1 and bbp[0][0] == C.FRAME_KEYFRAME)
    kfbp = msgpack.unpackb(bbp[0][1:], raw=False, strict_map_key=False)
    client_bp = {rid: spans for rid, spans in kfbp[5] if spans}
    check("back-pressure: coalesced keyframe carries the LATEST content",
          client_bp == truth("gamma\n"))
    check("back-pressure: force cleared after the successful coalesced send",
          "%1" not in subbp.force)

    # === t1055: `pause` self-throttle halts ALL pushes ======================
    # A paused connection emits nothing — neither binary frames nor the
    # pane_status heartbeat — even with a fresh forced keyframe pending and the
    # buffer well under high-water. Un-pausing emits again, with the forced
    # keyframe preserved across the pause (no state lost).
    subpz = C.Subscription()
    subpz.apply_subscribe({"panes": ["%1"], "cadence_idle_ms": 1000})
    wspz, monpz, panepz = FakeWS(), FakeMonitor(), FakePane("%1")
    monpz.snaps["%1"] = FakeSnap(panepz, "hello\n")
    connpz = FakeConn(subpz, paused=True)
    npz = {"t": 14000.0}
    schedpz = PushScheduler(connpz, wspz, monpz, clock=lambda: npz["t"])

    await schedpz._run_once()
    check("pause: zero binary frames while paused", len(binaries(wspz)) == 0)
    check("pause: zero pane_status (text) frames while paused", len(texts(wspz)) == 0)
    check("pause: nothing sent at all while paused", len(wspz.sent) == 0)
    check("pause: forced keyframe preserved in force during pause", "%1" in subpz.force)

    # resume (router clears conn.paused) -> next tick emits the preserved keyframe
    connpz.paused = False
    await schedpz._run_once()
    bpz = binaries(wspz)
    check("pause: un-pause -> emits exactly one binary keyframe",
          len(bpz) == 1 and bpz[0][0] == C.FRAME_KEYFRAME)
    check("pause: un-pause flushes the preserved forced keyframe", "%1" not in subpz.force)

    # === t822_14 resilience: abrupt disconnect mid-send =====================
    # Gap 2, layer B1 (PushScheduler). A send that raises is swallowed by _send
    # (-> _stopped), the pass returns cleanly, and the post-send-failure HARDENING
    # leaves `force`/PaneState untouched so a forced keyframe is not silently lost.
    subdc = C.Subscription()
    subdc.apply_subscribe({"panes": ["%1"], "cadence_idle_ms": 1000})
    rws, mondc, panedc = RaisingWS(), FakeMonitor(), FakePane("%1")
    mondc.snaps["%1"] = FakeSnap(panedc, "x\n")
    ndc = {"t": 13000.0}
    scheddc = PushScheduler(FakeConn(subdc), rws, mondc, clock=lambda: ndc["t"])
    await scheddc._run_once()        # must not raise
    check("disconnect(B1): send failure is swallowed (no raise out of _run_once)", True)
    check("disconnect(B1): a failed send sets _stopped", scheddc._stopped is True)
    check("disconnect(B1): nothing recorded as successfully sent", len(rws.sent) == 0)
    check("disconnect(B1): HARDENING - forced keyframe NOT dropped from force",
          "%1" in subdc.force)
    stdc = subdc.state_for("%1")
    check("disconnect(B1): HARDENING - PaneState not advanced after failed send",
          stdc.last_hash is None and stdc.last_send_t == 0.0 and stdc.last_dims is None)

    # B1 lifecycle against the raising WS: loop runs, fails, tears down cleanly.
    subdc2 = C.Subscription()
    subdc2.apply_subscribe({"panes": ["%1"], "cadence_idle_ms": 1000})
    rws2 = RaisingWS()
    scheddc2 = PushScheduler(FakeConn(subdc2), rws2, mondc, clock=lambda: ndc["t"])
    scheddc2.start()
    scheddc2.wake()
    await asyncio.sleep(0.05)
    await scheddc2.stop()
    check("disconnect(B1): stop() clears the loop task after send failure (no leak)",
          scheddc2._task is None)

    # Gap 2, layer B2 (AppLinkServer._handle). Exercise the REAL _handle finally:
    # it must pop the conn's pusher from _pushers and await pusher.stop() with no
    # leaked asyncio task. Build a real server WITHOUT the heavy constructor.
    srv = AppLinkServer.__new__(AppLinkServer)
    srv._conns = set()
    srv._live = {}
    srv._pushers = {}
    srv._conns_by_ip = {}              # t985 admission control (per-IP accounting)
    srv._audit = logging.getLogger("applink.audit.test")  # t985 audit (no handlers)
    srv._on_change = None
    srv._sessions = object()           # touch()/_suspend() not reached (bearer/session None)
    monh = FakeMonitor()
    monh.snaps["%1"] = FakeSnap(FakePane("%1"), "h\n")
    srv._monitor = monh
    srv._router = FakeRouter(monh)

    created = []
    _orig_ensure = srv._ensure_pusher
    def _spy_ensure(conn, ws):
        p = _orig_ensure(conn, ws)
        if p not in created:
            created.append(p)
        return p
    srv._ensure_pusher = _spy_ensure

    hws = HandleWS(['{"v":1,"id":"s1","kind":"req","verb":"subscribe"}'])
    await srv._handle(hws)             # must not raise
    await asyncio.sleep(0)             # let any cancelled task fully reap
    check("disconnect(B2): _handle returns cleanly on abrupt disconnect", True)
    check("disconnect(B2): a pusher was created for the subscription", len(created) == 1)
    check("disconnect(B2): _handle finally popped the pusher from _pushers",
          len(srv._pushers) == 0)
    check("disconnect(B2): _handle finally cancelled the pusher task (no leak)",
          created[0]._task is None)
    check("disconnect(B2): pusher stopped", created[0]._stopped is True)
    check("disconnect(B2): connection removed from _conns/_live",
          len(srv._conns) == 0 and len(srv._live) == 0)

    # === t1054 viewport-only keyframe =======================================
    # The capture holds scrollback above the visible viewport (-S -capture_lines).
    # A live keyframe must carry ONLY the trailing `height` viewport rows,
    # renumbered 0..height-1, with the wire `rows` field matching that count
    # (content_transport.md §Row schema). Decode the actual wire bytes and assert
    # against the viewport, never the scrollback.
    subvp = C.Subscription()
    subvp.apply_subscribe({"panes": ["%1"], "cadence_idle_ms": 1000})
    wsvp, monvp, panevp = FakeWS(), FakeMonitor(), FakePane("%1", height=3)
    # 3 scrollback rows (s0..s2) above the 3-row viewport (v0..v2).
    monvp.snaps["%1"] = FakeSnap(panevp, "s0\ns1\ns2\nv0\nv1\nv2\n")
    nvp = {"t": 20000.0}
    schedvp = PushScheduler(FakeConn(subvp), wsvp, monvp, clock=lambda: nvp["t"])
    await schedvp._run_once()
    kfvp = binaries(wsvp)
    check("viewport: forced pass -> one keyframe", len(kfvp) == 1 and kfvp[0][0] == C.FRAME_KEYFRAME)
    decvp = msgpack.unpackb(kfvp[0][1:], raw=False, strict_map_key=False)
    # decvp = [pane, fid, cols, rows, cursor, rowlist, osc8?]
    check("viewport: wire `rows` field == pane height (3)", decvp[3] == 3)
    rowlist = decvp[5]
    check("viewport: keyframe carries exactly `height` rows (no scrollback)", len(rowlist) == 3)
    check("viewport: row_ids renumbered 0..height-1", [r[0] for r in rowlist] == [0, 1, 2])
    check("viewport: rows are the VISIBLE viewport, not scrollback",
          [r[1][0][0] for r in rowlist] == ["v0", "v1", "v2"])

    # === history RPC: drain-after-live, negative row_ids (t1057) ===========
    def hist_frame(ws):
        """The single negative-row-id keyframe among a pass's binary frames."""
        out = None
        for b in binaries(ws):
            if b[0] != C.FRAME_KEYFRAME:
                continue
            body = msgpack.unpackb(b[1:], raw=False, strict_map_key=False)
            if body[5] and body[5][0][0] < 0:
                out = body
        return out

    def row_text(body):
        return {rid: "".join(s[0] for s in spans) for rid, spans in body[5]}

    # 6-line capture: scrollback L0..L2 (idx 0..2), viewport L3..L5; base = 3.
    SCROLL6 = "\n".join(f"L{i}" for i in range(6)) + "\n"

    subh = C.Subscription()
    subh.apply_subscribe({"panes": ["%1"], "cadence_idle_ms": 1000})
    wsh, monh = FakeWS(), FakeMonitor()
    monh.snaps["%1"] = FakeSnap(FakePane("%1", width=40, height=3), SCROLL6)
    schedh = PushScheduler(FakeConn(subh), wsh, monh, clock=lambda: 9000.0)
    subh.request_history("%1", 0, 2)               # queue BEFORE the first live keyframe
    await schedh._run_once()
    bh = binaries(wsh)
    live_body = msgpack.unpackb(bh[0][1:], raw=False, strict_map_key=False)
    check("history pass: live keyframe FIRST (non-negative rows, frame_id=1)",
          bh[0][0] == C.FRAME_KEYFRAME and live_body[1] == 1
          and all(rid >= 0 for rid, _ in live_body[5]))
    hb = hist_frame(wsh)
    check("history keyframe emitted AFTER the live one (negative row_ids)",
          hb is not None and [rid for rid, _ in hb[5]] == [-1, -2])
    check("history rows are the scrollback lines above the viewport (-1->L2, -2->L1)",
          row_text(hb) == {-1: "L2", -2: "L1"})
    check("history hidden cursor", hb[4] == [0, 0, False, 0])
    check("history frame_id == live frame_id; live chain not advanced",
          hb[1] == live_body[1] and subh.state_for("%1").frame_id == 1)
    check("history queue drained after the pass", subh.has_pending_history() is False)

    # anchoring: history reflects the DRAIN-TIME capture, not the queue-time one
    suba = C.Subscription()
    suba.apply_subscribe({"panes": ["%1"], "cadence_idle_ms": 1000})
    wsa, mona, panea = FakeWS(), FakeMonitor(), FakePane("%1", width=40, height=3)
    mona.snaps["%1"] = FakeSnap(panea, "\n".join(f"A{i}" for i in range(6)) + "\n")
    na = {"t": 9000.0}
    scheda = PushScheduler(FakeConn(suba), wsa, mona, clock=lambda: na["t"])
    await scheda._run_once()                        # establish the live baseline
    suba.request_history("%1", 0, 2)
    mona.snaps["%1"] = FakeSnap(panea, "\n".join(f"B{i}" for i in range(6)) + "\n")  # mutate
    na["t"] += 2.0; wsa.sent.clear()
    await scheda._run_once()
    check("history reflects the drain-time capture (best-effort anchoring)",
          row_text(hist_frame(wsa)) == {-1: "B2", -2: "B1"})

    # back-pressure: over high-water -> NO frame, history stays pending
    subb = C.Subscription()
    subb.apply_subscribe({"panes": ["%1"], "cadence_idle_ms": 1000})
    wsb, monb = FakeWS(), FakeMonitor()
    wsb.transport = FakeTransport(size=HIGH_WATER_BYTES + 1)
    monb.snaps["%1"] = FakeSnap(FakePane("%1", width=40, height=3), SCROLL6)
    schedb = PushScheduler(FakeConn(subb), wsb, monb, clock=lambda: 9000.0)
    subb.request_history("%1", 0, 2)
    await schedb._run_once()
    check("over high-water -> no binary frames (history included)",
          len(binaries(wsb)) == 0)
    check("over high-water -> history request stays pending (no loss)",
          subb.has_pending_history() is True)

    # best-effort delivery: subscribed pane absent from capture -> no keyframe
    subm = C.Subscription()
    subm.apply_subscribe({"panes": ["%9"], "cadence_idle_ms": 1000})  # %9 never captured
    wsm, monm = FakeWS(), FakeMonitor()                               # empty snaps
    schedm = PushScheduler(FakeConn(subm), wsm, monm, clock=lambda: 9000.0)
    subm.request_history("%9", 0, 5)
    await schedm._run_once()
    check("subscribed-but-missing pane -> no history keyframe (token != delivery)",
          hist_frame(wsm) is None)
    check("missing-pane history request is drained (no infinite retry)",
          subm.has_pending_history() is False)

    # paused: drain is halted until resume (request preserved)
    subp = C.Subscription()
    subp.apply_subscribe({"panes": ["%1"], "cadence_idle_ms": 1000})
    wsp, monp = FakeWS(), FakeMonitor()
    monp.snaps["%1"] = FakeSnap(FakePane("%1", width=40, height=3), SCROLL6)
    schedp = PushScheduler(FakeConn(subp, paused=True), wsp, monp, clock=lambda: 9000.0)
    subp.request_history("%1", 0, 2)
    await schedp._run_once()
    check("paused conn -> no history drain; request preserved",
          len(binaries(wsp)) == 0 and subp.has_pending_history() is True)

    # Whole-suite assertion: no "Task exception was never retrieved" / unhandled
    # callback ever surfaced through the loop exception handler.
    check("no unretrieved task / unhandled-callback exceptions across the suite",
          loop_excs == [])

    print(f"\nALL PASSED ({PASS} checks)")


asyncio.run(main())
PYEOF
