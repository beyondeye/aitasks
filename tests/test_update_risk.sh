#!/usr/bin/env bash
# test_update_risk.sh - Tests for the two-field risk (`risk_code_health` +
# `risk_goal_achievement`) and `risk_mitigation_tasks` frontmatter plumbing in
# aitask_update.sh (t884_9, replacing the single aggregate `risk` of t884_1).
#
# Covers:
#   - --risk-code-health high writes `risk_code_health: high`
#   - --risk-goal-achievement medium writes `risk_goal_achievement: medium`
#     (independent of code-health)
#   - both flags at once write both lines
#   - invalid value on either flag is rejected (non-zero exit)
#   - updating an unrelated field on a risk-less task leaves NO risk lines
#     (omit-by-default / conditional-emit holds)
#   - clearing one field with "" leaves the other intact
#   - --risk-mitigation-tasks writes a YAML list; an unrelated later update
#     preserves it (read-modify-write friendly)
#   - GUARD: aitask_create.sh emits neither risk field nor risk_mitigation_tasks
#     (risk is a planning output, never a creation input)
#
# Run: bash tests/test_update_risk.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

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
    local desc="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if grep -qF -- "$needle" <<< "$haystack"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (missing '$needle' in: $haystack)"
    fi
}

# Assert that the frontmatter contains no line beginning with "<field>:".
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

    mkdir -p aitasks/metadata aitasks/new
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
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

test_set_and_validate_risk() {
    echo "=== Test: two-field risk set + validation ==="
    setup_project

    write_task aitasks/t10_foo.md
    git add -A; git commit -m "seed t10" --quiet

    # (a) --risk-code-health writes its own line
    bash .aitask-scripts/aitask_update.sh --batch 10 --risk-code-health high --silent >/dev/null
    assert_eq "code-health risk set to high" "high" "$(read_frontmatter_field aitasks/t10_foo.md risk_code_health)"

    # (b) --risk-goal-achievement writes its own line, independent of code-health
    bash .aitask-scripts/aitask_update.sh --batch 10 --risk-goal-achievement medium --silent >/dev/null
    assert_eq "goal risk set to medium" "medium" "$(read_frontmatter_field aitasks/t10_foo.md risk_goal_achievement)"
    assert_eq "code-health risk preserved" "high" "$(read_frontmatter_field aitasks/t10_foo.md risk_code_health)"

    # (c) both at once
    bash .aitask-scripts/aitask_update.sh --batch 10 --risk-code-health low --risk-goal-achievement high --silent >/dev/null
    assert_eq "code-health updated to low" "low" "$(read_frontmatter_field aitasks/t10_foo.md risk_code_health)"
    assert_eq "goal updated to high" "high" "$(read_frontmatter_field aitasks/t10_foo.md risk_goal_achievement)"

    # (d) invalid value rejected on each flag
    local rc
    set +e
    bash .aitask-scripts/aitask_update.sh --batch 10 --risk-code-health bogus --silent >/dev/null 2>&1
    rc=$?
    set -e
    assert_nonzero "invalid --risk-code-health rejected" "$rc"
    set +e
    bash .aitask-scripts/aitask_update.sh --batch 10 --risk-goal-achievement nope --silent >/dev/null 2>&1
    rc=$?
    set -e
    assert_nonzero "invalid --risk-goal-achievement rejected" "$rc"

    # (f) clearing one field with "" leaves the other intact
    bash .aitask-scripts/aitask_update.sh --batch 10 --risk-code-health "" --silent >/dev/null
    assert_no_field "code-health cleared by \"\"" aitasks/t10_foo.md risk_code_health
    assert_eq "goal risk still set after clearing code-health" "high" "$(read_frontmatter_field aitasks/t10_foo.md risk_goal_achievement)"

    teardown
}

test_omit_by_default() {
    echo "=== Test: unrelated update on a risk-less task leaves no risk lines ==="
    setup_project

    write_task aitasks/t20_bar.md
    git add -A; git commit -m "seed t20" --quiet

    bash .aitask-scripts/aitask_update.sh --batch 20 --priority high --silent >/dev/null
    assert_eq "priority updated" "high" "$(read_frontmatter_field aitasks/t20_bar.md priority)"
    assert_no_field "no risk_code_health: line after unrelated update" aitasks/t20_bar.md risk_code_health
    assert_no_field "no risk_goal_achievement: line after unrelated update" aitasks/t20_bar.md risk_goal_achievement

    teardown
}

test_risk_mitigation_tasks() {
    echo "=== Test: --risk-mitigation-tasks list + read-modify-write preserve ==="
    setup_project

    write_task aitasks/t30_baz.md
    git add -A; git commit -m "seed t30" --quiet

    bash .aitask-scripts/aitask_update.sh --batch 30 --risk-mitigation-tasks "12,13" --silent >/dev/null
    local rmt
    rmt=$(read_frontmatter_field aitasks/t30_baz.md risk_mitigation_tasks)
    assert_contains "risk_mitigation_tasks contains 12" "12" "$rmt"
    assert_contains "risk_mitigation_tasks contains 13" "13" "$rmt"

    # Unrelated update preserves the list (read-modify-write contract for t884_4)
    bash .aitask-scripts/aitask_update.sh --batch 30 --status Editing --silent >/dev/null
    rmt=$(read_frontmatter_field aitasks/t30_baz.md risk_mitigation_tasks)
    assert_contains "list preserved after unrelated update (12)" "12" "$rmt"
    assert_contains "list preserved after unrelated update (13)" "13" "$rmt"

    # Cleared by ""
    bash .aitask-scripts/aitask_update.sh --batch 30 --risk-mitigation-tasks "" --silent >/dev/null
    assert_no_field "risk_mitigation_tasks cleared by \"\"" aitasks/t30_baz.md risk_mitigation_tasks

    teardown
}

test_create_emits_no_risk() {
    echo "=== Test: GUARD — aitask_create.sh emits no risk fields ==="
    setup_project

    local created
    created=$(./.aitask-scripts/aitask_create.sh --batch --silent \
        --name "no_risk_at_create" --desc "x" 2>/dev/null)

    TOTAL=$((TOTAL + 1))
    if [[ -n "$created" && -f "$created" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: create did not yield a file (got: '$created')"
        teardown
        return
    fi

    assert_no_field "created task has no risk_code_health:" "$created" risk_code_health
    assert_no_field "created task has no risk_goal_achievement:" "$created" risk_goal_achievement
    assert_no_field "created task has no risk_mitigation_tasks:" "$created" risk_mitigation_tasks

    teardown
}

teardown_all() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -d "$d" ]] && rm -rf "$d"
    done
}
trap teardown_all EXIT

test_set_and_validate_risk
test_omit_by_default
test_risk_mitigation_tasks
test_create_emits_no_risk

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
