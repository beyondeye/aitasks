#!/usr/bin/env bash
# test_archive_shadow_prune.sh - Archive-time pruning of the shadow
# concern-rejection store (t1427_1).
#
# aitask_archive.sh calls prune_shadow_rejections() at THREE distinct sites:
# plain parent archival, child archival, and the automatic parent archival that
# fires when the last child completes. The call is best-effort
# (`>/dev/null 2>&1 || true`), so a hook missing from one site — or passing the
# wrong id — is completely invisible to every other archive suite: they would
# stay green either way. Hence per-site coverage, one case each.
#
# Every case seeds BOTH the store for the id under archival and a decoy store
# for an unrelated id, so a hook wired to the wrong id fails rather than passes.
#
# The stores are seeded under the fake repo's own `.aitask-shadow/` — no
# AITASK_SHADOW_DIR override — so the default repo-root-relative path resolution
# is exercised exactly as it runs in production.
#
# Run: bash tests/test_archive_shadow_prune.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

# --- Setup a test project wired for archival + shadow pruning ---
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

    cp "$PROJECT_DIR/.aitask-scripts/aitask_archive.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/

    # The subject under test, plus the one lib the scaffold does not already
    # provide (it ships terminal_compat.sh and atomic_write.sh).
    cp "$PROJECT_DIR/.aitask-scripts/aitask_shadow_rejected.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/registry_lock.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/*.sh

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\n' \
        > aitasks/metadata/task_types.txt

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    # FIXTURE PRE-CHECK. The prune call is `|| true`, so a helper that failed to
    # copy would make every assertion below vacuously "pass" the wrong way. Fail
    # loudly here instead.
    assert_file_exists "fixture: helper copied into the fake repo" \
        ".aitask-scripts/aitask_shadow_rejected.sh"
    assert_eq "fixture: helper is executable and runnable" "PRUNED:absent" \
        "$(bash .aitask-scripts/aitask_shadow_rejected.sh prune 999999 2>&1)"
}

teardown() {
    popd > /dev/null 2>&1 || true
}

final_cleanup() {
    local d
    for d in "${CLEANUP_DIRS[@]:-}"; do
        [[ -n "$d" ]] && rm -rf "$d"
    done
}
trap final_cleanup EXIT

# Seed a rejection store for <id> via the real helper.
seed_store() {
    printf '%s\n' "- [high | seeded] rejection for t$1." \
        | bash .aitask-scripts/aitask_shadow_rejected.sh add "$1" --producer test >/dev/null
}

write_parent() {   # <num> <children_csv>
    cat > "aitasks/t$1_parent_task.md" << TASK
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
children_to_implement: [$2]
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Parent task t$1
TASK
}

write_child() {   # <parent> <child>
    mkdir -p "aitasks/t$1"
    cat > "aitasks/t$1/t$1_$2_child_task.md" << TASK
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Child task t$1_$2
TASK
}

write_standalone() {   # <num>
    cat > "aitasks/t$1_standalone_task.md" << TASK
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Standalone task t$1
TASK
}

# --- Case 1: plain parent archival prunes the parent's store ---
test_parent_archival() {
    echo "=== Case 1: parent archival prunes .aitask-shadow/<parent>/ ==="
    setup_archive_project

    write_standalone 30
    git add -A && git commit -m "Setup case 1" --quiet

    seed_store 30
    seed_store 41   # decoy: an unrelated task's store must survive
    assert_dir_exists "seeded parent store" ".aitask-shadow/30"
    assert_dir_exists "seeded decoy store" ".aitask-shadow/41"

    local output
    output=$(bash .aitask-scripts/aitask_archive.sh 30 2>&1)
    assert_contains "task was archived" "ARCHIVED_TASK:" "$output"

    assert_dir_not_exists "parent store pruned" ".aitask-shadow/30"
    assert_dir_exists "unrelated store untouched" ".aitask-shadow/41"

    teardown
}

# --- Case 2: child archival prunes the CHILD store, not the parent's ---
test_child_archival() {
    echo "=== Case 2: child archival prunes the child store only ==="
    setup_archive_project

    # Two children, so archiving one does NOT auto-archive the parent.
    write_parent 10 "t10_1, t10_2"
    write_child 10 1
    write_child 10 2
    git add -A && git commit -m "Setup case 2" --quiet

    seed_store 10_1
    seed_store 10     # the parent's own store — it is NOT archiving yet
    seed_store 41     # decoy
    assert_dir_exists "seeded child store" ".aitask-shadow/10_1"

    local output
    output=$(bash .aitask-scripts/aitask_archive.sh 10_1 2>&1)
    assert_contains "child was archived" "ARCHIVED_TASK:" "$output"
    assert_not_contains "parent did NOT auto-archive" "PARENT_ARCHIVED:" "$output"

    assert_dir_not_exists "child store pruned" ".aitask-shadow/10_1"
    # This is what distinguishes a hook wired only at the parent site, and a
    # hook that passes the parent number where the child id belongs.
    assert_dir_exists "parent store survives while the parent is still active" \
        ".aitask-shadow/10"
    assert_dir_exists "unrelated store untouched" ".aitask-shadow/41"

    teardown
}

# --- Case 3: last child triggers auto-parent archival; BOTH stores pruned ---
test_auto_parent_archival() {
    echo "=== Case 3: final child auto-archives the parent; both stores pruned ==="
    setup_archive_project

    write_parent 20 "t20_1"
    write_child 20 1
    git add -A && git commit -m "Setup case 3" --quiet

    seed_store 20_1
    seed_store 20
    seed_store 41   # decoy

    local output
    output=$(bash .aitask-scripts/aitask_archive.sh 20_1 2>&1)
    assert_contains "parent auto-archived after final child" "PARENT_ARCHIVED:" "$output"

    assert_dir_not_exists "child store pruned" ".aitask-shadow/20_1"
    # The third call site: without it the parent's store outlives the parent.
    assert_dir_not_exists "auto-archived parent store pruned" ".aitask-shadow/20"
    assert_dir_exists "unrelated store untouched" ".aitask-shadow/41"

    teardown
}

# --- Case 4: --dry-run prunes nothing ---
test_dry_run_preserves_store() {
    echo "=== Case 4: --dry-run leaves the store intact ==="
    setup_archive_project

    write_standalone 30
    git add -A && git commit -m "Setup case 4" --quiet

    seed_store 30
    local before
    before="$(cat .aitask-shadow/30/rejected.md)"

    local output
    output=$(bash .aitask-scripts/aitask_archive.sh --dry-run 30 2>&1)
    assert_contains "dry-run announces the prune it would do" \
        "[dry-run] Would prune shadow rejection store for t30" "$output"

    assert_dir_exists "dry-run left the store dir" ".aitask-shadow/30"
    assert_eq "dry-run left the store contents byte-identical" \
        "$before" "$(cat .aitask-shadow/30/rejected.md)"

    teardown
}

test_parent_archival
echo
test_child_archival
echo
test_auto_parent_archival
echo
test_dry_run_preserves_store

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
