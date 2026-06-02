#!/usr/bin/env bash
# test_risk_mitigation_landed.sh - Tests for aitask_risk_mitigation_landed.sh
# Run: bash tests/test_risk_mitigation_landed.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$PROJECT_DIR/.aitask-scripts/aitask_risk_mitigation_landed.sh"

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
        echo "FAIL: $desc"
        echo "  expected: $expected"
        echo "  actual:   $actual"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -q -- "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  expected to contain: $expected"
        echo "  actual: $actual"
    fi
}

assert_not_contains() {
    local desc="$1" needle="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -q -- "$needle"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  expected NOT to contain: $needle"
        echo "  actual: $actual"
    else
        PASS=$((PASS + 1))
    fi
}

# --- Fixed timestamps (deterministic; no date dependency) ---
VERIFY_TS="2026-06-01 10:00"
LATER_TS="2026-06-01 12:00"     # after VERIFY_TS  → landed
EARLIER_TS="2026-06-01 08:00"   # before VERIFY_TS → not landed

# --- Fixture factories ---

make_task() {
    # make_task <path> <inline-list>   e.g. "[884_4]" or "[884_4, 884_9]"
    local path="$1" list="$2"
    cat > "$path" <<EOF
---
priority: medium
issue_type: enhancement
risk_mitigation_tasks: $list
---

# Task body
EOF
}

make_task_no_field() {
    local path="$1"
    cat > "$path" <<'EOF'
---
priority: medium
issue_type: enhancement
---

# Task body
EOF
}

make_plan() {
    # make_plan <path> <verify_ts>   (empty verify_ts → no plan_verified entry)
    local path="$1" verify_ts="$2"
    if [[ -z "$verify_ts" ]]; then
        cat > "$path" <<'EOF'
---
Task: t900_test.md
Base branch: main
---

# Plan body
EOF
    else
        {
            echo "---"
            echo "Task: t900_test.md"
            echo "Base branch: main"
            echo "plan_verified:"
            echo "  - claudecode/opus4_8 @ $verify_ts"
            echo "---"
            echo ""
            echo "# Plan body"
        } > "$path"
    fi
}

make_archived_mitigation() {
    # make_archived_mitigation <archived_dir> <parent> <child> <completed_at>
    local adir="$1" parent="$2" child="$3" completed="$4"
    mkdir -p "$adir/t$parent"
    cat > "$adir/t$parent/t${parent}_${child}_mitigation.md" <<EOF
---
status: Done
completed_at: $completed
---

# Archived mitigation
EOF
}

echo "=== test_risk_mitigation_landed.sh ==="
echo ""

SANDBOX=$(mktemp -d)
trap 'rm -rf "$SANDBOX"' EXIT
ADIR="$SANDBOX/archived"
mkdir -p "$ADIR"
export ARCHIVED_DIR="$ADIR"
cd "$PROJECT_DIR"

# --- 1. Absent field → no-op ---
echo "--- absent risk_mitigation_tasks → FORCE_VERIFY:0 ---"
TASK="$SANDBOX/t_nofield.md"; PLAN="$SANDBOX/p_nofield.md"
make_task_no_field "$TASK"
make_plan "$PLAN" "$VERIFY_TS"
result=$("$HELPER" "$TASK" "$PLAN")
assert_eq "absent field → FORCE_VERIFY:0 only" "FORCE_VERIFY:0" "$result"
assert_not_contains "absent field → no LANDED lines" "LANDED:" "$result"

# --- 2. Field present but no prior verification → no-op ---
echo "--- no prior plan_verified → FORCE_VERIFY:0 ---"
TASK="$SANDBOX/t_noverify.md"; PLAN="$SANDBOX/p_noverify.md"
make_task "$TASK" "[884_4]"
make_plan "$PLAN" ""   # no plan_verified entry
make_archived_mitigation "$ADIR" 884 4 "$LATER_TS"
result=$("$HELPER" "$TASK" "$PLAN")
assert_eq "no prior verification → FORCE_VERIFY:0" "FORCE_VERIFY:0" "$result"

# --- 3. One mitigation landed AFTER last verify → FORCE_VERIFY:1 + LANDED ---
echo "--- one mitigation landed later → FORCE_VERIFY:1 ---"
TASK="$SANDBOX/t_one.md"; PLAN="$SANDBOX/p_one.md"
make_task "$TASK" "[884_4]"
make_plan "$PLAN" "$VERIFY_TS"
# (archived t884_4 already created above with LATER_TS)
result=$("$HELPER" "$TASK" "$PLAN")
assert_contains "one later → FORCE_VERIFY:1" "FORCE_VERIFY:1" "$result"
assert_contains "one later → LANDED line for 884_4" "LANDED:884_4|$LATER_TS" "$result"

# --- 4. Two mitigations landed → both listed ---
echo "--- two mitigations landed → both listed ---"
TASK="$SANDBOX/t_two.md"; PLAN="$SANDBOX/p_two.md"
make_task "$TASK" "[884_4, 884_9]"
make_plan "$PLAN" "$VERIFY_TS"
make_archived_mitigation "$ADIR" 884 9 "$LATER_TS"
result=$("$HELPER" "$TASK" "$PLAN")
assert_contains "two landed → FORCE_VERIFY:1" "FORCE_VERIFY:1" "$result"
assert_contains "two landed → 884_4 listed" "LANDED:884_4|" "$result"
assert_contains "two landed → 884_9 listed" "LANDED:884_9|" "$result"

# --- 5. Mitigation completed BEFORE last verify → not landed ---
echo "--- mitigation completed earlier than verify → FORCE_VERIFY:0 ---"
TASK="$SANDBOX/t_early.md"; PLAN="$SANDBOX/p_early.md"
make_task "$TASK" "[771_1]"
make_plan "$PLAN" "$VERIFY_TS"
make_archived_mitigation "$ADIR" 771 1 "$EARLIER_TS"
result=$("$HELPER" "$TASK" "$PLAN")
assert_eq "earlier completed_at → FORCE_VERIFY:0" "FORCE_VERIFY:0" "$result"

# --- 6. Mitigation not yet archived (NOT_FOUND) → skipped ---
echo "--- mitigation not archived → skipped ---"
TASK="$SANDBOX/t_pending.md"; PLAN="$SANDBOX/p_pending.md"
make_task "$TASK" "[999_3]"   # no archived file created for 999_3
make_plan "$PLAN" "$VERIFY_TS"
result=$("$HELPER" "$TASK" "$PLAN")
assert_eq "unlanded mitigation skipped → FORCE_VERIFY:0" "FORCE_VERIFY:0" "$result"

# --- 7. Mixed: one landed, one pending → FORCE_VERIFY:1 with only the landed one ---
echo "--- mixed landed + pending → only landed listed ---"
TASK="$SANDBOX/t_mixed.md"; PLAN="$SANDBOX/p_mixed.md"
make_task "$TASK" "[884_4, 999_3]"
make_plan "$PLAN" "$VERIFY_TS"
result=$("$HELPER" "$TASK" "$PLAN")
assert_contains "mixed → FORCE_VERIFY:1" "FORCE_VERIFY:1" "$result"
assert_contains "mixed → landed 884_4 listed" "LANDED:884_4|" "$result"
assert_not_contains "mixed → pending 999_3 not listed" "999_3" "$result"

# --- Summary ---
echo ""
echo "=== Results ==="
echo "Total:  $TOTAL"
echo "Pass:   $PASS"
echo "Fail:   $FAIL"

if [[ $FAIL -eq 0 ]]; then
    echo "PASS"
    exit 0
else
    echo "FAIL"
    exit 1
fi
