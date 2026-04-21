#!/usr/bin/env bash
# test_archive_verification_gate.sh - Tests for the manual_verification
# archival gate and carry-over flow in aitask_archive.sh.
#
# Covers:
#   - Gate blocks archival when any item is pending
#   - Gate blocks archival when any item is deferred and the carry-over flag
#     is not set
#   - Gate allows archival when all items are terminal
#   - Gate is no-op for non-manual_verification tasks
#   - Gate is no-op when the checklist section is missing
#   - --with-deferred-carryover creates a new seeded manual_verification task
#     (using a stubbed aitask_create.sh so the test stays hermetic)
#   - Child task gate path
#
# Run: bash tests/test_archive_verification_gate.sh

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
        echo "FAIL: $desc (expected output containing '$expected', got: $actual)"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -q "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (did NOT expect '$unexpected' in output, got: $actual)"
    else
        PASS=$((PASS + 1))
    fi
}

assert_file_exists() {
    local desc="$1" filepath="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$filepath" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (file '$filepath' does not exist)"
    fi
}

assert_file_not_exists() {
    local desc="$1" filepath="$2"
    TOTAL=$((TOTAL + 1))
    if [[ ! -f "$filepath" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (file '$filepath' should not exist)"
    fi
}

# Stub aitask_create.sh for carry-over tests. Builds a minimal task file
# with the frontmatter fields the gate needs, captures --name and --verifies,
# and outputs the file path. Keeps the test hermetic (no remote counter).
STUB_CREATE_CONTENTS='#!/usr/bin/env bash
set -euo pipefail

NAME=""
VERIFIES=""
TYPE=""
shift_needed=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --name) NAME="$2"; shift 2 ;;
        --verifies) VERIFIES="$2"; shift 2 ;;
        --type) TYPE="$2"; shift 2 ;;
        --batch|--commit|--silent) shift ;;
        --priority|--effort) shift 2 ;;
        *) shift ;;
    esac
done

[[ -z "$NAME" ]] && { echo "stub: --name required" >&2; exit 1; }

TASK_DIR="${TASK_DIR:-aitasks}"
mkdir -p "$TASK_DIR"

# Pick a non-colliding stub ID by scanning existing t<N>_*.md files.
NEXT=9001
while [[ -f "$TASK_DIR/t${NEXT}_${NAME}.md" ]]; do
    NEXT=$((NEXT + 1))
done

FILE="$TASK_DIR/t${NEXT}_${NAME}.md"
TIMESTAMP="$(date +"%Y-%m-%d %H:%M")"

{
    echo "---"
    echo "priority: medium"
    echo "effort: low"
    echo "depends: []"
    echo "issue_type: ${TYPE:-manual_verification}"
    echo "status: Ready"
    echo "labels: []"
    if [[ -n "$VERIFIES" ]]; then
        # Mimic format_yaml_list: "a,b,c" -> "[a, b, c]"
        formatted="[$(echo "$VERIFIES" | sed "s/,/, /g")]"
        echo "verifies: $formatted"
    fi
    echo "created_at: $TIMESTAMP"
    echo "updated_at: $TIMESTAMP"
    echo "---"
    echo
    echo "Stub-created carry-over task"
} > "$FILE"

git add "$FILE" >/dev/null 2>&1 || true
git commit -m "ait: Add stub task t${NEXT}" --quiet >/dev/null 2>&1 || true

echo "$FILE"
'

