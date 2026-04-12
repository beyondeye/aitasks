#!/usr/bin/env bash
# test_fold_validate.sh - Tests for aitask_fold_validate.sh
#
# Covers:
#   - Valid parent → VALID:<id>:<path>
#   - Valid child → VALID:<parent>_<child>:<path>
#   - Missing → INVALID:<id>:not_found
#   - Wrong status → INVALID:<id>:status_<status>
#   - Parent with pending children → INVALID:<id>:has_children
#   - --exclude-self → INVALID:<id>:is_self
#   - Batch of 4 IDs → 4 lines in request order
#
# Run: bash tests/test_fold_validate.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

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
    if echo "$actual" | grep -qF "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected' in output: $actual)"
    fi
}

setup_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")

    pushd "$tmpdir" > /dev/null

    mkdir -p aitasks/metadata .aitask-scripts/lib
    cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_validate.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/*.sh

    PROJECT_UNDER_TEST="$tmpdir"
}

teardown() {
    popd > /dev/null 2>&1 || true
}

write_task() {
    local path="$1"
    local status="$2"
    mkdir -p "$(dirname "$path")"
    cat > "$path" << EOF
---
priority: medium
effort: low
depends: []
issue_type: chore
status: ${status}
labels: []
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Body
EOF
}

test_valid_parent() {
    echo "=== Test: valid parent ==="
    setup_project
    write_task aitasks/t10_valid_task.md Ready

    local output
    output=$(bash .aitask-scripts/aitask_fold_validate.sh 10)
    assert_eq "valid parent emits VALID line" "VALID:10:aitasks/t10_valid_task.md" "$output"

    teardown
}

test_valid_child() {
    echo "=== Test: valid child ==="
    setup_project
    write_task aitasks/t20/t20_2_child.md Ready

    local output
    output=$(bash .aitask-scripts/aitask_fold_validate.sh 20_2)
    assert_eq "valid child emits VALID line" "VALID:20_2:aitasks/t20/t20_2_child.md" "$output"

    teardown
}

test_missing() {
    echo "=== Test: not found ==="
    setup_project

    local output
    output=$(bash .aitask-scripts/aitask_fold_validate.sh 99)
    assert_eq "missing task emits INVALID:not_found" "INVALID:99:not_found" "$output"

    teardown
}

test_wrong_status() {
    echo "=== Test: wrong status ==="
    setup_project
    write_task aitasks/t30_impl_task.md Implementing

    local output
    output=$(bash .aitask-scripts/aitask_fold_validate.sh 30)
    assert_eq "Implementing status emits INVALID:status_Implementing" \
        "INVALID:30:status_Implementing" "$output"

    teardown
}

test_parent_with_children() {
    echo "=== Test: parent with pending children ==="
    setup_project
    write_task aitasks/t40_parent.md Ready
    write_task aitasks/t40/t40_1_child.md Ready

    local output
    output=$(bash .aitask-scripts/aitask_fold_validate.sh 40)
    assert_eq "parent with children emits INVALID:has_children" \
        "INVALID:40:has_children" "$output"

    teardown
}

test_exclude_self() {
    echo "=== Test: --exclude-self ==="
    setup_project
    write_task aitasks/t50_self.md Ready

    local output
    output=$(bash .aitask-scripts/aitask_fold_validate.sh --exclude-self 50 50)
    assert_eq "--exclude-self marks id as is_self" "INVALID:50:is_self" "$output"

    teardown
}

test_batch_order() {
    echo "=== Test: batch of 4 IDs preserves order ==="
    setup_project
    write_task aitasks/t60_a.md Ready
    write_task aitasks/t61_b.md Implementing
    write_task aitasks/t62/t62_1_c.md Ready
    # 63 is missing

    local output
    output=$(bash .aitask-scripts/aitask_fold_validate.sh 60 61 62_1 63)
    local expected="VALID:60:aitasks/t60_a.md
INVALID:61:status_Implementing
VALID:62_1:aitasks/t62/t62_1_c.md
INVALID:63:not_found"
    assert_eq "batch order preserved, 4 lines" "$expected" "$output"

    teardown
}

teardown_all() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -d "$d" ]] && rm -rf "$d"
    done
}
trap teardown_all EXIT

test_valid_parent
test_valid_child
test_missing
test_wrong_status
test_parent_with_children
test_exclude_self
test_batch_order

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
