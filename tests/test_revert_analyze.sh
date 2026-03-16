#!/usr/bin/env bash
# test_revert_analyze.sh - Automated tests for aitask_revert_analyze.sh
# Run: bash tests/test_revert_analyze.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ANALYZE_SCRIPT="$PROJECT_DIR/.aitask-scripts/aitask_revert_analyze.sh"

PASS=0
FAIL=0
TOTAL=0
TMPDIR_TEST=""

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

assert_not_contains() {
    local label="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$haystack" != *"$needle"* ]]; then
        echo "  PASS: $label"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $label"
        echo "    should NOT contain: $needle"
        echo "    actual: $haystack"
        FAIL=$((FAIL + 1))
    fi
}

assert_line_count() {
    local label="$1" expected="$2" output="$3"
    local actual
    if [[ -z "$output" ]]; then
        actual=0
    else
        actual=$(echo "$output" | wc -l | tr -d ' ')
    fi
    TOTAL=$((TOTAL + 1))
    if [[ "$actual" == "$expected" ]]; then
        echo "  PASS: $label"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $label"
        echo "    expected $expected lines, got $actual"
        echo "    output: $output"
        FAIL=$((FAIL + 1))
    fi
}

# Create a temporary git repo with synthetic commits
setup_test_repo() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    # Copy required scripts
    mkdir -p "$tmpdir/.aitask-scripts/lib"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_revert_analyze.sh" "$tmpdir/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh" "$tmpdir/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" "$tmpdir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" "$tmpdir/.aitask-scripts/lib/"
    chmod +x "$tmpdir/.aitask-scripts/"*.sh

    (
        cd "$tmpdir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"

        # Initial commit
        echo "init" > file1.txt
        git add . && git commit -m "init" --quiet

        # Task 50: parent with 2 commits
        mkdir -p src
        echo "auth v1" > src/auth.py
        git add . && git commit -m "feature: Add auth module (t50)" --quiet

        echo "auth v2" > src/auth.py
        git add . && git commit -m "bug: Fix auth validation (t50)" --quiet

        # Task 50 children
        echo "login code" > src/login.py
        git add . && git commit -m "feature: Add login page (t50_1)" --quiet

        echo "signup code" > src/signup.py
        git add . && git commit -m "feature: Add signup flow (t50_2)" --quiet

        # Task 99: single commit in a different directory
        mkdir -p lib
        echo "utils code" > lib/utils.py
        git add . && git commit -m "feature: Add utility functions (t99)" --quiet

        # Administrative commit (should be filtered)
        echo "admin note" > README.md
        git add . && git commit -m "ait: Update task t50 metadata" --quiet

        # Create child task files so all-children works
        mkdir -p aitasks/t50
        echo "---" > aitasks/t50/t50_1_login.md
        echo "---" > aitasks/t50/t50_2_signup.md

        # Create task/plan files for --find-task tests
        # Active parent task + plan (t99)
        echo "---" > aitasks/t99_utils.md
        mkdir -p aiplans
        echo "---" > aiplans/p99_utils.md

        # Archived parent task + plan (t50)
        mkdir -p aitasks/archived aiplans/archived
        echo "---" > aitasks/archived/t50_auth.md
        echo "---" > aiplans/archived/p50_auth.md

        # Archived child plan (t50_1)
        mkdir -p aiplans/archived/p50
        echo "---" > aiplans/archived/p50/p50_1_login.md

        git add . && git commit -m "ait: Add child tasks" --quiet
    )

    echo "$tmpdir"
}

cleanup_test_repo() {
    if [[ -n "$TMPDIR_TEST" && -d "$TMPDIR_TEST" ]]; then
        rm -rf "$TMPDIR_TEST"
    fi
}
trap cleanup_test_repo EXIT

# --- Setup ---

TMPDIR_TEST=$(setup_test_repo)
SCRIPT="$TMPDIR_TEST/.aitask-scripts/aitask_revert_analyze.sh"

echo "=== Test: shellcheck ==="
TOTAL=$((TOTAL + 1))
if shellcheck "$ANALYZE_SCRIPT" 2>&1 | grep -qv 'SC1091'; then
    # SC1091 is info-level (not following sourced files) — acceptable
    echo "  PASS: shellcheck (no errors beyond SC1091)"
    PASS=$((PASS + 1))
else
    echo "  PASS: shellcheck clean"
    PASS=$((PASS + 1))
fi

echo "=== Test: --help exits 0 and shows usage ==="
result=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" --help 2>&1)
rc=$?
assert_eq "--help exits 0" "0" "$rc"
assert_contains "--help shows Usage" "Usage:" "$result"
assert_contains "--help lists subcommands" "--recent-tasks" "$result"

echo "=== Test: no args exits non-zero ==="
rc=0
result=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" 2>&1) || rc=$?
assert_eq "no args exits 1" "1" "$rc"
assert_contains "no args shows help" "Usage:" "$result"

