#!/usr/bin/env bash
# test_archive_obsolete.sh - aitask_archive.sh --obsolete and the `landed` trigger (t1981_6).
#
# The decision matrix runs against a recording stub in place of
# aitask_relations_enqueue.sh, so every case asserts exactly which ids the archive
# fired for: completed work only (never --superseded / --obsolete / --dry-run),
# a parent the child flow auto-archives included, and a failing helper never
# failing the archive. One end-to-end case runs the real helper and worker and
# waits (bounded) for its enqueue.log line.
#
# t2254: the run's reason goes on the flagged child only. The parent the child
# flow auto-archives is completed work (and fires) when any child landed -- a
# loose or a bundled record, both READ -- and takes the reason only when every
# record was read and none landed; an unreadable record leaves that unproven.
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

archived_record() {  # archived_record <path> [archived_reason] -- an archived child (status Done)
    mkdir -p "$(dirname "$1")"
    {
        echo "---"
        echo "priority: medium"
        echo "effort: low"
        echo "issue_type: feature"
        echo "status: Done"
        [[ -n "${2:-}" ]] && echo "archived_reason: $2"
        echo "created_at: 2026-01-01 10:00"
        echo "updated_at: 2026-01-01 10:00"
        echo "completed_at: 2026-01-01 10:00"
        echo "---"
        echo ""
        echo "Archived $1"
    } > "$1"
}

# bundle <archive> <parent> <n>[:<reason>]... -- a bundle with the member shape
# aitask_zip_old.sh writes (`tar -C <stage> .` -> ./t<P>/t<P>_<n>_*.md), holding
# archived child records; .tar.zst through zstd, anything else as .tar.gz.
bundle() {
    local archive="$1" parent="$2" spec n reason stage
    shift 2
    stage="$(mktemp -d)"
    CLEANUP_DIRS+=("$stage")
    for spec in "$@"; do
        n="${spec%%:*}"
        reason=""
        if [[ "$spec" == *:* ]]; then
            reason="${spec#*:}"
        fi
        archived_record "$stage/t${parent}/t${parent}_${n}_bundled.md" "$reason"
    done
    mkdir -p "$(dirname "$archive")"
    case "$archive" in
        *.tar.zst) tar -cf - -C "$stage" . | zstd -q -o "$archive" ;;
        *)         tar -czf "$archive" -C "$stage" . ;;
    esac
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
    task aitasks/t38_dryobs.md Ready
    commit_all
    ./.aitask-scripts/aitask_archive.sh --dry-run 34 > /dev/null 2>&1
    local out
    out=$(./.aitask-scripts/aitask_archive.sh --dry-run --obsolete 38 2>&1)
    assert_eq "no landed call" "" "$(cat "$CALLS")"
    assert_contains "dry-run previews the reason" "archived_reason=obsolete" "$out"
    assert_eq "dry-run left the task active" "1" "$(ls aitasks/t38_dryobs.md 2>/dev/null | wc -l | tr -d ' ')"
    teardown
}

# --- t2254: the run's reason names the child only; the auto-archived parent
# --- takes it only when none of its children landed.

