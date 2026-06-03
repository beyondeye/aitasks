#!/usr/bin/env bash
# test_version_checks.sh - Tests for bash version check functions.
# (Earlier check_python_version tests removed at t695_4 — function deleted as
# dead code after t695_2; python resolution now lives in lib/python_resolve.sh
# and is exercised by tests/test_python_resolution_fallback.sh.)
# Run: bash tests/test_version_checks.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

# Shared assertion helpers (see tests/lib/asserts.sh)
. "$PROJECT_DIR/tests/lib/asserts.sh"


# Source setup script for function access
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
set +euo pipefail

echo "=== Version Check Tests ==="
echo ""

# --- Test 1: check_bash_version passes on current shell ---
echo "--- Test 1: check_bash_version on current shell ---"

# Current shell should be bash 4+ (CI and most dev machines)
OS="linux"
output="$(check_bash_version 2>&1)"
rc=$?

if [[ "${BASH_VERSINFO[0]}" -ge 4 ]]; then
    assert_eq "check_bash_version returns 0 on bash 4+" "0" "$rc"
    assert_contains_ci "Reports meets minimum" "meets minimum" "$output"
else
    # If somehow running under bash 3.2, it should warn
    assert_contains_ci "Warns about old bash" "requires 4.0" "$output"
fi

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
