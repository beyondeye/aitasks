#!/usr/bin/env bash
# test_task_commit_scoped.sh - a board task/plan commit carries ONLY its own
# paths, and stages only what it must (t1702).
#
# Run: bash tests/test_task_commit_scoped.sh
#
# Before this, `ait board` committed task files with a pathspec-less
# `git commit` against the SHARED .aitask-data index, so whatever another
# session had staged rode along under the board's message — the same defect
# class t1599 closed for `ait sync`, aitask_pick_own.sh, aitask_create.sh and
# aitask_fold_mark.sh.
#
# --- CHARACTERIZATION: `commit -o` pathspec classes -------------------------
# (pre-phase risk mitigation `probe_commit_o_pathspec_classes`, measured against
# a scratch repo before aitask_task_commit.sh's classification loop was written.
# VERIFIED ANSWERS, which is why the loop looks the way it does:)
#
#   tracked, deleted from worktree  → rc 0, deletion committed, EMPTY index.
#   tracked, present                → rc 0, worktree content committed.
#   untracked, present              → rc 1 "pathspec did not match any file(s)
#                                     known to git" — until it is staged.
#   untracked, absent               → rc 1, same error; staging cannot fix it,
#                                     and ONE such path aborts the WHOLE commit.
#   empty pathspec                  → rc 128, "No paths with --include/--only
#                                     does not make sense" (the fail-loud
#                                     counterpart to a bare `git commit`
#                                     silently taking the whole index).
#   In every successful case a FOREIGN staged entry survived untouched.
#
# --- Negative control -------------------------------------------------------
# Test 10 runs the pre-fix shape — a raw pathspec-less `git commit` — against
# the same fixture and asserts the defect is POSITIVELY present. A control whose
# injection silently failed cannot pass.
#
# --- What the cleanup tests each discriminate (verified by mutation) ---------
# Cleanup exists twice on purpose: inside ait_commit_paths_staging_untracked (so
# a caller that forgets the trap still unwinds on a normal failure return) and as
# the script's EXIT trap (for the exits the function cannot reach). Every row
# below was MEASURED by applying the mutation and re-running this file — none is
# reasoned:
#
#   mutation                                   | tests that fail
#   -------------------------------------------|-----------------------
#   delete the script's EXIT trap              | 9b, 9c
#   delete the library's inline cleanup        | (none — the trap masks it)
#   delete BOTH                                | 8, 9b, 9c
#   record ownership AFTER `add` instead of    | 9c
#     before it (the Change Request 1 defect)  |
#
# So: Test 8 pins that a cleanup mechanism exists at all; 9b and 9c BOTH pin the
# EXIT trap (they are signal tests — nothing else can unwind them), and 9c alone
# additionally pins the record-before-add ordering. The inline cleanup is
# deliberately not independently observable; it is what a future third caller
# that forgets the trap still gets. This note exists so the redundancy is not
# mistaken for an untested branch — and so the table is updated, not guessed at,
# whenever a test is added here.

set -uo pipefail

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/sync_fixture.sh
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"

COMMIT_SH="./.aitask-scripts/aitask_task_commit.sh"
BYSTANDER="aitasks/t20_beta.md"

# assert_non_empty <desc> <value> — the shared helpers have no non-empty form,
# and assert_not_contains "" can never pass (every string contains "").
assert_non_empty() {
    local desc="$1" value="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -n "$value" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected a non-empty value, got '')"
    fi
}

data_git() { local t="$1"; shift; git -C "$t/local/.aitask-data" "$@" 2>/dev/null; }
head_files() { data_git "$1" show --name-only --format= HEAD; }
staged() { data_git "$1" diff --cached --name-only; }
commit_count() { data_git "$1" rev-list --count HEAD; }

# Run the helper inside <tmpdir>'s clone; sets TC_OUT / TC_RC here.
_tc() {
    local tmpdir="$1"; shift
    TC_RC=0
    TC_OUT="$(
        cd "$tmpdir/local" || exit 99
        export PATH="$PWD/bin:$PATH" TEST_HOSTNAME=testhost
        "$COMMIT_SH" "$@" 2>&1
    )" || TC_RC=$?
}

