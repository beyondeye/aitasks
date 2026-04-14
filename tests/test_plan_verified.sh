#!/usr/bin/env bash
# test_plan_verified.sh - Tests for aitask_plan_verified.sh
# Run: bash tests/test_plan_verified.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$PROJECT_DIR/.aitask-scripts/aitask_plan_verified.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

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

assert_empty() {
    local desc="$1" actual="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -z "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  expected: (empty)"
        echo "  actual:   $actual"
    fi
}

# --- Timestamp helpers (GNU/BSD portable) ---

fresh_ts() {
    date '+%Y-%m-%d %H:%M'
}

stale_ts() {
    if date -d "48 hours ago" '+%Y-%m-%d %H:%M' 2>/dev/null; then
        :
    else
        date -v-48H '+%Y-%m-%d %H:%M'
    fi
}

# --- Plan file factories ---

make_plan_no_field() {
    local path="$1"
    cat > "$path" <<'EOF'
---
Task: t999_test.md
Base branch: main
---

# Body
EOF
}

make_plan_empty_list() {
    local path="$1"
    cat > "$path" <<'EOF'
---
Task: t999_test.md
Base branch: main
plan_verified: []
---

# Body
EOF
}

make_plan_with_fresh_entries() {
    local path="$1" count="$2"
    local ts
    ts=$(fresh_ts)
    {
        echo "---"
        echo "Task: t999_test.md"
        echo "Base branch: main"
        echo "plan_verified:"
        local i=1
        while [[ $i -le $count ]]; do
            echo "  - claudecode/opus4_6 @ $ts"
            i=$((i + 1))
        done
        echo "---"
        echo ""
        echo "# Body"
    } > "$path"
}

make_plan_with_stale_entries() {
    local path="$1" count="$2"
    local ts
    ts=$(stale_ts)
    {
        echo "---"
        echo "Task: t999_test.md"
        echo "Base branch: main"
        echo "plan_verified:"
        local i=1
        while [[ $i -le $count ]]; do
            echo "  - claudecode/opus4_6 @ $ts"
            i=$((i + 1))
        done
        echo "---"
        echo ""
        echo "# Body"
    } > "$path"
}

make_plan_with_mixed_entries() {
    local path="$1"
    local fresh
    local stale
    fresh=$(fresh_ts)
    stale=$(stale_ts)
    {
        echo "---"
        echo "Task: t999_test.md"
        echo "Base branch: main"
        echo "plan_verified:"
        echo "  - claudecode/opus4_6 @ $stale"
        echo "  - claudecode/opus4_6 @ $fresh"
        echo "---"
        echo ""
        echo "# Body"
    } > "$path"
}

make_plan_with_malformed() {
    local path="$1"
    local ts
    ts=$(fresh_ts)
    {
        echo "---"
        echo "Task: t999_test.md"
        echo "Base branch: main"
        echo "plan_verified:"
        echo "  - agent_a @ $ts"
        echo "  - broken entry without timestamp"
        echo "  - agent_b @ $ts"
        echo "---"
        echo ""
        echo "# Body"
    } > "$path"
}

# --- Begin tests ---

echo "=== test_plan_verified.sh ==="
echo ""

SANDBOX=$(mktemp -d)
trap 'rm -rf "$SANDBOX"' EXIT

# --- read tests ---

echo "--- read: no field ---"
PLAN="$SANDBOX/p_no_field.md"
make_plan_no_field "$PLAN"
result=$("$HELPER" read "$PLAN")
assert_empty "read with no plan_verified field → empty" "$result"

echo "--- read: empty inline list ---"
PLAN="$SANDBOX/p_empty.md"
make_plan_empty_list "$PLAN"
result=$("$HELPER" read "$PLAN")
assert_empty "read with plan_verified: [] → empty" "$result"

echo "--- read: two entries ---"
PLAN="$SANDBOX/p_two.md"
make_plan_with_fresh_entries "$PLAN" 2
result=$("$HELPER" read "$PLAN")
line_count=$(printf '%s\n' "$result" | wc -l | tr -d ' ')
assert_eq "read two entries → 2 lines" "2" "$line_count"
assert_contains "read two entries → format agent|timestamp" "claudecode/opus4_6|" "$result"

echo "--- read: malformed entry skipped ---"
PLAN="$SANDBOX/p_malformed.md"
make_plan_with_malformed "$PLAN"
result=$("$HELPER" read "$PLAN")
line_count=$(printf '%s\n' "$result" | wc -l | tr -d ' ')
assert_eq "read with malformed → 2 valid lines" "2" "$line_count"
assert_contains "read with malformed → agent_a present" "agent_a|" "$result"
assert_contains "read with malformed → agent_b present" "agent_b|" "$result"

# --- append tests ---

echo "--- append: no field → field inserted ---"
PLAN="$SANDBOX/p_append_nofield.md"
make_plan_no_field "$PLAN"
"$HELPER" append "$PLAN" "claudecode/opus4_6"
result=$("$HELPER" read "$PLAN")
line_count=$(printf '%s\n' "$result" | wc -l | tr -d ' ')
assert_eq "append into no-field plan → 1 entry" "1" "$line_count"
assert_contains "append into no-field plan → entry readable" "claudecode/opus4_6|" "$result"
# Verify the header still has closing --- after insertion
header_close_count=$(grep -c '^---$' "$PLAN")
assert_eq "append into no-field → header still has 2 fence lines" "2" "$header_close_count"

