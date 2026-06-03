#!/usr/bin/env bash
# test_fold_risk_mitigation_drop.sh - Tests that aitask_fold_mark.sh treats
# risk_mitigation_tasks correctly when folding (t884_9).
#
# Contract:
#   - risk_mitigation_tasks is instance-specific and is NOT unioned into the
#     primary (unlike verifies).
#   - A folded task's own risk_mitigation_tasks is cleared on fold.
#   - The primary keeps both its own risk fields (risk_code_health +
#     risk_goal_achievement) untouched.
#
# Run: bash tests/test_fold_risk_mitigation_drop.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Shared assertion helpers (see tests/lib/asserts.sh).
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()


# Assert the frontmatter contains no line beginning with "<field>:".
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

    mkdir -p aitasks/metadata
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
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

test_fold_drops_mitigation_keeps_risk() {
    echo "=== Test: fold drops risk_mitigation_tasks, keeps primary's risk fields ==="
    setup_project

    # Primary carries both its own risk fields but no mitigation list.
    write_task aitasks/t10_primary.md "risk_code_health: medium" "risk_goal_achievement: high"
    # Folded task carries a mitigation list (and its own risk fields).
    write_task aitasks/t20_folded.md "risk_code_health: high" "risk_goal_achievement: low" "risk_mitigation_tasks: [99]"

    git add -A
    git commit -m "seed fold fixtures" --quiet

    local output
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode none 10 20 2>&1)
    echo "$output" | grep -q "FOLDED:20" || { echo "FAIL: t20 not folded"; FAIL=$((FAIL+1)); }

    # Primary keeps both its own risk fields, and did NOT gain a
    # risk_mitigation_tasks line
    assert_eq "primary keeps risk_code_health: medium" "medium" "$(read_frontmatter_field aitasks/t10_primary.md risk_code_health)"
    assert_eq "primary keeps risk_goal_achievement: high" "high" "$(read_frontmatter_field aitasks/t10_primary.md risk_goal_achievement)"
    assert_no_field "primary did not gain risk_mitigation_tasks" aitasks/t10_primary.md risk_mitigation_tasks

    # Folded task's own mitigation list was cleared
    assert_no_field "folded task's risk_mitigation_tasks cleared" aitasks/t20_folded.md risk_mitigation_tasks
    # Folded task still marked Folded into the primary
    assert_eq "folded task status=Folded" "Folded" "$(read_frontmatter_field aitasks/t20_folded.md status)"

    teardown
}

teardown_all() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -d "$d" ]] && rm -rf "$d"
    done
}
trap teardown_all EXIT

test_fold_drops_mitigation_keeps_risk

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
