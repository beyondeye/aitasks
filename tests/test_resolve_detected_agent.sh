#!/usr/bin/env bash
# test_resolve_detected_agent.sh - Tests for aitask_resolve_detected_agent.sh
# Run: bash tests/test_resolve_detected_agent.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Shared assertion helpers (see tests/lib/asserts.sh).
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
RESOLVE_SCRIPT="$PROJECT_DIR/.aitask-scripts/aitask_resolve_detected_agent.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

# --- Tests ---

echo "=== Test: env var fast path ==="
result=$(AITASK_AGENT_STRING="claudecode/opus4_6" bash "$RESOLVE_SCRIPT" 2>&1)
assert_eq "env var returns AGENT_STRING" "AGENT_STRING:claudecode/opus4_6" "$result"

echo "=== Test: explicit args override env var ==="
result=$(AITASK_AGENT_STRING="custom/model" bash "$RESOLVE_SCRIPT" --agent codex --cli-id gpt-5.4 2>&1)
assert_eq "explicit --agent/--cli-id beats env var" "AGENT_STRING:codex/gpt5_4" "$result"

echo "=== Test: explicit cli-id wins over env var (t703 regression) ==="
result=$(AITASK_AGENT_STRING="claudecode/opus4_7_1m" bash "$RESOLVE_SCRIPT" --agent claudecode --cli-id claude-opus-4-6 2>&1)
assert_eq "t703: explicit claude-opus-4-6 resolves despite env var" "AGENT_STRING:claudecode/opus4_6" "$result"

echo "=== Test: exact match claudecode ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent claudecode --cli-id claude-opus-4-6 2>&1)
assert_eq "claudecode exact match" "AGENT_STRING:claudecode/opus4_6" "$result"

echo "=== Test: exact match claudecode opus4_7 ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent claudecode --cli-id claude-opus-4-7 2>&1)
assert_eq "claudecode opus4_7 exact match" "AGENT_STRING:claudecode/opus4_7" "$result"

echo "=== Test: exact match claudecode opus4_7_1m ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent claudecode --cli-id 'claude-opus-4-7[1m]' 2>&1)
assert_eq "claudecode opus4_7_1m exact match" "AGENT_STRING:claudecode/opus4_7_1m" "$result"

echo "=== Test: exact match codex ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent codex --cli-id gpt-5.4 2>&1)
assert_eq "codex exact match" "AGENT_STRING:codex/gpt5_4" "$result"

echo "=== Test: exact match opencode ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent opencode --cli-id "openai/codex-mini-latest" 2>&1)
assert_eq "opencode exact match" "AGENT_STRING:opencode/openai_codex_mini_latest" "$result"

echo "=== Test: opencode suffix match ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent opencode --cli-id "codex-mini-latest" 2>&1)
assert_eq "opencode suffix match" "AGENT_STRING:opencode/openai_codex_mini_latest" "$result"

echo "=== Test: fallback for unknown cli_id ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent claudecode --cli-id unknown-model 2>&1)
assert_eq "fallback returns AGENT_STRING_FALLBACK" "AGENT_STRING_FALLBACK:claudecode/unknown-model" "$result"

echo "=== Test: invalid agent ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent invalidagent --cli-id foo 2>&1 || true)
assert_contains "invalid agent dies" "Invalid agent" "$result"

echo "=== Test: missing --agent ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --cli-id foo 2>&1 || true)
assert_contains "missing agent dies" "Missing required argument: --agent" "$result"

echo "=== Test: missing --cli-id ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent claudecode 2>&1 || true)
assert_contains "missing cli-id dies" "Missing required argument: --cli-id" "$result"

# --- Summary ---
echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
