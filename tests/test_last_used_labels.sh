#!/usr/bin/env bash
# test_last_used_labels.sh - Tests for get_last_used_labels / set_last_used_labels
# Run: bash tests/test_last_used_labels.sh

set -e

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"

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
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_not_contains() {
    local desc="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$haystack" | grep -qF "$needle"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (did NOT want '$needle', but it was present)"
    else
        PASS=$((PASS + 1))
    fi
}

# --- Setup: temp TASK_DIR so the helpers target an isolated userconfig.yaml ---

TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT

TASK_DIR="$TMPROOT/aitasks"
mkdir -p "$TASK_DIR/metadata"
export TASK_DIR

# task_utils.sh uses SCRIPT_DIR to locate sibling libs; unset any inherited
# value so it computes the right path relative to the sourced file.
unset SCRIPT_DIR || true

# shellcheck source=../.aitask-scripts/lib/task_utils.sh
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"

CONFIG="$TASK_DIR/metadata/userconfig.yaml"

# --- Case 1: round-trip read of an existing [a, b] field ---
cat > "$CONFIG" <<'EOF'
# Local user configuration (gitignored, not shared)
last_used_labels: [a, b]
EOF
assert_eq "read existing [a, b]" "a,b" "$(get_last_used_labels)"

# --- Case 2: file missing -> set creates file with header AND field ---
rm -f "$CONFIG"
set_last_used_labels "x,y"
if [[ -f "$CONFIG" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: set_last_used_labels did not create the file"
fi
TOTAL=$((TOTAL + 1))
file_content="$(cat "$CONFIG")"
assert_contains "created file has header comment" \
    "# Local user configuration (gitignored, not shared)" "$file_content"
assert_contains "created file has field" "last_used_labels: [x, y]" "$file_content"
assert_eq "round-trip x,y" "x,y" "$(get_last_used_labels)"

# --- Case 3: file exists without the field -> set appends, preserves email ---
cat > "$CONFIG" <<'EOF'
# Local user configuration (gitignored, not shared)
email: foo@bar.test
EOF
set_last_used_labels "x,y"
file_content="$(cat "$CONFIG")"
assert_contains "preserves existing email line" "email: foo@bar.test" "$file_content"
assert_contains "appends last_used_labels" "last_used_labels: [x, y]" "$file_content"

# --- Case 4: file exists with the field -> set replaces in place (one line only) ---
cat > "$CONFIG" <<'EOF'
# Local user configuration (gitignored, not shared)
email: foo@bar.test
last_used_labels: [old1, old2]
EOF
set_last_used_labels "c,d"
file_content="$(cat "$CONFIG")"
assert_contains "still has email" "email: foo@bar.test" "$file_content"
assert_contains "has new field value" "last_used_labels: [c, d]" "$file_content"
assert_not_contains "old value replaced" "old1" "$file_content"
count=$(grep -c '^last_used_labels:' "$CONFIG" | tr -d ' ')
assert_eq "exactly one last_used_labels line" "1" "$count"

# --- Case 5: empty input writes [] and reads back as empty ---
set_last_used_labels ""
assert_contains "empty input writes []" "last_used_labels: []" "$(cat "$CONFIG")"
assert_eq "empty list reads empty" "" "$(get_last_used_labels)"

# --- Case 6: absent field -> read returns empty ---
cat > "$CONFIG" <<'EOF'
# Local user configuration (gitignored, not shared)
email: foo@bar.test
EOF
assert_eq "absent field reads empty" "" "$(get_last_used_labels)"

# --- Case 7: missing file -> read returns empty ---
rm -f "$CONFIG"
assert_eq "missing file reads empty" "" "$(get_last_used_labels)"

echo ""
if [[ $FAIL -eq 0 ]]; then
    echo "PASS: $PASS/$TOTAL tests passed"
    exit 0
else
    echo "FAIL: $FAIL/$TOTAL tests failed ($PASS passed)"
    exit 1
fi
