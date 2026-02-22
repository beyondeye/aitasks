#!/usr/bin/env bash
# test_global_shim.sh - Tests for the global shim's auto-bootstrap behavior
# Run: bash tests/test_global_shim.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

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
    if echo "$actual" | grep -qi "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected')"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qi "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (output should NOT contain '$unexpected')"
    else
        PASS=$((PASS + 1))
    fi
}

# Generate a shim script into a temp file by calling install_global_shim
# with a custom SHIM_DIR
generate_test_shim() {
    local shim_dir="$1"
    mkdir -p "$shim_dir"

    # Source setup script to get the function
    SHIM_DIR="$shim_dir" source "$PROJECT_DIR/aiscripts/aitask_setup.sh" --source-only
    set +euo pipefail

    SHIM_DIR="$shim_dir" install_global_shim >/dev/null 2>/dev/null

    echo "$shim_dir/ait"
}

echo "=== Global Shim Tests ==="
echo ""

# --- Test 1: Syntax check of aitask_setup.sh ---
echo "--- Test 1: Syntax check of aitask_setup.sh ---"

TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/aiscripts/aitask_setup.sh" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: bash -n aitask_setup.sh (syntax error)"
fi

# --- Test 2: Generate shim and syntax check it ---
echo "--- Test 2: Generate and syntax-check shim ---"

TMPDIR_2="$(mktemp -d)"
SHIM_PATH_2="$(generate_test_shim "$TMPDIR_2/shimbin")"

TOTAL=$((TOTAL + 1))
if [[ -f "$SHIM_PATH_2" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Shim file not created at $SHIM_PATH_2"
fi

TOTAL=$((TOTAL + 1))
if bash -n "$SHIM_PATH_2" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: bash -n on generated shim (syntax error)"
fi

TOTAL=$((TOTAL + 1))
if [[ -x "$SHIM_PATH_2" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Shim should be executable"
fi

# --- Test 3: Non-setup command with no project → error suggesting ait setup ---
echo "--- Test 3: Non-setup command with no project ---"

TMPDIR_3="$(mktemp -d)"
SHIM_PATH_3="$(generate_test_shim "$TMPDIR_3/shimbin")"

# Run shim from an empty directory with "ls" command
output=$(cd "$TMPDIR_3" && "$SHIM_PATH_3" ls 2>&1)
rc=$?

assert_eq "Exit code is 1" "1" "$rc"
assert_contains "Suggests ait setup" "ait setup" "$output"
assert_contains "Error message present" "no ait project" "$output"

rm -rf "$TMPDIR_3"

# --- Test 4: Setup non-interactive with no project → skips prompt, tries download ---
echo "--- Test 4: Setup non-interactive (no project, no network) ---"

TMPDIR_4="$(mktemp -d)"
SHIM_PATH_4="$(generate_test_shim "$TMPDIR_4/shimbin")"

# Run shim with "setup" non-interactively (stdin from /dev/null)
# Confirmation is skipped (non-interactive), download will fail since we
# don't mock the network — shim should exit 1
output=$(cd "$TMPDIR_4" && "$SHIM_PATH_4" setup </dev/null 2>&1)
rc=$?

assert_eq "Exit code is 1 (download fails)" "1" "$rc"
# It should attempt the download, showing the "Downloading" message
assert_contains "Attempts download" "downloading" "$output"

rm -rf "$TMPDIR_4"

# --- Test 5: Setup command in existing project → dispatches to local ait ---
echo "--- Test 5: Setup in existing project dispatches locally ---"

TMPDIR_5="$(mktemp -d)"
SHIM_PATH_5="$(generate_test_shim "$TMPDIR_5/shimbin")"

# Create a fake project with a local ait that touches a marker file
mkdir -p "$TMPDIR_5/project/aiscripts"
cat > "$TMPDIR_5/project/ait" << 'EOF'
#!/usr/bin/env bash
touch "$(dirname "$0")/marker_dispatched"
echo "local ait called with: $*"
EOF
chmod +x "$TMPDIR_5/project/ait"

# Run shim from within the fake project
output=$(cd "$TMPDIR_5/project" && "$SHIM_PATH_5" setup 2>&1)

TOTAL=$((TOTAL + 1))
if [[ -f "$TMPDIR_5/project/marker_dispatched" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Local ait was not dispatched to"
fi

assert_contains "Local ait received setup command" "setup" "$output"

rm -rf "$TMPDIR_5"

# --- Test 6: Dispatch works from subdirectory of existing project ---
echo "--- Test 6: Dispatch from subdirectory ---"

TMPDIR_6="$(mktemp -d)"
SHIM_PATH_6="$(generate_test_shim "$TMPDIR_6/shimbin")"

# Create a fake project
mkdir -p "$TMPDIR_6/project/aiscripts"
mkdir -p "$TMPDIR_6/project/src/deep/nested"
cat > "$TMPDIR_6/project/ait" << 'EOF'
#!/usr/bin/env bash
touch "$(dirname "$0")/marker_dispatched"
EOF
chmod +x "$TMPDIR_6/project/ait"

# Run shim from a deep subdirectory
output=$(cd "$TMPDIR_6/project/src/deep/nested" && "$SHIM_PATH_6" ls 2>&1)

TOTAL=$((TOTAL + 1))
if [[ -f "$TMPDIR_6/project/marker_dispatched" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Local ait was not found from subdirectory"
fi

rm -rf "$TMPDIR_6"

# --- Test 7: Recursion guard ---
echo "--- Test 7: Recursion guard ---"

TMPDIR_7="$(mktemp -d)"
SHIM_PATH_7="$(generate_test_shim "$TMPDIR_7/shimbin")"

output=$(cd "$TMPDIR_7" && _AIT_SHIM_ACTIVE=1 "$SHIM_PATH_7" setup 2>&1)
rc=$?

assert_eq "Exit code is 1 with recursion guard" "1" "$rc"
assert_contains "Error mentions dispatcher not found" "not found" "$output"

rm -rf "$TMPDIR_7"

# --- Test 8: Shim contains REPO variable ---
echo "--- Test 8: Shim contains REPO variable ---"

TMPDIR_8="$(mktemp -d)"
SHIM_PATH_8="$(generate_test_shim "$TMPDIR_8/shimbin")"

assert_contains "REPO variable in shim" "beyondeye/aitasks" "$(cat "$SHIM_PATH_8")"

rm -rf "$TMPDIR_8"

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
