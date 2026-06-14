#!/usr/bin/env bash
# test_applink_router.sh — unit tests for the applink JSON control plane (t822_7).
#
# Drives the pure router (frame parsing, pairing, auth, profile gating, the
# pull-model confirm handshake, key translation, deferred verbs) against a stub
# monitor — no sockets, no tmux, no TLS handshake — plus a TLS fingerprint
# determinism check. Run: bash tests/test_applink_router.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

# pyyaml backs ProfileGate.load against the real profile YAMLs; skip the suite
# on a fresh clone that has not run `ait setup`.
if ! "$PYTHON" -c "import yaml" 2>/dev/null; then
    echo "SKIP: pyyaml not installed (run 'ait setup' first)"
    exit 0
fi

"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

import sessions as S
import profiles as P
from monitor.monitor_core import translate_key
from router import FrameRouter, ConnState, KNOWN_VERBS

PASS = 0
def check(label, cond):
    global PASS
    assert cond, f"FAIL: {label}"
    PASS += 1
    print(f"ok - {label}")


class StubMonitor:
    """Records dispatch calls; returns canned successes."""
    def __init__(self):
        self.calls = []
    def send_enter(self, p):
        self.calls.append(("send_enter", p)); return True
    def send_keys(self, p, k, literal=False):
        self.calls.append(("send_keys", p, k, literal)); return True
    def forward_key(self, p, key, character=None):
        self.calls.append(("forward_key", p, key)); return True
    def switch_to_pane(self, p, prefer_companion=False):
        self.calls.append(("focus", p, prefer_companion)); return True
    def cycle_compare_mode(self, p):
        self.calls.append(("cycle", p)); return ("raw", False)
    def kill_agent_pane_smart(self, p):
        self.calls.append(("kill_pane", p)); return (True, True)
    def kill_window(self, p):
        self.calls.append(("kill_window", p)); return True
    def spawn_tui(self, n):
        self.calls.append(("spawn_tui", n)); return True


def req(verb, payload=None, auth=None, mid="m1"):
    return {"v": 1, "id": mid, "kind": "req", "verb": verb,
            "payload": payload or {}, "auth": auth}


# --- key translation -------------------------------------------------------
check("translate_key special", translate_key("up") == ("Up", False))
check("translate_key ctrl", translate_key("ctrl+c") == ("C-c", False))
check("translate_key char", translate_key("a") == ("a", True))
check("translate_key glyph via character", translate_key("exclamation_mark", "!") == ("!", True))
check("translate_key unmappable", translate_key("supercalifragilistic") is None)

# --- router fixtures -------------------------------------------------------
profiles_dir = root / "aitasks" / "metadata" / "applink_profiles"
gate = P.ProfileGate.load(profiles_dir)
check("profiles load (read_only/monitor_control/full)",
      {"read_only", "monitor_control", "full"} <= set(gate.names()))

mon = StubMonitor()
st = S.SessionTable(Path("/tmp/applink_router_test"), persist=False)
router = FrameRouter(st, gate, mon, pair_profile="monitor_control")

# --- pairing ---------------------------------------------------------------
conn = ConnState()
r = router.handle(req("pair", {"token": "wrong"}), conn)
check("pair bad token -> AUTH_FAILED", r["kind"] == "err" and r["payload"]["code"] == "AUTH_FAILED")
check("pair bad token requests close", conn.close_requested is True)

tok = st.mint_pairing_token()
conn = ConnState()
r = router.handle(req("pair", {"token": tok, "device": {"name": "Pixel 8", "platform": "android"}}), conn)
check("pair ok -> res", r["kind"] == "res" and r["payload"]["profile"] == "monitor_control")
check("pair ok -> bearer issued", isinstance(r["payload"]["bearer"], str) and r["payload"]["bearer"])
check("pair ok -> expires_at iso", r["payload"]["expires_at"].endswith("Z"))
check("pair ok -> state Connected", conn.state == "Connected")
bearer = r["payload"]["bearer"]

r = router.handle(req("pair", {"token": tok}), ConnState())
check("pairing token is single-use (replay -> AUTH_FAILED)", r["payload"]["code"] == "AUTH_FAILED")

# optional additive device fields (location) are captured; last_seen initialized
tok2 = st.mint_pairing_token()
router.handle(req("pair", {"token": tok2, "device": {"name": "iPad", "location": "Berlin, DE"}}), ConnState())
ipad = [s for s in st.active_sessions() if s.device_name == "iPad"][0]
check("device.location captured on pair", ipad.location == "Berlin, DE")
check("last_seen initialized on pair", ipad.last_seen > 0)
prev_seen = ipad.last_seen
st.touch(ipad.bearer)
check("touch advances last_seen (>=)", ipad.last_seen >= prev_seen)

