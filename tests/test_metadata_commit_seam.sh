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
# --preflight (t1704): INSPECT the destination, write nothing.
#
# The cross-repo config push has to decide what is safe in ANOTHER repo before
# writing there. These pin the report; lib/cross_repo_settings.py turns it into
# a decision.
# ==========================================================================

# --- Test 12: every per-path state the preflight can report ---------------
echo "--- Test 12: --preflight reports clean/dirty/ignored/untracked/absent ---"
TMP12="$(setup_repo)"
seed_ignores "$TMP12"
seed_tracked "$TMP12" "codeagent_config.json" '{"defaults":{}}'
BASE12="$(data_head "$TMP12")"
(
    cd "$TMP12/local" || exit 1
    printf 'dirtied\n' >> .aitask-data/aitasks/metadata/stats_config.json
    printf '{"defaults":{}}\n' > .aitask-data/aitasks/metadata/codeagent_config.local.json
    printf 'loose\n' > .aitask-data/aitasks/metadata/untracked_thing.json
)
_mc "$TMP12" --preflight \
    aitasks/metadata/codeagent_config.json \
    aitasks/metadata/stats_config.json \
    aitasks/metadata/codeagent_config.local.json \
    aitasks/metadata/untracked_thing.json \
    aitasks/metadata/never_existed.json

assert_eq "12: exit 0 — an inspection is not a refusal" "0" "$MC_RC"
assert_contains "12: branch mode is reported" "MODE:branch" "$MC_OUT"
assert_contains "12: the data branch is named" "BRANCH:aitask-data" "$MC_OUT"
assert_contains "12: a tracked, unmodified path is clean" \
    "STATE:aitasks/metadata/codeagent_config.json:clean" "$MC_OUT"
assert_contains "12: a tracked, modified path is dirty" \
    "STATE:aitasks/metadata/stats_config.json:dirty" "$MC_OUT"
assert_contains "12: a user-layer path is ignored" \
    "STATE:aitasks/metadata/codeagent_config.local.json:ignored" "$MC_OUT"
assert_contains "12: an untracked-but-present path is untracked" \
    "STATE:aitasks/metadata/untracked_thing.json:untracked" "$MC_OUT"
assert_contains "12: a missing path is absent" \
    "STATE:aitasks/metadata/never_existed.json:absent" "$MC_OUT"
# The whole contract: it INSPECTS.
assert_not_contains "12: nothing was committed" "COMMITTED" "$MC_OUT"
assert_eq "12: the data branch did not move" "$BASE12" "$(data_head "$TMP12")"
assert_eq "12: nothing was staged" "" "$(staged_paths "$TMP12")"
assert_eq "12: the dirty file is STILL dirty (untouched)" "dirtied" \
    "$(tail -n1 "$TMP12/local/.aitask-data/aitasks/metadata/stats_config.json")"

# --- Test 13: MIDOP — a wedged destination is REPORTED, not fatal ----------
# The discriminating case for running the preflight with the wedged-worktree
# guard bypassed: assert_data_worktree_clean DIES on these states, and
# check-ignore (which _is_ignored uses) is not on the readonly allowlist. A
# preflight that died here could never report the very state it exists to find.
echo "--- Test 13: --preflight reports MIDOP instead of dying ---"
TMP13="$(setup_repo)"
seed_tracked "$TMP13" "codeagent_config.json" '{"defaults":{}}'
mkdir -p "$TMP13/local/.git/worktrees/-aitask-data"
: > "$TMP13/local/.git/worktrees/-aitask-data/MERGE_HEAD"
_mc "$TMP13" --preflight aitasks/metadata/codeagent_config.json

assert_eq "13: exit 0 — a wedged destination is a report, not a crash" "0" "$MC_RC"
assert_contains "13: the in-progress state is named" "MIDOP:MERGE_HEAD" "$MC_OUT"
assert_contains "13: per-path state is still reported" \
    "STATE:aitasks/metadata/codeagent_config.json:" "$MC_OUT"
rm -f "$TMP13/local/.git/worktrees/-aitask-data/MERGE_HEAD"
# Control: with the state cleared, no MIDOP line is emitted at all.
_mc "$TMP13" --preflight aitasks/metadata/codeagent_config.json
assert_not_contains "13: control — a clean destination emits no MIDOP" \
    "MIDOP:" "$MC_OUT"

