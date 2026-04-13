#!/usr/bin/env bash
# test_plan_externalize.sh - Tests for aitask_plan_externalize.sh
# Run: bash tests/test_plan_externalize.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
EXTERNALIZE="$PROJECT_DIR/.aitask-scripts/aitask_plan_externalize.sh"

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

assert_file_exists() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (missing: $path)"
    fi
}

# --- Setup helpers ---

new_sandbox() {
    local tmpdir
    tmpdir=$(mktemp -d)
    mkdir -p "$tmpdir/aitasks"
    mkdir -p "$tmpdir/aiplans"
    mkdir -p "$tmpdir/fakehome/.claude/plans"
    cat > "$tmpdir/aitasks/t999_sandbox_task.md" <<'EOF'
---
priority: medium
effort: medium
status: Ready
---

Sandbox task body.
EOF
    echo "$tmpdir"
}

make_fresh_internal() {
    local path="$1"
    cat > "$path" <<'EOF'
# Sandbox plan

- Step 1
- Step 2
EOF
}

# Portable "set file mtime to N hours ago". Uses touch -t YYYYMMDDhhmm.
make_old() {
    local path="$1" hours_ago="$2"
    local stamp
    if stamp=$(date -d "${hours_ago} hours ago" +%Y%m%d%H%M 2>/dev/null); then
        :
    else
        stamp=$(date -v-"${hours_ago}"H +%Y%m%d%H%M)
    fi
    touch -t "$stamp" "$path"
}

run_externalize() {
    local sandbox="$1"; shift
    local plans_dir="$1"; shift
    ( cd "$sandbox" && \
      AIT_PLAN_EXTERNALIZE_INTERNAL_DIR="$plans_dir" \
      "$EXTERNALIZE" "$@" )
}

echo "=== test_plan_externalize.sh ==="
echo ""

# --- Test 1: Fresh internal plan → EXTERNALIZED ---
echo "--- Test 1: fresh internal plan ---"
TMPDIR1=$(new_sandbox)
make_fresh_internal "$TMPDIR1/fakehome/.claude/plans/one-recent.md"
result=$(run_externalize "$TMPDIR1" "$TMPDIR1/fakehome/.claude/plans" 999)
assert_contains "fresh: EXTERNALIZED prefix" "EXTERNALIZED:aiplans/p999_sandbox_task.md:" "$result"
assert_file_exists "fresh: external plan created" "$TMPDIR1/aiplans/p999_sandbox_task.md"
first_line=$(head -n 1 "$TMPDIR1/aiplans/p999_sandbox_task.md")
assert_eq "fresh: frontmatter opener prepended" "---" "$first_line"
task_field=$(grep '^Task:' "$TMPDIR1/aiplans/p999_sandbox_task.md" || true)
assert_contains "fresh: Task field present" "t999_sandbox_task.md" "$task_field"
base_field=$(grep '^Base branch:' "$TMPDIR1/aiplans/p999_sandbox_task.md" || true)
assert_contains "fresh: Base branch field present" "main" "$base_field"
rm -rf "$TMPDIR1"

# --- Test 2: Second invocation → PLAN_EXISTS ---
echo "--- Test 2: idempotent no-op ---"
TMPDIR2=$(new_sandbox)
make_fresh_internal "$TMPDIR2/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR2" "$TMPDIR2/fakehome/.claude/plans" 999 >/dev/null
result=$(run_externalize "$TMPDIR2" "$TMPDIR2/fakehome/.claude/plans" 999)
assert_contains "no-op: PLAN_EXISTS" "PLAN_EXISTS:aiplans/p999_sandbox_task.md" "$result"
rm -rf "$TMPDIR2"

# --- Test 3: Only stale files → NOT_FOUND:no_internal_files ---
echo "--- Test 3: stale file ignored ---"
TMPDIR3=$(new_sandbox)
make_fresh_internal "$TMPDIR3/fakehome/.claude/plans/stale-old.md"
make_old "$TMPDIR3/fakehome/.claude/plans/stale-old.md" 2
result=$(run_externalize "$TMPDIR3" "$TMPDIR3/fakehome/.claude/plans" 999)
assert_contains "stale: NOT_FOUND:no_internal_files" "NOT_FOUND:no_internal_files" "$result"
rm -rf "$TMPDIR3"

# --- Test 4: Multiple fresh files → MULTIPLE_CANDIDATES ---
echo "--- Test 4: multiple candidates ---"
TMPDIR4=$(new_sandbox)
make_fresh_internal "$TMPDIR4/fakehome/.claude/plans/first.md"
make_fresh_internal "$TMPDIR4/fakehome/.claude/plans/second.md"
result=$(run_externalize "$TMPDIR4" "$TMPDIR4/fakehome/.claude/plans" 999)
assert_contains "multiple: MULTIPLE_CANDIDATES prefix" "MULTIPLE_CANDIDATES:" "$result"
assert_contains "multiple: first.md listed" "first.md" "$result"
assert_contains "multiple: second.md listed" "second.md" "$result"
rm -rf "$TMPDIR4"

