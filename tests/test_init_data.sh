#!/usr/bin/env bash
# test_init_data.sh - Tests for aitask_init_data.sh (lightweight data branch initialization)
# Run: bash tests/test_init_data.sh

set -e

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

assert_symlink() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -L "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc ('$path' is not a symlink)"
    fi
}

assert_not_symlink() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ ! -L "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc ('$path' should not be a symlink)"
    fi
}

# --- Setup helpers ---

DEFAULT_BRANCH="$(git config --global init.defaultBranch 2>/dev/null || echo "master")"

setup_repo_with_remote() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    git init --bare --quiet "$tmpdir/remote.git"
    git clone --quiet "$tmpdir/remote.git" "$tmpdir/local" 2>/dev/null
    (
        cd "$tmpdir/local"
        git config user.email "test@test.com"
        git config user.name "Test"
        echo "# Test Project" > README.md
        git add README.md
        git commit -m "init" --quiet
        git push --quiet 2>/dev/null
    )
    echo "$tmpdir"
}

setup_local_repo() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    (
        cd "$tmpdir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"
        echo "# Test Project" > README.md
        git add README.md
        git commit -m "init" --quiet
    )
    echo "$tmpdir"
}

# Copy the init_data script and its dependency into a test repo
install_script() {
    local repo_dir="$1"
    setup_fake_aitask_repo "$repo_dir"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_init_data.sh" "$repo_dir/.aitask-scripts/"
}

# Create aitask-data branch with content using setup_data_branch from aitask_setup.sh
# This sources setup.sh's function to create a proper data branch setup
create_data_branch_setup() {
    local repo_dir="$1"
    # Copy required scripts for setup
    setup_fake_aitask_repo "$repo_dir"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" "$repo_dir/.aitask-scripts/"
    # aitask_setup.sh sources lib/github_release.sh at startup (t1069); its
    # other startup dep, python_resolve.sh, is provided by setup_fake_aitask_repo.
    cp "$PROJECT_DIR/.aitask-scripts/lib/github_release.sh" "$repo_dir/.aitask-scripts/lib/"
    cp -r "$PROJECT_DIR/seed" "$repo_dir/seed" 2>/dev/null || true
    (
        cd "$repo_dir"
        # Source setup.sh to get setup_data_branch function
        SCRIPT_DIR="$repo_dir/.aitask-scripts"
        source "$repo_dir/.aitask-scripts/lib/terminal_compat.sh"
        source "$repo_dir/.aitask-scripts/aitask_setup.sh" --source-only
        setup_data_branch </dev/null >/dev/null 2>&1
    )
}

set +euo pipefail

echo "=== aitask_init_data.sh Tests ==="
echo ""

# --- Test 1: Legacy mode ---
echo "--- Test 1: Legacy mode (real aitasks/ directory) ---"

TMPDIR_1="$(setup_local_repo)"
install_script "$TMPDIR_1"
mkdir -p "$TMPDIR_1/aitasks/metadata"

pushd "$TMPDIR_1" >/dev/null
output=$(bash .aitask-scripts/aitask_init_data.sh 2>/dev/null)
assert_eq_trim "Legacy mode output" "LEGACY_MODE" "$output"
assert_not_symlink "aitasks/ is not a symlink" "aitasks"
popd >/dev/null

rm -rf "$TMPDIR_1"

# --- Test 2: Already initialized ---
echo "--- Test 2: Already initialized (worktree exists) ---"

TMPDIR_2="$(setup_repo_with_remote)"
install_script "$TMPDIR_2/local"
create_data_branch_setup "$TMPDIR_2/local"

pushd "$TMPDIR_2/local" >/dev/null
output=$(bash .aitask-scripts/aitask_init_data.sh 2>/dev/null)
assert_eq_trim "Already init output" "ALREADY_INIT" "$output"
assert_symlink "aitasks/ is a symlink" "aitasks"
assert_symlink "aiplans/ is a symlink" "aiplans"
popd >/dev/null

rm -rf "$TMPDIR_2"

# --- Test 3: No data branch ---
echo "--- Test 3: No data branch (fresh repo) ---"

TMPDIR_3="$(setup_local_repo)"
install_script "$TMPDIR_3"

pushd "$TMPDIR_3" >/dev/null
output=$(bash .aitask-scripts/aitask_init_data.sh 2>/dev/null)
assert_eq_trim "No data branch output" "NO_DATA_BRANCH" "$output"
popd >/dev/null

rm -rf "$TMPDIR_3"

# --- Test 4: Initialize from local branch ---
echo "--- Test 4: Initialize from local branch ---"

TMPDIR_4="$(setup_repo_with_remote)"
install_script "$TMPDIR_4/local"
create_data_branch_setup "$TMPDIR_4/local"

