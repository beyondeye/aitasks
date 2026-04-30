#!/usr/bin/env bash
# test_verification_followup.sh - Tests for aitask_verification_followup.sh (t583_6)
#
# Covers the follow-up bug-task creation flow delivered by t583_3:
#   1. Happy path: single `verifies:` entry auto-resolves origin, produces
#      FOLLOWUP_CREATED on stdout, writes a bug task with the failing item
#      text + commit/file context.
#   2. Ambiguous origin: 2+ `verifies:` entries without --origin -> exit 2
#      and ORIGIN_AMBIGUOUS:<csv> on stdout (no mutation).
#   3. Explicit --origin resolves ambiguity.
#   4. Back-reference appended to an existing `## Final Implementation Notes`
#      section in the origin's archived plan.
#   5. Back-reference creates the section when the archived plan lacks it.
#
# Run: bash tests/test_verification_followup.sh

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
        echo "  actual: $actual"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (unexpected '$unexpected' found)"
        echo "  actual: $actual"
    else
        PASS=$((PASS + 1))
    fi
}

# setup_project creates a bare-remote + local-clone pair, copies the minimal
# script set needed by aitask_verification_followup.sh (and its transitive
# deps), initializes the atomic id counter, and leaves CWD inside the local
# clone via pushd.
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

    mkdir -p aitasks/metadata aiplans/archived .aitask-scripts/lib

    # Minimum script set: followup helper + parser + create/update chain
    # (create.sh --commit calls claim_id + fold_mark transitively).
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_followup.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.py" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/*.sh

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\nmanual_verification\n' \
        > aitasks/metadata/task_types.txt
    : > aitasks/metadata/labels.txt

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    # Initialize the atomic id counter branch so aitask_create.sh --commit works.
    ./.aitask-scripts/aitask_claim_id.sh --init > /dev/null 2>&1
}

teardown() {
    popd > /dev/null 2>&1 || true
}

# seed_origin_commit <origin_id> creates a feature task, commits a dummy source
# file with the conventional "(tN)" suffix, and pushes. Returns via stdout the
# short commit hash.
seed_origin_commit() {
    local origin="$1"
    mkdir -p src
    printf 'placeholder for t%s\n' "$origin" > "src/origin_${origin}.py"
    git add "src/origin_${origin}.py" > /dev/null
    git commit -m "feature: seed origin (t${origin})" --quiet > /dev/null
    git rev-parse --short HEAD
}

# write_mv_task <path> <verifies_list_literal> writes a manual-verification
# task file with one unchecked checklist item.
write_mv_task() {
    local path="$1" verifies_literal="$2"
    mkdir -p "$(dirname "$path")"
    {
        printf '%s\n' "---"
        printf '%s\n' "priority: medium"
        printf '%s\n' "effort: low"
        printf '%s\n' "depends: []"
        printf '%s\n' "issue_type: manual_verification"
        printf '%s\n' "status: Ready"
        printf '%s\n' "labels: []"
        printf '%s\n' "verifies: ${verifies_literal}"
        printf '%s\n' "created_at: 2026-01-01 10:00"
        printf '%s\n' "updated_at: 2026-01-01 10:00"
        printf '%s\n' "---"
        printf '\n## Verification Checklist\n\n'
        printf -- '- [ ] Button opens the modal cleanly\n'
    } > "$path"
}

# Locate the bug task filepath emitted on the FOLLOWUP_CREATED line.
followup_path_from_output() {
    echo "$1" | sed -n 's/^FOLLOWUP_CREATED:[^:]*:\(.*\)$/\1/p' | tail -1
}

followup_id_from_output() {
    echo "$1" | sed -n 's/^FOLLOWUP_CREATED:\([^:]*\):.*$/\1/p' | tail -1
}

test_happy_path_single_verifies() {
    echo "=== Test: happy path — single verifies auto-resolves origin ==="
    setup_project

    local hash
    hash=$(seed_origin_commit 42)
    write_mv_task aitasks/t99_manual.md "[42]"
    git add -A && git commit -m "seed mv task" --quiet

    local out rc
    out=$(bash .aitask-scripts/aitask_verification_followup.sh --from 99 --item 1 2>&1) && rc=0 || rc=$?
    assert_eq "happy path exit 0" "0" "$rc"
    assert_contains "FOLLOWUP_CREATED emitted" "FOLLOWUP_CREATED:" "$out"

    local new_path
    new_path=$(followup_path_from_output "$out")
    if [[ -z "$new_path" || ! -f "$new_path" ]]; then
        FAIL=$((FAIL + 1))
        TOTAL=$((TOTAL + 1))
        echo "FAIL: bug task path not resolvable or file missing"
        echo "  out: $out"
    else
        TOTAL=$((TOTAL + 1)); PASS=$((PASS + 1))
        local body
        body=$(cat "$new_path")
        assert_contains "bug task includes failing item text" "Button opens the modal cleanly" "$body"
        assert_contains "bug task references origin commit" "$hash" "$body"
        assert_contains "bug task references touched file" "src/origin_42.py" "$body"
        assert_contains "bug task depends on origin" "depends: [42]" "$body"
        assert_contains "bug task type is bug" "issue_type: bug" "$body"
    fi

    teardown
}

