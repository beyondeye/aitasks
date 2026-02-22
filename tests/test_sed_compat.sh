#!/usr/bin/env bash
# test_sed_compat.sh - Tests for macOS/BSD sed compatibility fixes (t209)
# Run: bash tests/test_sed_compat.sh

set -e

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"
# Set SCRIPT_DIR so task_utils.sh can find terminal_compat.sh
SCRIPT_DIR="$PROJECT_DIR/aiscripts"
source "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh"
source "$PROJECT_DIR/aiscripts/lib/task_utils.sh"

PASS=0
FAIL=0
TOTAL=0
TMPDIR_TEST=""

# --- Test helpers ---

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  expected: $(echo "$expected" | head -3)"
        echo "  actual:   $(echo "$actual" | head -3)"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected to contain '$expected')"
        echo "  actual: $(echo "$actual" | head -3)"
    fi
}

setup_tmpdir() {
    TMPDIR_TEST=$(mktemp -d)
}

cleanup_tmpdir() {
    if [[ -n "$TMPDIR_TEST" && -d "$TMPDIR_TEST" ]]; then
        rm -rf "$TMPDIR_TEST"
    fi
}

trap cleanup_tmpdir EXIT

echo "=== sed Compatibility Tests (t209) ==="
echo ""

# ============================================================
# Test 1: sed_inplace() basic substitution
# ============================================================
echo "--- sed_inplace: basic substitution ---"

setup_tmpdir
echo "status: Ready" > "$TMPDIR_TEST/test1.txt"
sed_inplace "s/^status: .*/status: Done/" "$TMPDIR_TEST/test1.txt"
result=$(cat "$TMPDIR_TEST/test1.txt")
assert_eq "sed_inplace s/ substitution" "status: Done" "$result"
cleanup_tmpdir

# ============================================================
# Test 2: sed_inplace() with multiple lines
# ============================================================
echo "--- sed_inplace: multi-line file ---"

setup_tmpdir
cat > "$TMPDIR_TEST/test2.txt" <<'EOF'
---
status: Implementing
updated_at: 2026-01-01 00:00
labels: [test]
---
Some content here.
EOF
sed_inplace "s/^status: .*/status: Done/" "$TMPDIR_TEST/test2.txt"
sed_inplace "s/^updated_at: .*/updated_at: 2026-02-22 12:00/" "$TMPDIR_TEST/test2.txt"
assert_contains "status updated" "status: Done" "$(cat "$TMPDIR_TEST/test2.txt")"
assert_contains "updated_at updated" "updated_at: 2026-02-22 12:00" "$(cat "$TMPDIR_TEST/test2.txt")"
assert_contains "labels preserved" "labels: [test]" "$(cat "$TMPDIR_TEST/test2.txt")"
assert_contains "content preserved" "Some content here." "$(cat "$TMPDIR_TEST/test2.txt")"
cleanup_tmpdir

# ============================================================
# Test 3: awk append-after-line (replaces GNU sed /pattern/a)
# ============================================================
echo "--- awk append-after-line (archive pattern) ---"

setup_tmpdir
cat > "$TMPDIR_TEST/test3.txt" <<'EOF'
---
status: Done
updated_at: 2026-02-22 12:00
labels: [test]
---
EOF
timestamp="2026-02-22 12:00"
awk -v ts="$timestamp" '/^updated_at:/{print; print "completed_at: " ts; next}1' \
    "$TMPDIR_TEST/test3.txt" > "$TMPDIR_TEST/test3.txt.tmp" && mv "$TMPDIR_TEST/test3.txt.tmp" "$TMPDIR_TEST/test3.txt"
result=$(cat "$TMPDIR_TEST/test3.txt")
assert_contains "completed_at inserted" "completed_at: 2026-02-22 12:00" "$result"