test_child_reason_stays_on_child() {
    echo "=== --superseded / --obsolete on the last child: a landed sibling keeps the parent completed ==="
    setup_project
    task aitasks/t50_parent.md Implementing "children_to_implement: [t50_2]"
    archived_record aitasks/archived/t50/t50_1_done.md
    task aitasks/t50/t50_2_last.md Ready
    task aitasks/t51_parent.md Implementing "children_to_implement: [t51_2]"
    archived_record aitasks/archived/t51/t51_1_done.md
    task aitasks/t51/t51_2_last.md Ready
    commit_all
    local out rc=0
    out=$(./.aitask-scripts/aitask_archive.sh --superseded 50_2 2>&1) || rc=$?
    assert_eq "superseded: exit 0" "0" "$rc"
    assert_contains "superseded: child carries the reason" "archived_reason: superseded" \
        "$(cat aitasks/archived/t50/t50_2_last.md)"
    assert_contains "superseded: parent archived as Done" "status: Done" "$(cat aitasks/archived/t50_parent.md)"
    assert_not_contains "superseded: parent carries no reason" "archived_reason" \
        "$(cat aitasks/archived/t50_parent.md)"
    assert_contains "superseded: names the landed sibling" "Parent t50: t50_1 landed" "$out"
    assert_eq "superseded: fires for the parent only" "obsolescence landed 50" "$(cat "$CALLS")"
    rc=0
    out=$(./.aitask-scripts/aitask_archive.sh --obsolete 51_2 2>&1) || rc=$?
    assert_eq "obsolete: exit 0" "0" "$rc"
    assert_contains "obsolete: child carries the reason" "archived_reason: obsolete" \
        "$(cat aitasks/archived/t51/t51_2_last.md)"
    assert_not_contains "obsolete: parent carries no reason" "archived_reason" \
        "$(cat aitasks/archived/t51_parent.md)"
    assert_contains "obsolete: names the landed sibling" "Parent t51: t51_1 landed" "$out"
    assert_eq "obsolete: fires for the parent only" \
        $'obsolescence landed 50\nobsolescence landed 51' "$(cat "$CALLS")"
    teardown
}

test_parent_inherits_when_no_child_landed() {
    echo "=== a dropped sibling and a flagged last child: the parent takes the run's reason ==="
    setup_project
    task aitasks/t52_parent.md Implementing "children_to_implement: [t52_2]"
    archived_record aitasks/archived/t52/t52_1_drop.md superseded
    task aitasks/t52/t52_2_last.md Ready
    commit_all
    local out rc=0
    out=$(./.aitask-scripts/aitask_archive.sh --obsolete 52_2 2>&1) || rc=$?
    assert_eq "exit 0" "0" "$rc"
    assert_contains "parent takes the run's reason" $'status: Done\narchived_reason: obsolete' \
        "$(cat aitasks/archived/t52_parent.md)"
    assert_contains "says why" "no child landed (1 other archived child record(s) read)" "$out"
    assert_eq "no landed call" "" "$(cat "$CALLS")"
    teardown
}

test_single_child_parent_inherits() {
    echo "=== a flagged only child: the parent takes the run's reason ==="
    setup_project
    task aitasks/t53_parent.md Implementing "children_to_implement: [t53_1]"
    task aitasks/t53/t53_1_only.md Ready
    commit_all
    local out rc=0
    out=$(./.aitask-scripts/aitask_archive.sh --superseded 53_1 2>&1) || rc=$?
    assert_eq "exit 0" "0" "$rc"
    assert_contains "parent superseded" "archived_reason: superseded" "$(cat aitasks/archived/t53_parent.md)"
    assert_contains "says why" "no child landed (0 other archived child record(s) read)" "$out"
    assert_eq "no landed call" "" "$(cat "$CALLS")"
    teardown
}

test_all_dropped_bundle_parent_inherits() {
    echo "=== bundled siblings are READ: all dropped -> the parent takes the run's reason ==="
    setup_project
    task aitasks/t54_parent.md Implementing "children_to_implement: [t54_3]"
    task aitasks/t54/t54_3_last.md Ready
    bundle aitasks/archived/_b0/old0.tar.zst 54 1:superseded 2:obsolete
    commit_all
    local out rc=0
    out=$(./.aitask-scripts/aitask_archive.sh --obsolete 54_3 2>&1) || rc=$?
    assert_eq "exit 0" "0" "$rc"
    assert_contains "parent takes the run's reason" "archived_reason: obsolete" \
        "$(cat aitasks/archived/t54_parent.md)"
    assert_contains "both bundled records were read" \
        "no child landed (2 other archived child record(s) read)" "$out"
    assert_not_contains "no unverified fallback" "could not read" "$out"
    assert_eq "no landed call" "" "$(cat "$CALLS")"
    teardown
}

