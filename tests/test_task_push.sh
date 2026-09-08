#!/usr/bin/env bash
# test_task_push.sh - Automated tests for task_push/task_sync retry-rebase logic
# Run: bash tests/test_task_push.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

# --- Test helpers ---

assert_success() {
    local desc="$1" exit_code="$2"
    TOTAL=$((TOTAL + 1))
    if [[ "$exit_code" -eq 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected exit 0, got $exit_code)"
    fi
}

cleanup() {
    for d in "${CLEANUP_DIRS[@]}"; do
        rm -rf "$d" 2>/dev/null
    done
}
trap cleanup EXIT

# --- Git setup helpers ---

# Create a bare "remote" repo and a "local" clone.
# Sets: TEST_REMOTE, TEST_LOCAL, TEST_TMPDIR
setup_remote_and_clone() {
    TEST_TMPDIR="$(mktemp -d "${TMPDIR:-/tmp}/ait_push_test_XXXXXX")"
    CLEANUP_DIRS+=("$TEST_TMPDIR")
    TEST_REMOTE="$TEST_TMPDIR/remote.git"
    TEST_LOCAL="$TEST_TMPDIR/local"

    git init --bare --quiet "$TEST_REMOTE"
    git clone --quiet "$TEST_REMOTE" "$TEST_LOCAL" 2>/dev/null
    git -C "$TEST_LOCAL" config user.email "test@test.com"
    git -C "$TEST_LOCAL" config user.name "Test"

    # Initial commit so we have a branch
    echo "init" > "$TEST_LOCAL/init.txt"
    git -C "$TEST_LOCAL" add init.txt
    git -C "$TEST_LOCAL" commit -m "init" --quiet
    git -C "$TEST_LOCAL" push --quiet 2>/dev/null
}

# Advance the remote via a second clone (simulates another user pushing)
advance_remote() {
    local filename="${1:-other_user_file.txt}"
    local other_tmpdir
    other_tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ait_push_other_XXXXXX")"
    local other_dir="$other_tmpdir/other"

    git clone --quiet "$TEST_REMOTE" "$other_dir" 2>/dev/null
    git -C "$other_dir" config user.email "other@test.com"
    git -C "$other_dir" config user.name "Other"
    echo "other user change" > "$other_dir/$filename"
    git -C "$other_dir" add "$filename"
    git -C "$other_dir" commit -m "other user commit" --quiet
    git -C "$other_dir" push --quiet 2>/dev/null

    rm -rf "$other_tmpdir"
}

# --- t1725_1 helpers -------------------------------------------------------

# Commit <file> locally, then push a DIFFERENT body for the same file from a
# second clone. The next `pull --rebase` is then guaranteed to stop on a
# content conflict. Mirrors the inline fixture Test 19 has always used.
force_remote_conflict() {
    local file="${1:-conflict.txt}" tmp
    echo "local" > "$file"
    git add "$file"
    git commit -m "local conflicting commit" --quiet

    tmp="$(mktemp -d "${TMPDIR:-/tmp}/ait_push_conflict_XXXXXX")"
    git clone --quiet "$TEST_REMOTE" "$tmp/other" 2>/dev/null
    git -C "$tmp/other" config user.email "other@test.com"
    git -C "$tmp/other" config user.name "Other"
    echo "remote" > "$tmp/other/$file"
    git -C "$tmp/other" add "$file"
    git -C "$tmp/other" commit -m "remote conflicting commit" --quiet
    git -C "$tmp/other" push --quiet 2>/dev/null
    rm -rf "$tmp"
}

# Echo the in-progress state present in <gitdir> (or the cwd's), or "" when
# clean. Deliberately re-implemented from `ls` rather than calling the library
# helper under test — a probe that shares the implementation it is checking
# cannot detect that implementation being wrong.
probe_wedge() {
    local gd="${1:-}" s
    [[ -z "$gd" ]] && gd="$(git rev-parse --git-dir 2>/dev/null || echo .git)"
    for s in rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD BISECT_LOG; do
        [[ -e "$gd/$s" ]] && { printf '%s' "$s"; return 0; }
    done
    printf ''
}

# Assert that a later task_git commit succeeds — the literal AC3 clause
# ("the task's next ./ait git commit succeeds"), which is what a leftover
# rebase-merge breaks via assert_data_worktree_clean.
assert_next_commit_succeeds() {
    local desc="$1" name="ac3_probe_$$_${RANDOM}.txt" wt
    # task_git runs `git -C "$_AIT_DATA_WORKTREE"`, so the probe file has to be
    # created inside that worktree — in branch mode that is not the cwd.
    wt="${_AIT_DATA_WORKTREE:-.}"
    echo "after-recovery" > "$wt/$name"
    local out rc=0
    TOTAL=$((TOTAL + 1))
    out="$(task_git add "$name" 2>&1)" || rc=$?
    if [[ $rc -eq 0 ]]; then
        out="$(task_git commit -m "ait: AC3 probe" --quiet 2>&1)" || rc=$?
    fi
    if [[ $rc -eq 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        # Say WHY: a bare "was refused" cannot distinguish the wedge this
        # assertion exists to detect from a broken fixture.
        echo "FAIL: $desc (rc=$rc, worktree='$wt': ${out:-<no output>})"
    fi
}

# Setup branch mode: move TEST_LOCAL into a .aitask-data subdirectory
# Sets: TEST_MAIN_DIR (the parent directory to cd into)
setup_branch_mode() {
    TEST_MAIN_DIR="$TEST_TMPDIR/main_repo"
    mkdir -p "$TEST_MAIN_DIR"
    mv "$TEST_LOCAL" "$TEST_MAIN_DIR/.aitask-data"
    TEST_LOCAL="$TEST_MAIN_DIR/.aitask-data"
}

# Source task_utils.sh functions, resetting state
reload_task_utils() {
    unset _AIT_TASK_UTILS_LOADED
    _AIT_DATA_WORKTREE=""
    SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
    source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
    set +euo pipefail
}

# --- Setup ---
reload_task_utils

echo "=== task_push / task_sync Retry-Rebase Tests ==="
echo ""

# --- Test 1: task_push clean push (legacy mode) ---
echo "--- Test 1: task_push clean push (legacy mode) ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

echo "local change" > local_file.txt
git add local_file.txt
git commit -m "local commit" --quiet

task_push
push_rc=$?

assert_success "task_push returns 0" "$push_rc"
assert_eq "TASK_PUSH_STATUS is pushed" "pushed" "$TASK_PUSH_STATUS"
remote_count=$(git -C "$TEST_REMOTE" rev-list --count HEAD)
assert_eq_trim "Remote has 2 commits" "2" "$remote_count"

popd > /dev/null || exit 1

# --- Test 2: task_push clean push (branch mode) ---
echo "--- Test 2: task_push clean push (branch mode) ---"

setup_remote_and_clone
setup_branch_mode
pushd "$TEST_MAIN_DIR" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE=".aitask-data"

echo "branch mode change" > .aitask-data/branch_file.txt
git -C .aitask-data add branch_file.txt
git -C .aitask-data commit -m "branch mode commit" --quiet

task_push
push_rc=$?

assert_success "task_push returns 0 (branch mode)" "$push_rc"
remote_count=$(git -C "$TEST_REMOTE" rev-list --count HEAD)
assert_eq_trim "Remote has 2 commits (branch mode)" "2" "$remote_count"

popd > /dev/null || exit 1

# --- Test 3: task_push auto-rebases on conflict (legacy mode) ---
echo "--- Test 3: task_push auto-rebases on conflict (legacy mode) ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

echo "local change" > my_file.txt
git add my_file.txt
git commit -m "local commit" --quiet

advance_remote "remote_file.txt"

task_push
push_rc=$?

assert_success "task_push returns 0 after rebase" "$push_rc"
assert_eq "TASK_PUSH_STATUS is pushed after rebase" "pushed" "$TASK_PUSH_STATUS"
remote_count=$(git -C "$TEST_REMOTE" rev-list --count HEAD)
assert_eq_trim "Remote has 3 commits after rebase" "3" "$remote_count"

popd > /dev/null || exit 1

# --- Test 4: task_push auto-rebases on conflict (branch mode) ---
echo "--- Test 4: task_push auto-rebases on conflict (branch mode) ---"

setup_remote_and_clone
setup_branch_mode
pushd "$TEST_MAIN_DIR" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE=".aitask-data"

echo "local branch change" > .aitask-data/my_file.txt
git -C .aitask-data add my_file.txt
git -C .aitask-data commit -m "branch mode local commit" --quiet

advance_remote "remote_file.txt"

task_push
push_rc=$?

assert_success "task_push returns 0 after rebase (branch mode)" "$push_rc"
remote_count=$(git -C "$TEST_REMOTE" rev-list --count HEAD)
assert_eq_trim "Remote has 3 commits after rebase (branch mode)" "3" "$remote_count"

popd > /dev/null || exit 1

# --- Test 5: task_push returns 0 even when all retries fail ---
echo "--- Test 5: task_push returns 0 when all retries fail ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

echo "will not push" > orphan.txt
git add orphan.txt
git commit -m "orphan commit" --quiet

git remote set-url origin /nonexistent/path/repo.git

# Capture stderr to a FILE, not via "$(...)": command substitution runs in a
# subshell and would discard the TASK_PUSH_* globals the assertions below read.
task_push 2>"$TEST_TMPDIR/push_err.txt"
push_rc=$?
push_err="$(cat "$TEST_TMPDIR/push_err.txt")"

assert_success "task_push returns 0 even on total failure" "$push_rc"
assert_eq "TASK_PUSH_STATUS is failed" "failed" "$TASK_PUSH_STATUS"
assert_eq "TASK_PUSH_REASON is remote_unreachable" "remote_unreachable" "$TASK_PUSH_REASON"
assert_contains "warning names the stranded commit count" "1 commit(s) not pushed" "$push_err"

popd > /dev/null || exit 1

# --- Test 6: task_sync uses rebase (legacy mode) ---
echo "--- Test 6: task_sync uses rebase (legacy mode) ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

echo "local unpushed" > local_sync.txt
git add local_sync.txt
git commit -m "local unpushed commit" --quiet

advance_remote "remote_sync.txt"

task_sync

assert_eq "TASK_SYNC_STATUS is synced" "synced" "$TASK_SYNC_STATUS"
local_count=$(git rev-list --count HEAD)
assert_eq_trim "Local has 3 commits after sync rebase" "3" "$local_count"

top_msg=$(git log --format='%s' -1)
assert_eq_trim "Local commit is on top after rebase" "local unpushed commit" "$top_msg"

popd > /dev/null || exit 1

# --- Test 7: task_sync uses rebase (branch mode) ---
echo "--- Test 7: task_sync uses rebase (branch mode) ---"

setup_remote_and_clone
setup_branch_mode
pushd "$TEST_MAIN_DIR" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE=".aitask-data"

echo "local unpushed branch" > .aitask-data/local_sync.txt
git -C .aitask-data add local_sync.txt
git -C .aitask-data commit -m "local unpushed commit" --quiet

advance_remote "remote_sync.txt"

task_sync

assert_eq "TASK_SYNC_STATUS is synced (branch mode)" "synced" "$TASK_SYNC_STATUS"
local_count=$(git -C .aitask-data rev-list --count HEAD)
assert_eq_trim "Local has 3 commits after sync rebase (branch mode)" "3" "$local_count"

top_msg=$(git -C .aitask-data log --format='%s' -1)
assert_eq_trim "Local commit on top after rebase (branch mode)" "local unpushed commit" "$top_msg"

popd > /dev/null || exit 1

# --- Test 8: ait git push dispatcher intercept ---
echo "--- Test 8: ait git push dispatcher intercept ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1

# Create minimal ait dispatcher structure pointing to real scripts
setup_fake_aitask_repo "$PWD"
cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/ait" ./ait
chmod +x ./ait

echo "local for ait push" > ait_push_file.txt
git add ait_push_file.txt .aitask-scripts/ ait
git commit -m "local with ait" --quiet

advance_remote "remote_ait.txt"

./ait git push
ait_rc=$?

assert_success "ait git push returns 0 after conflict" "$ait_rc"
remote_count=$(git -C "$TEST_REMOTE" rev-list --count HEAD)
assert_eq_trim "Remote has 3 commits via ait git push" "3" "$remote_count"

popd > /dev/null || exit 1

# --- Test 9: ait git <other> passes through ---
echo "--- Test 9: ait git <other> passes through ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1

setup_fake_aitask_repo "$PWD"
cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/ait" ./ait
chmod +x ./ait
git add .aitask-scripts/ ait
git commit -m "add ait scripts" --quiet
git push --quiet 2>/dev/null

status_output=$(./ait git status 2>&1)
status_rc=$?
assert_success "ait git status returns 0" "$status_rc"

log_output=$(./ait git log --oneline -1 2>&1)
log_rc=$?
assert_success "ait git log returns 0" "$log_rc"
assert_contains "ait git log shows commit" "add ait scripts" "$log_output"

popd > /dev/null || exit 1

# --- Test 10: failure classifier (pure unit — fixtures, no git) ---
echo "--- Test 10: _task_push_classify reason codes ---"

reload_task_utils

reject_err="To /tmp/remote.git
 ! [rejected]        master -> master (non-fast-forward)
error: failed to push some refs to '/tmp/remote.git'"

assert_eq "classify: dirty worktree blocks the rebase fallback" "dirty_worktree" \
    "$(_task_push_classify "$reject_err" "error: cannot pull with rebase: You have unstaged changes.")"

# Discriminator: the push rejection is only the symptom. When BOTH signals are
# present the blocker must win, otherwise the hint sends the user to the wrong
# recovery (reconcile the remote instead of cleaning the worktree).
assert_eq "classify: blocker beats the push rejection" "dirty_worktree" \
    "$(_task_push_classify "$reject_err" "error: cannot pull with rebase: You have unstaged changes.
hint: fetch first")"

assert_eq "classify: rebase stopped on conflicts" "rebase_conflict" \
    "$(_task_push_classify "$reject_err" "CONFLICT (content): Merge conflict in t42.md
error: could not apply 1a2b3c4... local commit")"

# --- t1725_1: _task_pull_rebase's own sentinels ---
# These are contract text: the classifier is the only consumer, and the hint the
# user sees is chosen from the code it returns.
sent_locked="aitask: another session is reconciling the task data right now; pull skipped"
sent_inprog="aitask: a rebase is already in progress in the data worktree (rebase-merge)"
sent_stillin="aitask: rebase --abort failed - a rebase is still in progress in the data worktree"
sent_foreign="aitask: a rebase started outside this pull is in progress in the data worktree - leaving it untouched"
sent_appeared="aitask: a rebase appeared in the data worktree during a pull that failed for another reason - leaving it untouched"
sent_midop="aitask: the data worktree is mid-MERGE_HEAD; leaving it untouched"
sent_aborted="aitask: rebase aborted after conflict - worktree restored, local commits kept"
conflict_text="CONFLICT (content): Merge conflict in t42.md
error: could not apply 1a2b3c4... local commit"

assert_eq "classify: pull skipped because another session holds the lock" "pull_locked" \
    "$(_task_push_classify "" "$sent_locked")"
assert_eq "classify: a rebase was already in progress" "rebase_in_progress" \
    "$(_task_push_classify "" "$sent_inprog")"
assert_eq "classify: the abort did not land" "rebase_in_progress" \
    "$(_task_push_classify "" "$sent_stillin")"
assert_eq "classify: someone else's rebase" "rebase_in_progress" \
    "$(_task_push_classify "" "$sent_foreign")"
assert_eq "classify: a rebase appeared during an unrelated failure" "rebase_in_progress" \
    "$(_task_push_classify "" "$sent_appeared")"
assert_eq "classify: a non-rebase mid-operation" "data_midop" \
    "$(_task_push_classify "" "$sent_midop")"
# The abort sentinel means the rebase is GONE: it must stay rebase_conflict, so
# the hint tells the user to reconcile rather than to abort something.
assert_eq "classify: an aborted conflict is still rebase_conflict" "rebase_conflict" \
    "$(_task_push_classify "" "${conflict_text}
${sent_aborted}")"

# Ordering. task_push accumulates every attempt's output, so these blobs are the
# real shape: attempt 1 conflicts, attempt 2 finds what it left behind.
assert_eq "classify: in-progress beats a co-occurring conflict" "rebase_in_progress" \
    "$(_task_push_classify "" "${conflict_text}
${sent_stillin}")"
assert_eq "classify: pull_locked beats everything — no pull was attempted" "pull_locked" \
    "$(_task_push_classify "" "${sent_locked}
${conflict_text}
${sent_inprog}")"
# Git's own "already a rebase-merge directory" text keeps its historical
# rebase_conflict verdict when no sentinel accompanies it (nothing else changed).
assert_eq "classify: git's bare rebase-merge text is unchanged" "rebase_conflict" \
    "$(_task_push_classify "" "fatal: It seems that there is already a rebase-merge directory")"

assert_eq "classify: remote unreachable" "remote_unreachable" \
    "$(_task_push_classify "fatal: '/nonexistent/path/repo.git' does not appear to be a git repository" "")"

assert_eq "classify: diverged with no rebase blocker" "diverged" \
    "$(_task_push_classify " ! [rejected]        master -> master (fetch first)" "")"

assert_eq "classify: unrecognised output falls back to unknown" "unknown" \
    "$(_task_push_classify "fatal: something nobody has seen before" "")"

# Each code must map to a distinct, non-empty hint.
assert_contains "hint: dirty worktree points at the syncer" "ait syncer" \
    "$(_task_push_reason_hint dirty_worktree)"
# Since t1725_1 a conflicted pull aborts itself, so rebase_conflict means the
# rebase is GONE and the two sides still diverge. Naming 'rebase --abort' here
# would advertise a recovery for a state that no longer exists — so this
# assertion is the inverse of the one it replaces, and both halves matter.
assert_contains "hint: rebase conflict says the rebase was aborted" \
    "was aborted (nothing left in progress)" \
    "$(_task_push_reason_hint rebase_conflict)"
TOTAL=$((TOTAL + 1))
if [[ "$(_task_push_reason_hint rebase_conflict)" == *"rebase --abort"* ]]; then
    FAIL=$((FAIL + 1))
    echo "FAIL: rebase_conflict hint still advertises 'rebase --abort' for a rebase that was already aborted"
else
    PASS=$((PASS + 1))
fi

# The three codes t1725_1 adds. Each names a recovery that matches its state:
# only the rebase one may say 'rebase --abort'.
assert_contains "hint: rebase in progress offers the abort/continue pair" \
    "./ait git rebase --abort" "$(_task_push_reason_hint rebase_in_progress)"
assert_contains "hint: rebase in progress says what --abort discards" \
    "discards only the partially replayed remote commits" \
    "$(_task_push_reason_hint rebase_in_progress)"
assert_contains "hint: data_midop points at git-health for the exact state" \
    "./ait git-health" "$(_task_push_reason_hint data_midop)"
# Discriminator: a merge / cherry-pick / revert / bisect must NOT be handed a
# rebase remedy. This is the assertion that fails if data_midop is ever folded
# back into rebase_in_progress.
TOTAL=$((TOTAL + 1))
if [[ "$(_task_push_reason_hint data_midop)" == *"rebase"* ]]; then
    FAIL=$((FAIL + 1))
    echo "FAIL: data_midop hint mentions a rebase, but the state is not one"
else
    PASS=$((PASS + 1))
fi
assert_contains "hint: pull_locked says nothing was changed" \
    "nothing was changed" "$(_task_push_reason_hint pull_locked)"

assert_contains "hint: unreachable remote mentions connectivity" "connectivity" \
    "$(_task_push_reason_hint remote_unreachable)"

# A configured remote with no upstream for the current branch: both git
# directions have their own wording, and both must reach the same code.
assert_eq "classify: pull with no tracking information" "no_upstream" \
    "$(_task_push_classify "" "There is no tracking information for the current branch.
Please specify which branch you want to rebase against.")"
assert_eq "classify: push with no upstream branch" "no_upstream" \
    "$(_task_push_classify "fatal: The current branch data has no upstream branch." "")"
assert_contains "hint: no upstream names the one-command fix" \
    "./ait git branch --set-upstream-to=origin/<branch>" \
    "$(_task_push_reason_hint no_upstream)"

# Discriminator: the recovery MUST route through the './ait git' gateway. In
# branch mode the branch needing an upstream is aitask-data inside
# .aitask-data; a bare `git branch --set-upstream-to=...` typed at the repo
# root would retarget the CODE branch and leave every later sync failing.
# Strip the gateway form, then assert no bare `git branch` survives.
noups_hint="$(_task_push_reason_hint no_upstream)"
TOTAL=$((TOTAL + 1))
if [[ "${noups_hint//.\/ait git branch/}" == *"git branch"* ]]; then
    FAIL=$((FAIL + 1))
    echo "FAIL: no_upstream hint suggests a bare 'git branch' (must use './ait git')"
else
    PASS=$((PASS + 1))
fi

# The sync path reuses the classifier with an EMPTY push argument — the verdict
# must not depend on that argument being populated.
assert_eq "classify (sync shape): dirty worktree" "dirty_worktree" \
    "$(_task_push_classify "" "error: cannot pull with rebase: You have unstaged changes.")"
assert_eq "classify (sync shape): rebase conflict" "rebase_conflict" \
    "$(_task_push_classify "" "CONFLICT (content): Merge conflict in t42.md")"
assert_eq "classify (sync shape): remote unreachable" "remote_unreachable" \
    "$(_task_push_classify "" "fatal: '/nonexistent/repo.git' does not appear to be a git repository")"

# The hint table is shared, so the retry command must be caller-selectable:
# a failed PULL must not send the user to the push recovery.
assert_contains "hint: default retry command is the push" "./ait git push" \
    "$(_task_push_reason_hint remote_unreachable)"
assert_contains "hint: sync caller gets the sync retry command" "./ait sync" \
    "$(_task_push_reason_hint remote_unreachable "./ait sync")"
sync_hint="$(_task_push_reason_hint remote_unreachable "./ait sync")"
if [[ "$sync_hint" == *"./ait git push"* ]]; then
    TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
    echo "FAIL: sync hint must not also name the push command"
else
    TOTAL=$((TOTAL + 1)); PASS=$((PASS + 1))
fi

# --- Test 11: origin ahead + dirty data worktree (the live t635_27 failure) ---
echo "--- Test 11: dirty worktree blocks rebase — reported, not silent ---"

setup_remote_and_clone
setup_branch_mode
pushd "$TEST_MAIN_DIR" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE=".aitask-data"

# Pin the outcome regardless of the developer's global git config.
git -C .aitask-data config rebase.autoStash false

echo "local branch change" > .aitask-data/my_file.txt
git -C .aitask-data add my_file.txt
git -C .aitask-data commit -m "branch mode local commit" --quiet

advance_remote "remote_file.txt"

# Another session's uncommitted edit to a TRACKED file: this is what
# permanently blocks the pull --rebase fallback on a shared checkout.
echo "another session's in-flight edit" >> .aitask-data/init.txt

task_push 2>"$TEST_TMPDIR/dirty_err.txt"
push_rc=$?
dirty_err="$(cat "$TEST_TMPDIR/dirty_err.txt")"

assert_success "task_push still returns 0 (best-effort contract)" "$push_rc"
assert_eq "TASK_PUSH_STATUS is failed" "failed" "$TASK_PUSH_STATUS"
assert_eq "TASK_PUSH_REASON is dirty_worktree" "dirty_worktree" "$TASK_PUSH_REASON"
assert_eq "TASK_PUSH_UNPUSHED counts the stranded commit" "1" "$TASK_PUSH_UNPUSHED"
assert_contains "warning names the stranded commit count" "1 commit(s) not pushed" "$dirty_err"
assert_contains "warning names the actual blocker" "unstaged changes" "$dirty_err"
assert_contains "warning names the recovery path" "ait syncer" "$dirty_err"

# Nothing reached the remote — this is exactly the state that used to be
# indistinguishable from success.
remote_count=$(git -C "$TEST_REMOTE" rev-list --count HEAD)
assert_eq_trim "Remote unchanged: nothing was pushed" "2" "$remote_count"

popd > /dev/null || exit 1

# --- Test 12: nothing to push stays silent ---
echo "--- Test 12: nothing to push -> up-to-date, no warning ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

task_push 2>"$TEST_TMPDIR/uptodate_err.txt"
push_rc=$?
uptodate_err="$(cat "$TEST_TMPDIR/uptodate_err.txt")"

assert_success "task_push returns 0 with nothing to push" "$push_rc"
assert_eq "TASK_PUSH_STATUS is up-to-date" "up-to-date" "$TASK_PUSH_STATUS"
assert_eq "no warning when nothing is stranded" "" "$uptodate_err"

popd > /dev/null || exit 1

# --- Test 13: no remote configured stays silent ---
echo "--- Test 13: no remote -> no-remote, no warning ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

git remote remove origin
echo "local only" > solo.txt
git add solo.txt
git commit -m "solo commit" --quiet

task_push 2>"$TEST_TMPDIR/noremote_err.txt"
push_rc=$?
noremote_err="$(cat "$TEST_TMPDIR/noremote_err.txt")"

assert_success "task_push returns 0 with no remote" "$push_rc"
assert_eq "TASK_PUSH_STATUS is no-remote" "no-remote" "$TASK_PUSH_STATUS"
assert_eq "solo repos stay silent" "" "$noremote_err"

popd > /dev/null || exit 1

# --- Test 14: the one documented exception to the exit-0 contract ---
echo "--- Test 14: wedged data worktree dies (documented exception) ---"

setup_remote_and_clone
setup_branch_mode
pushd "$TEST_MAIN_DIR" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE=".aitask-data"

# Make _ait_data_gitdir resolve and plant an in-progress rebase.
mkdir -p .git/worktrees/-aitask-data/rebase-merge

( task_push ) 2>"$TEST_TMPDIR/wedged_err.txt"
wedged_rc=$?
wedged_err="$(cat "$TEST_TMPDIR/wedged_err.txt")"

assert_eq "wedged worktree exits 1 (not a push outcome)" "1" "$wedged_rc"
assert_contains "the die names the stuck operation" "rebase" "$wedged_err"
assert_contains "the die offers a recovery command" "--abort" "$wedged_err"

( AIT_GIT_SKIP_STATE_CHECK=1 task_push ) >/dev/null 2>&1
bypass_rc=$?
assert_success "AIT_GIT_SKIP_STATE_CHECK=1 bypasses the guard" "$bypass_rc"

popd > /dev/null || exit 1

# --- Test 15: ait git push --batch (public machine interface) ---
echo "--- Test 15: ait git push --batch outcome tokens ---"

# Scaffold ./ait + the libs it sources into the current repo.
setup_ait_cli() {
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/ait" ./ait
    chmod +x ./ait
}

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
setup_ait_cli

echo "batch push" > batch_file.txt
git add batch_file.txt .aitask-scripts/ ait
git commit -m "commit for batch push" --quiet

batch_out="$(./ait git push --batch 2>"$TEST_TMPDIR/batch_err.txt")"
batch_rc=$?
assert_success "ait git push --batch returns 0 (PUSHED)" "$batch_rc"
assert_eq "--batch prints PUSHED" "PUSHED" "$batch_out"
remote_count=$(git -C "$TEST_REMOTE" rev-list --count HEAD)
assert_eq_trim "Remote advanced via ait git push --batch" "2" "$remote_count"

# Same repo, now in sync.
batch_out="$(./ait git push --batch 2>"$TEST_TMPDIR/batch_err.txt")"
batch_rc=$?
assert_success "ait git push --batch returns 0 (NOTHING)" "$batch_rc"
assert_eq "--batch prints NOTHING when in sync" "NOTHING" "$batch_out"
assert_eq "NOTHING is silent on stderr" "" "$(cat "$TEST_TMPDIR/batch_err.txt")"

# Negative control: the default surface stays clean.
plain_out="$(./ait git push 2>/dev/null)"
assert_eq "plain ait git push prints nothing on stdout" "" "$plain_out"

git remote remove origin
batch_out="$(./ait git push --batch 2>"$TEST_TMPDIR/batch_err.txt")"
batch_rc=$?
assert_success "ait git push --batch returns 0 (NO_REMOTE)" "$batch_rc"
assert_eq "--batch prints NO_REMOTE" "NO_REMOTE" "$batch_out"
assert_eq "NO_REMOTE is silent on stderr" "" "$(cat "$TEST_TMPDIR/batch_err.txt")"

popd > /dev/null || exit 1

# Fresh clone for the failure token (needs an upstream so the count resolves).
setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
setup_ait_cli

echo "stranded" > stranded.txt
git add stranded.txt
git commit -m "commit that will not reach the remote" --quiet
git remote set-url origin /nonexistent/path/repo.git

batch_out="$(./ait git push --batch 2>"$TEST_TMPDIR/batch_fail_err.txt")"
batch_rc=$?
batch_err="$(cat "$TEST_TMPDIR/batch_fail_err.txt")"
assert_success "ait git push --batch returns 0 on failure" "$batch_rc"
assert_eq "--batch prints FAILED:<reason>:<count>" "FAILED:remote_unreachable:1" "$batch_out"
assert_contains "failure still warns on stderr" "1 commit(s) not pushed" "$batch_err"

popd > /dev/null || exit 1

# --- Test 16: task_sync with nothing to pull stays silent ---
echo "--- Test 16: task_sync up-to-date -> no warning ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

task_sync 2>"$TEST_TMPDIR/sync_uptodate_err.txt"
sync_rc=$?
sync_err="$(cat "$TEST_TMPDIR/sync_uptodate_err.txt")"

assert_success "task_sync returns 0 with nothing to pull" "$sync_rc"
assert_eq "TASK_SYNC_STATUS is up-to-date" "up-to-date" "$TASK_SYNC_STATUS"
assert_eq "TASK_SYNC_UNPUSHED is 0" "0" "$TASK_SYNC_UNPUSHED"
assert_eq "TASK_SYNC_UNPULLED is 0" "0" "$TASK_SYNC_UNPULLED"
assert_eq "an up-to-date sync stays silent" "" "$sync_err"

popd > /dev/null || exit 1

# --- Test 17: task_sync with no remote configured stays silent ---
echo "--- Test 17: task_sync no remote -> no-remote, no warning ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

git remote remove origin

task_sync 2>"$TEST_TMPDIR/sync_noremote_err.txt"
sync_rc=$?
sync_err="$(cat "$TEST_TMPDIR/sync_noremote_err.txt")"

assert_success "task_sync returns 0 with no remote" "$sync_rc"
assert_eq "TASK_SYNC_STATUS is no-remote" "no-remote" "$TASK_SYNC_STATUS"
assert_eq "TASK_SYNC_REASON is empty when not failed" "" "$TASK_SYNC_REASON"
assert_eq "solo repos stay silent on sync" "" "$sync_err"

popd > /dev/null || exit 1

# --- Test 18: dirty data worktree blocks the pull (the t1269 flagship) ---
echo "--- Test 18: task_sync dirty worktree — reported, not silent ---"

setup_remote_and_clone
setup_branch_mode
pushd "$TEST_MAIN_DIR" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE=".aitask-data"

# Pin the outcome regardless of the developer's global git config.
git -C .aitask-data config rebase.autoStash false

echo "local branch change" > .aitask-data/my_file.txt
git -C .aitask-data add my_file.txt
git -C .aitask-data commit -m "branch mode local commit" --quiet

advance_remote "remote_only.txt"

# Another session's uncommitted edit to a TRACKED file.
echo "another session's in-flight edit" >> .aitask-data/init.txt

task_sync 2>"$TEST_TMPDIR/sync_dirty_err.txt"
sync_rc=$?
sync_err="$(cat "$TEST_TMPDIR/sync_dirty_err.txt")"

assert_success "task_sync still returns 0 (best-effort contract)" "$sync_rc"
assert_eq "TASK_SYNC_STATUS is failed" "failed" "$TASK_SYNC_STATUS"
assert_eq "TASK_SYNC_REASON is dirty_worktree" "dirty_worktree" "$TASK_SYNC_REASON"
assert_eq "TASK_SYNC_UNPUSHED counts the local commit" "1" "$TASK_SYNC_UNPUSHED"
# `pull --rebase` refuses BEFORE it fetches, so the local upstream ref never
# moved: the remote count reads 0 even though the remote is one commit ahead.
# This is exactly why the warning must not present it as a current reading.
assert_eq "TASK_SYNC_UNPULLED reads the stale upstream (0)" "0" "$TASK_SYNC_UNPULLED"
assert_contains "warning names the local unpushed count" "1 local unpushed" "$sync_err"
assert_contains "warning flags the remote count as cached" "last successful fetch" "$sync_err"
assert_contains "warning names the actual blocker" "unstaged changes" "$sync_err"
assert_contains "warning names the recovery path" "ait syncer" "$sync_err"

# The remote commit never landed — proof the sync really failed, so the
# assertions above are not vacuous.
if [[ -e .aitask-data/remote_only.txt ]]; then
    TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
    echo "FAIL: sync was expected to fail, but the remote file landed locally"
else
    TOTAL=$((TOTAL + 1)); PASS=$((PASS + 1))
fi

popd > /dev/null || exit 1

# --- Test 19: pull stops on a rebase conflict ---
echo "--- Test 19: task_sync rebase conflict -> reported ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

# Control FIRST: with nothing to conflict with, the fixture must be clean. Without
# this, "no wedge afterwards" below could pass because nothing ever wedged.
assert_eq_trim "19: control — a clean fixture has no in-progress state" "" "$(probe_wedge)"

force_remote_conflict conflict.txt

task_sync 2>"$TEST_TMPDIR/sync_conflict_err.txt"
sync_rc=$?
sync_err="$(cat "$TEST_TMPDIR/sync_conflict_err.txt")"

assert_success "task_sync returns 0 on rebase conflict" "$sync_rc"
assert_eq "TASK_SYNC_STATUS is failed (conflict)" "failed" "$TASK_SYNC_STATUS"
assert_eq "TASK_SYNC_REASON is rebase_conflict" "rebase_conflict" "$TASK_SYNC_REASON"

# t1725_1: the conflicted rebase must be gone. This block used to END with
# `git rebase --abort || true` to "leave the fixture recoverable" — that cleanup
# WAS the bug, performed by the test instead of by the code under test.
assert_eq_trim "19: the conflicted rebase was aborted, not left behind" "" "$(probe_wedge)"
assert_contains "19: the warning says the rebase was aborted" \
    "was aborted (nothing left in progress)" "$sync_err"

# The sentinel itself is NOT on task_sync's stderr, and must not be: task_sync
# captures `_task_pull_rebase 2>&1` into pull_err to feed the classifier, so the
# user gets one warn() line rather than two overlapping messages. Pin the
# sentinel where it is actually observable — at the function that emits it.
# The fixture still diverges after the abort, so this conflicts again.
pull_out="$(_task_pull_rebase 2>&1)"
assert_contains "19: _task_pull_rebase announces the abort on its own stderr" \
    "rebase aborted after conflict - worktree restored, local commits kept" "$pull_out"
assert_contains "19: it also passes git's own conflict text through" \
    "CONFLICT" "$pull_out"
assert_eq_trim "19: and the second conflict is cleaned up too" "" "$(probe_wedge)"

# AC3, literally: "the task's next ./ait git commit succeeds".
assert_next_commit_succeeds "19: the next task_git commit succeeds after the abort"

# The lock must not outlive the call, or every later pull reports pull_locked.
TOTAL=$((TOTAL + 1))
if [[ -e ".git/aitask-pull.lock" ]]; then
    FAIL=$((FAIL + 1)); echo "FAIL: 19: the pull mutex was left behind"
else
    PASS=$((PASS + 1))
fi

popd > /dev/null || exit 1

# --- Test 20: unreachable remote with a pending commit warns ---
echo "--- Test 20: task_sync unreachable remote, 1 pending -> warns ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

echo "pending" > pending.txt
git add pending.txt
git commit -m "pending commit" --quiet

git remote set-url origin /nonexistent/path/repo.git

task_sync 2>"$TEST_TMPDIR/sync_unreach_err.txt"
sync_rc=$?
sync_err="$(cat "$TEST_TMPDIR/sync_unreach_err.txt")"

assert_success "task_sync returns 0 with an unreachable remote" "$sync_rc"
assert_eq "TASK_SYNC_STATUS is failed (unreachable)" "failed" "$TASK_SYNC_STATUS"
assert_eq "TASK_SYNC_REASON is remote_unreachable" "remote_unreachable" "$TASK_SYNC_REASON"
assert_contains "warning names the local unpushed count" "1 local unpushed" "$sync_err"
assert_contains "sync failure points at the sync retry command" "./ait sync" "$sync_err"

popd > /dev/null || exit 1

# --- Test 21: unreachable remote with nothing pending stays silent ---
echo "--- Test 21: task_sync unreachable remote, nothing pending -> silent ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

git remote set-url origin /nonexistent/path/repo.git

task_sync 2>"$TEST_TMPDIR/sync_offline_err.txt"
sync_rc=$?
sync_err="$(cat "$TEST_TMPDIR/sync_offline_err.txt")"

assert_success "task_sync returns 0 when offline with nothing pending" "$sync_rc"
assert_eq "TASK_SYNC_STATUS is failed (offline)" "failed" "$TASK_SYNC_STATUS"
assert_eq "TASK_SYNC_UNPUSHED is 0" "0" "$TASK_SYNC_UNPUSHED"
# The noise negative control: task_sync runs on EVERY pick, so an offline user
# with nothing at risk must not be warned.
assert_eq "offline with nothing pending stays silent" "" "$sync_err"

popd > /dev/null || exit 1

# --- Test 22: remote configured but the branch has no upstream ---
echo "--- Test 22: task_sync no upstream -> classified, not silent ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

# A remote IS configured (so the no-remote short-circuit does not fire), but
# this branch has no upstream. Nothing is pushed here, so the upstream stays
# unset regardless of the developer's push.autoSetupRemote setting.
git checkout -q -b data_no_upstream
echo "orphan branch" > orphan_branch.txt
git add orphan_branch.txt
git commit -m "commit on a branch with no upstream" --quiet

task_sync 2>"$TEST_TMPDIR/sync_noupstream_err.txt"
sync_rc=$?
sync_err="$(cat "$TEST_TMPDIR/sync_noupstream_err.txt")"

assert_success "task_sync returns 0 with no upstream" "$sync_rc"
assert_eq "TASK_SYNC_STATUS is failed (no upstream)" "failed" "$TASK_SYNC_STATUS"
assert_eq "TASK_SYNC_REASON is no_upstream" "no_upstream" "$TASK_SYNC_REASON"
# Both rev-list probes fail on the missing @{upstream} and must swallow it
# rather than abort the caller.
assert_eq "TASK_SYNC_UNPUSHED is undeterminable" "" "$TASK_SYNC_UNPUSHED"
assert_eq "TASK_SYNC_UNPULLED is undeterminable" "" "$TASK_SYNC_UNPULLED"
assert_contains "warning says the counts are unavailable" "counts unavailable" "$sync_err"
assert_contains "warning names the one-command fix" "set-upstream-to" "$sync_err"

popd > /dev/null || exit 1

# --- Test 23: aitask_pick_own.sh --sync outcome tokens ---
echo "--- Test 23: aitask_pick_own.sh --sync tokens ---"

# Scaffold ./ait plus the libs aitask_pick_own.sh sources. In --sync mode it
# runs task_sync + aitask_lock.sh --cleanup, so the lock script must be present:
# without it the cleanup call exits 127 and pick_own reports a spurious
# invoke_failed warning that has nothing to do with the sync path under test.
setup_pick_own_cli() {
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"   .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh"    .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_pick_own.sh"   .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh"       .aitask-scripts/
    chmod +x .aitask-scripts/aitask_pick_own.sh .aitask-scripts/aitask_lock.sh
}

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
setup_pick_own_cli

sync_out="$(./.aitask-scripts/aitask_pick_own.sh --sync 2>/dev/null)"
sync_rc=$?
assert_success "pick_own --sync returns 0 on a healthy repo" "$sync_rc"
assert_eq "healthy sync still prints SYNCED" "SYNCED" "$sync_out"

# Same repo, now with an unreachable remote and a stranded commit.
echo "stranded" > stranded.txt
git add stranded.txt .aitask-scripts/
git commit -m "commit that will not reconcile" --quiet
git remote set-url origin /nonexistent/path/repo.git

sync_out="$(./.aitask-scripts/aitask_pick_own.sh --sync 2>"$TEST_TMPDIR/pickown_err.txt")"
sync_rc=$?
pickown_err="$(cat "$TEST_TMPDIR/pickown_err.txt")"
assert_success "pick_own --sync still returns 0 on failure" "$sync_rc"
assert_eq "failed sync prints SYNC_FAILED:<reason>" "SYNC_FAILED:remote_unreachable" "$sync_out"
assert_contains "failed sync warns on stderr" "1 local unpushed" "$pickown_err"

popd > /dev/null || exit 1

# --- Test 24: --sync stays silent about a healthy lock sweep ---
# sync_remote() runs a stale-lock sweep on every pick. It used to discard both
# its stderr and its exit status; now it reports failures — but the quiet paths
# must stay quiet, and the child's progress notices must not leak into the
# structured stdout that the pick skill parses.
echo "--- Test 24: --sync lock sweep stays silent when it succeeds ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
setup_pick_own_cli
git add .aitask-scripts/ && git commit -m "scaffold" --quiet && git push --quiet 2>/dev/null
./.aitask-scripts/aitask_lock.sh --init > /dev/null 2>&1
# Lock a task and archive it, so the sweep actually has something to remove.
mkdir -p aitasks/archived
./.aitask-scripts/aitask_lock.sh --lock 1 --email "user@test.com" > /dev/null 2>&1
echo "---" > aitasks/archived/t1_test_task.md
git add aitasks/ && git commit -m "archive t1" --quiet && git push --quiet 2>/dev/null

sync_out="$(./.aitask-scripts/aitask_pick_own.sh --sync 2>"$TEST_TMPDIR/sweep_ok_err.txt")"
sync_rc=$?
sweep_ok_err="$(cat "$TEST_TMPDIR/sweep_ok_err.txt")"
assert_success "pick_own --sync returns 0 after a successful sweep" "$sync_rc"
assert_eq "a successful sweep leaves stdout as exactly SYNCED" "SYNCED" "$sync_out"
assert_eq "a successful sweep stays silent on stderr" "" "$sweep_ok_err"

popd > /dev/null || exit 1

# --- Test 25: --sync reports a failed lock sweep without blocking the pick ---
echo "--- Test 25: --sync reports a failed lock sweep, still exits 0 ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
setup_pick_own_cli
git add .aitask-scripts/ && git commit -m "scaffold" --quiet && git push --quiet 2>/dev/null
./.aitask-scripts/aitask_lock.sh --init > /dev/null 2>&1
mkdir -p aitasks/archived
./.aitask-scripts/aitask_lock.sh --lock 1 --email "user@test.com" > /dev/null 2>&1
echo "---" > aitasks/archived/t1_test_task.md
git add aitasks/ && git commit -m "archive t1" --quiet && git push --quiet 2>/dev/null

# Make the remote reject the cleanup push (but stay readable, so the sync
# itself still succeeds and only the lock sweep fails).
printf '#!/bin/sh\necho "rejected by test hook" >&2\nexit 1\n' \
    > "$TEST_REMOTE/hooks/pre-receive"
chmod +x "$TEST_REMOTE/hooks/pre-receive"

sync_out="$(./.aitask-scripts/aitask_pick_own.sh --sync 2>"$TEST_TMPDIR/sweep_fail_err.txt")"
sync_rc=$?
sweep_fail_err="$(cat "$TEST_TMPDIR/sweep_fail_err.txt")"
assert_success "a failed sweep never blocks the pick" "$sync_rc"
assert_eq "a failed sweep leaves the stdout token intact" "SYNCED" "$sync_out"
assert_contains "the lock script's own diagnosis is forwarded" "1 stale lock(s)" "$sweep_fail_err"
assert_contains "the consequence is named" "LOCK_FAILED for a task nobody is working on" "$sweep_fail_err"

rm -f "$TEST_REMOTE/hooks/pre-receive"
popd > /dev/null || exit 1

# =====================================================================
# task_data_converge — state matrix (t1658_1)
#
# The seam is `fetch` + `merge --ff-only`, chosen over `pull --rebase`
# because the rebase refuses (exit 128) BEFORE it fetches whenever the
# shared data worktree is dirty. Each behind-state test below carries the
# negative control that pins that difference.
# =====================================================================

# Stderr sink for converge calls. task_data_converge reports through GLOBALS,
# so it must never be wrapped in $( ) — a subshell discards the verdict, which
# is the exact defect this feature removes. Redirect stderr to a file instead.
converge_err_file="$(mktemp "${TMPDIR:-/tmp}/ait_converge_err_XXXXXX")"
CLEANUP_DIRS+=("$converge_err_file")

# Seed a dirty (unstaged, uncommitted) file in the data worktree.
seed_dirty_file() {
    local dir="$1" name="$2" content="$3"
    echo "$content" > "$dir/$name"
    git -C "$dir" add "$name"
    git -C "$dir" commit -m "seed $name" --quiet
    git -C "$dir" push --quiet 2>/dev/null
    printf 'LOCAL EDIT\n' >> "$dir/$name"
}

# --- Test 26: converge clean + behind -> fast-forwarded (legacy mode) ---
echo "--- Test 26: converge clean + behind -> fast-forwarded (legacy) ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

advance_remote "remote_only.txt"
remote_sha=$(git ls-remote "$TEST_REMOTE" HEAD | awk '{print $1}')

task_data_converge "test"
conv_rc=$?

assert_success "task_data_converge returns 0" "$conv_rc"
assert_eq "clean+behind is fast-forwarded" "fast-forwarded" "$TASK_CONVERGE_STATUS"
assert_eq_trim "behind is 0 after the ff" "0" "$TASK_CONVERGE_BEHIND"
git merge-base --is-ancestor "$remote_sha" HEAD 2>/dev/null
assert_success "the remote commit is an ancestor of local HEAD" "$?"

popd > /dev/null || exit 1

# --- Test 27: converge clean + behind -> fast-forwarded (branch mode) ---
echo "--- Test 27: converge clean + behind -> fast-forwarded (branch mode) ---"

setup_remote_and_clone
setup_branch_mode
pushd "$TEST_MAIN_DIR" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE=".aitask-data"

advance_remote "remote_only.txt"
remote_sha=$(git ls-remote "$TEST_REMOTE" HEAD | awk '{print $1}')

task_data_converge "test"

assert_eq "clean+behind is fast-forwarded (branch mode)" "fast-forwarded" "$TASK_CONVERGE_STATUS"
git -C .aitask-data merge-base --is-ancestor "$remote_sha" HEAD 2>/dev/null
assert_success "remote commit is an ancestor of local HEAD (branch mode)" "$?"

popd > /dev/null || exit 1

# --- Test 28: converge dirty NON-overlapping + behind -> still fast-forwarded ---
echo "--- Test 28: converge dirty non-overlapping + behind -> fast-forwarded ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

seed_dirty_file "$TEST_LOCAL" "mine.txt" "mine"
dirty_before="$(cat mine.txt)"
advance_remote "theirs.txt"

# NEGATIVE CONTROL, in this exact fixture state: the seam the old code used
# refuses outright, which is the whole reason for the replacement.
rebase_out="$(git pull --rebase --quiet 2>&1)"
rebase_rc=$?
assert_eq "control: pull --rebase exits 128 while dirty" "128" "$rebase_rc"
assert_contains "control: git names the unstaged changes" "unstaged changes" "$rebase_out"

task_data_converge "test"

assert_eq "dirty non-overlapping + behind is fast-forwarded" "fast-forwarded" "$TASK_CONVERGE_STATUS"
assert_eq "the dirty file survives the merge byte-for-byte" "$dirty_before" "$(cat mine.txt)"

popd > /dev/null || exit 1

# --- Test 29: converge dirty OVERLAPPING + behind -> blocked / ff_blocked ---
echo "--- Test 29: converge dirty overlapping + behind -> blocked/ff_blocked ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

seed_dirty_file "$TEST_LOCAL" "shared.txt" "shared"
dirty_before="$(cat shared.txt)"
head_before="$(git rev-parse HEAD)"

# Advance the remote on the SAME file the worktree is dirty on.
other_tmp="$(mktemp -d "${TMPDIR:-/tmp}/ait_push_overlap_XXXXXX")"
CLEANUP_DIRS+=("$other_tmp")
git clone --quiet "$TEST_REMOTE" "$other_tmp/other" 2>/dev/null
git -C "$other_tmp/other" config user.email "other@test.com"
git -C "$other_tmp/other" config user.name "Other"
echo "their version" > "$other_tmp/other/shared.txt"
git -C "$other_tmp/other" add shared.txt
git -C "$other_tmp/other" commit -m "other edits shared.txt" --quiet
git -C "$other_tmp/other" push --quiet 2>/dev/null

task_data_converge "test" 2>"$converge_err_file"
converge_err="$(cat "$converge_err_file")"

assert_eq "dirty overlapping + behind is blocked" "blocked" "$TASK_CONVERGE_STATUS"
assert_eq "the blocked ff is reported as ff_blocked" "ff_blocked" "$TASK_CONVERGE_REASON"
assert_contains "a warning is emitted" "not converged" "$converge_err"
assert_contains "the hint names the real recovery" "./ait sync" "$converge_err"
assert_eq "the local ref did not move" "$head_before" "$(git rev-parse HEAD)"
assert_eq "the dirty file is untouched" "$dirty_before" "$(cat shared.txt)"

popd > /dev/null || exit 1

# --- Test 30: converge ahead only -> pushed ---
echo "--- Test 30: converge ahead only -> pushed ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

echo "local only" > ahead.txt
git add ahead.txt
git commit -m "local ahead commit" --quiet
local_sha="$(git rev-parse HEAD)"

task_data_converge "test"

assert_eq "ahead only is pushed" "pushed" "$TASK_CONVERGE_STATUS"
assert_eq_trim "ahead is 0 after the push" "0" "$TASK_CONVERGE_AHEAD"
assert_eq_trim "the remote now has the commit" "$local_sha" \
    "$(git -C "$TEST_REMOTE" rev-parse HEAD)"

popd > /dev/null || exit 1

# --- Test 31: converge ahead AND behind -> diverged / local_diverged ---
echo "--- Test 31: converge ahead and behind -> diverged/local_diverged ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

echo "local only" > mine.txt
git add mine.txt
git commit -m "local ahead commit" --quiet
head_before="$(git rev-parse HEAD)"
advance_remote "theirs.txt"

task_data_converge "test" 2>"$converge_err_file"
converge_err="$(cat "$converge_err_file")"

assert_eq "ahead+behind is diverged" "diverged" "$TASK_CONVERGE_STATUS"
assert_eq "the reason comes from the counts" "local_diverged" "$TASK_CONVERGE_REASON"
assert_contains "a warning is emitted" "not converged" "$converge_err"
assert_eq "no ref moved" "$head_before" "$(git rev-parse HEAD)"

popd > /dev/null || exit 1

# --- Test 32: converge with no upstream -> failed / no_upstream ---
echo "--- Test 32: converge no upstream -> failed/no_upstream ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

git branch --unset-upstream 2>/dev/null

task_data_converge "test" 2>"$converge_err_file"
converge_err="$(cat "$converge_err_file")"

assert_eq "no upstream is failed" "failed" "$TASK_CONVERGE_STATUS"
assert_eq "no upstream reason" "no_upstream" "$TASK_CONVERGE_REASON"
assert_contains "a warning is emitted" "not converged" "$converge_err"
# Both probes print nothing without an upstream. The warning must say the
# counts are UNAVAILABLE, not claim a concrete "0 local unpushed, 0 remote
# unpulled" — that would be a false report on the state.
assert_contains "the warning says the counts are unavailable" \
    "commit counts unavailable" "$converge_err"
assert_not_contains "and does not claim a concrete zero count" \
    "0 local unpushed" "$converge_err"

popd > /dev/null || exit 1

# --- Test 33: converge with no remote -> no-remote, silent ---
echo "--- Test 33: converge no remote -> no-remote, silent ---"

no_remote_tmp="$(mktemp -d "${TMPDIR:-/tmp}/ait_push_noremote_XXXXXX")"
CLEANUP_DIRS+=("$no_remote_tmp")
git init --quiet "$no_remote_tmp/solo"
git -C "$no_remote_tmp/solo" config user.email "test@test.com"
git -C "$no_remote_tmp/solo" config user.name "Test"
echo init > "$no_remote_tmp/solo/init.txt"
git -C "$no_remote_tmp/solo" add init.txt
git -C "$no_remote_tmp/solo" commit -m init --quiet

pushd "$no_remote_tmp/solo" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

task_data_converge "test" 2>"$converge_err_file"
converge_err="$(cat "$converge_err_file")"

assert_eq "no remote is no-remote" "no-remote" "$TASK_CONVERGE_STATUS"
assert_eq "no remote is silent" "" "$converge_err"

popd > /dev/null || exit 1

# --- Test 34: converge success paths are silent ---
echo "--- Test 34: converge success paths are silent ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

task_data_converge "test" 2>"$converge_err_file"
converge_err="$(cat "$converge_err_file")"
assert_eq "already-converged is converged" "converged" "$TASK_CONVERGE_STATUS"
assert_eq "already-converged is silent" "" "$converge_err"

advance_remote "quiet.txt"
task_data_converge "test" 2>"$converge_err_file"
converge_err="$(cat "$converge_err_file")"
assert_eq "fast-forward is silent" "" "$converge_err"

popd > /dev/null || exit 1

# --- Test 35: converge loses the push race -> diverged, not failed ---
echo "--- Test 35: converge loses the push race -> diverged/local_diverged ---"

# The ahead-only arm fetches, sees ahead=1/behind=0, then pushes. If another
# writer advances origin in between, git rejects non-fast-forward and the
# classifier says "diverged" — but the TRUE state is ahead-and-behind. Without
# the pass-2 rule this returns failed; the assertion below is what pins it.
#
# The race is injected deterministically through a pre-push hook on the bare
# remote: the hook advances origin from a second clone on the FIRST push only,
# so no sleeping and no wall-clock dependency.
setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

echo "local only" > mine.txt
git add mine.txt
git commit -m "local ahead commit" --quiet
head_before="$(git rev-parse HEAD)"

race_helper="$TEST_TMPDIR/race_advance.sh"
cat > "$race_helper" <<RACEEOF
#!/usr/bin/env bash
# Advance origin once, from a clone, to simulate a competing writer landing
# between our fetch and our push.
flag="$TEST_TMPDIR/race_fired"
[ -f "\$flag" ] && exit 0
touch "\$flag"
tmp="\$(mktemp -d)"
git clone --quiet "$TEST_REMOTE" "\$tmp/other" >/dev/null 2>&1
git -C "\$tmp/other" config user.email other@test.com
git -C "\$tmp/other" config user.name Other
echo racer > "\$tmp/other/racer.txt"
git -C "\$tmp/other" add racer.txt
git -C "\$tmp/other" commit -m "competing writer" --quiet
git -C "\$tmp/other" push --quiet origin HEAD:master >/dev/null 2>&1 \
  || git -C "\$tmp/other" push --quiet origin HEAD:main >/dev/null 2>&1
rm -rf "\$tmp"
RACEEOF
chmod +x "$race_helper"

# Wrap _task_push_once so the competing push lands immediately before ours.
eval "$(declare -f _task_push_once | sed '1s/^_task_push_once/_task_push_once_orig/')"
_task_push_once() {
    "$race_helper"
    _task_push_once_orig
}

task_data_converge "test" 2>"$converge_err_file"
converge_err="$(cat "$converge_err_file")"

assert_eq "a lost push race is diverged, not failed" "diverged" "$TASK_CONVERGE_STATUS"
assert_eq "a lost push race reports local_diverged" "local_diverged" "$TASK_CONVERGE_REASON"
assert_eq_trim "the ahead count is real" "1" "$TASK_CONVERGE_AHEAD"
assert_eq_trim "the behind count is real" "1" "$TASK_CONVERGE_BEHIND"
assert_contains "a warning is emitted" "not converged" "$converge_err"
assert_eq "no local ref moved" "$head_before" "$(git rev-parse HEAD)"

unset -f _task_push_once
eval "$(declare -f _task_push_once_orig | sed '1s/^_task_push_once_orig/_task_push_once/')"
unset -f _task_push_once_orig

popd > /dev/null || exit 1

# --- Test 36: a NON-race push failure still terminates as failed ---
echo "--- Test 36: non-race push failure terminates failed (negative control) ---"

# Negative control for Test 35: if the pass rule retried on ANY push failure,
# this would loop and misreport too. Only a non-fast-forward rejection may
# consume pass 2.
setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

echo "local only" > mine.txt
git add mine.txt
git commit -m "local ahead commit" --quiet

# A push that fails for a reason that is NOT a race: the remote is gone.
git remote set-url origin "$TEST_TMPDIR/definitely_not_a_repo"

task_data_converge "test" 2>"$converge_err_file"
converge_err="$(cat "$converge_err_file")"

assert_eq "an unreachable remote is failed, not diverged" "failed" "$TASK_CONVERGE_STATUS"
assert_not_contains "and it is not classified as a race" "local_diverged" "$TASK_CONVERGE_REASON"
assert_contains "a warning is emitted" "not converged" "$converge_err"

popd > /dev/null || exit 1

# --- Test 37: the documented recovery actually converges a diverged branch ---
echo "--- Test 37: './ait sync' recovery converges from diverged ---"

# task_data_converge REPORTS diverged rather than resolving it, and hands
# ownership to './ait sync'. That hand-off is a claim about another program, so
# it is EXECUTED here rather than asserted in prose.
setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

# aitask_sync.sh's auto_commit runs `git add aitasks/ aiplans/`, which fails
# WHOLESALE (staging nothing) when either directory is absent. A real project
# always has both, so seed both here or the recovery silently no-ops.
mkdir -p aitasks aiplans
printf 'local line\n' > aitasks/t1_local.md
: > aiplans/.keep
git add aitasks/t1_local.md aiplans/.keep
git commit -m "local task" --quiet
advance_remote "aitasks_remote.txt"

task_data_converge "test"
assert_eq "precondition: the branch is diverged" "diverged" "$TASK_CONVERGE_STATUS"

# No pipeline here on purpose: `x="$(cmd | tail -n1)"` followed by
# ${PIPESTATUS[0]} reads the ASSIGNMENT's status in this shell (always 0), so
# the exit assertion would be vacuous. Take $? from the substitution itself,
# then trim to the verdict line.
sync_raw="$("$PROJECT_DIR/.aitask-scripts/aitask_sync.sh" --batch 2>/dev/null)"
sync_rc=$?
sync_out="$(printf '%s\n' "$sync_raw" | tail -n1)"

assert_success "the recovery exits 0" "$sync_rc"
case "$sync_out" in
    SYNCED|AUTOMERGED|PUSHED|PULLED) recovery_ok=0 ;;
    *) recovery_ok=1 ;;
esac
assert_eq "the recovery reports convergence (got: $sync_out)" "0" "$recovery_ok"
assert_eq_trim "nothing left unpushed" "0" "$(git rev-list --count '@{u}..HEAD' 2>/dev/null)"
assert_eq_trim "nothing left unpulled" "0" "$(git rev-list --count 'HEAD..@{u}' 2>/dev/null)"
# The recovery rebases, which rewrites the commit hash, so the original sha is
# deliberately NOT the invariant — the surviving WORK is.
assert_contains "the local work survived the recovery (no work lost)" "local line" \
    "$(git show HEAD:aitasks/t1_local.md 2>/dev/null || true)"
assert_file_exists "the pulled remote file is present too" "aitasks_remote.txt"

popd > /dev/null || exit 1

# --- Test 38: the documented recovery converges from ff_blocked ---
echo "--- Test 38: './ait sync' recovery converges from ff_blocked ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

# A file both sides touch, on DIFFERENT lines: enough for merge --ff-only to
# refuse (it is a path-level check), but cleanly 3-way mergeable on rebase.
# aitask_sync.sh's auto_commit runs `git add aitasks/ aiplans/`, which fails
# WHOLESALE (staging nothing) when either directory is absent. A real project
# always has both, so seed both here or the recovery silently no-ops.
mkdir -p aitasks aiplans
printf 'header\nb\nc\nd\ne\nf\ng\nmine\nfooter\n' > aitasks/t2_shared.md
: > aiplans/.keep
git add aitasks/t2_shared.md aiplans/.keep
git commit -m "seed shared task" --quiet
git push --quiet 2>/dev/null

other_tmp="$(mktemp -d "${TMPDIR:-/tmp}/ait_push_ffrec_XXXXXX")"
CLEANUP_DIRS+=("$other_tmp")
git clone --quiet "$TEST_REMOTE" "$other_tmp/other" 2>/dev/null
git -C "$other_tmp/other" config user.email "other@test.com"
git -C "$other_tmp/other" config user.name "Other"
printf 'HEADER CHANGED\nb\nc\nd\ne\nf\ng\nmine\nfooter\n' > "$other_tmp/other/aitasks/t2_shared.md"
git -C "$other_tmp/other" add aitasks/t2_shared.md
git -C "$other_tmp/other" commit -m "other edits the header" --quiet
git -C "$other_tmp/other" push --quiet 2>/dev/null

# Dirty the same path locally, on a different line.
printf 'header\nb\nc\nd\ne\nf\ng\nMINE CHANGED\nfooter\n' > aitasks/t2_shared.md

task_data_converge "test"
assert_eq "precondition: the fast-forward is blocked" "blocked" "$TASK_CONVERGE_STATUS"
assert_eq "precondition: reported as ff_blocked" "ff_blocked" "$TASK_CONVERGE_REASON"

sync_raw="$("$PROJECT_DIR/.aitask-scripts/aitask_sync.sh" --batch 2>/dev/null)"
sync_rc=$?
sync_out="$(printf '%s\n' "$sync_raw" | tail -n1)"
assert_success "the ff_blocked recovery exits 0" "$sync_rc"

case "$sync_out" in
    SYNCED|AUTOMERGED|PUSHED|PULLED) recovery_ok=0 ;;
    *) recovery_ok=1 ;;
