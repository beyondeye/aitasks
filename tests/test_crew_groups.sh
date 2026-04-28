#!/usr/bin/env bash
# test_crew_groups.sh - Automated tests for agentcrew operation groups.
# Run: bash tests/test_crew_groups.sh

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

assert_file_not_exists() {
    local desc="$1" file="$2"
    if [[ ! -f "$file" ]]; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: $desc (file '$file' should not exist)"
    fi
}

# --- Setup ---

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

cleanup_test_repo() {
    local tmpdir="$1"
    cd "$ORIG_DIR"
    if [[ -d "$tmpdir" ]]; then
        (cd "$tmpdir" && git worktree prune 2>/dev/null || true)
        rm -rf "$tmpdir"
    fi
}

# Determine python
PYTHON="python3"
if [[ -x "$HOME/.aitask/venv/bin/python" ]]; then
    PYTHON="$HOME/.aitask/venv/bin/python"
fi

# ============================================================
# Tests
# ============================================================

echo "=== AgentCrew Operation Groups Tests ==="
echo ""

# --- Test 1: addwork --group creates group field in agent_status.yaml ---
echo "Test 1: addwork --group writes group field"
TMPDIR_T1="$(setup_test_repo)"
(
    cd "$TMPDIR_T1"

    bash .aitask-scripts/aitask_crew_init.sh --id testcrew --batch \
        --add-type "impl:claudecode/opus4_6" >/dev/null 2>&1

    echo "# work" > /tmp/work2do_t1.md
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_a --work2do /tmp/work2do_t1.md --type impl --group explore_001 --batch >/dev/null 2>&1
    rm -f /tmp/work2do_t1.md

    wt=".aitask-crews/crew-testcrew"
    group_val=$(grep 'group:' "$wt/agent_a_status.yaml" | head -1 | sed 's/^group:[[:space:]]*//')
    assert_eq "group field is explore_001" "explore_001" "$group_val"
)
cleanup_test_repo "$TMPDIR_T1"

# --- Test 2: addwork --group creates _groups.yaml ---
echo "Test 2: addwork --group creates _groups.yaml"
TMPDIR_T2="$(setup_test_repo)"
(
    cd "$TMPDIR_T2"

    bash .aitask-scripts/aitask_crew_init.sh --id testcrew --batch \
        --add-type "impl:claudecode/opus4_6" >/dev/null 2>&1

    echo "# work" > /tmp/work2do_t2.md
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_a --work2do /tmp/work2do_t2.md --type impl --group explore_001 --batch >/dev/null 2>&1
    rm -f /tmp/work2do_t2.md

    wt=".aitask-crews/crew-testcrew"
    assert_file_exists "_groups.yaml created" "$wt/_groups.yaml"
    assert_contains "_groups.yaml has explore_001" "explore_001" "$(cat "$wt/_groups.yaml")"
    assert_contains "_groups.yaml has sequence 1" "sequence: 1" "$(cat "$wt/_groups.yaml")"
)
cleanup_test_repo "$TMPDIR_T2"

# --- Test 3: second group gets sequence 2 ---
echo "Test 3: second group gets sequence 2"
TMPDIR_T3="$(setup_test_repo)"
(
    cd "$TMPDIR_T3"

    bash .aitask-scripts/aitask_crew_init.sh --id testcrew --batch \
        --add-type "impl:claudecode/opus4_6" >/dev/null 2>&1

    echo "# work" > /tmp/work2do_t3.md
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_a --work2do /tmp/work2do_t3.md --type impl --group explore_001 --batch >/dev/null 2>&1
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_b --work2do /tmp/work2do_t3.md --type impl --group compare_002 --batch >/dev/null 2>&1
    rm -f /tmp/work2do_t3.md

    wt=".aitask-crews/crew-testcrew"
    groups_content="$(cat "$wt/_groups.yaml")"
    assert_contains "has explore_001" "explore_001" "$groups_content"
    assert_contains "has compare_002" "compare_002" "$groups_content"
    assert_contains "has sequence 2" "sequence: 2" "$groups_content"
)
cleanup_test_repo "$TMPDIR_T3"

