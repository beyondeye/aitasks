#!/usr/bin/env bash
# test_task_levels.sh - Tests for the single-source-of-truth task level enum
# (t911). Covers the bash helpers in lib/task_utils.sh:
#   - is_valid_task_level accepts high/medium/low, rejects everything else
#     (including the empty string and wrong-case "High")
#   - task_levels_lines / task_levels_lines_asc emit the exact ordered lists
# Also verifies the Python mirror (lib/task_levels.py) agrees on the value set.
#
# Run: bash tests/test_task_levels.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.aitask-scripts" && pwd)"
# shellcheck source=../.aitask-scripts/lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

PASS=0
FAIL=0
TOTAL=0

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  expected: $expected"
        echo "  actual:   $actual"
    fi
}

assert_valid() {
    local val="$1"
    TOTAL=$((TOTAL + 1))
    if is_valid_task_level "$val"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: is_valid_task_level should accept '$val'"
    fi
}

assert_invalid() {
    local val="$1"
    TOTAL=$((TOTAL + 1))
    if is_valid_task_level "$val"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: is_valid_task_level should reject '$val'"
    else
        PASS=$((PASS + 1))
    fi
}

# --- Membership ---
assert_valid "high"
assert_valid "medium"
assert_valid "low"
assert_invalid ""
assert_invalid "med"
assert_invalid "urgent"
assert_invalid "High"
assert_invalid "high medium"

# --- Ordered emitters ---
assert_eq "task_levels_lines order" $'high\nmedium\nlow' "$(task_levels_lines)"
assert_eq "task_levels_lines_asc order" $'low\nmedium\nhigh' "$(task_levels_lines_asc)"

# --- Constant ---
assert_eq "TASK_LEVELS value" "high medium low" "$TASK_LEVELS"

# --- Python mirror agrees on the value set ---
py_levels="$(cd "$SCRIPT_DIR" && python3 -c \
    'import sys; sys.path.insert(0, "lib"); import task_levels; print(" ".join(sorted(task_levels.LEVELS)))')"
bash_levels="$(printf '%s\n' $TASK_LEVELS | sort | tr '\n' ' ' | sed 's/ $//')"
assert_eq "Python LEVELS mirrors bash TASK_LEVELS" "$bash_levels" "$py_levels"

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
