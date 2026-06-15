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

# Shared assertion helpers (see tests/lib/asserts.sh)
. "$PROJECT_DIR/tests/lib/asserts.sh"


run_dry() {
    # $1 = skill, rest = skill args
    local skill="$1"; shift
    bash "$SKILLRUN" "$skill" --profile fast --agent-string codex/gpt5_4 --dry-run -- "$@" 2>&1
}

# --- Analysis skills launch directly in default mode (no plan helper) ---
echo "--- qa launches directly in Codex default mode ---"
out=$(run_dry qa 42)
assert_not_contains_ci "skillrun qa bypasses plan helper" "aitask_codex_plan_invoke" "$out"
assert_contains_ci "skillrun qa prompts aitask-qa" "aitask-qa" "$out"
assert_contains_ci "skillrun qa is a codex launch" "codex -m gpt-5.4" "$out"

echo "--- explain launches directly in Codex default mode ---"
out=$(run_dry explain src/main.py)
assert_not_contains_ci "skillrun explain bypasses plan helper" "aitask_codex_plan_invoke" "$out"
assert_contains_ci "skillrun explain prompts aitask-explain" "aitask-explain" "$out"

echo "--- shadow launches directly in Codex default mode ---"
out=$(run_dry shadow %7 100_2)
assert_not_contains_ci "skillrun shadow bypasses plan helper" "aitask_codex_plan_invoke" "$out"
assert_contains_ci "skillrun shadow prompts aitask-shadow" "aitask-shadow" "$out"
assert_contains_ci "skillrun shadow forwards pane id" "%7" "$out"
assert_contains_ci "skillrun shadow forwards task id" "100_2" "$out"

# --- Planning skills go through the /plan PTY helper ---
echo "--- pick uses the plan-mode helper ---"
out=$(run_dry pick 42)
assert_contains_ci "skillrun pick uses plan helper" "aitask_codex_plan_invoke" "$out"
assert_contains_ci "skillrun pick prompts aitask-pick" "aitask-pick" "$out"

echo "--- explore uses the plan-mode helper ---"
out=$(bash "$SKILLRUN" explore --profile fast --agent-string codex/gpt5_4 --dry-run 2>&1)
assert_contains_ci "skillrun explore uses plan helper" "aitask_codex_plan_invoke" "$out"
assert_contains_ci "skillrun explore prompts aitask-explore" "aitask-explore" "$out"

# --- Summary ---
echo ""
echo "=== Results ==="
echo "PASS: $PASS / $TOTAL"
if [[ "$FAIL" -gt 0 ]]; then
    echo "$FAIL test(s) failed."
    exit 1
fi
echo "All tests passed."
