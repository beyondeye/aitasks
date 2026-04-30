#!/usr/bin/env bash
# test_archive_related_issues.sh - Tests for related_issues handling during archival
# Covers:
#   - extract_related_issues() unit tests (multiple URLs, single, empty, missing)
#   - Parent archival emits RELATED_ISSUE: lines
#   - Child archival emits RELATED_ISSUE: lines
#   - Parent auto-archival emits PARENT_RELATED_ISSUE: lines
#   - Folded task emits FOLDED_RELATED_ISSUE: lines
#
# Run: bash tests/test_archive_related_issues.sh

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

assert_not_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -q "$expected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output NOT containing '$expected')"
    else
        PASS=$((PASS + 1))
    fi
}

# --- Setup a test project with archive capabilities ---
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
    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\n' > aitasks/metadata/task_types.txt

    # Initial commit
    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    PROJECT_UNDER_TEST="$local_dir"
}

teardown() {
    popd > /dev/null 2>&1 || true
}

# --- Test A: extract_related_issues unit tests ---
test_extract_related_issues_unit() {
    echo "=== Test A: extract_related_issues() unit tests ==="

    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")

    # Source task_utils.sh (set SCRIPT_DIR so it finds terminal_compat.sh)
    SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
    source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"

    # A1: Multiple URLs
    cat > "$tmpdir/multi.md" << 'TASK'
---
priority: high
issue_type: feature
status: Ready
related_issues: ["https://github.com/o/r/issues/1", "https://github.com/o/r/issues/2"]
---

Task with multiple related issues
TASK

    local output
    output=$(extract_related_issues "$tmpdir/multi.md")
    local count
    count=$(echo "$output" | grep -c "https://" || true)
    assert_eq "Multiple URLs: count" "2" "$count"
    assert_contains "Multiple URLs: first URL" "https://github.com/o/r/issues/1" "$output"
    assert_contains "Multiple URLs: second URL" "https://github.com/o/r/issues/2" "$output"

    # A2: Single URL
    cat > "$tmpdir/single.md" << 'TASK'
---
priority: high
issue_type: feature
status: Ready
related_issues: ["https://github.com/o/r/issues/5"]
---

Task with single related issue
TASK

    output=$(extract_related_issues "$tmpdir/single.md")
    count=$(echo "$output" | grep -c "https://" || true)
    assert_eq "Single URL: count" "1" "$count"
    assert_contains "Single URL: URL present" "https://github.com/o/r/issues/5" "$output"

    # A3: Empty array
    cat > "$tmpdir/empty.md" << 'TASK'
---
priority: high
issue_type: feature
status: Ready
related_issues: []
---

Task with empty related issues
TASK

    output=$(extract_related_issues "$tmpdir/empty.md")
    assert_eq "Empty array: no output" "" "$output"

    # A4: Missing field
    cat > "$tmpdir/missing.md" << 'TASK'
---
priority: high
issue_type: feature
status: Ready
---

Task without related_issues field
TASK

    output=$(extract_related_issues "$tmpdir/missing.md")
    assert_eq "Missing field: no output" "" "$output"
}

# --- Test B: Parent archival emits RELATED_ISSUE: lines ---
test_parent_archive_related_issues() {
    echo ""
    echo "=== Test B: Parent archival emits RELATED_ISSUE: lines ==="
    setup_archive_project

    # Create parent task with issue and related_issues
    cat > aitasks/t100_merged_task.md << 'TASK'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
issue: https://github.com/o/r/issues/10
related_issues: ["https://github.com/o/r/issues/11", "https://github.com/o/r/issues/12"]
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Parent task with merged issues
TASK

    git add -A
    git commit -m "Setup test B" --quiet

    local output
    output=$(bash .aitask-scripts/aitask_archive.sh 100 2>&1)

    assert_contains "Primary ISSUE emitted" "ISSUE:100:https://github.com/o/r/issues/10" "$output"
    assert_contains "Related issue 11 emitted" "RELATED_ISSUE:100:https://github.com/o/r/issues/11" "$output"
    assert_contains "Related issue 12 emitted" "RELATED_ISSUE:100:https://github.com/o/r/issues/12" "$output"

    teardown
}