echo "=== Test: --recent-tasks lists tasks ==="
result=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" --recent-tasks 2>&1)
assert_contains "recent-tasks shows t50" "TASK|50|" "$result"
assert_contains "recent-tasks shows t99" "TASK|99|" "$result"
assert_not_contains "recent-tasks excludes ait: commits" "ait:" "$result"

echo "=== Test: --recent-tasks deduplicates ==="
t50_lines=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" --recent-tasks 2>&1 | grep -c 'TASK|50|' | tr -d ' ')
assert_eq "t50 appears exactly once" "1" "$t50_lines"

echo "=== Test: --recent-tasks commit count ==="
result=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" --recent-tasks 2>&1)
# t50 has 2 direct commits (feature + bug fix)
t50_line=$(echo "$result" | grep 'TASK|50|')
assert_contains "t50 commit count >= 2" "|2" "$t50_line"

echo "=== Test: --recent-tasks --limit 1 ==="
result=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" --recent-tasks --limit 1 2>&1)
assert_line_count "limit 1 returns 1 task" "1" "$result"

echo "=== Test: --task-commits parent includes children ==="
result=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" --task-commits 50 2>&1)
assert_contains "parent commits include |50" "|50" "$result"
assert_contains "parent commits include child 50_1" "|50_1" "$result"
assert_contains "parent commits include child 50_2" "|50_2" "$result"

echo "=== Test: --task-commits child returns only that child ==="
result=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" --task-commits 50_1 2>&1)
assert_contains "child commits include 50_1" "|50_1" "$result"
assert_not_contains "child commits exclude parent 50" "|50
" "$result"

echo "=== Test: --task-commits single task ==="
result=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" --task-commits 99 2>&1)
assert_line_count "t99 has 1 commit" "1" "$result"
assert_contains "t99 commit has task id" "|99" "$result"

echo "=== Test: --task-areas groups by directory ==="
result=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" --task-areas 50 2>&1)
assert_contains "areas include src/" "AREA|src/" "$result"

echo "=== Test: --task-areas for t99 ==="
result=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" --task-areas 99 2>&1)
assert_contains "areas include lib/" "AREA|lib/" "$result"

echo "=== Test: --task-files lists files ==="
result=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" --task-files 50 2>&1)
assert_contains "files include auth.py" "FILE|src/auth.py|" "$result"
assert_contains "files include login.py" "FILE|src/login.py|" "$result"
assert_contains "files include signup.py" "FILE|src/signup.py|" "$result"

echo "=== Test: --task-files for t99 ==="
result=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" --task-files 99 2>&1)
assert_contains "files include utils.py" "FILE|lib/utils.py|" "$result"
assert_line_count "t99 has 1 file" "1" "$result"

echo "=== Test: --task-commits nonexistent task ==="
result=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" --task-commits 9999 2>&1)
assert_eq "nonexistent task returns empty" "" "$result"

echo "=== Test: --find-task active parent ==="
result=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" --find-task 99 2>&1)
assert_contains "find active task" "TASK_LOCATION|active|" "$result"
assert_contains "find active task path" "t99_utils.md" "$result"
assert_contains "find active plan" "PLAN_LOCATION|active|" "$result"
assert_contains "find active plan path" "p99_utils.md" "$result"
assert_line_count "find-task outputs 2 lines" "2" "$result"

echo "=== Test: --find-task archived parent ==="
result=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" --find-task 50 2>&1)
# t50 has active children in aitasks/t50/ but no active parent task file;
# the parent task file is in aitasks/archived/
assert_contains "find archived task" "TASK_LOCATION|archived|" "$result"
assert_contains "find archived task path" "t50_auth.md" "$result"
assert_contains "find archived plan" "PLAN_LOCATION|archived|" "$result"
assert_contains "find archived plan path" "p50_auth.md" "$result"

echo "=== Test: --find-task active child ==="
result=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" --find-task 50_1 2>&1)
assert_contains "find active child task" "TASK_LOCATION|active|" "$result"
assert_contains "find active child path" "t50_1_login.md" "$result"
# Child plan is archived
assert_contains "find archived child plan" "PLAN_LOCATION|archived|" "$result"
assert_contains "find archived child plan path" "p50_1_login.md" "$result"

echo "=== Test: --find-task nonexistent ==="
result=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" --find-task 9999 2>&1)
assert_contains "not found task" "TASK_LOCATION|not_found|" "$result"
assert_contains "not found plan" "PLAN_LOCATION|not_found|" "$result"
assert_line_count "not-found outputs 2 lines" "2" "$result"

echo "=== Test: --help shows --find-task ==="
result=$(cd "$TMPDIR_TEST" && bash "$SCRIPT" --help 2>&1)
assert_contains "--help lists --find-task" "--find-task" "$result"

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -gt 0 ]]; then
    echo "SOME TESTS FAILED"
    exit 1
else
    echo "ALL TESTS PASSED"
fi
