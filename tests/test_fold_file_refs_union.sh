#!/usr/bin/env bash
# test_fold_file_refs_union.sh - Tests for file_references union during fold
#
# Covers aitask_fold_mark.sh's extension to union file_references from
# primary + directly folded + transitively folded tasks into the primary.
#
# Run: bash tests/test_fold_file_refs_union.sh

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
    cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/*.sh

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\n' > aitasks/metadata/task_types.txt
    : > aitasks/metadata/labels.txt

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    PROJECT_UNDER_TEST="$local_dir"
}

teardown() {
    popd > /dev/null 2>&1 || true
}

# write_task PATH [extra_frontmatter_line ...]
# Writes a task file with a minimal Ready frontmatter. Extra lines are inserted
# inside the frontmatter before created_at/updated_at.
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

test_basic_union() {
    echo "=== Test: basic union — primary + folded entries merge ==="
    setup_project

    write_task aitasks/t10_primary.md "file_references: [a.py:1-5]"
    write_task aitasks/t20_folded.md "file_references: [b.py, a.py:10-20]"

    git add -A
    git commit -m "Setup basic union" --quiet

    local output
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode none 10 20 2>&1)
    assert_contains "primary updated" "PRIMARY_UPDATED:10" "$output"
    assert_contains "t20 folded" "FOLDED:20" "$output"

    local refs
    refs=$(read_frontmatter_field aitasks/t10_primary.md file_references)
    # Expect primary's a.py:1-5 first, then b.py, then a.py:10-20
    assert_contains "refs contain a.py:1-5" "a.py:1-5" "$refs"
    assert_contains "refs contain b.py" "b.py" "$refs"
    assert_contains "refs contain a.py:10-20" "a.py:10-20" "$refs"

    # Order: primary first, then folded in argument order
    local stripped
    stripped=$(echo "$refs" | tr -d '[]" ')
    assert_eq "order preserved: primary, then folded" "a.py:1-5,b.py,a.py:10-20" "$stripped"

    teardown
}

test_dedup_exact_match() {
    echo "=== Test: dedup — identical entries collapse ==="
    setup_project

    write_task aitasks/t10_primary.md "file_references: [a.py:1-5]"
    write_task aitasks/t20_folded.md "file_references: [a.py:1-5]"

    git add -A
    git commit -m "Setup dedup" --quiet

    bash .aitask-scripts/aitask_fold_mark.sh --commit-mode none 10 20 > /dev/null 2>&1

    local refs
    refs=$(read_frontmatter_field aitasks/t10_primary.md file_references)
    local stripped
    stripped=$(echo "$refs" | tr -d '[]" ')
    assert_eq "dedup leaves single entry" "a.py:1-5" "$stripped"

    teardown
}

test_transitive_union() {
    echo "=== Test: transitive — A's file_references unioned via folded_tasks chain ==="
    setup_project

    # P = primary with [p.py]
    write_task aitasks/t50_primary.md "file_references: [p.py]"
    # Q has folded_tasks: [70] and its own [q.py]
    write_task aitasks/t60_q.md "file_references: [q.py]" "folded_tasks: [70]"
    # R was previously folded into Q and has [r.py]
    write_task aitasks/t70_r.md "file_references: [r.py]" "folded_into: 60"
    # Rewrite R's status to Folded (write_task sets Ready first, then extras append)
    sed -i 's/^status: Ready$/status: Folded/' aitasks/t70_r.md 2>/dev/null || \
        { sed -i.bak 's/^status: Ready$/status: Folded/' aitasks/t70_r.md; rm -f aitasks/t70_r.md.bak; }

    git add -A
    git commit -m "Setup transitive" --quiet

    local output
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode none 50 60 2>&1)
    assert_contains "Q folded" "FOLDED:60" "$output"
    assert_contains "transitive 70 reported" "TRANSITIVE:70" "$output"

    local refs
    refs=$(read_frontmatter_field aitasks/t50_primary.md file_references)
    local stripped
    stripped=$(echo "$refs" | tr -d '[]" ')
    assert_eq "union includes primary+direct+transitive" "p.py,q.py,r.py" "$stripped"

    teardown
}

test_empty_union_leaves_primary_untouched() {
    echo "=== Test: empty union — neither primary nor folded has file_references ==="
    setup_project

    write_task aitasks/t10_primary.md
    write_task aitasks/t20_folded.md

    git add -A
    git commit -m "Setup empty" --quiet

    bash .aitask-scripts/aitask_fold_mark.sh --commit-mode none 10 20 > /dev/null 2>&1

    # file_references line should not appear at all (or be empty)
    local refs
    refs=$(read_frontmatter_field aitasks/t10_primary.md file_references)
    assert_eq "file_references absent or empty" "" "$refs"

    teardown
}

test_primary_only_preserved() {
    echo "=== Test: folded task has no refs — primary's entries preserved ==="
    setup_project

    write_task aitasks/t10_primary.md "file_references: [only.py:1-3]"
    write_task aitasks/t20_folded.md

    git add -A
    git commit -m "Setup primary-only" --quiet

    bash .aitask-scripts/aitask_fold_mark.sh --commit-mode none 10 20 > /dev/null 2>&1

    local refs
    refs=$(read_frontmatter_field aitasks/t10_primary.md file_references)
    local stripped
    stripped=$(echo "$refs" | tr -d '[]" ')
    assert_eq "primary entry preserved" "only.py:1-3" "$stripped"

    teardown
}

test_syntax_check() {
    echo "=== Test: syntax check touched scripts ==="
    TOTAL=$((TOTAL + 1))
    if bash -n "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" \
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

test_basic_union
test_dedup_exact_match
test_transitive_union
test_empty_union_leaves_primary_untouched
test_primary_only_preserved
test_syntax_check

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
