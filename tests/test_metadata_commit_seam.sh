#!/usr/bin/env bash
# test_metadata_commit_seam.sh - aitask_metadata_commit.sh, the metadata owner (t1677).
#
# Run: bash tests/test_metadata_commit_seam.sh
#
# Why this file exists
# --------------------
# t1599_3 made `ait sync`'s sweep refuse to commit any file it cannot attribute
# to a task. Correct — but `aitasks/metadata/*` has no derivable task id and
# nothing else committed it, so an ownerless dirty config became a PERMANENT
# rebase deferral. This helper is the owner.
#
# Every assertion here is written to fail against a helper that does not exist
# (or against one that takes the obvious shortcuts): committing index-wide,
# staging in the default mode, or accepting an untracked path.
#
# Three of them are the ones a naive implementation gets wrong:
#   - Test 3  a path another session STAGED must not ride along (`commit -o --`).
#   - Test 7  an untracked path must be REFUSED, not silently added to the branch.
#   - Test 9  a FAILED commit must leave nothing of ours staged, and must not
#             unstage anybody else's entry.

set -uo pipefail

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"

MC="./.aitask-scripts/aitask_metadata_commit.sh"

# --- Local helpers -----------------------------------------------------------

# Run the helper in <tmpdir>'s clone. Sets MC_OUT / MC_ERR / MC_RC in THIS shell
# (an assignment made inside $( ) would never reach here).
_mc() {
    local tmpdir="$1"; shift
    MC_RC=0
    MC_OUT="$(
        cd "$tmpdir/local" || exit 99
        export PATH="$PWD/bin:$PATH" TEST_HOSTNAME="${TEST_HOSTNAME:-testhost}"
        export AITASKS_LOCK_DIR="$tmpdir/locks"
        "$MC" "$@" 2>"$tmpdir/mc_stderr"
    )" || MC_RC=$?
    MC_ERR="$(cat "$tmpdir/mc_stderr" 2>/dev/null)"
}

# Commit a metadata file onto the data branch, so tests have a TRACKED target
# beyond the fixture's own stats_config.json.
seed_tracked() {   # <tmpdir> <relpath under aitasks/metadata> <content>
    local tmpdir="$1" rel="$2" content="$3"
    (
        cd "$tmpdir/local" || exit 1
        mkdir -p "$(dirname ".aitask-data/aitasks/metadata/$rel")"
        printf '%s\n' "$content" > ".aitask-data/aitasks/metadata/$rel"
        git -C .aitask-data add -- "aitasks/metadata/$rel"
        git -C .aitask-data commit -q -m "seed $rel"
    ) >/dev/null 2>&1
}

# The data branch's real ignore rules — the fixture ships none, and the
# user-layer skip is one of the behaviours under test.
seed_ignores() {   # <tmpdir>
    local tmpdir="$1"
    (
        cd "$tmpdir/local" || exit 1
        printf 'aitasks/metadata/userconfig.yaml\naitasks/metadata/*.local.json\naitasks/metadata/profiles/local/\n' \
            > .aitask-data/.gitignore
        git -C .aitask-data add -- .gitignore
        git -C .aitask-data commit -q -m "seed gitignore"
    ) >/dev/null 2>&1
}

# Make `git commit` fail, without touching anything else. Same seam and same
# reasoning as tests/test_fold_mark.sh:337 — no commit site passes --no-verify,
# and git releases the index lock on hook failure, so the index stays readable.
# The hook lives in the COMMON git dir, which the .aitask-data worktree shares.
install_failing_pre_commit() {   # <tmpdir>
    local hook="$1/local/.git/hooks/pre-commit"
    mkdir -p "$(dirname "$hook")"
    printf '#!/bin/sh\nexit 1\n' > "$hook"
    chmod +x "$hook"
}

data_git() { local tmpdir="$1"; shift; git -C "$tmpdir/local/.aitask-data" "$@" 2>/dev/null; }
staged_paths() { data_git "$1" diff --cached --name-only; }
head_files()   { data_git "$1" show --name-only --format= HEAD; }
head_subject() { data_git "$1" log -1 --format=%s; }
is_tracked()   { data_git "$1" ls-files --error-unmatch -- "$2" >/dev/null 2>&1; }

