#!/usr/bin/env bash
# test_verification_followup_anchor.sh - Verifies the best-effort topic anchor
# threaded into aitask_verification_followup.sh (t1016_3).
#
# The bug task created from a failed manual-verification item now joins its
# origin feature task's anchor topic via --followup-of — but only when the
# origin actually resolves (active / archived / tar-bundled). The flag is
# guarded so a commit-only / unresolvable origin (the existing-test fixture
# shape) leaves the bug task a topic root, preserving the tolerant contract.
#
#   (a) resolvable origin (real task file) -> bug has `anchor: <origin>` AND
#       still `depends: [origin]`.
#   (b) commit-only / unresolvable origin  -> bug has NO `anchor:` line, still
#       `depends:` (guard fail-safe).
#
# Run: bash tests/test_verification_followup_anchor.sh

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

    mkdir -p aitasks/metadata aiplans/archived
    setup_fake_aitask_repo "$PWD"

    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_followup.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.py" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh" .aitask-scripts/
    # aitask_query_files.sh is REQUIRED by the new best-effort anchor guard
    # (and by aitask_create.sh --followup-of validation).
    cp "$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh" .aitask-scripts/
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

    ./.aitask-scripts/aitask_claim_id.sh --init > /dev/null 2>&1
}

teardown() {
    popd > /dev/null 2>&1 || true
}

# seed_origin_commit <id> - commit a dummy source file with the "(tN)" suffix
# (NO task file -> origin is commit-only / unresolvable).
seed_origin_commit() {
    local origin="$1"
    mkdir -p src
    printf 'placeholder for t%s\n' "$origin" > "src/origin_${origin}.py"
    git add "src/origin_${origin}.py" > /dev/null
    git commit -m "feature: seed origin (t${origin})" --quiet > /dev/null
}

# write_origin_task <id> - create a REAL, resolvable origin task file (a topic
# root: no anchor of its own).
write_origin_task() {
    local origin="$1"
    {
        echo "---"
        echo "priority: medium"
        echo "effort: medium"
        echo "depends: []"
        echo "issue_type: feature"
        echo "status: Done"
        echo "labels: []"
        echo "created_at: 2026-01-01 10:00"
        echo "updated_at: 2026-01-01 10:00"
        echo "---"
        echo
        echo "Origin feature."
    } > "aitasks/t${origin}_origin.md"
}

write_mv_task() {
    local path="$1" verifies_literal="$2"
    mkdir -p "$(dirname "$path")"
    {
        echo "---"
        echo "priority: medium"
        echo "effort: low"
        echo "depends: []"
        echo "issue_type: manual_verification"
        echo "status: Ready"
        echo "labels: []"
        echo "verifies: ${verifies_literal}"
        echo "created_at: 2026-01-01 10:00"
        echo "updated_at: 2026-01-01 10:00"
        echo "---"
        echo
        echo "## Verification Checklist"
        echo
        echo "- [ ] Button opens the modal cleanly"
    } > "$path"
}

followup_path_from_output() {
    echo "$1" | sed -n 's/^FOLLOWUP_CREATED:[^:]*:\(.*\)$/\1/p' | tail -1
}

# --- Test (a): resolvable origin -> bug task is anchored to it ---
test_resolvable_origin_anchors() {
    echo "=== Test (a): resolvable origin -> bug task anchored to origin ==="
    setup_project

    seed_origin_commit 42
    write_origin_task 42          # real, resolvable origin task (topic root)
    write_mv_task aitasks/t99_manual.md "[42]"
    git add -A && git commit -m "seed origin task + mv task" --quiet

    local out rc
    out=$(bash .aitask-scripts/aitask_verification_followup.sh --from 99 --item 1 2>&1) && rc=0 || rc=$?
    assert_eq "exit 0" "0" "$rc"
    assert_contains "FOLLOWUP_CREATED emitted" "FOLLOWUP_CREATED:" "$out"

    local new_path
    new_path=$(followup_path_from_output "$out")
    TOTAL=$((TOTAL + 1))
    if [[ -z "$new_path" || ! -f "$new_path" ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: bug task path not resolvable or file missing"
        echo "  out: $out"
    else
        PASS=$((PASS + 1))
        local body
        body=$(cat "$new_path")
        assert_contains "bug task anchored to origin topic root" "anchor: 42" "$body"
        assert_contains "bug task still depends on origin" "depends: [42]" "$body"
    fi

    teardown
}

# --- Test (b): commit-only origin -> guard skips anchor (still depends) ---
test_unresolvable_origin_no_anchor() {
    echo ""
    echo "=== Test (b): commit-only origin -> bug task has NO anchor (guard fail-safe) ==="
    setup_project

    seed_origin_commit 77        # commit only, NO task file -> unresolvable
    write_mv_task aitasks/t99_manual.md "[77]"
    git add -A && git commit -m "seed mv task" --quiet

    local out rc
    out=$(bash .aitask-scripts/aitask_verification_followup.sh --from 99 --item 1 2>&1) && rc=0 || rc=$?
    assert_eq "exit 0 (creation still succeeds)" "0" "$rc"
    assert_contains "FOLLOWUP_CREATED emitted" "FOLLOWUP_CREATED:" "$out"

    local new_path
    new_path=$(followup_path_from_output "$out")
    TOTAL=$((TOTAL + 1))
    if [[ -z "$new_path" || ! -f "$new_path" ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: bug task path not resolvable or file missing"
        echo "  out: $out"
    else
        PASS=$((PASS + 1))
        local body
        body=$(cat "$new_path")
        assert_not_contains "no anchor line for unresolvable origin" "anchor:" "$body"
        assert_contains "bug task still depends on origin" "depends: [77]" "$body"
    fi

    teardown
}

# --- Run ---
test_resolvable_origin_anchors
test_unresolvable_origin_no_anchor

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
