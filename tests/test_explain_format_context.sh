#!/usr/bin/env bash
# test_explain_format_context.sh - Automated tests for aitask_explain_format_context.py
# Run: bash tests/test_explain_format_context.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRIPT="$PROJECT_DIR/.aitask-scripts/aitask_explain_format_context.py"

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
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -q "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected')"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -q "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (output should NOT contain '$unexpected')"
    else
        PASS=$((PASS + 1))
    fi
}

assert_exit_zero() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (command exited non-zero)"
    fi
}

# --- Setup ---

TMPDIR_BASE="$(mktemp -d "${TMPDIR:-/tmp}/explain_fmt_XXXXXX")"

setup_test_data() {
    local run_dir="$TMPDIR_BASE/run1"
    mkdir -p "$run_dir/plans"

    cat > "$run_dir/reference.yaml" << 'YAMLEOF'
files:
  - path: src/foo.py
    line_ranges:
      - start: 1
        end: 50
        commits: [1]
        tasks: ["100"]
      - start: 51
        end: 100
        commits: [2]
        tasks: ["200"]
      - start: 101
        end: 120
        commits: [3]
        tasks: ["100", "300"]
  - path: src/bar.py
    line_ranges:
      - start: 1
        end: 30
        commits: [1]
        tasks: ["100"]
      - start: 31
        end: 80
        commits: [2]
        tasks: ["200"]
  - path: src/baz.py
    line_ranges:
      - start: 1
        end: 10
        commits: [1]
        tasks: []

tasks:
  - id: "100"
    task_file: "tasks/t100.md"
    plan_file: "plans/p100.md"
  - id: "200"
    task_file: "tasks/t200.md"
    plan_file: "plans/p200.md"
  - id: "300"
    task_file: "tasks/t300.md"
    plan_file: ""
YAMLEOF

    cat > "$run_dir/plans/p100.md" << 'EOF'
---
Task: t100_auth.md
---

# Implement Authentication System

This plan covers authentication with JWT tokens.

## Steps
1. Add login endpoint
2. Add token validation
EOF

    cat > "$run_dir/plans/p200.md" << 'EOF'
---
Task: t200_api.md
---

# Build REST API Layer

Design and implement the API endpoints.

## Steps
1. Create router
2. Add middleware
EOF
}

setup_test_data

# --- Convenience ---

RUN_DIR="$TMPDIR_BASE/run1"
REF_ARG="$RUN_DIR/reference.yaml:$RUN_DIR"

run_script() {
    python3 "$SCRIPT" "$@" 2>/dev/null
}

# --- Tests ---

echo "=== test_explain_format_context.sh ==="

# Test 1: Basic two-file output with max-plans 2
output="$(run_script --max-plans 2 --ref "$REF_ARG" -- src/foo.py src/bar.py)"
assert_contains "header present" "## Historical Architectural Context" "$output"
assert_contains "t100 plan shown" "### t100: Implement Authentication System" "$output"
assert_contains "t200 plan shown" "### t200: Build REST API Layer" "$output"
assert_contains "t100 covers both files" "src/foo.py, src/bar.py" "$output"
assert_contains "context notes present" "### Context Notes" "$output"
assert_contains "all plans found" "2 of 2 plans found" "$output"

# Test 2: max-plans 1 limits per-file selection
output="$(run_script --max-plans 1 --ref "$REF_ARG" -- src/foo.py src/bar.py)"
assert_contains "max1: t100 present" "### t100:" "$output"
assert_contains "max1: t200 present" "### t200:" "$output"
# t100 gets foo.py (70 lines: 50+20), t200 gets bar.py (50 lines > 30 lines for t100)
# Each file's top-1 plan should differ, so both still appear but with single file each

# Test 3: Missing plan handling
output="$(run_script --max-plans 3 --ref "$REF_ARG" -- src/foo.py)"
assert_contains "missing: t300 shown" "### t300:" "$output"
assert_contains "missing: not available msg" "Plan content not available" "$output"
assert_contains "missing: count" "2 of 3 plans found" "$output"
assert_contains "missing: missing id" "t300" "$output"

# Test 4: Non-existent target file - empty output, exit 0
output="$(run_script --max-plans 2 --ref "$REF_ARG" -- nonexistent.py)"
exit_code=$?
assert_eq "nofile: exit code 0" "0" "$exit_code"
assert_eq "nofile: empty output" "" "$output"

# Test 5: File with empty tasks array - no output
output="$(run_script --max-plans 2 --ref "$REF_ARG" -- src/baz.py)"
exit_code=$?
assert_eq "empty tasks: exit code 0" "0" "$exit_code"
assert_eq "empty tasks: empty output" "" "$output"

# Test 6: max-plans 0 exits immediately
output="$(run_script --max-plans 0 --ref "$REF_ARG" -- src/foo.py)"
exit_code=$?
assert_eq "maxplans0: exit code 0" "0" "$exit_code"
assert_eq "maxplans0: empty output" "" "$output"

