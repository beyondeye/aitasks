#!/usr/bin/env bash
# test_scan_profiles.sh - Automated tests for aitask_scan_profiles.sh
# Run: bash tests/test_scan_profiles.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCAN_SCRIPT="$PROJECT_DIR/aiscripts/aitask_scan_profiles.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

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
    if echo "$actual" | grep -q "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -q "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (output should NOT contain '$unexpected', got '$actual')"
    else
        PASS=$((PASS + 1))
    fi
}

assert_line_count() {
    local desc="$1" expected="$2" actual="$3"
    local count
    count=$(echo "$actual" | grep -c "^" || true)
    TOTAL=$((TOTAL + 1))
    if [[ "$count" -eq "$expected" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected $expected lines, got $count)"
    fi
}

# Create a temp dir with profile files
create_profiles_dir() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    mkdir -p "$tmpdir/profiles"
    echo "$tmpdir"
}

# Disable strict mode for test error handling
set +e

echo "=== aitask_scan_profiles.sh Tests ==="
echo ""

# --- Test 1: No profiles directory ---
echo "--- Test 1: No profiles (empty dir) ---"

TMPDIR_1="$(create_profiles_dir)"
output=$(PROFILES_DIR="$TMPDIR_1/profiles" bash "$SCAN_SCRIPT" 2>&1)
assert_eq "No profiles outputs NO_PROFILES" "NO_PROFILES" "$output"
rm -rf "$TMPDIR_1"

# --- Test 2: Single profile ---
echo "--- Test 2: Single profile ---"

TMPDIR_2="$(create_profiles_dir)"
cat > "$TMPDIR_2/profiles/fast.yaml" <<'EOF'
name: fast
description: Minimal prompts - skip confirmations
skip_task_confirmation: true
EOF
output=$(PROFILES_DIR="$TMPDIR_2/profiles" bash "$SCAN_SCRIPT" 2>&1)
assert_eq "Single profile output" "PROFILE|fast.yaml|fast|Minimal prompts - skip confirmations" "$output"
rm -rf "$TMPDIR_2"

# --- Test 3: Multiple profiles (alphabetical order) ---
echo "--- Test 3: Multiple profiles ---"

TMPDIR_3="$(create_profiles_dir)"
cat > "$TMPDIR_3/profiles/default.yaml" <<'EOF'
name: default
description: Standard interactive workflow
EOF
cat > "$TMPDIR_3/profiles/fast.yaml" <<'EOF'
name: fast
description: Minimal prompts
EOF
cat > "$TMPDIR_3/profiles/remote.yaml" <<'EOF'
name: remote
description: Fully autonomous workflow
EOF
output=$(PROFILES_DIR="$TMPDIR_3/profiles" bash "$SCAN_SCRIPT" 2>&1)
assert_line_count "Three profiles = 3 lines" 3 "$output"
assert_contains "First profile is default" "PROFILE|default.yaml|default|Standard interactive workflow" "$output"
assert_contains "Second profile is fast" "PROFILE|fast.yaml|fast|Minimal prompts" "$output"
assert_contains "Third profile is remote" "PROFILE|remote.yaml|remote|Fully autonomous workflow" "$output"
rm -rf "$TMPDIR_3"

# --- Test 4: --auto selects remote profile ---
echo "--- Test 4: --auto selects remote ---"

TMPDIR_4="$(create_profiles_dir)"
cat > "$TMPDIR_4/profiles/default.yaml" <<'EOF'
name: default
description: Standard
EOF
cat > "$TMPDIR_4/profiles/remote.yaml" <<'EOF'
name: remote
description: Autonomous
EOF
output=$(PROFILES_DIR="$TMPDIR_4/profiles" bash "$SCAN_SCRIPT" --auto 2>&1)
assert_eq "Auto selects remote" "AUTO_SELECTED|remote.yaml|remote|Autonomous" "$output"
rm -rf "$TMPDIR_4"

# --- Test 5: --auto with single profile ---
echo "--- Test 5: --auto with single profile ---"

TMPDIR_5="$(create_profiles_dir)"
cat > "$TMPDIR_5/profiles/custom.yaml" <<'EOF'
name: custom
description: My custom profile
EOF
output=$(PROFILES_DIR="$TMPDIR_5/profiles" bash "$SCAN_SCRIPT" --auto 2>&1)
assert_eq "Auto selects single profile" "AUTO_SELECTED|custom.yaml|custom|My custom profile" "$output"
rm -rf "$TMPDIR_5"

# --- Test 6: --auto with multiple (no remote) → first alphabetically ---
echo "--- Test 6: --auto first alphabetically ---"