# --- Test 5a: --internal explicit path → EXTERNALIZED ---
echo "--- Test 5a: --internal path ---"
TMPDIR5=$(new_sandbox)
explicit_path="$TMPDIR5/fakehome/.claude/plans/fresh.md"
make_fresh_internal "$explicit_path"
result=$(run_externalize "$TMPDIR5" "$TMPDIR5/fakehome/.claude/plans" 999 --internal "$explicit_path")
assert_contains "--internal ok: EXTERNALIZED" "EXTERNALIZED:aiplans/p999_sandbox_task.md:" "$result"
rm -rf "$TMPDIR5"

# --- Test 5b: --internal with nonexistent path → NOT_FOUND:source_not_file ---
echo "--- Test 5b: --internal nonexistent ---"
TMPDIR5b=$(new_sandbox)
result=$(run_externalize "$TMPDIR5b" "$TMPDIR5b/fakehome/.claude/plans" 999 --internal /nonexistent/plan.md)
assert_contains "--internal nonexistent: NOT_FOUND:source_not_file" "NOT_FOUND:source_not_file" "$result"
rm -rf "$TMPDIR5b"

# --- Test 6: Child task form → aiplans/p<parent>/p<parent>_<child>_*.md ---
echo "--- Test 6: child task ---"
TMPDIR6=$(new_sandbox)
mkdir -p "$TMPDIR6/aitasks/t999"
cat > "$TMPDIR6/aitasks/t999/t999_2_sub.md" <<'EOF'
---
priority: medium
status: Ready
---

Child task body.
EOF
make_fresh_internal "$TMPDIR6/fakehome/.claude/plans/child.md"
result=$(run_externalize "$TMPDIR6" "$TMPDIR6/fakehome/.claude/plans" 999_2)
assert_contains "child: EXTERNALIZED path" "EXTERNALIZED:aiplans/p999/p999_2_sub.md:" "$result"
assert_file_exists "child: external plan created in subdir" "$TMPDIR6/aiplans/p999/p999_2_sub.md"
parent_field=$(grep '^Parent Task:' "$TMPDIR6/aiplans/p999/p999_2_sub.md" || true)
assert_contains "child: Parent Task field present" "t999_sandbox_task.md" "$parent_field"
rm -rf "$TMPDIR6"

# --- Test 7: Internal plan already has frontmatter → no duplicate header ---
echo "--- Test 7: existing frontmatter not duplicated ---"
TMPDIR7=$(new_sandbox)
cat > "$TMPDIR7/fakehome/.claude/plans/with_front.md" <<'EOF'
---
Task: t999_sandbox_task.md
---

# Already has frontmatter
EOF
result=$(run_externalize "$TMPDIR7" "$TMPDIR7/fakehome/.claude/plans" 999)
assert_contains "existing front: EXTERNALIZED" "EXTERNALIZED:" "$result"
count=$(grep -c '^---$' "$TMPDIR7/aiplans/p999_sandbox_task.md" || true)
assert_eq "existing front: frontmatter not duplicated (--- count == 2)" "2" "$count"
rm -rf "$TMPDIR7"

# --- Test 8: AIT_PLAN_EXTERNALIZE_MAX_AGE_SECS widens window ---
echo "--- Test 8: age-window env var ---"
TMPDIR8=$(new_sandbox)
make_fresh_internal "$TMPDIR8/fakehome/.claude/plans/twohours.md"
make_old "$TMPDIR8/fakehome/.claude/plans/twohours.md" 2
result=$(
    cd "$TMPDIR8" && \
    AIT_PLAN_EXTERNALIZE_INTERNAL_DIR="$TMPDIR8/fakehome/.claude/plans" \
    AIT_PLAN_EXTERNALIZE_MAX_AGE_SECS=14400 \
    "$EXTERNALIZE" 999
)
assert_contains "widened window: EXTERNALIZED (includes 2h-old file)" "EXTERNALIZED:" "$result"
rm -rf "$TMPDIR8"

# --- Test 9: Unknown task id → NOT_FOUND:no_task_file ---
echo "--- Test 9: unknown task id ---"
TMPDIR9=$(new_sandbox)
make_fresh_internal "$TMPDIR9/fakehome/.claude/plans/whatever.md"
result=$(run_externalize "$TMPDIR9" "$TMPDIR9/fakehome/.claude/plans" 12345)
assert_contains "unknown task: NOT_FOUND:no_task_file" "NOT_FOUND:no_task_file" "$result"
rm -rf "$TMPDIR9"

# --- Results ---

echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
