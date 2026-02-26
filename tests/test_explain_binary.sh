#!/usr/bin/env bash
# test_explain_binary.sh - Tests for binary file handling in aiexplains pipeline (t255_1)
# Run: bash tests/test_explain_binary.sh

set -e

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"
SCRIPT_DIR="$PROJECT_DIR/aiscripts"
source "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh"

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
    if echo "$actual" | grep -qF -- "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected to contain '$expected')"
        echo "  actual: $(echo "$actual" | head -5)"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF -- "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected NOT to contain '$unexpected')"
        echo "  actual: $(echo "$actual" | head -5)"
    else
        PASS=$((PASS + 1))
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

# Binary test file (must be git-tracked)
BINARY_FILE="imgs/aitasks_logo_dark_theme.png"
# Text test file (must be git-tracked)
TEXT_FILE="aiscripts/lib/terminal_compat.sh"

cd "$PROJECT_DIR"

echo "=== Binary File Handling Tests (t255_1) ==="
echo ""

# ============================================================
# Test 1: is_binary detects PNG as binary
# ============================================================
echo "--- is_binary: PNG detection ---"

# Define is_binary matching the implementation (can't source the script as it runs main())
is_binary() {
    local filepath="$1"
    file -b --mime-encoding "$filepath" 2>/dev/null | grep -q 'binary'
}

TOTAL=$((TOTAL + 1))
if is_binary "$BINARY_FILE"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: is_binary should detect PNG as binary"
fi

# ============================================================
# Test 2: is_binary does NOT flag text file
# ============================================================
echo "--- is_binary: text file detection ---"

TOTAL=$((TOTAL + 1))
if is_binary "$TEXT_FILE"; then
    FAIL=$((FAIL + 1))
    echo "FAIL: is_binary should NOT detect text file as binary"
else
    PASS=$((PASS + 1))
fi

# ============================================================
# Test 3: Binary file extraction contains BINARY_FILE marker
# ============================================================
echo "--- Shell extraction: binary file has BINARY_FILE marker ---"

setup_tmpdir
AIEXPLAINS_DIR="$TMPDIR_TEST" bash "$PROJECT_DIR/aiscripts/aitask_explain_extract_raw_data.sh" \
    --gather "$BINARY_FILE" --max-commits 5 > "$TMPDIR_TEST/gather_out.txt" 2>&1

RUN_DIR=$(grep "^RUN_DIR:" "$TMPDIR_TEST/gather_out.txt" | sed 's/^RUN_DIR: //')
raw_data=$(cat "$RUN_DIR/raw_data.txt")

assert_contains "binary raw_data has BINARY_FILE marker" "BINARY_FILE" "$raw_data"

# ============================================================
# Test 4: Binary file extraction contains COMMIT_TIMELINE
# ============================================================
echo "--- Shell extraction: binary file has COMMIT_TIMELINE ---"

assert_contains "binary raw_data has COMMIT_TIMELINE" "COMMIT_TIMELINE:" "$raw_data"

# ============================================================
# Test 5: Binary file extraction does NOT contain BLAME_LINES
# ============================================================
echo "--- Shell extraction: binary file has no BLAME_LINES ---"

assert_not_contains "binary raw_data has no BLAME_LINES" "BLAME_LINES:" "$raw_data"

cleanup_tmpdir

# ============================================================
# Test 6: Text file extraction contains BLAME_LINES
# ============================================================
echo "--- Shell extraction: text file has BLAME_LINES ---"

setup_tmpdir
AIEXPLAINS_DIR="$TMPDIR_TEST" bash "$PROJECT_DIR/aiscripts/aitask_explain_extract_raw_data.sh" \
    --gather "$TEXT_FILE" --max-commits 5 > "$TMPDIR_TEST/gather_out.txt" 2>&1

RUN_DIR=$(grep "^RUN_DIR:" "$TMPDIR_TEST/gather_out.txt" | sed 's/^RUN_DIR: //')
raw_data=$(cat "$RUN_DIR/raw_data.txt")

assert_contains "text raw_data has BLAME_LINES" "BLAME_LINES:" "$raw_data"

# ============================================================
# Test 7: Text file extraction does NOT contain BINARY_FILE
# ============================================================
echo "--- Shell extraction: text file has no BINARY_FILE marker ---"

