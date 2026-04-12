#!/usr/bin/env bash
# test_fold_mark.sh - Tests for aitask_fold_mark.sh
#
# Covers:
#   - --commit-mode fresh: primary folded_tasks updated, folded tasks marked
#     Folded+folded_into, child folded task removed from parent
#     children_to_implement, commit created with expected subject
#   - --commit-mode none: no new commit created
#   - Transitive: folding A (which has folded_tasks: [X, Y]) updates X and Y's
#     folded_into to point at the primary
#
# Run: bash tests/test_fold_mark.sh

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
        echo "FAIL: $desc"
        echo "  expected: $expected"
        echo "  actual:   $actual"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (missing '$expected' in output)"
    fi
}

assert_file_exists() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (file '$path' does not exist)"
    fi
}

setup_project() {
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

    mkdir -p aitasks/metadata .aitask-scripts/lib
    cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/*.sh

    printf 'bug\nchore\ndocumentation\nfeature\nperformance\nrefactor\nstyle\ntest\n' > aitasks/metadata/task_types.txt
    : > aitasks/metadata/labels.txt

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    PROJECT_UNDER_TEST="$local_dir"
}

teardown() {
    popd > /dev/null 2>&1 || true
}

write_task() {
    local path="$1"
    shift
    mkdir -p "$(dirname "$path")"
    {
        printf '%s\n' "---"
        printf '%s\n' "priority: medium"
        printf '%s\n' "effort: low"
        printf '%s\n' "depends: []"
        printf '%s\n' "issue_type: chore"
        printf '%s\n' "status: Ready"
        printf '%s\n' "labels: []"
        for extra in "$@"; do
            printf '%s\n' "$extra"
        done
        printf '%s\n' "created_at: 2026-01-01 10:00"
        printf '%s\n' "updated_at: 2026-01-01 10:00"
        printf '%s\n' "---"
        printf '\nBody\n'
    } > "$path"
}

read_frontmatter_field() {
    local file="$1" field="$2"
    awk -v f="$field" '
        BEGIN { in_fm = 0 }
        $0 == "---" { in_fm = !in_fm; next }
        in_fm && $0 ~ "^" f ":" {
            sub("^" f ":[[:space:]]*", "")
            print
            exit
        }
    ' "$file"
}

test_fresh_mode_full_flow() {
    echo "=== Test: --commit-mode fresh, parent + child folded ==="
    setup_project

    # Primary task
    write_task aitasks/t10_primary.md

    # Two simple parent tasks to fold
    write_task aitasks/t20_a.md
    write_task aitasks/t21_b.md

    # Child task with its own parent (t30), to test child cleanup
    write_task aitasks/t30_orig_parent.md "children_to_implement: [t30_1]"
    write_task aitasks/t30/t30_1_child.md

    git add -A
    git commit -m "Setup test" --quiet

    local output
    output=$(bash .aitask-scripts/aitask_fold_mark.sh \
        --commit-mode fresh 10 20 21 30_1 2>&1)

    assert_contains "primary updated" "PRIMARY_UPDATED:10" "$output"
    assert_contains "t20 folded" "FOLDED:20" "$output"
    assert_contains "t21 folded" "FOLDED:21" "$output"
    assert_contains "t30_1 folded" "FOLDED:30_1" "$output"
    assert_contains "child removed from original parent" "CHILD_REMOVED:30:1" "$output"
    assert_contains "committed" "COMMITTED:" "$output"

    # Primary's folded_tasks contains all three new IDs
    local folded
    folded=$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)
    assert_contains "folded_tasks contains 20" "20" "$folded"
    assert_contains "folded_tasks contains 21" "21" "$folded"
    assert_contains "folded_tasks contains 30_1" "30_1" "$folded"

    # Each folded task has status Folded and folded_into=10
    assert_eq "t20 status=Folded" "Folded" "$(read_frontmatter_field aitasks/t20_a.md status)"
    assert_eq "t20 folded_into=10" "10" "$(read_frontmatter_field aitasks/t20_a.md folded_into)"
    assert_eq "t21 status=Folded" "Folded" "$(read_frontmatter_field aitasks/t21_b.md status)"
    assert_eq "t30_1 status=Folded" "Folded" "$(read_frontmatter_field aitasks/t30/t30_1_child.md status)"

    # t30's children_to_implement no longer references t30_1
    local t30_children
    t30_children=$(read_frontmatter_field aitasks/t30_orig_parent.md children_to_implement)
    if echo "$t30_children" | grep -qF "t30_1"; then
        TOTAL=$((TOTAL + 1))
        FAIL=$((FAIL + 1))
        echo "FAIL: t30_1 should have been removed from parent's children_to_implement (got: $t30_children)"
    else
        TOTAL=$((TOTAL + 1))
        PASS=$((PASS + 1))
    fi

    # A new commit was created with the expected subject
    local subject
    subject=$(git log -1 --pretty=%s)
    assert_contains "commit subject" "ait: Fold tasks into t10" "$subject"
    assert_contains "commit lists merged ids" "merge t20, t21, t30_1" "$subject"

    teardown
}

test_none_mode_no_commit() {
    echo "=== Test: --commit-mode none creates no commit ==="
    setup_project

    write_task aitasks/t10_primary.md
    write_task aitasks/t20_a.md

    git add -A
    git commit -m "Setup test none" --quiet

    local before_hash
    before_hash=$(git rev-parse HEAD)

    local output
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode none 10 20 2>&1)
    assert_contains "output says NO_COMMIT" "NO_COMMIT" "$output"

    local after_hash
    after_hash=$(git rev-parse HEAD)
    assert_eq "HEAD unchanged" "$before_hash" "$after_hash"

    teardown
}

test_transitive() {
    echo "=== Test: transitive folded tasks ==="
    setup_project

    write_task aitasks/t50_primary.md
    # Task A has folded_tasks: [X, Y]
    write_task aitasks/t60_a.md "folded_tasks: [70, 71]"
    # X and Y already folded into A
    write_task aitasks/t70_x.md "folded_into: 60" "status: Folded"
    write_task aitasks/t71_y.md "folded_into: 60" "status: Folded"

    # Note: write_task sets status: Ready first, then the extras append. The
    # duplicate "status: Folded" later in the file is harmless for YAML parsing
    # as long as the first-seen wins; but to be safe, rewrite X/Y status to
    # Folded directly:
    sed -i 's/^status: Ready$/status: Folded/' aitasks/t70_x.md aitasks/t71_y.md 2>/dev/null || \
        { sed -i.bak 's/^status: Ready$/status: Folded/' aitasks/t70_x.md aitasks/t71_y.md; rm -f aitasks/t70_x.md.bak aitasks/t71_y.md.bak; }

    git add -A
    git commit -m "Setup transitive" --quiet

    local output
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode none 50 60 2>&1)

    assert_contains "A folded into primary" "FOLDED:60" "$output"
    assert_contains "transitive 70" "TRANSITIVE:70" "$output"
    assert_contains "transitive 71" "TRANSITIVE:71" "$output"

    # X and Y now point at the new primary
    assert_eq "t70 folded_into=50" "50" "$(read_frontmatter_field aitasks/t70_x.md folded_into)"
    assert_eq "t71 folded_into=50" "50" "$(read_frontmatter_field aitasks/t71_y.md folded_into)"

    # Primary's folded_tasks contains 60, 70, 71
    local folded
    folded=$(read_frontmatter_field aitasks/t50_primary.md folded_tasks)
    assert_contains "primary folded_tasks contains 60" "60" "$folded"
    assert_contains "primary folded_tasks contains 70" "70" "$folded"
    assert_contains "primary folded_tasks contains 71" "71" "$folded"

    teardown
}

teardown_all() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -d "$d" ]] && rm -rf "$d"
    done
}
trap teardown_all EXIT

test_fresh_mode_full_flow
test_none_mode_no_commit
test_transitive

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
