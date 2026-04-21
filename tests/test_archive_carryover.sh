#!/usr/bin/env bash
# test_archive_carryover.sh - Regression test for the manual_verification
# carry-over archival path in aitask_archive.sh.
#
# Guards specifically against the bug fixed in commit b63a8502:
#   create_carryover_task() invoked aitask_create.sh --batch --commit --silent
#   without --desc / --desc-file, which the batch validator rejects, so the
#   archive aborted with "Carry-over task creation failed".
#
# The companion test tests/test_archive_verification_gate.sh covers the broad
# gate behaviour (pending/deferred/terminal/etc). This file only covers the
# narrow regression that would have caught the missing --desc.
#
# Run: bash tests/test_archive_carryover.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

# --- Test helpers (mirrors test_archive_verification_gate.sh) ---

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
    if echo "$actual" | grep -q -- "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got: $actual)"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -q -- "$unexpected"; then
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

# --- Strict stub aitask_create.sh ---
# Unlike the forgiving stub in test_archive_verification_gate.sh, this one
# EXITS 1 if --desc / --desc-file is absent. It also logs every received arg
# to $STUB_ARG_LOG so the test can introspect them after the fact.
STRICT_STUB_CONTENTS='#!/usr/bin/env bash
set -euo pipefail

: "${STUB_ARG_LOG:?STUB_ARG_LOG must be exported}"

# Persist the full argv for post-hoc introspection.
printf "%s\n" "$@" >> "$STUB_ARG_LOG"

NAME=""
DESC=""
DESC_FILE=""
VERIFIES=""
TYPE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --name) NAME="$2"; shift 2 ;;
        --desc) DESC="$2"; shift 2 ;;
        --desc-file) DESC_FILE="$2"; shift 2 ;;
        --verifies) VERIFIES="$2"; shift 2 ;;
        --type) TYPE="$2"; shift 2 ;;
        --batch|--commit|--silent) shift ;;
        --priority|--effort) shift 2 ;;
        *) shift ;;
    esac
done

[[ -z "$NAME" ]] && { echo "stub: --name required" >&2; exit 1; }

# The regression check: the real validator rejects --batch without --desc /
# --desc-file. The stub enforces the same contract so a caller that forgets
# --desc fails visibly instead of silently succeeding.
if [[ -z "$DESC" && -z "$DESC_FILE" ]]; then
    echo "stub: --desc or --desc-file required (regression: missing in caller)" >&2
    exit 1
fi

TASK_DIR="${TASK_DIR:-aitasks}"
mkdir -p "$TASK_DIR"

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
        formatted="[$(echo "$VERIFIES" | sed "s/,/, /g")]"
        echo "verifies: $formatted"
    fi
    echo "created_at: $TIMESTAMP"
    echo "updated_at: $TIMESTAMP"
    echo "---"
    echo
    # Echo --desc so tests can assert it was threaded through.
    if [[ -n "$DESC" ]]; then
        echo "$DESC"
    elif [[ -n "$DESC_FILE" ]]; then
        cat "$DESC_FILE"
    fi
} > "$FILE"

git add "$FILE" >/dev/null 2>&1 || true
git commit -m "ait: Add stub task t${NEXT}" --quiet >/dev/null 2>&1 || true

echo "$FILE"
'

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
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.py" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true

    printf '%s' "$STRICT_STUB_CONTENTS" > .aitask-scripts/aitask_create.sh

    chmod +x .aitask-scripts/*.sh .aitask-scripts/*.py 2>/dev/null || true

    printf 'bug\nchore\ndocumentation\nfeature\nperformance\nrefactor\nstyle\ntest\nmanual_verification\n' \
        > aitasks/metadata/task_types.txt

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    PROJECT_UNDER_TEST="$local_dir"
    STUB_ARG_LOG="$tmpdir/stub_args.log"
    export STUB_ARG_LOG
    : > "$STUB_ARG_LOG"
}

teardown() {
    unset STUB_ARG_LOG
    popd > /dev/null 2>&1 || true
}

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
        echo "created_at: 2026-04-21 10:00"
        echo "updated_at: 2026-04-21 10:00"
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

# --- Test 1: archive passes --desc to aitask_create.sh ---
# Regression for b63a8502: without --desc the strict stub exits 1 and the
# archive aborts with "Carry-over task creation failed".
test_archive_passes_desc_to_create() {
    echo "=== Test 1: --with-deferred-carryover passes --desc to aitask_create.sh ==="
    setup_archive_project

    write_mv_task aitasks/t200_verify.md manual_verification "" \
        "- [defer] deferred item preserved in carry-over" \
        "- [x] terminal item stays behind"

    git add -A && git commit -m "setup" --quiet

    local output rc
    set +e
    output=$(bash .aitask-scripts/aitask_archive.sh --with-deferred-carryover 200 2>&1)
    rc=$?
    set -e

    assert_eq "Archive exits 0 when --desc is supplied" "0" "$rc"
    assert_contains "CARRYOVER_CREATED emitted" "CARRYOVER_CREATED:" "$output"
    assert_contains "ARCHIVED_TASK emitted" "ARCHIVED_TASK:" "$output"
    assert_file_not_exists "Original task moved out of aitasks/" "aitasks/t200_verify.md"

    # The specific regression assertion: introspect the stub's arg log.
    local arg_log_contents
    arg_log_contents="$(cat "$STUB_ARG_LOG")"
    assert_contains "Stub received --desc flag" "^--desc$" "$arg_log_contents"

    # And the --desc value must be non-empty (the line after --desc).
    local desc_value
    desc_value="$(awk '/^--desc$/ {getline; print; exit}' "$STUB_ARG_LOG")"
    TOTAL=$((TOTAL + 1))
    if [[ -n "$desc_value" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: --desc value was empty in stub arg log"
    fi

    teardown
}

# --- Test 2: carry-over file contents are correctly seeded ---
# Covers the deferred-item preservation and terminal-item exclusion so we
# don't lose that property if test_archive_verification_gate.sh's Test 6 is
# ever refactored.
test_carryover_seeds_only_deferred() {
    echo ""
    echo "=== Test 2: carry-over file is seeded with deferred items only ==="
    setup_archive_project

    write_mv_task aitasks/t201_verify.md manual_verification "[t1, t2]" \
        "- [defer] still pending review" \
        "- [x] already confirmed working"

    git add -A && git commit -m "setup" --quiet

    local output rc
    set +e
    output=$(bash .aitask-scripts/aitask_archive.sh --with-deferred-carryover 201 2>&1)
    rc=$?
    set -e

    assert_eq "Archive exits 0" "0" "$rc"

    local carryover_file
    carryover_file="$(ls aitasks/t*_verify_deferred_carryover.md 2>/dev/null | head -1 || true)"

    TOTAL=$((TOTAL + 1))
    if [[ -z "$carryover_file" ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: carry-over task file not created"
    else
        PASS=$((PASS + 1))

        local checklist
        checklist="$(grep '^- \[' "$carryover_file" || true)"
        assert_contains "Carry-over has fresh [ ] item" "\[ \]" "$checklist"
        assert_contains "Deferred item text preserved" "still pending review" "$checklist"
        assert_not_contains "Terminal item excluded" "already confirmed working" "$checklist"

        local carry_verifies
        carry_verifies="$(grep '^verifies:' "$carryover_file" || true)"
        assert_contains "verifies list preserved (t1)" "t1" "$carry_verifies"
        assert_contains "verifies list preserved (t2)" "t2" "$carry_verifies"
    fi

    teardown
}

# --- Run ---
test_archive_passes_desc_to_create
test_carryover_seeds_only_deferred

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
