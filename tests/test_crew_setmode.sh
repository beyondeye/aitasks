#!/usr/bin/env bash
# test_crew_setmode.sh - Automated tests for ait crew setmode (t461_2).
# Run: bash tests/test_crew_setmode.sh

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
    if echo "$actual" | grep -qF -- "$expected"; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    if echo "$actual" | grep -qF -- "$unexpected"; then
        _inc_fail
        echo "FAIL: $desc (did not expect '$unexpected' in '$actual')"
    else
        _inc_pass
    fi
}

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [[ "$expected" == "$actual" ]]; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: $desc (expected '$expected', got '$actual')"
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

# --- Setup: create isolated git repo with a crew and a Waiting agent ---

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
        cp "$PROJECT_DIR/.aitask-scripts/lib/launch_modes_sh.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/launch_modes.py"    .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_init.sh"    .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_addwork.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_setmode.sh" .aitask-scripts/
        chmod +x .aitask-scripts/aitask_crew_init.sh \
                 .aitask-scripts/aitask_crew_addwork.sh \
                 .aitask-scripts/aitask_crew_setmode.sh

        echo "email: test@test.com" > aitasks/metadata/userconfig.yaml

        git add -A
        git commit -m "Initial setup" --quiet
    )

    echo "$tmpdir"
}

