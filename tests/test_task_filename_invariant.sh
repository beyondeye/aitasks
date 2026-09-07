#!/usr/bin/env bash
# test_task_filename_invariant.sh — repo invariant guard for task filenames (t1721).
#
# Every task file must carry a task id in its name: `t<N>_<name>.md` for a
# parent, `t<N>_<M>_<name>.md` for a child. The convention is load-bearing, not
# cosmetic — an id is how a listing row, a board card, a lock, an archive entry
# and a trail member are all addressed back to the file. A file that does not
# carry one is unaddressable by every consumer: `aitask_ls.sh` now skips it with
# a warning, `roadmap_run.py` reports it as UNPARSABLE_TASK_FILE, and the rest
# (aitask_claim_id.sh, aitask_attach.sh, aitask_artifact.sh,
# aitask_find_by_file.sh) glob `t*.md` loosely and derive an empty id from it.
#
# Guarding it at each consumer would be a long tail; guarding the DATA is one
# check that covers the whole class. That is what this file does.
#
# Known instance this was written for:
#   aitasks/t_refresh_codeagent_suite_default_model_expectations.md — hand-written
#   into aitasks/ as a side-file of an unrelated commit rather than created via
#   `ait create` (which always claims an id from the atomic counter). Renumbered
#   and archived by t1721.
#
# Run: bash tests/test_task_filename_invariant.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

# --- The scan --------------------------------------------------------------
#
# Takes a root so the SAME code runs against the live repo and against a
# fixture. Prints one offending path per line; prints nothing when clean.
#
# `find -L` is mandatory, not stylistic: `aitasks/` is a SYMLINK into the
# `.aitask-data` worktree, and a plain `find aitasks -name 't*.md'` returns zero
# files — which would make the live-repo assertion below pass for every possible
# repository state. (aitask_followup_backfill.sh uses -L for the same reason.)
#
# Scope is the whole tree, `aitasks/archived/` included: an unnumbered file is
# equally unaddressable once archived. `old.tar.zst` bundles are not `.md` and
# are not matched.
scan_unnumbered() {
    local root="$1"
    find -L "$root" -type f -name 't*.md' -print 2>/dev/null | sort | while IFS= read -r p; do
        case "$(basename "$p")" in
            t[0-9]*_*.md)
                # Has a leading number and at least one underscore — now insist
                # on the full shape, so `t12x_foo.md` or `t12_.md` still fail.
                printf '%s\n' "$p" \
                    | grep -qE '/t[0-9]+(_[0-9]+)?_[^/]+\.md$' \
                    || printf '%s\n' "$p"
                ;;
            *)
                printf '%s\n' "$p"
                ;;
        esac
    done
}

echo "=== test_task_filename_invariant.sh ==="
echo

# --- Test 1: the live repo -------------------------------------------------

echo "--- Test 1: live repo ($PROJECT_DIR/aitasks) ---"

offenders=$(scan_unnumbered "$PROJECT_DIR/aitasks")
scanned=$(find -L "$PROJECT_DIR/aitasks" -type f -name 't*.md' -print 2>/dev/null | wc -l)

# Assert the scan actually SAW something first. A broken scan (a missing -L, a
# moved data worktree) returns zero files, and "zero offenders out of zero
# files" is a vacuous pass that would survive any amount of drift.
if [[ "$scanned" -gt 0 ]]; then
    assert_record_pass
else
    assert_record_fail
    echo "FAIL: the scan reached the task tree (expected >0 task files under"
    echo "      $PROJECT_DIR/aitasks, found 0 — is 'find -L' still in the scan,"
    echo "      and does the .aitask-data worktree exist?)"
fi

if [[ -z "$offenders" ]]; then
    assert_record_pass
else
    assert_record_fail
    echo "FAIL: every task file name carries a task id — unaddressable task file(s) found."
    echo "      Rename to t<N>_<name>.md (child: t<N>_<M>_<name>.md), or archive:"
    # Line-oriented, not word-oriented: a path may contain spaces, and an
    # unquoted expansion would also glob.
    printf '%s\n' "$offenders" | while IFS= read -r p; do echo "        $p"; done
fi

# --- Test 2: negative control ----------------------------------------------
#
# Test 1 passes by finding nothing, so on a clean repo it cannot distinguish "the
# invariant holds" from "the scan is broken". This fixture makes the scan prove
# it still detects a violation, on every run.

echo "--- Test 2: negative control (fixture with a known violation) ---"

FIXTURE=$(mktemp -d)
trap 'rm -rf "$FIXTURE"' EXIT

mkdir -p "$FIXTURE/aitasks/t10" "$FIXTURE/aitasks/archived"
: > "$FIXTURE/aitasks/t10_conforming_parent.md"
: > "$FIXTURE/aitasks/t10/t10_1_conforming_child.md"
: > "$FIXTURE/aitasks/archived/t9_conforming_archived.md"
: > "$FIXTURE/aitasks/t_no_number_here.md"

fixture_hits=$(scan_unnumbered "$FIXTURE/aitasks")

assert_eq_trim "fixture scan finds exactly 1 violation" \
    "1" "$(printf '%s' "$fixture_hits" | grep -c . || true)"
assert_contains "fixture scan names the unnumbered file" \
    "t_no_number_here.md" "$fixture_hits"
assert_not_contains "fixture scan does not flag a conforming parent" \
    "t10_conforming_parent.md" "$fixture_hits"
assert_not_contains "fixture scan does not flag a conforming child" \
    "t10_1_conforming_child.md" "$fixture_hits"
assert_not_contains "fixture scan does not flag a conforming archived task" \
    "t9_conforming_archived.md" "$fixture_hits"

# Near-miss shapes: a leading digit alone is not an id, and an id alone is not a
# name. Without these the scan could degrade to `^t[0-9]` and still look green.
: > "$FIXTURE/aitasks/t12x_leading_digits_then_letters.md"
: > "$FIXTURE/aitasks/t13_.md"
near_miss=$(scan_unnumbered "$FIXTURE/aitasks")
assert_contains "fixture scan flags t12x_… (digits must run to the underscore)" \
    "t12x_leading_digits_then_letters.md" "$near_miss"
assert_contains "fixture scan flags t13_.md (an id with no name)" \
    "t13_.md" "$near_miss"

# --- Summary ---------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
