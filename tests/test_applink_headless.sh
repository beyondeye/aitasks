#!/usr/bin/env bash
# test_applink_headless.sh — unit/contract + launcher-routing tests for the
# applink headless runner (t822_13).
#
# Group A (no socket): the no-Textual import contract, render_pairing_block
# purity, headless.py --help, and the "validate --profile before any side
# effect" ordering (proved with construction spies).
# Group B (launcher): `ait monitor --headless-for-applink --help` routes to the
# headless runner, forwards its flags, and does NOT fall through to the Textual
# monitor TUI.
# Run: bash tests/test_applink_headless.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

# Headless needs the applink runtime deps (NOT textual — that's the point).
if ! "$PYTHON" -c "import websockets, msgpack, segno" 2>/dev/null; then
    echo "SKIP: websockets/msgpack/segno not installed (run 'ait setup' first)"
    exit 0
fi

# ---- Group A: pure/contract assertions (no socket) -------------------------
"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import asyncio
import io
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))


def check(label, cond):
    assert cond, f"FAIL: {label}"
    print(f"ok - {label}")


# A1. No-Textual contract: importing the runner must not pull in Textual.
import applink.headless as h
check("import applink.headless does not load textual", "textual" not in sys.modules)

# A2. render_pairing_block is pure and correct.
uri = "applink://192.168.1.5:8765/pair?t=TOK&fp=FP"
noqr = h.render_pairing_block(uri, "FP", show_qr=False)
full = h.render_pairing_block(uri, "FP", show_qr=True)
check("render contains the pairing URI", uri in noqr)
check("render contains the fingerprint", "FP" in noqr)
check("show_qr=False omits the QR block", "\n\n" not in noqr.rstrip("\n"))
check("show_qr=True appends a (longer) QR block", isinstance(full, str) and len(full) > len(noqr))

# A4. Unknown --profile is rejected BEFORE any side effect. Spy on the module
# globals: if serve() constructs either collaborator for a bad profile, the spy
# raises and the test fails. Reaching return code 2 with no exception proves the
# cert was never generated, no token minted, and no socket opened.
class _Boom:
    def __init__(self, *a, **k):
        raise AssertionError("must not construct on bad profile")

orig_cert, orig_sessions = h.CertManager, h.SessionTable
h.CertManager = _Boom
h.SessionTable = _Boom
try:
    rc = asyncio.run(h.serve(port=0, profile="does-not-exist-xyz", show_qr=False))
finally:
    h.CertManager, h.SessionTable = orig_cert, orig_sessions
check("bad --profile returns exit code 2", rc == 2)
check("bad --profile constructs neither CertManager nor SessionTable", True)  # no spy raised

print("\nGroup A PASSED")
PYEOF

# A3. headless.py --help exits 0 and lists the headless-specific flags.
help_out="$("$PYTHON" "$PROJECT_DIR/.aitask-scripts/applink/headless.py" --help)"
for flag in -- "--port" "--profile" "--no-qr"; do
    [[ "$flag" == "--" ]] && continue
    echo "$help_out" | grep -q -- "$flag" || { echo "FAIL: headless --help missing $flag"; exit 1; }
done
echo "ok - headless.py --help exits 0 and lists --port/--profile/--no-qr"

# ---- Group B: launcher routing (the actual entry point) --------------------
if ! command -v tmux >/dev/null 2>&1 || ! "$PYTHON" -c "import yaml" 2>/dev/null; then
    echo "SKIP (Group B): tmux or pyyaml missing"
    echo "ALL PASSED (Group A only)"
    exit 0
fi

route_out="$(bash "$PROJECT_DIR/.aitask-scripts/aitask_monitor.sh" --headless-for-applink --help 2>&1)"
echo "$route_out" | grep -q -- "--no-qr" \
    || { echo "FAIL: launcher did not forward headless flags (--no-qr absent)"; exit 1; }
echo "ok - launcher forwards headless flags (routed to headless.py)"

if echo "$route_out" | grep -qiE "tmux session name|--interval"; then
    echo "FAIL: launcher fell through to the Textual monitor TUI help"
    exit 1
fi
echo "ok - launcher did not fall through to the Textual TUI (Textual startup skipped)"

echo ""
echo "ALL PASSED"