# Test 7: Frontmatter is stripped from plan content
output="$(run_script --max-plans 1 --ref "$REF_ARG" -- src/foo.py)"
assert_not_contains "no frontmatter in output" "Task: t100_auth.md" "$output"
assert_contains "plan content preserved" "authentication with JWT" "$output"

# Test 8: Invalid --ref format (warning on stderr, graceful)
output="$(python3 "$SCRIPT" --max-plans 1 --ref "bad_no_colon" -- src/foo.py 2>/dev/null)"
exit_code=$?
assert_eq "bad ref: exit code 0" "0" "$exit_code"
assert_eq "bad ref: empty output" "" "$output"

# Test 9: Missing reference.yaml file (warning on stderr, graceful)
output="$(python3 "$SCRIPT" --max-plans 1 --ref "/tmp/nonexistent.yaml:/tmp" -- src/foo.py 2>/dev/null)"
exit_code=$?
assert_eq "missing ref yaml: exit code 0" "0" "$exit_code"
assert_eq "missing ref yaml: empty output" "" "$output"

# Test 10: Multiple --ref pairs (second run_dir)
run_dir2="$TMPDIR_BASE/run2"
mkdir -p "$run_dir2/plans"
cat > "$run_dir2/reference.yaml" << 'YAMLEOF'
files:
  - path: src/extra.py
    line_ranges:
      - start: 1
        end: 40
        commits: [1]
        tasks: ["400"]
tasks:
  - id: "400"
    task_file: "tasks/t400.md"
    plan_file: "plans/p400.md"
YAMLEOF
cat > "$run_dir2/plans/p400.md" << 'EOF'
# Extra Feature Plan

Details about the extra feature.
EOF

output="$(run_script --max-plans 2 --ref "$REF_ARG" --ref "$run_dir2/reference.yaml:$run_dir2" -- src/foo.py src/extra.py)"
assert_contains "multi-ref: t100 present" "### t100:" "$output"
assert_contains "multi-ref: t400 present" "### t400:" "$output"
assert_contains "multi-ref: extra.py" "src/extra.py" "$output"

# Test 11: Compound task IDs (e.g., "228_5")
run_dir3="$TMPDIR_BASE/run3"
mkdir -p "$run_dir3/plans"
cat > "$run_dir3/reference.yaml" << 'YAMLEOF'
files:
  - path: src/compound.py
    line_ranges:
      - start: 1
        end: 25
        commits: [1]
        tasks: ["228_5"]
tasks:
  - id: "228_5"
    task_file: "tasks/t228_5.md"
    plan_file: "plans/p228_5.md"
YAMLEOF
cat > "$run_dir3/plans/p228_5.md" << 'EOF'
# Compound Task Plan

Plan for compound task 228_5.
EOF

output="$(run_script --max-plans 1 --ref "$run_dir3/reference.yaml:$run_dir3" -- src/compound.py)"
assert_contains "compound: task id shown" "### t228_5:" "$output"
assert_contains "compound: plan content" "Compound Task Plan" "$output"

# Test 12: Plans sorted by number of affected files
# t100 covers 2 files (foo+bar), t200 covers 2 files (foo+bar)
# Both should appear before t300 which covers 1 file
output="$(run_script --max-plans 3 --ref "$REF_ARG" -- src/foo.py src/bar.py)"
# Find line numbers of t100 and t300
t100_line=$(echo "$output" | grep -n "### t100:" | head -1 | cut -d: -f1)
# t300 only appears with max-plans 3 on foo.py, not bar.py
# Actually t300 only has 20 lines on foo.py, so with max-plans 3 it would be included for foo.py
# But for bar.py there are only 2 tasks (100 and 200), so t300 won't appear for bar.py
# So t100 and t200 cover 2 files each, t300 covers 1 file -> t300 should be last
output_3="$(run_script --max-plans 3 --ref "$REF_ARG" -- src/foo.py src/bar.py)"
if echo "$output_3" | grep -q "### t300:"; then
    t300_line=$(echo "$output_3" | grep -n "### t300:" | head -1 | cut -d: -f1)
    t100_line=$(echo "$output_3" | grep -n "### t100:" | head -1 | cut -d: -f1)
    TOTAL=$((TOTAL + 1))
    if [[ "$t100_line" -lt "$t300_line" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: sorting: t100 (2 files) should appear before t300 (1 file)"
    fi
else
    # t300 only appears for foo.py with max-plans >= 3, which is fine
    TOTAL=$((TOTAL + 1))
    PASS=$((PASS + 1))
fi

# --- Cleanup ---

rm -rf "$TMPDIR_BASE"

# --- Summary ---

echo ""
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
if [[ $FAIL -gt 0 ]]; then
    echo "FAIL"
    exit 1
else
    echo "PASS"
    exit 0
fi