# ==========================================================================
echo "=== aitask_metadata_commit.sh — the metadata owner (t1677) ==="
echo ""

# --- Test 1: a tracked metadata path is committed, naming the FILE ---------
echo "--- Test 1: one tracked path -> its own commit, named after the file ---"
TMP1="$(setup_repo)"
(cd "$TMP1/local" && printf 'changed\n' >> .aitask-data/aitasks/metadata/stats_config.json)
_mc "$TMP1" aitasks/metadata/stats_config.json

assert_eq "exit 0 on a successful commit" "0" "$MC_RC"
assert_contains "reports COMMITTED with the subject" \
    "COMMITTED:1:ait: Update stats_config.json" "$MC_OUT"
assert_eq "the commit names the FILE, never a task" \
    "ait: Update stats_config.json" "$(head_subject "$TMP1")"
assert_eq "the path is clean afterwards" \
    "" "$(data_git "$TMP1" status --porcelain -- aitasks/metadata/stats_config.json)"

# --- Test 2: bystander isolation ------------------------------------------
echo "--- Test 2: an unrelated dirty task file does NOT ride along ---"
TMP2="$(setup_repo)"
(cd "$TMP2/local" && printf 'changed\n' >> .aitask-data/aitasks/metadata/stats_config.json \
                  && printf 'edit10\n'  >> .aitask-data/aitasks/t10_alpha.md)
_mc "$TMP2" aitasks/metadata/stats_config.json
F2="$(head_files "$TMP2")"

assert_contains "the commit carries the metadata file" "stats_config.json" "$F2"
assert_not_contains "the commit does NOT carry the bystander task file" "t10_alpha" "$F2"
assert_contains "the bystander is still dirty" "t10_alpha.md" \
    "$(data_git "$TMP2" status --porcelain)"

# --- Test 3: another session's STAGED entry is not swept in ----------------
# The discriminating case for `commit -o -- <paths>`: it takes worktree content
# at those paths and ignores the index, so a foreign staged entry survives
# untouched. A bare `git commit` would carry it.
echo "--- Test 3: a foreign STAGED entry is neither committed nor unstaged ---"
TMP3="$(setup_repo)"
(cd "$TMP3/local" && printf 'changed\n' >> .aitask-data/aitasks/metadata/stats_config.json \
                  && printf 'edit20\n'  >> .aitask-data/aitasks/t20_beta.md)
data_git "$TMP3" add -- aitasks/t20_beta.md
_mc "$TMP3" aitasks/metadata/stats_config.json

assert_not_contains "the foreign staged file is NOT in the commit" \
    "t20_beta" "$(head_files "$TMP3")"
assert_contains "the foreign entry is STILL staged" \
    "aitasks/t20_beta.md" "$(staged_paths "$TMP3")"

# --- Test 4: out-of-scope paths are refused, fail-closed -------------------
echo "--- Test 4: a path outside aitasks/metadata/ is refused ---"
TMP4="$(setup_repo)"
BASE4="$(data_head "$TMP4")"
(cd "$TMP4/local" && printf 'x\n' >> README.md)
_mc "$TMP4" README.md
assert_eq "exit 2 for an out-of-scope path" "2" "$MC_RC"
assert_contains "reports REFUSED:out_of_scope" "REFUSED:out_of_scope:README.md" "$MC_OUT"

_mc "$TMP4" 'aitasks/metadata/../../etc/passwd'
assert_eq "exit 2 for a .. escape" "2" "$MC_RC"
assert_contains "a .. escape is refused too" "REFUSED:out_of_scope" "$MC_OUT"

_mc "$TMP4" /etc/passwd
assert_eq "exit 2 for an absolute path" "2" "$MC_RC"
assert_contains "an absolute path is refused too" "REFUSED:out_of_scope" "$MC_OUT"

assert_eq "no commit was made by any refusal" \
    "$BASE4" "$(data_head "$TMP4")"