# --- Test 4: addwork without --group is backwards compatible ---
echo "Test 4: addwork without --group backwards compat"
TMPDIR_T4="$(setup_test_repo)"
(
    cd "$TMPDIR_T4"

    bash .aitask-scripts/aitask_crew_init.sh --id testcrew --batch \
        --add-type "impl:claudecode/opus4_6" >/dev/null 2>&1

    echo "# work" > /tmp/work2do_t4.md
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_a --work2do /tmp/work2do_t4.md --type impl --batch >/dev/null 2>&1
    rm -f /tmp/work2do_t4.md

    wt=".aitask-crews/crew-testcrew"
    # group field should be empty
    group_val=$(grep 'group:' "$wt/agent_a_status.yaml" | head -1 | sed 's/^group:[[:space:]]*//')
    assert_eq "group field is empty" "" "$group_val"
    # no _groups.yaml created
    assert_file_not_exists "no _groups.yaml" "$wt/_groups.yaml"
)
cleanup_test_repo "$TMPDIR_T4"

# --- Test 5: Runner group priority scheduling ---
echo "Test 5: runner prioritizes lower-sequence groups"
TMPDIR_T5="$(setup_test_repo)"
(
    cd "$TMPDIR_T5"

    bash .aitask-scripts/aitask_crew_init.sh --id testcrew --batch \
        --add-type "impl:claudecode/opus4_6" >/dev/null 2>&1

    wt=".aitask-crews/crew-testcrew"

    # Set max_parallel to 1 so only one agent can launch
    $PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import read_yaml, write_yaml
meta = read_yaml('$wt/_crew_meta.yaml')
meta['agent_types']['impl']['max_parallel'] = 1
write_yaml('$wt/_crew_meta.yaml', meta)
"

    # Add agent_a in group alpha_001 (sequence 1)
    echo "# work" > /tmp/work2do_t5.md
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_a --work2do /tmp/work2do_t5.md --type impl --group alpha_001 --batch >/dev/null 2>&1

    # Add agent_b in group beta_002 (sequence 2)
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_b --work2do /tmp/work2do_t5.md --type impl --group beta_002 --batch >/dev/null 2>&1
    rm -f /tmp/work2do_t5.md

    output=$(PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --once --dry-run --batch 2>&1)

    # Only agent_a (alpha_001, seq 1) should be launched
    assert_contains "agent_a is launched" "Would launch agent 'agent_a'" "$output"
    assert_not_contains "agent_b not launched" "Would launch agent 'agent_b'" "$output"
)
cleanup_test_repo "$TMPDIR_T5"

# --- Test 6: Runner without groups works (backwards compat) ---
echo "Test 6: runner without groups works"
TMPDIR_T6="$(setup_test_repo)"
(
    cd "$TMPDIR_T6"

    bash .aitask-scripts/aitask_crew_init.sh --id testcrew --batch \
        --add-type "impl:claudecode/opus4_6" >/dev/null 2>&1

    echo "# work" > /tmp/work2do_t6.md
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_a --work2do /tmp/work2do_t6.md --type impl --batch >/dev/null 2>&1
    rm -f /tmp/work2do_t6.md

    output=$(PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_runner.py \
        --crew testcrew --once --dry-run --batch 2>&1)

    assert_contains "agent_a is ready" "agent_a" "$output"
    assert_contains "dry run completes" "ONCE_COMPLETE" "$output"
)
cleanup_test_repo "$TMPDIR_T6"

# --- Test 7: send-group sends to matching agents ---
echo "Test 7: send-group sends to matching agents"
TMPDIR_T7="$(setup_test_repo)"
(
    cd "$TMPDIR_T7"

    bash .aitask-scripts/aitask_crew_init.sh --id testcrew --batch \
        --add-type "impl:claudecode/opus4_6" >/dev/null 2>&1

    wt=".aitask-crews/crew-testcrew"

    echo "# work" > /tmp/work2do_t7.md
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_a --work2do /tmp/work2do_t7.md --type impl --group explore_001 --batch >/dev/null 2>&1
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_b --work2do /tmp/work2do_t7.md --type impl --group explore_001 --batch >/dev/null 2>&1
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_c --work2do /tmp/work2do_t7.md --type impl --group compare_002 --batch >/dev/null 2>&1
    rm -f /tmp/work2do_t7.md

    # Set all to Running so send works
    for a in agent_a agent_b agent_c; do
        $PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import update_yaml_field
update_yaml_field('$wt/${a}_status.yaml', 'status', 'Running')
" 2>/dev/null
    done

    output=$(bash .aitask-scripts/aitask_crew_command.sh send-group \
        --crew testcrew --group explore_001 --command pause 2>&1)

    # agent_a and agent_b should get the command
    assert_contains "agent_a got command" "COMMAND_SENT:pause" "$output"

    # Check agent_c did NOT get a command
    cmd_c_content=$(cat "$wt/agent_c_commands.yaml")
    assert_not_contains "agent_c no command" "pause" "$cmd_c_content"

    # Check agent_a DID get a command
    cmd_a_content=$(cat "$wt/agent_a_commands.yaml")
    assert_contains "agent_a has pause" "pause" "$cmd_a_content"
)
cleanup_test_repo "$TMPDIR_T7"

