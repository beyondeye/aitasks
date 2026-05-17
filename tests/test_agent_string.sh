#!/usr/bin/env bash
# test_agent_string.sh - Tests for .aitask-scripts/lib/agent_string.sh
#   Validates the single-source-of-truth extraction (t777_5):
#     parse_agent_string, get_cli_binary, get_model_flag, plus the
#     double-source guard (_AIT_AGENT_STRING_LOADED).
# Run: bash tests/test_agent_string.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qi -- "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

cd "$PROJECT_DIR"

LIB="$PROJECT_DIR/.aitask-scripts/lib/agent_string.sh"
[[ -f "$LIB" ]] || { echo "FAIL: lib not found at $LIB"; exit 1; }

# --- Test 1: parse_agent_string with valid input sets PARSED_AGENT / PARSED_MODEL ---
out="$(bash -c "source '$LIB'; parse_agent_string claudecode/opus4_7_1m; echo \"\$PARSED_AGENT|\$PARSED_MODEL\"")"
assert_eq "parse valid: PARSED_AGENT|PARSED_MODEL" "claudecode|opus4_7_1m" "$out"

# --- Test 2: parse_agent_string with no slash dies ---
TOTAL=$((TOTAL + 1))
if bash -c "source '$LIB'; parse_agent_string bogus" 2>/dev/null; then
    FAIL=$((FAIL + 1))
    echo "FAIL: parse 'bogus' should die (no slash)"
else
    PASS=$((PASS + 1))
fi

# --- Test 3: parse_agent_string with unknown agent dies ---
TOTAL=$((TOTAL + 1))
if bash -c "source '$LIB'; parse_agent_string fakeagent/x" 2>/dev/null; then
    FAIL=$((FAIL + 1))
    echo "FAIL: parse 'fakeagent/x' should die (unknown agent)"
else
    PASS=$((PASS + 1))
fi

# --- Tests 4-7: get_cli_binary mapping ---
assert_eq "get_cli_binary claudecode" "claude"   "$(bash -c "source '$LIB'; get_cli_binary claudecode")"
assert_eq "get_cli_binary geminicli"  "gemini"   "$(bash -c "source '$LIB'; get_cli_binary geminicli")"
assert_eq "get_cli_binary codex"      "codex"    "$(bash -c "source '$LIB'; get_cli_binary codex")"
assert_eq "get_cli_binary opencode"   "opencode" "$(bash -c "source '$LIB'; get_cli_binary opencode")"

# --- Tests 8-11: get_model_flag mapping ---
assert_eq "get_model_flag claudecode" "--model" "$(bash -c "source '$LIB'; get_model_flag claudecode")"
assert_eq "get_model_flag geminicli"  "-m"      "$(bash -c "source '$LIB'; get_model_flag geminicli")"
assert_eq "get_model_flag codex"      "-m"      "$(bash -c "source '$LIB'; get_model_flag codex")"
assert_eq "get_model_flag opencode"   "--model" "$(bash -c "source '$LIB'; get_model_flag opencode")"

# --- Test 12: double-source guard ---
# Source the lib twice in the same shell, set a sentinel between them, assert
# the sentinel survives (i.e., second source short-circuited).
out="$(bash -c "
    source '$LIB'
    MY_SENTINEL=42
    source '$LIB'
    echo \"\$MY_SENTINEL\"
")"
assert_eq "double-source guard preserves caller state" "42" "$out"

# --- Test 13: DEFAULT_AGENT_STRING constant is set ---
out="$(bash -c "source '$LIB'; echo \"\$DEFAULT_AGENT_STRING\"")"
assert_contains "DEFAULT_AGENT_STRING non-empty" "/" "$out"

# --- Test 14: get_cli_model_id resolves a real model from models_claudecode.json ---
# Smoke test that the JSON-loading path still works after extraction.
out="$(bash -c "source '$LIB'; get_cli_model_id claudecode opus4_7_1m" 2>/dev/null)"
TOTAL=$((TOTAL + 1))
if [[ -n "$out" && "$out" != "null" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: get_cli_model_id claudecode opus4_7_1m returned empty/null (models_claudecode.json may be missing or jq unavailable)"
fi

# --- Summary ---

echo ""
echo "================================================================"
echo "tests/test_agent_string.sh: PASS=$PASS FAIL=$FAIL TOTAL=$TOTAL"
echo "================================================================"

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
