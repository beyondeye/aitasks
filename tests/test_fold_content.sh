#!/usr/bin/env bash
# test_fold_content.sh - Tests for aitask_fold_content.sh
#
# Covers:
#   - Positional <primary_file> form produces merged body
#   - --primary-stdin form matches positional form when stdin = primary body
#   - Filename parsing: t12_simple, t16_2_child, t100_multi_word_name
#   - Frontmatter correctly stripped
#   - "## Folded Tasks" section references each folded task with filename
#
# Run: bash tests/test_fold_content.sh

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
        echo "FAIL: $desc (missing '$expected')"
    fi
}

assert_not_contains() {
    local desc="$1" unwanted="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF "$unwanted"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (should not contain '$unwanted')"
    else
        PASS=$((PASS + 1))
    fi
}

setup_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")

    pushd "$tmpdir" > /dev/null

    mkdir -p aitasks .aitask-scripts/lib
    cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_content.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/*.sh

    PROJECT_UNDER_TEST="$tmpdir"
}

teardown() {
    popd > /dev/null 2>&1 || true
}

write_task() {
    local path="$1"
    local body="$2"
    mkdir -p "$(dirname "$path")"
    cat > "$path" << EOF
---
priority: medium
effort: low
status: Ready
---

${body}
EOF
}

test_positional_basic() {
    echo "=== Test: positional primary file ==="
    setup_project
    write_task aitasks/t12_simple.md "Primary body content"
    write_task aitasks/t13_other.md "Folded content"

    local output
    output=$(bash .aitask-scripts/aitask_fold_content.sh aitasks/t12_simple.md aitasks/t13_other.md)

    assert_contains "primary body preserved" "Primary body content" "$output"
    assert_contains "merged header for folded task" "## Merged from t13: other" "$output"
    assert_contains "folded body preserved" "Folded content" "$output"
    assert_contains "folded tasks section header" "## Folded Tasks" "$output"
    assert_contains "folded tasks reference line" "**t13** (\`t13_other.md\`)" "$output"
    assert_not_contains "frontmatter marker not leaked" "priority: medium" "$output"

    teardown
}

test_stdin_form() {
    echo "=== Test: --primary-stdin form ==="
    setup_project
    write_task aitasks/t20_folded.md "Stdin folded"

    local body="Stdin primary body"
    local output
    output=$(echo "$body" | bash .aitask-scripts/aitask_fold_content.sh --primary-stdin aitasks/t20_folded.md)

    assert_contains "stdin primary body preserved" "Stdin primary body" "$output"
    assert_contains "folded header" "## Merged from t20: folded" "$output"
    assert_contains "folded body" "Stdin folded" "$output"

    teardown
}

test_filename_parsing() {
    echo "=== Test: filename parsing variants ==="
    setup_project
    write_task aitasks/t12_simple.md "B12"
    write_task aitasks/t16/t16_2_child.md "B16c"
    write_task aitasks/t100_multi_word_name.md "B100"
    write_task aitasks/t1_primary.md "Primary"

    local output
    output=$(bash .aitask-scripts/aitask_fold_content.sh \
        aitasks/t1_primary.md \
        aitasks/t12_simple.md \
        aitasks/t16/t16_2_child.md \
        aitasks/t100_multi_word_name.md)

    assert_contains "parent id t12 'simple'" "## Merged from t12: simple" "$output"
    assert_contains "child id t16_2 'child'" "## Merged from t16_2: child" "$output"
    assert_contains "multi-word name normalized" "## Merged from t100: multi word name" "$output"
    assert_contains "ref to t16_2 child file" "**t16_2** (\`t16_2_child.md\`)" "$output"

    teardown
}

test_frontmatter_stripped() {
    echo "=== Test: frontmatter stripped from all inputs ==="
    setup_project
    write_task aitasks/t70_prim.md "Prim body"
    write_task aitasks/t71_a.md "A body"
    write_task aitasks/t72_b.md "B body"

    local output
    output=$(bash .aitask-scripts/aitask_fold_content.sh aitasks/t70_prim.md aitasks/t71_a.md aitasks/t72_b.md)

    assert_not_contains "no priority field" "priority: medium" "$output"
    assert_not_contains "no effort field" "effort: low" "$output"
    assert_not_contains "no status field" "status: Ready" "$output"

    teardown
}

teardown_all() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -d "$d" ]] && rm -rf "$d"
    done
}
trap teardown_all EXIT

test_positional_basic
test_stdin_form
test_filename_parsing
test_frontmatter_stripped

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
