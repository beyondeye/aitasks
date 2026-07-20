#!/usr/bin/env bash
# test_codex_no_plan_injection.sh - Structural guard (t1171).
#
# The framework used to wrap Codex skill launches in a PTY helper that typed
# "/plan <prompt>" into the composer, forcing Codex into plan mode. That was a
# workaround for request_user_input being unavailable outside plan mode; the
# limitation is gone (ait setup enables default_mode_request_user_input), and
# forcing plan mode broke dynamic skill rendering (the stubs' render step writes
# files, which read-only plan mode blocks).
#
# This test asserts the injection cannot come back: for EVERY operation, on BOTH
# real dry-run surfaces, the launch command must contain neither the helper name
# nor a "/plan" token.
#
# Uses --dry-run, which is side-effect-free, so it runs against the real repo.
# Run: bash tests/test_codex_no_plan_injection.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CODEAGENT="$PROJECT_DIR/.aitask-scripts/aitask_codeagent.sh"
SKILLRUN="$PROJECT_DIR/.aitask-scripts/aitask_skillrun.sh"

PASS=0
FAIL=0
TOTAL=0

# Shared assertion helpers (see tests/lib/asserts.sh)
. "$PROJECT_DIR/tests/lib/asserts.sh"

# assert_no_injection <label> <output>
# Both sentinels must be absent: the helper script name and the /plan token the
# helper used to type into the composer.
assert_no_injection() {
    local label="$1" out="$2"
    assert_not_contains_ci "$label: no plan helper" "aitask_codex_plan_invoke" "$out"
    assert_not_contains_ci "$label: no /plan token" "/plan" "$out"
}

# --- Surface 1: ait codeagent invoke ---
echo "--- codeagent invoke: no operation injects /plan ---"

run_codeagent() {
    local op="$1"; shift
    "$CODEAGENT" --agent-string codex/gpt5_4 --dry-run invoke "$op" "$@" 2>&1
}

assert_no_injection "codeagent pick"         "$(run_codeagent pick 42)"
assert_no_injection "codeagent explore"      "$(run_codeagent explore)"
assert_no_injection "codeagent qa"           "$(run_codeagent qa 42)"
assert_no_injection "codeagent explain"      "$(run_codeagent explain src/main.py)"
assert_no_injection "codeagent shadow"       "$(run_codeagent shadow %7 100_2)"
assert_no_injection "codeagent learn"        "$(run_codeagent learn %7)"
assert_no_injection "codeagent raw"          "$(run_codeagent raw hello)"
assert_no_injection "codeagent batch-review" "$(run_codeagent batch-review review-me)"

# --- Surface 2: aitask_skillrun.sh ---
echo "--- skillrun: no skill injects /plan ---"

run_skillrun() {
    local skill="$1"; shift
    bash "$SKILLRUN" "$skill" --profile fast --agent-string codex/gpt5_4 --dry-run -- "$@" 2>&1
}

assert_no_injection "skillrun pick"    "$(run_skillrun pick 42)"
assert_no_injection "skillrun qa"      "$(run_skillrun qa 42)"
assert_no_injection "skillrun explain" "$(run_skillrun explain src/main.py)"
assert_no_injection "skillrun shadow"  "$(run_skillrun shadow %7 100_2)"
assert_no_injection "skillrun explore" \
    "$(bash "$SKILLRUN" explore --profile fast --agent-string codex/gpt5_4 --dry-run 2>&1)"

# --- The machinery itself is gone ---
echo "--- deleted machinery leaves no trace ---"

assert_not_exists() {
    local label="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -e "$path" ]]; then
        echo "FAIL: $label (still present: $path)"
        FAIL=$((FAIL + 1))
    else
        PASS=$((PASS + 1))
    fi
}

assert_not_exists "plan PTY helper deleted" "$PROJECT_DIR/.aitask-scripts/aitask_codex_plan_invoke.py"
assert_not_exists "plan policy lib deleted" "$PROJECT_DIR/.aitask-scripts/lib/codex_plan_policy.sh"

# No production source still references the removed policy function or helper.
# Scoped to .aitask-scripts deliberately: tests legitimately name these strings
# inside assert_not_contains negative controls.
refs=$(grep -rn 'codex_plan_policy\|codex_plan_invoke\|codex_skill_forces_plan_mode' \
    "$PROJECT_DIR/.aitask-scripts" 2>/dev/null || true)
TOTAL=$((TOTAL + 1))
if [[ -n "$refs" ]]; then
    echo "FAIL: dangling references to the removed plan-mode machinery:"
    echo "$refs"
    FAIL=$((FAIL + 1))
else
    PASS=$((PASS + 1))
fi

# --- Summary ---
echo ""
echo "=== Results ==="
echo "PASS: $PASS / $TOTAL"
if [[ "$FAIL" -gt 0 ]]; then
    echo "$FAIL test(s) failed."
    exit 1
fi
echo "All tests passed."