# --- Test 14: a legacy-layout destination reports MODE:legacy -------------
# cross_repo_settings refuses those before writing, so the report has to be able
# to say so.
echo "--- Test 14: --preflight reports MODE:legacy for a legacy layout ---"
TMP14="$(mktemp -d)"
(
    cd "$TMP14" || exit 1
    git init --quiet .
    git config user.email t@t.com; git config user.name T
    mkdir -p aitasks/metadata .aitask-scripts/lib
    cp "$PROJECT_DIR/.aitask-scripts/aitask_metadata_commit.sh" .aitask-scripts/
    ln -s "$PROJECT_DIR/.aitask-scripts/lib" .aitask-scripts/lib_real 2>/dev/null
    rm -rf .aitask-scripts/lib && ln -s "$PROJECT_DIR/.aitask-scripts/lib" .aitask-scripts/lib
    printf '{}\n' > aitasks/metadata/codeagent_config.json
    git add -A && git commit -q -m init
) >/dev/null 2>&1
MC_RC=0
MC_OUT="$(cd "$TMP14" && ./.aitask-scripts/aitask_metadata_commit.sh --preflight \
    aitasks/metadata/codeagent_config.json 2>/dev/null)" || MC_RC=$?
assert_eq "14: exit 0 in legacy mode" "0" "$MC_RC"
assert_contains "14: legacy layout is reported as such" "MODE:legacy" "$MC_OUT"
assert_contains "14: the path state is still reported" \
    "STATE:aitasks/metadata/codeagent_config.json:clean" "$MC_OUT"
rm -rf "$TMP14"

# --- Test 15: the preflight shares the commit path's scope ladder ----------
echo "--- Test 15: --preflight refuses an out-of-scope path ---"
TMP15B="$(setup_repo)"
_mc "$TMP15B" --preflight aitasks/t10_alpha.md
assert_eq "15: exit 2 on an out-of-scope path" "2" "$MC_RC"
assert_contains "15: refused by the same fail-closed rule" \
    "REFUSED:out_of_scope:aitasks/t10_alpha.md" "$MC_OUT"
_mc "$TMP15B" --preflight "aitasks/metadata/../../escape.json"
assert_eq "15: exit 2 on a .. escape" "2" "$MC_RC"
assert_contains "15: the escape is refused, never normalized" \
    "REFUSED:out_of_scope:" "$MC_OUT"
# A commit cannot be requested at the same time — answering an --expect with an
# inspection would read as a successful commit.
_mc "$TMP15B" --preflight --expect "aitasks/metadata/stats_config.json=/dev/null" \
    aitasks/metadata/stats_config.json
assert_eq "15: --preflight with --expect is rejected" "1" "$MC_RC"
assert_contains "15: and says why" "cannot be combined" "$MC_ERR"

# ==========================================================================
# --expect (t1704): the compare-and-commit guard.
#
# The damaging race is not a lost edit — it is PUBLISHING a racer's bytes under
# this helper's own "ait: Update <file>" message, i.e. the framework attributing
# content it never wrote. Every case below is written so the control reproduces
# exactly that.
# ==========================================================================

# --- Test 16: matching bytes commit exactly as before ----------------------
echo "--- Test 16: --expect with matching bytes commits ---"
TMP16="$(setup_repo)"
(cd "$TMP16/local" && printf 'mine\n' >> .aitask-data/aitasks/metadata/stats_config.json)
cp "$TMP16/local/.aitask-data/aitasks/metadata/stats_config.json" "$TMP16/expected16"
_mc "$TMP16" --expect "aitasks/metadata/stats_config.json=$TMP16/expected16" \
    aitasks/metadata/stats_config.json

assert_eq "16: exit 0 — the guard passes through" "0" "$MC_RC"
assert_contains "16: it committed" "COMMITTED:1:ait: Update stats_config.json" "$MC_OUT"
assert_contains "16: the file is in the commit" "stats_config.json" "$(head_files "$TMP16")"

# --- Test 17: stale bytes REFUSE, publishing nothing -----------------------
echo "--- Test 17: --expect with stale bytes refuses and commits nothing ---"
TMP17="$(setup_repo)"
(cd "$TMP17/local" && printf 'mine\n' >> .aitask-data/aitasks/metadata/stats_config.json)
cp "$TMP17/local/.aitask-data/aitasks/metadata/stats_config.json" "$TMP17/expected17"
# A racer lands after our write and before our commit.
(cd "$TMP17/local" && printf 'THEIRS\n' >> .aitask-data/aitasks/metadata/stats_config.json)
BASE17="$(data_head "$TMP17")"
_mc "$TMP17" --expect "aitasks/metadata/stats_config.json=$TMP17/expected17" \
    aitasks/metadata/stats_config.json

assert_eq "17: exit 2 on a raced path" "2" "$MC_RC"
assert_contains "17: the refusal names the path" \
    "REFUSED:changed:aitasks/metadata/stats_config.json" "$MC_OUT"
assert_eq "17: the data branch did NOT move" "$BASE17" "$(data_head "$TMP17")"
assert_eq "17: nothing was left staged" "" "$(staged_paths "$TMP17")"
assert_eq "17: the racer's bytes survive untouched" "THEIRS" \
    "$(tail -n1 "$TMP17/local/.aitask-data/aitasks/metadata/stats_config.json")"