esac
assert_eq "the recovery reports convergence (got: $sync_out)" "0" "$recovery_ok"
assert_eq_trim "nothing left unpushed" "0" "$(git rev-list --count '@{u}..HEAD' 2>/dev/null)"
assert_eq_trim "nothing left unpulled" "0" "$(git rev-list --count 'HEAD..@{u}' 2>/dev/null)"
assert_contains "the previously-dirty edit survived into a commit" "MINE CHANGED" \
    "$(git show HEAD:aitasks/t2_shared.md 2>/dev/null || cat aitasks/t2_shared.md)"

popd > /dev/null || exit 1

# --- Test 39: a pre-existing rebase is never touched (t1725_1) ---
# The discriminating case for "clean up after YOURSELF": the wedge is planted
# with a FOREIGN orig-head, so ownership cannot be proven and the abort must not
# run. Test 19 is its positive control — same code path, provable ownership.
echo "--- Test 39: pre-existing foreign rebase -> left in place ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

force_remote_conflict conflict.txt

# Plant a rebase-merge whose orig-head names a commit that is not our HEAD.
mkdir -p .git/rebase-merge
echo "0000000000000000000000000000000000000000" > .git/rebase-merge/orig-head
assert_eq_trim "39: the planted wedge is present before the call" \
    "rebase-merge" "$(probe_wedge)"

