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

echo ""
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