assert_not_contains "text raw_data has no BINARY_FILE" "BINARY_FILE" "$raw_data"

cleanup_tmpdir

# ============================================================
# Test 8: Binary file reference.yaml contains binary: true
# ============================================================
echo "--- Python processor: binary file has binary: true ---"

setup_tmpdir
AIEXPLAINS_DIR="$TMPDIR_TEST" bash "$PROJECT_DIR/aiscripts/aitask_explain_extract_raw_data.sh" \
    --gather "$BINARY_FILE" --max-commits 5 > "$TMPDIR_TEST/gather_out.txt" 2>&1

RUN_DIR=$(grep "^RUN_DIR:" "$TMPDIR_TEST/gather_out.txt" | sed 's/^RUN_DIR: //')
ref_yaml=$(cat "$RUN_DIR/reference.yaml")

assert_contains "reference.yaml has binary: true" "binary: true" "$ref_yaml"

# ============================================================
# Test 9: Binary file reference.yaml has empty line_ranges
# ============================================================
echo "--- Python processor: binary file has empty line_ranges ---"

# Check that after "line_ranges:" there is no "- start:" before the next section
# Extract the line_ranges section for the binary file
line_ranges_section=$(echo "$ref_yaml" | sed -n '/line_ranges:/,/^[^ ]/p' | head -5)
assert_not_contains "binary line_ranges has no entries" "- start:" "$line_ranges_section"

cleanup_tmpdir

# ============================================================
# Test 10: Backward compatibility — old format without BINARY_FILE
# ============================================================
echo "--- Backward compat: old format raw_data processes correctly ---"

setup_tmpdir
# Create a raw_data.txt in the old format (no BINARY_FILE marker)
cat > "$TMPDIR_TEST/old_raw_data.txt" <<'RAWEOF'
=== FILE: some/text_file.sh ===

COMMIT_TIMELINE:
1|abc1234|2026-01-15|Author|feature: Add something (t42)|42

BLAME_LINES:
1|abc1234abc1234abc1234abc1234abc1234abc1234
2|abc1234abc1234abc1234abc1234abc1234abc1234

=== END FILE ===

=== TASK_INDEX ===
42|tasks/t42.md|plans/p42.md
=== END TASK_INDEX ===
RAWEOF

python3 "$PROJECT_DIR/aiscripts/aitask_explain_process_raw_data.py" \
    "$TMPDIR_TEST/old_raw_data.txt" "$TMPDIR_TEST/old_reference.yaml"

old_ref=$(cat "$TMPDIR_TEST/old_reference.yaml")
assert_not_contains "old format has no binary: true" "binary: true" "$old_ref"
assert_contains "old format has line_ranges entries" "- start:" "$old_ref"

cleanup_tmpdir

# ============================================================
# Test 11: Mixed binary + text in same extraction run
# ============================================================
echo "--- Mixed: binary + text files in same run ---"

setup_tmpdir
AIEXPLAINS_DIR="$TMPDIR_TEST" bash "$PROJECT_DIR/aiscripts/aitask_explain_extract_raw_data.sh" \
    --gather "$BINARY_FILE" "$TEXT_FILE" --max-commits 5 > "$TMPDIR_TEST/gather_out.txt" 2>&1

RUN_DIR=$(grep "^RUN_DIR:" "$TMPDIR_TEST/gather_out.txt" | sed 's/^RUN_DIR: //')
raw_data=$(cat "$RUN_DIR/raw_data.txt")
ref_yaml=$(cat "$RUN_DIR/reference.yaml")

# Binary file should have BINARY_FILE marker
assert_contains "mixed: raw_data has BINARY_FILE" "BINARY_FILE" "$raw_data"

# Text file should have BLAME_LINES
assert_contains "mixed: raw_data has BLAME_LINES" "BLAME_LINES:" "$raw_data"

# reference.yaml should have binary: true for the binary file
assert_contains "mixed: reference.yaml has binary: true" "binary: true" "$ref_yaml"

# reference.yaml should have line_ranges with entries for the text file
# Extract the text file's section (second file entry)
text_section=$(echo "$ref_yaml" | sed -n "/path: .*terminal_compat/,/^  - path:/p")
assert_contains "mixed: text file has line_ranges entries" "- start:" "$text_section"

cleanup_tmpdir

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
