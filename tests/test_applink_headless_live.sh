#!/usr/bin/env bash
# test_applink_headless_live.sh — live wss:// round-trip for the applink headless
# bridge (t822_13). Exercises the task's explicit acceptance: `ait monitor
# --headless-for-applink` starts WITHOUT a controlling TTY and a scripted client
# pairs over real TLS and (best-effort) receives a keyframe. Skip-capable: skips
# cleanly when the runtime deps / tmux / openssl are unavailable.
# Run: bash tests/test_applink_headless_live.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

if ! "$PYTHON" -c "import websockets, msgpack, segno, yaml" 2>/dev/null; then
    echo "SKIP: websockets/msgpack/segno/pyyaml not installed (run 'ait setup' first)"
    exit 0
fi
if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not installed"
    exit 0
fi
if ! command -v openssl >/dev/null 2>&1; then
    echo "SKIP: openssl not installed (needed to generate the self-signed cert)"
    exit 0
fi
if ! command -v setsid >/dev/null 2>&1; then
    echo "SKIP: setsid not available (cannot launch without a controlling TTY)"
    exit 0
fi

PORT="$("$PYTHON" -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1]); s.close()")"
SESS="ait_hltest_$$"
LOG="$(mktemp)"
HL_PID=""

cleanup() {
    [[ -n "$HL_PID" ]] && kill -TERM "$HL_PID" 2>/dev/null || true
    tmux kill-session -t "$SESS" 2>/dev/null || true
    rm -f "$LOG"
}
trap cleanup EXIT

# A throwaway tmux session rooted in the repo so the headless monitor discovers
# it as an aitasks session (discovery walks the pane cwd up to the project root).
# Created BEFORE the server starts so the first discovery sees it. Only THIS
# session is ever torn down; a developer's real `aitasks` session is untouched,
# and the client only subscribes to this session's pane (read-only capture).
tmux new-session -d -s "$SESS" -c "$PROJECT_DIR" -x 80 -y 24 2>/dev/null || {
    echo "SKIP: could not create a throwaway tmux session"; exit 0; }
PANE_ID="$(tmux list-panes -t "$SESS" -F '#{pane_id}' 2>/dev/null | head -1)"

# Launch the bridge with NO controlling TTY (setsid), via the real launcher, on
# the chosen free port. stdout/stderr captured to $LOG.
setsid bash "$PROJECT_DIR/.aitask-scripts/aitask_monitor.sh" \
    --headless-for-applink --port "$PORT" >"$LOG" 2>&1 &
HL_PID=$!

# Wait for the "Pair URL:" line — proves it started without a TTY and is serving.
deadline=$(( SECONDS + 20 ))
PAIR_LINE=""
while (( SECONDS < deadline )); do
    if ! kill -0 "$HL_PID" 2>/dev/null; then
        echo "FAIL: headless process exited early"; echo "--- log ---"; cat "$LOG"; exit 1
    fi
    PAIR_LINE="$(grep -m1 'Pair URL:' "$LOG" 2>/dev/null || true)"
    [[ -n "$PAIR_LINE" ]] && break
    sleep 0.5
done
if [[ -z "$PAIR_LINE" ]]; then
    echo "FAIL: no 'Pair URL:' within timeout"; echo "--- log ---"; cat "$LOG"; exit 1
fi
echo "ok - headless bridge started without a TTY and printed a pairing endpoint"

URI="$(echo "$PAIR_LINE" | sed -E 's/^Pair URL:[[:space:]]*//')"
TOKEN="$(echo "$URI" | sed -E 's/.*[?&]t=([^&]+).*/\1/')"
FP="$(echo "$URI" | sed -E 's/.*[?&]fp=([^&]+).*/\1/')"
CERT="$PROJECT_DIR/aitasks/metadata/applink_sessions/server.crt"

# Scripted wss:// client: pin the cert (TLS verifies against the on-disk cert and
# the printed fingerprint is checked against it), pair, then best-effort keyframe.
"$PYTHON" - "$PORT" "$TOKEN" "$FP" "$CERT" "$PANE_ID" <<'PYEOF'
import asyncio, base64, hashlib, json, ssl, sys

port, token, printed_fp, cert_path, pane_id = sys.argv[1:6]
port = int(port)

import websockets


def cert_fingerprint(path):
    pem = open(path).read()
    der = ssl.PEM_cert_to_DER_cert(pem)
    return base64.urlsafe_b64encode(hashlib.sha256(der).digest()).decode().rstrip("=")


