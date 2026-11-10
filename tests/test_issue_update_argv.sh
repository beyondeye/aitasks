#!/usr/bin/env bash
# test_issue_update_argv.sh - Characterize the exact gh / glab argv that
# aitask_issue_update.sh sends for each action (t2261_1 pre-phase
# characterize_issue_update_argv).
#
# Written and first run against the UNMODIFIED script at commit 0e17732b1,
# before the platform backends moved into lib/issue_backends.sh. It pins the
# full call sequence per action, auth check included, so the extraction can
# only change what it means to change.
#
# Every assertion carries a tag:
#   [C] constant: byte-identical before and after the extraction.
#   [D] deliberately changed: the GitHub issue argument went from the issue
#       NUMBER to the issue URL, because `gh issue comment|close|view` accept
#       a URL and a bare number targets the CURRENT repository, which is the
#       wrong issue for a cross-repo or GitHub Enterprise `issue:` URL.
#
# Run: bash tests/test_issue_update_argv.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config

PASS=0
FAIL=0
TOTAL=0

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_issue_update_argv_XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT
# Private lock base, the documented isolation seam (t1496).
AITASKS_LOCK_DIR="$TMP/locks"
export AITASKS_LOCK_DIR

. "$PROJECT_DIR/tests/lib/issue_update_fixture.sh"
ifx_write_stubs
REPO="$TMP/repo"
ifx_make_repo "$REPO"

# [D] The GitHub issue argument: the issue URL (lib/issue_backends.sh
# source_issue_ref). Pre-change control, measured on the unmodified script
# (blob 936d9a96, identical at 0e17732b1 and 79416f14c): the bare number.
#   GH_REF_7="7"
#   GH_REF_42="42"
# Run with those two values against the pre-change script: all 39 assertions
# pass. Run with the URL values against it: exactly the 4 [D] rows fail.
GH_REF_7="https://github.com/o/r/issues/7"
GH_REF_42="https://github.com/o/r/issues/42"

BODY_10="$(ifx_body "$REPO" 10)"
BODY_20="$(ifx_body "$REPO" 20)"
GH_AUTH="$(ifx_render gh auth status)"
GL_AUTH="$(ifx_render glab auth status)"

echo "=== aitask_issue_update.sh argv characterization (t2261_1) ==="

# --- GitHub ---------------------------------------------------------------

ifx_run "$REPO" --close 10
assert_eq "gh close-with-notes: exit 0 [C]" "0" "$IFX_RC"
assert_eq "gh close-with-notes: 2 calls [C]" "2" "$(ifx_log_count)"
assert_eq "gh close-with-notes: auth check [C]" "$GH_AUTH" "$(ifx_log_line 1)"
assert_eq "gh close-with-notes: close with comment [D]" \
    "$(ifx_render gh issue close "$GH_REF_7" --comment "$BODY_10")" "$(ifx_log_line 2)"

ifx_run "$REPO" 10
assert_eq "gh comment-only: exit 0 [C]" "0" "$IFX_RC"
assert_eq "gh comment-only: 2 calls [C]" "2" "$(ifx_log_count)"
assert_eq "gh comment-only: auth check [C]" "$GH_AUTH" "$(ifx_log_line 1)"
assert_eq "gh comment-only: comment [D]" \
    "$(ifx_render gh issue comment "$GH_REF_7" --body "$BODY_10")" "$(ifx_log_line 2)"

ifx_run "$REPO" --close --no-comment 10
assert_eq "gh close-silently: exit 0 [C]" "0" "$IFX_RC"
assert_eq "gh close-silently: 2 calls [C]" "2" "$(ifx_log_count)"
assert_eq "gh close-silently: auth check [C]" "$GH_AUTH" "$(ifx_log_line 1)"
assert_eq "gh close-silently: close, no comment [D]" \
    "$(ifx_render gh issue close "$GH_REF_7")" "$(ifx_log_line 2)"

ifx_run "$REPO" --issue-url "https://github.com/o/r/issues/42" --close 10
assert_eq "gh folded: exit 0 [C]" "0" "$IFX_RC"
assert_eq "gh folded: 2 calls [C]" "2" "$(ifx_log_count)"
assert_eq "gh folded: auth check [C]" "$GH_AUTH" "$(ifx_log_line 1)"
assert_eq "gh folded: close the override issue with the primary task's body [D]" \
    "$(ifx_render gh issue close "$GH_REF_42" --comment "$BODY_10")" "$(ifx_log_line 2)"

