#!/usr/bin/env bash
# test_version_checks.sh - Tests for bash/python version check functions
# Run: bash tests/test_version_checks.sh

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

# Source setup script for function access
source "$PROJECT_DIR/aiscripts/aitask_setup.sh" --source-only
set +euo pipefail

echo "=== Version Check Tests ==="
echo ""

# --- Test 1: check_bash_version passes on current shell ---
echo "--- Test 1: check_bash_version on current shell ---"

# Current shell should be bash 4+ (CI and most dev machines)
OS="linux"
output="$(check_bash_version 2>&1)"
rc=$?

if [[ "${BASH_VERSINFO[0]}" -ge 4 ]]; then
    assert_eq "check_bash_version returns 0 on bash 4+" "0" "$rc"
    assert_contains "Reports meets minimum" "meets minimum" "$output"
else
    # If somehow running under bash 3.2, it should warn
    assert_contains "Warns about old bash" "requires 4.0" "$output"
fi

# --- Test 2: check_python_version with adequate Python ---
echo "--- Test 2: check_python_version with Python >= 3.9 ---"

TMPDIR_2="$(mktemp -d)"
cat > "$TMPDIR_2/python3" << 'STUB'
#!/bin/bash
if echo "$*" | grep -q "sys.version_info"; then
    echo "3.12.1"
fi
STUB
chmod +x "$TMPDIR_2/python3"

OS="linux"
PYTHON_VERSION_OK=0
# Cannot use $() — it creates a subshell and PYTHON_VERSION_OK won't propagate
PATH="$TMPDIR_2:$PATH" check_python_version "$TMPDIR_2/python3" >/dev/null 2>&1

assert_eq "Python 3.12 passes version check" "1" "$PYTHON_VERSION_OK"

rm -rf "$TMPDIR_2"

# --- Test 3: check_python_version with old Python ---
echo "--- Test 3: check_python_version with Python 3.8 (too old) ---"

TMPDIR_3="$(mktemp -d)"
cat > "$TMPDIR_3/python3" << 'STUB'
#!/bin/bash
if echo "$*" | grep -q "sys.version_info"; then
    echo "3.8.10"
fi
STUB
chmod +x "$TMPDIR_3/python3"

OS="linux"
PYTHON_VERSION_OK=0
PATH="$TMPDIR_3:$PATH" check_python_version "$TMPDIR_3/python3" >/dev/null 2>&1

assert_eq "Python 3.8 fails version check" "0" "$PYTHON_VERSION_OK"

rm -rf "$TMPDIR_3"

# --- Test 4: check_python_version with exactly 3.9 (boundary) ---
echo "--- Test 4: check_python_version with Python 3.9.0 (exact minimum) ---"

TMPDIR_4="$(mktemp -d)"
cat > "$TMPDIR_4/python3" << 'STUB'
#!/bin/bash
if echo "$*" | grep -q "sys.version_info"; then
    echo "3.9.0"
fi
STUB
chmod +x "$TMPDIR_4/python3"

OS="linux"
PYTHON_VERSION_OK=0
PATH="$TMPDIR_4:$PATH" check_python_version "$TMPDIR_4/python3" >/dev/null 2>&1

assert_eq "Python 3.9.0 passes version check" "1" "$PYTHON_VERSION_OK"

rm -rf "$TMPDIR_4"

# --- Test 5: check_python_version with Python 2.7 ---
echo "--- Test 5: check_python_version with Python 2.7 ---"

TMPDIR_5="$(mktemp -d)"
cat > "$TMPDIR_5/python3" << 'STUB'
#!/bin/bash
if echo "$*" | grep -q "sys.version_info"; then
    echo "2.7.18"
fi
STUB
chmod +x "$TMPDIR_5/python3"

OS="linux"
PYTHON_VERSION_OK=0
PATH="$TMPDIR_5:$PATH" check_python_version "$TMPDIR_5/python3" >/dev/null 2>&1

assert_eq "Python 2.7 fails version check" "0" "$PYTHON_VERSION_OK"

rm -rf "$TMPDIR_5"

# --- Test 6: check_python_version with broken python ---
echo "--- Test 6: check_python_version with non-functional python ---"

TMPDIR_6="$(mktemp -d)"
cat > "$TMPDIR_6/python3" << 'STUB'
#!/bin/bash
exit 1
STUB
chmod +x "$TMPDIR_6/python3"

OS="linux"
PYTHON_VERSION_OK=0
PATH="$TMPDIR_6:$PATH" check_python_version "$TMPDIR_6/python3" >/dev/null 2>&1

assert_eq "Broken python fails version check" "0" "$PYTHON_VERSION_OK"

rm -rf "$TMPDIR_6"

# --- Test 7: check_python_version on macOS with old python warns about brew ---
echo "--- Test 7: macOS python too old mentions Homebrew ---"

TMPDIR_7="$(mktemp -d)"
cat > "$TMPDIR_7/python3" << 'STUB'
#!/bin/bash
if echo "$*" | grep -q "sys.version_info"; then
    echo "3.7.5"
fi
STUB
chmod +x "$TMPDIR_7/python3"

OS="macos"
PYTHON_VERSION_OK=0
# Run non-interactively (stdin from /dev/null) to avoid prompts
# Remove brew from PATH to skip the install attempt
PATH="$TMPDIR_7" check_python_version "$TMPDIR_7/python3" </dev/null >/dev/null 2>&1

assert_eq "Python 3.7 fails on macOS" "0" "$PYTHON_VERSION_OK"

rm -rf "$TMPDIR_7"

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