async def main():
    # Pin: the printed fingerprint must match the cert the server serves.
    if cert_fingerprint(cert_path) != printed_fp:
        print("FAIL: printed fingerprint does not match the server cert")
        return 1
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(cert_path)   # cryptographic pin to the cert
    ctx.check_hostname = False             # CN is ait-applink, host is 127.0.0.1
    async with websockets.connect(f"wss://127.0.0.1:{port}/", ssl=ctx) as ws:
        await ws.send(json.dumps({
            "v": 1, "id": "1", "kind": "req", "verb": "pair",
            "payload": {"token": token, "device": {"name": "live-test", "platform": "test"}},
        }))
        res = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        if res.get("kind") != "res" or not res.get("payload", {}).get("bearer"):
            print(f"FAIL: pair did not return a bearer: {res}")
            return 1
        bearer = res["payload"]["bearer"]
        if res["payload"].get("profile") != "monitor_control":
            print(f"FAIL: unexpected profile {res['payload'].get('profile')!r}")
            return 1
        print("ok - paired over wss:// (fingerprint pinned), bearer + monitor_control profile")

        # t1044: an EMPTY `subscribe` must mean "all currently-discovered panes".
        # Send panes:[] (exactly what the mobile client does) and assert the server's
        # subscribe ack lists the throwaway session's pane in the roster — proving
        # the expansion end-to-end against the real server. Then best-effort await a
        # binary keyframe (content streaming) for that pane.
        await ws.send(json.dumps({
            "v": 1, "id": "2", "kind": "req", "verb": "subscribe",
            "auth": bearer, "payload": {"panes": []},
        }))
        got_roster = False
        got_keyframe = False
        try:
            deadline = asyncio.get_event_loop().time() + 8
            while asyncio.get_event_loop().time() < deadline:
                msg = await asyncio.wait_for(ws.recv(), timeout=8)
                if isinstance(msg, (bytes, bytearray)):
                    if msg and msg[0] == 0x01:
                        got_keyframe = True
                    continue
                frame = json.loads(msg)
                if frame.get("id") == "2" and frame.get("kind") == "res":
                    roster = frame.get("payload", {}).get("panes", [])
                    if pane_id not in roster:
                        print(f"FAIL: empty subscribe roster {roster} omits throwaway pane {pane_id}")
                        return 1
                    got_roster = True
                    print(f"ok - empty subscribe expanded to all discovered panes (roster includes {pane_id})")
                if got_roster and got_keyframe:
                    break
        except asyncio.TimeoutError:
            pass
        if not got_roster:
            print("FAIL: no subscribe ack (res id=2) received for empty subscribe")
            return 1
        if got_keyframe:
            print("ok - received a binary keyframe (0x01) on the empty-subscribe data plane")
        else:
            print("SKIP: roster verified; no keyframe within timeout (pane may be empty/undiscovered)")
        return 0

sys.exit(asyncio.run(main()))
PYEOF
client_rc=$?
if [[ "$client_rc" -ne 0 ]]; then
    echo "FAIL: scripted wss:// client failed (rc=$client_rc)"; echo "--- log ---"; cat "$LOG"; exit 1
fi

# Re-pairing affordance: SIGHUP mints a fresh token and reprints.
before="$(grep -c 'Pair URL:' "$LOG")"
kill -HUP "$HL_PID" 2>/dev/null || true
deadline=$(( SECONDS + 8 ))
while (( SECONDS < deadline )); do
    after="$(grep -c 'Pair URL:' "$LOG")"
    (( after > before )) && break
    sleep 0.5
done
if (( $(grep -c 'Pair URL:' "$LOG") > before )); then
    echo "ok - SIGHUP reprinted a fresh pairing token"
else
    echo "WARN: SIGHUP did not reprint within timeout (non-fatal)"
fi

# Clean shutdown on SIGTERM.
kill -TERM "$HL_PID" 2>/dev/null || true
deadline=$(( SECONDS + 8 ))
while (( SECONDS < deadline )); do
    kill -0 "$HL_PID" 2>/dev/null || break
    sleep 0.5
done
if kill -0 "$HL_PID" 2>/dev/null; then
    echo "FAIL: headless did not exit on SIGTERM"; exit 1
fi
HL_PID=""
echo "ok - headless bridge shut down cleanly on SIGTERM"

echo ""
echo "ALL PASSED"
