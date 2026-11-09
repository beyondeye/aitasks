#!/usr/bin/env bash
# test_archive_obsolete.sh - aitask_archive.sh --obsolete and the `landed` trigger (t1981_6).
#
# The decision matrix runs against a recording stub in place of
# aitask_relations_enqueue.sh, so every case asserts exactly which ids the archive
# fired for: completed work only (never --superseded / --obsolete / --dry-run),
# a parent the child flow auto-archives included, and a failing helper never
# failing the archive. One end-to-end case runs the real helper and worker and
# waits (bounded) for its enqueue.log line.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()
CALLS=""

setup_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")
    git init --bare --quiet "$tmpdir/remote.git"
    git clone --quiet "$tmpdir/remote.git" "$tmpdir/local" 2>/dev/null
    pushd "$tmpdir/local" > /dev/null || exit 1
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
    CALLS="$tmpdir/enqueue_calls"
    : > "$CALLS"
    cat > .aitask-scripts/aitask_relations_enqueue.sh <<EOF
#!/usr/bin/env bash
echo "\$*" >> "$CALLS"
echo "stub stdout that must never reach the caller"
exit \${STUB_RC:-0}
EOF
    chmod +x .aitask-scripts/*.sh
    printf 'bug\nchore\nfeature\n' > aitasks/metadata/task_types.txt
    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true
}

teardown() {
    popd > /dev/null 2>&1 || true
}

task() {  # task <path> <status> [extra frontmatter line]
    mkdir -p "$(dirname "$1")"
    {
        echo "---"
        echo "priority: medium"
        echo "effort: low"
        echo "issue_type: feature"
        echo "status: $2"
        [[ -n "${3:-}" ]] && echo "$3"
        echo "created_at: 2026-01-01 10:00"
        echo "updated_at: 2026-01-01 10:00"
        echo "---"
        echo ""
        echo "Body of $1"
    } > "$1"
}

commit_all() {
    git add -A
    git commit -m "tasks" --quiet
}

test_completed_archive_fires() {
    echo "=== completed archive fires obsolescence landed ==="
    setup_project
    task aitasks/t30_done.md Implementing
    commit_all
    local out rc=0
    out=$(./.aitask-scripts/aitask_archive.sh 30 2>&1) || rc=$?
    assert_eq "archive exit 0" "0" "$rc"
    assert_eq "fired once for t30" "obsolescence landed 30" "$(cat "$CALLS")"
    assert_not_contains "helper stdout never reaches the caller" "stub stdout" "$out"
    teardown
}

test_superseded_and_obsolete_fire_nothing() {
    echo "=== --superseded / --obsolete fire nothing and write the reason ==="
    setup_project
    task aitasks/t31_sup.md Ready
    task aitasks/t32_obs.md Ready
    commit_all
    ./.aitask-scripts/aitask_archive.sh --superseded 31 > /dev/null 2>&1
    ./.aitask-scripts/aitask_archive.sh --obsolete 32 > /dev/null 2>&1
    assert_eq "no landed call" "" "$(cat "$CALLS")"
    assert_contains "superseded reason" "archived_reason: superseded" "$(cat aitasks/archived/t31_sup.md)"
    assert_contains "obsolete reason" "archived_reason: obsolete" "$(cat aitasks/archived/t32_obs.md)"
    assert_contains "status line kept above the reason" $'status: Done\narchived_reason: obsolete' \
        "$(cat aitasks/archived/t32_obs.md)"
    teardown
}

test_flags_are_exclusive() {
    echo "=== --superseded and --obsolete are mutually exclusive ==="
    setup_project
    task aitasks/t33_x.md Ready
    commit_all
    local out rc=0
    out=$(./.aitask-scripts/aitask_archive.sh --superseded --obsolete 33 2>&1) || rc=$?
    assert_eq "refused" "1" "$rc"
    assert_contains "says why" "mutually exclusive" "$out"
    assert_eq "task untouched" "1" "$(ls aitasks/t33_x.md 2>/dev/null | wc -l | tr -d ' ')"
    teardown
}

test_dry_run_fires_nothing() {
    echo "=== --dry-run fires nothing ==="
    setup_project
    task aitasks/t34_dry.md Implementing
    commit_all
    ./.aitask-scripts/aitask_archive.sh --dry-run 34 > /dev/null 2>&1
    assert_eq "no landed call" "" "$(cat "$CALLS")"
    teardown
}

test_child_flow_fires_for_child_and_parent() {
    echo "=== child archive that auto-archives its parent fires for both ==="
    setup_project
    task aitasks/t40_parent.md Implementing "children_to_implement: [t40_1]"
    task aitasks/t40/t40_1_child.md Implementing
    commit_all
    local rc=0
    ./.aitask-scripts/aitask_archive.sh 40_1 > /dev/null 2>&1 || rc=$?
    assert_eq "archive exit 0" "0" "$rc"
    assert_eq "child then parent" $'obsolescence landed 40_1\nobsolescence landed 40' "$(cat "$CALLS")"
    teardown
}

test_child_without_parent_archive() {
    echo "=== child archive with siblings left fires for the child only, exit 0 ==="
    setup_project
    task aitasks/t41_parent.md Implementing "children_to_implement: [t41_1, t41_2]"
    task aitasks/t41/t41_1_a.md Implementing
    task aitasks/t41/t41_2_b.md Ready
    commit_all
    local rc=0
    ./.aitask-scripts/aitask_archive.sh 41_1 > /dev/null 2>&1 || rc=$?
    assert_eq "archive exit 0 (no errexit leak from the parent branch)" "0" "$rc"
    assert_eq "child only" "obsolescence landed 41_1" "$(cat "$CALLS")"
    teardown
}

test_no_commit_fires_nothing() {
    echo "=== --no-commit (stage only) fires nothing, parent and child ==="
    setup_project
    task aitasks/t37_stage.md Implementing
    task aitasks/t42_parent.md Implementing "children_to_implement: [t42_1]"
    task aitasks/t42/t42_1_child.md Implementing
    commit_all
    local head rc=0
    head=$(git rev-parse HEAD)
    ./.aitask-scripts/aitask_archive.sh --no-commit 37 > /dev/null 2>&1 || rc=$?
    assert_eq "parent stage-only exit 0" "0" "$rc"
    ./.aitask-scripts/aitask_archive.sh --no-commit 42_1 > /dev/null 2>&1 || rc=$?
    assert_eq "child stage-only exit 0" "0" "$rc"
    assert_eq "HEAD unchanged" "$head" "$(git rev-parse HEAD)"
    assert_eq "no landed call" "" "$(cat "$CALLS")"
    teardown
}

test_failing_helper_never_fails_the_archive() {
    echo "=== a failing helper never fails the archive ==="
    setup_project
    task aitasks/t35_ok.md Implementing
    commit_all
    local out rc=0
    out=$(STUB_RC=1 ./.aitask-scripts/aitask_archive.sh 35 2>&1) || rc=$?
    assert_eq "archive exit 0" "0" "$rc"
    assert_contains "archived" "ARCHIVED_TASK:" "$out"
    assert_eq "the helper was called" "obsolescence landed 35" "$(cat "$CALLS")"
    teardown
}

test_real_helper_end_to_end() {
    echo "=== real helper + worker: SKIPPED:disabled lands in enqueue.log ==="
    setup_project
    cp "$PROJECT_DIR/.aitask-scripts/aitask_relations_enqueue.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/"*.py .aitask-scripts/lib/
    task aitasks/t36_real.md Implementing
    commit_all
    local rc=0
    ./.aitask-scripts/aitask_archive.sh 36 > /dev/null 2>&1 || rc=$?
    assert_eq "archive exit 0" "0" "$rc"
    local log
    log="$(git rev-parse --path-format=absolute --git-common-dir)/aitask-relations/spool/enqueue.log"
    local _
    for _ in $(seq 1 150); do
        grep -q 'ENQUEUE:obsolescence|landed|t36|SKIPPED:disabled' "$log" 2>/dev/null && break
        sleep 0.1
    done
    assert_contains "detached part logged the skip" "ENQUEUE:obsolescence|landed|t36|SKIPPED:disabled" \
        "$(cat "$log" 2>/dev/null)"
    teardown
}

test_completed_archive_fires
test_superseded_and_obsolete_fire_nothing
test_flags_are_exclusive
test_dry_run_fires_nothing
test_child_flow_fires_for_child_and_parent
test_child_without_parent_archive
test_no_commit_fires_nothing
test_failing_helper_never_fails_the_archive
test_real_helper_end_to_end

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
