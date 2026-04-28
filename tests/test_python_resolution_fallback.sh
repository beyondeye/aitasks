#!/usr/bin/env bash
# test_python_resolution_fallback.sh — verify lib/python_resolve.sh works in
# stripped environments (e.g. remote sandboxes where ~/.aitask/ doesn't exist).
# Run: bash tests/test_python_resolution_fallback.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

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

assert_nonempty() {
    local desc="$1" actual="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -n "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (got empty value)"
    fi
}

echo "=== Python Resolution Fallback Tests ==="
echo ""

# --- Test 1: AIT_VENV_PYTHON_MIN constant is defined after sourcing ---
echo "--- Test 1: AIT_VENV_PYTHON_MIN constant is exposed by helper ---"
result="$(bash -c "
    set -e
    cd '$PROJECT_DIR'
    # shellcheck source=.aitask-scripts/lib/python_resolve.sh
    source .aitask-scripts/lib/python_resolve.sh
    echo \"\$AIT_VENV_PYTHON_MIN\"
")"
assert_nonempty "AIT_VENV_PYTHON_MIN is set" "$result"
assert_eq "AIT_VENV_PYTHON_MIN defaults to 3.11" "3.11" "$result"

# --- Test 2: resolve_python falls back to system python3 in stripped env ---
echo "--- Test 2: resolve_python falls back to system python3 ---"
SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT

# Find the system python3 path (independent of any symlinks the test might shadow)
expected_python=""
for cand in /usr/bin/python3 /bin/python3; do
    if [[ -x "$cand" ]]; then
        expected_python="$cand"
        break
    fi
done

if [[ -z "$expected_python" ]]; then
    echo "SKIP: No system python3 found at /usr/bin or /bin — cannot verify fallback"
else
    result="$(env -i HOME="$SCRATCH" PATH=/usr/bin:/bin bash -c "
        cd '$PROJECT_DIR'
        # shellcheck source=.aitask-scripts/lib/python_resolve.sh
        source .aitask-scripts/lib/python_resolve.sh
        resolve_python
    ")"
    assert_eq "resolve_python returns system python3 in stripped HOME+PATH" \
        "$expected_python" "$result"
fi

# --- Test 3: aitask_verification_parse.sh runs without crashing in stripped env ---
echo "--- Test 3: aitask_verification_parse.sh handles stripped environment ---"
# The wrapper sources python_resolve.sh + uses require_python (no version check)
# so should run on plain system python3.
fixture="$SCRATCH/empty_task.md"
echo "---" > "$fixture"
echo "---" >> "$fixture"
# Run with stripped env. We don't care what the script outputs — only that it
# doesn't crash with a "framework not bootstrapped" error.
output="$(env -i HOME="$SCRATCH" PATH=/usr/bin:/bin bash -c "
    cd '$PROJECT_DIR'
    ./.aitask-scripts/aitask_verification_parse.sh '$fixture' 2>&1
" || true)"
# Check that the output does NOT contain the helper's failure message:
if echo "$output" | grep -q "No Python interpreter found"; then
    FAIL=$((FAIL + 1))
    TOTAL=$((TOTAL + 1))
    echo "FAIL: verification_parse should not report 'No Python interpreter found' when system python3 is on PATH"
else
    PASS=$((PASS + 1))
    TOTAL=$((TOTAL + 1))
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
