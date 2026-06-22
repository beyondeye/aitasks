#!/usr/bin/env bash
# test_applink_smoke.sh - Smoke test for applink TUI app.
# Run: bash tests/test_applink_smoke.sh
#
# Constructs the ApplinkApp without entering the event loop. Catches
# import errors and basic constructor failures (e.g. missing segno dep,
# broken tui_switcher import, malformed Textual BINDINGS).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APPLINK_APP="$PROJECT_DIR/.aitask-scripts/applink/applink_app.py"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

PASS=0
FAIL=0
TOTAL=0

run_smoke() {
    local desc="$1"
    TOTAL=$((TOTAL + 1))
    local stderr_file
    stderr_file=$(mktemp)
    if "$PYTHON" "$APPLINK_APP" --smoke 2>"$stderr_file"; then
        if [[ -s "$stderr_file" ]]; then
            FAIL=$((FAIL + 1))
            echo "FAIL: $desc — unexpected stderr:"
            cat "$stderr_file"
        else
            PASS=$((PASS + 1))
        fi
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc — non-zero exit"
        cat "$stderr_file"
    fi
    rm -f "$stderr_file"
}

# Skip when the venv lacks the runtime deps (e.g. fresh clone without `ait setup`).
if ! "$PYTHON" -c "import textual, segno" 2>/dev/null; then
    echo "SKIP: textual or segno not installed (run 'ait setup' first)"
    exit 0
fi

run_smoke "applink_app --smoke exits 0 without stderr"

# Construction spy: the --smoke path must perform no firewall I/O. The doctor
# (firewall_doctor.diagnose, which spawns systemctl/ip) must run ONLY in the
# live mount worker, never at construction. Patch it to a tripwire and assert
# the spy never fires through main(["--smoke"]) (t1043).
TOTAL=$((TOTAL + 1))
spy_out=$(mktemp)
if "$PYTHON" - "$PROJECT_DIR" >"$spy_out" 2>&1 <<'PYEOF'
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

import firewall_doctor
import applink_app

called = {"diagnose": False}
firewall_doctor.diagnose = lambda *a, **k: called.__setitem__("diagnose", True)

rc = applink_app.main(["--smoke"])
assert rc == 0, f"smoke main returned {rc}"
assert not called["diagnose"], "firewall_doctor.diagnose was called on --smoke path"
print("ok - --smoke performs no firewall I/O")
PYEOF
then
    PASS=$((PASS + 1))
    cat "$spy_out"
else
    FAIL=$((FAIL + 1))
    echo "FAIL: --smoke construction spy"
    cat "$spy_out"
fi
rm -f "$spy_out"

echo ""
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
