#!/usr/bin/env bash
# test_format_yaml_list.sh - Tests for format_yaml_list() in lib/task_utils.sh
#
# Covers empty, single-entry, and multi-entry cases including the shapes
# produced by the depends/children, labels, and file_references fields.
#
# Run: bash tests/test_format_yaml_list.sh

set -e

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/task_utils.sh
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"

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

# Empty input
assert_eq "empty -> []"                "[]"                   "$(format_yaml_list "")"

# Single entry
assert_eq "single alpha -> [a]"        "[a]"                  "$(format_yaml_list "a")"
assert_eq "single numeric -> [42]"     "[42]"                 "$(format_yaml_list "42")"
assert_eq "single child id"            "[t85_2]"              "$(format_yaml_list "t85_2")"

# Multi-entry (depends / children shape)
assert_eq "two numeric entries"        "[1, 2]"               "$(format_yaml_list "1,2")"
assert_eq "three numeric entries"      "[1, 3, 5]"            "$(format_yaml_list "1,3,5")"

# Labels shape
assert_eq "labels multi"               "[ui, backend]"        "$(format_yaml_list "ui,backend")"

# File references shape (colon + range)
assert_eq "file refs with colon/range" "[foo.py, bar.py:10-20]" "$(format_yaml_list "foo.py,bar.py:10-20")"

# Round-trip: parse_yaml_list inverse -> format_yaml_list reproduces inline form
assert_eq "round-trip via parse/format" "[1, 2, 3]" \
    "$(format_yaml_list "$(parse_yaml_list "[1, 2, 3]")")"

# Syntax check the touched library
TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: syntax check task_utils.sh"
fi

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