pull_out="$(_task_pull_rebase 2>&1)"
assert_eq_trim "39: the foreign rebase is still there afterwards" \
    "rebase-merge" "$(probe_wedge)"
assert_contains "39: it is reported as already in progress" \
    "already in progress in the data worktree" "$pull_out"
assert_eq "39: and classified as rebase_in_progress" "rebase_in_progress" \
    "$(_task_push_classify "" "$pull_out")"

rm -rf .git/rebase-merge
popd > /dev/null || exit 1

# --- Test 40: a pre-existing NON-rebase state gets non-rebase wording ---
# A merge / cherry-pick / revert must not be announced as a rebase, nor handed
# `rebase --abort`. Before t1725_1 this text matched no classifier arm at all
# (`*CONFLICT*` is case-sensitive) and landed on `unknown`.
echo "--- Test 40: pre-existing MERGE_HEAD -> data_midop, no rebase advice ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

force_remote_conflict conflict.txt
: > .git/MERGE_HEAD
assert_eq_trim "40: MERGE_HEAD is present before the call" "MERGE_HEAD" "$(probe_wedge)"

pull_out="$(_task_pull_rebase 2>&1)"
midop_reason="$(_task_push_classify "" "$pull_out")"

assert_eq_trim "40: MERGE_HEAD survives untouched" "MERGE_HEAD" "$(probe_wedge)"
assert_contains "40: the message names the actual state" "mid-MERGE_HEAD" "$pull_out"
assert_eq "40: classified as data_midop, not rebase_in_progress" "data_midop" "$midop_reason"
# The discriminator. Asserting only "MERGE_HEAD survived" would also pass if the
# state were described as a rebase — which is exactly the defect this guards.
TOTAL=$((TOTAL + 1))
if [[ "$pull_out" == *"rebase"* ]]; then
    FAIL=$((FAIL + 1))
    echo "FAIL: 40: a MERGE_HEAD was described using the word 'rebase'"