test_ambiguous_origin() {
    echo "=== Test: ambiguous origin — 2+ verifies without --origin ==="
    setup_project

    seed_origin_commit 42 > /dev/null
    seed_origin_commit 43 > /dev/null
    write_mv_task aitasks/t99_manual.md "[42, 43]"
    git add -A && git commit -m "seed mv task" --quiet

    local out rc
    out=$(bash .aitask-scripts/aitask_verification_followup.sh --from 99 --item 1 2>&1) && rc=0 || rc=$?
    assert_eq "ambiguous origin exits 2" "2" "$rc"
    assert_contains "ORIGIN_AMBIGUOUS emitted" "ORIGIN_AMBIGUOUS:" "$out"
    assert_contains "csv contains 42" "42" "$out"
    assert_contains "csv contains 43" "43" "$out"
    assert_not_contains "no FOLLOWUP_CREATED on ambiguous" "FOLLOWUP_CREATED:" "$out"

    teardown
}

test_explicit_origin_resolves_ambiguity() {
    echo "=== Test: explicit --origin resolves ambiguity ==="
    setup_project

    local hash
    hash=$(seed_origin_commit 42)
    seed_origin_commit 43 > /dev/null
    write_mv_task aitasks/t99_manual.md "[42, 43]"
    git add -A && git commit -m "seed mv task" --quiet

    local out rc
    out=$(bash .aitask-scripts/aitask_verification_followup.sh --from 99 --item 1 --origin 42 2>&1) && rc=0 || rc=$?
    assert_eq "explicit origin exits 0" "0" "$rc"
    assert_contains "FOLLOWUP_CREATED emitted with --origin" "FOLLOWUP_CREATED:" "$out"

    local new_path
    new_path=$(followup_path_from_output "$out")
    if [[ -n "$new_path" && -f "$new_path" ]]; then
        local body
        body=$(cat "$new_path")
        assert_contains "bug task depends on chosen origin (42)" "depends: [42]" "$body"
        assert_not_contains "bug task does not reference other origin (43)" "depends: [43]" "$body"
        assert_contains "chosen origin commit included" "$hash" "$body"
    else
        TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
        echo "FAIL: bug task path not resolvable for explicit-origin case"
    fi

    teardown
}

test_backref_appended_to_existing_notes() {
    echo "=== Test: back-reference appended to existing Final Implementation Notes ==="
    setup_project

    seed_origin_commit 42 > /dev/null
    write_mv_task aitasks/t99_manual.md "[42]"

    # Archived plan with an existing Final Implementation Notes section.
    mkdir -p aiplans/archived
    cat > aiplans/archived/p42_origin.md <<'EOF'
---
Task: t42_origin.md
---

# Plan: origin

## Final Implementation Notes

- **Actual work done:** initial implementation
EOF
    git add -A && git commit -m "seed mv task + archived plan" --quiet

    local out rc
    out=$(bash .aitask-scripts/aitask_verification_followup.sh --from 99 --item 1 2>&1) && rc=0 || rc=$?
    assert_eq "backref path exit 0" "0" "$rc"

    local new_id
    new_id=$(followup_id_from_output "$out")
    local plan_content
    plan_content=$(cat aiplans/archived/p42_origin.md)
    assert_contains "plan mentions Manual-verification failure" "Manual-verification failure" "$plan_content"
    assert_contains "plan references new follow-up task id" "t${new_id}" "$plan_content"
    assert_contains "existing notes line preserved" "initial implementation" "$plan_content"

    # Exactly one "## Final Implementation Notes" heading — the helper should
    # have appended under the existing section, not duplicated it.
    local heading_count
    heading_count=$(grep -c '^## Final Implementation Notes' aiplans/archived/p42_origin.md || true)
    assert_eq "single Final Implementation Notes section" "1" "$heading_count"

    teardown
}

test_backref_creates_section_when_missing() {
    echo "=== Test: back-reference creates section when archived plan lacks it ==="
    setup_project

    seed_origin_commit 42 > /dev/null
    write_mv_task aitasks/t99_manual.md "[42]"

    # Archived plan WITHOUT a Final Implementation Notes section.
    mkdir -p aiplans/archived
    cat > aiplans/archived/p42_origin.md <<'EOF'
---
Task: t42_origin.md
---

# Plan: origin

## Overview

Something else.
EOF
    git add -A && git commit -m "seed mv task + archived plan (no notes)" --quiet

    local out rc
    out=$(bash .aitask-scripts/aitask_verification_followup.sh --from 99 --item 1 2>&1) && rc=0 || rc=$?
    assert_eq "create-section path exit 0" "0" "$rc"

    local new_id
    new_id=$(followup_id_from_output "$out")
    local plan_content
    plan_content=$(cat aiplans/archived/p42_origin.md)
    assert_contains "Final Implementation Notes section created" "## Final Implementation Notes" "$plan_content"
    assert_contains "plan references new follow-up task id" "t${new_id}" "$plan_content"
    assert_contains "pre-existing section preserved" "## Overview" "$plan_content"

    teardown
}

test_syntax_check() {
    echo "=== Test: syntax check touched script ==="
    TOTAL=$((TOTAL + 1))
    if bash -n "$PROJECT_DIR/.aitask-scripts/aitask_verification_followup.sh"; then
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

test_happy_path_single_verifies
test_ambiguous_origin
test_explicit_origin_resolves_ambiguity
test_backref_appended_to_existing_notes
test_backref_creates_section_when_missing
test_syntax_check

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