# --- Test 5: the user layer is skipped, not refused ------------------------
echo "--- Test 5: a gitignored user-layer path is SKIPPED ---"
TMP5="$(setup_repo)"
seed_ignores "$TMP5"
BASE5="$(data_head "$TMP5")"
(cd "$TMP5/local" && printf '{}\n' > .aitask-data/aitasks/metadata/board_config.local.json)
_mc "$TMP5" aitasks/metadata/board_config.local.json

assert_contains "reports SKIPPED for the user layer" \
    "SKIPPED:aitasks/metadata/board_config.local.json" "$MC_OUT"
assert_contains "and falls through to NOCHANGE" "NOCHANGE" "$MC_OUT"
assert_eq "exit 2, nothing committed" "2" "$MC_RC"
assert_eq "the data branch did not move" "$BASE5" "$(data_head "$TMP5")"

# --- Test 6: a deletion of a tracked file is recorded ----------------------
echo "--- Test 6: deleting a tracked profile commits the deletion ---"
TMP6="$(setup_repo)"
seed_tracked "$TMP6" "profiles/scratch.yaml" "name: scratch"
(cd "$TMP6/local" && rm -f .aitask-data/aitasks/metadata/profiles/scratch.yaml)
_mc "$TMP6" aitasks/metadata/profiles/scratch.yaml

assert_eq "exit 0 — a deletion is a change" "0" "$MC_RC"
assert_contains "the commit names the deleted file" \
    "ait: Update scratch.yaml" "$(head_subject "$TMP6")"
if is_tracked "$TMP6" aitasks/metadata/profiles/scratch.yaml; then
    assert_record_fail
    echo "FAIL: the deleted profile is still tracked after the commit"
else
    assert_record_pass
fi

# --- Test 7: an UNTRACKED path is refused, and stays untracked -------------
# task_git_commit_scoped stages what it is given, so a helper that only
# scope-checks would silently add local content to the shared data branch.
echo "--- Test 7: an untracked metadata path is refused and never added ---"
TMP7="$(setup_repo)"
seed_ignores "$TMP7"
BASE7="$(data_head "$TMP7")"
(cd "$TMP7/local" && printf '{"local":true}\n' > .aitask-data/aitasks/metadata/stray.json)
_mc "$TMP7" aitasks/metadata/stray.json

assert_eq "exit 2 for an untracked path" "2" "$MC_RC"
assert_contains "reports REFUSED:untracked" \
    "REFUSED:untracked:aitasks/metadata/stray.json" "$MC_OUT"
assert_eq "no commit was made" "$BASE7" "$(data_head "$TMP7")"
if is_tracked "$TMP7" aitasks/metadata/stray.json; then
    assert_record_fail
    echo "FAIL: the refused path was added to the data branch anyway"
else
    assert_record_pass
fi
assert_eq "and it was not left staged either" "" "$(staged_paths "$TMP7")"

# --- Test 8: --allow-new is the narrow opt-in ------------------------------
echo "--- Test 8: --allow-new accepts exactly that path, and no more ---"
TMP8="$(setup_repo)"
seed_ignores "$TMP8"
(cd "$TMP8/local" && printf '{"shared":true}\n' > .aitask-data/aitasks/metadata/newconf.json)
_mc "$TMP8" --allow-new aitasks/metadata/newconf.json

assert_eq "exit 0 — the created file is committed" "0" "$MC_RC"
assert_contains "named after the file" "ait: Update newconf.json" "$(head_subject "$TMP8")"
if is_tracked "$TMP8" aitasks/metadata/newconf.json; then
    assert_record_pass
else
    assert_record_fail
    echo "FAIL: --allow-new did not actually track the new file"
fi

# ...but the flag does not widen the other two rules.
(cd "$TMP8/local" && printf '{}\n' > .aitask-data/aitasks/metadata/other.local.json)
_mc "$TMP8" --allow-new aitasks/metadata/other.local.json
assert_contains "--allow-new still SKIPS a gitignored path" \
    "SKIPPED:aitasks/metadata/other.local.json" "$MC_OUT"

(cd "$TMP8/local" && mkdir -p .aitask-data/aitasks/metadata/adir)
_mc "$TMP8" --allow-new aitasks/metadata/adir
assert_eq "exit 2 for a directory" "2" "$MC_RC"
assert_contains "--allow-new still refuses a non-file" \
    "REFUSED:not_a_file:aitasks/metadata/adir" "$MC_OUT"