test_bundled_landed_sibling_keeps_parent_completed() {
    echo "=== a landed sibling inside a legacy bundle keeps the parent completed ==="
    setup_project
    task aitasks/t56_parent.md Implementing "children_to_implement: [t56_3]"
    archived_record aitasks/archived/t56/t56_1_drop.md superseded
    task aitasks/t56/t56_3_last.md Ready
    bundle aitasks/archived/old.tar.gz 56 2
    commit_all
    local out rc=0
    out=$(./.aitask-scripts/aitask_archive.sh --obsolete 56_3 2>&1) || rc=$?
    assert_eq "exit 0" "0" "$rc"
    assert_not_contains "parent carries no reason" "archived_reason" "$(cat aitasks/archived/t56_parent.md)"
    assert_contains "names the bundled landed sibling" "Parent t56: t56_2 landed" "$out"
    assert_eq "fires for the parent" "obsolescence landed 56" "$(cat "$CALLS")"
    teardown
}

test_unreadable_bundle_falls_back_to_completed() {
    echo "=== an unreadable bundle: unproven -> completed, announced, never claimed as landed ==="
    setup_project
    task aitasks/t57_parent.md Implementing "children_to_implement: [t57_1]"
    task aitasks/t57/t57_1_only.md Ready
    printf 'not a tarball\n' > aitasks/archived/old.tar.gz
    commit_all
    local out err errf rc=0
    errf="$(mktemp)"
    out=$(./.aitask-scripts/aitask_archive.sh --obsolete 57_1 2>"$errf") || rc=$?
    err="$(cat "$errf")"
    rm -f "$errf"
    assert_eq "exit 0" "0" "$rc"
    assert_not_contains "parent carries no reason" "archived_reason" "$(cat aitasks/archived/t57_parent.md)"
    assert_contains "stderr says it could not verify" \
        "could not read every child record (unlistable bundle aitasks/archived/old.tar.gz)" "$err"
    assert_not_contains "no false landed claim (stdout)" "landed — archiving" "$out"
    assert_not_contains "no false landed claim (stderr)" "landed — archiving" "$err"
    assert_eq "completed work fires" "obsolescence landed 57" "$(cat "$CALLS")"
    teardown
}

test_unpack_handoff_between_scans_is_rechecked() {
    echo "=== an unpack handoff between the loose and bundle scans is caught by the stability recheck ==="
    setup_project
    task aitasks/t58_parent.md Implementing "children_to_implement: [t58_2]"
    task aitasks/t58/t58_2_last.md Ready
    bundle aitasks/archived/old.tar.gz 58 1
    commit_all
    local hook log
    hook="$(dirname "$PWD")/handoff_hook.sh"
    log="$(dirname "$PWD")/handoff.log"
    # Simulates aitask_zip_old.sh cmd_unpack landing mid-scan: the landed record
    # is copied loose first, then dropped together with its now-empty bundle.
    cat > "$hook" <<EOF
echo "attempt \$AIT_ARCHIVE_SCAN_ATTEMPT" >> "$log"
[ -f aitasks/archived/old.tar.gz ] || exit 0
mkdir -p aitasks/archived/t58
tar -xzf aitasks/archived/old.tar.gz -O ./t58/t58_1_bundled.md > aitasks/archived/t58/t58_1_bundled.md
rm aitasks/archived/old.tar.gz
EOF
    local out rc=0
    out=$(AIT_ARCHIVE_PARENT_SCAN_HOOK="bash $hook" \
          ./.aitask-scripts/aitask_archive.sh --obsolete 58_2 2>&1) || rc=$?
    assert_eq "exit 0" "0" "$rc"
    assert_eq "the handoff ran on attempt 1; the rescan found the record loose" \
        "attempt 1" "$(cat "$log" 2>/dev/null)"
    assert_eq "the handoff left the record loose" "1" \
        "$(ls aitasks/archived/t58/t58_1_bundled.md 2>/dev/null | wc -l | tr -d ' ')"
    assert_not_contains "parent carries no reason" "archived_reason" "$(cat aitasks/archived/t58_parent.md)"
    assert_contains "names the restored sibling" "Parent t58: t58_1 landed" "$out"
    assert_eq "fires for the parent" "obsolescence landed 58" "$(cat "$CALLS")"
    teardown
}