# A concurrent session's in-flight edit: committed, then modified AND STAGED.
# This is the entry a pathspec-less commit swallows.
dirty_staged_bystander() {
    local t="$1"
    (
        cd "$t/local" || exit 1
        printf '\nMid-edit by another session.\n' >> "$BYSTANDER"
        git -C .aitask-data add -- "$BYSTANDER"
    ) >/dev/null 2>&1
}

echo "=== aitask_task_commit.sh: scoped commits, owned staging (t1702) ==="
echo ""

# --- Test 1: a new (untracked) task file commits; the bystander does not ----
echo "--- Test 1: create shape ---"
T1="$(setup_repo)"
dirty_staged_bystander "$T1"
printf -- '---\nstatus: Ready\n---\nNew.\n' > "$T1/local/aitasks/t40_delta.md"

_tc "$T1" -m "ait: Add t40" aitasks/t40_delta.md
assert_eq "Test 1: exit 0" "0" "$TC_RC"
assert_contains "Test 1: reports COMMITTED" "COMMITTED:1:ait: Add t40" "$TC_OUT"
assert_eq "Test 1: subject is the caller's message" \
    "ait: Add t40" "$(data_git "$T1" log -1 --format=%s)"
files1="$(head_files "$T1")"
assert_contains "Test 1: the new task file IS in the commit" \
    "aitasks/t40_delta.md" "$files1"
assert_not_contains "Test 1: the bystander is NOT in the commit" "t20_beta" "$files1"
assert_contains "Test 1: the bystander's staged entry survives" \
    "$BYSTANDER" "$(staged "$T1")"

# --- Test 2: deletions commit with NO `git rm` staging ----------------------
echo "--- Test 2: delete shape (worktree unlink only) ---"
T2="$(setup_repo)"
(cd "$T2/local" && printf 'plan\n' > aiplans/p10_alpha.md \
  && git -C .aitask-data add -- aiplans/p10_alpha.md \
  && git -C .aitask-data commit -q -m "seed plan") >/dev/null 2>&1
dirty_staged_bystander "$T2"
# The board unlinks; it does NOT `git rm`, so nothing of ours is staged.
rm -f "$T2/local/aitasks/t10_alpha.md" "$T2/local/aiplans/p10_alpha.md"
assert_not_contains "Test 2: precondition — our deletions are NOT staged" \
    "t10_alpha" "$(staged "$T2")"

_tc "$T2" -m "ait: Delete task t10 and associated files" \
    aitasks/t10_alpha.md aiplans/p10_alpha.md
assert_eq "Test 2: exit 0" "0" "$TC_RC"
files2="$(head_files "$T2")"
assert_contains "Test 2: the task deletion landed" "aitasks/t10_alpha.md" "$files2"
assert_contains "Test 2: the plan deletion landed" "aiplans/p10_alpha.md" "$files2"
assert_not_contains "Test 2: the bystander is NOT in the commit" "t20_beta" "$files2"
assert_contains "Test 2: the bystander's staged entry survives" \
    "$BYSTANDER" "$(staged "$T2")"

# --- Test 3: a rename commits both halves, with no explicit `git add` -------
echo "--- Test 3: rename shape ---"
T3="$(setup_repo)"
dirty_staged_bystander "$T3"
mv "$T3/local/aitasks/t30_gamma.md" "$T3/local/aitasks/t30_renamed.md"

_tc "$T3" -m "ait: Rename t30: renamed" aitasks/t30_gamma.md aitasks/t30_renamed.md
assert_eq "Test 3: exit 0" "0" "$TC_RC"
status3="$(data_git "$T3" show --name-status --format= HEAD)"
assert_contains "Test 3: the old path is recorded as deleted" \
    "aitasks/t30_gamma.md" "$status3"
assert_contains "Test 3: the new path is recorded as added" \
    "aitasks/t30_renamed.md" "$status3"
assert_not_contains "Test 3: the bystander is NOT in the commit" "t20_beta" "$status3"
assert_contains "Test 3: the bystander's staged entry survives" \
    "$BYSTANDER" "$(staged "$T3")"