# --- Test 9: a FAILED commit leaves the index exactly as it found it -------
echo "--- Test 9: forced commit failure -> reported, nothing of ours staged ---"
TMP9="$(setup_repo)"
seed_ignores "$TMP9"
BASE9="$(data_head "$TMP9")"
install_failing_pre_commit "$TMP9"
(cd "$TMP9/local" && printf 'changed\n' >> .aitask-data/aitasks/metadata/stats_config.json \
                  && printf 'edit20\n'  >> .aitask-data/aitasks/t20_beta.md)
# A foreign staged entry at a DIFFERENT path, staged before our call.
data_git "$TMP9" add -- aitasks/t20_beta.md
_mc "$TMP9" aitasks/metadata/stats_config.json

assert_eq "exit 1 on a commit failure" "1" "$MC_RC"
assert_contains "reports FAILED" "FAILED:" "$MC_OUT"
assert_eq "nothing was committed" "$BASE9" "$(data_head "$TMP9")"
assert_contains "the config edit SURVIVES on disk" "changed" \
    "$(cat "$TMP9/local/.aitask-data/aitasks/metadata/stats_config.json")"
assert_not_contains "the tracked path is NOT left staged" \
    "stats_config.json" "$(staged_paths "$TMP9")"
assert_contains "the foreign staged entry is untouched" \
    "aitasks/t20_beta.md" "$(staged_paths "$TMP9")"

# The --allow-new half: staged by us, so it must be unstaged again.
(cd "$TMP9/local" && printf '{"shared":true}\n' > .aitask-data/aitasks/metadata/newfail.json)
_mc "$TMP9" --allow-new aitasks/metadata/newfail.json
assert_eq "exit 1 for the created path too" "1" "$MC_RC"
assert_not_contains "an --allow-new path is unstaged after failure" \
    "newfail.json" "$(staged_paths "$TMP9")"
if is_tracked "$TMP9" aitasks/metadata/newfail.json; then
    assert_record_fail
    echo "FAIL: a failed --allow-new commit left the file tracked"
else
    assert_record_pass
fi
assert_contains "the foreign entry is STILL untouched" \
    "aitasks/t20_beta.md" "$(staged_paths "$TMP9")"

# The backstop: a file whose commit failed is still dirty, so sync still names it.
rm -f "$TMP9/local/.git/hooks/pre-commit"
OUT9="$(run_sync "$TMP9")"
assert_contains "ait sync still reports the uncommitted file as ownerless" \
    "ownerless" "$(sync_err "$TMP9")"

# --- Test 10: after a successful commit, sync reports nothing --------------
# The task's own acceptance bullet.
echo "--- Test 10: a committed config is no longer ownerless to ait sync ---"
TMP10="$(setup_repo)"
(cd "$TMP10/local" && printf 'changed\n' >> .aitask-data/aitasks/metadata/stats_config.json)
_mc "$TMP10" aitasks/metadata/stats_config.json
assert_eq "precondition: the commit succeeded" "0" "$MC_RC"
OUT10="$(run_sync "$TMP10")"
assert_not_contains "ait sync reports no ownerless file" \
    "ownerless" "$(sync_err "$TMP10")"
assert_not_contains "and does not defer on protected_dirty" \
    "DEFERRED:protected_dirty" "$OUT10"

# --- Test 11: no paths at all is a refusal, never an index-wide commit -----
echo "--- Test 11: no paths -> usage, never a whole-index commit ---"
TMP11="$(setup_repo)"
BASE11="$(data_head "$TMP11")"
(cd "$TMP11/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
data_git "$TMP11" add -- aitasks/t10_alpha.md
_mc "$TMP11"
assert_eq "exit 2 with no arguments" "2" "$MC_RC"
assert_eq "the staged index was NOT committed" "$BASE11" "$(data_head "$TMP11")"

# ==========================================================================
echo ""
echo "=== Results: $PASS passed, $FAIL failed (of $TOTAL) ==="
[[ "$FAIL" -eq 0 ]]