# Verify order: updated_at then completed_at then labels
line_updated=$(grep -n "^updated_at:" "$TMPDIR_TEST/test3.txt" | head -1 | cut -d: -f1)
line_completed=$(grep -n "^completed_at:" "$TMPDIR_TEST/test3.txt" | head -1 | cut -d: -f1)
line_labels=$(grep -n "^labels:" "$TMPDIR_TEST/test3.txt" | head -1 | cut -d: -f1)
assert_eq "completed_at is right after updated_at" "$((line_updated + 1))" "$line_completed"
assert_eq "labels is after completed_at" "$((line_completed + 1))" "$line_labels"
cleanup_tmpdir

# ============================================================
# Test 4: awk append-after-line in pipe (create pattern)
# ============================================================
echo "--- awk append-after-line in pipe (create pattern) ---"

content="---
labels: [test, backend]
created_at: 2026-01-01
---"
children_yaml="[1, 2, 3]"
result=$(echo "$content" | awk -v line="children_to_implement: $children_yaml" '/^labels:/{print; print line; next}1')
assert_contains "children_to_implement inserted" "children_to_implement: [1, 2, 3]" "$result"
assert_contains "labels preserved" "labels: [test, backend]" "$result"

# Verify order
line_labels=$(echo "$result" | grep -n "^labels:" | head -1 | cut -d: -f1)
line_children=$(echo "$result" | grep -n "^children_to_implement:" | head -1 | cut -d: -f1)
assert_eq "children_to_implement right after labels" "$((line_labels + 1))" "$line_children"

# ============================================================
# Test 5: ${var^} uppercase first letter (replaces sed \U)
# ============================================================
echo "--- bash \${var^} capitalize (stats pattern) ---"

_w="feature"; assert_eq "capitalize feature" "Feature" "${_w^}"
_w="bug"; assert_eq "capitalize bug" "Bug" "${_w^}"
_w="performance"; assert_eq "capitalize performance" "Performance" "${_w^}"
_w="chore"; assert_eq "capitalize chore" "Chore" "${_w^}"
_w="documentation"; assert_eq "capitalize documentation" "Documentation" "${_w^}"
_w="already_upper"; assert_eq "capitalize already mixed" "Already_upper" "${_w^}"
_w=""; assert_eq "capitalize empty string" "" "${_w^}"

# ============================================================
# Test 6: awk trailing blank line trim (replaces complex sed)
# ============================================================
echo "--- awk trailing blank line trim (task_utils pattern) ---"

# Input with trailing blank lines
input="line 1
line 2

line 3


"
result=$(echo "$input" | sed '/./,$!d' | awk '{lines[NR]=$0} /[^[:space:]]/{last=NR} END{for(i=1;i<=last;i++) print lines[i]}')
expected="line 1
line 2

line 3"
assert_eq "trailing blanks removed, internal blank preserved" "$expected" "$result"

# Input with leading blank lines
input="

line 1
line 2"
result=$(echo "$input" | sed '/./,$!d' | awk '{lines[NR]=$0} /[^[:space:]]/{last=NR} END{for(i=1;i<=last;i++) print lines[i]}')
expected="line 1
line 2"
assert_eq "leading blanks removed" "$expected" "$result"

# Input with both leading and trailing blank lines
input="

content here

more content


"
result=$(echo "$input" | sed '/./,$!d' | awk '{lines[NR]=$0} /[^[:space:]]/{last=NR} END{for(i=1;i<=last;i++) print lines[i]}')
expected="content here

more content"
assert_eq "leading+trailing blanks removed, internal preserved" "$expected" "$result"

# ============================================================
# Test 7: sed_inplace does not corrupt file on error
# ============================================================
echo "--- sed_inplace: file preserved on no-match ---"

setup_tmpdir
echo "hello world" > "$TMPDIR_TEST/test7.txt"
sed_inplace "s/^nonexistent_pattern/replacement/" "$TMPDIR_TEST/test7.txt"
result=$(cat "$TMPDIR_TEST/test7.txt")
assert_eq "file unchanged when no match" "hello world" "$result"
cleanup_tmpdir

