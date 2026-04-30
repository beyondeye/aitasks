#!/usr/bin/env bash
# test_verifies_field.sh - Tests for the `verifies:` frontmatter field (t583_2)
#
# Covers the 3-layer propagation mandated by CLAUDE.md "Adding a New Frontmatter Field":
#   1. aitask_create.sh batch flag --verifies emits the field conditionally
#   2. aitask_update.sh --verifies / --add-verifies / --remove-verifies
#   3. aitask_fold_mark.sh unions verifies across primary + folded tasks
#
# The board widget (aitask_board.py VerifiesField) is covered by manual verification.
#
# Run: bash tests/test_verifies_field.sh

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
        echo "  actual: $actual"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (found unexpected '$unexpected' in output)"
        echo "  actual: $actual"
    else
        PASS=$((PASS + 1))
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
    cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/*.sh

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\n' > aitasks/metadata/task_types.txt
    : > aitasks/metadata/labels.txt

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true
}

teardown() {
    popd > /dev/null 2>&1 || true
}

# write_task PATH [extra_frontmatter_line ...]
# Writes a task file with a minimal Ready frontmatter. Extras insert inside the
# frontmatter before created_at/updated_at.
write_task() {
    local path="$1"
    shift
    mkdir -p "$(dirname "$path")"
    {
        printf '%s\n' "---"
        printf '%s\n' "priority: medium"
        printf '%s\n' "effort: low"
        printf '%s\n' "depends: []"
        printf '%s\n' "issue_type: feature"
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

read_verifies() {
    grep '^verifies:' "$1" 2>/dev/null | head -1 | sed 's/^verifies:[[:space:]]*//'
}

test_create_with_verifies() {
    echo "=== Test: create --verifies emits field ==="
    setup_project

    bash .aitask-scripts/aitask_create.sh --batch --type feature \
        --name smoke_a --verifies "10,11" --desc "x" > /dev/null 2>&1

    local draft_file
    draft_file=$(ls aitasks/new/draft_*_smoke_a.md 2>/dev/null | head -1)
    assert_contains "draft file created" "smoke_a.md" "$draft_file"

    local line
    line=$(read_verifies "$draft_file")
    assert_eq "verifies line matches" "[10, 11]" "$line"

    teardown
}

test_create_without_verifies_omits_field() {
    echo "=== Test: create without --verifies omits field ==="
    setup_project

    bash .aitask-scripts/aitask_create.sh --batch --type feature \
        --name smoke_b --desc "y" > /dev/null 2>&1

    local draft_file
    draft_file=$(ls aitasks/new/draft_*_smoke_b.md 2>/dev/null | head -1)

    local content
    content=$(cat "$draft_file")
    assert_not_contains "no verifies line in output" "verifies:" "$content"

    teardown
}

test_update_set_verifies() {
    echo "=== Test: update --verifies replaces list ==="
    setup_project

    write_task aitasks/t99_t.md "verifies: [10, 11]"
    git add -A && git commit -m "seed" --quiet

    bash .aitask-scripts/aitask_update.sh --batch 99 --verifies "20,21" --silent > /dev/null 2>&1
    local line
    line=$(read_verifies aitasks/t99_t.md)
    assert_eq "set replaces" "[20, 21]" "$line"

    teardown
}

test_update_add_verifies() {
    echo "=== Test: update --add-verifies appends and dedupes ==="
    setup_project

    write_task aitasks/t99_t.md "verifies: [10, 11]"
    git add -A && git commit -m "seed" --quiet

    bash .aitask-scripts/aitask_update.sh --batch 99 --add-verifies 12 --silent > /dev/null 2>&1
    local line
    line=$(read_verifies aitasks/t99_t.md)
    assert_eq "add appends" "[10, 11, 12]" "$line"

    # Adding an existing id should not duplicate
    bash .aitask-scripts/aitask_update.sh --batch 99 --add-verifies 11 --silent > /dev/null 2>&1
    line=$(read_verifies aitasks/t99_t.md)
    assert_eq "add-existing is dedup-noop" "[10, 11, 12]" "$line"

    teardown
}

