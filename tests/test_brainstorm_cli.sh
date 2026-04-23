#!/usr/bin/env bash
# test_brainstorm_cli.sh - Automated tests for brainstorm CLI scripts.
# Run: bash tests/test_brainstorm_cli.sh

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

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [[ "$expected" == "$actual" ]]; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    if echo "$actual" | grep -qi "$expected"; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_file_exists() {
    local desc="$1" file="$2"
    if [[ -f "$file" ]]; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: $desc (file '$file' does not exist)"
    fi
}

assert_dir_exists() {
    local desc="$1" dir="$2"
    if [[ -d "$dir" ]]; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: $desc (directory '$dir' does not exist)"
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

        mkdir -p .aitask-scripts/lib .aitask-scripts/brainstorm .aitask-scripts/agentcrew
        mkdir -p aitasks/metadata

        # Copy required library files
        cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/

        # Copy brainstorm scripts
        cp "$PROJECT_DIR/.aitask-scripts/aitask_brainstorm_init.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_brainstorm_status.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_brainstorm_archive.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_brainstorm_delete.sh" .aitask-scripts/
        chmod +x .aitask-scripts/aitask_brainstorm_*.sh

        # Copy crew scripts (needed by brainstorm init/archive)
        cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_init.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_cleanup.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_status.sh" .aitask-scripts/
        chmod +x .aitask-scripts/aitask_crew_init.sh .aitask-scripts/aitask_crew_cleanup.sh .aitask-scripts/aitask_crew_status.sh

        # Copy query_files (needed by brainstorm init to resolve tasks)
        cp "$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh" .aitask-scripts/
        chmod +x .aitask-scripts/aitask_query_files.sh

        # Copy Python modules
        cp "$PROJECT_DIR/.aitask-scripts/brainstorm/"*.py .aitask-scripts/brainstorm/
        cp "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_utils.py" .aitask-scripts/agentcrew/
        cp "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_status.py" .aitask-scripts/agentcrew/
        touch .aitask-scripts/agentcrew/__init__.py
        # __init__.py for brainstorm should already exist from copy

        # Create userconfig
        echo "email: test@test.com" > aitasks/metadata/userconfig.yaml

        # Create a dummy task file
        cat > aitasks/t999_test_brainstorm.md <<'TASK'
---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [test]
---

## Test task for brainstorm integration testing.
TASK

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

# Detect Python
VENV_PYTHON="$HOME/.aitask/venv/bin/python"
if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="${PYTHON:-python3}"
fi

# ============================================================
# Tests
# ============================================================

echo "=== Brainstorm CLI Tests ==="
echo ""

# --- Test 1: brainstorm init basic ---
echo "Test 1: brainstorm init basic"
TMPDIR_T1="$(setup_test_repo)"
(
    cd "$TMPDIR_T1"
    output=$(bash .aitask-scripts/aitask_brainstorm_init.sh 999 2>&1)
    assert_contains "init outputs INITIALIZED" "INITIALIZED:999" "$output"

    WT=".aitask-crews/crew-brainstorm-999"
    assert_file_exists "br_session.yaml created" "$WT/br_session.yaml"
    assert_file_exists "br_graph_state.yaml created" "$WT/br_graph_state.yaml"
    assert_file_exists "br_groups.yaml created" "$WT/br_groups.yaml"
    assert_dir_exists "br_nodes/ created" "$WT/br_nodes"
    assert_dir_exists "br_proposals/ created" "$WT/br_proposals"
    assert_dir_exists "br_plans/ created" "$WT/br_plans"

    # Verify session content
    task_id=$(grep '^task_id:' "$WT/br_session.yaml" | sed 's/^task_id: *//')
    assert_eq "session has correct task_id" "999" "$task_id"

    status=$(grep '^status:' "$WT/br_session.yaml" | sed 's/^status: *//')
    assert_eq "session status is init" "init" "$status"
)
cleanup_test_repo "$TMPDIR_T1"

# --- Test 2: brainstorm init rejects missing task ---
echo "Test 2: brainstorm init rejects missing task"
TMPDIR_T2="$(setup_test_repo)"
(
    cd "$TMPDIR_T2"
    assert_exit_nonzero "rejects non-existent task" bash .aitask-scripts/aitask_brainstorm_init.sh 12345
)
cleanup_test_repo "$TMPDIR_T2"

# --- Test 3: brainstorm init rejects duplicate ---
echo "Test 3: brainstorm init rejects duplicate session"
TMPDIR_T3="$(setup_test_repo)"
(
    cd "$TMPDIR_T3"
    bash .aitask-scripts/aitask_brainstorm_init.sh 999 >/dev/null 2>&1
    assert_exit_nonzero "rejects duplicate session" bash .aitask-scripts/aitask_brainstorm_init.sh 999
)
cleanup_test_repo "$TMPDIR_T3"

# --- Test 4: brainstorm status shows session info ---
echo "Test 4: brainstorm status shows session info"
TMPDIR_T4="$(setup_test_repo)"
(
    cd "$TMPDIR_T4"
    bash .aitask-scripts/aitask_brainstorm_init.sh 999 >/dev/null 2>&1
    output=$(bash .aitask-scripts/aitask_brainstorm_status.sh 999 2>&1)
    assert_contains "status shows task_id" "999" "$output"
    assert_contains "status shows status" "init" "$output"
)
cleanup_test_repo "$TMPDIR_T4"

# --- Test 5: brainstorm list shows sessions ---
echo "Test 5: brainstorm list shows sessions"
TMPDIR_T5="$(setup_test_repo)"
(
    cd "$TMPDIR_T5"
    bash .aitask-scripts/aitask_brainstorm_init.sh 999 >/dev/null 2>&1
    output=$(bash .aitask-scripts/aitask_brainstorm_status.sh --list 2>&1)
    assert_contains "list shows task num" "999" "$output"
    assert_contains "list shows status" "init" "$output"
)
cleanup_test_repo "$TMPDIR_T5"

# --- Test 6: brainstorm status with no session ---
echo "Test 6: brainstorm status with no session"
TMPDIR_T6="$(setup_test_repo)"
(
    cd "$TMPDIR_T6"
    assert_exit_nonzero "status fails for non-existent session" bash .aitask-scripts/aitask_brainstorm_status.sh 12345
)
cleanup_test_repo "$TMPDIR_T6"

# --- Test 7: brainstorm_cli.py exists subcommand ---
echo "Test 7: brainstorm_cli.py exists subcommand"
TMPDIR_T7="$(setup_test_repo)"
(
    cd "$TMPDIR_T7"
    # Before init: NOT_EXISTS
    output=$("$PYTHON" .aitask-scripts/brainstorm/brainstorm_cli.py exists --task-num 999 2>&1)
    assert_eq "exists returns NOT_EXISTS before init" "NOT_EXISTS" "$output"

    # After init: EXISTS
    bash .aitask-scripts/aitask_brainstorm_init.sh 999 >/dev/null 2>&1
    output=$("$PYTHON" .aitask-scripts/brainstorm/brainstorm_cli.py exists --task-num 999 2>&1)
    assert_eq "exists returns EXISTS after init" "EXISTS" "$output"
)
cleanup_test_repo "$TMPDIR_T7"

# --- Test 8: brainstorm help ---
echo "Test 8: brainstorm init --help"
TMPDIR_T8="$(setup_test_repo)"
(
    cd "$TMPDIR_T8"
    output=$(bash .aitask-scripts/aitask_brainstorm_init.sh --help 2>&1)
    assert_contains "help shows usage" "Usage" "$output"
    assert_contains "help shows task_num" "task_num" "$output"
)
cleanup_test_repo "$TMPDIR_T8"

# --- Test 9: brainstorm delete removes session ---
echo "Test 9: brainstorm delete removes session"
TMPDIR_T9="$(setup_test_repo)"
(
    cd "$TMPDIR_T9"
    bash .aitask-scripts/aitask_brainstorm_init.sh 999 >/dev/null 2>&1
    # Verify session exists
    output=$("$PYTHON" .aitask-scripts/brainstorm/brainstorm_cli.py exists --task-num 999 2>&1)
    assert_eq "session exists before delete" "EXISTS" "$output"

    # Delete with --yes to skip confirmation
    output=$(bash .aitask-scripts/aitask_brainstorm_delete.sh 999 --yes 2>&1)
    assert_contains "delete outputs DELETED" "DELETED:999" "$output"

    # Verify session is gone
    output=$("$PYTHON" .aitask-scripts/brainstorm/brainstorm_cli.py exists --task-num 999 2>&1)
    assert_eq "session gone after delete" "NOT_EXISTS" "$output"
)
cleanup_test_repo "$TMPDIR_T9"

# --- Test 10: brainstorm delete rejects non-existent session ---
echo "Test 10: brainstorm delete rejects non-existent session"
TMPDIR_T10="$(setup_test_repo)"
(
    cd "$TMPDIR_T10"
    assert_exit_nonzero "delete rejects non-existent session" bash .aitask-scripts/aitask_brainstorm_delete.sh 12345 --yes
)
cleanup_test_repo "$TMPDIR_T10"

# --- Test 11: brainstorm archive succeeds with no-plan session ---
echo "Test 11: brainstorm archive handles no-plan HEAD gracefully"
TMPDIR_T11="$(setup_test_repo)"
(
    cd "$TMPDIR_T11"
    bash .aitask-scripts/aitask_brainstorm_init.sh 999 >/dev/null 2>&1
    # Archive without generating any plan — HEAD node has no plan_file
    output=$(bash .aitask-scripts/aitask_brainstorm_archive.sh 999 2>&1)
    assert_contains "archive outputs NO_PLAN warning" "NO_PLAN" "$output"
    assert_contains "archive outputs ARCHIVED" "ARCHIVED:999" "$output"
)
cleanup_test_repo "$TMPDIR_T11"

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