# --- Test 8: status --group filters output ---
echo "Test 8: status --group filters output"
TMPDIR_T8="$(setup_test_repo)"
(
    cd "$TMPDIR_T8"

    bash .aitask-scripts/aitask_crew_init.sh --id testcrew --batch \
        --add-type "impl:claudecode/opus4_6" >/dev/null 2>&1

    echo "# work" > /tmp/work2do_t8.md
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_a --work2do /tmp/work2do_t8.md --type impl --group explore_001 --batch >/dev/null 2>&1
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_b --work2do /tmp/work2do_t8.md --type impl --group compare_002 --batch >/dev/null 2>&1
    rm -f /tmp/work2do_t8.md

    output=$(PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_status.py \
        --crew testcrew list --group explore_001 2>&1)

    assert_contains "agent_a shown" "agent_a" "$output"
    assert_not_contains "agent_b not shown" "agent_b" "$output"
)
cleanup_test_repo "$TMPDIR_T8"

# --- Test 9: report --group filters output ---
echo "Test 9: report --group filters output"
TMPDIR_T9="$(setup_test_repo)"
(
    cd "$TMPDIR_T9"

    bash .aitask-scripts/aitask_crew_init.sh --id testcrew --batch \
        --add-type "impl:claudecode/opus4_6" >/dev/null 2>&1

    echo "# work" > /tmp/work2do_t9.md
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_a --work2do /tmp/work2do_t9.md --type impl --group explore_001 --batch >/dev/null 2>&1
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_b --work2do /tmp/work2do_t9.md --type impl --group compare_002 --batch >/dev/null 2>&1
    rm -f /tmp/work2do_t9.md

    output=$(PYTHONPATH=".aitask-scripts" $PYTHON .aitask-scripts/agentcrew/agentcrew_report.py \
        --batch summary --crew testcrew --group explore_001 2>&1)

    assert_contains "agent_a shown" "agent_a" "$output"
    assert_not_contains "agent_b not shown" "agent_b" "$output"
)
cleanup_test_repo "$TMPDIR_T9"

# --- Test 10: Python utils group functions ---
echo "Test 10: Python group helpers"
TMPDIR_T10="$(setup_test_repo)"
(
    cd "$TMPDIR_T10"

    bash .aitask-scripts/aitask_crew_init.sh --id testcrew --batch \
        --add-type "impl:claudecode/opus4_6" >/dev/null 2>&1

    echo "# work" > /tmp/work2do_t10.md
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_a --work2do /tmp/work2do_t10.md --type impl --group explore_001 --batch >/dev/null 2>&1
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_b --work2do /tmp/work2do_t10.md --type impl --group explore_001 --batch >/dev/null 2>&1
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name agent_c --work2do /tmp/work2do_t10.md --type impl --group compare_002 --batch >/dev/null 2>&1
    rm -f /tmp/work2do_t10.md

    wt=".aitask-crews/crew-testcrew"

    # Test load_groups returns sorted by sequence
    result=$($PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import load_groups
groups = load_groups('$wt')
print(','.join(g['name'] for g in groups))
" 2>&1)
    assert_eq "load_groups sorted" "explore_001,compare_002" "$result"

    # Test get_group_agents
    result=$($PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import get_group_agents
agents = get_group_agents('$wt', 'explore_001')
print(','.join(sorted(agents)))
" 2>&1)
    assert_eq "get_group_agents" "agent_a,agent_b" "$result"

    # Test get_group_status (all Waiting -> Waiting)
    result=$($PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import get_group_status
print(get_group_status('$wt', 'explore_001'))
" 2>&1)
    assert_eq "group_status waiting" "Waiting" "$result"

    # Mark both agents as Completed, test group status
    $PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import update_yaml_field
update_yaml_field('$wt/agent_a_status.yaml', 'status', 'Completed')
update_yaml_field('$wt/agent_b_status.yaml', 'status', 'Completed')
" 2>/dev/null

    result=$($PYTHON -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from agentcrew.agentcrew_utils import get_group_status
print(get_group_status('$wt', 'explore_001'))
" 2>&1)
    assert_eq "group_status completed" "Completed" "$result"
)
cleanup_test_repo "$TMPDIR_T10"

# ============================================================
# Summary
# ============================================================

echo ""
read -r pass fail total < "$COUNTER_FILE"
echo "=== Results: $pass passed, $fail failed, $total total ==="
if [[ "$fail" -gt 0 ]]; then
    exit 1
fi
echo "All tests passed!"
