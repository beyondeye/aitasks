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

assert_eq "classify: remote unreachable" "remote_unreachable" \
    "$(_task_push_classify "fatal: '/nonexistent/path/repo.git' does not appear to be a git repository" "")"

assert_eq "classify: diverged with no rebase blocker" "diverged" \
    "$(_task_push_classify " ! [rejected]        master -> master (fetch first)" "")"

assert_eq "classify: unrecognised output falls back to unknown" "unknown" \
    "$(_task_push_classify "fatal: something nobody has seen before" "")"

# Each code must map to a distinct, non-empty hint.
assert_contains "hint: dirty worktree points at the syncer" "ait syncer" \
    "$(_task_push_reason_hint dirty_worktree)"
assert_contains "hint: rebase conflict points at --abort" "rebase --abort" \
    "$(_task_push_reason_hint rebase_conflict)"
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

echo "local" > conflict.txt
git add conflict.txt
git commit -m "local conflicting commit" --quiet

# Same file, different content, from "another user".
conflict_tmp="$(mktemp -d "${TMPDIR:-/tmp}/ait_push_conflict_XXXXXX")"
git clone --quiet "$TEST_REMOTE" "$conflict_tmp/other" 2>/dev/null
git -C "$conflict_tmp/other" config user.email "other@test.com"
git -C "$conflict_tmp/other" config user.name "Other"
echo "remote" > "$conflict_tmp/other/conflict.txt"
git -C "$conflict_tmp/other" add conflict.txt
git -C "$conflict_tmp/other" commit -m "remote conflicting commit" --quiet
git -C "$conflict_tmp/other" push --quiet 2>/dev/null
rm -rf "$conflict_tmp"

task_sync 2>"$TEST_TMPDIR/sync_conflict_err.txt"
sync_rc=$?
sync_err="$(cat "$TEST_TMPDIR/sync_conflict_err.txt")"

assert_success "task_sync returns 0 on rebase conflict" "$sync_rc"
assert_eq "TASK_SYNC_STATUS is failed (conflict)" "failed" "$TASK_SYNC_STATUS"
assert_eq "TASK_SYNC_REASON is rebase_conflict" "rebase_conflict" "$TASK_SYNC_REASON"
assert_contains "warning offers the rebase recovery" "rebase --abort" "$sync_err"

# Leave the fixture recoverable (counts mid-rebase are meaningless, so they
# are deliberately not asserted above).
git rebase --abort 2>/dev/null || true

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

# --- Summary ---
echo ""
echo "=== Results: $PASS passed, $FAIL failed, $TOTAL total ==="
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
