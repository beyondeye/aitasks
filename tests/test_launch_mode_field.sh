#!/usr/bin/env bash
# test_launch_mode_field.sh - Automated tests for --launch-mode flag in aitask_crew_addwork.sh.
# Run: bash tests/test_launch_mode_field.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ORIG_DIR="$(pwd)"

# File-based counters (work across subshells)
COUNTER_FILE="$(mktemp "${TMPDIR:-/tmp}/ait_test_counters_XXXXXX")"
echo "0 0 0" > "$COUNTER_FILE"
trap 'rm -f "$COUNTER_FILE"' EXIT

_inc_pass() {
    local p f t
    read -r p f t < "$COUNTER_FILE"
    echo "$((p + 1)) $f $((t + 1))" > "$COUNTER_FILE"
}
_inc_fail() {
    local p f t
    read -r p f t < "$COUNTER_FILE"
    echo "$p $((f + 1)) $((t + 1))" > "$COUNTER_FILE"
}

# --- Test helpers ---

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    if echo "$actual" | grep -q "$expected"; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    if echo "$actual" | grep -q "$unexpected"; then
        _inc_fail
        echo "FAIL: $desc (did not expect '$unexpected' in '$actual')"
    else
        _inc_pass
    fi
}

assert_exit_nonzero() {
    local desc="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        _inc_fail
        echo "FAIL: $desc (expected non-zero exit, got 0)"
    else
        _inc_pass
    fi
}

# --- Setup: create isolated git repo ---

setup_test_repo() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    (
        cd "$tmpdir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"

        mkdir -p .aitask-scripts/lib aitasks/metadata

        cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_init.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_addwork.sh" .aitask-scripts/
        chmod +x .aitask-scripts/aitask_crew_init.sh .aitask-scripts/aitask_crew_addwork.sh

        echo "email: test@test.com" > aitasks/metadata/userconfig.yaml

        git add -A
        git commit -m "Initial setup" --quiet
    )

    echo "$tmpdir"
}

cleanup_test_repo() {
    local tmpdir="$1"
    cd "$ORIG_DIR"
    if [[ -d "$tmpdir" ]]; then
        (cd "$tmpdir" && git worktree prune 2>/dev/null || true)
        rm -rf "$tmpdir"
    fi
}

# ============================================================
# Tests
# ============================================================

echo "=== AgentCrew launch_mode field tests ==="
echo ""

# --- Test 1: default (no flag) sets launch_mode: headless ---
echo "Test 1: default launch_mode is headless"
TMPDIR_T1="$(setup_test_repo)"
(
    cd "$TMPDIR_T1"
    bash .aitask-scripts/aitask_crew_init.sh --id lm1 --add-type impl:claudecode/opus4_6 --batch >/dev/null 2>&1
    bash .aitask-scripts/aitask_crew_addwork.sh --crew lm1 --name a_default --work2do /dev/null --type impl --batch >/dev/null 2>&1
    status_content=$(cat ".aitask-crews/crew-lm1/a_default_status.yaml")
    assert_contains "default launch_mode is headless" "launch_mode: headless" "$status_content"
)
cleanup_test_repo "$TMPDIR_T1"

# --- Test 2: --launch-mode headless is explicit ---
echo "Test 2: --launch-mode headless is explicit"
TMPDIR_T2="$(setup_test_repo)"
(
    cd "$TMPDIR_T2"
    bash .aitask-scripts/aitask_crew_init.sh --id lm2 --add-type impl:claudecode/opus4_6 --batch >/dev/null 2>&1
    bash .aitask-scripts/aitask_crew_addwork.sh --crew lm2 --name a_headless --work2do /dev/null --type impl --launch-mode headless --batch >/dev/null 2>&1
    status_content=$(cat ".aitask-crews/crew-lm2/a_headless_status.yaml")
    assert_contains "explicit headless sets launch_mode: headless" "launch_mode: headless" "$status_content"
    assert_not_contains "no stray interactive value" "interactive" "$status_content"
)
cleanup_test_repo "$TMPDIR_T2"

# --- Test 3: --launch-mode interactive sets the field ---
echo "Test 3: --launch-mode interactive sets the field"
TMPDIR_T3="$(setup_test_repo)"
(
    cd "$TMPDIR_T3"
    bash .aitask-scripts/aitask_crew_init.sh --id lm3 --add-type impl:claudecode/opus4_6 --batch >/dev/null 2>&1
    output=$(bash .aitask-scripts/aitask_crew_addwork.sh --crew lm3 --name a_inter --work2do /dev/null --type impl --launch-mode interactive --batch 2>&1)
    assert_contains "addwork with interactive succeeds" "ADDED:a_inter" "$output"
    status_content=$(cat ".aitask-crews/crew-lm3/a_inter_status.yaml")
    assert_contains "launch_mode is interactive" "launch_mode: interactive" "$status_content"
)
cleanup_test_repo "$TMPDIR_T3"

# --- Test 4: invalid --launch-mode value is rejected ---
echo "Test 4: invalid --launch-mode value is rejected"
TMPDIR_T4="$(setup_test_repo)"
(
    cd "$TMPDIR_T4"
    bash .aitask-scripts/aitask_crew_init.sh --id lm4 --add-type impl:claudecode/opus4_6 --batch >/dev/null 2>&1
    assert_exit_nonzero "rejects invalid launch_mode" \
        bash .aitask-scripts/aitask_crew_addwork.sh --crew lm4 --name a_bad --work2do /dev/null --type impl --launch-mode weird --batch
)
cleanup_test_repo "$TMPDIR_T4"

# --- Test 5: --launch-mode without value is rejected ---
echo "Test 5: --launch-mode without value is rejected"
TMPDIR_T5="$(setup_test_repo)"
(
    cd "$TMPDIR_T5"
    bash .aitask-scripts/aitask_crew_init.sh --id lm5 --add-type impl:claudecode/opus4_6 --batch >/dev/null 2>&1
    assert_exit_nonzero "rejects empty --launch-mode" \
        bash .aitask-scripts/aitask_crew_addwork.sh --crew lm5 --name a_empty --work2do /dev/null --type impl --launch-mode --batch
)
cleanup_test_repo "$TMPDIR_T5"

# ============================================================
# Summary
# ============================================================

read -r PASS FAIL TOTAL < "$COUNTER_FILE"

echo ""
echo "=== Results ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "TOTAL: $TOTAL"

if [[ $FAIL -gt 0 ]]; then
    echo "SOME TESTS FAILED"
    exit 1
else
    echo "ALL TESTS PASSED"
fi
