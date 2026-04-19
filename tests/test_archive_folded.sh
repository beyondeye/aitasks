#!/usr/bin/env bash
# test_archive_folded.sh - Tests for folded task handling during archival
# Covers:
#   - Child archival with folded_tasks (Issue 1)
#   - Parent auto-archival with folded_tasks (Issue 2)
#   - handle_folded_tasks() with child task ID format (Issue 5)
#
# Run: bash tests/test_archive_folded.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

# --- Test helpers ---

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    expected="$(echo "$expected" | xargs)"
    actual="$(echo "$actual" | xargs)"
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

assert_file_exists() {
    local desc="$1" filepath="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$filepath" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (file '$filepath' does not exist)"
    fi
}

assert_file_not_exists() {
    local desc="$1" filepath="$2"
    TOTAL=$((TOTAL + 1))
    if [[ ! -f "$filepath" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (file '$filepath' should not exist)"
    fi
}

# --- Setup a test project with archive capabilities ---
# Returns the project dir via PROJECT_UNDER_TEST variable
setup_archive_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")

    # Create bare "remote" repo
    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"

    # Create local working repo
    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir" 2>/dev/null

    pushd "$local_dir" > /dev/null
    git config user.email "test@test.com"
    git config user.name "Test"

    # Create project structure
    mkdir -p aitasks/archived aitasks/metadata aiplans/archived .aitask-scripts/lib

    # Copy scripts needed by archive
    cp "$PROJECT_DIR/.aitask-scripts/aitask_archive.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/*.sh

    # Create task types file
    printf 'bug\nchore\ndocumentation\nfeature\nperformance\nrefactor\nstyle\ntest\n' > aitasks/metadata/task_types.txt

    # Initial commit
    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    PROJECT_UNDER_TEST="$local_dir"
}

teardown() {
    popd > /dev/null 2>&1 || true
}

# --- Test A: Child archival deletes child's folded tasks ---
test_child_archive_with_folded_tasks() {
    echo "=== Test A: Child archival deletes child's folded tasks ==="
    setup_archive_project

    # Create parent task with children
    cat > aitasks/t10_parent_task.md << 'TASK'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
children_to_implement: [t10_1]
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Parent task
TASK

    # Create child task with folded_tasks
    mkdir -p aitasks/t10
    cat > aitasks/t10/t10_1_child_task.md << 'TASK'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
folded_tasks: [50]
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Child task with folded task
TASK

    # Create the folded task (should be deleted when child is archived)
    cat > aitasks/t50_folded_task.md << 'TASK'
---
priority: medium
effort: low
depends: []
issue_type: feature
status: Folded
labels: []
folded_into: 10_1
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

This task was folded into t10_1
TASK

    # Create folded task's plan (should also be deleted)
    cat > aiplans/p50_folded_task.md << 'TASK'
---
Task: t50_folded_task.md
---

Plan for folded task
TASK

    git add -A
    git commit -m "Setup test A" --quiet

    # Run archive for child task 10_1
    local output
    output=$(bash .aitask-scripts/aitask_archive.sh 10_1 2>&1)

    # Verify folded task was deleted
    assert_contains "Archive output contains FOLDED_DELETED" "FOLDED_DELETED:50" "$output"
    assert_file_not_exists "Folded task file should be deleted" "aitasks/t50_folded_task.md"
    assert_contains "Archive output shows child archived" "ARCHIVED_TASK:" "$output"

    teardown
}

# --- Test B: Parent auto-archival (from last child) deletes parent's folded tasks ---
test_parent_auto_archive_with_folded_tasks() {
    echo ""
    echo "=== Test B: Parent auto-archival deletes parent's folded tasks ==="
    setup_archive_project

    # Create parent task with folded_tasks and one remaining child
    cat > aitasks/t20_parent_with_folds.md << 'TASK'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
children_to_implement: [t20_1]
folded_tasks: [60]
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Parent task with folded tasks
TASK

    # Create the last remaining child task
    mkdir -p aitasks/t20
    cat > aitasks/t20/t20_1_last_child.md << 'TASK'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Last child task
TASK

    # Create the parent's folded task (should be deleted when parent is auto-archived)
    cat > aitasks/t60_parent_folded.md << 'TASK'
---
priority: medium
effort: low
depends: []
issue_type: feature
status: Folded
labels: []
folded_into: 20
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

This task was folded into t20
TASK

    git add -A
    git commit -m "Setup test B" --quiet

    # Archive the last child -> should trigger parent auto-archival
    local output
    output=$(bash .aitask-scripts/aitask_archive.sh 20_1 2>&1)

    # Verify parent was auto-archived
    assert_contains "Parent was auto-archived" "PARENT_ARCHIVED:" "$output"
    # Verify parent's folded task was deleted
    assert_contains "Parent's folded task deleted" "FOLDED_DELETED:60" "$output"
    assert_file_not_exists "Parent's folded task file should be deleted" "aitasks/t60_parent_folded.md"

    teardown
}

# --- Test C: handle_folded_tasks with child task ID format ---
test_folded_child_task_id_resolution() {
    echo ""
    echo "=== Test C: handle_folded_tasks with child task ID format ==="
    setup_archive_project

    # Create a parent task that has a child task ID in its folded_tasks
    cat > aitasks/t30_task_with_child_fold.md << 'TASK'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
folded_tasks: [40_2]
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Task with a folded child task reference
TASK

    # Create the child task that was folded (in its parent's directory)
    mkdir -p aitasks/t40
    cat > aitasks/t40/t40_2_folded_child.md << 'TASK'
---
priority: medium
effort: low
depends: []
issue_type: feature
status: Folded
labels: []
folded_into: 30
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

This child task was folded into t30
TASK

    # Create its plan in child plan dir
    mkdir -p aiplans/p40
    cat > aiplans/p40/p40_2_folded_child.md << 'TASK'
---
Task: t40_2_folded_child.md
---

Plan for folded child task
TASK

    git add -A
    git commit -m "Setup test C" --quiet

    # Archive parent task t30
    local output
    output=$(bash .aitask-scripts/aitask_archive.sh 30 2>&1)

    # Verify the folded child task was found and deleted
    assert_contains "Folded child task deleted" "FOLDED_DELETED:40_2" "$output"
    assert_file_not_exists "Folded child task file should be deleted" "aitasks/t40/t40_2_folded_child.md"

    teardown
}

# --- Run all tests ---
test_child_archive_with_folded_tasks
test_parent_auto_archive_with_folded_tasks
test_folded_child_task_id_resolution

# Cleanup
for dir in "${CLEANUP_DIRS[@]}"; do
    rm -rf "$dir"
done

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
if [[ "$FAIL" -gt 0 ]]; then
    exit 1
else
    echo "All tests PASSED"
fi