# --- Test 4: out-of-scope paths are refused, and nothing is committed -------
echo "--- Test 4: scope refusals ---"
T4="$(setup_repo)"
before4="$(commit_count "$T4")"
for bad in "/etc/passwd" "aitasks/../README.md" "README.md" "../outside.md"; do
    _tc "$T4" -m "ait: nope" "$bad"
    assert_eq "Test 4: '$bad' exits 2" "2" "$TC_RC"
    assert_contains "Test 4: '$bad' is refused" "REFUSED:out_of_scope:" "$TC_OUT"
done
assert_eq "Test 4: no commit was made" "$before4" "$(commit_count "$T4")"

# --- Test 5: no paths / no message never reaches a commit ------------------
echo "--- Test 5: empty invocations ---"
T5="$(setup_repo)"
before5="$(commit_count "$T5")"
_tc "$T5" -m "ait: nothing"
assert_eq "Test 5: no paths exits 2" "2" "$TC_RC"
assert_contains "Test 5: no paths prints usage" "Usage:" "$TC_OUT"
_tc "$T5" aitasks/t10_alpha.md
assert_eq "Test 5: no message exits 2" "2" "$TC_RC"
assert_eq "Test 5: no commit was made" "$before5" "$(commit_count "$T5")"

# --- Test 6: a path git never knew is skipped, not fatal -------------------
echo "--- Test 6: unknown path is skipped ---"
T6="$(setup_repo)"
(cd "$T6/local" && printf 'edit\n' >> aitasks/t10_alpha.md)
_tc "$T6" -m "ait: Update t10" aitasks/t10_alpha.md aitasks/t99_never_existed.md
assert_eq "Test 6: exit 0 — the known path still commits" "0" "$TC_RC"
assert_contains "Test 6: the unknown path is reported skipped" \
    "SKIPPED:unknown:aitasks/t99_never_existed.md" "$TC_OUT"
assert_contains "Test 6: the known path landed" \
    "aitasks/t10_alpha.md" "$(head_files "$T6")"

echo "--- Test 6b: only-unknown paths report NOCHANGE ---"
before6b="$(commit_count "$T6")"
_tc "$T6" -m "ait: ghosts" aitasks/t98_ghost.md
assert_eq "Test 6b: exit 2" "2" "$TC_RC"
assert_contains "Test 6b: reports NOCHANGE" "NOCHANGE" "$TC_OUT"
assert_eq "Test 6b: no commit was made" "$before6b" "$(commit_count "$T6")"

# --- Test 7: a clean path set reports NOCHANGE -----------------------------
echo "--- Test 7: nothing to commit ---"
T7="$(setup_repo)"
before7="$(commit_count "$T7")"
_tc "$T7" -m "ait: no-op" aitasks/t10_alpha.md
assert_eq "Test 7: exit 2" "2" "$TC_RC"
assert_contains "Test 7: reports NOCHANGE" "NOCHANGE" "$TC_OUT"
assert_eq "Test 7: no commit was made" "$before7" "$(commit_count "$T7")"

# --- Test 8: a PARTIAL staging failure leaves nothing of ours staged --------
# Fault injected through a documented seam: `git add` refuses a path matched by
# .gitignore. The first path stages, the second cannot — and the cleanup must
# unwind the first rather than leaving it for someone else's commit to collect.
echo "--- Test 8: partial staging failure ---"
T8="$(setup_repo)"
(
    cd "$T8/local" || exit 1
    printf 'aitasks/ignored_*.md\n' > .aitask-data/.gitignore
    git -C .aitask-data add -- .gitignore
    git -C .aitask-data commit -q -m "seed gitignore"
) >/dev/null 2>&1
dirty_staged_bystander "$T8"
printf -- '---\nstatus: Ready\n---\nA\n' > "$T8/local/aitasks/t50_first.md"
printf -- '---\nstatus: Ready\n---\nB\n' > "$T8/local/aitasks/ignored_second.md"
before8="$(commit_count "$T8")"

