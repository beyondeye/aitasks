#!/usr/bin/env bash
set -uo pipefail

# Test install.sh create_data_dirs() / ensure_data_root() — the dangling
# data-symlink guard (t1193).
#
# Regression context: create_data_dirs() ran five unguarded `mkdir -p` calls on
# aitasks/ and aiplans/. `mkdir -p` FAILS ("File exists") when the leading path
# component is a dangling symlink, and install.sh runs under `set -euo pipefail`
# — so a tarball that captured this repo's own gitignored
# `aitasks -> .aitask-data/aitasks` symlinks aborted the entire install with an
# opaque diagnostic. Every later install step writes through these roots, so the
# guard has to repair the root, not warn-and-skip.
#
# The guard must NOT unlink a legitimate branch-mode symlink whose worktree is
# merely missing — doing so would silently redirect framework metadata into a
# real, gitignored aitasks/ dir that is not the data branch. Tests 5-9 pin every
# non-destructive branch; test 3 is the negative control proving test 2 passes
# because of the guard rather than because `mkdir -p` was always fine.

PASS=0
FAIL=0
# shellcheck disable=SC2034  # TOTAL is mutated by the sourced asserts.sh helpers.
TOTAL=0

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

TESTROOT="$(mktemp -d)"
trap 'rm -rf "$TESTROOT"' EXIT

# assert_symlink is single-use here and stays inline (see asserts.sh header).
assert_symlink() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -L "$path" ]]; then
        echo "  PASS: $desc"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc"
        echo "    expected '$path' to still be a symlink"
        FAIL=$((FAIL + 1))
    fi
}

# Run create_data_dirs against a fixture. Isolated in a subshell so a `die`
# (which exits 1) cannot take the test run down. Echoes nothing; sets $rc.
run_guard() {
    local dir="$1"
    (
        # shellcheck disable=SC2030,SC2034  # read by the sourced create_data_dirs.
        INSTALL_DIR="$dir"
        create_data_dirs
    ) > /dev/null 2>&1
    rc=$?
}

# A fixture whose aitasks/ is a canonical-but-dangling data-branch symlink.
make_dangling() {
    local name="$1" root="$2"
    local dir="$TESTROOT/$name"
    mkdir -p "$dir"
    ln -s ".aitask-data/$root" "$dir/$root"   # target deliberately absent
    echo "$dir"
}

# A git repo with a real .aitask-data worktree on an orphan aitask-data branch —
# the production branch-mode layout.
make_branch_mode() {
    local name="$1"
    local dir="$TESTROOT/$name"
    mkdir -p "$dir"
    (
        cd "$dir" || exit 1
        git init --quiet -b main
        git config user.email "test@test.com"
        git config user.name "Test User"
        git config commit.gpgsign false
        echo "# test" > README.md
        git add README.md
        git commit --quiet -m "init"
        local empty_tree commit
        empty_tree="$(git mktree < /dev/null)"
        commit="$(echo "init data" | git commit-tree "$empty_tree")"
        git update-ref refs/heads/aitask-data "$commit"
        git worktree add --quiet .aitask-data aitask-data
        mkdir -p .aitask-data/aitasks .aitask-data/aiplans
        ln -s .aitask-data/aitasks aitasks
        ln -s .aitask-data/aiplans aiplans
    ) > /dev/null 2>&1
    echo "$dir"
}

# Unit under test — load install.sh's functions only (the --source-only guard
# returns before main()).
# shellcheck source=../install.sh
source "$PROJECT_DIR/install.sh" --source-only
# install.sh sets `-euo pipefail` at file scope, which leaks into this shell when
# sourced. The scenarios below deliberately provoke failures and inspect $?.
set +euo pipefail

echo "=== create_data_dirs() dangling-symlink guard Tests ==="
echo ""

# --- Test 1: baseline ---
echo "--- Test 1: empty dir creates every data directory ---"
DIR1="$TESTROOT/t1"
mkdir -p "$DIR1"
run_guard "$DIR1"
assert_exit_zero_rc "T1: exits 0 on a clean dir" "$rc"
assert_dir_exists "T1: aitasks/metadata/profiles created" "$DIR1/aitasks/metadata/profiles"
assert_dir_exists "T1: aitasks/archived created" "$DIR1/aitasks/archived"
assert_dir_exists "T1: aiplans/archived created" "$DIR1/aiplans/archived"
assert_dir_exists "T1: aireviewguides created" "$DIR1/aireviewguides"

echo ""

# --- Test 2: the reported failure — dangling aitasks, no data branch ---
echo "--- Test 2: dangling aitasks/ with no data branch is repaired ---"
DIR2="$(make_dangling t2 aitasks)"
# This fixture is deliberately NOT a git repo — install.sh supports non-git
# install dirs, so the branch-mode probes must stay silent there.
out2="$(
    # shellcheck disable=SC2030,SC2034  # read by the sourced create_data_dirs.
    INSTALL_DIR="$DIR2"
    create_data_dirs 2>&1
)"
rc=$?
assert_exit_zero_rc "T2: exits 0 instead of aborting the install" "$rc"
assert_not_contains "T2: no git noise leaks from the branch-mode probes" \
    "not a git repository" "$out2"
