#!/usr/bin/env bash
# test_applink_sessions.sh — at-rest permissions for the bearer session table (t985).
#
# A persisted sessions.json holds live bearer secrets; it must be owner-only,
# and so must the runtime dir that contains it. Run:
#   bash tests/test_applink_sessions.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import stat
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

import sessions as S

PASS = 0
def check(label, cond):
    global PASS
    assert cond, f"FAIL: {label}"
    PASS += 1
    print(f"ok - {label}")

with tempfile.TemporaryDirectory() as d:
    sdir = Path(d) / "applink_sessions"
    table = S.SessionTable(sdir, persist=True)
    sess = table.issue_bearer("monitor_control", device_name="Pixel")  # triggers _save
    spath = sdir / S.SESSIONS_FILENAME

    check("sessions.json persisted", spath.is_file())
    check("bearer present in table", table.lookup(sess.bearer) is not None)

    if hasattr(stat, "S_IMODE"):
        file_mode = stat.S_IMODE(spath.stat().st_mode)
        dir_mode = stat.S_IMODE(sdir.stat().st_mode)
        check("sessions.json is owner-only (0o600)", file_mode == 0o600)
        check("sessions.json not group/other readable", file_mode & 0o077 == 0)
        check("runtime dir is owner-only (0o700)", dir_mode == 0o700)

    # A second mutation (revoke) re-saves and must preserve the locked-down mode.
    table.revoke(sess.bearer)
    if hasattr(stat, "S_IMODE") and spath.is_file():
        check("sessions.json stays 0o600 after re-save",
              stat.S_IMODE(spath.stat().st_mode) == 0o600)

print(f"\nALL PASSED ({PASS} checks)")
PYEOF