else
    PASS=$((PASS + 1))
fi
TOTAL=$((TOTAL + 1))
if [[ "$(_task_push_reason_hint "$midop_reason")" == *"rebase --abort"* ]]; then
    FAIL=$((FAIL + 1))
    echo "FAIL: 40: a MERGE_HEAD was handed 'rebase --abort'"
else
    PASS=$((PASS + 1))
fi

rm -f .git/MERGE_HEAD
popd > /dev/null || exit 1

# --- Test 41: a failed abort is reported as such, never as "restored" ---
# The branch a real conflict never reaches: `rebase --abort … || true` swallows
# its own failure, and the rebase_conflict hint claims "nothing left in
# progress". Force it through the documented seam — _ait_data_git is the single
# runner every data-worktree git call goes through.
echo "--- Test 41: rebase --abort fails -> rebase_in_progress, no false claim ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

force_remote_conflict conflict.txt

_ait_data_git() {
    if [[ "${1:-}" == "rebase" && "${2:-}" == "--abort" ]]; then
        return 1                      # the abort fails AND changes nothing
    fi
    LC_ALL=C git "$@"
}

pull_out="$(_task_pull_rebase 2>&1)"
fail_reason="$(_task_push_classify "" "$pull_out")"

assert_eq_trim "41: the wedge survives a failed abort" "rebase-merge" "$(probe_wedge)"
assert_eq "41: classified as rebase_in_progress" "rebase_in_progress" "$fail_reason"
assert_contains "41: the failure is named" "rebase --abort failed" "$pull_out"
# The claim that must NOT appear. Test 19 is the negative control: identical
# fixture, real runner, and it asserts this exact string IS present.
TOTAL=$((TOTAL + 1))
if [[ "$pull_out" == *"worktree restored"* ]]; then
    FAIL=$((FAIL + 1))
    echo "FAIL: 41: claimed the worktree was restored after the abort failed"