# --- Setup a test project with archive capabilities ---
# PROJECT_UNDER_TEST is set to the working directory.
# use_stub_create=true installs the stub aitask_create.sh instead of the real one.
setup_archive_project() {
    local use_stub_create="${1:-false}"
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

    # Copy scripts used by archive + verification gate.
    cp "$PROJECT_DIR/.aitask-scripts/aitask_archive.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.py" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true

    if [[ "$use_stub_create" == "true" ]]; then
        printf '%s' "$STUB_CREATE_CONTENTS" > .aitask-scripts/aitask_create.sh
    else
        cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/ 2>/dev/null || true
    fi

    chmod +x .aitask-scripts/*.sh .aitask-scripts/*.py 2>/dev/null || true

    # task_types.txt must include manual_verification for the gate to trigger.
    printf 'bug\nchore\ndocumentation\nfeature\nperformance\nrefactor\nstyle\ntest\nmanual_verification\n' \
        > aitasks/metadata/task_types.txt

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    PROJECT_UNDER_TEST="$local_dir"
}

teardown() {
    popd > /dev/null 2>&1 || true
}

# Write a manual_verification task file with the given checklist lines.
# Usage: write_mv_task <path> <issue_type> <verifies_or_empty> <checklist_line1> [<line2> ...]
write_mv_task() {
    local path="$1"; shift
    local issue_type="$1"; shift
    local verifies="$1"; shift

    {
        echo "---"
        echo "priority: medium"
        echo "effort: low"
        echo "depends: []"
        echo "issue_type: $issue_type"
        echo "status: Implementing"
        echo "labels: []"
        [[ -n "$verifies" ]] && echo "verifies: $verifies"
        echo "created_at: 2026-04-19 10:00"
        echo "updated_at: 2026-04-19 10:00"
        echo "---"
        echo
        echo "Body."
        echo
        echo "## Verification Checklist"
        echo
        for line in "$@"; do
            echo "$line"
        done
    } > "$path"
}

# --- Test 1: pending items block archival ---
test_pending_blocks_archival() {
    echo "=== Test 1: pending items block archival ==="
    setup_archive_project false

    write_mv_task aitasks/t100_verify.md manual_verification "" \
        "- [ ] first item pending" \
        "- [x] second item pass"

    git add -A && git commit -m "setup" --quiet

    local output rc
    set +e
    output=$(bash .aitask-scripts/aitask_archive.sh 100 2>&1)
    rc=$?
    set -e

    assert_eq "Exits 2 when pending" "2" "$rc"
    assert_contains "PENDING count emitted" "PENDING:1" "$output"
    assert_contains "VERIFICATION_PENDING marker emitted" "VERIFICATION_PENDING:" "$output"
    assert_not_contains "No COMMITTED line on blocked gate" "COMMITTED:" "$output"
    assert_file_exists "Task file still in aitasks/" "aitasks/t100_verify.md"

    teardown
}

# --- Test 2: deferred without flag blocks archival ---
test_deferred_without_flag_blocks() {
    echo ""
    echo "=== Test 2: deferred blocks without --with-deferred-carryover ==="
    setup_archive_project false

    write_mv_task aitasks/t101_verify.md manual_verification "" \
        "- [defer] deferred item" \
        "- [x] pass item"

    git add -A && git commit -m "setup" --quiet

    local output rc
    set +e
    output=$(bash .aitask-scripts/aitask_archive.sh 101 2>&1)
    rc=$?
    set -e

    assert_eq "Exits 2 when deferred without flag" "2" "$rc"
    assert_contains "DEFERRED count emitted" "DEFERRED:1" "$output"
    assert_contains "VERIFICATION_DEFERRED marker emitted" "VERIFICATION_DEFERRED:" "$output"
    assert_file_exists "Task file still in aitasks/" "aitasks/t101_verify.md"

    teardown
}

# --- Test 3: all-terminal items allow normal archival ---
test_all_terminal_archives_normally() {
    echo ""
    echo "=== Test 3: all-terminal items archive normally ==="
    setup_archive_project false

    write_mv_task aitasks/t102_verify.md manual_verification "" \
        "- [x] passed" \
        "- [fail] failed" \
        "- [skip] skipped"

    git add -A && git commit -m "setup" --quiet

    local output rc
    set +e
    output=$(bash .aitask-scripts/aitask_archive.sh 102 2>&1)
    rc=$?
    set -e

    assert_eq "Exits 0 when all terminal" "0" "$rc"
    assert_not_contains "No VERIFICATION_PENDING on success" "VERIFICATION_PENDING:" "$output"
    assert_not_contains "No VERIFICATION_DEFERRED on success" "VERIFICATION_DEFERRED:" "$output"
    assert_contains "ARCHIVED_TASK emitted" "ARCHIVED_TASK:" "$output"
    assert_file_not_exists "Task moved out of aitasks/" "aitasks/t102_verify.md"

    teardown
}

# --- Test 4: non-manual_verification tasks are no-op ---
test_non_manual_verification_is_noop() {
    echo ""
    echo "=== Test 4: non-manual_verification tasks skip the gate ==="
    setup_archive_project false

    # issue_type: feature with a dummy checklist — gate should ignore it.
    write_mv_task aitasks/t103_feature.md feature "" \
        "- [ ] would block if gate were active"

    git add -A && git commit -m "setup" --quiet

    local output rc
    set +e
    output=$(bash .aitask-scripts/aitask_archive.sh 103 2>&1)
    rc=$?
    set -e

    assert_eq "Exits 0 for feature task" "0" "$rc"
    assert_not_contains "No VERIFICATION_PENDING on feature task" "VERIFICATION_PENDING:" "$output"
    assert_contains "ARCHIVED_TASK emitted" "ARCHIVED_TASK:" "$output"

    teardown
}

# --- Test 5: manual_verification with no checklist section is no-op ---
test_no_checklist_is_noop() {
    echo ""
    echo "=== Test 5: manual_verification without checklist archives normally ==="
    setup_archive_project false

    cat > aitasks/t104_verify.md <<'TASK'
---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Implementing
labels: []
created_at: 2026-04-19 10:00
updated_at: 2026-04-19 10:00
---

Body without a Verification Checklist section.
TASK

    git add -A && git commit -m "setup" --quiet

    local output rc
    set +e
    output=$(bash .aitask-scripts/aitask_archive.sh 104 2>&1)
    rc=$?
    set -e

    assert_eq "Exits 0 when no checklist" "0" "$rc"
    assert_not_contains "No VERIFICATION_PENDING when empty" "VERIFICATION_PENDING:" "$output"
    assert_contains "ARCHIVED_TASK emitted" "ARCHIVED_TASK:" "$output"

    teardown
}

# --- Test 6: --with-deferred-carryover creates carry-over task + archives ---
test_deferred_with_flag_creates_carryover() {
    echo ""
    echo "=== Test 6: --with-deferred-carryover creates carry-over and archives ==="
    setup_archive_project true  # stub aitask_create.sh

    write_mv_task aitasks/t105_verify.md manual_verification "[t571_4, t571_5]" \
        "- [defer] needs follow-up review" \
        "- [x] confirmed working"

    git add -A && git commit -m "setup" --quiet

    local output rc
    set +e
    output=$(bash .aitask-scripts/aitask_archive.sh --with-deferred-carryover 105 2>&1)
    rc=$?
    set -e

    assert_eq "Exits 0 with flag + deferred" "0" "$rc"
    assert_contains "CARRYOVER_CREATED emitted" "CARRYOVER_CREATED:" "$output"
    assert_contains "ARCHIVED_TASK emitted" "ARCHIVED_TASK:" "$output"
    assert_file_not_exists "Original task archived" "aitasks/t105_verify.md"

    # Locate the carry-over task (stub assigns IDs starting at 9001).
    local carryover_file
    carryover_file=$(ls aitasks/t*_verify_carryover.md 2>/dev/null | head -1 || true)

    if [[ -z "$carryover_file" ]]; then
        FAIL=$((FAIL + 1))
        TOTAL=$((TOTAL + 1))
        echo "FAIL: carry-over task file not created in aitasks/"
    else
        PASS=$((PASS + 1))
        TOTAL=$((TOTAL + 1))
        # Carry-over must contain ONLY the deferred item, as a fresh `- [ ]`.
        local checklist
        checklist=$(grep '^- \[' "$carryover_file" || true)
        assert_contains "Carry-over has a checklist entry" "\[ \]" "$checklist"
        assert_contains "Carry-over item text preserved" "needs follow-up review" "$checklist"
        assert_not_contains "Carry-over excludes the non-deferred item" "confirmed working" "$checklist"

        # verifies: must be preserved on the carry-over task.
        local carry_verifies
        carry_verifies=$(grep '^verifies:' "$carryover_file" || true)
        assert_contains "Carry-over preserves verifies list" "t571_4" "$carry_verifies"
        assert_contains "Carry-over preserves all verifies entries" "t571_5" "$carry_verifies"
    fi

    teardown
}

# --- Test 7: child task gate fires on the child-archive path ---
test_child_task_gate() {
    echo ""
    echo "=== Test 7: gate fires for child manual_verification task ==="
    setup_archive_project false

    # Minimal parent, plus child with pending checklist.
    cat > aitasks/t106_parent.md <<'TASK'
---
priority: medium
effort: low
depends: []
issue_type: feature
status: Implementing
labels: []
children_to_implement: [t106_1]
created_at: 2026-04-19 10:00
updated_at: 2026-04-19 10:00
---

Parent.
TASK

    mkdir -p aitasks/t106
    write_mv_task aitasks/t106/t106_1_child_verify.md manual_verification "" \
        "- [ ] pending child item" \
        "- [x] terminal child item"

    git add -A && git commit -m "setup" --quiet

    local output rc
    set +e
    output=$(bash .aitask-scripts/aitask_archive.sh 106_1 2>&1)
    rc=$?
    set -e

    assert_eq "Child gate exits 2 when pending" "2" "$rc"
    assert_contains "Child gate emits PENDING" "PENDING:1" "$output"
    assert_contains "Child gate emits VERIFICATION_PENDING" "VERIFICATION_PENDING:" "$output"
    assert_file_exists "Child task still in aitasks/" "aitasks/t106/t106_1_child_verify.md"

    teardown
}

# --- Run ---
test_pending_blocks_archival
test_deferred_without_flag_blocks
test_all_terminal_archives_normally
test_non_manual_verification_is_noop
test_no_checklist_is_noop
test_deferred_with_flag_creates_carryover
test_child_task_gate

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
