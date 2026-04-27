#!/usr/bin/env bash
# test_crew_status.sh - Tests for agentcrew status, heartbeat, and command system.
# Run: bash tests/test_crew_status.sh

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
    local desc="$1" unexpected="$2" actual="$3"
    if echo "$actual" | grep -qi "$unexpected"; then
        _inc_fail
        echo "FAIL: $desc (output should NOT contain '$unexpected')"
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

# --- Find Python ---
find_python() {
    local venv_py="$HOME/.aitask/venv/bin/python"
    if [[ -x "$venv_py" ]]; then
        echo "$venv_py"
    elif command -v python3 &>/dev/null; then
        echo "python3"
    else
        echo ""
    fi
}

PYTHON="$(find_python)"

# --- Setup: create isolated git repo with a crew and agents ---

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
        chmod +x .aitask-scripts/aitask_crew_command.sh 2>/dev/null || true

        echo "email: test@test.com" > aitasks/metadata/userconfig.yaml

        git add -A
        git commit -m "Initial setup" --quiet
    )

    echo "$tmpdir"
}

# Create a crew with two agents (planner depends on nothing, coder depends on planner)
setup_crew_with_agents() {
    local tmpdir="$1"
    (
        cd "$tmpdir"

        # Init crew with agent type
        bash .aitask-scripts/aitask_crew_init.sh --id testcrew --add-type impl:claudecode/opus4_6 --batch >/dev/null 2>&1

        # Create work2do files
        echo "# Plan the feature" > /tmp/plan_work2do.md
        echo "# Code the feature" > /tmp/code_work2do.md

        # Add agents
        bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew --name planner --work2do /tmp/plan_work2do.md --type impl --batch >/dev/null 2>&1
        bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew --name coder --work2do /tmp/code_work2do.md --type impl --depends planner --batch >/dev/null 2>&1

        rm -f /tmp/plan_work2do.md /tmp/code_work2do.md
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

echo "=== AgentCrew Status/Heartbeat/Command Tests ==="
echo ""

# --- Test 1: Python module compiles ---
echo "Test 1: Python modules compile"
if [[ -n "$PYTHON" ]]; then
    if $PYTHON -m py_compile "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_utils.py" 2>/dev/null; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: agentcrew_utils.py does not compile"
    fi
    if $PYTHON -m py_compile "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_status.py" 2>/dev/null; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: agentcrew_status.py does not compile"
    fi
else
    echo "SKIP: Python not available"
    _inc_pass; _inc_pass
fi

# --- Test 2: Python utils — status validation ---
echo "Test 2: Status transition validation"
if [[ -n "$PYTHON" ]]; then
    result=$($PYTHON -c "
import sys; sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts')
from agentcrew.agentcrew_utils import validate_agent_transition
print(validate_agent_transition('Waiting', 'Ready'))
print(validate_agent_transition('Ready', 'Running'))
print(validate_agent_transition('Running', 'Completed'))
print(validate_agent_transition('Running', 'Paused'))
print(validate_agent_transition('Paused', 'Running'))
# Invalid transitions
print(validate_agent_transition('Waiting', 'Completed'))
print(validate_agent_transition('Completed', 'Running'))
print(validate_agent_transition('Ready', 'Completed'))
# Error recovery and self-reported terminal transitions (t671: heartbeat
# freshness no longer participates in lifecycle transitions).
print(validate_agent_transition('Running', 'Error'))
print(validate_agent_transition('Running', 'Aborted'))
print(validate_agent_transition('Error', 'Running'))
print(validate_agent_transition('Error', 'Completed'))
# MissedHeartbeat is removed from the namespace — it must reject all transitions.
print(validate_agent_transition('Running', 'MissedHeartbeat'))
print(validate_agent_transition('MissedHeartbeat', 'Running'))
" 2>&1)
    assert_eq "Waiting->Ready valid" "True" "$(echo "$result" | sed -n '1p')"
    assert_eq "Ready->Running valid" "True" "$(echo "$result" | sed -n '2p')"
    assert_eq "Running->Completed valid" "True" "$(echo "$result" | sed -n '3p')"
    assert_eq "Running->Paused valid" "True" "$(echo "$result" | sed -n '4p')"
    assert_eq "Paused->Running valid" "True" "$(echo "$result" | sed -n '5p')"
    assert_eq "Waiting->Completed invalid" "False" "$(echo "$result" | sed -n '6p')"
    assert_eq "Completed->Running invalid" "False" "$(echo "$result" | sed -n '7p')"
    assert_eq "Ready->Completed invalid" "False" "$(echo "$result" | sed -n '8p')"
    assert_eq "Running->Error valid (self-reported)" "True" "$(echo "$result" | sed -n '9p')"
    assert_eq "Running->Aborted valid (self-reported)" "True" "$(echo "$result" | sed -n '10p')"
    assert_eq "Error->Running valid (recovery)" "True" "$(echo "$result" | sed -n '11p')"
    assert_eq "Error->Completed valid (direct recovery)" "True" "$(echo "$result" | sed -n '12p')"
    assert_eq "Running->MissedHeartbeat invalid (removed)" "False" "$(echo "$result" | sed -n '13p')"
    assert_eq "MissedHeartbeat->Running invalid (removed)" "False" "$(echo "$result" | sed -n '14p')"
else
    echo "SKIP: Python not available"
    for _ in $(seq 14); do _inc_pass; done
fi

# --- Test 3: Python utils — crew status computation ---
echo "Test 3: Crew status computation"
if [[ -n "$PYTHON" ]]; then
    result=$($PYTHON -c "
import sys; sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts')
from agentcrew.agentcrew_utils import compute_crew_status
print(compute_crew_status(['Completed', 'Completed']))
print(compute_crew_status(['Running', 'Waiting']))
print(compute_crew_status(['Waiting', 'Waiting']))
print(compute_crew_status(['Error', 'Completed']))
print(compute_crew_status([]))
print(compute_crew_status(['Paused', 'Completed']))
# A heartbeat-stale Running agent stays Running (status is self-reported now);
# crew rollup sees it as Running as expected (t671).
print(compute_crew_status(['Running', 'Completed']))
print(compute_crew_status(['Error', 'Running']))
" 2>&1)
    assert_eq "all completed -> Completed" "Completed" "$(echo "$result" | sed -n '1p')"
    assert_eq "any running -> Running" "Running" "$(echo "$result" | sed -n '2p')"
    assert_eq "all waiting -> Initializing" "Initializing" "$(echo "$result" | sed -n '3p')"
    assert_eq "error no running -> Error" "Error" "$(echo "$result" | sed -n '4p')"
    assert_eq "empty -> Initializing" "Initializing" "$(echo "$result" | sed -n '5p')"
    assert_eq "paused no running -> Paused" "Paused" "$(echo "$result" | sed -n '6p')"
    assert_eq "Running + Completed mix -> Running" "Running" "$(echo "$result" | sed -n '7p')"
    assert_eq "Error suppressed by Running sibling" "Running" "$(echo "$result" | sed -n '8p')"
else
    echo "SKIP: Python not available"
    for _ in $(seq 8); do _inc_pass; done
fi

# --- Test 4: Python utils — DAG topo sort and cycle detection ---
echo "Test 4: DAG topo sort and cycle detection"
if [[ -n "$PYTHON" ]]; then
    result=$($PYTHON -c "
import sys; sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts')
from agentcrew.agentcrew_utils import topo_sort, detect_cycles
# Valid DAG
order = topo_sort({'a': [], 'b': ['a'], 'c': ['b']})
print(','.join(order))
# Cycle detection on valid graph
print(detect_cycles({'a': [], 'b': ['a']}))
# Cycle detection on graph with cycle
cycle = detect_cycles({'a': ['b'], 'b': ['a']})
print(sorted(cycle))
" 2>&1)
    assert_eq "topo sort order" "a,b,c" "$(echo "$result" | sed -n '1p')"
    assert_eq "no cycle in valid DAG" "None" "$(echo "$result" | sed -n '2p')"
    assert_contains "cycle detected" "a" "$(echo "$result" | sed -n '3p')"
else
    echo "SKIP: Python not available"
    for _ in $(seq 3); do _inc_pass; done
fi

# --- Test 5: Python utils — heartbeat check ---
echo "Test 5: Heartbeat alive check"
if [[ -n "$PYTHON" ]]; then
    result=$($PYTHON -c "
import sys; sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts')
from agentcrew.agentcrew_utils import check_agent_alive, write_yaml
import tempfile, os
from datetime import datetime, timezone, timedelta

# Create a fresh heartbeat file
td = tempfile.mkdtemp()
alive_path = os.path.join(td, 'test_alive.yaml')

# Recent heartbeat (should be alive)
now = datetime.now(timezone.utc)
write_yaml(alive_path, {'last_heartbeat': now.strftime('%Y-%m-%d %H:%M:%S')})
print(check_agent_alive(alive_path, 300))

# Old heartbeat (should be stale)
old = (now - timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
write_yaml(alive_path, {'last_heartbeat': old})
print(check_agent_alive(alive_path, 300))

# No heartbeat
write_yaml(alive_path, {'last_heartbeat': None})
print(check_agent_alive(alive_path, 300))

import shutil; shutil.rmtree(td)
" 2>&1)
    assert_eq "recent heartbeat alive" "True" "$(echo "$result" | sed -n '1p')"
    assert_eq "old heartbeat stale" "False" "$(echo "$result" | sed -n '2p')"
    assert_eq "no heartbeat stale" "False" "$(echo "$result" | sed -n '3p')"
else
    echo "SKIP: Python not available"
    for _ in $(seq 3); do _inc_pass; done
fi

# --- Test 6: Python utils — ready agents detection ---
echo "Test 6: Ready agents detection"
if [[ -n "$PYTHON" ]]; then
    result=$($PYTHON -c "
import sys; sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts')
from agentcrew.agentcrew_utils import get_ready_agents, write_yaml
import tempfile, os

td = tempfile.mkdtemp()

# Agent a: Waiting, no deps -> should be ready
write_yaml(os.path.join(td, 'a_status.yaml'), {
    'agent_name': 'a', 'status': 'Waiting', 'depends_on': []
})
# Agent b: Waiting, depends on a (not completed) -> not ready
write_yaml(os.path.join(td, 'b_status.yaml'), {
    'agent_name': 'b', 'status': 'Waiting', 'depends_on': ['a']
})

ready = get_ready_agents(td)
print(','.join(ready))

# Now mark a as Completed
write_yaml(os.path.join(td, 'a_status.yaml'), {
    'agent_name': 'a', 'status': 'Completed', 'depends_on': []
})

ready = get_ready_agents(td)
print(','.join(ready))

import shutil; shutil.rmtree(td)
" 2>&1)
    assert_eq "a is ready (no deps)" "a" "$(echo "$result" | sed -n '1p')"
    assert_eq "b is ready (a completed)" "b" "$(echo "$result" | sed -n '2p')"
else
    echo "SKIP: Python not available"
    for _ in $(seq 2); do _inc_pass; done
fi

# --- Test 7: Status CLI — get crew status ---
echo "Test 7: Status CLI — get crew status"
if [[ -n "$PYTHON" ]]; then
    TMPDIR_T7="$(setup_test_repo)"
    setup_crew_with_agents "$TMPDIR_T7"
    (
        cd "$TMPDIR_T7"
        export PYTHONPATH=".aitask-scripts"
        output=$($PYTHON .aitask-scripts/agentcrew/agentcrew_status.py --crew testcrew get 2>&1)
        assert_contains "crew status shown" "CREW_STATUS:" "$output"
        assert_contains "crew progress shown" "CREW_PROGRESS:" "$output"

        # Get agent status
        output=$($PYTHON .aitask-scripts/agentcrew/agentcrew_status.py --crew testcrew --agent planner get 2>&1)
        assert_contains "agent status shown" "AGENT_STATUS:Waiting" "$output"
        assert_contains "agent progress shown" "AGENT_PROGRESS:0" "$output"
    )
    cleanup_test_repo "$TMPDIR_T7"
else
    echo "SKIP: Python not available"
    for _ in $(seq 4); do _inc_pass; done
fi

# --- Test 8: Status CLI — set status with valid transition ---
echo "Test 8: Status CLI — set status (valid transition)"
if [[ -n "$PYTHON" ]]; then
    TMPDIR_T8="$(setup_test_repo)"
    setup_crew_with_agents "$TMPDIR_T8"
    (
        cd "$TMPDIR_T8"
        export PYTHONPATH=".aitask-scripts"

        # Waiting -> Ready
        output=$($PYTHON .aitask-scripts/agentcrew/agentcrew_status.py --crew testcrew --agent planner set --status Ready 2>&1)
        assert_contains "set Waiting->Ready" "STATUS_SET:planner:Waiting:Ready" "$output"

        # Ready -> Running
        output=$($PYTHON .aitask-scripts/agentcrew/agentcrew_status.py --crew testcrew --agent planner set --status Running 2>&1)
        assert_contains "set Ready->Running" "STATUS_SET:planner:Ready:Running" "$output"

        # Running -> Completed
        output=$($PYTHON .aitask-scripts/agentcrew/agentcrew_status.py --crew testcrew --agent planner set --status Completed 2>&1)
        assert_contains "set Running->Completed" "STATUS_SET:planner:Running:Completed" "$output"

        # Verify crew status recomputed (planner Completed, coder Waiting -> Running)
        output=$($PYTHON .aitask-scripts/agentcrew/agentcrew_status.py --crew testcrew get 2>&1)
        assert_contains "crew status recomputed" "CREW_STATUS:Running" "$output"
    )
    cleanup_test_repo "$TMPDIR_T8"
else
    echo "SKIP: Python not available"
    for _ in $(seq 4); do _inc_pass; done
fi

# --- Test 9: Status CLI — reject invalid transition ---
echo "Test 9: Status CLI — reject invalid transition"
if [[ -n "$PYTHON" ]]; then
    TMPDIR_T9="$(setup_test_repo)"
    setup_crew_with_agents "$TMPDIR_T9"
    (
        cd "$TMPDIR_T9"
        export PYTHONPATH=".aitask-scripts"

        # Waiting -> Completed (invalid)
        assert_exit_nonzero "reject Waiting->Completed" \
            $PYTHON .aitask-scripts/agentcrew/agentcrew_status.py --crew testcrew --agent planner set --status Completed
    )
    cleanup_test_repo "$TMPDIR_T9"
else
    echo "SKIP: Python not available"
    _inc_pass
fi

# --- Test 10: Status CLI — heartbeat ---
echo "Test 10: Status CLI — heartbeat"
if [[ -n "$PYTHON" ]]; then
    TMPDIR_T10="$(setup_test_repo)"
    setup_crew_with_agents "$TMPDIR_T10"
    (
        cd "$TMPDIR_T10"
        export PYTHONPATH=".aitask-scripts"

        output=$($PYTHON .aitask-scripts/agentcrew/agentcrew_status.py --crew testcrew --agent planner heartbeat --message "working on it" 2>&1)
        assert_contains "heartbeat updated" "HEARTBEAT_UPDATED:planner" "$output"

        # Verify alive file updated
        alive_file=".aitask-crews/crew-testcrew/planner_alive.yaml"
        if grep -q "last_heartbeat:" "$alive_file" && grep -q "working on it" "$alive_file"; then
            _inc_pass
        else
            _inc_fail
            echo "FAIL: alive file not updated correctly"
        fi
    )
    cleanup_test_repo "$TMPDIR_T10"
else
    echo "SKIP: Python not available"
    for _ in $(seq 2); do _inc_pass; done
fi

# --- Test 11: Status CLI — list agents ---
echo "Test 11: Status CLI — list agents"
if [[ -n "$PYTHON" ]]; then
    TMPDIR_T11="$(setup_test_repo)"
    setup_crew_with_agents "$TMPDIR_T11"
    (
        cd "$TMPDIR_T11"
        export PYTHONPATH=".aitask-scripts"

        output=$($PYTHON .aitask-scripts/agentcrew/agentcrew_status.py --crew testcrew list 2>&1)
        assert_contains "planner listed" "AGENT:planner" "$output"
        assert_contains "coder listed" "AGENT:coder" "$output"
        assert_contains "ready agents shown" "READY_AGENTS:" "$output"
    )
    cleanup_test_repo "$TMPDIR_T11"
else
    echo "SKIP: Python not available"
    for _ in $(seq 3); do _inc_pass; done
fi

# --- Test 12: Command — send and list ---
echo "Test 12: Command — send and list"
TMPDIR_T12="$(setup_test_repo)"
setup_crew_with_agents "$TMPDIR_T12"
(
    cd "$TMPDIR_T12"

    # Send a kill command
    output=$(bash .aitask-scripts/aitask_crew_command.sh send --crew testcrew --agent planner --command kill 2>&1)
    assert_contains "command sent" "COMMAND_SENT:kill" "$output"

    # List commands
    output=$(bash .aitask-scripts/aitask_crew_command.sh list --crew testcrew --agent planner 2>&1)
    assert_contains "kill command listed" "kill" "$output"
    assert_not_contains "not empty" "NO_COMMANDS" "$output"
)
cleanup_test_repo "$TMPDIR_T12"

# --- Test 13: Command — ack clears commands ---
echo "Test 13: Command — ack clears commands"
TMPDIR_T13="$(setup_test_repo)"
setup_crew_with_agents "$TMPDIR_T13"
(
    cd "$TMPDIR_T13"

    # Send a command first
    bash .aitask-scripts/aitask_crew_command.sh send --crew testcrew --agent planner --command pause >/dev/null 2>&1

    # Ack
    output=$(bash .aitask-scripts/aitask_crew_command.sh ack --crew testcrew --agent planner 2>&1)
    assert_contains "commands acked" "COMMANDS_ACKED:planner" "$output"

    # Verify empty
    output=$(bash .aitask-scripts/aitask_crew_command.sh list --crew testcrew --agent planner 2>&1)
    assert_contains "no commands after ack" "NO_COMMANDS" "$output"
)
cleanup_test_repo "$TMPDIR_T13"

# --- Test 14: Command — reject invalid command ---
echo "Test 14: Command — reject invalid command"
TMPDIR_T14="$(setup_test_repo)"
setup_crew_with_agents "$TMPDIR_T14"
(
    cd "$TMPDIR_T14"
    assert_exit_nonzero "reject invalid command" \
        bash .aitask-scripts/aitask_crew_command.sh send --crew testcrew --agent planner --command invalid_cmd
)
cleanup_test_repo "$TMPDIR_T14"

# --- Test 15: Status CLI — self-reported terminal lifecycle + Error -> Completed (t671) ---
echo "Test 15: Status CLI — self-reported terminal lifecycle + Error->Completed recovery"
if [[ -n "$PYTHON" ]]; then
    TMPDIR_T15="$(setup_test_repo)"
    setup_crew_with_agents "$TMPDIR_T15"
    (
        cd "$TMPDIR_T15"
        export PYTHONPATH=".aitask-scripts"

        # Waiting -> Ready -> Running
        $PYTHON .aitask-scripts/agentcrew/agentcrew_status.py --crew testcrew --agent planner set --status Ready >/dev/null
        $PYTHON .aitask-scripts/agentcrew/agentcrew_status.py --crew testcrew --agent planner set --status Running >/dev/null

        # MissedHeartbeat is no longer accepted — the CLI must reject it.
        output=$($PYTHON .aitask-scripts/agentcrew/agentcrew_status.py --crew testcrew --agent planner set --status MissedHeartbeat 2>&1 || true)
        assert_contains "MissedHeartbeat rejected as unknown status" "Invalid status" "$output"

        # Running -> Error (genuine self-reported failure)
        output=$($PYTHON .aitask-scripts/agentcrew/agentcrew_status.py --crew testcrew --agent planner set --status Error 2>&1)
        assert_contains "set Running->Error self-reported" "STATUS_SET:planner:Running:Error" "$output"

        # completed_at must be stamped on terminal self-report (Error included).
        completed_at_err=$($PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import read_yaml
print(bool(read_yaml('.aitask-crews/crew-testcrew/planner_status.yaml').get('completed_at', '')))
" 2>/dev/null)
        assert_eq "completed_at stamped on self-reported Error" "True" "$completed_at_err"

        # Error -> Completed (direct recovery — preserved from prior behavior)
        output=$($PYTHON .aitask-scripts/agentcrew/agentcrew_status.py --crew testcrew --agent planner set --status Completed 2>&1)
        assert_contains "set Error->Completed (direct recovery)" "STATUS_SET:planner:Error:Completed" "$output"

        # Verify completed_at was stamped on the Error->Completed transition
        completed_at=$($PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import read_yaml
print(bool(read_yaml('.aitask-crews/crew-testcrew/planner_status.yaml').get('completed_at', '')))
" 2>/dev/null)
        assert_eq "completed_at stamped on Error->Completed" "True" "$completed_at"
    )
    cleanup_test_repo "$TMPDIR_T15"
else
    echo "SKIP: Python not available"
    for _ in $(seq 5); do _inc_pass; done
fi

# ============================================================
# Summary
# ============================================================

echo ""
echo "=== Results ==="
read -r pass fail total < "$COUNTER_FILE"
echo "Total: $total  Pass: $pass  Fail: $fail"

if [[ "$fail" -gt 0 ]]; then
    echo "SOME TESTS FAILED"
    exit 1
else
    echo "ALL TESTS PASSED"
fi