# Remove worktree and symlinks but keep the branch
pushd "$TMPDIR_4/local" >/dev/null
git worktree remove .aitask-data --force 2>/dev/null
rm -f aitasks aiplans

# Verify branch still exists locally
branch_exists=$(git show-ref --verify refs/heads/aitask-data >/dev/null 2>&1 && echo "yes" || echo "no")
assert_eq_trim "aitask-data branch exists locally" "yes" "$branch_exists"

# Run init
output=$(bash .aitask-scripts/aitask_init_data.sh 2>/dev/null)
assert_eq_trim "Initialize from local branch output" "INITIALIZED" "$output"
assert_symlink "aitasks/ is a symlink after init" "aitasks"
assert_symlink "aiplans/ is a symlink after init" "aiplans"
assert_dir_exists ".aitask-data worktree created" ".aitask-data"
popd >/dev/null

rm -rf "$TMPDIR_4"

# --- Test 5: Initialize from remote branch ---
echo "--- Test 5: Initialize from remote branch (second clone) ---"

TMPDIR_5="$(setup_repo_with_remote)"
install_script "$TMPDIR_5/local"
create_data_branch_setup "$TMPDIR_5/local"

# Create a second clone — aitask-data branch exists on remote but not locally
git clone --quiet "$TMPDIR_5/remote.git" "$TMPDIR_5/clone2" 2>/dev/null
install_script "$TMPDIR_5/clone2"
(cd "$TMPDIR_5/clone2" && git config user.email "test@test.com" && git config user.name "Test")

pushd "$TMPDIR_5/clone2" >/dev/null
# Verify branch is NOT local but IS on remote
local_branch=$(git show-ref --verify refs/heads/aitask-data 2>/dev/null && echo "yes" || echo "no")
remote_branch=$(git ls-remote --heads origin aitask-data 2>/dev/null | grep -q aitask-data && echo "yes" || echo "no")
assert_eq_trim "aitask-data NOT local in clone2" "no" "$local_branch"
assert_eq_trim "aitask-data IS on remote" "yes" "$remote_branch"

# Run init
output=$(bash .aitask-scripts/aitask_init_data.sh 2>/dev/null)
assert_eq_trim "Initialize from remote branch output" "INITIALIZED" "$output"
assert_symlink "aitasks/ is a symlink in clone2" "aitasks"
assert_symlink "aiplans/ is a symlink in clone2" "aiplans"
assert_dir_exists ".aitask-data worktree created in clone2" ".aitask-data"
popd >/dev/null

rm -rf "$TMPDIR_5"

# --- Test 6: Broken symlink repair ---
echo "--- Test 6: Broken symlink repair ---"

TMPDIR_6="$(setup_repo_with_remote)"
install_script "$TMPDIR_6/local"
create_data_branch_setup "$TMPDIR_6/local"

pushd "$TMPDIR_6/local" >/dev/null
# Remove worktree but leave broken symlinks
git worktree remove .aitask-data --force 2>/dev/null

# Verify symlinks are broken
assert_symlink "aitasks/ is still a symlink" "aitasks"
broken="no"
[[ ! -e "aitasks" ]] && broken="yes"
assert_eq_trim "aitasks/ symlink is broken" "yes" "$broken"

# Run init
output=$(bash .aitask-scripts/aitask_init_data.sh 2>/dev/null)
assert_eq_trim "Broken symlink repair output" "INITIALIZED" "$output"
assert_symlink "aitasks/ is a symlink after repair" "aitasks"
# Verify symlinks now work (target exists)
valid="no"
[[ -e "aitasks" ]] && valid="yes"
assert_eq_trim "aitasks/ symlink is valid after repair" "yes" "$valid"
popd >/dev/null

rm -rf "$TMPDIR_6"

# --- Test 7: Idempotency ---
echo "--- Test 7: Idempotency (double run) ---"

TMPDIR_7="$(setup_repo_with_remote)"
install_script "$TMPDIR_7/local"
create_data_branch_setup "$TMPDIR_7/local"

pushd "$TMPDIR_7/local" >/dev/null
output1=$(bash .aitask-scripts/aitask_init_data.sh 2>/dev/null)
output2=$(bash .aitask-scripts/aitask_init_data.sh 2>/dev/null)
assert_eq_trim "First run: ALREADY_INIT" "ALREADY_INIT" "$output1"
assert_eq_trim "Second run: ALREADY_INIT" "ALREADY_INIT" "$output2"
popd >/dev/null

rm -rf "$TMPDIR_7"

# --- Test 8: Missing symlinks with existing worktree ---
echo "--- Test 8: Missing symlinks with existing worktree ---"

