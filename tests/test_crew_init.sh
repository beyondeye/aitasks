#!/usr/bin/env bash
# test_crew_init.sh - Automated tests for agentcrew init, addwork, and DAG validation.
# Run: bash tests/test_crew_init.sh

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

echo "=== AgentCrew Init/AddWork Tests ==="
echo ""

# --- Test 1: crew init creates branch, worktree, and meta files ---
echo "Test 1: crew init basic"
TMPDIR_T1="$(setup_test_repo)"
(
    cd "$TMPDIR_T1"
    output=$(bash .aitask-scripts/aitask_crew_init.sh --id testcrew --batch 2>&1)
    assert_contains "init outputs CREATED" "CREATED:testcrew" "$output"

    if git show-ref --verify refs/heads/crew-testcrew &>/dev/null; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: crew init branch not created"
    fi

    assert_file_exists "worktree meta created" ".aitask-crews/crew-testcrew/_crew_meta.yaml"
    assert_file_exists "worktree status created" ".aitask-crews/crew-testcrew/_crew_status.yaml"

    meta_id=$(grep '^id:' .aitask-crews/crew-testcrew/_crew_meta.yaml | sed 's/^id: *//')
    assert_eq "meta has correct id" "testcrew" "$meta_id"

    status=$(grep '^status:' .aitask-crews/crew-testcrew/_crew_status.yaml | sed 's/^status: *//')
    assert_eq "status is Initializing" "Initializing" "$status"
)
cleanup_test_repo "$TMPDIR_T1"

# --- Test 2: crew init with --add-type ---
echo "Test 2: crew init with --add-type"
TMPDIR_T2="$(setup_test_repo)"
(
    cd "$TMPDIR_T2"
    output=$(bash .aitask-scripts/aitask_crew_init.sh --id typed --add-type impl:claudecode/opus4_6 --add-type review:claudecode/sonnet4_6 --batch 2>&1)
    assert_contains "init outputs CREATED" "CREATED:typed" "$output"

    if grep -q "^  impl:" .aitask-crews/crew-typed/_crew_meta.yaml; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: agent_types missing 'impl' type"
    fi
    if grep -q "^  review:" .aitask-crews/crew-typed/_crew_meta.yaml; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: agent_types missing 'review' type"
    fi
)
cleanup_test_repo "$TMPDIR_T2"

# --- Test 3: crew init rejects invalid ID ---
echo "Test 3: crew init rejects invalid ID"
TMPDIR_T3="$(setup_test_repo)"
(
    cd "$TMPDIR_T3"
    assert_exit_nonzero "rejects uppercase" bash .aitask-scripts/aitask_crew_init.sh --id "UPPER" --batch
    assert_exit_nonzero "rejects spaces" bash .aitask-scripts/aitask_crew_init.sh --id "has space" --batch
    assert_exit_nonzero "rejects dots" bash .aitask-scripts/aitask_crew_init.sh --id "has.dot" --batch
)
cleanup_test_repo "$TMPDIR_T3"

# --- Test 4: crew init rejects duplicate ID ---
echo "Test 4: crew init rejects duplicate ID"
TMPDIR_T4="$(setup_test_repo)"
(
    cd "$TMPDIR_T4"
    bash .aitask-scripts/aitask_crew_init.sh --id dup --batch >/dev/null 2>&1
    assert_exit_nonzero "rejects duplicate crew" bash .aitask-scripts/aitask_crew_init.sh --id dup --batch
)
cleanup_test_repo "$TMPDIR_T4"

# --- Test 5: addwork creates all 7 agent files ---
echo "Test 5: addwork creates all 7 agent files"
TMPDIR_T5="$(setup_test_repo)"
(
    cd "$TMPDIR_T5"
    bash .aitask-scripts/aitask_crew_init.sh --id files --add-type impl:claudecode/opus4_6 --batch >/dev/null 2>&1

    echo "# Do this thing" > /tmp/test_work2do.md

    output=$(bash .aitask-scripts/aitask_crew_addwork.sh --crew files --name agent_a --work2do /tmp/test_work2do.md --type impl --batch 2>&1)
    assert_contains "addwork outputs ADDED" "ADDED:agent_a" "$output"

    WT=".aitask-crews/crew-files"
    assert_file_exists "work2do file" "$WT/agent_a_work2do.md"
    assert_file_exists "status file" "$WT/agent_a_status.yaml"
    assert_file_exists "input file" "$WT/agent_a_input.md"
    assert_file_exists "output file" "$WT/agent_a_output.md"
    assert_file_exists "instructions file" "$WT/agent_a_instructions.md"
    assert_file_exists "commands file" "$WT/agent_a_commands.yaml"
    assert_file_exists "alive file" "$WT/agent_a_alive.yaml"

    work2do_content=$(cat "$WT/agent_a_work2do.md")
    assert_eq "work2do content copied" "# Do this thing" "$work2do_content"

    agent_status=$(grep '^status:' "$WT/agent_a_status.yaml" | sed 's/^status: *//')
    assert_eq "agent status is Waiting" "Waiting" "$agent_status"

    meta_agents=$(grep '^agents:' "$WT/_crew_meta.yaml" | sed 's/^agents: *//')
    assert_contains "agent in meta agents list" "agent_a" "$meta_agents"

    rm -f /tmp/test_work2do.md
)
cleanup_test_repo "$TMPDIR_T5"

