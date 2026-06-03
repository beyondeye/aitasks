#!/usr/bin/env bash
# test_crew_addwork_output_instructions.sh - Regression test for t820.
#
# aitask_crew_addwork.sh pre-creates <agent>_output.md with placeholder
# content. Claude Code's Write tool refuses to overwrite an existing file
# that has not been Read first, so a crew agent's first write to its output
# file fails. The generated <agent>_instructions.md must tell the agent to
# read the output file once before writing it.
#
# Run: bash tests/test_crew_addwork_output_instructions.sh

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
        echo "FAIL: $desc (expected output containing '$expected')"
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

        # Mirror the full .aitask-scripts/ tree so transitive deps are present.
        cp -R "$PROJECT_DIR/.aitask-scripts" .aitask-scripts
        find .aitask-scripts -type d -name __pycache__ -prune -exec rm -rf {} +
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

echo "=== Crew addwork output-instructions Tests (t820) ==="
echo ""

# --- Test 1: generated _instructions.md tells the agent to read _output.md
#             before writing it ---
echo "Test 1: _instructions.md carries the read-before-write note"
TMPDIR_T1="$(setup_test_repo)"
(
    cd "$TMPDIR_T1"

    bash .aitask-scripts/aitask_crew_init.sh --id testcrew --batch \
        --add-type "impl:claudecode/opus4_6" >/dev/null 2>&1

    echo "# work" > /tmp/work2do_t820.md
    bash .aitask-scripts/aitask_crew_addwork.sh --crew testcrew \
        --name planner --work2do /tmp/work2do_t820.md --type impl --batch >/dev/null 2>&1
    rm -f /tmp/work2do_t820.md

    wt=".aitask-crews/crew-testcrew"
    instr="$wt/planner_instructions.md"

    assert_file_exists "instructions file created" "$instr"

    content="$(cat "$instr" 2>/dev/null)"
    assert_contains "has Writing Output section" "## Writing Output" "$content"
    assert_contains "names the agent output file" \
        "planner_output.md" "$content"
    assert_contains "warns the file pre-exists" \
        "This file already exists with placeholder content" "$content"
    assert_contains "instructs read-before-write" \
        "require reading a file before overwriting it" "$content"

    # Sanity: the placeholder _output.md is still pre-created (the fix is an
    # instruction, not a removal of the placeholder).
    assert_file_exists "placeholder output file created" \
        "$wt/planner_output.md"
)
cleanup_test_repo "$TMPDIR_T1"

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
