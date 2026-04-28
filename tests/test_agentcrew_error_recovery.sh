#!/usr/bin/env bash
# test_agentcrew_error_recovery.sh - Regression test for t653_3.
#
# Verifies the extended AGENT_TRANSITIONS["Error"] = ["Waiting","Running","Completed"]:
# - Error -> Completed succeeds (already allowed before this task; pinning it).
# - Error -> Running succeeds (new transition added in this task).
# - Error -> Aborted still fails (Aborted intentionally terminal).
#
# Run: bash tests/test_agentcrew_error_recovery.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ORIG_DIR="$(pwd)"

# shellcheck source=lib/venv_python.sh
. "$SCRIPT_DIR/lib/venv_python.sh"

PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "FAIL: $1"; }

TMPROOT="$(mktemp -d "${TMPDIR:-/tmp}/aitask_test_error_recovery_XXXXXX")"
trap 'cd "$ORIG_DIR"; rm -rf "$TMPROOT"' EXIT

cd "$TMPROOT"
git init -q
git config user.email "test@example.com"
git config user.name "Test User"
git commit -q --allow-empty -m "init"

CREW_DIR=".aitask-crews/crew-test_crew"
mkdir -p "$CREW_DIR"

cat > "$CREW_DIR/_crew_status.yaml" <<EOF
status: Running
updated_at: 2026-04-26 00:00:00
progress: 0
EOF

seed_error() {
    cat > "$CREW_DIR/foo_status.yaml" <<EOF
agent_name: foo
status: Error
EOF
    git add -A >/dev/null 2>&1
    git commit -q -m "seed Error" >/dev/null 2>&1 || true
}

run_status_set() {
    "$AITASK_PYTHON" "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_status.py" "$@" >/dev/null 2>&1
}

run_status_set_capture_rc() {
    "$AITASK_PYTHON" "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_status.py" "$@" >/dev/null 2>&1
    echo $?
}

# --- Test 1: Error -> Completed allowed (regression pin) ---
seed_error
run_status_set --crew test_crew --agent foo set --status Completed || true
if grep -q "^status: Completed" "$CREW_DIR/foo_status.yaml"; then
    pass "Error -> Completed allowed"
else
    fail "Error -> Completed rejected"
fi

# --- Test 2: Error -> Running allowed (new transition in this task) ---
seed_error
run_status_set --crew test_crew --agent foo set --status Running || true
if grep -q "^status: Running" "$CREW_DIR/foo_status.yaml"; then
    pass "Error -> Running allowed (new transition)"
else
    fail "Error -> Running rejected"
fi

# --- Test 3: Error -> Aborted still rejected ---
seed_error
RC="$(run_status_set_capture_rc --crew test_crew --agent foo set --status Aborted)"
if [[ "$RC" -ne 0 ]]; then
    pass "Error -> Aborted correctly rejected (exit=$RC)"
else
    fail "Error -> Aborted should have been rejected but exited 0"
fi
# Confirm status was NOT mutated to Aborted
if grep -q "^status: Error" "$CREW_DIR/foo_status.yaml"; then
    pass "rejected transition left status as Error"
else
    fail "rejected transition mutated status anyway"
fi

# --- Test 4: Error -> Waiting still works (the original recovery path) ---
seed_error
run_status_set --crew test_crew --agent foo set --status Waiting || true
if grep -q "^status: Waiting" "$CREW_DIR/foo_status.yaml"; then
    pass "Error -> Waiting still allowed (original recovery path)"
else
    fail "Error -> Waiting rejected"
fi

# --- Summary ---
TOTAL=$((PASS + FAIL))
echo ""
echo "=========================================="
echo "Test Summary: $PASS/$TOTAL passed"
if [[ $FAIL -gt 0 ]]; then
    echo "FAILED: $FAIL test(s) failed"
    exit 1
fi
echo "All tests passed!"
exit 0
