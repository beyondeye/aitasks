#!/usr/bin/env bash
# Direct scoped-commit lifetime checks: inspect before the suite removes TMPDIR.
set -uo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config
PASS=0 FAIL=0 TOTAL=0
ROOT="$(mktemp -d "${TMPDIR:-/tmp}/commit_capture_XXXXXX")" || exit 1
trap 'rm -rf -- "$ROOT"' EXIT
export SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
export CAPTURE_LIB="${CAPTURE_LIB_OVERRIDE:-$SCRIPT_DIR/lib/task_utils.sh}"

cat > "$ROOT/call.sh" <<'CALL'
set -euo pipefail
. "$CAPTURE_LIB"
cd "$CASE/data" || exit 1
_AIT_DATA_WORKTREE="$CASE/data"
export TMPDIR="$CASE/tmp" AITASKS_LOCK_DIR="$CASE/locks"
caller_exit() {
    printf '%s\n' "$1" > "$CASE/trap-status"
    printf '%s\n' "caller's trap" > "$CASE/trap-marker"
    printf 'exit-eight\n' >&8
    printf 'exit-nine\n' >&9
    printf 'exit-ten\n' >&10
    printf 'exit-eleven\n' >&11
}
trap 'caller_exit "$?"' EXIT
before="$(trap -p EXIT)"
exec 8>"$CASE/fd8" 9>"$CASE/fd9" 10>"$CASE/fd10" 11>"$CASE/fd11"
if [[ "$MODE" == no_stage_busy_* ]]; then
    # 10 and 11 already belong to the EXIT handler. Occupy the rest of the
    # former allocation window, leaving higher descriptors available.
    for (( fd=12; fd<64; fd++ )); do
        eval "exec $fd>/dev/null"
    done
fi
case "$MODE" in
    stage_wedge|no_stage_wedge|no_stage_busy_wedge|no_stage_clean) : > "$CASE/data/.git/MERGE_HEAD" ;;
    add_failure) : > "$CASE/data/.git/index.lock" ;;
    commit_failure)
        printf '#!/bin/sh\necho hook-rejected >&2\nexit 1\n' > "$CASE/data/.git/hooks/pre-commit"
        chmod +x "$CASE/data/.git/hooks/pre-commit" ;;
    mktemp_failure) mktemp() { return 1; } ;;
    race)
        : > "$CASE/locks/.ait_commit_scoped_test_seams"
        export AIT_COMMIT_SCOPED_SEAM_PREGIT=': > "$CASE/data/.git/MERGE_HEAD"' ;;
esac
rc=0
AIT_COMMIT_SCOPED_ERR=stale
case "$MODE" in
    no_stage_*|race) task_git_commit_scoped --no-stage "capture test" task.md || rc=$? ;;
    *) task_git_commit_scoped "capture test" task.md || rc=$? ;;
esac
printf '%s\n' "$AIT_COMMIT_SCOPED_ERR" > "$CASE/diagnostic"
printf 'original-eight\n' >&8
printf 'original-nine\n' >&9
[[ "$(trap -p EXIT)" == "$before" ]] && : > "$CASE/trap-restored"
exit "$rc"
CALL

run_case() {
    local mode="$1" expected="$2" rc=0 captures
    # Capture paths must survive spaces and quotes in the caller's TMPDIR.
    export CASE="$ROOT/$mode space ' quote" MODE="$mode"
    mkdir -p "$CASE/data" "$CASE/tmp" "$CASE/locks"
    git -C "$CASE/data" init -q
    git -C "$CASE/data" config user.email test@example.com
    git -C "$CASE/data" config user.name Test
    git -C "$CASE/data" config commit.gpgsign false
    printf 'before\n' > "$CASE/data/task.md"
    git -C "$CASE/data" add task.md
    git -C "$CASE/data" commit -qm initial
    [[ "$mode" == *_clean ]] || printf 'after\n' > "$CASE/data/task.md"
    bash "$ROOT/call.sh" > "$CASE/stdout" 2> "$CASE/stderr" || rc=$?
    assert_eq "$mode: status" "$expected" "$rc"
    assert_eq "$mode: stdout stays a data channel" '' "$(cat "$CASE/stdout")"
    captures="$(find "$CASE/tmp" -name 'ait_commit_scoped_err.*' | wc -l | tr -d ' ')"
    assert_eq "$mode: capture removed before outer cleanup" 0 "$captures"
    assert_eq "$mode: original EXIT status" "$expected" "$(cat "$CASE/trap-status")"
    assert_eq "$mode: caller EXIT handler ran" "caller's trap" "$(cat "$CASE/trap-marker")"
    case "$mode" in
        stage_wedge|no_stage_wedge|no_stage_busy_wedge|race)
            assert_eq "$mode: EXIT handler retains fd 8" exit-eight "$(cat "$CASE/fd8")"
            assert_eq "$mode: EXIT handler retains fd 9" exit-nine "$(cat "$CASE/fd9")"
            assert_eq "$mode: guard exits the calling shell" no "$([[ -e "$CASE/diagnostic" ]] && echo yes || echo no)" ;;
        *)
            assert_file_exists "$mode: caller trap restored before return" "$CASE/trap-restored"
            assert_eq "$mode: fd 8 retained through return and EXIT" $'original-eight\nexit-eight' "$(cat "$CASE/fd8")"
            assert_eq "$mode: fd 9 retained through return and EXIT" $'original-nine\nexit-nine' "$(cat "$CASE/fd9")" ;;
    esac
    assert_eq "$mode: EXIT handler retains occupied fd 10" exit-ten "$(cat "$CASE/fd10")"
    assert_eq "$mode: EXIT handler retains occupied fd 11" exit-eleven "$(cat "$CASE/fd11")"
    assert_not_contains "$mode: EXIT writes have valid descriptors" 'Bad file descriptor' "$(cat "$CASE/stderr")"
    case "$mode" in
        add_failure) assert_contains 'add failure diagnostic retained' 'index.lock' "$(cat "$CASE/diagnostic")" ;;
        commit_failure) assert_contains 'commit failure diagnostic retained' 'hook-rejected' "$(cat "$CASE/diagnostic")" ;;
        success|no_stage_success|no_stage_clean|no_stage_busy_clean|no_stage_busy_success|mktemp_failure)
            assert_eq "$mode: stale diagnostic cleared" '' "$(cat "$CASE/diagnostic")" ;;
    esac
}

run_case stage_wedge 1
run_case no_stage_wedge 1
run_case no_stage_clean 2
run_case success 0
run_case no_stage_success 0
run_case add_failure 1
run_case commit_failure 1
run_case mktemp_failure 0
run_case race 1
run_case no_stage_busy_clean 2
run_case no_stage_busy_success 0
run_case no_stage_busy_wedge 1
printf 'Results: %s/%s passed, %s failed\n' "$PASS" "$TOTAL" "$FAIL"
[[ "$FAIL" == 0 ]]