else
    PASS=$((PASS + 1))
fi
# And the hint must point at a recovery for a state that IS still there.
assert_contains "41: the hint offers the abort/continue pair" "rebase --abort" \
    "$(_task_push_reason_hint "$fail_reason")"

unset -f _ait_data_git
reload_task_utils
_AIT_DATA_WORKTREE="."
git rebase --abort 2>/dev/null || true
popd > /dev/null || exit 1

# --- Test 42: ait_rebase_abort_if_ours verdict table (t1725_1) ---
# Unit level, against a fabricated git-dir and a stub runner, so every branch —
# including the ones a live fixture cannot reach — is deterministic. The stub
# records whether it ran: for every not_ours verdict it must NOT have.
echo "--- Test 42: ait_rebase_abort_if_ours verdicts ---"

reload_task_utils
GD_42="$(mktemp -d "${TMPDIR:-/tmp}/ait_own_XXXXXX")"
CLEANUP_DIRS+=("$GD_42")
OURS_42="1111111111111111111111111111111111111111"
THEIRS_42="2222222222222222222222222222222222222222"

# Stub runners. Each records its invocation in $GD_42/ran.
stub_removes() { : > "$GD_42/ran"; rm -rf "${GD_42:?}/rebase-merge" "${GD_42:?}/rebase-apply"; return 0; }
stub_fails()   { : > "$GD_42/ran"; return 1; }