assert_dir_exists "T2: aitasks/metadata/profiles created" "$DIR2/aitasks/metadata/profiles"
assert_dir_exists "T2: aitasks/archived created" "$DIR2/aitasks/archived"
TOTAL=$((TOTAL + 1))
if [[ ! -L "$DIR2/aitasks" && -d "$DIR2/aitasks" ]]; then
    echo "  PASS: T2: dangling symlink replaced by a real directory"
    PASS=$((PASS + 1))
else
    echo "  FAIL: T2: aitasks/ is not a real directory after the repair"
    FAIL=$((FAIL + 1))
fi

echo ""

# --- Test 3: negative control ---
# Without the guard, a bare `mkdir -p` through the same dangling symlink fails.
# This is what makes T2 attributable to ensure_data_root rather than to
# `mkdir -p` having been harmless all along.
echo "--- Test 3: negative control — bare mkdir -p through the link fails ---"
DIR3="$(make_dangling t3 aitasks)"
mkdir -p "$DIR3/aitasks/metadata" > /dev/null 2>&1
rc3=$?
assert_exit_nonzero_rc "T3: unguarded mkdir -p exits non-zero (the original bug)" "$rc3"

echo ""

# --- Test 4: the second data root ---
echo "--- Test 4: dangling aiplans/ with no data branch is repaired ---"
DIR4="$(make_dangling t4 aiplans)"
run_guard "$DIR4"
assert_exit_zero_rc "T4: exits 0" "$rc"
assert_dir_exists "T4: aiplans/archived created" "$DIR4/aiplans/archived"
TOTAL=$((TOTAL + 1))
if [[ ! -L "$DIR4/aiplans" && -d "$DIR4/aiplans" ]]; then
    echo "  PASS: T4: dangling symlink replaced by a real directory"
    PASS=$((PASS + 1))
else
    echo "  FAIL: T4: aiplans/ is not a real directory after the repair"
    FAIL=$((FAIL + 1))
fi

echo ""

# --- Test 5: live worktree, unmaterialized target ---
# The symlink is correct; only its target subdir is missing. The guard must
# materialize the target and leave the branch-mode layout intact.
echo "--- Test 5: live worktree — target materialized, symlink preserved ---"
DIR5="$(make_branch_mode t5)"
rm -rf "$DIR5/.aitask-data/aitasks"
run_guard "$DIR5"
assert_exit_zero_rc "T5: exits 0" "$rc"
assert_symlink "T5: aitasks/ is still a symlink (branch mode intact)" "$DIR5/aitasks"
assert_dir_exists "T5: target materialized on the data branch" \
    "$DIR5/.aitask-data/aitasks/metadata/profiles"

echo ""

# --- Test 6: healthy symlink is never touched ---
echo "--- Test 6: healthy data-branch symlinks are left alone ---"
DIR6="$(make_branch_mode t6)"
run_guard "$DIR6"
assert_exit_zero_rc "T6: exits 0" "$rc"
assert_symlink "T6: aitasks/ still a symlink" "$DIR6/aitasks"
assert_symlink "T6: aiplans/ still a symlink" "$DIR6/aiplans"
assert_dir_exists "T6: dirs created through the link onto the data branch" \
    "$DIR6/.aitask-data/aitasks/metadata/profiles"
assert_dir_exists "T6: aiplans/archived created through the link" \
    "$DIR6/.aitask-data/aiplans/archived"

echo ""

# --- Test 7: branch-mode evidence, worktree gone → fail clearly ---
# The dangerous case: a real branch-mode project whose worktree was deleted.
# Unlinking here would redirect framework metadata off the data branch.
echo "--- Test 7: registered worktree + branch ref, dir gone → hard error ---"
DIR7="$(make_branch_mode t7)"
rm -rf "$DIR7/.aitask-data"   # registration and refs/heads/aitask-data remain
run_guard "$DIR7"
assert_exit_nonzero_rc "T7: refuses to proceed" "$rc"
assert_symlink "T7: the data-branch symlink is preserved" "$DIR7/aitasks"
TOTAL=$((TOTAL + 1))
if [[ -L "$DIR7/aitasks" && ! -e "$DIR7/aitasks" ]]; then
    echo "  PASS: T7: no real aitasks/ directory was created in its place"
    PASS=$((PASS + 1))
else
    echo "  FAIL: T7: aitasks/ was materialized despite the missing worktree"
    FAIL=$((FAIL + 1))
fi

echo ""

# --- Test 8: stale .git marker → not live, but still evidence ---
# `-f .aitask-data/.git` alone is not proof of a worktree: rev-parse must also
# succeed. A stale/copied marker lands in the hard-error branch, never in the
# materialize branch and never in the unlink branch.
echo "--- Test 8: stale .aitask-data/.git marker → hard error, no unlink ---"
DIR8="$(make_dangling t8 aitasks)"
mkdir -p "$DIR8/.aitask-data"
echo "gitdir: /nonexistent/worktrees/aitask-data" > "$DIR8/.aitask-data/.git"
run_guard "$DIR8"
assert_exit_nonzero_rc "T8: refuses to proceed on a stale marker" "$rc"
assert_symlink "T8: the symlink is preserved" "$DIR8/aitasks"

