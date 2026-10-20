#!/usr/bin/env bash
# test_archive_scratchpad_prune.sh - Archive-time pruning of the scratchpad
# notes store (t2073_1).
#
# aitask_archive.sh calls prune_scratchpad() at FOUR distinct sites: plain parent
# archival, child archival, the automatic parent archival that fires when the
# last child completes, and handle_folded_tasks (a folded task's file is deleted
# when its primary archives). The call is best-effort (`>/dev/null 2>&1 ||
# true`), so a hook missing from one site — or passing the wrong id — is
# invisible to every other archive suite. Hence per-site coverage, one case each.
#
# Every case seeds BOTH the store for the id under archival and a decoy store
# for an unrelated id, so a hook wired to the wrong id fails rather than passes.
# Stores are seeded through the real helper (`open` + `save`) under the fake
# repo's own `.aitask-scratchpad/` — no AITASK_SCRATCHPAD_DIR override — so the
# default repo-root-relative resolution runs exactly as in production.
#
# The last case pins the cost of a contended store: archival still completes and
# commits within the helper's lock-wait budget, leaving the store for a later
# prune.
#
# Run: bash tests/test_archive_scratchpad_prune.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

unset AITASK_SCRATCHPAD_DIR AITASK_SCRATCHPAD_PAUSE_FIFO TASK_DIR

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()
HOLDER_PID=""

STORE=.aitask-scratchpad

