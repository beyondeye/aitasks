#!/usr/bin/env bash
# test_resolve_detected_agent.sh - Tests for aitask_resolve_detected_agent.sh
# Run: bash tests/test_resolve_detected_agent.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RESOLVE_SCRIPT="$PROJECT_DIR/.aitask-scripts/aitask_resolve_detected_agent.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

assert_eq() {
    local label="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$actual" == "$expected" ]]; then
        echo "  PASS: $label"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $label"
        echo "    expected: $expected"
        echo "    actual:   $actual"
        FAIL=$((FAIL + 1))
    fi
}

assert_contains() {
    local label="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$haystack" == *"$needle"* ]]; then
        echo "  PASS: $label"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $label"
        echo "    expected to contain: $needle"
        echo "    actual: $haystack"
        FAIL=$((FAIL + 1))
    fi
}

# --- Tests ---

echo "=== Test: env var fast path ==="
result=$(AITASK_AGENT_STRING="claudecode/opus4_6" bash "$RESOLVE_SCRIPT" 2>&1)
assert_eq "env var returns AGENT_STRING" "AGENT_STRING:claudecode/opus4_6" "$result"

echo "=== Test: env var overrides args ==="
result=$(AITASK_AGENT_STRING="custom/model" bash "$RESOLVE_SCRIPT" --agent codex --cli-id gpt-5.4 2>&1)
assert_eq "env var overrides --agent/--cli-id" "AGENT_STRING:custom/model" "$result"

echo "=== Test: exact match claudecode ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent claudecode --cli-id claude-opus-4-6 2>&1)
assert_eq "claudecode exact match" "AGENT_STRING:claudecode/opus4_6" "$result"

echo "=== Test: exact match geminicli ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent geminicli --cli-id gemini-3.1-pro-preview 2>&1)
assert_eq "geminicli exact match" "AGENT_STRING:geminicli/gemini3_1pro" "$result"

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