# Create a crew with one Waiting agent (default headless launch_mode)
seed_crew_with_agent() {
    local crew_id="$1" agent_name="$2"
    bash .aitask-scripts/aitask_crew_init.sh --id "$crew_id" --add-type impl:claudecode/opus4_6 --batch >/dev/null 2>&1
    bash .aitask-scripts/aitask_crew_addwork.sh --crew "$crew_id" --name "$agent_name" --work2do /dev/null --type impl --batch >/dev/null 2>&1
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

echo "=== ait crew setmode tests ==="
echo ""

# --- Test 1: happy path — flip headless to interactive ---
echo "Test 1: happy path (headless -> interactive)"
TMPDIR_T1="$(setup_test_repo)"
(
    cd "$TMPDIR_T1"
    seed_crew_with_agent sm1 worker1

    output=$(bash .aitask-scripts/aitask_crew_setmode.sh --crew sm1 --name worker1 --mode interactive 2>&1)
    assert_contains "structured success line" "UPDATED:worker1:interactive" "$output"

    status_content=$(cat ".aitask-crews/crew-sm1/worker1_status.yaml")
    assert_contains "yaml shows interactive" "launch_mode: interactive" "$status_content"
    assert_not_contains "yaml has no stray headless line" "launch_mode: headless" "$status_content"

    last_msg=$(git -C ".aitask-crews/crew-sm1" log -1 --format=%s)
    assert_contains "commit message records mutation" "Set launch_mode=interactive" "$last_msg"
)
cleanup_test_repo "$TMPDIR_T1"

# --- Test 2: round trip interactive -> headless ---
echo "Test 2: round trip (headless -> interactive -> headless)"
TMPDIR_T2="$(setup_test_repo)"
(
    cd "$TMPDIR_T2"
    seed_crew_with_agent sm2 worker2

    bash .aitask-scripts/aitask_crew_setmode.sh --crew sm2 --name worker2 --mode interactive >/dev/null 2>&1
    bash .aitask-scripts/aitask_crew_setmode.sh --crew sm2 --name worker2 --mode headless >/dev/null 2>&1

    status_content=$(cat ".aitask-crews/crew-sm2/worker2_status.yaml")
    assert_contains "final yaml is headless" "launch_mode: headless" "$status_content"
    assert_not_contains "no leftover interactive" "launch_mode: interactive" "$status_content"

    # Two new commits: one for interactive, one for headless
    new_commits=$(git -C ".aitask-crews/crew-sm2" log --format=%s | grep -c "Set launch_mode=" || true)
    assert_eq "two setmode commits exist" "2" "$new_commits"
)
cleanup_test_repo "$TMPDIR_T2"

# --- Test 3: idempotent — setting the same mode twice creates only one commit ---
echo "Test 3: idempotent (setting same mode twice creates only one commit)"
TMPDIR_T3="$(setup_test_repo)"
(
    cd "$TMPDIR_T3"
    seed_crew_with_agent sm3 worker3

    bash .aitask-scripts/aitask_crew_setmode.sh --crew sm3 --name worker3 --mode interactive >/dev/null 2>&1
    count_after_first=$(git -C ".aitask-crews/crew-sm3" rev-list --count HEAD)

    output=$(bash .aitask-scripts/aitask_crew_setmode.sh --crew sm3 --name worker3 --mode interactive 2>&1)
    count_after_second=$(git -C ".aitask-crews/crew-sm3" rev-list --count HEAD)

    assert_contains "second call still prints structured success" "UPDATED:worker3:interactive" "$output"
    assert_eq "no new commit on second call" "$count_after_first" "$count_after_second"
)
cleanup_test_repo "$TMPDIR_T3"

# --- Test 4: status gate — Running agent cannot be mutated ---
echo "Test 4: status gate rejects non-Waiting agents"
TMPDIR_T4="$(setup_test_repo)"
(
    cd "$TMPDIR_T4"
    seed_crew_with_agent sm4 worker4

    # Manually flip status to Running by rewriting the line
    status_file=".aitask-crews/crew-sm4/worker4_status.yaml"
    tmp="$(mktemp "${TMPDIR:-/tmp}/sm4_XXXXXX")"
    sed 's/^status: Waiting/status: Running/' "$status_file" > "$tmp" && mv "$tmp" "$status_file"

    set +e
    err_output=$(bash .aitask-scripts/aitask_crew_setmode.sh --crew sm4 --name worker4 --mode interactive 2>&1)
    rc=$?
    set -e

    if [[ $rc -ne 0 ]]; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: status gate did not block Running agent (exit was 0)"
    fi
    assert_contains "error mentions pending launches" "launch_mode only applies to pending launches" "$err_output"

    # Yaml should be unchanged: still headless
    assert_contains "yaml unchanged after rejection" "launch_mode: headless" "$(cat "$status_file")"
)
cleanup_test_repo "$TMPDIR_T4"

# --- Test 5: bad --mode value is rejected ---
echo "Test 5: bad --mode value is rejected"
TMPDIR_T5="$(setup_test_repo)"
(
    cd "$TMPDIR_T5"
    seed_crew_with_agent sm5 worker5

    set +e
    err_output=$(bash .aitask-scripts/aitask_crew_setmode.sh --crew sm5 --name worker5 --mode verbose 2>&1)
    rc=$?
    set -e

    if [[ $rc -ne 0 ]]; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: bad mode did not exit non-zero"
    fi
    assert_contains "validation error message" "must be one of:" "$err_output"
)
cleanup_test_repo "$TMPDIR_T5"

# --- Test 6: missing agent ---
echo "Test 6: missing agent rejected"
TMPDIR_T6="$(setup_test_repo)"
(
    cd "$TMPDIR_T6"
    seed_crew_with_agent sm6 worker6
    assert_exit_nonzero "missing agent rejected" \
        bash .aitask-scripts/aitask_crew_setmode.sh --crew sm6 --name does_not_exist --mode interactive
)
cleanup_test_repo "$TMPDIR_T6"

# --- Test 7: missing crew ---
echo "Test 7: missing crew rejected"
TMPDIR_T7="$(setup_test_repo)"
(
    cd "$TMPDIR_T7"
    assert_exit_nonzero "missing crew rejected" \
        bash .aitask-scripts/aitask_crew_setmode.sh --crew does_not_exist --name worker --mode interactive
)
cleanup_test_repo "$TMPDIR_T7"

# --- Test 8: missing required flags ---
echo "Test 8: missing required flags rejected"
TMPDIR_T8="$(setup_test_repo)"
(
    cd "$TMPDIR_T8"
    seed_crew_with_agent sm8 worker8

    assert_exit_nonzero "missing --mode rejected" \
        bash .aitask-scripts/aitask_crew_setmode.sh --crew sm8 --name worker8
    assert_exit_nonzero "missing --name rejected" \
        bash .aitask-scripts/aitask_crew_setmode.sh --crew sm8 --mode interactive
    assert_exit_nonzero "missing --crew rejected" \
        bash .aitask-scripts/aitask_crew_setmode.sh --name worker8 --mode interactive
)
cleanup_test_repo "$TMPDIR_T8"

# --- Test 9: --help exits clean and shows usage ---
echo "Test 9: --help shows usage and exits 0"
TMPDIR_T9="$(setup_test_repo)"
(
    cd "$TMPDIR_T9"
    output=$(bash .aitask-scripts/aitask_crew_setmode.sh --help 2>&1)
    assert_contains "help mentions setmode" "Usage: ait crew setmode" "$output"
    assert_contains "help lists --mode" "--mode" "$output"
)
cleanup_test_repo "$TMPDIR_T9"

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
