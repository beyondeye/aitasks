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
# only runs task_sync + aitask_lock.sh --cleanup (already `|| true`).
setup_pick_own_cli() {
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"   .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh"    .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_pick_own.sh"   .aitask-scripts/
    chmod +x .aitask-scripts/aitask_pick_own.sh
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

# --- Summary ---
echo ""
echo "=== Results: $PASS passed, $FAIL failed, $TOTAL total ==="
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