# --- Test 6: addwork validates agent name uniqueness ---
echo "Test 6: addwork rejects duplicate agent name"
TMPDIR_T6="$(setup_test_repo)"
(
    cd "$TMPDIR_T6"
    bash .aitask-scripts/aitask_crew_init.sh --id uniq --add-type impl:claudecode/opus4_6 --batch >/dev/null 2>&1
    bash .aitask-scripts/aitask_crew_addwork.sh --crew uniq --name agent_x --work2do /dev/null --type impl --batch >/dev/null 2>&1
    assert_exit_nonzero "rejects duplicate agent" bash .aitask-scripts/aitask_crew_addwork.sh --crew uniq --name agent_x --work2do /dev/null --type impl --batch
)
cleanup_test_repo "$TMPDIR_T6"

# --- Test 7: addwork validates type exists ---
echo "Test 7: addwork rejects unknown agent type"
TMPDIR_T7="$(setup_test_repo)"
(
    cd "$TMPDIR_T7"
    bash .aitask-scripts/aitask_crew_init.sh --id typechk --add-type impl:claudecode/opus4_6 --batch >/dev/null 2>&1
    assert_exit_nonzero "rejects unknown type" bash .aitask-scripts/aitask_crew_addwork.sh --crew typechk --name agent_y --work2do /dev/null --type nonexistent --batch
)
cleanup_test_repo "$TMPDIR_T7"

# --- Test 8: addwork with dependencies ---
echo "Test 8: addwork with valid dependencies"
TMPDIR_T8="$(setup_test_repo)"
(
    cd "$TMPDIR_T8"
    bash .aitask-scripts/aitask_crew_init.sh --id deps --add-type impl:claudecode/opus4_6 --batch >/dev/null 2>&1
    bash .aitask-scripts/aitask_crew_addwork.sh --crew deps --name upstream --work2do /dev/null --type impl --batch >/dev/null 2>&1
    output=$(bash .aitask-scripts/aitask_crew_addwork.sh --crew deps --name downstream --work2do /dev/null --type impl --depends upstream --batch 2>&1)
    assert_contains "addwork with deps succeeds" "ADDED:downstream" "$output"

    deps_yaml=$(grep '^depends_on:' .aitask-crews/crew-deps/downstream_status.yaml | sed 's/^depends_on: *//')
    assert_contains "depends_on contains upstream" "upstream" "$deps_yaml"
)
cleanup_test_repo "$TMPDIR_T8"

# --- Test 9: addwork rejects missing dependency ---
echo "Test 9: addwork rejects missing dependency"
TMPDIR_T9="$(setup_test_repo)"
(
    cd "$TMPDIR_T9"
    bash .aitask-scripts/aitask_crew_init.sh --id misdep --add-type impl:claudecode/opus4_6 --batch >/dev/null 2>&1
    assert_exit_nonzero "rejects missing dep" bash .aitask-scripts/aitask_crew_addwork.sh --crew misdep --name agent_z --work2do /dev/null --type impl --depends ghost --batch
)
cleanup_test_repo "$TMPDIR_T9"

# --- Test 10: DAG validation accepts valid graph ---
echo "Test 10: DAG validation accepts valid graph"
TMPDIR_T10="$(setup_test_repo)"
(
    cd "$TMPDIR_T10"
    bash .aitask-scripts/aitask_crew_init.sh --id dag --add-type impl:claudecode/opus4_6 --batch >/dev/null 2>&1
    bash .aitask-scripts/aitask_crew_addwork.sh --crew dag --name a --work2do /dev/null --type impl --batch >/dev/null 2>&1
    bash .aitask-scripts/aitask_crew_addwork.sh --crew dag --name b --work2do /dev/null --type impl --depends a --batch >/dev/null 2>&1
    output=$(bash .aitask-scripts/aitask_crew_addwork.sh --crew dag --name c --work2do /dev/null --type impl --depends a,b --batch 2>&1)
    assert_contains "valid DAG accepted" "ADDED:c" "$output"
)
cleanup_test_repo "$TMPDIR_T10"

# --- Test 11: addwork with /dev/null work2do ---
echo "Test 11: addwork with /dev/null"
TMPDIR_T11="$(setup_test_repo)"
(
    cd "$TMPDIR_T11"
    bash .aitask-scripts/aitask_crew_init.sh --id devnull --add-type impl:claudecode/opus4_6 --batch >/dev/null 2>&1
    output=$(bash .aitask-scripts/aitask_crew_addwork.sh --crew devnull --name empty_agent --work2do /dev/null --type impl --batch 2>&1)
    assert_contains "addwork with /dev/null succeeds" "ADDED:empty_agent" "$output"

    wc_lines=$(wc -l < ".aitask-crews/crew-devnull/empty_agent_work2do.md" | tr -d ' ')
    assert_eq "work2do is empty" "1" "$wc_lines"
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