plant_42() {   # <state> <orig-head-or-"none">
    rm -rf "${GD_42:?}/rebase-merge" "${GD_42:?}/rebase-apply"
    rm -f "${GD_42:?}/MERGE_HEAD" "$GD_42/ran"
    case "$1" in
        MERGE_HEAD) : > "$GD_42/MERGE_HEAD" ;;
        *) mkdir -p "$GD_42/$1"
           [[ "${2:-none}" != "none" ]] && echo "$2" > "$GD_42/$1/orig-head" ;;
    esac
}
ran_42() { [[ -e "$GD_42/ran" ]] && echo yes || echo no; }

plant_42 rebase-merge "$OURS_42"
assert_eq_trim "42: ours + abort lands -> aborted" "aborted" \
    "$(ait_rebase_abort_if_ours stub_removes "$GD_42" "$OURS_42" rebase-merge)"

plant_42 rebase-merge "$OURS_42"
assert_eq_trim "42: ours + abort fails -> abort_failed" "abort_failed" \
    "$(ait_rebase_abort_if_ours stub_fails "$GD_42" "$OURS_42" rebase-merge)"

plant_42 rebase-merge "$THEIRS_42"
assert_eq_trim "42: foreign orig-head -> not_ours" "not_ours" \
    "$(ait_rebase_abort_if_ours stub_removes "$GD_42" "$OURS_42" rebase-merge)"
assert_eq_trim "42: and the runner was never invoked" "no" "$(ran_42)"

plant_42 rebase-merge none
assert_eq_trim "42: missing orig-head -> not_ours" "not_ours" \
    "$(ait_rebase_abort_if_ours stub_removes "$GD_42" "$OURS_42" rebase-merge)"
assert_eq_trim "42: missing orig-head never invokes the runner" "no" "$(ran_42)"

plant_42 rebase-apply "$OURS_42"
assert_eq_trim "42: the apply backend is honoured too" "aborted" \
    "$(ait_rebase_abort_if_ours stub_removes "$GD_42" "$OURS_42" rebase-apply)"

plant_42 MERGE_HEAD
assert_eq_trim "42: a non-rebase state -> not_ours" "not_ours" \
    "$(ait_rebase_abort_if_ours stub_removes "$GD_42" "$OURS_42" MERGE_HEAD)"
assert_eq_trim "42: a non-rebase state never invokes the runner" "no" "$(ran_42)"

plant_42 rebase-merge "$OURS_42"
assert_eq_trim "42: an empty head_before proves nothing -> not_ours" "not_ours" \
    "$(ait_rebase_abort_if_ours stub_removes "$GD_42" "" rebase-merge)"
assert_eq_trim "42: an empty head_before never invokes the runner" "no" "$(ran_42)"

unset -f stub_removes stub_fails plant_42 ran_42

# --- Test 43: the pull mutex (t1725_1) ---
# Serialization is the reason the ownership evidence is trustworthy at all, so
# assert it against a real concurrent holder, not a mock.
echo "--- Test 43: pull mutex busy / reclaim / release ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

force_remote_conflict conflict.txt
LOCK_43=".git/aitask-pull.lock"

# A published stale_lock is <dir>/pid (the holder) + <dir>/owner (the release
# token). Writing anything else would make this lock read as legacy/tokenless,
# which is reclaimable on age alone — the assertion below would then pass
# without ever exercising the live-holder rule.
plant_lock_43() {   # <pid>
    mkdir -p "$LOCK_43"
    printf '%s\n' "$1" > "$LOCK_43/pid"
    printf 'not-our-token-%s\n' "$RANDOM" > "$LOCK_43/owner"
}

# A LIVE holder is never displaced: this shell is by definition running.
plant_lock_43 "$$"

busy_out="$(ait_pull_mutex_acquire 1 2>&1; echo "rc=$?")"
assert_contains "43: acquiring a live-held lock reports busy" "rc=1" "$busy_out"

task_sync 2>/dev/null
assert_eq "43: TASK_SYNC_REASON is pull_locked" "pull_locked" "$TASK_SYNC_REASON"
assert_eq "43: sync still returns a non-fatal failed status" "failed" "$TASK_SYNC_STATUS"
assert_eq_trim "43: no rebase was started while the lock was held" "" "$(probe_wedge)"
TOTAL=$((TOTAL + 1))
if [[ -d "$LOCK_43" ]]; then
    PASS=$((PASS + 1))          # the holder's lock is intact
else
    FAIL=$((FAIL + 1)); echo "FAIL: 43: a live holder's lock was displaced"
fi

# Release it and re-run: the control proving the previous block was the lock and
# not a broken fixture.
rm -rf "$LOCK_43"
task_sync 2>/dev/null
assert_eq "43: with the lock free the pull runs and conflicts" "rebase_conflict" \
    "$TASK_SYNC_REASON"
assert_eq_trim "43: and cleans up after itself" "" "$(probe_wedge)"
TOTAL=$((TOTAL + 1))
if [[ -e "$LOCK_43" ]]; then
    FAIL=$((FAIL + 1)); echo "FAIL: 43: the mutex was not released"
else
    PASS=$((PASS + 1))
fi

# A DEAD holder is reclaimed rather than waited out. PID 2^22-1 is above every
# Linux/macOS default pid_max, so it cannot name a running process.
plant_lock_43 4194303
TOTAL=$((TOTAL + 1))
if ait_pull_mutex_acquire 5 >/dev/null 2>&1; then
    PASS=$((PASS + 1))
    ait_pull_mutex_release
else
    FAIL=$((FAIL + 1)); echo "FAIL: 43: a dead holder's lock was not reclaimed"
fi
rm -rf "$LOCK_43"

popd > /dev/null || exit 1

# --- Test 44: the push retry loop cleans up too, in BRANCH mode (t1725_1) ---
# task_push reaches _task_pull_rebase through a different caller and, in branch
# mode, through the other git-dir resolution path (_ait_data_gitdir rather than
# the legacy `git rev-parse --git-dir` fallback). Both must clean up.
echo "--- Test 44: task_push retry conflict -> no wedge (branch mode) ---"

setup_remote_and_clone
setup_branch_mode
pushd "$TEST_MAIN_DIR" > /dev/null || exit 1
reload_task_utils
# Pinned exactly as every other branch-mode test here does: TEST_MAIN_DIR is not
# itself a git repo, so leaving detection to run from a transient cwd is what the
# other tests avoid by setting this explicitly.
_AIT_DATA_WORKTREE=".aitask-data"

pushd .aitask-data > /dev/null || exit 1
force_remote_conflict conflict.txt
popd > /dev/null || exit 1
_AIT_DATA_WORKTREE=".aitask-data"

GD_44="$(git -C .aitask-data rev-parse --absolute-git-dir)"
assert_eq_trim "44: control — clean before the push cycle" "" "$(probe_wedge "$GD_44")"

task_push 2>/dev/null
assert_eq "44: the push cycle reports failed" "failed" "$TASK_PUSH_STATUS"
assert_eq_trim "44: no rebase is left behind by the retry loop" "" "$(probe_wedge "$GD_44")"
TOTAL=$((TOTAL + 1))
if [[ -e "$GD_44/aitask-pull.lock" ]]; then
    FAIL=$((FAIL + 1)); echo "FAIL: 44: the mutex was left behind in branch mode"
else
    PASS=$((PASS + 1))
fi
# AC3 through the branch-mode gateway: the next write must not be refused.
assert_next_commit_succeeds "44: the next task_git commit succeeds (branch mode)"

popd > /dev/null || exit 1

# --- Test 45: aitask_pick_own.sh --sync under a conflict (t1725_1, AC3 e2e) ---
# The real entry point that runs at every pick — a real process, not a sourced
# function, so it also proves task_utils.sh's new startup dependency resolves.
echo "--- Test 45: pick_own --sync conflict -> SYNC_FAILED, no wedge ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
setup_pick_own_cli
force_remote_conflict conflict.txt

assert_eq_trim "45: control — clean before the sync" "" "$(probe_wedge)"
sync_out="$(./.aitask-scripts/aitask_pick_own.sh --sync 2>/dev/null)"
sync_rc=$?

assert_success "45: --sync still exits 0 (best-effort contract)" "$sync_rc"
assert_eq_trim "45: it reports the conflict reason" "SYNC_FAILED:rebase_conflict" "$sync_out"
assert_eq_trim "45: and leaves no wedge behind" "" "$(probe_wedge)"

popd > /dev/null || exit 1

# --- Test 46: a wedge that appeared during a NON-conflict failure (t1725_1) ---
# Signal 3. Unreachable from a single-process fixture — it needs a rebase to
# appear while our own pull is failing for an unrelated reason — so drive the
# decide-and-clean seam directly with exactly that combination. Without this
# signal, a concurrent session's rebase could be aborted by a pull that never
# conflicted at all.
echo "--- Test 46: rebase appeared during an unrelated failure -> untouched ---"

reload_task_utils
GD_46="$(mktemp -d "${TMPDIR:-/tmp}/ait_sig3_XXXXXX")"
CLEANUP_DIRS+=("$GD_46")
OURS_46="1111111111111111111111111111111111111111"
mkdir -p "$GD_46/rebase-merge"
# orig-head MATCHES, so signals 4 and 5 would both pass: only the non-conflict
# output stops the abort. That is what makes this discriminating.
echo "$OURS_46" > "$GD_46/rebase-merge/orig-head"

sig3_out="$(_task_pull_rebase_cleanup "$GD_46" "" "$OURS_46" \
    "error: cannot pull with rebase: You have unstaged changes." 2>&1)"

assert_eq_trim "46: the rebase is still there" "rebase-merge" "$(probe_wedge "$GD_46")"
assert_contains "46: and is reported as not ours to clean up" \
    "appeared in the data worktree during a pull that failed for another reason" "$sig3_out"
assert_eq "46: classified as rebase_in_progress" "rebase_in_progress" \
    "$(_task_push_classify "" "$sig3_out")"

# Positive control: the SAME state and orig-head, but conflict-shaped output —
# now it is ours and must be cleaned up. Proves signal 3 is what discriminated,
# not some unrelated refusal.
ctrl_runner() { rm -rf "${GD_46:?}/rebase-merge"; return 0; }
assert_eq_trim "46: control — conflict-shaped output makes it ours" "aborted" \
    "$(ait_rebase_abort_if_ours ctrl_runner "$GD_46" "$OURS_46" rebase-merge)"
unset -f ctrl_runner

# --- Test 47: signal 5 at the integration level (t1725_1) ---
# Test 39's foreign rebase is caught by signal 1 (it was there BEFORE the pull),
# so it never reaches the ownership check. The case that does is a rebase that
# appears DURING a conflicted pull and carries someone else's orig-head — the
# concurrent-session race the mutex narrows but cannot make impossible. Drive it
# through the same seam as Test 46.
echo "--- Test 47: foreign rebase appearing during our own conflict -> untouched ---"

GD_47="$(mktemp -d "${TMPDIR:-/tmp}/ait_sig5_XXXXXX")"
CLEANUP_DIRS+=("$GD_47")
mkdir -p "$GD_47/rebase-merge"
echo "2222222222222222222222222222222222222222" > "$GD_47/rebase-merge/orig-head"

sig5_out="$(_task_pull_rebase_cleanup "$GD_47" "" \
    "1111111111111111111111111111111111111111" \
    "CONFLICT (content): Merge conflict in t42.md
error: could not apply 1a2b3c4... local commit" 2>&1)"

assert_eq_trim "47: another session's rebase is left in place" \
    "rebase-merge" "$(probe_wedge "$GD_47")"
assert_contains "47: and is named as started outside this pull" \
    "started outside this pull" "$sig5_out"
assert_eq "47: classified as rebase_in_progress" "rebase_in_progress" \
    "$(_task_push_classify "" "$sig5_out")"
# Discriminator: everything except orig-head is identical to the ours case, so a
# gate that stopped checking ownership would abort here.
TOTAL=$((TOTAL + 1))
if [[ "$sig5_out" == *"worktree restored"* ]]; then
    FAIL=$((FAIL + 1))
    echo "FAIL: 47: aborted a rebase this pull did not start"
