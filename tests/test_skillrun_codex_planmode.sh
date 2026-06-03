#!/usr/bin/env bash
# test_skillrun_codex_planmode.sh - Verify aitask_skillrun.sh routes Codex
# skill launches through the plan-mode policy (lib/codex_plan_policy.sh):
# planning skills (pick, explore) via the /plan PTY helper; analysis skills
# (qa, explain) directly in Codex default mode.
#
# Uses --dry-run, which is side-effect-free, so it runs against the real repo.
# Run: bash tests/test_skillrun_codex_planmode.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLRUN="$PROJECT_DIR/.aitask-scripts/aitask_skillrun.sh"

PASS=0
FAIL=0
TOTAL=0

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

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qi -- "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output NOT containing '$unexpected', got '$actual')"
    else
        PASS=$((PASS + 1))
    fi
}

run_dry() {
    # $1 = skill, rest = skill args
    local skill="$1"; shift
    bash "$SKILLRUN" "$skill" --profile fast --agent-string codex/gpt5_4 --dry-run -- "$@" 2>&1
}

# --- Analysis skills launch directly in default mode (no plan helper) ---
echo "--- qa launches directly in Codex default mode ---"
out=$(run_dry qa 42)
assert_not_contains "skillrun qa bypasses plan helper" "aitask_codex_plan_invoke" "$out"
assert_contains "skillrun qa prompts aitask-qa" "aitask-qa" "$out"
assert_contains "skillrun qa is a codex launch" "codex -m gpt-5.4" "$out"

echo "--- explain launches directly in Codex default mode ---"
out=$(run_dry explain src/main.py)
assert_not_contains "skillrun explain bypasses plan helper" "aitask_codex_plan_invoke" "$out"
assert_contains "skillrun explain prompts aitask-explain" "aitask-explain" "$out"

# --- Planning skills go through the /plan PTY helper ---
echo "--- pick uses the plan-mode helper ---"
out=$(run_dry pick 42)
assert_contains "skillrun pick uses plan helper" "aitask_codex_plan_invoke" "$out"
assert_contains "skillrun pick prompts aitask-pick" "aitask-pick" "$out"

echo "--- explore uses the plan-mode helper ---"
out=$(bash "$SKILLRUN" explore --profile fast --agent-string codex/gpt5_4 --dry-run 2>&1)
assert_contains "skillrun explore uses plan helper" "aitask_codex_plan_invoke" "$out"
assert_contains "skillrun explore prompts aitask-explore" "aitask-explore" "$out"

# --- Summary ---
echo ""
echo "=== Results ==="
echo "PASS: $PASS / $TOTAL"
if [[ "$FAIL" -gt 0 ]]; then
    echo "$FAIL test(s) failed."
    exit 1
fi
echo "All tests passed."
