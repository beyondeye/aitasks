#!/usr/bin/env bash
# test_crew_report.sh - Automated tests for agentcrew report and cleanup.
# Run: bash tests/test_crew_report.sh

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

assert_not_contains() {
    local desc="$1" expected="$2" actual="$3"
    if echo "$actual" | grep -qi "$expected"; then
        _inc_fail
        echo "FAIL: $desc (expected output NOT containing '$expected', got '$actual')"
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

# --- Setup: create isolated git repo with crew ---

setup_test_repo() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    (
        cd "$tmpdir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"

        mkdir -p aitasks/metadata

        # Mirror the full .aitask-scripts/ tree so transitive deps (e.g.
        # lib/launch_modes_sh.sh) are present. Hand-curated copy lists drift
        # silently as new sources/imports are added.
        cp -R "$PROJECT_DIR/.aitask-scripts" .aitask-scripts
        find .aitask-scripts -type d -name __pycache__ -prune -exec rm -rf {} +
        chmod +x .aitask-scripts/aitask_crew_init.sh .aitask-scripts/aitask_crew_addwork.sh
        chmod +x .aitask-scripts/aitask_crew_cleanup.sh .aitask-scripts/aitask_crew_report.sh

        echo "email: test@test.com" > aitasks/metadata/userconfig.yaml

        git add -A
        git commit -m "Initial setup" --quiet
    )

    echo "$tmpdir"
}