# --- auth ------------------------------------------------------------------
r = router.handle(req("send_keys", {"pane_id": "%1", "keys": "hi"}, auth=None), ConnState())
check("command without bearer -> AUTH_FAILED", r["payload"]["code"] == "AUTH_FAILED")
r = router.handle(req("send_keys", {"pane_id": "%1", "keys": "hi"}, auth="nope"), ConnState())
check("command with bad bearer -> AUTH_FAILED", r["payload"]["code"] == "AUTH_FAILED")

# --- allowed dispatch ------------------------------------------------------
mon.calls.clear()
r = router.handle(req("send_keys", {"pane_id": "%1", "keys": "hi", "literal": True}, auth=bearer), ConnState())
check("send_keys allowed -> res ok", r["kind"] == "res" and r["payload"]["ok"] is True)
check("send_keys reached monitor literally", ("send_keys", "%1", "hi", True) in mon.calls)
r = router.handle(req("forward_key", {"pane_id": "%1", "key": "up"}, auth=bearer), ConnState())
check("forward_key allowed -> res ok", r["payload"]["ok"] is True)
check("forward_key reached monitor", ("forward_key", "%1", "up") in mon.calls)
r = router.handle(req("send_keys", {"pane_id": "%1"}, auth=bearer), ConnState())
check("send_keys missing keys -> BAD_PAYLOAD", r["payload"]["code"] == "BAD_PAYLOAD")

# --- gating ----------------------------------------------------------------
ro = st.issue_bearer("read_only")
r = router.handle(req("send_keys", {"pane_id": "%1", "keys": "x"}, auth=ro.bearer), ConnState())
check("read_only send_keys -> PERMISSION_DENIED", r["payload"]["code"] == "PERMISSION_DENIED")
check("PERMISSION_DENIED names required_profile",
      r["payload"]["detail"]["required_profile"] == "monitor_control")
r = router.handle(req("task_detail", {"task_id": "1"}, auth=ro.bearer), ConnState())
check("read_only task_detail allowed (not PERMISSION_DENIED)",
      r["payload"].get("code") != "PERMISSION_DENIED")

# --- confirm pull-model ----------------------------------------------------
full = st.issue_bearer("full")
mon.calls.clear()
r = router.handle(req("kill_pane", {"pane_id": "%2"}, auth=full.bearer), ConnState())
check("kill_pane unconfirmed -> confirm_required", r["payload"].get("confirm_required") is True)
check("kill_pane unconfirmed does NOT execute", not any(c[0] == "kill_pane" for c in mon.calls))
r = router.handle(req("kill_pane", {"pane_id": "%2", "confirmed": True}, auth=full.bearer), ConnState())
check("kill_pane confirmed -> executes", ("kill_pane", "%2") in mon.calls and r["payload"]["ok"] is True)

# --- deferred + unknown verbs ----------------------------------------------
r = router.handle(req("pick_next_sibling", {"pane_id": "%1"}, auth=full.bearer), ConnState())
check("pick_next_sibling -> UNKNOWN_VERB(deferred)",
      r["payload"]["code"] == "UNKNOWN_VERB" and r["payload"]["detail"]["reason"] == "deferred")
r = router.handle(req("frobnicate", {}, auth=full.bearer), ConnState())
check("unknown verb -> UNKNOWN_VERB", r["payload"]["code"] == "UNKNOWN_VERB")

# --- session verbs ---------------------------------------------------------
conn = ConnState()
r = router.handle(req("bye", auth=full.bearer), conn)
check("bye -> ok + close", r["payload"]["ok"] is True and conn.close_requested is True)
r = router.handle(req("send_enter", {"pane_id": "%1"}, auth=full.bearer), ConnState())
check("revoked bearer (post-bye) -> AUTH_FAILED", r["payload"]["code"] == "AUTH_FAILED")

# --- malformed envelopes ---------------------------------------------------
r = router.handle("not-an-object", ConnState())
check("non-object frame -> BAD_PAYLOAD", r["payload"]["code"] == "BAD_PAYLOAD")
r = router.handle({"v": 1, "id": "x", "kind": "push", "verb": "pair"}, ConnState())
check("non-req kind -> BAD_PAYLOAD", r["payload"]["code"] == "BAD_PAYLOAD")

# --- verb registry covers every profile verb -------------------------------
for name in gate.names():
    for v in gate.get(name).allowed_verbs:
        check(f"profile verb '{v}' is registered", v in KNOWN_VERBS)

# --- TLS fingerprint determinism (skipped if openssl absent) ---------------
if shutil.which("openssl"):
    import tempfile
    import tls
    with tempfile.TemporaryDirectory() as d:
        cm = tls.CertManager(Path(d))
        fp1 = cm.fingerprint()
        fp2 = tls.CertManager(Path(d)).fingerprint()  # reuses the same cert
        check("tls fingerprint deterministic + unpadded", fp1 == fp2 and "=" not in fp1 and len(fp1) > 20)
else:
    print("ok - tls fingerprint check skipped (openssl not found)")

print(f"\nALL PASSED ({PASS} checks)")
PYEOF