TMPDIR_8="$(setup_repo_with_remote)"
install_script "$TMPDIR_8/local"
create_data_branch_setup "$TMPDIR_8/local"

pushd "$TMPDIR_8/local" >/dev/null
# Delete only symlinks, keep worktree
rm -f aitasks aiplans

# Verify worktree still exists
assert_dir_exists "Worktree still exists" ".aitask-data"

# Run init
output=$(bash .aitask-scripts/aitask_init_data.sh 2>/dev/null)
assert_eq_trim "Missing symlinks output" "ALREADY_INIT" "$output"
assert_symlink "aitasks/ symlink recreated" "aitasks"
assert_symlink "aiplans/ symlink recreated" "aiplans"
popd >/dev/null

rm -rf "$TMPDIR_8"

# --- Test 9: Help flag ---
echo "--- Test 9: Help flag ---"

output=$(bash "$PROJECT_DIR/.aitask-scripts/aitask_init_data.sh" --help 2>/dev/null)
assert_contains "Help output mentions INITIALIZED" "INITIALIZED" "$output"
assert_contains "Help output mentions LEGACY_MODE" "LEGACY_MODE" "$output"
assert_contains "Help output mentions --link-worktree" "--link-worktree" "$output"
assert_contains "Help output mentions LINKED" "LINKED" "$output"
assert_contains "Help output mentions NOT_INITIALIZED" "NOT_INITIALIZED" "$output"
assert_contains "Help output mentions WORKTREE_UNLINKED" "WORKTREE_UNLINKED" "$output"

# ===========================================================================
# --link-worktree (t1616)
#
# A `git worktree add` checkout of the code branch has no aitasks/aiplans
# symlinks — they are gitignored and live in the primary checkout — so ./ait
# run from inside it resolves aitasks/ locally and finds nothing, and every
# suite module reading aitasks/metadata/*.json dies with FileNotFoundError.
# These cases cover the happy path, the validate-and-repair contract, and
# every refusal, each with a negative control asserting nothing was written.
# ===========================================================================

FIXTURE_REL="aitasks/metadata/lw_fixture.json"

# lw_repo -> a branch-mode primary at $LW_MAIN with a task worktree at
# $LW_MAIN/aiwork/tA, and a distinguishable fixture on the data branch.
# Sets LW_TMP / LW_MAIN / LW_WT.
lw_repo() {
    local marker="${1:-primary}"
    LW_TMP="$(setup_repo_with_remote)"
    LW_MAIN="$LW_TMP/local"
    install_script "$LW_MAIN"
    create_data_branch_setup "$LW_MAIN"
    mkdir -p "$LW_MAIN/.aitask-data/aitasks/metadata"
    printf '{"marker":"%s"}\n' "$marker" > "$LW_MAIN/.aitask-data/$FIXTURE_REL"
    git -C "$LW_MAIN" worktree add -q -b aitask/tA "$LW_MAIN/aiwork/tA" HEAD
    LW_WT="$LW_MAIN/aiwork/tA"
}

# lw_run <dir> -> stdout in LW_OUT, stderr in LW_ERR, status in LW_RC.
lw_run() {
    local errfile
    errfile="$(mktemp)"
    LW_RC=0
    LW_OUT="$(bash "$LW_MAIN/.aitask-scripts/aitask_init_data.sh" \
        --link-worktree "$1" 2>"$errfile")" || LW_RC=$?
    LW_ERR="$(cat "$errfile")"
    rm -f "$errfile"
}

# assert_untouched <desc> <dir> -> none of the three names exist under <dir>.
assert_no_layout() {
    local desc="$1" dir="$2" name
    for name in .aitask-data aitasks aiplans; do
        TOTAL=$((TOTAL + 1))
        if [[ -e "$dir/$name" || -L "$dir/$name" ]]; then
            FAIL=$((FAIL + 1))
            echo "FAIL: $desc ('$dir/$name' was created)"
        else
            PASS=$((PASS + 1))
        fi
    done
}

# --- Test 10: creates the layout and the data becomes readable ---
echo "--- Test 10: --link-worktree creates the layout ---"

lw_repo primary
lw_run "$LW_WT"
assert_eq_trim "10: reports LINKED" "LINKED" "$LW_OUT"
assert_eq "10: exits 0" "0" "$LW_RC"
assert_symlink "10: .aitask-data symlink" "$LW_WT/.aitask-data"
assert_symlink "10: aitasks symlink" "$LW_WT/aitasks"
assert_symlink "10: aiplans symlink" "$LW_WT/aiplans"
# The defect this fixes: the fixture must be readable THROUGH the worktree.
assert_eq "10: fixture readable from the worktree" \
    '{"marker":"primary"}' "$(cat "$LW_WT/$FIXTURE_REL" 2>/dev/null)"