# ============================================================
# Test 8: Full archive_metadata_update simulation
# ============================================================
echo "--- Full archive metadata update simulation ---"

setup_tmpdir
cat > "$TMPDIR_TEST/task.md" <<'EOF'
---
priority: medium
effort: low
status: Implementing
labels: [test]
assigned_to: test@example.com
created_at: 2026-01-01 00:00
updated_at: 2026-01-01 00:00
---

Task description here.
EOF

# Simulate archive_metadata_update logic
timestamp="2026-02-22 15:30"
sed_inplace "s/^status: .*/status: Done/" "$TMPDIR_TEST/task.md"
sed_inplace "s/^updated_at: .*/updated_at: $timestamp/" "$TMPDIR_TEST/task.md"
if ! grep -q "^completed_at:" "$TMPDIR_TEST/task.md"; then
    awk -v ts="$timestamp" '/^updated_at:/{print; print "completed_at: " ts; next}1' \
        "$TMPDIR_TEST/task.md" > "$TMPDIR_TEST/task.md.tmp" && mv "$TMPDIR_TEST/task.md.tmp" "$TMPDIR_TEST/task.md"
fi

result=$(cat "$TMPDIR_TEST/task.md")
assert_contains "full sim: status=Done" "status: Done" "$result"
assert_contains "full sim: updated_at set" "updated_at: 2026-02-22 15:30" "$result"
assert_contains "full sim: completed_at inserted" "completed_at: 2026-02-22 15:30" "$result"
assert_contains "full sim: priority preserved" "priority: medium" "$result"
assert_contains "full sim: description preserved" "Task description here." "$result"

# Verify completed_at not duplicated on re-run
if ! grep -q "^completed_at:" "$TMPDIR_TEST/task.md"; then
    awk -v ts="$timestamp" '/^updated_at:/{print; print "completed_at: " ts; next}1' \
        "$TMPDIR_TEST/task.md" > "$TMPDIR_TEST/task.md.tmp" && mv "$TMPDIR_TEST/task.md.tmp" "$TMPDIR_TEST/task.md"
fi
count=$(grep -c "^completed_at:" "$TMPDIR_TEST/task.md")
assert_eq "full sim: completed_at not duplicated" "1" "$count"
cleanup_tmpdir

# ============================================================
# Test 9: portable_date basic formatting
# ============================================================
echo "--- portable_date: basic formatting ---"

result=$(portable_date -d "2026-01-15" +%Y-%m-%d)
assert_eq "portable_date formats date" "2026-01-15" "$result"

# ============================================================
# Test 10: portable_date epoch conversion
# ============================================================
echo "--- portable_date: epoch conversion ---"

epoch=$(portable_date -d "2026-01-01" +%s)
TOTAL=$((TOTAL + 1))
if [[ "$epoch" =~ ^[0-9]+$ ]] && [[ "$epoch" -gt 0 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: portable_date epoch conversion (got: '$epoch')"
fi

# ============================================================
# Test 11: portable_date day-of-week
# ============================================================
echo "--- portable_date: day of week ---"

# 2026-01-05 is a Monday
dow=$(portable_date -d "2026-01-05" +%u)
assert_eq "portable_date Monday=1" "1" "$dow"

# 2026-01-11 is a Sunday
dow=$(portable_date -d "2026-01-11" +%u)
assert_eq "portable_date Sunday=7" "7" "$dow"

# ============================================================
# Test 12: portable_date arithmetic
# ============================================================
echo "--- portable_date: date arithmetic ---"

result=$(portable_date -d "2026-01-10 - 3 days" +%Y-%m-%d)
assert_eq "portable_date subtract 3 days" "2026-01-07" "$result"

result=$(portable_date -d "2026-01-01 - 1 days" +%Y-%m-%d)
assert_eq "portable_date subtract across month" "2025-12-31" "$result"

# ============================================================
# Summary
# ============================================================
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