test_update_remove_verifies() {
    echo "=== Test: update --remove-verifies drops entry ==="
    setup_project

    write_task aitasks/t99_t.md "verifies: [10, 11, 12]"
    git add -A && git commit -m "seed" --quiet

    bash .aitask-scripts/aitask_update.sh --batch 99 --remove-verifies 10 --silent > /dev/null 2>&1
    local line
    line=$(read_verifies aitasks/t99_t.md)
    assert_eq "remove drops" "[11, 12]" "$line"

    teardown
}

test_update_add_and_remove_combined() {
    echo "=== Test: combined --add-verifies + --remove-verifies in one call ==="
    setup_project

    write_task aitasks/t99_t.md "verifies: [10, 11, 12]"
    git add -A && git commit -m "seed" --quiet

    bash .aitask-scripts/aitask_update.sh --batch 99 \
        --add-verifies 30 --remove-verifies 11 --silent > /dev/null 2>&1
    local line
    line=$(read_verifies aitasks/t99_t.md)
    assert_eq "combined add/remove" "[10, 12, 30]" "$line"

    teardown
}

test_update_set_seeds_then_add() {
    echo "=== Test: --verifies seeds base then --add-verifies applies on top ==="
    setup_project

    write_task aitasks/t99_t.md "verifies: [10]"
    git add -A && git commit -m "seed" --quiet

    bash .aitask-scripts/aitask_update.sh --batch 99 \
        --verifies "40,41" --add-verifies 42 --silent > /dev/null 2>&1
    local line
    line=$(read_verifies aitasks/t99_t.md)
    assert_eq "set+add precedence" "[40, 41, 42]" "$line"

    teardown
}

test_fold_unions_verifies() {
    echo "=== Test: fold unions verifies from primary + folded tasks ==="
    setup_project

    write_task aitasks/t10_a.md "verifies: [1, 2]"
    write_task aitasks/t11_b.md "verifies: [2, 3]"
    write_task aitasks/t12_c.md
    git add -A && git commit -m "seed" --quiet

    bash .aitask-scripts/aitask_fold_mark.sh --commit-mode none 12 10 11 > /dev/null 2>&1
    local line
    line=$(read_verifies aitasks/t12_c.md)
    assert_eq "fold union: [1, 2, 3]" "[1, 2, 3]" "$line"

    teardown
}

test_fold_preserves_primary_verifies() {
    echo "=== Test: fold preserves primary's existing verifies entries first ==="
    setup_project

    write_task aitasks/t10_a.md "verifies: [1, 2]"
    write_task aitasks/t12_c.md "verifies: [9]"
    git add -A && git commit -m "seed" --quiet

    bash .aitask-scripts/aitask_fold_mark.sh --commit-mode none 12 10 > /dev/null 2>&1
    local line
    line=$(read_verifies aitasks/t12_c.md)
    assert_eq "primary first, then folded" "[9, 1, 2]" "$line"

    teardown
}

test_fold_no_verifies_anywhere() {
    echo "=== Test: fold with no verifies anywhere emits no verifies line ==="
    setup_project

    write_task aitasks/t10_a.md
    write_task aitasks/t12_c.md
    git add -A && git commit -m "seed" --quiet

    bash .aitask-scripts/aitask_fold_mark.sh --commit-mode none 12 10 > /dev/null 2>&1
    local content
    content=$(cat aitasks/t12_c.md)
    assert_not_contains "no verifies line" "verifies:" "$content"

    teardown
}

test_syntax_check() {
    echo "=== Test: syntax check touched scripts ==="
    TOTAL=$((TOTAL + 1))
    if bash -n "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" \
        && bash -n "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" \
        && bash -n "$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: syntax check"
    fi
}

teardown_all() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -d "$d" ]] && rm -rf "$d"
    done
}
trap teardown_all EXIT

test_create_with_verifies
test_create_without_verifies_omits_field
test_update_set_verifies
test_update_add_verifies
test_update_remove_verifies
test_update_add_and_remove_combined
test_update_set_seeds_then_add
test_fold_unions_verifies
test_fold_preserves_primary_verifies
test_fold_no_verifies_anywhere
test_syntax_check

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
