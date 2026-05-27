#!/usr/bin/env bash
# test_xdeps_fold_warn.sh - Verify aitask_fold_validate.sh warns when
# folding a task whose xdeps / xdeprepo would silently drop (t832_3).
#
# WARNING lines are non-blocking: VALID still emits, and existing callers
# (auto_merge in aitask_create.sh) ignore unknown line types.
#
# Run: bash tests/test_xdeps_fold_warn.sh

set -e

SCRIPT_DIR_T="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR_T/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

assert_contains() {
    local desc="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if grep -qF -- "$needle" <<< "$haystack"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  expected substring: $needle"
        echo "  actual: $haystack"
    fi
}

assert_not_contains() {
    local desc="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if grep -qF -- "$needle" <<< "$haystack"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (forbidden substring present)"
        echo "  forbidden: $needle"
        echo "  actual: $haystack"
    else
        PASS=$((PASS + 1))
    fi
}

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

mkdir -p "$TMPROOT/aitasks"

write_task() {
    local file="$1"
    shift
    {
        echo "---"
        echo "priority: medium"
        echo "effort: medium"
        echo "issue_type: feature"
        echo "status: Ready"
        echo "labels: []"
        for line in "$@"; do echo "$line"; done
        echo "---"
        echo "body"
    } > "$file"
}

VALIDATE="$PROJECT_DIR/.aitask-scripts/aitask_fold_validate.sh"

# --- Case 1: foldee carries xdeps the primary lacks → WARNING -----------

write_task "$TMPROOT/aitasks/t100_primary.md"
write_task "$TMPROOT/aitasks/t101_foldee.md" \
    "xdeps: [1, 2_3]" \
    "xdeprepo: sister"

out=$(cd "$TMPROOT" && "$VALIDATE" --exclude-self 100 101 2>&1)
assert_contains "VALID still emitted for foldee 101" "VALID:101:" "$out"
assert_contains "WARNING emitted for xdeps loss"     "WARNING:101:xdeps_loss" "$out"
assert_contains "WARNING includes the xdeprepo"      "sister" "$out"

# --- Case 2: foldee and primary share xdeprepo + foldee's xdeps ⊆ primary's → no WARNING

write_task "$TMPROOT/aitasks/t200_primary.md" \
    "xdeps: [1, 2_3, 5]" \
    "xdeprepo: sister"
write_task "$TMPROOT/aitasks/t201_foldee.md" \
    "xdeps: [1, 2_3]" \
    "xdeprepo: sister"

out=$(cd "$TMPROOT" && "$VALIDATE" --exclude-self 200 201 2>&1)
assert_contains    "VALID still emitted"            "VALID:201:"            "$out"
assert_not_contains "no WARNING when superset holds" "WARNING:201:xdeps_loss" "$out"

# --- Case 3: foldee w/o xdeps → no WARNING regardless of primary --------

write_task "$TMPROOT/aitasks/t300_primary.md"
write_task "$TMPROOT/aitasks/t301_foldee.md"

out=$(cd "$TMPROOT" && "$VALIDATE" --exclude-self 300 301 2>&1)
assert_contains    "VALID still emitted"     "VALID:301:"            "$out"
assert_not_contains "plain foldee no WARNING" "WARNING:301"          "$out"

# --- Case 4: foldee has xdeps but no --exclude-self → no WARNING --------
# (backward compatibility: callers that don't pass --exclude-self get the
# old VALID/INVALID-only contract)

write_task "$TMPROOT/aitasks/t401_foldee.md" \
    "xdeps: [9]" \
    "xdeprepo: sister"

out=$(cd "$TMPROOT" && "$VALIDATE" 401 2>&1)
assert_contains    "VALID still emitted"            "VALID:401:" "$out"
assert_not_contains "no WARNING without --exclude-self" "WARNING:401" "$out"

# --- Summary ------------------------------------------------------------

echo
echo "=========================================="
echo "Tests: $TOTAL  Passed: $PASS  Failed: $FAIL"
echo "=========================================="

[[ "$FAIL" -eq 0 ]]