# --- Test 11: branch-mode routing probe ---
# _ait_detect_data_worktree() (lib/task_utils.sh) selects branch vs legacy mode
# by testing `.aitask-data/.git` relative to cwd. Assert that literal probe, not
# merely that links exist — it is what makes ./ait git route to the data branch
# instead of silently degrading to legacy mode inside the worktree.
echo "--- Test 11: branch-mode routing probe ---"

TOTAL=$((TOTAL + 1))
if [[ -d "$LW_WT/.aitask-data/.git" || -f "$LW_WT/.aitask-data/.git" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: 11: .aitask-data/.git not visible from the worktree (ait git would use legacy mode)"
fi

# --- Test 12: idempotent ---
echo "--- Test 12: idempotency ---"

before_data="$(readlink "$LW_WT/.aitask-data")"
before_tasks="$(readlink "$LW_WT/aitasks")"
before_plans="$(readlink "$LW_WT/aiplans")"
lw_run "$LW_WT"
assert_eq_trim "12: second run reports ALREADY_LINKED" "ALREADY_LINKED" "$LW_OUT"
assert_eq "12: .aitask-data target unchanged" "$before_data" "$(readlink "$LW_WT/.aitask-data")"
assert_eq "12: aitasks target unchanged" "$before_tasks" "$(readlink "$LW_WT/aitasks")"
assert_eq "12: aiplans target unchanged" "$before_plans" "$(readlink "$LW_WT/aiplans")"
rm -rf "$LW_TMP"

# --- Test 13: dangling link is repaired ---
echo "--- Test 13: dangling link repair ---"

lw_repo primary
rm -f "$LW_WT/aitasks"
ln -s .aitask-data/gone "$LW_WT/aitasks"
lw_run "$LW_WT"
assert_eq_trim "13: reports LINKED" "LINKED" "$LW_OUT"
assert_eq "13: aitasks repaired to the canonical target" \
    ".aitask-data/aitasks" "$(readlink "$LW_WT/aitasks")"
assert_eq "13: fixture readable again" \
    '{"marker":"primary"}' "$(cat "$LW_WT/$FIXTURE_REL" 2>/dev/null)"
rm -rf "$LW_TMP"

# --- Test 14: stale .aitask-data pointing at ANOTHER checkout ---
# A resolving link is not a correct link. A worktree reused across checkouts can
# carry .aitask-data -> /other/checkout/.aitask-data, which resolves fine and
# would silently point ./ait and the whole suite at another repo's task data.
# The discriminating assertion is which fixture is read, not link identity.
echo "--- Test 14: stale cross-checkout .aitask-data is repaired ---"

lw_repo primary
OTHER_TMP="$(setup_repo_with_remote)"
install_script "$OTHER_TMP/local"
create_data_branch_setup "$OTHER_TMP/local"
mkdir -p "$OTHER_TMP/local/.aitask-data/aitasks/metadata"
printf '{"marker":"%s"}\n' "wrong-checkout" > "$OTHER_TMP/local/.aitask-data/$FIXTURE_REL"

rm -f "$LW_WT/.aitask-data"
ln -s "$OTHER_TMP/local/.aitask-data" "$LW_WT/.aitask-data"
lw_run "$LW_WT"
assert_eq_trim "14: reports LINKED, not ALREADY_LINKED" "LINKED" "$LW_OUT"
assert_eq "14: .aitask-data repointed at this checkout" \
    "$(cd "$LW_MAIN/.aitask-data" && pwd -P)" \
    "$(cd "$LW_WT/.aitask-data" && pwd -P)"
assert_eq "14: reads THIS repo's fixture, not the other checkout's" \
    '{"marker":"primary"}' "$(cat "$LW_WT/$FIXTURE_REL" 2>/dev/null)"
assert_contains "14: stderr names the old target" \
    "$OTHER_TMP/local/.aitask-data" "$LW_ERR"
rm -rf "$LW_TMP" "$OTHER_TMP"

# --- Test 15: stale aitasks target ---
echo "--- Test 15: stale aitasks target is repaired ---"

lw_repo primary
rm -f "$LW_WT/aitasks"
ln -s .aitask-data/aiplans "$LW_WT/aitasks"   # resolves, but is the wrong target
lw_run "$LW_WT"
assert_eq_trim "15: reports LINKED" "LINKED" "$LW_OUT"
assert_eq "15: aitasks repaired" ".aitask-data/aitasks" "$(readlink "$LW_WT/aitasks")"
assert_eq "15: aiplans left correct" ".aitask-data/aiplans" "$(readlink "$LW_WT/aiplans")"
rm -rf "$LW_TMP"

# --- Test 15b: stale aiplans target — the symmetric case ---
# Case 15 alone does not cover this: a validate-and-repair loop that only
# inspects the first element of AIT_DATA_LINKS passes 15 and every other case
# while leaving aiplans pointed at another tree. Each link is probed with the
# other held correct, so the loop's second iteration is exercised.
echo "--- Test 15b: stale aiplans target is repaired ---"

lw_repo primary
rm -f "$LW_WT/aiplans"
ln -s .aitask-data/aitasks "$LW_WT/aiplans"
lw_run "$LW_WT"
assert_eq_trim "15b: reports LINKED" "LINKED" "$LW_OUT"
assert_eq "15b: aiplans repaired" ".aitask-data/aiplans" "$(readlink "$LW_WT/aiplans")"
assert_eq "15b: aitasks left correct" ".aitask-data/aitasks" "$(readlink "$LW_WT/aitasks")"
rm -rf "$LW_TMP"

# --- Test 16: non-symlink entry is refused, and NOTHING else is written ---
# The second half is what tests the read-only preflight: a sequential per-entry
# implementation creates .aitask-data before it ever reaches the conflict.
echo "--- Test 16: non-symlink entry refused, nothing written ---"

lw_repo primary
rm -f "$LW_WT/.aitask-data" "$LW_WT/aitasks" "$LW_WT/aiplans"
mkdir -p "$LW_WT/aitasks"
echo "keepme" > "$LW_WT/aitasks/user.txt"
lw_run "$LW_WT"
assert_exit_nonzero_rc "16: exits non-zero" "$LW_RC"
assert_eq "16: the real directory's file is untouched" \
    "keepme" "$(cat "$LW_WT/aitasks/user.txt" 2>/dev/null)"
TOTAL=$((TOTAL + 1))
if [[ ! -e "$LW_WT/.aitask-data" && ! -L "$LW_WT/.aitask-data" \
      && ! -e "$LW_WT/aiplans" && ! -L "$LW_WT/aiplans" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: 16: preflight did not run before writing (other entries were created)"
fi
rm -rf "$LW_TMP"

# --- Test 16b: conflict on the LAST entry, earlier ones stale-but-repairable ---
# Proves preflight ran before ANY repair, not merely before the conflicting one.
echo "--- Test 16b: late conflict leaves earlier stale entries untouched ---"

lw_repo primary
rm -f "$LW_WT/.aitask-data" "$LW_WT/aitasks" "$LW_WT/aiplans"
ln -s "$LW_TMP" "$LW_WT/.aitask-data"          # stale, repairable
ln -s .aitask-data/aiplans "$LW_WT/aitasks"    # stale, repairable
mkdir -p "$LW_WT/aiplans"                      # conflict, processed last
echo "keepme" > "$LW_WT/aiplans/user.txt"
lw_run "$LW_WT"
assert_exit_nonzero_rc "16b: exits non-zero" "$LW_RC"
assert_eq "16b: .aitask-data still carries its ORIGINAL stale target" \
    "$LW_TMP" "$(readlink "$LW_WT/.aitask-data")"
assert_eq "16b: aitasks still carries its ORIGINAL stale target" \
    ".aitask-data/aiplans" "$(readlink "$LW_WT/aitasks")"
assert_eq "16b: the real directory's file is untouched" \
    "keepme" "$(cat "$LW_WT/aiplans/user.txt" 2>/dev/null)"
rm -rf "$LW_TMP"

# --- Test 17: an ordinary subdirectory of the primary is refused ---
# The negative control for the worktree-root guard. Without it, a plain subdir
# shares the primary's git-common-dir, resolves the same main root, and is
# trivially unequal to it — so it would pass every other guard and be linked.
echo "--- Test 17: ordinary subdirectory refused ---"

lw_repo primary
mkdir -p "$LW_MAIN/sub"
lw_run "$LW_MAIN/sub"
assert_exit_nonzero_rc "17: exits non-zero" "$LW_RC"
assert_contains "17: says it is not a worktree root" "not a worktree root" "$LW_ERR"
assert_no_layout "17: subdirectory left untouched" "$LW_MAIN/sub"

# --- Test 18: the main checkout is refused ---
echo "--- Test 18: main checkout refused ---"

lw_run "$LW_MAIN"
assert_exit_nonzero_rc "18: exits non-zero" "$LW_RC"
assert_contains "18: says it is the main checkout" "main checkout" "$LW_ERR"

# --- Test 19: the .aitask-data worktree is refused ---
# It is ALSO a registered worktree root, so it passes the root and main-root
# guards; linking it would nest .aitask-data inside the data branch.
echo "--- Test 19: .aitask-data worktree refused ---"

lw_run "$LW_MAIN/.aitask-data"
assert_exit_nonzero_rc "19: exits non-zero" "$LW_RC"
assert_contains "19: says it is the data worktree" ".aitask-data worktree" "$LW_ERR"
TOTAL=$((TOTAL + 1))
if [[ ! -e "$LW_MAIN/.aitask-data/.aitask-data" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: 19: nested .aitask-data was created inside the data worktree"
fi
rm -rf "$LW_TMP"

# --- Test 20: a directory outside any git repo is refused ---
echo "--- Test 20: non-repo directory refused ---"

lw_repo primary
OUTSIDE_DIR="$(mktemp -d)"
lw_run "$OUTSIDE_DIR"
assert_exit_nonzero_rc "20: exits non-zero" "$LW_RC"
assert_contains "20: says it is not inside a git repository" "not inside a git repository" "$LW_ERR"
assert_no_layout "20: directory left untouched" "$OUTSIDE_DIR"
rm -rf "$OUTSIDE_DIR" "$LW_TMP"

# --- Test 21: legacy-mode primary is a no-op ---
# Negative control for the no-op path: it must report, not fabricate a layout.
echo "--- Test 21: legacy-mode primary is a no-op ---"

TMPDIR_21="$(setup_local_repo)"
install_script "$TMPDIR_21"
mkdir -p "$TMPDIR_21/aitasks" "$TMPDIR_21/aiplans"
touch "$TMPDIR_21/aitasks/.keep"
git -C "$TMPDIR_21" add -A >/dev/null 2>&1
git -C "$TMPDIR_21" commit -qm "legacy layout" >/dev/null 2>&1
git -C "$TMPDIR_21" worktree add -q -b aitask/tL "$TMPDIR_21/aiwork/tL" HEAD

LW_MAIN="$TMPDIR_21"
lw_run "$TMPDIR_21/aiwork/tL"
assert_eq_trim "21: reports LEGACY_MODE" "LEGACY_MODE" "$LW_OUT"
assert_eq "21: exits 0" "0" "$LW_RC"
TOTAL=$((TOTAL + 1))
if [[ ! -L "$TMPDIR_21/aiwork/tL/.aitask-data" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: 21: legacy-mode no-op fabricated a .aitask-data link"
fi
rm -rf "$TMPDIR_21"

# --- Test 22: link-form pin (the install.sh:353 coupling) ---
# install.sh's ensure_data_root() recognizes ONLY `.aitask-data/<name>` and
# die()s on anything else. If the helper ever changes the spelling, fresh
# installs break with no other test failing.
echo "--- Test 22: canonical link form ---"

lw_repo primary
lw_run "$LW_WT"
assert_eq "22: aitasks target is exactly .aitask-data/aitasks" \
    ".aitask-data/aitasks" "$(readlink "$LW_WT/aitasks")"
assert_eq "22: aiplans target is exactly .aitask-data/aiplans" \
    ".aitask-data/aiplans" "$(readlink "$LW_WT/aiplans")"
assert_eq "22: primary's aitasks target is the same form" \
    ".aitask-data/aitasks" "$(readlink "$LW_MAIN/aitasks")"
rm -rf "$LW_TMP"

# ===========================================================================
# Bare (no-flag) invocation from a checkout that is not the primary (t1624)
#
# The bare form's Checks 1 and 2 probe RELATIVE paths, so they only ever see the
# checkout they are standing in. Inside a linked task worktree neither fires, and
# control used to reach Step 4 and attempt `git worktree add .aitask-data
# aitask-data` — which does one of two wrong things depending on the primary's
# state. These cases pin all three worktree outcomes plus the controls that keep
# the guard from swallowing a state that already answered correctly.
# ===========================================================================

# trace_run <dir> -> bare (no-flag) invocation with cwd=<dir>, run under a
# PATH-injected `git` shim that appends every argv to a log before delegating to
# the real git. Sets BARE_OUT / BARE_ERR / BARE_RC / TRACE.
#
# The trace is load-bearing. A REFUSED `git worktree add` (the branch is already
# checked out at the primary) and a NEVER-ATTEMPTED one leave IDENTICAL on-disk
# state: no .aitask-data directory, the same worktree list. Only the attempt
# itself distinguishes "the guard stopped it" from "Step 4 ran and git said no",
# so state assertions alone cannot catch a regression that reaches Step 4.
#
# The script is invoked by its PRIMARY path, as lw_run does: install_script
# copies into the working tree without committing, so a worktree cut from HEAD
# has no .aitask-scripts/ of its own. cwd is what the bare form keys on.
# strip_ansi <text> -> the text with CSI colour sequences removed. die_code()
# wraps its message in ${RED}…${NC} unconditionally, so a remedy extracted from
# stderr carries a trailing reset that breaks `eval`. Builds a literal ESC byte
# rather than using the \x1b shorthand, which is GNU-only — the same technique
# and the same reason as shadow_strip_ansi in aitask_shadow_capture.sh.
strip_ansi() {
    local esc
    esc="$(printf '\033')"
    printf '%s\n' "$1" | sed "s/${esc}\[[0-9;]*m//g"
}

trace_run() {
    local shimdir errfile tracelog real_git
    shimdir="$(mktemp -d)"
    errfile="$(mktemp)"
    tracelog="$(mktemp)"
    real_git="$(command -v git)"
    # real_git is baked in as an absolute path so the shim cannot recurse.
    cat > "$shimdir/git" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$tracelog"
exec "$real_git" "\$@"
EOF
    chmod +x "$shimdir/git"
    BARE_RC=0
    BARE_OUT="$(cd "$1" && PATH="$shimdir:$PATH" \
        bash "$LW_MAIN/.aitask-scripts/aitask_init_data.sh" 2>"$errfile")" || BARE_RC=$?
    BARE_ERR="$(cat "$errfile")"
    TRACE="$(cat "$tracelog")"
    rm -rf "$shimdir" "$errfile" "$tracelog"
}

# --- Test 23: bare invocation inside .aitask-data/ still reports LEGACY_MODE ---
# Characterization, and load-bearing for the guard below: the data worktree IS a
# registered linked worktree, so its toplevel differs from the main root exactly
# like a task worktree's does. Only Check 2 winning first (the data branch checks
# out a real aitasks/ directory) keeps it out of the linked-worktree guard.
echo "--- Test 23: bare invocation inside .aitask-data/ reports LEGACY_MODE ---"

lw_repo primary
trace_run "$LW_MAIN/.aitask-data"
assert_eq_trim "23: reports LEGACY_MODE" "LEGACY_MODE" "$BARE_OUT"
assert_eq "23: exits 0" "0" "$BARE_RC"
rm -rf "$LW_TMP"

# --- Test 24a: the defect — unlinked worktree, primary holds the branch ---
echo "--- Test 24a: unlinked worktree reports WORKTREE_UNLINKED ---"

lw_repo primary
trace_run "$LW_WT"
assert_eq_trim "24a: reports WORKTREE_UNLINKED" "WORKTREE_UNLINKED" "$BARE_OUT"
assert_eq "24a: exits 3" "3" "$BARE_RC"
assert_contains "24a: names the --link-worktree remedy" "--link-worktree" "$BARE_ERR"
assert_contains "24a: names this worktree" "$LW_WT" "$BARE_ERR"
# The whole point of t1624: the old message advised the command that just failed.
assert_not_contains "24a: does not advise the impossible add" \
    "git worktree add .aitask-data aitask-data" "$BARE_ERR"
assert_not_contains "24a: never attempted a worktree add" "worktree add" "$TRACE"
# Shim liveness. Without this, a failed PATH injection would leave an empty log
# and the not_contains above would pass vacuously.
assert_contains "24a: the git shim actually captured invocations" "rev-parse" "$TRACE"

# --- Test 24b: nested subdirectory — the guard keys on the worktree ROOT ---
# Also the copy-safety pin: from here a ./.aitask-scripts/... spelling does not
# resolve, so the printed command must carry an absolute script path.
echo "--- Test 24b: nested subdirectory of a worktree ---"

mkdir -p "$LW_WT/nested/deep"
trace_run "$LW_WT/nested/deep"
assert_eq_trim "24b: reports WORKTREE_UNLINKED from a nested subdir" \
    "WORKTREE_UNLINKED" "$BARE_OUT"
assert_eq "24b: exits 3" "3" "$BARE_RC"
# Extract the remedy verbatim and run it from that same nested subdirectory.
remedy="$(strip_ansi "$BARE_ERR" | sed -n 's/.*Run: //p')"
remedy_script="$(printf '%s\n' "$remedy" | sed -n 's/^"\([^"]*\)".*/\1/p')"
assert_contains "24b: the remedy script path is absolute" "/" "${remedy_script:0:1}"
assert_file_exists "24b: the remedy script path exists" "$remedy_script"
REMEDY_RC=0
REMEDY_OUT="$(cd "$LW_WT/nested/deep" && eval "$remedy" 2>/dev/null)" || REMEDY_RC=$?
assert_eq_trim "24b: the printed remedy links the worktree" "LINKED" "$REMEDY_OUT"
assert_eq "24b: the printed remedy exits 0" "0" "$REMEDY_RC"

# --- Test 24c: positive control — a LINKED worktree still reports ALREADY_INIT ---
# Without this, 24a would also pass if the guard fired unconditionally.
echo "--- Test 24c: linked worktree reports ALREADY_INIT ---"

# Establish the precondition here rather than inheriting 24b's remedy run, so a
# break in 24b fails 24b alone instead of also failing this control for the
# wrong reason. --link-worktree is idempotent, so this is safe either way.
lw_run "$LW_WT"
trace_run "$LW_WT"
assert_eq_trim "24c: reports ALREADY_INIT" "ALREADY_INIT" "$BARE_OUT"
assert_eq "24c: exits 0" "0" "$BARE_RC"

# --- Test 24d: the primary is unaffected by a worktree existing ---
echo "--- Test 24d: primary still reports ALREADY_INIT ---"

trace_run "$LW_MAIN"
assert_eq_trim "24d: reports ALREADY_INIT" "ALREADY_INIT" "$BARE_OUT"
assert_eq "24d: exits 0" "0" "$BARE_RC"

# --- Test 24e: an ordinary subdirectory of the primary is not a worktree ---
# Pins the toplevel-vs-$PWD discrimination: a plain subdir shares the primary's
# toplevel, so it must NOT be described as a linked worktree.
echo "--- Test 24e: ordinary subdirectory of the primary ---"

mkdir -p "$LW_MAIN/sub"
trace_run "$LW_MAIN/sub"
assert_not_contains "24e: emits no WORKTREE_UNLINKED token" "WORKTREE_UNLINKED" "$BARE_OUT"
assert_not_contains "24e: emits no NOT_INITIALIZED token" "NOT_INITIALIZED" "$BARE_OUT"
assert_not_contains "24e: does not call a subdirectory a worktree" \
    "linked git worktree" "$BARE_ERR"
rm -rf "$LW_TMP"

# --- Test 24f: NO_DATA_BRANCH survives from inside a worktree ---
# The ordering pin. Check 3b runs AFTER the branch probe precisely so this
# already-correct answer is not swallowed by the guard.
echo "--- Test 24f: worktree with no data branch reports NO_DATA_BRANCH ---"

TMPDIR_24F="$(setup_repo_with_remote)"
LW_MAIN="$TMPDIR_24F/local"
install_script "$LW_MAIN"
git -C "$LW_MAIN" worktree add -q -b aitask/tF "$LW_MAIN/aiwork/tF" HEAD
trace_run "$LW_MAIN/aiwork/tF"
assert_eq_trim "24f: reports NO_DATA_BRANCH" "NO_DATA_BRANCH" "$BARE_OUT"
assert_eq "24f: exits 0" "0" "$BARE_RC"
assert_not_contains "24f: never attempted a worktree add" "worktree add" "$TRACE"
rm -rf "$TMPDIR_24F"

# --- Test 24g: uninitialized primary is classified, not initialized into ---
# Before t1624 this case SUCCEEDED and planted the repo's only data checkout
# inside a throwaway task worktree, which disappears when the task lands.
echo "--- Test 24g: worktree whose primary has no .aitask-data ---"

lw_repo primary
git -C "$LW_MAIN" worktree remove --force .aitask-data
git -C "$LW_MAIN" worktree prune
trace_run "$LW_WT"
assert_eq_trim "24g: reports NOT_INITIALIZED" "NOT_INITIALIZED" "$BARE_OUT"
assert_eq "24g: exits 3" "3" "$BARE_RC"
assert_contains "24g: points at ait setup" "ait setup" "$BARE_ERR"
assert_not_contains "24g: never attempted a worktree add" "worktree add" "$TRACE"
assert_dir_not_exists "24g: no data checkout planted in the worktree" \
    "$LW_WT/.aitask-data"
rm -rf "$LW_TMP"

# --- Test 24h: tracer positive control ---
# Proves the "never attempted a worktree add" assertions above are capable of
# failing: on the path where Step 4 legitimately runs, the trace DOES record it.
echo "--- Test 24h: tracer records a worktree add when one happens ---"

TMPDIR_24H="$(setup_repo_with_remote)"
LW_MAIN="$TMPDIR_24H/local"
install_script "$LW_MAIN"
create_data_branch_setup "$LW_MAIN"
git -C "$LW_MAIN" worktree remove --force .aitask-data
git -C "$LW_MAIN" worktree prune
rm -f "$LW_MAIN/aitasks" "$LW_MAIN/aiplans"
trace_run "$LW_MAIN"
assert_eq_trim "24h: reports INITIALIZED" "INITIALIZED" "$BARE_OUT"
assert_contains "24h: the trace DID record the worktree add" "worktree add" "$TRACE"
rm -rf "$TMPDIR_24H"

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