else
    PASS=$((PASS + 1))
fi

# ============================================================================
# t1727 — the workflow pull auto-merges what `ait sync` auto-merges
# ============================================================================
#
# Before t1727 `_task_pull_rebase` was a bare `pull --rebase`: the SAME
# frontmatter-only collision `ait sync` resolves silently made every pick fail
# with rebase_conflict. These fixtures drive the shared engine
# (lib/task_automerge.sh) through the two callers that now use it.

# Seed a task file with the four ADJACENT frontmatter fields the driver merges
# by three different rules — boardcol (keep-local), labels (union), updated_at
# (newest wins). Adjacency is load-bearing: far-apart edits merge TEXTUALLY and
# never reach the driver at all (test_sync_branch_mode_automerge.sh Test 4).
write_sample_task() {   # <path> <boardcol> <labels> <updated_at> [body]
    mkdir -p "$(dirname "$1")"
    cat > "$1" <<TASKEOF
---
priority: high
status: Ready
boardcol: $2
labels: $3
updated_at: $4
---
${5:-Task body stays the same}
TASKEOF
}

# Push a conflicting edit to aitasks/t1_sample.md from a second clone.
# Args are the same as write_sample_task's, minus the path.
# VERIFIES that it actually advanced the remote. The clone and the push used to
# swallow their errors with 2>/dev/null; when either silently failed the remote
# was never ahead, the pull under test found nothing to conflict with, and the
# test failed on its BEHAVIOUR assertions instead of naming the broken fixture.
# A precondition that can fail silently is not a precondition.
advance_remote_task() {   # <boardcol> <labels> <updated_at> [body]
    local tmp before after
    before="$(git -C "$TEST_REMOTE" rev-list --count HEAD 2>/dev/null || echo 0)"
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/ait_push_am_XXXXXX")"
    git clone --quiet "$TEST_REMOTE" "$tmp/other" 2>/dev/null
    git -C "$tmp/other" config user.email "other@test.com"
    git -C "$tmp/other" config user.name "Other"
    write_sample_task "$tmp/other/aitasks/t1_sample.md" "$1" "$2" "$3" "${4:-}"
    git -C "$tmp/other" add -A
    git -C "$tmp/other" commit -m "pc2: conflicting frontmatter edit" --quiet
    git -C "$tmp/other" push --quiet 2>/dev/null
    rm -rf "$tmp"
    after="$(git -C "$TEST_REMOTE" rev-list --count HEAD 2>/dev/null || echo 0)"
    TOTAL=$((TOTAL + 1))
    if [[ "$after" -gt "$before" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: fixture: advance_remote_task did not advance the remote ($before -> $after)"
    fi
}

# Seed + push the shared starting point both sides diverge from.
seed_sample_task() {
    write_sample_task aitasks/t1_sample.md backlog "[ui]" "2026-01-01 10:00"
    git add -A
    git commit -m "seed sample task" --quiet
    git push --quiet 2>/dev/null
}

# --- Test 48: task_sync auto-merges a frontmatter-only conflict ---
echo "--- Test 48: task_sync frontmatter conflict -> auto-merged, converged ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

seed_sample_task
advance_remote_task now "[ui]" "2026-01-01 10:00"
# Local: a different adjacent field, identical body.
write_sample_task aitasks/t1_sample.md backlog "[api, ui]" "2026-01-01 10:00"
git add -A
git commit -m "local: change labels" --quiet

task_sync 2>"$TEST_TMPDIR/am48_err.txt"
sync_rc=$?
sync_err="$(cat "$TEST_TMPDIR/am48_err.txt")"

assert_success "48: task_sync returns 0" "$sync_rc"
assert_eq "48: TASK_SYNC_STATUS is synced" "synced" "$TASK_SYNC_STATUS"
assert_eq "48: TASK_SYNC_AUTOMERGED is set" "1" "$TASK_SYNC_AUTOMERGED"
assert_eq "48: TASK_SYNC_REASON stays empty" "" "$TASK_SYNC_REASON"
assert_contains "48: the sentinel names the auto-merge" \
    "auto-merged task-data conflict(s) during pull" "$sync_err"
# BOTH sides' values survive — the merge really merged, it did not pick a side.
merged48="$(cat aitasks/t1_sample.md)"
assert_contains "48: local boardcol kept (keep-local rule)" "boardcol: backlog" "$merged48"
assert_contains "48: local label survives (union rule)" "api" "$merged48"
assert_contains "48: remote-side label survives (union rule)" "ui" "$merged48"
# Fully converged in BOTH directions, and nothing left in progress.
assert_eq_trim "48: nothing left to pull" "0" \
    "$(git rev-list --count 'HEAD..@{u}' 2>/dev/null)"
assert_eq_trim "48: nothing left unpushed after the later push" "1" \
    "$(git rev-list --count '@{u}..HEAD' 2>/dev/null)"
assert_eq_trim "48: no rebase left behind" "" "$(probe_wedge)"
assert_next_commit_succeeds "48: the next task_git commit succeeds"

popd > /dev/null || exit 1

# --- Test 49: the same conflict cleared through task_push's retry ---
echo "--- Test 49: task_push retry auto-merges, then pushes ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

seed_sample_task
advance_remote_task now "[ui]" "2026-01-01 10:00"
write_sample_task aitasks/t1_sample.md backlog "[api, ui]" "2026-01-01 10:00"
git add -A
git commit -m "ait: Start work on t1: set status to Implementing" --quiet

task_push 2>"$TEST_TMPDIR/am49_err.txt"
push_rc=$?

assert_success "49: task_push returns 0" "$push_rc"
assert_eq "49: TASK_PUSH_STATUS is pushed" "pushed" "$TASK_PUSH_STATUS"
assert_eq "49: TASK_PUSH_AUTOMERGED is set" "1" "$TASK_PUSH_AUTOMERGED"
assert_eq "49: nothing left unpushed" "0" "$TASK_PUSH_UNPUSHED"
# The COUNT, not just the status: a green run must not be able to mean
# "nothing was pushed".
assert_eq_trim "49: the claim commit reached the remote" "1" \
    "$(git -C "$TEST_REMOTE" log --oneline --grep='Start work on t1' | wc -l | tr -d ' ')"
assert_eq_trim "49: no rebase left behind" "" "$(probe_wedge)"

popd > /dev/null || exit 1

# --- Test 50: negative control — a BODY conflict on a task file still aborts ---
echo "--- Test 50: task-file body conflict -> t1725_1 abort, no auto-merge ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

seed_sample_task
# Same frontmatter, DIVERGING bodies: this is the discriminating case — it
# enters the auto-merge branch and the driver answers PARTIAL. (Test 19's
# conflict.txt is the non-task-file control, which never reaches the driver.)
advance_remote_task backlog "[ui]" "2026-01-01 10:00" "remote rewrote the body"
write_sample_task aitasks/t1_sample.md backlog "[ui]" "2026-01-01 10:00" "local rewrote the body"
git add -A
git commit -m "local: rewrite body" --quiet

task_sync 2>"$TEST_TMPDIR/am50_err.txt"
sync_rc=$?
sync_err="$(cat "$TEST_TMPDIR/am50_err.txt")"

assert_success "50: task_sync still returns 0" "$sync_rc"
assert_eq "50: TASK_SYNC_STATUS is failed" "failed" "$TASK_SYNC_STATUS"
assert_eq "50: TASK_SYNC_REASON is rebase_conflict" "rebase_conflict" "$TASK_SYNC_REASON"
assert_eq "50: TASK_SYNC_AUTOMERGED stays unset" "" "$TASK_SYNC_AUTOMERGED"
assert_not_contains "50: no auto-merge sentinel on a body conflict" \
    "auto-merged task-data conflict(s) during pull" "$sync_err"
assert_eq_trim "50: the rebase was aborted (t1725_1 behaviour intact)" "" "$(probe_wedge)"
assert_next_commit_succeeds "50: the next task_git commit succeeds after the abort"

popd > /dev/null || exit 1

# --- Test 51: library absent -> degrade to no auto-merge, never break ---
echo "--- Test 51: task_utils.sh without task_automerge.sh still works ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1

# The standalone-fixture case: setup_fake_aitask_repo copies neither
# lib/task_automerge.sh nor board/aitask_merge.py.
setup_fake_aitask_repo "$PWD"
cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"    .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
TOTAL=$((TOTAL + 1))
if [[ -e .aitask-scripts/lib/task_automerge.sh || -e .aitask-scripts/board/aitask_merge.py ]]; then
    FAIL=$((FAIL + 1))
    echo "FAIL: 51: fixture is not actually missing the library — test would be vacuous"
else
    PASS=$((PASS + 1))
fi

# Source the copied task_utils.sh the way a scaffolded script would.
unset _AIT_TASK_UTILS_LOADED
_AIT_DATA_WORKTREE=""
SCRIPT_DIR="$PWD/.aitask-scripts"
source_rc=0
# shellcheck disable=SC1091
source "$PWD/.aitask-scripts/lib/task_utils.sh" || source_rc=$?
set +euo pipefail
assert_success "51: sourcing task_utils.sh without the library succeeds" "$source_rc"
_AIT_DATA_WORKTREE="."

seed_sample_task
advance_remote_task now "[ui]" "2026-01-01 10:00"
write_sample_task aitasks/t1_sample.md backlog "[api, ui]" "2026-01-01 10:00"
git add -A
git commit -m "local: change labels" --quiet

task_sync 2>"$TEST_TMPDIR/am51_err.txt"
assert_eq "51: without the library the conflict fails as before" \
    "failed" "$TASK_SYNC_STATUS"
assert_eq "51: reason is still rebase_conflict" "rebase_conflict" "$TASK_SYNC_REASON"
assert_eq "51: and nothing claims an auto-merge" "" "$TASK_SYNC_AUTOMERGED"
assert_eq_trim "51: the rebase was still aborted" "" "$(probe_wedge)"

popd > /dev/null || exit 1
# Restore the real library for the tests that follow.
reload_task_utils

# --- Test 52: the sentinel is inert to the failure classifier ---
echo "--- Test 52: the auto-merge sentinel is not a failure reason ---"

sentinel52="aitask: auto-merged 2 task-data conflict(s) during pull - rebase completed"
assert_eq "52: the sentinel alone classifies as unknown, not a failure mode" \
    "unknown" "$(_task_push_classify "" "$sentinel52")"
# Named negative controls: these are the two arms an ill-chosen wording would
# have collided with.
TOTAL=$((TOTAL + 1))
cls52="$(_task_push_classify "" "$sentinel52")"
if [[ "$cls52" == "rebase_conflict" || "$cls52" == "rebase_in_progress" ]]; then
    FAIL=$((FAIL + 1))
    echo "FAIL: 52: the sentinel was classified as $cls52"
else
    PASS=$((PASS + 1))
fi

# --- Test 53: the flags RESET between calls in one shell ---
echo "--- Test 53: TASK_*_AUTOMERGED do not leak into the next call ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

seed_sample_task
advance_remote_task now "[ui]" "2026-01-01 10:00"
write_sample_task aitasks/t1_sample.md backlog "[api, ui]" "2026-01-01 10:00"
git add -A
git commit -m "local: change labels" --quiet

task_sync 2>/dev/null
assert_eq "53: first sync auto-merged" "1" "$TASK_SYNC_AUTOMERGED"
# Second call in the SAME shell, nothing to do. aitask_pick_own.sh calls
# task_sync and task_push in one process, so a leaked flag would make an
# ordinary call report a merge that never happened.
task_sync 2>/dev/null
assert_eq "53: second sync is up-to-date" "up-to-date" "$TASK_SYNC_STATUS"
assert_eq "53: and TASK_SYNC_AUTOMERGED was reset" "" "$TASK_SYNC_AUTOMERGED"

task_push 2>/dev/null
assert_eq "53: the push had no conflict to merge" "" "$TASK_PUSH_AUTOMERGED"

popd > /dev/null || exit 1

# --- Test 54: multi-round replay — TWO conflicting local commits ---
echo "--- Test 54: two replayed commits both auto-merge (loop, not one shot) ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

seed_sample_task
advance_remote_task now "[ui]" "2026-01-01 10:00"
# TWO separate local commits, each touching a different adjacent field, so the
# rebase replays two patches and BOTH overlap the remote's boardcol hunk.
write_sample_task aitasks/t1_sample.md backlog "[api, ui]" "2026-01-01 10:00"
git add -A
git commit -m "local A: change labels" --quiet
write_sample_task aitasks/t1_sample.md backlog "[api, ui]" "2026-03-02 09:15"
git add -A
git commit -m "local B: change updated_at" --quiet

task_sync 2>"$TEST_TMPDIR/am54_err.txt"
sync_rc=$?
sync_err="$(cat "$TEST_TMPDIR/am54_err.txt")"

assert_success "54: task_sync returns 0" "$sync_rc"
assert_eq "54: TASK_SYNC_STATUS is synced" "synced" "$TASK_SYNC_STATUS"
assert_eq "54: TASK_SYNC_AUTOMERGED is set" "1" "$TASK_SYNC_AUTOMERGED"
# THE DISCRIMINATOR. A count of 1 means only one round ran and this fixture
# degenerated into Test 48 — fix the fixture, never this assertion.
assert_contains "54: the sentinel reports TWO merged conflicts (both rounds ran)" \
    "auto-merged task-data conflict(s) during pull (2 file(s))" "$sync_err"
assert_eq_trim "54: both local commits were replayed and kept" "2" \
    "$(git rev-list --count '@{u}..HEAD' 2>/dev/null)"
merged54="$(cat aitasks/t1_sample.md)"
assert_contains "54: local boardcol kept" "boardcol: backlog" "$merged54"
assert_contains "54: local label survives" "api" "$merged54"
assert_contains "54: commit B's updated_at survives" "2026-03-02 09:15" "$merged54"
assert_eq_trim "54: no rebase left behind" "" "$(probe_wedge)"
# Negative control for the round cap: a cap that tripped early would satisfy
# every abort-free assertion above for the wrong reason.
assert_not_contains "54: the round cap did not fire on a healthy replay" \
    "auto-merge gave up after" "$sync_err"

popd > /dev/null || exit 1

# --- Test 55: the round cap FIRES, and fails safe when it does ---
echo "--- Test 55: AIT_AUTOMERGE_MAX_ROUNDS exhaustion -> clean abort ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

seed_sample_task
advance_remote_task now "[ui]" "2026-01-01 10:00"
write_sample_task aitasks/t1_sample.md backlog "[api, ui]" "2026-01-01 10:00"
git add -A
git commit -m "local A" --quiet
write_sample_task aitasks/t1_sample.md backlog "[api, ui]" "2026-03-02 09:15"
git add -A
git commit -m "local B" --quiet
write_sample_task aitasks/t1_sample.md backlog "[api, ui, web]" "2026-03-02 09:15"
git add -A
git commit -m "local C" --quiet
before_head_55="$(git rev-parse HEAD)"

AIT_AUTOMERGE_MAX_ROUNDS=1 task_sync 2>"$TEST_TMPDIR/am55_err.txt"
sync_rc=$?
sync_err="$(cat "$TEST_TMPDIR/am55_err.txt")"

assert_success "55: task_sync still returns 0 (best-effort contract)" "$sync_rc"
assert_contains "55: the cap diagnostic names the round budget" \
    "auto-merge gave up after 1 rounds" "$sync_err"
assert_eq "55: TASK_SYNC_STATUS is failed" "failed" "$TASK_SYNC_STATUS"
assert_eq "55: TASK_SYNC_REASON is rebase_conflict" "rebase_conflict" "$TASK_SYNC_REASON"
# A partially auto-merged run that then gave up is NOT an auto-merge.
assert_eq "55: TASK_SYNC_AUTOMERGED stays unset" "" "$TASK_SYNC_AUTOMERGED"
# The whole point of the cap: the shared worktree is not left blocked.
assert_eq_trim "55: the rebase was aborted, nothing left in progress" "" "$(probe_wedge)"
assert_eq_trim "55: the abort restored orig-head — all three local commits kept" \
    "$before_head_55" "$(git rev-parse HEAD)"
assert_next_commit_succeeds "55: the next task_git commit succeeds"

popd > /dev/null || exit 1

# --- Test 56: a malformed cap override FAILS CLOSED to the default ---
echo "--- Test 56: AIT_AUTOMERGE_MAX_ROUNDS junk/0 cannot disable the cap ---"

for bad_cap in abc 0; do
    setup_remote_and_clone
    pushd "$TEST_LOCAL" > /dev/null || exit 1
    reload_task_utils
    _AIT_DATA_WORKTREE="."

    seed_sample_task
    advance_remote_task now "[ui]" "2026-01-01 10:00"
    write_sample_task aitasks/t1_sample.md backlog "[api, ui]" "2026-01-01 10:00"
    git add -A
    git commit -m "local A" --quiet
    write_sample_task aitasks/t1_sample.md backlog "[api, ui]" "2026-03-02 09:15"
    git add -A
    git commit -m "local B" --quiet

    AIT_AUTOMERGE_MAX_ROUNDS="$bad_cap" task_sync 2>"$TEST_TMPDIR/am56_err.txt"
    sync_err="$(cat "$TEST_TMPDIR/am56_err.txt")"

    # A cap of "abc"/0 taken literally would give up on round 1 (or never run);
    # falling closed to the default 50 lets the two-round replay converge.
    assert_eq "56 ($bad_cap): falls closed to the default, so the replay converges" \
        "synced" "$TASK_SYNC_STATUS"
    assert_not_contains "56 ($bad_cap): the cap did not fire" \
        "auto-merge gave up after" "$sync_err"

    popd > /dev/null || exit 1
done

# --- Test 57: pick_own --sync converges and still prints exactly SYNCED ---
echo "--- Test 57: aitask_pick_own.sh --sync auto-merges, token unchanged ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1

# The whole tree, as tests/test_sync.sh does: the merge driver lives under
# board/ and imports from lib/, so the itemized scaffold cannot supply it.
cp -r "$PROJECT_DIR/.aitask-scripts" ./.aitask-scripts
mkdir -p aitasks aiplans
seed_sample_task
advance_remote_task now "[ui]" "2026-01-01 10:00"
write_sample_task aitasks/t1_sample.md backlog "[api, ui]" "2026-01-01 10:00"
git add -A
git commit -m "local: change labels" --quiet

sync_out="$(./.aitask-scripts/aitask_pick_own.sh --sync 2>"$TEST_TMPDIR/am57_err.txt")"
sync_rc=$?
sync_err="$(cat "$TEST_TMPDIR/am57_err.txt")"

assert_success "57: pick_own --sync returns 0" "$sync_rc"
# The cross-process token is DELIBERATELY unchanged — no SYNCED:automerged.
assert_eq "57: stdout is still exactly SYNCED" "SYNCED" "$sync_out"
assert_contains "57: the human notice goes to stderr" \
    "auto-merged task-data conflict(s) during pull" "$sync_err"
merged57="$(cat aitasks/t1_sample.md)"
assert_contains "57: both sides merged" "api" "$merged57"
assert_contains "57: both sides merged (remote label)" "ui" "$merged57"

popd > /dev/null || exit 1

# --- Test 58: the push progress grant is REACHED and terminates ---
echo "--- Test 58: every retry auto-merges a fresh conflict; stops at the cap ---"

# The grant only fires when a retry pull actually AUTO-MERGES something, so the
# remote must hand each retry a NEW frontmatter conflict. A fixture that merely
# rejects pushes never reaches the grant at all and would pass against the old
# three-attempt loop — which is exactly what the first version of this test did.
#
# The shim therefore does two things per push: advance the remote with a fresh
# conflicting `boardcol` edit, and reject the push. Every subsequent pull then
# finds a real conflict, auto-merges it, and returns an attempt to the budget —
# until the budget runs out.
setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

seed_sample_task
# One local commit on an ADJACENT field, so every replay overlaps the remote's
# boardcol hunk.
write_sample_task aitasks/t1_sample.md backlog "[api, ui]" "2026-01-01 10:00"
git add -A
git commit -m "local claim" --quiet

REAL_GIT="$(command -v git)"
SIDE58="$TEST_TMPDIR/side58"
git clone --quiet "$TEST_REMOTE" "$SIDE58" 2>/dev/null
git -C "$SIDE58" config user.email "other@test.com"
git -C "$SIDE58" config user.name "Other"

# Advance the remote by one conflicting commit. Calls git by ABSOLUTE path so it
# is never intercepted by the shim below.
cat > "$TEST_TMPDIR/bump58.sh" <<BUMPEOF
#!/usr/bin/env bash
n="\$1"
"$REAL_GIT" -C "$SIDE58" pull --quiet --rebase >/dev/null 2>&1
mkdir -p "$SIDE58/aitasks"
cat > "$SIDE58/aitasks/t1_sample.md" <<TASKEOF
---
priority: high
status: Ready
boardcol: col\$n
labels: [ui]
updated_at: 2026-01-01 10:00
---
Task body stays the same
TASKEOF
"$REAL_GIT" -C "$SIDE58" add -A
"$REAL_GIT" -C "$SIDE58" commit -q -m "remote bump \$n"
"$REAL_GIT" -C "$SIDE58" push -q
BUMPEOF
chmod +x "$TEST_TMPDIR/bump58.sh"

: > "$TEST_TMPDIR/push_attempts.txt"
SHIM58="$TEST_TMPDIR/shim58"
mkdir -p "$SHIM58"
cat > "$SHIM58/git" <<SHIMEOF
#!/usr/bin/env bash
for _a in "\$@"; do
    if [[ "\$_a" == "push" ]]; then
        echo x >> "$TEST_TMPDIR/push_attempts.txt"
        n=\$(wc -l < "$TEST_TMPDIR/push_attempts.txt" | tr -d ' ')
        bash "$TEST_TMPDIR/bump58.sh" "\$n" >/dev/null 2>&1
        echo "error: failed to push some refs (non-fast-forward)" >&2
        exit 1
    fi
done
exec "$REAL_GIT" "\$@"
SHIMEOF
chmod +x "$SHIM58/git"

PATH="$SHIM58:$PATH" task_push 2>/dev/null
push_rc=$?
attempts58="$(wc -l < "$TEST_TMPDIR/push_attempts.txt" | tr -d ' ')"

assert_success "58: task_push returns 0 (best-effort contract)" "$push_rc"
assert_eq "58: TASK_PUSH_STATUS is failed" "failed" "$TASK_PUSH_STATUS"
# The grant was actually REACHED — without this the attempt count below could
# be right for the wrong reason.
assert_eq "58: the retries really did auto-merge" "1" "$TASK_PUSH_AUTOMERGED"
# EXACTLY max_attempts(3) + _AIT_PUSH_PROGRESS_GRANTS(2) = 5. Asserting the
# exact number is what discriminates: the pre-grant implementation stops at 3,
# and an unbounded grant never stops at all.
assert_eq "58: stops at exactly the hard cap (3 attempts + 2 grants)" \
    "5" "$attempts58"
assert_eq_trim "58: no rebase left behind" "" "$(probe_wedge)"

popd > /dev/null || exit 1

# --- Test 59: a RECOVERED conflict must not classify a later failure ---
echo "--- Test 59: post-recovery network failure is not called rebase_conflict ---"

# _task_pull_rebase forwards git's own "CONFLICT (content)" text even when the
# auto-merge then completes the rebase. If that output reached the classifier,
# its rebase_conflict arm — ordered AHEAD of the remote/diverged arms — would
# win over the real blocker and tell the user to reconcile a divergence that no
# longer exists. Only a FAILED pull may contribute to the classification.
setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

seed_sample_task
advance_remote_task now "[ui]" "2026-01-01 10:00"
write_sample_task aitasks/t1_sample.md backlog "[api, ui]" "2026-01-01 10:00"
git add -A
git commit -m "local claim" --quiet

REAL_GIT59="$(command -v git)"
SHIM59="$TEST_TMPDIR/shim59"
mkdir -p "$SHIM59"
: > "$TEST_TMPDIR/push59.txt"
# Push 1 goes through to the real git and is genuinely rejected (the remote is
# ahead), so the retry pull runs and auto-merges. Every LATER push fails as an
# unreachable remote — the blocker the classifier must actually report.
cat > "$SHIM59/git" <<SHIMEOF
#!/usr/bin/env bash
for _a in "\$@"; do
    if [[ "\$_a" == "push" ]]; then
        echo x >> "$TEST_TMPDIR/push59.txt"
        n=\$(wc -l < "$TEST_TMPDIR/push59.txt" | tr -d ' ')
        if [[ \$n -gt 1 ]]; then
            echo "fatal: Could not read from remote repository." >&2
            exit 128
        fi
        break
    fi
done
exec "$REAL_GIT59" "\$@"
SHIMEOF
chmod +x "$SHIM59/git"

PATH="$SHIM59:$PATH" task_push 2>/dev/null
push_rc=$?

assert_success "59: task_push returns 0" "$push_rc"
assert_eq "59: TASK_PUSH_STATUS is failed" "failed" "$TASK_PUSH_STATUS"
# Precondition, so the assertion below cannot pass vacuously: the run really did
# recover a conflict before the network failed.
assert_eq "59: a conflict WAS auto-merged during the retries" "1" "$TASK_PUSH_AUTOMERGED"
# THE DISCRIMINATOR. Pre-fix this reads rebase_conflict, because the recovered
# pull's CONFLICT text was still in the classification blob.
assert_eq "59: the real blocker is reported, not the recovered conflict" \
    "remote_unreachable" "$TASK_PUSH_REASON"
assert_contains "59: and the hint names the network, not a divergence" \
    "remote unreachable" "$(_task_push_reason_hint "$TASK_PUSH_REASON")"

popd > /dev/null || exit 1

# --- Test 60: an UNRECOVERED conflict still classifies as rebase_conflict ---
echo "--- Test 60: negative control - a real conflict is still a real blocker ---"

# The other direction of Test 59: narrowing the classifier input must not make
# it blind to a conflict that genuinely did not resolve.
setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

seed_sample_task
# Diverging BODIES: the driver answers PARTIAL, the pull fails and aborts.
advance_remote_task backlog "[ui]" "2026-01-01 10:00" "remote rewrote the body"
write_sample_task aitasks/t1_sample.md backlog "[ui]" "2026-01-01 10:00" "local rewrote the body"
git add -A
git commit -m "local claim" --quiet

task_push 2>/dev/null
assert_eq "60: TASK_PUSH_STATUS is failed" "failed" "$TASK_PUSH_STATUS"
assert_eq "60: an unresolved conflict is still rebase_conflict" \
    "rebase_conflict" "$TASK_PUSH_REASON"
assert_eq "60: and nothing claims an auto-merge" "" "$TASK_PUSH_AUTOMERGED"

popd > /dev/null || exit 1

# --- Summary ---
# --- Summary ---
echo ""
echo "=== Results: $PASS passed, $FAIL failed, $TOTAL total ==="
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
