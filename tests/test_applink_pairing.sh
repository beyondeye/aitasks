#!/usr/bin/env bash
# test_applink_pairing.sh — unit test for the QR pairing-URI builder (t822_5).
#
# Confirms build_pairing_uri() appends the optional &name=<urlencoded(hostname)>
# query parameter per aidocs/applink/protocol.md §Pairing flow: present and
# correctly percent-encoded when a hostname is given, absent (additive/optional)
# when it is not. pairing.py imports only stdlib (no textual/segno), so this test
# needs no dependency-skip guard.
# Run: bash tests/test_applink_pairing.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import socket
import sys
from pathlib import Path
from urllib.parse import quote

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

from pairing import build_pairing_uri


def check(label, cond):
    assert cond, f"FAIL: {label}"
    print(f"ok - {label}")


# 1. name= present and matches urlencoded(socket.gethostname()) — the literal AC.
host = socket.gethostname()
uri = build_pairing_uri(token="tok", ip="192.168.1.5", port=8765,
                        fingerprint="fp", hostname=host)
expected = f"name={quote(host, safe='')}"
check("name= matches urlencoded(socket.gethostname())", expected in uri)

# 2. Unsafe characters (space, non-ASCII) are percent-encoded via quote(safe='').
weird = "my host.örg"
uri_weird = build_pairing_uri(token="tok", ip="10.0.0.1", port=8765,
                              fingerprint="fp", hostname=weird)
check("space and non-ASCII percent-encoded",
      f"name={quote(weird, safe='')}" in uri_weird)
check("encoded form is literally name=my%20host.%C3%B6rg",
      "name=my%20host.%C3%B6rg" in uri_weird)

# 3. Optional / additive: no hostname -> no name= param (older clients unaffected).
base = "applink://192.168.1.5:8765/pair?t=tok&fp=fp"
check("hostname=None omits name=",
      build_pairing_uri(token="tok", ip="192.168.1.5", port=8765,
                        fingerprint="fp", hostname=None) == base)
check("hostname='' omits name=",
      build_pairing_uri(token="tok", ip="192.168.1.5", port=8765,
                        fingerprint="fp", hostname="") == base)
check("default (no hostname kwarg) omits name=",
      build_pairing_uri(token="tok", ip="192.168.1.5", port=8765,
                        fingerprint="fp") == base)

print("\nALL PASSED")
PYEOF