# Setup a crew with agents in known state (for report tests)
setup_crew_with_agents() {
    local tmpdir="$1"
    (
        cd "$tmpdir"
        bash .aitask-scripts/aitask_crew_init.sh --id rptcrew --add-type impl:claudecode/opus4_6 --batch >/dev/null 2>&1

        echo "# Task A work" > /tmp/test_work2do_a.md
        echo "# Task B work" > /tmp/test_work2do_b.md
        echo "# Task C work" > /tmp/test_work2do_c.md

        bash .aitask-scripts/aitask_crew_addwork.sh --crew rptcrew --name agent_a --work2do /tmp/test_work2do_a.md --type impl --batch >/dev/null 2>&1
        bash .aitask-scripts/aitask_crew_addwork.sh --crew rptcrew --name agent_b --work2do /tmp/test_work2do_b.md --type impl --depends agent_a --batch >/dev/null 2>&1
        bash .aitask-scripts/aitask_crew_addwork.sh --crew rptcrew --name agent_c --work2do /tmp/test_work2do_c.md --type impl --depends agent_a,agent_b --batch >/dev/null 2>&1

        # Write some output for agent_a
        echo "Agent A completed its work successfully." > .aitask-crews/crew-rptcrew/agent_a_output.md

        # Mark agent_a as Completed (manually update status yaml)
        local status_file=".aitask-crews/crew-rptcrew/agent_a_status.yaml"
        local tmp_status
        tmp_status=$(mktemp "${TMPDIR:-/tmp}/ait_status_XXXXXX")
        sed 's/^status: .*/status: Completed/' "$status_file" > "$tmp_status"
        mv "$tmp_status" "$status_file"

        rm -f /tmp/test_work2do_a.md /tmp/test_work2do_b.md /tmp/test_work2do_c.md
    )
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

echo "=== AgentCrew Report/Cleanup Tests ==="
echo ""

# --- Test 1: report summary batch output ---
echo "Test 1: report summary batch output"
TMPDIR_T1="$(setup_test_repo)"
(
    cd "$TMPDIR_T1"
    setup_crew_with_agents "$TMPDIR_T1"
    export PYTHONPATH=".aitask-scripts"
    output=$(python3 .aitask-scripts/agentcrew/agentcrew_report.py --batch summary --crew rptcrew 2>&1)
    assert_contains "batch has CREW_ID" "CREW_ID:rptcrew" "$output"
    assert_contains "batch has CREW_STATUS" "CREW_STATUS:" "$output"
    assert_contains "batch has agent_a" "AGENT:agent_a" "$output"
    assert_contains "batch has agent_b" "AGENT:agent_b" "$output"
    assert_contains "batch has agent_c" "AGENT:agent_c" "$output"
)
cleanup_test_repo "$TMPDIR_T1"

# --- Test 2: report summary interactive output ---
echo "Test 2: report summary interactive output"
TMPDIR_T2="$(setup_test_repo)"
(
    cd "$TMPDIR_T2"
    setup_crew_with_agents "$TMPDIR_T2"
    export PYTHONPATH=".aitask-scripts"
    output=$(python3 .aitask-scripts/agentcrew/agentcrew_report.py summary --crew rptcrew 2>&1)
    assert_contains "interactive has crew name" "rptcrew" "$output"
    assert_contains "interactive has agent_a" "agent_a" "$output"
    assert_contains "interactive has Completed" "Completed" "$output"
)
cleanup_test_repo "$TMPDIR_T2"

# --- Test 3: report detail batch output ---
echo "Test 3: report detail batch output"
TMPDIR_T3="$(setup_test_repo)"
(
    cd "$TMPDIR_T3"
    setup_crew_with_agents "$TMPDIR_T3"
    export PYTHONPATH=".aitask-scripts"
    output=$(python3 .aitask-scripts/agentcrew/agentcrew_report.py --batch detail --crew rptcrew --agent agent_a 2>&1)
    assert_contains "detail has AGENT" "AGENT:agent_a" "$output"
    assert_contains "detail has STATUS" "STATUS:Completed" "$output"
    assert_contains "detail has HAS_WORK2DO" "HAS_WORK2DO:true" "$output"
    assert_contains "detail has HAS_OUTPUT" "HAS_OUTPUT:true" "$output"
)
cleanup_test_repo "$TMPDIR_T3"

# --- Test 4: report output aggregates in dependency order ---
echo "Test 4: report output aggregation order"
TMPDIR_T4="$(setup_test_repo)"
(
    cd "$TMPDIR_T4"
    setup_crew_with_agents "$TMPDIR_T4"
    # Add output for agent_b too
    echo "Agent B output here." > .aitask-crews/crew-rptcrew/agent_b_output.md

    export PYTHONPATH=".aitask-scripts"
    output=$(python3 .aitask-scripts/agentcrew/agentcrew_report.py --batch output --crew rptcrew 2>&1)
    assert_contains "output has agent_a section" "OUTPUT_AGENT:agent_a" "$output"
    assert_contains "output has agent_b section" "OUTPUT_AGENT:agent_b" "$output"
    # agent_a should come before agent_b (it has no deps)
    pos_a=$(echo "$output" | grep -n "OUTPUT_AGENT:agent_a" | head -1 | cut -d: -f1)
    pos_b=$(echo "$output" | grep -n "OUTPUT_AGENT:agent_b" | head -1 | cut -d: -f1)
    if [[ "$pos_a" -lt "$pos_b" ]]; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: agent_a should appear before agent_b in topo order"
    fi
)
cleanup_test_repo "$TMPDIR_T4"

# --- Test 5: report list ---
echo "Test 5: report list"
TMPDIR_T5="$(setup_test_repo)"
(
    cd "$TMPDIR_T5"
    setup_crew_with_agents "$TMPDIR_T5"
    export PYTHONPATH=".aitask-scripts"
    output=$(python3 .aitask-scripts/agentcrew/agentcrew_report.py --batch list 2>&1)
    assert_contains "list has CREW" "CREW:rptcrew" "$output"
    assert_contains "list has AGENTS" "AGENTS:3" "$output"
)
cleanup_test_repo "$TMPDIR_T5"

# --- Test 6: report for nonexistent crew ---
echo "Test 6: report for nonexistent crew"
TMPDIR_T6="$(setup_test_repo)"
(
    cd "$TMPDIR_T6"
    export PYTHONPATH=".aitask-scripts"
    assert_exit_nonzero "summary for nonexistent crew" python3 .aitask-scripts/agentcrew/agentcrew_report.py summary --crew nosuch
)
cleanup_test_repo "$TMPDIR_T6"

# --- Test 7: cleanup removes completed crew worktree ---
echo "Test 7: cleanup removes completed crew"
TMPDIR_T7="$(setup_test_repo)"
(
    cd "$TMPDIR_T7"
    bash .aitask-scripts/aitask_crew_init.sh --id cleanme --batch >/dev/null 2>&1
    # Set crew status to Completed
    tmp_status=$(mktemp "${TMPDIR:-/tmp}/ait_status_XXXXXX")
    sed 's/^status: .*/status: Completed/' ".aitask-crews/crew-cleanme/_crew_status.yaml" > "$tmp_status"
    mv "$tmp_status" ".aitask-crews/crew-cleanme/_crew_status.yaml"

    output=$(bash .aitask-scripts/aitask_crew_cleanup.sh --crew cleanme --batch 2>&1)
    assert_contains "cleanup outputs CLEANED" "CLEANED:cleanme" "$output"

    if [[ -d ".aitask-crews/crew-cleanme" ]]; then
        _inc_fail
        echo "FAIL: worktree directory should be removed"
    else
        _inc_pass
    fi
)
cleanup_test_repo "$TMPDIR_T7"

# --- Test 8: cleanup refuses non-terminal crew ---
echo "Test 8: cleanup refuses non-terminal crew"
TMPDIR_T8="$(setup_test_repo)"
(
    cd "$TMPDIR_T8"
    bash .aitask-scripts/aitask_crew_init.sh --id running --batch >/dev/null 2>&1
    # Status is Initializing (non-terminal) by default
    output=$(bash .aitask-scripts/aitask_crew_cleanup.sh --crew running --batch 2>&1) || true
    assert_contains "cleanup outputs NOT_TERMINAL" "NOT_TERMINAL:running" "$output"

    if [[ -d ".aitask-crews/crew-running" ]]; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: worktree should still exist for non-terminal crew"
    fi
)
cleanup_test_repo "$TMPDIR_T8"

# --- Test 9: cleanup --all-completed only cleans terminal crews ---
echo "Test 9: cleanup --all-completed"
TMPDIR_T9="$(setup_test_repo)"
(
    cd "$TMPDIR_T9"
    bash .aitask-scripts/aitask_crew_init.sh --id done1 --batch >/dev/null 2>&1
    bash .aitask-scripts/aitask_crew_init.sh --id active1 --batch >/dev/null 2>&1

    # Set done1 to Completed
    tmp_status=$(mktemp "${TMPDIR:-/tmp}/ait_status_XXXXXX")
    sed 's/^status: .*/status: Completed/' ".aitask-crews/crew-done1/_crew_status.yaml" > "$tmp_status"
    mv "$tmp_status" ".aitask-crews/crew-done1/_crew_status.yaml"

    output=$(bash .aitask-scripts/aitask_crew_cleanup.sh --all-completed --batch 2>&1)
    assert_contains "cleaned done1" "CLEANED:done1" "$output"
    assert_contains "refused active1" "NOT_TERMINAL:active1" "$output"

    if [[ -d ".aitask-crews/crew-active1" ]]; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: active crew should still exist"
    fi
)
cleanup_test_repo "$TMPDIR_T9"

# --- Test 10: cleanup --delete-branch ---
echo "Test 10: cleanup --delete-branch"
TMPDIR_T10="$(setup_test_repo)"
(
    cd "$TMPDIR_T10"
    bash .aitask-scripts/aitask_crew_init.sh --id delbranch --batch >/dev/null 2>&1

    # Set to Completed
    tmp_status=$(mktemp "${TMPDIR:-/tmp}/ait_status_XXXXXX")
    sed 's/^status: .*/status: Completed/' ".aitask-crews/crew-delbranch/_crew_status.yaml" > "$tmp_status"
    mv "$tmp_status" ".aitask-crews/crew-delbranch/_crew_status.yaml"

    output=$(bash .aitask-scripts/aitask_crew_cleanup.sh --crew delbranch --delete-branch --batch 2>&1)
    assert_contains "cleanup outputs CLEANED" "CLEANED:delbranch" "$output"

    if git show-ref --verify refs/heads/crew-delbranch &>/dev/null; then
        _inc_fail
        echo "FAIL: branch should be deleted"
    else
        _inc_pass
    fi
)
cleanup_test_repo "$TMPDIR_T10"

# --- Test 11: report no crews ---
echo "Test 11: report list with no crews"
TMPDIR_T11="$(setup_test_repo)"
(
    cd "$TMPDIR_T11"
    export PYTHONPATH=".aitask-scripts"
    output=$(python3 .aitask-scripts/agentcrew/agentcrew_report.py --batch list 2>&1)
    assert_contains "no crews" "NO_CREWS" "$output"
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