echo "--- append: empty inline list → populated ---"
PLAN="$SANDBOX/p_append_empty.md"
make_plan_empty_list "$PLAN"
"$HELPER" append "$PLAN" "claudecode/opus4_6"
result=$("$HELPER" read "$PLAN")
line_count=$(printf '%s\n' "$result" | wc -l | tr -d ' ')
assert_eq "append into empty_list → 1 entry" "1" "$line_count"
# plan_verified: [] should be gone, replaced with multi-line form
inline_empty=$(grep -c 'plan_verified: \[\]' "$PLAN" || true)
assert_eq "append into empty_list → inline [] replaced" "0" "$inline_empty"

echo "--- append: existing list → appended ---"
PLAN="$SANDBOX/p_append_existing.md"
make_plan_with_fresh_entries "$PLAN" 1
"$HELPER" append "$PLAN" "geminicli/gemini_3"
result=$("$HELPER" read "$PLAN")
line_count=$(printf '%s\n' "$result" | wc -l | tr -d ' ')
assert_eq "append into existing → 2 entries" "2" "$line_count"
assert_contains "append into existing → new agent present" "geminicli/gemini_3|" "$result"
assert_contains "append into existing → old agent still present" "claudecode/opus4_6|" "$result"

# --- decide tests ---

echo "--- decide: no file ---"
result=$("$HELPER" decide "$SANDBOX/does_not_exist.md" 1 24)
assert_contains "decide no file → DECISION:VERIFY" "DECISION:VERIFY" "$result"
assert_contains "decide no file → TOTAL:0" "TOTAL:0" "$result"
assert_contains "decide no file → DISPLAY line present" "DISPLAY:No plan file found" "$result"

echo "--- decide: zero entries ---"
PLAN="$SANDBOX/p_decide_zero.md"
make_plan_no_field "$PLAN"
result=$("$HELPER" decide "$PLAN" 1 24)
assert_contains "decide zero entries → DECISION:VERIFY" "DECISION:VERIFY" "$result"
assert_contains "decide zero entries → TOTAL:0" "TOTAL:0" "$result"
assert_contains "decide zero entries → DISPLAY line present" "DISPLAY:No prior verifications" "$result"

echo "--- decide: 1 fresh, required=1 → SKIP ---"
PLAN="$SANDBOX/p_decide_1fresh_req1.md"
make_plan_with_fresh_entries "$PLAN" 1
result=$("$HELPER" decide "$PLAN" 1 24)
assert_contains "decide 1f req1 → DECISION:SKIP" "DECISION:SKIP" "$result"
assert_contains "decide 1f req1 → FRESH:1" "FRESH:1" "$result"
assert_contains "decide 1f req1 → STALE:0" "STALE:0" "$result"
assert_contains "decide 1f req1 → TOTAL:1" "TOTAL:1" "$result"

echo "--- decide: 1 fresh, required=2 → ASK_STALE ---"
PLAN="$SANDBOX/p_decide_1fresh_req2.md"
make_plan_with_fresh_entries "$PLAN" 1
result=$("$HELPER" decide "$PLAN" 2 24)
assert_contains "decide 1f req2 → DECISION:ASK_STALE" "DECISION:ASK_STALE" "$result"
assert_contains "decide 1f req2 → FRESH:1" "FRESH:1" "$result"

echo "--- decide: 1 stale, required=1 → ASK_STALE ---"
PLAN="$SANDBOX/p_decide_1stale_req1.md"
make_plan_with_stale_entries "$PLAN" 1
result=$("$HELPER" decide "$PLAN" 1 24)
assert_contains "decide 1s req1 → DECISION:ASK_STALE" "DECISION:ASK_STALE" "$result"
assert_contains "decide 1s req1 → FRESH:0" "FRESH:0" "$result"
assert_contains "decide 1s req1 → STALE:1" "STALE:1" "$result"

echo "--- decide: 2 fresh, required=1 → SKIP ---"
PLAN="$SANDBOX/p_decide_2fresh_req1.md"
make_plan_with_fresh_entries "$PLAN" 2
result=$("$HELPER" decide "$PLAN" 1 24)
assert_contains "decide 2f req1 → DECISION:SKIP" "DECISION:SKIP" "$result"
assert_contains "decide 2f req1 → FRESH:2" "FRESH:2" "$result"

echo "--- decide: 1 fresh + 1 stale, required=1 → SKIP ---"
PLAN="$SANDBOX/p_decide_mix_req1.md"
make_plan_with_mixed_entries "$PLAN"
result=$("$HELPER" decide "$PLAN" 1 24)
assert_contains "decide mix req1 → DECISION:SKIP" "DECISION:SKIP" "$result"
assert_contains "decide mix req1 → FRESH:1" "FRESH:1" "$result"
assert_contains "decide mix req1 → STALE:1" "STALE:1" "$result"

echo "--- decide: 1 fresh + 1 stale, required=2 → ASK_STALE ---"
PLAN="$SANDBOX/p_decide_mix_req2.md"
make_plan_with_mixed_entries "$PLAN"
result=$("$HELPER" decide "$PLAN" 2 24)
assert_contains "decide mix req2 → DECISION:ASK_STALE" "DECISION:ASK_STALE" "$result"

echo "--- decide: DISPLAY line emitted ---"
PLAN="$SANDBOX/p_decide_display.md"
make_plan_no_field "$PLAN"
result=$("$HELPER" decide "$PLAN" 1 24)
assert_contains "decide → DISPLAY key present" "DISPLAY:" "$result"

echo "--- decide: bad required arg ---"
PLAN="$SANDBOX/p_decide_bad.md"
make_plan_no_field "$PLAN"
set +e
err=$("$HELPER" decide "$PLAN" abc 24 2>&1)
rc=$?
set -e
assert_contains "decide bad required → non-zero exit" "positive integer" "$err"
TOTAL=$((TOTAL + 1))
if [[ $rc -ne 0 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: decide bad required → expected non-zero exit code, got $rc"
fi

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