# --- GitLab (every row constant: the number plus -R <slug>) ---------------

ifx_run "$REPO" --close 20
assert_eq "glab close-with-notes: exit 0 [C]" "0" "$IFX_RC"
assert_eq "glab close-with-notes: 3 calls [C]" "3" "$(ifx_log_count)"
assert_eq "glab close-with-notes: auth check [C]" "$GL_AUTH" "$(ifx_log_line 1)"
assert_eq "glab close-with-notes: note first [C]" \
    "$(ifx_render glab issue note 9 -R g/p -m "$BODY_20")" "$(ifx_log_line 2)"
assert_eq "glab close-with-notes: then close [C]" \
    "$(ifx_render glab issue close 9 -R g/p)" "$(ifx_log_line 3)"

ifx_run "$REPO" 20
assert_eq "glab comment-only: exit 0 [C]" "0" "$IFX_RC"
assert_eq "glab comment-only: 2 calls [C]" "2" "$(ifx_log_count)"
assert_eq "glab comment-only: auth check [C]" "$GL_AUTH" "$(ifx_log_line 1)"
assert_eq "glab comment-only: note [C]" \
    "$(ifx_render glab issue note 9 -R g/p -m "$BODY_20")" "$(ifx_log_line 2)"

ifx_run "$REPO" --close --no-comment 20
assert_eq "glab close-silently: exit 0 [C]" "0" "$IFX_RC"
assert_eq "glab close-silently: 2 calls [C]" "2" "$(ifx_log_count)"
assert_eq "glab close-silently: auth check [C]" "$GL_AUTH" "$(ifx_log_line 1)"
assert_eq "glab close-silently: close only [C]" \
    "$(ifx_render glab issue close 9 -R g/p)" "$(ifx_log_line 2)"

ifx_run "$REPO" --issue-url "https://gitlab.com/g/p/-/issues/11" --close 20
assert_eq "glab folded: exit 0 [C]" "0" "$IFX_RC"
assert_eq "glab folded: 3 calls [C]" "3" "$(ifx_log_count)"
assert_eq "glab folded: auth check [C]" "$GL_AUTH" "$(ifx_log_line 1)"
assert_eq "glab folded: note on the override issue [C]" \
    "$(ifx_render glab issue note 11 -R g/p -m "$BODY_20")" "$(ifx_log_line 2)"
assert_eq "glab folded: close the override issue [C]" \
    "$(ifx_render glab issue close 11 -R g/p)" "$(ifx_log_line 3)"

# --- Dry run --------------------------------------------------------------
#
# run_update checks the CLI (source_check_cli) BEFORE its dry-run return, so a
# dry run makes exactly one call, the auth probe, and no `issue` call. It also
# writes nothing: HEAD and the ledger's file list are unchanged by it (earlier
# runs above may legitimately have recorded entries).

ledger_files() { find "$REPO/aitasks/metadata/release_issues" -type f 2>/dev/null | sort; }
head_before="$(git -C "$REPO" rev-parse HEAD)"
files_before="$(ledger_files)"
ifx_run "$REPO" --dry-run --close 10
assert_eq "gh dry-run: exit 0 [C]" "0" "$IFX_RC"
assert_eq "gh dry-run: only the auth check [C]" "$GH_AUTH" "$(cat "$STUB_LOG")"
assert_eq "gh dry-run: no commit [C]" "$head_before" "$(git -C "$REPO" rev-parse HEAD)"
assert_eq "gh dry-run: no ledger file written [C]" "$files_before" "$(ledger_files)"
assert_not_contains "gh dry-run: no RELEASE_LEDGER line [C]" "RELEASE_LEDGER" "$IFX_OUT"

ifx_run "$REPO" --dry-run --close 20
assert_eq "glab dry-run: exit 0 [C]" "0" "$IFX_RC"
assert_eq "glab dry-run: only the auth check [C]" "$GL_AUTH" "$(cat "$STUB_LOG")"

# --- summary ---------------------------------------------------------------
echo
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
[[ "$FAIL" -eq 0 ]]