_tc "$T8" -m "ait: two new files" aitasks/t50_first.md aitasks/ignored_second.md
assert_eq "Test 8: exit 1" "1" "$TC_RC"
assert_contains "Test 8: reports FAILED" "FAILED:" "$TC_OUT"
assert_eq "Test 8: no commit was made" "$before8" "$(commit_count "$T8")"
staged8="$(staged "$T8")"
assert_not_contains "Test 8: the path we staged was unstaged again" \
    "t50_first" "$staged8"
assert_contains "Test 8: the FOREIGN staged entry is untouched" \
    "$BYSTANDER" "$staged8"

# --- Test 9: an ABORTED run leaves nothing staged --------------------------
# assert_data_worktree_clean() DIES — exiting the process — on a wedged data
# worktree, and it is reached from `add`/`commit`/`reset` but not from the
# read-only `ls-files`. The pre-flight must fire BEFORE the staging loop, or the
# die lands mid-loop with entries already in the shared index.
echo "--- Test 9: aborted run (wedged data worktree) ---"
T9="$(setup_repo)"
dirty_staged_bystander "$T9"
printf -- '---\nstatus: Ready\n---\nA\n' > "$T9/local/aitasks/t60_first.md"
printf -- '---\nstatus: Ready\n---\nB\n' > "$T9/local/aitasks/t61_second.md"
gitdir9="$(cd "$T9/local" && git -C .aitask-data rev-parse --absolute-git-dir)"
: > "$gitdir9/MERGE_HEAD"
before9="$(commit_count "$T9")"

_tc "$T9" -m "ait: two new files" aitasks/t60_first.md aitasks/t61_second.md
assert_non_empty "Test 9: the run aborted (non-zero exit)" \
    "$([[ "$TC_RC" -ne 0 ]] && echo "rc=$TC_RC")"
assert_contains "Test 9: the guard's own message is what aborted the run" \
    "Data worktree (.aitask-data) is stuck mid-MERGE_HEAD" "$TC_OUT"
assert_eq "Test 9: no commit was made" "$before9" "$(commit_count "$T9")"
staged9="$(staged "$T9")"
assert_not_contains "Test 9: nothing of ours was staged" "t60_first" "$staged9"
assert_not_contains "Test 9: nothing of ours was staged" "t61_second" "$staged9"
assert_contains "Test 9: the FOREIGN staged entry is untouched" \
    "$BYSTANDER" "$staged9"
rm -f "$gitdir9/MERGE_HEAD"

# --- Test 9b: a run KILLED after staging leaves nothing staged -------------
# The discriminating case for the EXIT trap. Tests 8 and 9 both abort at a point
# the function's own cleanup can still reach; only a signal arriving *between*
# the staging loop and the commit escapes it. Injected through the fixture's own
# PATH-shim seam (the one it already uses for `hostname`): a `git` shim that
# passes everything through, but SIGTERMs the helper when the commit is
# attempted — i.e. with the untracked path already staged.
#
# Measured while writing this: bash runs an EXIT trap on a fatal SIGTERM even at
# default disposition, so the EXIT trap alone carries this case and the helper
# ships no INT/TERM handler. Verified discriminating: deleting the EXIT trap
# fails the "unwound" assertion below (and Test 9c's — see the mutation table).
echo "--- Test 9b: killed after staging ---"
T9B="$(setup_repo)"
dirty_staged_bystander "$T9B"
printf -- '---\nstatus: Ready\n---\nA\n' > "$T9B/local/aitasks/t70_first.md"
REAL_GIT="$(command -v git)"
cat > "$T9B/local/bin/git" <<SHIM
#!/usr/bin/env bash
for a in "\$@"; do
    if [[ "\$a" == "commit" ]]; then
        kill -TERM "\$PPID"
        exit 143
    fi
done
exec "$REAL_GIT" "\$@"
SHIM
chmod +x "$T9B/local/bin/git"
before9b="$(commit_count "$T9B")"

_tc "$T9B" -m "ait: Add t70" aitasks/t70_first.md
rm -f "$T9B/local/bin/git"   # off PATH before the assertions read git state