TMPDIR_6="$(create_profiles_dir)"
cat > "$TMPDIR_6/profiles/beta.yaml" <<'EOF'
name: beta
description: Beta profile
EOF
cat > "$TMPDIR_6/profiles/alpha.yaml" <<'EOF'
name: alpha
description: Alpha profile
EOF
output=$(PROFILES_DIR="$TMPDIR_6/profiles" bash "$SCAN_SCRIPT" --auto 2>&1)
assert_eq "Auto selects alpha (first alphabetically)" "AUTO_SELECTED|alpha.yaml|alpha|Alpha profile" "$output"
rm -rf "$TMPDIR_6"

# --- Test 7: --auto with no profiles ---
echo "--- Test 7: --auto with no profiles ---"

TMPDIR_7="$(create_profiles_dir)"
output=$(PROFILES_DIR="$TMPDIR_7/profiles" bash "$SCAN_SCRIPT" --auto 2>&1)
assert_eq "Auto with no profiles" "NO_PROFILES" "$output"
rm -rf "$TMPDIR_7"

# --- Test 8: Invalid profile (missing name) skipped in listing ---
echo "--- Test 8: Invalid profile skipped ---"

TMPDIR_8="$(create_profiles_dir)"
cat > "$TMPDIR_8/profiles/good.yaml" <<'EOF'
name: good
description: Good profile
EOF
cat > "$TMPDIR_8/profiles/bad.yaml" <<'EOF'
description: Missing name field
some_setting: true
EOF
output=$(PROFILES_DIR="$TMPDIR_8/profiles" bash "$SCAN_SCRIPT" 2>&1)
assert_contains "Good profile listed" "PROFILE|good.yaml|good|Good profile" "$output"
assert_contains "Bad profile reported as invalid" "INVALID|bad.yaml" "$output"
assert_not_contains "Bad profile not listed as PROFILE" "PROFILE|bad.yaml" "$output"
rm -rf "$TMPDIR_8"

# --- Test 9: Invalid profile in --auto mode (stderr) ---
echo "--- Test 9: Invalid profile in --auto (stderr) ---"

TMPDIR_9="$(create_profiles_dir)"
cat > "$TMPDIR_9/profiles/good.yaml" <<'EOF'
name: good
description: Good profile
EOF
cat > "$TMPDIR_9/profiles/bad.yaml" <<'EOF'
description: Missing name
EOF
stdout_output=$(PROFILES_DIR="$TMPDIR_9/profiles" bash "$SCAN_SCRIPT" --auto 2>/dev/null)
stderr_output=$(PROFILES_DIR="$TMPDIR_9/profiles" bash "$SCAN_SCRIPT" --auto 2>&1 1>/dev/null)
assert_eq "Auto selects good profile" "AUTO_SELECTED|good.yaml|good|Good profile" "$stdout_output"
assert_contains "Invalid reported on stderr" "INVALID|bad.yaml" "$stderr_output"
rm -rf "$TMPDIR_9"

# --- Test 10: Profile with empty description ---
echo "--- Test 10: Empty description ---"

TMPDIR_10="$(create_profiles_dir)"
cat > "$TMPDIR_10/profiles/minimal.yaml" <<'EOF'
name: minimal
EOF
output=$(PROFILES_DIR="$TMPDIR_10/profiles" bash "$SCAN_SCRIPT" 2>&1)
assert_eq "Profile with empty description" "PROFILE|minimal.yaml|minimal|" "$output"
rm -rf "$TMPDIR_10"

# --- Test 11: All profiles invalid ---
echo "--- Test 11: All profiles invalid ---"

TMPDIR_11="$(create_profiles_dir)"
cat > "$TMPDIR_11/profiles/bad1.yaml" <<'EOF'
description: no name
EOF
cat > "$TMPDIR_11/profiles/bad2.yaml" <<'EOF'
key: value
EOF
output=$(PROFILES_DIR="$TMPDIR_11/profiles" bash "$SCAN_SCRIPT" 2>&1)
assert_contains "First invalid reported" "INVALID|bad1.yaml" "$output"
assert_contains "Second invalid reported" "INVALID|bad2.yaml" "$output"
assert_contains "Falls back to NO_PROFILES" "NO_PROFILES" "$output"
rm -rf "$TMPDIR_11"

# --- Test 12: Syntax check ---
echo "--- Test 12: Syntax check ---"

TOTAL=$((TOTAL + 1))
if bash -n "$SCAN_SCRIPT" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Syntax check"
fi

# --- Test 13: Shellcheck ---
echo "--- Test 13: Shellcheck ---"

TOTAL=$((TOTAL + 1))
if command -v shellcheck >/dev/null 2>&1; then
    if shellcheck "$SCAN_SCRIPT" 2>/dev/null; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: Shellcheck found issues"
    fi
else
    PASS=$((PASS + 1))
    echo "  (shellcheck not installed, skipping)"
fi

# --- Test 14: --help flag ---
echo "--- Test 14: --help ---"

TOTAL=$((TOTAL + 1))
if bash "$SCAN_SCRIPT" --help >/dev/null 2>&1; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: --help should exit 0"
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