test_records_that_keep_changing_are_unverified() {
    echo "=== records that change during every scan: unproven -> completed, never claimed as landed ==="
    setup_project
    task aitasks/t59_parent.md Implementing "children_to_implement: [t59_2]"
    archived_record aitasks/archived/t59/t59_1_drop.md superseded
    task aitasks/t59/t59_2_last.md Ready
    commit_all
    local hook log
    hook="$(dirname "$PWD")/churn_hook.sh"
    log="$(dirname "$PWD")/churn.log"
    cat > "$hook" <<EOF
echo "attempt \$AIT_ARCHIVE_SCAN_ATTEMPT" >> "$log"
echo "touched on attempt \$AIT_ARCHIVE_SCAN_ATTEMPT" >> aitasks/archived/t59/t59_1_drop.md
EOF
    local out err errf rc=0
    errf="$(mktemp)"
    out=$(AIT_ARCHIVE_PARENT_SCAN_HOOK="bash $hook" \
          ./.aitask-scripts/aitask_archive.sh --obsolete 59_2 2>"$errf") || rc=$?
    err="$(cat "$errf")"
    rm -f "$errf"
    assert_eq "exit 0" "0" "$rc"
    assert_eq "every attempt saw a change (bounded at 3)" \
        $'attempt 1\nattempt 2\nattempt 3' "$(cat "$log" 2>/dev/null)"
    assert_not_contains "parent carries no reason" "archived_reason" "$(cat aitasks/archived/t59_parent.md)"
    assert_contains "stderr says the view never settled" \
        "child records kept changing during the scan (3 attempts)" "$err"
    assert_not_contains "no false landed claim" "landed — archiving" "$out$err"
    assert_eq "completed work fires" "obsolescence landed 59" "$(cat "$CALLS")"
    teardown
}

test_flagged_child_with_siblings_left() {
    echo "=== a flagged child with siblings left: exit 0, one commit, parent untouched ==="
    setup_project
    task aitasks/t55_parent.md Implementing "children_to_implement: [t55_1, t55_2]"
    task aitasks/t55/t55_1_a.md Ready
    task aitasks/t55/t55_2_b.md Ready
    commit_all
    local head rc=0
    head=$(git rev-parse HEAD)
    ./.aitask-scripts/aitask_archive.sh --superseded 55_1 > /dev/null 2>&1 || rc=$?
    assert_eq "archive exit 0 (no errexit leak from the reason branches)" "0" "$rc"
    assert_eq "exactly one commit" "1" "$(git rev-list --count "$head"..HEAD)"
    assert_contains "child carries the reason" "archived_reason: superseded" \
        "$(cat aitasks/archived/t55/t55_1_a.md)"
    assert_eq "parent still active" "1" "$(ls aitasks/t55_parent.md 2>/dev/null | wc -l | tr -d ' ')"
    assert_not_contains "parent carries no reason" "archived_reason" "$(cat aitasks/t55_parent.md)"
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
test_child_reason_stays_on_child
test_parent_inherits_when_no_child_landed
test_single_child_parent_inherits
test_all_dropped_bundle_parent_inherits
test_bundled_landed_sibling_keeps_parent_completed
test_unreadable_bundle_falls_back_to_completed
test_unpack_handoff_between_scans_is_rechecked
test_records_that_keep_changing_are_unverified
test_flagged_child_with_siblings_left

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