# --- Test C: Child archival emits RELATED_ISSUE: lines ---
test_child_archive_related_issues() {
    echo ""
    echo "=== Test C: Child archival emits RELATED_ISSUE: lines ==="
    setup_archive_project

    # Create parent task
    cat > aitasks/t200_parent.md << 'TASK'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
children_to_implement: [t200_1]
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Parent task
TASK

    # Create child task with related_issues
    mkdir -p aitasks/t200
    cat > aitasks/t200/t200_1_child_with_related.md << 'TASK'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
issue: https://github.com/o/r/issues/20
related_issues: ["https://github.com/o/r/issues/21"]
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Child task with related issues
TASK

    git add -A
    git commit -m "Setup test C" --quiet

    local output
    output=$(bash .aitask-scripts/aitask_archive.sh 200_1 2>&1)

    assert_contains "Child primary ISSUE emitted" "ISSUE:200_1:https://github.com/o/r/issues/20" "$output"
    assert_contains "Child related issue emitted" "RELATED_ISSUE:200_1:https://github.com/o/r/issues/21" "$output"

    teardown
}

# --- Test D: Parent auto-archival emits PARENT_RELATED_ISSUE: lines ---
test_parent_auto_archive_related_issues() {
    echo ""
    echo "=== Test D: Parent auto-archival emits PARENT_RELATED_ISSUE: lines ==="
    setup_archive_project

    # Create parent task with related_issues and one remaining child
    cat > aitasks/t300_parent_with_related.md << 'TASK'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
children_to_implement: [t300_1]
issue: https://github.com/o/r/issues/30
related_issues: ["https://github.com/o/r/issues/31", "https://github.com/o/r/issues/32"]
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Parent task with related issues
TASK

    # Create the last remaining child task
    mkdir -p aitasks/t300
    cat > aitasks/t300/t300_1_last_child.md << 'TASK'
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

    git add -A
    git commit -m "Setup test D" --quiet

    # Archive the last child -> triggers parent auto-archival
    local output
    output=$(bash .aitask-scripts/aitask_archive.sh 300_1 2>&1)

    assert_contains "Parent auto-archived" "PARENT_ARCHIVED:" "$output"
    assert_contains "Parent primary issue emitted" "PARENT_ISSUE:300:https://github.com/o/r/issues/30" "$output"
    assert_contains "Parent related issue 31 emitted" "PARENT_RELATED_ISSUE:300:https://github.com/o/r/issues/31" "$output"
    assert_contains "Parent related issue 32 emitted" "PARENT_RELATED_ISSUE:300:https://github.com/o/r/issues/32" "$output"

    teardown
}

# --- Test E: Folded task emits FOLDED_RELATED_ISSUE: lines ---
test_folded_task_related_issues() {
    echo ""
    echo "=== Test E: Folded task emits FOLDED_RELATED_ISSUE: lines ==="
    setup_archive_project

    # Create main task with folded_tasks
    cat > aitasks/t400_main_task.md << 'TASK'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
folded_tasks: [450]
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Main task with folded task
TASK

    # Create the folded task with related_issues
    cat > aitasks/t450_folded_with_related.md << 'TASK'
---
priority: medium
effort: low
depends: []
issue_type: feature
status: Folded
labels: []
folded_into: 400
issue: https://github.com/o/r/issues/45
related_issues: ["https://github.com/o/r/issues/46"]
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Folded task with related issues
TASK

    git add -A
    git commit -m "Setup test E" --quiet

    local output
    output=$(bash .aitask-scripts/aitask_archive.sh 400 2>&1)

    assert_contains "Folded primary issue emitted" "FOLDED_ISSUE:450:https://github.com/o/r/issues/45" "$output"
    assert_contains "Folded related issue emitted" "FOLDED_RELATED_ISSUE:450:https://github.com/o/r/issues/46" "$output"

    teardown
}

# --- Run all tests ---
test_extract_related_issues_unit
test_parent_archive_related_issues
test_child_archive_related_issues
test_parent_auto_archive_related_issues
test_folded_task_related_issues

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
