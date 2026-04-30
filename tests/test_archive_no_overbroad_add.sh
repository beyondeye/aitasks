#!/usr/bin/env bash
# test_archive_no_overbroad_add.sh - Regression test for t533
#
# Ensures aitask_archive.sh stages ONLY the files belonging to the archived task,
# and does not sweep in unrelated in-progress edits to sibling task/plan files.
# Covers:
#   - Parent archival (archive_parent)
#   - Child archival without parent auto-archival
#   - Child archival with parent auto-archival
#
# Run: bash tests/test_archive_no_overbroad_add.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/terminal_compat.sh
source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

# --- Test helpers ---

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF -- "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got: $actual)"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF -- "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output NOT containing '$unexpected', got: $actual)"
    else
        PASS=$((PASS + 1))
    fi
}

# --- Setup a test project with archive capabilities ---
setup_archive_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")

    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"

    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir" 2>/dev/null

    pushd "$local_dir" > /dev/null
    git config user.email "test@test.com"
    git config user.name "Test"

    mkdir -p aitasks/archived aitasks/metadata aiplans/archived .aitask-scripts/lib

    cp "$PROJECT_DIR/.aitask-scripts/aitask_archive.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/*.sh

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\n' > aitasks/metadata/task_types.txt

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true
}

teardown() {
    popd > /dev/null 2>&1 || true
}

# Helper: extract the COMMITTED hash from archive script output
extract_commit_hash() {
    local output="$1"
    echo "$output" | grep -oE '^COMMITTED:[a-f0-9]+' | head -1 | cut -d: -f2
}

# --- Case A: Parent archival does not sweep in unrelated modifications ---
test_parent_archive_no_sweep() {
    echo "=== Case A: Parent archival does not sweep in unrelated edits ==="
    setup_archive_project

    # Target task to archive
    cat > aitasks/t100_target.md << 'TASK'
---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: []
created_at: 2026-04-13 10:00
updated_at: 2026-04-13 10:00
---

Target task
TASK

    cat > aiplans/p100_target.md << 'PLAN'
---
Task: t100_target.md
---

Target plan
PLAN

    # Bystander task (unrelated, will be mid-edit when archival runs)
    cat > aitasks/t101_bystander.md << 'TASK'
---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: []
created_at: 2026-04-13 10:00
updated_at: 2026-04-13 10:00
---

Bystander task - should remain unstaged after archival
TASK

    cat > aiplans/p101_bystander.md << 'PLAN'
---
Task: t101_bystander.md
---

Bystander plan
PLAN

    git add -A
    git commit -m "Setup case A" --quiet

    # Modify the bystander task and plan (unstaged)
    sed_inplace 's/^status: Ready/status: Implementing/' aitasks/t101_bystander.md
    echo "Unstaged edit by sibling agent" >> aiplans/p101_bystander.md

    # Run archival
    local output
    output=$(bash .aitask-scripts/aitask_archive.sh 100 2>&1)

    local hash
    hash=$(extract_commit_hash "$output")
    if [[ -z "$hash" ]]; then
        FAIL=$((FAIL + 1))
        TOTAL=$((TOTAL + 1))
        echo "FAIL: Case A: no COMMITTED hash in output: $output"
        teardown
        return
    fi

    local commit_files
    commit_files=$(git show --name-status --pretty=format: -M0 "$hash")

    assert_contains "Case A: archived task staged" "aitasks/archived/t100_target.md" "$commit_files"
    assert_contains "Case A: archived plan staged" "aiplans/archived/p100_target.md" "$commit_files"
    assert_contains "Case A: original task deletion staged" "aitasks/t100_target.md" "$commit_files"
    assert_contains "Case A: original plan deletion staged" "aiplans/p100_target.md" "$commit_files"
    assert_not_contains "Case A: bystander task NOT in commit" "t101_bystander" "$commit_files"
    assert_not_contains "Case A: bystander plan NOT in commit" "p101_bystander" "$commit_files"

    # Verify bystander files remain modified-but-unstaged
    local status_line
    status_line=$(git status --porcelain aitasks/t101_bystander.md aiplans/p101_bystander.md)
    assert_contains "Case A: bystander task still unstaged" " M aitasks/t101_bystander.md" "$status_line"
    assert_contains "Case A: bystander plan still unstaged" " M aiplans/p101_bystander.md" "$status_line"

    teardown
}

