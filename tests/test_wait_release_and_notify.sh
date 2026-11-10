#!/usr/bin/env bash
# test_wait_release_and_notify.sh - the framework release wrapper
# (wait_release_and_notify.sh, t2261_2): it waits for the shared publication
# check, then runs the consumer, against a scenario-scripted gh stub whose JSON
# follows real captured `gh release view` / `gh run list` output.
#
# Legacy-mode fixture (tests/lib/release_notify_fixture.sh), so the wrapper's
# branch-mode reconciliation is skipped here; it is covered by
# test_release_notify_branch_mode.sh.
#
# Coverage:
#   (1) delayed publication: 404 -> draft -> no run -> in progress -> success
#   (2) a failed workflow: exit 2, nothing posted, RETRY printed
#   (3) timeouts: a stuck run, and a missing asset
#   (4) a retry after a failed run that was re-run successfully
#   (5) a retry after a partial notification posts only the remainder
#   (6) a run for the tag at another commit is ignored
#   (7) a non-designated machine: exit 5 before any gh call
#   (8) sequential retries leave exactly one marker comment per issue
#   (9) an incomplete framework policy refuses to start; SHIPPED_EARLIER
#       lines carry the wrapper's own retry command
#
# The duplicate-prevention guarantee asserted in (5) and (8) is for runs
# serialised on the designated machine and sequential retries, NOT for
# concurrent runs on several machines.
#
# Assertions assert outcomes, never exact poll counts.
#
# Run: bash tests/test_wait_release_and_notify.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config

PASS=0
FAIL=0
TOTAL=0