echo ""

# --- Test 9: unrecognized symlink target ---
# Only the exact form setup_data_branch() writes is recognized. An absolute,
# ../-bearing, or custom target must never reach an mkdir or an rm.
echo "--- Test 9: unrecognized dangling target → hard error, nothing created ---"
DIR9="$TESTROOT/t9"
mkdir -p "$DIR9"
ln -s "../elsewhere/aitasks" "$DIR9/aitasks"
run_guard "$DIR9"
assert_exit_nonzero_rc "T9: refuses to touch an unrecognized link" "$rc"
assert_symlink "T9: the symlink is preserved" "$DIR9/aitasks"
assert_dir_not_exists "T9: nothing created outside the install dir" \
    "$TESTROOT/elsewhere"

echo ""

# --- Test 9b: unwritable install dir → the repair reports, never aborts bare ---
# Every failure path in ensure_data_root() carries a diagnostic; the leftover
# repair's `rm -f` must not be the one exception that lets `set -e` abort with a
# bare `rm:` line. Skipped as root, where the permission bits do not bite.
echo "--- Test 9b: unwritable dir → repair fails with a diagnostic ---"
if [[ "$(id -u)" -eq 0 ]]; then
    echo "  SKIP: running as root — permission bits do not apply"
else
    DIR9B="$(make_dangling t9b aitasks)"
    chmod a-w "$DIR9B"
    out9b="$(
        # shellcheck disable=SC2030,SC2034  # read by the sourced create_data_dirs.
        INSTALL_DIR="$DIR9B"
        create_data_dirs 2>&1
    )"
    rc9b=$?
    chmod u+w "$DIR9B"   # restore so the EXIT trap can clean up
    assert_exit_nonzero_rc "T9b: refuses to proceed" "$rc9b"
    assert_contains "T9b: fails with the guard's diagnostic, not a bare rm error" \
        "Cannot replace dangling symlink" "$out9b"
    assert_symlink "T9b: the symlink is untouched" "$DIR9B/aitasks"
fi

echo ""

# --- Test 10: idempotence ---
echo "--- Test 10: re-running on a repaired dir is a no-op ---"
run_guard "$DIR2"
assert_exit_zero_rc "T10: second run exits 0" "$rc"
assert_dir_exists "T10: dirs still present" "$DIR2/aitasks/metadata/profiles"

echo ""

# --- Test 11: end-to-end through the real install.sh entry point ---
# The actual reported repro: a hand-built tarball that captured the repo's own
# gitignored aitasks/aiplans symlinks, extracted into a fresh install dir.
echo "--- Test 11: install.sh --local-tarball with dangling symlinks in the tarball ---"
STAGING="$TESTROOT/staging"
mkdir -p "$STAGING"
cp -r "$PROJECT_DIR/.aitask-scripts" "$STAGING/"
cp "$PROJECT_DIR/ait" "$STAGING/"
[[ -d "$PROJECT_DIR/seed" ]] && cp -r "$PROJECT_DIR/seed" "$STAGING/"
[[ -d "$PROJECT_DIR/packaging" ]] && cp -r "$PROJECT_DIR/packaging" "$STAGING/"
# The defect carrier: dangling data symlinks, exactly as the repo has them.
ln -s .aitask-data/aitasks "$STAGING/aitasks"
ln -s .aitask-data/aiplans "$STAGING/aiplans"

TARBALL="$TESTROOT/aitasks_dangling.tar.gz"
(cd "$STAGING" && tar czf "$TARBALL" .) > /dev/null 2>&1

SCRATCH="$TESTROOT/install_target"
mkdir -p "$SCRATCH"
(
    cd "$SCRATCH" || exit 1
    git init --quiet
    git config user.email "test@test.com"
    git config user.name "Test User"
    git config commit.gpgsign false
    echo "# project" > README.md
    git add README.md
    git commit --quiet -m "init"
) > /dev/null 2>&1

install_out="$(bash "$PROJECT_DIR/install.sh" --dir "$SCRATCH" \
    --local-tarball "$TARBALL" < /dev/null 2>&1)"
rc11=$?
assert_exit_zero_rc "T11: install.sh completes instead of aborting" "$rc11"
assert_not_contains "T11: no 'cannot create directory' abort" \
    "cannot create directory" "$install_out"
assert_dir_exists "T11: data dirs exist after install" \
    "$SCRATCH/aitasks/metadata/profiles"
# Attributability: prove the install survived because the guard repaired the
# roots, not because the tarball's symlinks failed to land.
assert_contains "T11: the guard repaired aitasks/ during the real install" \
    "Replacing dangling symlink $SCRATCH/aitasks" "$install_out"
assert_contains "T11: the guard repaired aiplans/ during the real install" \
    "Replacing dangling symlink $SCRATCH/aiplans" "$install_out"

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed"
echo "========================================="
[[ $FAIL -eq 0 ]]
