#!/usr/bin/env bash
# test_install_merge.sh - Tests for aitask_install_merge.py
# Run: bash tests/test_install_merge.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MERGE_SCRIPT="$PROJECT_DIR/.aitask-scripts/aitask_install_merge.py"

# shellcheck source=lib/venv_python.sh
. "$SCRIPT_DIR/lib/venv_python.sh"

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

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF -- "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected' in output, got: $actual)"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF -- "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (did not expect '$unexpected', got: $actual)"
    else
        PASS=$((PASS + 1))
    fi
}

TMP="$(mktemp -d -t aitask_install_merge_XXXXXX)"
trap "rm -rf '$TMP'" EXIT

# --- YAML merge: dest values win, new seed keys added, nested deep-merge ---

cat > "$TMP/src.yaml" <<'EOF'
a: 1
nested:
  x: 10
  z: 30
new_key: from_seed
EOF
cat > "$TMP/dest.yaml" <<'EOF'
a: 999
nested:
  x: 999
  y: 20
extra: user_only
EOF
"$AITASK_PYTHON" "$MERGE_SCRIPT" yaml "$TMP/src.yaml" "$TMP/dest.yaml"
merged_yaml="$(cat "$TMP/dest.yaml")"
assert_contains "yaml: existing scalar dest value wins" "a: 999" "$merged_yaml"
assert_contains "yaml: new seed top-level key added" "new_key: from_seed" "$merged_yaml"
assert_contains "yaml: nested dest scalar wins" "x: 999" "$merged_yaml"
assert_contains "yaml: nested seed-only key added" "z: 30" "$merged_yaml"
assert_contains "yaml: dest-only nested key preserved" "y: 20" "$merged_yaml"
assert_contains "yaml: dest-only top-level key preserved" "extra: user_only" "$merged_yaml"

# --- YAML merge: list values replaced atomically by dest (per deep_merge semantics) ---

cat > "$TMP/src.yaml" <<'EOF'
items:
  - a
  - b
  - c
EOF
cat > "$TMP/dest.yaml" <<'EOF'
items:
  - a
  - custom
EOF
"$AITASK_PYTHON" "$MERGE_SCRIPT" yaml "$TMP/src.yaml" "$TMP/dest.yaml"
list_merged="$(cat "$TMP/dest.yaml")"
assert_contains "yaml: dest list wins (contains 'custom')" "custom" "$list_merged"
assert_not_contains "yaml: dest list wins (seed-only 'b' dropped)" "- b" "$list_merged"

# --- YAML merge: dest-absent falls back to straight copy ---

rm -f "$TMP/new_dest.yaml"
"$AITASK_PYTHON" "$MERGE_SCRIPT" yaml "$TMP/src.yaml" "$TMP/new_dest.yaml"
assert_eq "yaml: dest-missing copies seed bytes verbatim" \
    "$(cat "$TMP/src.yaml")" "$(cat "$TMP/new_dest.yaml")"

# --- JSON merge: same semantics ---

echo '{"a":1,"n":{"x":10,"z":30},"new":"seed"}' > "$TMP/src.json"
echo '{"a":999,"n":{"x":999,"y":20},"extra":"user"}' > "$TMP/dest.json"
"$AITASK_PYTHON" "$MERGE_SCRIPT" json "$TMP/src.json" "$TMP/dest.json"
merged_json="$(cat "$TMP/dest.json")"
assert_contains "json: dest scalar wins" '"a": 999' "$merged_json"
assert_contains "json: nested seed-only key added" '"z": 30' "$merged_json"
assert_contains "json: dest-only nested key preserved" '"y": 20' "$merged_json"
assert_contains "json: new top-level seed key added" '"new": "seed"' "$merged_json"

# --- JSON merge: invalid JSON fails non-zero, dest untouched ---

echo 'not valid json {' > "$TMP/bad.json"
echo '{"ok": true}' > "$TMP/good_dest.json"
original_good_dest="$(cat "$TMP/good_dest.json")"
if "$AITASK_PYTHON" "$MERGE_SCRIPT" json "$TMP/bad.json" "$TMP/good_dest.json" 2>/dev/null; then
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
    echo "FAIL: json: invalid src should exit non-zero"
else
    PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
fi
assert_eq "json: invalid src leaves dest untouched" \
    "$original_good_dest" "$(cat "$TMP/good_dest.json")"

# --- text-union: dest order preserved, seed-only lines appended ---

printf 'bug\nfeature\nchore\ntest\ndocs\n' > "$TMP/src.txt"
printf 'feature\nbug\nmy_custom\n' > "$TMP/dest.txt"
"$AITASK_PYTHON" "$MERGE_SCRIPT" text-union "$TMP/src.txt" "$TMP/dest.txt"
merged_txt="$(cat "$TMP/dest.txt")"
expected_txt="feature
bug
my_custom
chore
test
docs"
assert_eq "text-union: dest order preserved, seed additions appended" \
    "$expected_txt" "$merged_txt"

# --- text-union: idempotent (running twice yields same result) ---

"$AITASK_PYTHON" "$MERGE_SCRIPT" text-union "$TMP/src.txt" "$TMP/dest.txt"
assert_eq "text-union: idempotent on repeat merge" \
    "$expected_txt" "$(cat "$TMP/dest.txt")"

# --- text-union: dest-absent falls back to copy ---

rm -f "$TMP/new_dest.txt"
"$AITASK_PYTHON" "$MERGE_SCRIPT" text-union "$TMP/src.txt" "$TMP/new_dest.txt"
assert_eq "text-union: dest-missing copies seed verbatim" \
    "$(cat "$TMP/src.txt")" "$(cat "$TMP/new_dest.txt")"

# --- Usage errors ---

if "$AITASK_PYTHON" "$MERGE_SCRIPT" unknown_mode "$TMP/src.txt" "$TMP/dest.txt" 2>/dev/null; then
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
    echo "FAIL: unknown mode should exit non-zero"
else
    PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
fi

if "$AITASK_PYTHON" "$MERGE_SCRIPT" yaml 2>/dev/null; then
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
    echo "FAIL: missing args should exit non-zero"
else
    PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
fi

# --- Summary ---

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