# --- Setup a test project wired for archival + scratchpad pruning ---
setup_archive_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")

    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"

    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir" 2>/dev/null

    pushd "$local_dir" > /dev/null || exit 1
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

    # The subject under test. The scaffold already ships every lib it sources
    # (terminal_compat.sh, registry_lock.sh + stale_lock.sh, atomic_write.sh).
    cp "$PROJECT_DIR/.aitask-scripts/aitask_scratchpad_store.sh" .aitask-scripts/
    chmod +x .aitask-scripts/*.sh

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\n' \
        > aitasks/metadata/task_types.txt

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    # FIXTURE PRE-CHECK. The prune call is `|| true`, so a helper that failed to
    # copy would make every "pruned" assertion below pass for the wrong reason.
    assert_file_exists "fixture: helper copied into the fake repo" \
        ".aitask-scripts/aitask_scratchpad_store.sh"
    assert_eq "fixture: helper is executable and runnable" "PRUNED:absent" \
        "$(bash .aitask-scripts/aitask_scratchpad_store.sh prune 999999 2>&1)"
}

teardown() {
    popd > /dev/null 2>&1 || true
}

final_cleanup() {
    local d
    [[ -n "$HOLDER_PID" ]] && kill "$HOLDER_PID" 2>/dev/null
    for d in "${CLEANUP_DIRS[@]:-}"; do
        [[ -n "$d" ]] && rm -rf "$d"
    done
}
trap final_cleanup EXIT

# Seed a notes store for <id> via the real helper (the task must be active).
seed_store() {
    bash .aitask-scripts/aitask_scratchpad_store.sh open "$1" >/dev/null
    printf 'notes for t%s\n' "$1" \
        | bash .aitask-scripts/aitask_scratchpad_store.sh save "$1" >/dev/null
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

write_standalone() {   # <num> [folded_csv]
    local folded=""
    [[ -n "${2:-}" ]] && folded="folded_tasks: [$2]"
    cat > "aitasks/t$1_standalone_task.md" << TASK
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: []
$folded
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Standalone task t$1
TASK
}

write_folded() {   # <num> <folded_into>
    cat > "aitasks/t$1_folded_task.md" << TASK
---
priority: medium
effort: low
depends: []
issue_type: feature
status: Folded
labels: []
folded_into: $2
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

This task was folded into t$2
TASK
}

# The decoy: an active, never-archived task with its own store.
seed_decoy() {
    write_standalone 41
    git add -A && git commit -m "decoy" --quiet
    seed_store 41
}

# --- Case 1: plain parent archival prunes the parent's store ---
test_parent_archival() {
    echo "=== Case 1: parent archival prunes $STORE/<parent>/ ==="
    setup_archive_project
    seed_decoy

    write_standalone 30
    git add -A && git commit -m "Setup case 1" --quiet
    seed_store 30
    assert_file_exists "seeded parent notes" "$STORE/30/notes.md"

    local output
    output=$(bash .aitask-scripts/aitask_archive.sh 30 2>&1)
    assert_contains "task was archived" "ARCHIVED_TASK:" "$output"

    assert_dir_not_exists "parent store pruned" "$STORE/30"
    assert_file_exists "unrelated store untouched" "$STORE/41/notes.md"

    teardown
}

# --- Case 2: child archival prunes the CHILD store, not the parent's ---
test_child_archival() {
    echo "=== Case 2: child archival prunes the child store only ==="
    setup_archive_project
    seed_decoy

    # Two children, so archiving one does NOT auto-archive the parent.
    write_parent 10 "t10_1, t10_2"
    write_child 10 1
    write_child 10 2
    git add -A && git commit -m "Setup case 2" --quiet
    seed_store 10_1
    seed_store 10

    local output
    output=$(bash .aitask-scripts/aitask_archive.sh 10_1 2>&1)
    assert_contains "child was archived" "ARCHIVED_TASK:" "$output"
    assert_not_contains "parent did NOT auto-archive" "PARENT_ARCHIVED:" "$output"

    assert_dir_not_exists "child store pruned" "$STORE/10_1"
    assert_dir_exists "parent store survives while the parent is still active" "$STORE/10"
    assert_file_exists "unrelated store untouched" "$STORE/41/notes.md"

    teardown
}

# --- Case 3: last child triggers auto-parent archival; BOTH stores pruned ---
test_auto_parent_archival() {
    echo "=== Case 3: final child auto-archives the parent; both stores pruned ==="
    setup_archive_project
    seed_decoy

    write_parent 20 "t20_1"
    write_child 20 1
    git add -A && git commit -m "Setup case 3" --quiet
    seed_store 20_1
    seed_store 20

    local output
    output=$(bash .aitask-scripts/aitask_archive.sh 20_1 2>&1)
    assert_contains "parent auto-archived after final child" "PARENT_ARCHIVED:" "$output"

    assert_dir_not_exists "child store pruned" "$STORE/20_1"
    assert_dir_not_exists "auto-archived parent store pruned" "$STORE/20"
    assert_file_exists "unrelated store untouched" "$STORE/41/notes.md"

    teardown
}

# --- Case 4: a folded task's store goes with its deleted task file ---
test_folded_archival() {
    echo "=== Case 4: archiving the primary prunes the folded task's store ==="
    setup_archive_project
    seed_decoy

    write_standalone 50 "51"
    write_folded 51 50
    git add -A && git commit -m "Setup case 4" --quiet
    seed_store 50
    seed_store 51

    local output
    output=$(bash .aitask-scripts/aitask_archive.sh 50 2>&1)
    assert_contains "folded task deleted" "FOLDED_DELETED:51:" "$output"

    assert_dir_not_exists "primary store pruned" "$STORE/50"
    assert_dir_not_exists "folded task store pruned" "$STORE/51"
    assert_file_exists "unrelated store untouched" "$STORE/41/notes.md"

    teardown
}

# --- Case 5: --dry-run prunes nothing, at the parent and folded sites ---
test_dry_run_preserves_store() {
    echo "=== Case 5: --dry-run leaves the stores intact ==="
    setup_archive_project

    write_standalone 30 "31"
    write_folded 31 30
    git add -A && git commit -m "Setup case 5" --quiet
    seed_store 30
    seed_store 31
    local before
    before="$(cat "$STORE/30/notes.md" "$STORE/31/notes.md")"

    local output
    output=$(bash .aitask-scripts/aitask_archive.sh --dry-run 30 2>&1)
    assert_contains "dry-run announces the parent prune" \
        "[dry-run] Would prune scratchpad for t30" "$output"
    assert_contains "dry-run announces the folded prune" \
        "[dry-run] Would prune scratchpad for t31" "$output"

    assert_dir_exists "dry-run left the parent store" "$STORE/30"
    assert_dir_exists "dry-run left the folded store" "$STORE/31"
    assert_eq "dry-run left the store contents byte-identical" \
        "$before" "$(cat "$STORE/30/notes.md" "$STORE/31/notes.md")"

    teardown
}

# --- Case 6 (archive_stall_bound): a held store lock delays archival boundedly ---
test_contended_store_bounded() {
    echo "=== Case 6: a held scratchpad lock leaves archival complete and the store in place ==="
    setup_archive_project

    write_standalone 60
    git add -A && git commit -m "Setup case 6" --quiet
    seed_store 60

    # A LIVE holder: registry_lock.sh never steals from a running pid.
    local lockd="$STORE/.locks/60.lockd"
    mkdir -p "$lockd"
    sleep 60 &
    HOLDER_PID=$!
    echo "$HOLDER_PID" > "$lockd/pid"
    echo "held-by-test" > "$lockd/owner"

    local output rc=0 start elapsed
    start=$(date +%s)
    output=$(bash .aitask-scripts/aitask_archive.sh 60 2>&1) || rc=$?
    elapsed=$(( $(date +%s) - start ))
    assert_eq "archival exits 0 despite the contended store" "0" "$rc"
    assert_contains "task was archived" "ARCHIVED_TASK:" "$output"
    assert_file_exists "task file moved to archived/" "aitasks/archived/t60_standalone_task.md"
    assert_contains "archival commit names the archived task" \
        "aitasks/archived/t60_standalone_task.md" "$(git log -1 --name-only --format='')"
    # 5 s lock-wait budget + 5 s slack for the rest of archival.
    if (( elapsed <= 10 )); then bounded=yes; else bounded="no (${elapsed}s)"; fi
    assert_eq "archival returned within the lock-wait budget plus slack" "yes" "$bounded"
    assert_file_exists "contended store left in place" "$STORE/60/notes.md"

    kill "$HOLDER_PID" 2>/dev/null || true
    wait "$HOLDER_PID" 2>/dev/null || true
    HOLDER_PID=""
    rm -rf "$lockd"
    assert_eq "a later prune finishes the job" "PRUNED:60" \
        "$(bash .aitask-scripts/aitask_scratchpad_store.sh prune 60 2>&1)"
    assert_dir_not_exists "store gone after the later prune" "$STORE/60"

    teardown
}

test_parent_archival
echo
test_child_archival
echo
test_auto_parent_archival
echo
test_folded_archival
echo
test_dry_run_preserves_store
echo
test_contended_store_bounded

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
