#!/usr/bin/env bash
# test_crew_runner.sh - Automated tests for agentcrew runner.
# Run: bash tests/test_crew_runner.sh

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
    local desc="$1" not_expected="$2" actual="$3"
    if echo "$actual" | grep -qi "$not_expected"; then
        _inc_fail
        echo "FAIL: $desc (did NOT expect '$not_expected' in output)"
    else
        _inc_pass
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

assert_exit_zero() {
    local desc="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: $desc (expected zero exit, got non-zero)"
    fi
}

# --- Setup: create isolated git repo with crew worktree ---

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
        # lib/launch_modes_sh.sh, lib/tui_registry.py) are present. A
        # hand-curated subset drifts as new sources/imports are added.
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

# Create a crew with 3 agents: A (no deps), B (depends A), C (depends A+B)
setup_crew_with_agents() {
    local tmpdir="$1"
    (
        cd "$tmpdir"

        # Init crew with an agent type
        bash .aitask-scripts/aitask_crew_init.sh --id testcrew --batch \
            --add-type "impl:claudecode/opus4_6" >/dev/null 2>&1

        local wt=".aitask-crews/crew-testcrew"

        # Create work2do files
        echo "# Agent A work" > /tmp/work2do_a.md
        echo "# Agent B work" > /tmp/work2do_b.md
        echo "# Agent C work" > /tmp/work2do_c.md

        # Add agents
        bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
            --name agent_a --work2do /tmp/work2do_a.md --type impl --batch >/dev/null 2>&1

        bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
            --name agent_b --work2do /tmp/work2do_b.md --type impl --depends agent_a --batch >/dev/null 2>&1

        bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
            --name agent_c --work2do /tmp/work2do_c.md --type impl --depends agent_a,agent_b --batch >/dev/null 2>&1

        rm -f /tmp/work2do_a.md /tmp/work2do_b.md /tmp/work2do_c.md
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

# Determine python for running runner directly
PYTHON="python3"
if [[ -x "$HOME/.aitask/venv/bin/python" ]]; then
    PYTHON="$HOME/.aitask/venv/bin/python"
fi

# ============================================================
# Tests
# ============================================================

echo "=== AgentCrew Runner Tests ==="
echo ""

# --- Test 1: Python compilation check ---
echo "Test 1: Python syntax check"
(
    output=$($PYTHON -m py_compile "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_runner.py" 2>&1)
    assert_eq "agentcrew_runner.py compiles" "" "$output"
)

# --- Test 2: --once --dry-run shows only A as ready ---
echo "Test 2: dry-run shows correct ready agents"
TMPDIR_T2="$(setup_test_repo)"
(
    cd "$TMPDIR_T2"
    setup_crew_with_agents "$TMPDIR_T2"

    output=$(PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --once --dry-run --batch 2>&1)

    assert_contains "agent_a is ready" "agent_a" "$output"
    assert_not_contains "agent_b not ready yet" "Would launch agent 'agent_b'" "$output"
    assert_not_contains "agent_c not ready yet" "Would launch agent 'agent_c'" "$output"
    assert_contains "dry run completes" "ONCE_COMPLETE" "$output"
)
cleanup_test_repo "$TMPDIR_T2"

# --- Test 3: After A complete, B becomes ready ---
echo "Test 3: dependency resolution after completion"
TMPDIR_T3="$(setup_test_repo)"
(
    cd "$TMPDIR_T3"
    setup_crew_with_agents "$TMPDIR_T3"

    wt=".aitask-crews/crew-testcrew"

    # Manually mark agent_a as Completed
    $PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import update_yaml_field
update_yaml_field('$wt/agent_a_status.yaml', 'status', 'Completed')
"

    output=$(PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --once --dry-run --batch 2>&1)

    assert_contains "agent_b becomes ready" "agent_b" "$output"
    assert_not_contains "agent_c not ready yet (needs B)" "Would launch agent 'agent_c'" "$output"
)
cleanup_test_repo "$TMPDIR_T3"

# --- Test 4: After A+B complete, C becomes ready ---
echo "Test 4: multi-dependency resolution"
TMPDIR_T4="$(setup_test_repo)"
(
    cd "$TMPDIR_T4"
    setup_crew_with_agents "$TMPDIR_T4"

    wt=".aitask-crews/crew-testcrew"

    # Mark A and B as Completed
    $PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import update_yaml_field
update_yaml_field('$wt/agent_a_status.yaml', 'status', 'Completed')
update_yaml_field('$wt/agent_b_status.yaml', 'status', 'Ready')
" 2>/dev/null
    $PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import update_yaml_field
update_yaml_field('$wt/agent_b_status.yaml', 'status', 'Completed')
" 2>/dev/null

    output=$(PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --once --dry-run --batch 2>&1)

    assert_contains "agent_c becomes ready" "agent_c" "$output"
)
cleanup_test_repo "$TMPDIR_T4"

# --- Test 5: Per-type max_parallel enforcement ---
echo "Test 5: per-type max_parallel limit"
TMPDIR_T5="$(setup_test_repo)"
(
    cd "$TMPDIR_T5"

    # Init crew with max_parallel=1 for impl type
    bash .aitask-scripts/aitask_crew_init.sh --id testcrew --batch \
        --add-type "impl:claudecode/opus4_6" >/dev/null 2>&1

    wt=".aitask-crews/crew-testcrew"

    # Set max_parallel to 1
    $PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import read_yaml, write_yaml
meta = read_yaml('$wt/_crew_meta.yaml')
meta['agent_types']['impl']['max_parallel'] = 1
write_yaml('$wt/_crew_meta.yaml', meta)
"

    # Create two independent agents (no deps)
    echo "# work X" > /tmp/work2do_x.md
    echo "# work Y" > /tmp/work2do_y.md
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_x --work2do /tmp/work2do_x.md --type impl --batch >/dev/null 2>&1
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_y --work2do /tmp/work2do_y.md --type impl --batch >/dev/null 2>&1
    rm -f /tmp/work2do_x.md /tmp/work2do_y.md

    output=$(PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --once --dry-run --batch 2>&1)

    # Only 1 agent should be launched (max_parallel=1)
    launch_count=$(echo "$output" | grep -c "DRY_RUN: Would launch" || true)
    assert_eq "only 1 agent launched (max_parallel=1)" "1" "$launch_count"
)
cleanup_test_repo "$TMPDIR_T5"

# --- Test 6: Single-instance detection ---
echo "Test 6: single-instance detection"
TMPDIR_T6="$(setup_test_repo)"
(
    cd "$TMPDIR_T6"
    setup_crew_with_agents "$TMPDIR_T6"

    wt=".aitask-crews/crew-testcrew"

    # Write a fake runner_alive.yaml with current hostname and a PID that exists
    # Use our parent shell PID which is still alive
    alive_pid=$$
    $PYTHON -c "
import sys, socket; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import write_yaml
from datetime import datetime, timezone
now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
write_yaml('$wt/_runner_alive.yaml', {
    'status': 'running',
    'pid': $alive_pid,
    'hostname': socket.gethostname(),
    'started_at': now,
    'last_heartbeat': now,
    'next_check_at': now,
    'interval': 30,
    'requested_action': None,
})
"

    # Attempting to start runner should fail (PID is alive = our own test process)
    if PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --once --batch 2>/dev/null; then
        _inc_fail
        echo "FAIL: runner should refuse to start when another is alive"
    else
        _inc_pass
    fi
)
cleanup_test_repo "$TMPDIR_T6"

# --- Test 7: --check diagnostic mode ---
echo "Test 7: diagnostic mode (--check)"
TMPDIR_T7="$(setup_test_repo)"
(
    cd "$TMPDIR_T7"
    setup_crew_with_agents "$TMPDIR_T7"

    wt=".aitask-crews/crew-testcrew"

    # No runner alive file — should exit 1
    if PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --check --batch 2>/dev/null; then
        _inc_fail
        echo "FAIL: --check should exit 1 when no runner alive"
    else
        _inc_pass
    fi

    output=$(PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --check --batch 2>&1 || true)
    assert_contains "check reports not_running" "RUNNER_STATUS:not_running" "$output"

    # Write alive file for a running runner
    $PYTHON -c "
import sys, os, socket; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import write_yaml
from datetime import datetime, timezone
now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
write_yaml('$wt/_runner_alive.yaml', {
    'status': 'running',
    'pid': os.getpid(),
    'hostname': socket.gethostname(),
    'started_at': now,
    'last_heartbeat': now,
    'next_check_at': now,
    'interval': 30,
    'requested_action': None,
})
"

    output=$(PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --check --batch 2>&1 || true)
    assert_contains "check reports running" "RUNNER_STATUS:running" "$output"
    assert_contains "check reports hostname" "RUNNER_HOSTNAME:" "$output"
    assert_contains "check reports alive" "RUNNER_ALIVE:" "$output"
)
cleanup_test_repo "$TMPDIR_T7"

# --- Test 8: Config file resolution ---
echo "Test 8: config file resolution"
TMPDIR_T8="$(setup_test_repo)"
(
    cd "$TMPDIR_T8"
    setup_crew_with_agents "$TMPDIR_T8"

    # Create a config file with custom values
    mkdir -p aitasks/metadata
    cat > aitasks/metadata/crew_runner_config.yaml << 'YAML'
interval: 60
max_concurrent: 5
YAML

    # Run with --once --dry-run and verify it uses config values
    # (We can't easily assert interval/max_concurrent from dry-run output alone,
    #  but we can verify it doesn't crash when reading the config)
    output=$(PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --once --dry-run --batch 2>&1)
    assert_contains "runner works with config file" "ONCE_COMPLETE" "$output"

    # CLI args should override config
    output=$(PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --once --dry-run --batch --interval 10 --max-concurrent 1 2>&1)
    assert_contains "runner works with CLI overrides" "ONCE_COMPLETE" "$output"

    # Only 1 agent should launch with max-concurrent=1
    launch_count=$(echo "$output" | grep -c "DRY_RUN: Would launch" || true)
    assert_eq "max-concurrent=1 limits to 1 launch" "1" "$launch_count"
)
cleanup_test_repo "$TMPDIR_T8"

# --- Test 9: All terminal state detection ---
echo "Test 9: all terminal state detection"
TMPDIR_T9="$(setup_test_repo)"
(
    cd "$TMPDIR_T9"
    setup_crew_with_agents "$TMPDIR_T9"

    wt=".aitask-crews/crew-testcrew"

    # Mark all agents as Completed (transition through proper states)
    for agent in agent_a agent_b agent_c; do
        $PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import update_yaml_field
update_yaml_field('$wt/${agent}_status.yaml', 'status', 'Completed')
" 2>/dev/null
    done

    output=$(PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --once --dry-run --batch 2>&1)
    assert_contains "detects all terminal" "ALL_TERMINAL" "$output"
)
cleanup_test_repo "$TMPDIR_T9"

# --- Test 10: Stale runner detection (same host, stale heartbeat) ---
echo "Test 10: stale runner takeover"
TMPDIR_T10="$(setup_test_repo)"
(
    cd "$TMPDIR_T10"
    setup_crew_with_agents "$TMPDIR_T10"

    wt=".aitask-crews/crew-testcrew"

    # Write a stale runner_alive (old heartbeat, dead PID)
    $PYTHON -c "
import sys, socket; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import write_yaml
write_yaml('$wt/_runner_alive.yaml', {
    'status': 'running',
    'pid': 99999999,
    'hostname': socket.gethostname(),
    'started_at': '2020-01-01 00:00:00',
    'last_heartbeat': '2020-01-01 00:00:00',
    'next_check_at': '2020-01-01 00:00:30',
    'interval': 30,
    'requested_action': None,
})
"

    # Should succeed (stale runner, take over)
    output=$(PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --once --dry-run --batch 2>&1)
    assert_contains "takes over stale runner" "ONCE_COMPLETE" "$output"
)
cleanup_test_repo "$TMPDIR_T10"

# --- Test 11: --reset-errors identifies Error agents (dry-run) ---
echo "Test 11: --reset-errors identifies Error agents in dry-run"
TMPDIR_T11="$(setup_test_repo)"
(
    cd "$TMPDIR_T11"
    setup_crew_with_agents "$TMPDIR_T11"

    wt=".aitask-crews/crew-testcrew"

    # Mark all agents as Error
    for agent in agent_a agent_b agent_c; do
        $PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import update_yaml_field
update_yaml_field('$wt/${agent}_status.yaml', 'status', 'Error')
update_yaml_field('$wt/${agent}_status.yaml', 'error_message', 'Heartbeat timeout')
" 2>/dev/null
    done

    output=$(PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --once --dry-run --reset-errors --batch 2>&1)

    assert_contains "dry-run reset agent_a" "RESET_DRY:agent_a" "$output"
    assert_contains "dry-run reset agent_b" "RESET_DRY:agent_b" "$output"
    assert_contains "dry-run reset agent_c" "RESET_DRY:agent_c" "$output"
    # In dry-run mode agents stay Error, so ALL_TERMINAL is expected
    assert_contains "dry-run still shows ALL_TERMINAL" "ALL_TERMINAL" "$output"
)
cleanup_test_repo "$TMPDIR_T11"

# --- Test 12: Without --reset-errors, all-Error agents trigger ALL_TERMINAL ---
echo "Test 12: all-Error without --reset-errors triggers ALL_TERMINAL"
TMPDIR_T12="$(setup_test_repo)"
(
    cd "$TMPDIR_T12"
    setup_crew_with_agents "$TMPDIR_T12"

    wt=".aitask-crews/crew-testcrew"

    # Mark all agents as Error
    for agent in agent_a agent_b agent_c; do
        $PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import update_yaml_field
update_yaml_field('$wt/${agent}_status.yaml', 'status', 'Error')
" 2>/dev/null
    done

    output=$(PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --once --dry-run --batch 2>&1)
    assert_contains "all-Error triggers ALL_TERMINAL" "ALL_TERMINAL" "$output"
)
cleanup_test_repo "$TMPDIR_T12"

# --- Test 13: reset command via aitask_crew_command.sh ---
echo "Test 13: reset command accepted by crew command script"
TMPDIR_T13="$(setup_test_repo)"
(
    cd "$TMPDIR_T13"
    setup_crew_with_agents "$TMPDIR_T13"

    output=$(bash .aitask-scripts/aitask_crew_command.sh send --crew testcrew \
        --agent agent_a --command reset 2>&1)
    assert_contains "reset command accepted" "COMMAND_SENT:reset" "$output"

    output=$(bash .aitask-scripts/aitask_crew_command.sh list --crew testcrew \
        --agent agent_a 2>&1)
    assert_contains "reset command listed" "reset" "$output"
)
cleanup_test_repo "$TMPDIR_T13"

# --- Test 14: process_pending_commands handles reset command ---
echo "Test 14: runner processes pending reset command"
TMPDIR_T14="$(setup_test_repo)"
(
    cd "$TMPDIR_T14"
    setup_crew_with_agents "$TMPDIR_T14"

    wt=".aitask-crews/crew-testcrew"

    # Mark agent_a as Error
    $PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import update_yaml_field
update_yaml_field('$wt/agent_a_status.yaml', 'status', 'Error')
update_yaml_field('$wt/agent_a_status.yaml', 'error_message', 'Test error')
" 2>/dev/null

    # Write a pending reset command for agent_a
    $PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import write_yaml
write_yaml('$wt/agent_a_commands.yaml', {
    'pending_commands': [{'command': 'reset', 'sent_at': '2026-01-01 00:00:00', 'sent_by': 'user'}]
})
" 2>/dev/null

    # Use --dry-run to prevent agent launch after reset
    output=$(PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --once --dry-run --batch 2>&1)
    assert_contains "runner resets agent_a via command" "CMD_RESET:agent_a" "$output"

    # Verify status is now Waiting (process_pending_commands modifies even in dry-run)
    status=$($PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import read_yaml
print(read_yaml('$wt/agent_a_status.yaml').get('status', ''))
" 2>/dev/null)
    assert_eq "agent_a is Waiting after reset command" "Waiting" "$status"
)
cleanup_test_repo "$TMPDIR_T14"

# --- Test 15: Error → Waiting transition validation ---
echo "Test 15: Error → Waiting transition is valid"
(
    result=$($PYTHON -c "
import sys; sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts')
from agentcrew.agentcrew_utils import validate_agent_transition
print(validate_agent_transition('Error', 'Waiting'))
" 2>/dev/null)
    assert_eq "Error → Waiting is valid" "True" "$result"

    result=$($PYTHON -c "
import sys; sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts')
from agentcrew.agentcrew_utils import validate_agent_transition
print(validate_agent_transition('Completed', 'Waiting'))
" 2>/dev/null)
    assert_eq "Completed → Waiting is still invalid" "False" "$result"
)

# --- Test 16: Running → MissedHeartbeat on stale heartbeat ---
echo "Test 16: stale heartbeat marks Running agent as MissedHeartbeat"
TMPDIR_T16="$(setup_test_repo)"
(
    cd "$TMPDIR_T16"
    setup_crew_with_agents "$TMPDIR_T16"

    wt=".aitask-crews/crew-testcrew"

    # Tighten heartbeat timeout to 1 minute so old timestamps look stale.
    $PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import update_yaml_field
update_yaml_field('$wt/_crew_meta.yaml', 'heartbeat_timeout_minutes', 1)
" 2>/dev/null

    # Mark agent_a Running with a long-stale heartbeat.
    $PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import update_yaml_field, write_yaml
update_yaml_field('$wt/agent_a_status.yaml', 'status', 'Running')
write_yaml('$wt/agent_a_alive.yaml', {'last_heartbeat': '2020-01-01 00:00:00'})
" 2>/dev/null

    PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --once --dry-run --batch >/dev/null 2>&1

    status=$($PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import read_yaml
print(read_yaml('$wt/agent_a_status.yaml').get('status', ''))
" 2>/dev/null)
    assert_eq "agent_a status flipped to MissedHeartbeat" "MissedHeartbeat" "$status"

    missed_at=$($PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import read_yaml
print(bool(read_yaml('$wt/agent_a_status.yaml').get('missed_heartbeat_at', '')))
" 2>/dev/null)
    assert_eq "missed_heartbeat_at recorded" "True" "$missed_at"
)
cleanup_test_repo "$TMPDIR_T16"

# --- Test 17: MissedHeartbeat → Running when heartbeat resumes ---
echo "Test 17: MissedHeartbeat recovers to Running on fresh heartbeat"
TMPDIR_T17="$(setup_test_repo)"
(
    cd "$TMPDIR_T17"
    setup_crew_with_agents "$TMPDIR_T17"

    wt=".aitask-crews/crew-testcrew"

    $PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import update_yaml_field
update_yaml_field('$wt/_crew_meta.yaml', 'heartbeat_timeout_minutes', 1)
" 2>/dev/null

    # Agent already in MissedHeartbeat with a fresh-enough heartbeat.
    $PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import update_yaml_field, write_yaml
from datetime import datetime, timezone
now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
update_yaml_field('$wt/agent_a_status.yaml', 'status', 'MissedHeartbeat')
update_yaml_field('$wt/agent_a_status.yaml', 'missed_heartbeat_at', now)
write_yaml('$wt/agent_a_alive.yaml', {'last_heartbeat': now})
" 2>/dev/null

    PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --once --dry-run --batch >/dev/null 2>&1

    status=$($PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import read_yaml
print(read_yaml('$wt/agent_a_status.yaml').get('status', ''))
" 2>/dev/null)
    assert_eq "agent_a recovered to Running" "Running" "$status"

    missed_cleared=$($PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import read_yaml
print(read_yaml('$wt/agent_a_status.yaml').get('missed_heartbeat_at', ''))
" 2>/dev/null)
    assert_eq "missed_heartbeat_at cleared on recovery" "" "$missed_cleared"
)
cleanup_test_repo "$TMPDIR_T17"

# --- Test 18: MissedHeartbeat → Error when grace expires ---
echo "Test 18: MissedHeartbeat escalates to Error after grace window"
TMPDIR_T18="$(setup_test_repo)"
(
    cd "$TMPDIR_T18"
    setup_crew_with_agents "$TMPDIR_T18"

    wt=".aitask-crews/crew-testcrew"

    $PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import update_yaml_field
update_yaml_field('$wt/_crew_meta.yaml', 'heartbeat_timeout_minutes', 1)
" 2>/dev/null

    # Agent in MissedHeartbeat with both missed_at and last_heartbeat long stale.
    $PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import update_yaml_field, write_yaml
update_yaml_field('$wt/agent_a_status.yaml', 'status', 'MissedHeartbeat')
update_yaml_field('$wt/agent_a_status.yaml', 'missed_heartbeat_at', '2020-01-01 00:00:00')
write_yaml('$wt/agent_a_alive.yaml', {'last_heartbeat': '2020-01-01 00:00:00'})
" 2>/dev/null

    PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --once --dry-run --batch >/dev/null 2>&1

    status=$($PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import read_yaml
print(read_yaml('$wt/agent_a_status.yaml').get('status', ''))
" 2>/dev/null)
    assert_eq "agent_a escalated to Error" "Error" "$status"

    err_msg=$($PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import read_yaml
print(read_yaml('$wt/agent_a_status.yaml').get('error_message', ''))
" 2>/dev/null)
    assert_contains "error_message mentions grace expiry" "grace window expired" "$err_msg"
)
cleanup_test_repo "$TMPDIR_T18"

# ============================================================
# Summary
# ============================================================

echo ""
read -r PASSES FAILS TOTAL < "$COUNTER_FILE"
echo "=== Results: $PASSES passed, $FAILS failed, $TOTAL total ==="

if [[ "$FAILS" -gt 0 ]]; then
    exit 1
fi
