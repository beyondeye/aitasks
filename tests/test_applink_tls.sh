#!/usr/bin/env bash
# test_applink_tls.sh — TLS hardening + at-rest permissions for applink (t985).
#
# Covers build_ssl_context (TLS 1.2 floor + AEAD cipher pinning) and the
# secure-dir / key-permission behaviour of ensure_cert. Run:
#   bash tests/test_applink_tls.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

if ! command -v openssl >/dev/null 2>&1; then
    echo "SKIP: openssl not found (applink TLS cert generation needs it)"
    exit 0
fi

"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import ssl
import stat
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

import tls

PASS = 0
def check(label, cond):
    global PASS
    assert cond, f"FAIL: {label}"
    PASS += 1
    print(f"ok - {label}")

with tempfile.TemporaryDirectory() as d:
    cert_dir = Path(d) / "applink_sessions"
    cert_path, key_path = tls.ensure_cert(cert_dir)

    # --- at-rest permissions ----------------------------------------------
    check("ensure_cert created cert + key", cert_path.is_file() and key_path.is_file())
    # POSIX-only mode asserts (skip on filesystems without mode bits).
    if hasattr(stat, "S_IMODE"):
        dir_mode = stat.S_IMODE(cert_dir.stat().st_mode)
        key_mode = stat.S_IMODE(key_path.stat().st_mode)
        check("runtime dir is owner-only (0o700)", dir_mode == 0o700)
        check("private key is owner-only (0o600)", key_mode == 0o600)
        check("private key not group/other readable", key_mode & 0o077 == 0)

    # --- TLS context hardening --------------------------------------------
    ctx = tls.build_ssl_context(cert_path, key_path)
    check("min TLS version is 1.2 (1.0/1.1 dropped)", ctx.minimum_version == ssl.TLSVersion.TLSv1_2)
    # set_ciphers restricted to ECDHE/AEAD — no plain-RSA-kx or NULL suites.
    suites = {c["name"] for c in ctx.get_ciphers()}
    check("all negotiable 1.2 suites are ECDHE (forward secret)",
          all("ECDHE" in n or "TLS_" in n for n in suites))
    check("no NULL / aNULL suites offered",
          not any("NULL" in n.upper() for n in suites))

    # --- idempotent reuse keeps the fingerprint stable --------------------
    fp1 = tls.fingerprint(cert_path)
    cert_path2, _ = tls.ensure_cert(cert_dir)
    check("ensure_cert idempotent (same cert reused)", cert_path2 == cert_path)
    check("fingerprint stable across ensure", tls.fingerprint(cert_path2) == fp1)

print(f"\nALL PASSED ({PASS} checks)")
PYEOF