# --- Case B: Child archival without parent auto-archival ---
test_child_archive_no_sweep() {
    echo ""
    echo "=== Case B: Child archival (non-terminal) does not sweep in unrelated edits ==="
    setup_archive_project

    cat > aitasks/t200_parent.md << 'TASK'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
children_to_implement: [t200_1, t200_2]
created_at: 2026-04-13 10:00
updated_at: 2026-04-13 10:00
---

Parent with two children
TASK

    mkdir -p aitasks/t200 aiplans/p200

    cat > aitasks/t200/t200_1_target.md << 'TASK'
---
priority: high
effort: low
depends: []
issue_type: feature
status: Implementing
labels: []
created_at: 2026-04-13 10:00
updated_at: 2026-04-13 10:00
---

Target child task
TASK

    cat > aiplans/p200/p200_1_target.md << 'PLAN'
---
Task: t200_1_target.md
---

Target child plan
PLAN

    cat > aitasks/t200/t200_2_bystander.md << 'TASK'
---
priority: medium
effort: low
depends: []
issue_type: feature
status: Ready
labels: []
created_at: 2026-04-13 10:00
updated_at: 2026-04-13 10:00
---

Bystander child task
TASK

    cat > aiplans/p200/p200_2_bystander.md << 'PLAN'
---
Task: t200_2_bystander.md
---

Bystander child plan
PLAN

    git add -A
    git commit -m "Setup case B" --quiet

    sed_inplace 's/^status: Ready/status: Implementing/' aitasks/t200/t200_2_bystander.md
    echo "Unstaged edit" >> aiplans/p200/p200_2_bystander.md

    local output
    output=$(bash .aitask-scripts/aitask_archive.sh 200_1 2>&1)

    local hash
    hash=$(extract_commit_hash "$output")
    if [[ -z "$hash" ]]; then
        FAIL=$((FAIL + 1))
        TOTAL=$((TOTAL + 1))
        echo "FAIL: Case B: no COMMITTED hash in output: $output"
        teardown
        return
    fi

    local commit_files
    commit_files=$(git show --name-status --pretty=format: -M0 "$hash")

    assert_contains "Case B: archived child staged" "aitasks/archived/t200/t200_1_target.md" "$commit_files"
    assert_contains "Case B: archived child plan staged" "aiplans/archived/p200/p200_1_target.md" "$commit_files"
    assert_contains "Case B: parent updated in commit" "aitasks/t200_parent.md" "$commit_files"
    assert_not_contains "Case B: bystander child NOT in commit" "t200_2_bystander" "$commit_files"
    assert_not_contains "Case B: bystander child plan NOT in commit" "p200_2_bystander" "$commit_files"

    local status_line
    status_line=$(git status --porcelain aitasks/t200/t200_2_bystander.md aiplans/p200/p200_2_bystander.md)
    assert_contains "Case B: bystander child still unstaged" " M aitasks/t200/t200_2_bystander.md" "$status_line"
    assert_contains "Case B: bystander child plan still unstaged" " M aiplans/p200/p200_2_bystander.md" "$status_line"

    teardown
}

# --- Case C: Child archival triggering parent auto-archival ---
test_child_archive_with_parent_no_sweep() {
    echo ""
    echo "=== Case C: Child archival with parent auto-archival does not sweep in unrelated edits ==="
    setup_archive_project

    cat > aitasks/t300_parent.md << 'TASK'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
children_to_implement: [t300_1]
created_at: 2026-04-13 10:00
updated_at: 2026-04-13 10:00
---

Parent with single remaining child
TASK

    cat > aiplans/p300_parent.md << 'PLAN'
---
Task: t300_parent.md
---

Parent plan
PLAN

    mkdir -p aitasks/t300

    cat > aitasks/t300/t300_1_last_child.md << 'TASK'
---
priority: high
effort: low
depends: []
issue_type: feature
status: Implementing
labels: []
created_at: 2026-04-13 10:00
updated_at: 2026-04-13 10:00
---

Last child task
TASK

    # Unrelated parent (bystander)
    cat > aitasks/t301_bystander.md << 'TASK'
---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: []
created_at: 2026-04-13 10:00
updated_at: 2026-04-13 10:00
---

Bystander parent task
TASK

    cat > aiplans/p301_bystander.md << 'PLAN'
---
Task: t301_bystander.md
---

Bystander parent plan
PLAN

    git add -A
    git commit -m "Setup case C" --quiet

    sed_inplace 's/^status: Ready/status: Implementing/' aitasks/t301_bystander.md
    echo "Unstaged edit" >> aiplans/p301_bystander.md

    local output
    output=$(bash .aitask-scripts/aitask_archive.sh 300_1 2>&1)

    local hash
    hash=$(extract_commit_hash "$output")
    if [[ -z "$hash" ]]; then
        FAIL=$((FAIL + 1))
        TOTAL=$((TOTAL + 1))
        echo "FAIL: Case C: no COMMITTED hash in output: $output"
        teardown
        return
    fi

    local commit_files
    commit_files=$(git show --name-status --pretty=format: -M0 "$hash")

    assert_contains "Case C: archived child staged" "aitasks/archived/t300/t300_1_last_child.md" "$commit_files"
    assert_contains "Case C: archived parent staged" "aitasks/archived/t300_parent.md" "$commit_files"
    assert_contains "Case C: archived parent plan staged" "aiplans/archived/p300_parent.md" "$commit_files"
    assert_not_contains "Case C: bystander task NOT in commit" "t301_bystander" "$commit_files"
    assert_not_contains "Case C: bystander plan NOT in commit" "p301_bystander" "$commit_files"

    local status_line
    status_line=$(git status --porcelain aitasks/t301_bystander.md aiplans/p301_bystander.md)
    assert_contains "Case C: bystander task still unstaged" " M aitasks/t301_bystander.md" "$status_line"
    assert_contains "Case C: bystander plan still unstaged" " M aiplans/p301_bystander.md" "$status_line"

    teardown
}

# --- Run all tests ---
test_parent_archive_no_sweep
test_child_archive_no_sweep
test_child_archive_with_parent_no_sweep

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
