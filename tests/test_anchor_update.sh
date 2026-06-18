#!/usr/bin/env bash
# test_anchor_update.sh - Tests for editable + validated `anchor:` in
# aitask_update.sh (t1016_1): --anchor sets/clears, id normalization to bare
# form, existence validation (the board re-anchor integrity gate), and
# read-modify-write preservation under unrelated updates.
#
# Covers:
#   - --anchor 42                -> anchor: 42 (set)
#   - --anchor t42               -> anchor: 42 (leading t stripped)
#   - --anchor ""                -> field cleared
#   - --anchor 999999 (missing)  -> non-zero, file unchanged (validation gate)
#   - unrelated update           -> existing anchor preserved (RMW)
#
# Run: bash tests/test_anchor_update.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

assert_nonzero() {
    local desc="$1" rc="$2"
    TOTAL=$((TOTAL + 1))
    if [[ "$rc" -ne 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected non-zero exit, got $rc)"
    fi
}

assert_no_field() {
    local desc="$1" file="$2" field="$3"
    TOTAL=$((TOTAL + 1))
    if grep -qE "^${field}:" "$file"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc ('${field}:' unexpectedly present in $file)"
    else
        PASS=$((PASS + 1))
    fi
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

    mkdir -p aitasks/metadata aitasks/new aitasks/archived
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    chmod +x .aitask-scripts/*.sh

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\n' > aitasks/metadata/task_types.txt
    : > aitasks/metadata/labels.txt
    echo "aitasks/new/" > .gitignore

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1 || true
}

teardown() {
    popd > /dev/null 2>&1 || true
}

seed_task() {
    local path="$1"; shift
    mkdir -p "$(dirname "$path")"
    {
        printf '%s\n' "---"
        printf '%s\n' "priority: medium"
        printf '%s\n' "effort: low"
        printf '%s\n' "depends: []"
        printf '%s\n' "issue_type: chore"
        printf '%s\n' "status: Ready"
        printf '%s\n' "labels: []"
        for extra in "$@"; do printf '%s\n' "$extra"; done
        printf '%s\n' "created_at: 2026-01-01 10:00"
        printf '%s\n' "updated_at: 2026-01-01 10:00"
        printf '%s\n' "---"
        printf '\nBody\n'
    } > "$path"
}

test_set_normalize_clear() {
    echo "=== Test: --anchor set / normalize / clear ==="
    setup_project
    seed_task aitasks/t42_target.md
    seed_task aitasks/t10_foo.md
    git add -A; git commit -m "seed" --quiet

    # set
    bash .aitask-scripts/aitask_update.sh --batch 10 --anchor 42 --silent >/dev/null
    assert_eq "--anchor 42 sets anchor: 42" "42" "$(read_frontmatter_field aitasks/t10_foo.md anchor)"

    # normalize t-prefix -> bare
    bash .aitask-scripts/aitask_update.sh --batch 10 --anchor t42 --silent >/dev/null
    assert_eq "--anchor t42 stores bare 42" "42" "$(read_frontmatter_field aitasks/t10_foo.md anchor)"

    # clear by ""
    bash .aitask-scripts/aitask_update.sh --batch 10 --anchor "" --silent >/dev/null
    assert_no_field "--anchor \"\" clears the field" aitasks/t10_foo.md anchor

    teardown
}

test_missing_rejected_file_unchanged() {
    echo "=== Test: --anchor <missing> rejected, file unchanged (integrity gate) ==="
    setup_project
    seed_task aitasks/t20_bar.md "anchor: 42"
    seed_task aitasks/t42_target.md
    git add -A; git commit -m "seed" --quiet

    local before
    before="$(cat aitasks/t20_bar.md)"

    local rc
    set +e
    bash .aitask-scripts/aitask_update.sh --batch 20 --anchor 999999 --silent >/dev/null 2>&1; rc=$?
    set -e
    assert_nonzero "--anchor 999999 rejected" "$rc"

    TOTAL=$((TOTAL + 1))
    if [[ "$before" == "$(cat aitasks/t20_bar.md)" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: file changed despite rejected anchor update"
    fi
    assert_eq "original anchor intact after rejected update" "42" "$(read_frontmatter_field aitasks/t20_bar.md anchor)"

    teardown
}

test_rmw_preserve() {
    echo "=== Test: unrelated update preserves anchor (read-modify-write) ==="
    setup_project
    seed_task aitasks/t30_baz.md "anchor: 42"
    seed_task aitasks/t42_target.md
    git add -A; git commit -m "seed" --quiet

    bash .aitask-scripts/aitask_update.sh --batch 30 --priority high --silent >/dev/null
    assert_eq "priority updated" "high" "$(read_frontmatter_field aitasks/t30_baz.md priority)"
    assert_eq "anchor preserved after unrelated update" "42" "$(read_frontmatter_field aitasks/t30_baz.md anchor)"

    teardown
}

teardown_all() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -d "$d" ]] && rm -rf "$d"
    done
}
trap teardown_all EXIT

test_set_normalize_clear
test_missing_rejected_file_unchanged
test_rmw_preserve

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
