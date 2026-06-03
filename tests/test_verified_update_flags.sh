#!/usr/bin/env bash
# test_verified_update_flags.sh - Tests for --agent/--cli-id flags on aitask_verified_update.sh
# Run: bash tests/test_verified_update_flags.sh

set -e

# Clear env-var fast-path so resolver honors --cli-id / --agent-string flags.
unset AITASK_AGENT_STRING

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Shared assertion helpers (see tests/lib/asserts.sh).
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
UPDATE_SCRIPT="$PROJECT_DIR/.aitask-scripts/aitask_verified_update.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

# --- Tests ---

echo "=== Test: --agent/--cli-id resolves and updates ==="
result=$(cd "$PROJECT_DIR" && bash "$UPDATE_SCRIPT" --agent claudecode --cli-id claude-opus-4-6 --skill test_414_flags --score 5 --silent 2>&1)
assert_contains "agent/cli-id resolves to UPDATED" "UPDATED:claudecode/opus4_6:test_414_flags:" "$result"

echo "=== Test: --agent-string backward compat ==="
result=$(cd "$PROJECT_DIR" && bash "$UPDATE_SCRIPT" --agent-string claudecode/opus4_6 --skill test_414_flags --score 4 --silent 2>&1)
assert_contains "agent-string still works" "UPDATED:claudecode/opus4_6:test_414_flags:" "$result"

echo "=== Test: --agent-string and --agent together errors ==="
result=$(cd "$PROJECT_DIR" && bash "$UPDATE_SCRIPT" --agent-string claudecode/opus4_6 --agent claudecode --cli-id claude-opus-4-6 --skill test_414_flags --score 3 --silent 2>&1 || true)
assert_contains "mutual exclusion error" "cannot be combined" "$result"

echo "=== Test: --agent without --cli-id errors ==="
result=$(cd "$PROJECT_DIR" && bash "$UPDATE_SCRIPT" --agent claudecode --skill test_414_flags --score 3 --silent 2>&1 || true)
assert_contains "missing cli-id error" "--cli-id is required" "$result"

echo "=== Test: --cli-id without --agent errors ==="
result=$(cd "$PROJECT_DIR" && bash "$UPDATE_SCRIPT" --cli-id claude-opus-4-6 --skill test_414_flags --score 3 --silent 2>&1 || true)
assert_contains "missing agent error" "Either --agent-string or --agent/--cli-id is required" "$result"

echo "=== Test: neither --agent-string nor --agent errors ==="
result=$(cd "$PROJECT_DIR" && bash "$UPDATE_SCRIPT" --skill test_414_flags --score 3 --silent 2>&1 || true)
assert_contains "no agent identifier error" "Either --agent-string or --agent/--cli-id is required" "$result"

# --- Summary ---
echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
