#!/usr/bin/env bash
# test_shadow_context.sh - Automated tests for aitask_shadow_context.sh
# Run: bash tests/test_shadow_context.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

SHADOW="$PROJECT_DIR/.aitask-scripts/aitask_shadow_context.sh"

# --- Setup mock directory structure ---

TMPDIR_BASE=$(mktemp -d "${TMPDIR:-/tmp}/test_shadow_ctx_XXXXXX")
trap 'rm -rf "$TMPDIR_BASE"' EXIT

BASE="$TMPDIR_BASE/repo"
mkdir -p "$BASE"

# Active parent task + plan
mkdir -p "$BASE/aitasks" "$BASE/aiplans"
printf -- '---\nstatus: Ready\n---\nParent 42\n' > "$BASE/aitasks/t42_fix_bug.md"
printf -- '---\nPlan\n---\n' > "$BASE/aiplans/p42_fix_bug.md"

# Active child task + plan (primary use case: child id resolution)
mkdir -p "$BASE/aitasks/t16" "$BASE/aiplans/p16"
printf -- '---\nstatus: Ready\n---\nChild 16_2\n' > "$BASE/aitasks/t16/t16_2_add_login.md"
printf -- '---\nPlan child\n---\n' > "$BASE/aiplans/p16/p16_2_add_login.md"

# Active child with MULTIPLE matching plans (most-recent selection)
printf -- '---\nstatus: Ready\n---\nChild 16_9\n' > "$BASE/aitasks/t16/t16_9_multi.md"
printf -- '---\nPlan aaa\n---\n' > "$BASE/aiplans/p16/p16_9_aaa_plan.md"
printf -- '---\nPlan zzz\n---\n' > "$BASE/aiplans/p16/p16_9_zzz_plan.md"

# Archived child task (active-miss -> archived fallback), no active twin
mkdir -p "$BASE/aitasks/archived/t20"
printf -- '---\nstatus: Done\n---\nArchived 20_1\n' > "$BASE/aitasks/archived/t20/t20_1_old_task.md"

# Sibling-context fixture under parent 10 (mirrors test_query.sh)
mkdir -p "$BASE/aitasks/t10" "$BASE/aiplans/p10"
mkdir -p "$BASE/aitasks/archived/t10" "$BASE/aiplans/archived/p10"
printf -- '---\nstatus: Ready\n---\nPending sibling 10_3\n' > "$BASE/aitasks/t10/t10_3_third.md"
printf -- '---\nPlan\n---\n' > "$BASE/aiplans/p10/p10_3_third.md"
printf -- '---\nstatus: Done\n---\nArchived 10_1\n' > "$BASE/aitasks/archived/t10/t10_1_first.md"
printf -- '---\nstatus: Done\n---\nArchived 10_2\n' > "$BASE/aitasks/archived/t10/t10_2_second.md"
printf -- '---\nPlan\n---\n' > "$BASE/aiplans/archived/p10/p10_1_first.md"

export TASK_DIR="$BASE/aitasks"
export PLAN_DIR="$BASE/aiplans"
export ARCHIVED_DIR="$BASE/aitasks/archived"
export ARCHIVED_PLAN_DIR="$BASE/aiplans/archived"

# ============================================================
# Tests: active child resolution (the use-case-2 path)
# ============================================================
echo "--- active child ---"

out=$("$SHADOW" 16_2)
assert_contains "child 16_2 task resolved"  "TASK_FILE:" "$out"
assert_contains "child 16_2 task path"      "t16/t16_2_add_login.md" "$out"
assert_contains "child 16_2 plan resolved"  "PLAN_FILE:" "$out"
assert_contains "child 16_2 plan path"      "p16/p16_2_add_login.md" "$out"
assert_not_contains "child 16_2 no NOT_FOUND" "NOT_FOUND" "$out"

# t-prefix accepted, same result
out=$("$SHADOW" t16_2)
assert_contains "child t16_2 prefix task" "t16_2_add_login.md" "$out"
assert_contains "child t16_2 prefix plan" "p16_2_add_login.md" "$out"

# ============================================================
# Tests: active parent resolution
# ============================================================
echo "--- active parent ---"

out=$("$SHADOW" 42)
assert_contains "parent 42 task path" "t42_fix_bug.md" "$out"
assert_contains "parent 42 plan path" "p42_fix_bug.md" "$out"

out=$("$SHADOW" t42)
assert_contains "parent t42 prefix task" "t42_fix_bug.md" "$out"

# ============================================================
# Tests: most-recent plan selection (multiple matches)
# ============================================================
echo "--- most-recent plan ---"

out=$("$SHADOW" 16_9)
plan_line=$(printf '%s\n' "$out" | grep '^PLAN_FILE:')
assert_contains "16_9 picks lexicographically-last plan" "p16_9_zzz_plan.md" "$plan_line"
assert_not_contains "16_9 not the earlier plan" "p16_9_aaa_plan.md" "$plan_line"

# ============================================================
# Tests: archived task fallback
# ============================================================
echo "--- archived fallback ---"

out=$("$SHADOW" 20_1)
assert_contains "20_1 falls back to archived task" "t20/t20_1_old_task.md" "$out"
assert_contains "20_1 task line present" "TASK_FILE:" "$out"
# No active or archived plan for 20_1
assert_contains "20_1 plan not found" "PLAN_FILE:NOT_FOUND" "$out"

# ============================================================
# Tests: missing task/plan
# ============================================================
echo "--- missing ---"

out=$("$SHADOW" 999)
assert_contains "999 task not found" "TASK_FILE:NOT_FOUND" "$out"
assert_contains "999 plan not found" "PLAN_FILE:NOT_FOUND" "$out"

out=$("$SHADOW" 999_9)
assert_contains "999_9 child task not found" "TASK_FILE:NOT_FOUND" "$out"
assert_contains "999_9 child plan not found" "PLAN_FILE:NOT_FOUND" "$out"

# ============================================================
# Tests: sibling context (flag-gated)
# ============================================================
echo "--- siblings ---"

out=$("$SHADOW" --siblings 10_3)
assert_contains "siblings emits SIBLING line" "SIBLING:" "$out"
assert_contains "siblings includes pending sibling" "t10_3_third.md" "$out"
assert_contains "siblings includes archived plan" "p10_1_first.md" "$out"

# Default (no flag) emits no sibling lines
out=$("$SHADOW" 10_3)
assert_not_contains "no --siblings, no SIBLING line" "SIBLING:" "$out"

# --siblings works in either position
out=$("$SHADOW" 10_3 --siblings)
assert_contains "siblings flag trailing position" "SIBLING:" "$out"

# ============================================================
# Tests: input validation
# ============================================================
echo "--- input validation ---"

out=$("$SHADOW" abc 2>&1 || true)
assert_contains "invalid id rejected" "Invalid task id" "$out"

rc=0
"$SHADOW" abc >/dev/null 2>&1 || rc=$?
assert_eq "invalid id exits non-zero" "1" "$rc"

out=$("$SHADOW" --help 2>&1)
assert_contains "help shows usage" "Usage:" "$out"

out=$("$SHADOW" 2>&1 || true)
assert_contains "missing id rejected" "task_id required" "$out"

# ============================================================
# Summary
# ============================================================
echo ""
echo "=============================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=============================="

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