command -v jq >/dev/null 2>&1 || { echo "SKIP: jq is required by the gh stub"; exit 0; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_wait_release_XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT
AITASKS_LOCK_DIR="$TMP/locks"
export AITASKS_LOCK_DIR
mkdir -p "$AITASKS_LOCK_DIR"

. "$PROJECT_DIR/tests/lib/release_notify_fixture.sh"
rnf_write_stubs

POLICY=$'release_notify_host: testhost\nrelease_publication_workflow: release.yml\nrelease_publication_assets:\n  - app-{tag}.tar.gz\n'
N=0
new_repo() {
    N=$((N + 1))
    mkdir -p "$TMP/r$N"
    REPO="$(rnf_make_repo "$TMP/r$N")"
    cp "$PROJECT_DIR/wait_release_and_notify.sh" "$REPO/"
    ln -s "$PROJECT_DIR/.aitask-scripts" "$REPO/.aitask-scripts"
    printf '/.aitask-scripts\n/wait_release_and_notify.sh\n' >> "$REPO/.git/info/exclude"
    rnf_config "$REPO" "$POLICY"
    rnf_reset_state
}
sha_of() { git -C "$REPO" rev-parse "$1^{commit}"; }
posts() { rnf_log_count '^gh issue comment'; }
complete_release() { rnf_release "$1" "${2:-1}" false "app-$1.tar.gz:uploaded:7"; }
success_run() { rnf_runs "$1" "${2:-1}" "7 $(sha_of "$1") $1 completed success"; }

# w_run <args…> — the wrapper from the fixture root.
w_run() {
    RNF_RC=0
    ( cd "$REPO" && PATH="$RNF_BIN:$PATH" ./wait_release_and_notify.sh "$@" ) \
        > "$TMP/w.out" 2> "$TMP/w.err" || RNF_RC=$?
    RNF_OUT="$(cat "$TMP/w.out")"
    RNF_ERR="$(cat "$TMP/w.err")"
}

# ---------------------------------------------------------------------------
# (1) delayed publication
new_repo
P50="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
rnf_release_raw v1.2.0 1 404
rnf_release v1.2.0 2 true
complete_release v1.2.0 3
rnf_runs v1.2.0 1
rnf_runs v1.2.0 2 "7 $(sha_of v1.2.0) v1.2.0 in_progress "
success_run v1.2.0 3
w_run v1.2.0 --timeout 30 --interval 0
assert_eq "(1) exit 0" "0" "$RNF_RC"
assert_contains "(1) waited for the release" "WAIT:no_release" "$RNF_OUT"
assert_contains "(1) waited for the draft" "WAIT:draft" "$RNF_OUT"
assert_contains "(1) waited for the run" "WAIT:run_not_found" "$RNF_OUT"
assert_contains "(1) waited for completion" "WAIT:run_in_progress" "$RNF_OUT"
assert_contains "(1) published" "PUBLICATION:published|7" "$RNF_OUT"
assert_contains "(1) posted" "POSTED:50|https://github.com/o/r/issues/50" "$RNF_OUT"
assert_eq "(1) one comment" "1" "$(rnf_comment_count o_r_50)"
assert_not_contains "(1) no retry line on success" "RETRY:" "$RNF_OUT"

# ---------------------------------------------------------------------------
# (2) a failed workflow
new_repo
P50="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
complete_release v1.2.0
rnf_runs v1.2.0 1 "7 $(sha_of v1.2.0) v1.2.0 completed failure"
w_run v1.2.0 --timeout 30 --interval 0
assert_eq "(2) exit 2" "2" "$RNF_RC"
assert_contains "(2) workflow failed" "WORKFLOW_FAILED:failure" "$RNF_OUT"
assert_contains "(2) retry" "RETRY: ./wait_release_and_notify.sh v1.2.0" "$RNF_OUT"
assert_eq "(2) no post" "0" "$(posts)"
assert_file_exists "(2) stays pending" "$REPO/$P50"

# ---------------------------------------------------------------------------
# (4) the failed run is re-run successfully: the newest run decides
rnf_runs v1.2.0 1 "7 $(sha_of v1.2.0) v1.2.0 completed failure" "8 $(sha_of v1.2.0) v1.2.0 completed success"
rnf_reset_steps
w_run v1.2.0 --timeout 30 --interval 0
assert_eq "(4) retry exit 0" "0" "$RNF_RC"
assert_contains "(4) the re-run counts" "PUBLICATION:published|8" "$RNF_OUT"
assert_eq "(4) one comment" "1" "$(rnf_comment_count o_r_50)"

# ---------------------------------------------------------------------------
# (3) timeouts
new_repo
P50="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
complete_release v1.2.0
rnf_runs v1.2.0 1 "7 $(sha_of v1.2.0) v1.2.0 in_progress "
w_run v1.2.0 --timeout 2 --interval 1
assert_eq "(3) stuck run: exit 3" "3" "$RNF_RC"
assert_contains "(3) stuck run: timeout" "TIMEOUT:PUBLICATION:pending:run_in_progress" "$RNF_OUT"
assert_contains "(3) stuck run: retry" "RETRY: ./wait_release_and_notify.sh v1.2.0" "$RNF_OUT"
rnf_release v1.2.0 1 false
success_run v1.2.0
rnf_reset_steps
w_run v1.2.0 --timeout 2 --interval 1
assert_eq "(3) missing asset: exit 3" "3" "$RNF_RC"
assert_contains "(3) missing asset: timeout" "TIMEOUT:PUBLICATION:pending:assets_missing:app-v1.2.0.tar.gz" "$RNF_OUT"
assert_eq "(3) no post" "0" "$(posts)"

# ---------------------------------------------------------------------------
# (6) a run for this tag at another commit is ignored
complete_release v1.2.0
rnf_runs v1.2.0 1 "9 $(sha_of v1.1.0) v1.2.0 completed success"
rnf_reset_steps
w_run v1.2.0 --timeout 2 --interval 1
assert_eq "(6) exit 3" "3" "$RNF_RC"
assert_contains "(6) not found" "TIMEOUT:PUBLICATION:pending:run_not_found" "$RNF_OUT"
assert_eq "(6) no post" "0" "$(posts)"

# ---------------------------------------------------------------------------
# (5) a retry after a partial notification, then (8) sequential retries
new_repo
P50="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
rnf_record "$REPO" 60 https://github.com/o/r/issues/60 >/dev/null
complete_release v1.2.0
success_run v1.2.0
: > "$RNF_STATE/fail_post_60"
w_run v1.2.0 --timeout 30 --interval 0
assert_eq "(5) partial: exit 4" "4" "$RNF_RC"
assert_contains "(5) partial: t60 failed" "FAILED:60|https://github.com/o/r/issues/60|post_failed" "$RNF_OUT"
assert_contains "(5) partial: retry" "RETRY: ./wait_release_and_notify.sh v1.2.0" "$RNF_OUT"
rm -f "$RNF_STATE/fail_post_60"
w_run v1.2.0 --timeout 30 --interval 0
assert_eq "(5) retry: exit 0" "0" "$RNF_RC"
assert_contains "(5) retry: posts the remainder" "POSTED:60|" "$RNF_OUT"
assert_not_contains "(5) retry: t50 untouched" "POSTED:50|" "$RNF_OUT"
for _ in 1 2; do w_run v1.2.0 --timeout 30 --interval 0; done
assert_eq "(8) sequential retries: one marker on #50" "1" \
    "$(grep -l -F '<!-- aitask-release:v1.2.0 t50 -->' "$RNF_STATE"/comments/o_r_50/* | wc -l | tr -d ' ')"
assert_eq "(8) sequential retries: one marker on #60" "1" \
    "$(grep -l -F '<!-- aitask-release:v1.2.0 t60 -->' "$RNF_STATE"/comments/o_r_60/* | wc -l | tr -d ' ')"

# ---------------------------------------------------------------------------
# (7) a non-designated machine
new_repo
P50="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
complete_release v1.2.0
success_run v1.2.0
TEST_HOSTNAME=laptop w_run v1.2.0 --timeout 30 --interval 0
assert_eq "(7) exit 5" "5" "$RNF_RC"
assert_contains "(7) names the designated host" "notifications run only on testhost: run ./wait_release_and_notify.sh v1.2.0 there" "$RNF_OUT"
assert_eq "(7) zero run list calls" "0" "$(rnf_log_count '^gh run list')"
assert_eq "(7) zero gh calls at all" "0" "$(rnf_log_count '^gh ')"
assert_file_exists "(7) stays pending" "$REPO/$P50"

# ---------------------------------------------------------------------------
# (9) refusal without a framework policy, and the SHIPPED_EARLIER relay
rnf_config "$REPO" $'release_notify_host: testhost\n'
w_run v1.2.0
assert_eq "(9) incomplete policy: exit 1" "1" "$RNF_RC"
assert_contains "(9) incomplete policy" "SETUP_ERROR:policy_incomplete" "$RNF_OUT"
rnf_config "$REPO" "$POLICY"
rnf_record "$REPO" 10 https://github.com/o/r/issues/10 >/dev/null
w_run v1.2.0 --timeout 30 --interval 0
assert_contains "(9) shipped earlier relayed" "SHIPPED_EARLIER:10|https://github.com/o/r/issues/10|v1.0.0" "$RNF_OUT"
assert_contains "(9) the wrapper's own retry command" "HINT:notify it with: ./wait_release_and_notify.sh v1.0.0" "$RNF_OUT"

# --- summary -----------------------------------------------------------------
echo
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
[[ "$FAIL" -eq 0 ]]
