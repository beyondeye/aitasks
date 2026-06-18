#!/usr/bin/env bash
# test_archive_carryover_anchor.sh - Verifies that the deferred-carryover task
# created during archival is anchored to the original task's topic (t1016_3).
#
# create_carryover_task() (aitask_archive.sh) now passes
# --followup-of "$orig_id" to aitask_create.sh, so the carry-over manual-
# verification task joins the original task's anchor topic. The original is still
# ACTIVE when the carry-over is created (verification_gate_and_carryover runs
# before the archive move), so --followup-of resolves via task-status.
#
# Unlike tests/test_archive_carryover.sh (which stubs aitask_create.sh to assert
# --desc threading), this test uses the REAL aitask_create.sh so it can assert
# the actual `anchor:` frontmatter line on the created carry-over file.
#
# Run: bash tests/test_archive_carryover_anchor.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

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

    mkdir -p aitasks/archived aitasks/metadata aiplans/archived
    setup_fake_aitask_repo "$PWD"

    # SUT + the real create chain (create --commit calls claim_id + fold_mark
    # transitively; --followup-of validation shells to aitask_query_files.sh).
    cp "$PROJECT_DIR/.aitask-scripts/aitask_archive.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.py" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/

    chmod +x .aitask-scripts/*.sh .aitask-scripts/*.py 2>/dev/null || true

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\nmanual_verification\n' \
        > aitasks/metadata/task_types.txt
    : > aitasks/metadata/labels.txt

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    # Atomic id counter branch so aitask_create.sh --commit can allocate an id.
    ./.aitask-scripts/aitask_claim_id.sh --init > /dev/null 2>&1
}

teardown() {
    popd > /dev/null 2>&1 || true
}

write_mv_task() {
    local path="$1"; shift
    {
        echo "---"
        echo "priority: medium"
        echo "effort: low"
        echo "depends: []"
        echo "issue_type: manual_verification"
        echo "status: Implementing"
        echo "labels: []"
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

# --- Test: carry-over task is anchored to the original task's topic root ---
test_carryover_anchored_to_origin() {
    echo "=== Test: --with-deferred-carryover anchors the carry-over to the original ==="
    setup_archive_project

    # t200 is a topic root (no anchor of its own) → carry-over anchor == 200.
    write_mv_task aitasks/t200_verify.md \
        "- [defer] deferred item preserved in carry-over" \
        "- [x] terminal item stays behind"
    git add -A && git commit -m "setup" --quiet

    local output rc
    set +e
    output=$(bash .aitask-scripts/aitask_archive.sh --with-deferred-carryover 200 2>&1)
    rc=$?
    set -e

    assert_eq_trim "Archive exits 0" "0" "$rc"
    assert_contains "CARRYOVER_CREATED emitted" "CARRYOVER_CREATED:" "$output"

    local carryover_file
    carryover_file="$(ls aitasks/t*_verify_carryover.md 2>/dev/null | head -1 || true)"

    TOTAL=$((TOTAL + 1))
    if [[ -z "$carryover_file" ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: carry-over task file not created"
        echo "  out: $output"
    else
        PASS=$((PASS + 1))
        local fm
        fm="$(cat "$carryover_file")"
        assert_contains "carry-over anchored to original topic root" "anchor: 200" "$fm"
    fi

    teardown
}

# --- Run ---
test_carryover_anchored_to_origin

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