assert_eq "Test 9b: the run was killed (143)" "143" "$TC_RC"
assert_eq "Test 9b: no commit was made" "$before9b" "$(commit_count "$T9B")"
staged9b="$(staged "$T9B")"
assert_not_contains "Test 9b: the staged path was unwound by the trap" \
    "t70_first" "$staged9b"
assert_contains "Test 9b: the FOREIGN staged entry is untouched" \
    "$BYSTANDER" "$staged9b"

# --- Test 9c: killed BETWEEN the add and the ownership record --------------
# The narrow window Test 9b cannot see. Ownership must be recorded BEFORE the
# mutating `add`, not after it: a signal landing in between runs the EXIT trap
# with an empty ownership list, and the path git has already staged is left in
# the shared index for someone else's commit to collect.
#
# Recording first is safe because `git reset -- <paths>` tolerates a path it
# never staged (verified: rc 0, the genuinely staged entries in the same set are
# still unstaged, and the worktree is untouched) — so the one case this
# over-records, an `add` that then failed, costs nothing.
#
# Same PATH-shim seam as Test 9b, moved one step earlier: the shim runs the real
# `add`, THEN signals, so the kill lands exactly in the window.
echo "--- Test 9c: killed between the add and the ownership record ---"
T9C="$(setup_repo)"
dirty_staged_bystander "$T9C"
printf -- '---\nstatus: Ready\n---\nA\n' > "$T9C/local/aitasks/t80_first.md"
REAL_GIT="$(command -v git)"
cat > "$T9C/local/bin/git" <<SHIM
#!/usr/bin/env bash
for a in "\$@"; do
    if [[ "\$a" == "add" ]]; then
        "$REAL_GIT" "\$@"; rc=\$?
        kill -TERM "\$PPID"
        exit \$rc
    fi
done
exec "$REAL_GIT" "\$@"
SHIM
chmod +x "$T9C/local/bin/git"
before9c="$(commit_count "$T9C")"

_tc "$T9C" -m "ait: Add t80" aitasks/t80_first.md
rm -f "$T9C/local/bin/git"

assert_eq "Test 9c: no commit was made" "$before9c" "$(commit_count "$T9C")"
staged9c="$(staged "$T9C")"
assert_not_contains "Test 9c: the just-added path was unwound by the trap" \
    "t80_first" "$staged9c"
assert_contains "Test 9c: the FOREIGN staged entry is untouched" \
    "$BYSTANDER" "$staged9c"

# --- Test 10: NEGATIVE CONTROL — the pre-fix shape sweeps the bystander -----
# Asserts the defect POSITIVELY: if this stopped reproducing, every assertion
# above would be measuring nothing.
echo "--- Test 10: NEGATIVE CONTROL — pathspec-less commit ---"
T10="$(setup_repo)"
dirty_staged_bystander "$T10"
printf -- '---\nstatus: Ready\n---\nNew.\n' > "$T10/local/aitasks/t40_delta.md"
(
    cd "$T10/local" || exit 1
    # Exactly what the three board sites did before t1702: stage our own path,
    # then commit with no pathspec.
    git -C .aitask-data add -- aitasks/t40_delta.md
    git -C .aitask-data commit -q -m "ait: Add t40"
) >/dev/null 2>&1
files10="$(head_files "$T10")"
assert_contains "Test 10: pre-fix DOES commit our own file" \
    "aitasks/t40_delta.md" "$files10"
assert_contains "Test 10: pre-fix DOES sweep the bystander" "t20_beta" "$files10"
assert_eq "Test 10: pre-fix leaves the bystander's entry consumed" \
    "" "$(staged "$T10")"

# --- Test 11: syntax --------------------------------------------------------
echo "--- Test 11: syntax ---"
bash -n "$PROJECT_DIR/.aitask-scripts/aitask_task_commit.sh"
assert_eq "Test 11: aitask_task_commit.sh parses" "0" "$?"
bash -n "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
assert_eq "Test 11: task_utils.sh parses" "0" "$?"
bash -n "$PROJECT_DIR/.aitask-scripts/aitask_metadata_commit.sh"
assert_eq "Test 11: aitask_metadata_commit.sh parses" "0" "$?"

# --- Summary ---
echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
echo "========================================="
[[ "$FAIL" -eq 0 ]]