# The control that makes Test 17 mean something: the SAME raced state, without
# --expect, commits — and the racer's line lands under our message. This is the
# misattribution the guard exists to prevent, reproduced.
echo "--- Test 17b: control — the same race WITHOUT --expect publishes it ---"
_mc "$TMP17" aitasks/metadata/stats_config.json
assert_eq "17b: control exit 0 — it committed" "0" "$MC_RC"
assert_contains "17b: under the helper's own file-naming message" \
    "ait: Update stats_config.json" "$(head_subject "$TMP17")"
assert_contains "17b: and the racer's bytes are what got published" "THEIRS" \
    "$(data_git "$TMP17" show "HEAD:aitasks/metadata/stats_config.json")"

# --- Test 18: a vanished path is a change, not an absence ------------------
echo "--- Test 18: --expect on a path that disappeared refuses ---"
TMP18="$(setup_repo)"
(cd "$TMP18/local" && printf 'mine\n' >> .aitask-data/aitasks/metadata/stats_config.json)
cp "$TMP18/local/.aitask-data/aitasks/metadata/stats_config.json" "$TMP18/expected18"
rm -f "$TMP18/local/.aitask-data/aitasks/metadata/stats_config.json"
BASE18="$(data_head "$TMP18")"
_mc "$TMP18" --expect "aitasks/metadata/stats_config.json=$TMP18/expected18" \
    aitasks/metadata/stats_config.json
assert_eq "18: exit 2" "2" "$MC_RC"
assert_contains "18: reported as changed, not as an absence" \
    "REFUSED:changed:aitasks/metadata/stats_config.json" "$MC_OUT"
assert_eq "18: the deletion was NOT committed" "$BASE18" "$(data_head "$TMP18")"

# --- Test 19: fail-closed completeness ------------------------------------
# A partially-guarded commit is the shape that looks safe and is not: the
# unguarded path is exactly where a racer's bytes would still be published.
echo "--- Test 19: --expect naming only SOME committable paths is refused ---"
TMP19="$(setup_repo)"
seed_tracked "$TMP19" "codeagent_config.json" '{"defaults":{}}'
(
    cd "$TMP19/local" || exit 1
    printf 'a\n' >> .aitask-data/aitasks/metadata/stats_config.json
    printf 'b\n' >> .aitask-data/aitasks/metadata/codeagent_config.json
)
cp "$TMP19/local/.aitask-data/aitasks/metadata/stats_config.json" "$TMP19/expected19"
BASE19="$(data_head "$TMP19")"
_mc "$TMP19" --expect "aitasks/metadata/stats_config.json=$TMP19/expected19" \
    aitasks/metadata/stats_config.json aitasks/metadata/codeagent_config.json

assert_eq "19: exit 2" "2" "$MC_RC"
assert_contains "19: refused as incomplete" "REFUSED:expect_incomplete" "$MC_OUT"
assert_eq "19: nothing was committed" "$BASE19" "$(data_head "$TMP19")"
assert_eq "19: nothing was left staged" "" "$(staged_paths "$TMP19")"

# An expectation for a path NOT being committed is the same programmer error.
_mc "$TMP19" \
    --expect "aitasks/metadata/stats_config.json=$TMP19/expected19" \
    --expect "aitasks/metadata/not_being_committed.json=$TMP19/expected19" \
    aitasks/metadata/stats_config.json
assert_eq "19: exit 2 for an expectation naming an uncommitted path" "2" "$MC_RC"
assert_contains "19: also refused as incomplete" "REFUSED:expect_incomplete" "$MC_OUT"

# --- Test 20: the guard does not disturb the pre-existing callers ----------
# settings_app / aitask_board / chatlink wizard all pass no --expect. Their path
# must be byte-for-byte the old behaviour, including on a raced file.
echo "--- Test 20: no --expect keeps the original contract ---"
TMP20="$(setup_repo)"
(cd "$TMP20/local" && printf 'edit\n' >> .aitask-data/aitasks/metadata/stats_config.json)
_mc "$TMP20" aitasks/metadata/stats_config.json
assert_eq "20: exit 0" "0" "$MC_RC"
assert_contains "20: committed exactly as before" \
    "COMMITTED:1:ait: Update stats_config.json" "$MC_OUT"
# And a user-layer path still SKIPs rather than being guarded into a refusal.
seed_ignores "$TMP20"
(cd "$TMP20/local" && printf '{}\n' > .aitask-data/aitasks/metadata/codeagent_config.local.json)
_mc "$TMP20" aitasks/metadata/codeagent_config.local.json
assert_contains "20: an ignored path is still SKIPPED" "SKIPPED:" "$MC_OUT"

# ==========================================================================
echo ""
echo "=== Results: $PASS passed, $FAIL failed (of $TOTAL) ==="
[[ "$FAIL" -eq 0 ]]
