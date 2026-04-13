#!/usr/bin/env bash
# test_agentcrew_pythonpath.sh - Regression test for t536.
#
# Ensures that the agentcrew Python CLIs invoked via ait wrappers do not fail
# with ModuleNotFoundError when called from a cwd other than the repo root.
# The bug: agentcrew_status.py used `from agentcrew.agentcrew_utils import ...`
# without prepending its parent directory to sys.path, so Python could not
# locate the `agentcrew` package regardless of cwd.
#
# Run: bash tests/test_agentcrew_pythonpath.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ORIG_DIR="$(pwd)"

# File-based counters (work across subshells)
COUNTER_FILE="$(mktemp "${TMPDIR:-/tmp}/ait_test_counters_XXXXXX")"
echo "0 0 0" > "$COUNTER_FILE"
trap 'rm -f "$COUNTER_FILE"; cd "$ORIG_DIR"' EXIT

_inc_pass() {
    local p f t
    read -r p f t < "$COUNTER_FILE"
    echo "$((p + 1)) $f $((t + 1))" > "$COUNTER_FILE"
}
_inc_fail() {
    local p f t
    read -r p f t < "$COUNTER_FILE"
    echo "$p $((f + 1)) $((t + 1))" > "$COUNTER_FILE"
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    if echo "$actual" | grep -qF -- "$unexpected"; then
        _inc_fail
        echo "FAIL: $desc (did not expect '$unexpected' in output)"
        echo "---- output ----"
        echo "$actual"
        echo "----------------"
    else
        _inc_pass
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    if echo "$actual" | grep -qF -- "$expected"; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: $desc (expected output containing '$expected')"
        echo "---- output ----"
        echo "$actual"
        echo "----------------"
    fi
}

run_from() {
    local cwd="$1"
    shift
    ( cd "$cwd" && "$@" 2>&1 ) || true
}

# --- Tests ---

echo "=== Test: agentcrew_status.py import (t536 regression) ==="

# 1. From repo root — existing behavior.
output="$(run_from "$PROJECT_DIR" "$PROJECT_DIR/ait" crew status --crew __nonexistent_t536__ list)"
assert_not_contains "repo root: no ModuleNotFoundError" "ModuleNotFoundError" "$output"
assert_not_contains "repo root: no missing agentcrew module" "No module named 'agentcrew'" "$output"
assert_contains    "repo root: Python body executed (crew not found error)" "Crew '__nonexistent_t536__' not found" "$output"

# 2. From /tmp — previously broken (t536).
tmpcwd="$(mktemp -d "${TMPDIR:-/tmp}/t536_cwd_XXXXXX")"
output="$(run_from "$tmpcwd" "$PROJECT_DIR/ait" crew status --crew __nonexistent_t536__ list)"
rmdir "$tmpcwd" 2>/dev/null || true
assert_not_contains "tempdir: no ModuleNotFoundError" "ModuleNotFoundError" "$output"
assert_not_contains "tempdir: no missing agentcrew module" "No module named 'agentcrew'" "$output"
assert_contains    "tempdir: Python body executed (crew not found error)" "Crew '__nonexistent_t536__' not found" "$output"

# 3. From / (filesystem root) — stress case.
output="$(run_from "/" "$PROJECT_DIR/ait" crew status --crew __nonexistent_t536__ list)"
assert_not_contains "fs root: no ModuleNotFoundError" "ModuleNotFoundError" "$output"
assert_contains    "fs root: Python body executed (crew not found error)" "Crew '__nonexistent_t536__' not found" "$output"

# 4. Sanity: agentcrew_runner is unaffected and still works.
output="$(run_from "$PROJECT_DIR" "$PROJECT_DIR/ait" crew runner --help)"
assert_not_contains "runner --help: no ModuleNotFoundError" "ModuleNotFoundError" "$output"

# --- Summary ---

read -r PASSED FAILED TOTAL < "$COUNTER_FILE"
echo ""
echo "=========================================="
echo "Test Summary: $PASSED/$TOTAL passed"
if [[ $FAILED -gt 0 ]]; then
    echo "FAILED: $FAILED test(s) failed"
    exit 1
fi
echo "All tests passed!"
exit 0
