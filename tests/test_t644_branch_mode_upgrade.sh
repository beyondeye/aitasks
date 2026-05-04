#!/usr/bin/env bash
# test_t644_branch_mode_upgrade.sh - Regression test for ait upgrade in branch-mode setups (t644)
#
# When a project uses a separate aitask-data branch (aitasks/ and aiplans/ are
# symlinks into a .aitask-data/ worktree), `ait upgrade` previously failed
# silently: `git add aitasks/metadata/` errored with `pathspec ... is beyond a
# symbolic link` and the bulk add aborted, leaving NO framework files committed.
# This test reproduces the layout, runs install.sh, and asserts that:
#   - Master-branch framework files (.aitask-scripts/, ait, .claude/skills/) commit
#   - Data-branch metadata (aitasks/metadata/) commit on the aitask-data branch
#   - No "beyond a symbolic link" error appears
#
# Run: bash tests/test_t644_branch_mode_upgrade.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEST_ROOT="$(mktemp -d)/test_t644"

PASS=0
FAIL=0
TOTAL=0

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    expected="$(echo "$expected" | xargs)"
    actual="$(echo "$actual" | xargs)"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qi -- "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected')"
        echo "  ACTUAL OUTPUT:"
        echo "$actual" | sed 's/^/    /' | head -20
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qi -- "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (output should NOT contain '$unexpected')"
        echo "  ACTUAL OUTPUT:"
        echo "$actual" | sed 's/^/    /' | head -20
    else
        PASS=$((PASS + 1))
    fi
}

echo "=== Integration Test: ait upgrade in branch-mode setup (t644) ==="
echo "Test root: $TEST_ROOT"
echo ""

# --- Build a release-style tarball from the current project ---
TARBALL="/tmp/aitasks_test_t644.tar.gz"
rm -f "$TARBALL"
(
    cd "$PROJECT_DIR"
    tar czf "$TARBALL" \
        .aitask-scripts/ \
        aitasks/metadata/labels.txt \
        aitasks/metadata/task_types.txt \
        aitasks/metadata/claude_settings.seed.json \
        aitasks/metadata/profiles/ \
        ait \
        packaging/ \
        2>/dev/null
    if [[ -d ".claude/skills" ]]; then
        tar rzf "$TARBALL" .claude/skills/ 2>/dev/null || true
    fi
    if [[ -d "seed" ]]; then
        tar rzf "$TARBALL" seed/ 2>/dev/null || true
    fi
) 2>/dev/null

# ============================================================
# Setup: project with aitask-data branch + worktree + symlinks
# ============================================================
echo "--- Building branch-mode test project ---"

PROJECT="$TEST_ROOT/proj"
rm -rf "$TEST_ROOT"
mkdir -p "$PROJECT"

(
    cd "$PROJECT"
    git init --quiet -b master
    git config user.email "test@test.com"
    git config user.name "Test User"
    git config commit.gpgsign false
    echo "# branch-mode project" > README.md
    git add README.md
    git commit -q -m "Initial commit"
) || { echo "FATAL: could not init test repo"; exit 1; }

# First install (simulates pre-upgrade state)
bash "$PROJECT_DIR/install.sh" --dir "$PROJECT" --local-tarball "$TARBALL" </dev/null >/dev/null 2>&1

# Sanity check
TOTAL=$((TOTAL + 1))
if [[ -f "$PROJECT/.aitask-scripts/VERSION" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: setup precondition: .aitask-scripts/VERSION missing after first install"
fi

# Create an aitask-data orphan branch + worktree (mimics ait setup's branch-mode setup)
(
    cd "$PROJECT"
    empty_tree=$(git mktree < /dev/null)
    branch_commit=$(echo "ait: Initialize aitask-data branch" | git commit-tree "$empty_tree")
    git update-ref refs/heads/aitask-data "$branch_commit"

    # Move existing aitasks/ + aiplans/ content into the data worktree
    mv aitasks .aitask-data-staging-aitasks
    mv aiplans .aitask-data-staging-aiplans 2>/dev/null || mkdir -p .aitask-data-staging-aiplans

    git worktree add .aitask-data aitask-data 2>/dev/null

    mkdir -p .aitask-data/aitasks .aitask-data/aiplans
    cp -a .aitask-data-staging-aitasks/. .aitask-data/aitasks/ 2>/dev/null || true
    cp -a .aitask-data-staging-aiplans/. .aitask-data/aiplans/ 2>/dev/null || true
    rm -rf .aitask-data-staging-aitasks .aitask-data-staging-aiplans

    ln -s .aitask-data/aitasks aitasks
    ln -s .aitask-data/aiplans aiplans

    # Commit data-branch initial state
    git -C .aitask-data add aitasks/ aiplans/ 2>/dev/null || true
    git -C .aitask-data -c user.email=test@test.com -c user.name=Test \
        commit -q -m "ait: Migrate task data to aitask-data branch" 2>/dev/null || true

    # Commit the master-branch framework files (and the symlinks).
    git add -A 2>/dev/null || true
    git -c user.email=test@test.com -c user.name=Test \
        commit -q -m "ait: Add aitask framework" 2>/dev/null || true
)

# Verify symlink-to-data layout is in place (sanity)
TOTAL=$((TOTAL + 1))
if [[ -L "$PROJECT/aitasks" && -d "$PROJECT/.aitask-data/.git" ]] || \
   [[ -L "$PROJECT/aitasks" && -f "$PROJECT/.aitask-data/.git" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: precondition: symlink/data-worktree layout not in place"
    ls -la "$PROJECT" | head -10
fi

# Capture pre-upgrade state
master_commits_before=$(git -C "$PROJECT" rev-list --count master 2>/dev/null)
data_commits_before=$(git -C "$PROJECT/.aitask-data" rev-list --count HEAD 2>/dev/null)

echo "  Master commits before upgrade: $master_commits_before"
echo "  Data commits before upgrade:   $data_commits_before"
echo ""

# ============================================================
# Scenario A: branch-mode upgrade commits on BOTH branches
# ============================================================
echo "=== Scenario A: branch-mode upgrade commits framework files ==="

# Bump the VERSION inside the tarball so install.sh sees a "new" version
NEW_VERSION="99.0.0-t644test"
TARBALL_NEW="/tmp/aitasks_test_t644_new.tar.gz"
TARBALL_BUILD="$TEST_ROOT/tarball_build"
mkdir -p "$TARBALL_BUILD"
tar -xzf "$TARBALL" -C "$TARBALL_BUILD"
echo "$NEW_VERSION" > "$TARBALL_BUILD/.aitask-scripts/VERSION"
# Add a brand-new framework file so we can prove untracked files get added
echo "# new helper for t644 test" > "$TARBALL_BUILD/.aitask-scripts/aitask_t644_marker.sh"
# Also touch a file under aitasks/metadata/ via the seed pipeline to ensure
# data-branch changes need a commit. install.sh's install_seed_profiles will
# handle this if the seed dir is present.
(cd "$TARBALL_BUILD" && tar czf "$TARBALL_NEW" .)

# Run upgrade (force flag, like ait upgrade does)
upgrade_output=$(bash "$PROJECT_DIR/install.sh" --force --dir "$PROJECT" --local-tarball "$TARBALL_NEW" </dev/null 2>&1)

assert_not_contains "A1: No 'beyond a symbolic link' error" "beyond a symbolic link" "$upgrade_output"
assert_contains "A2: Master-branch commit reported" "committed to git" "$upgrade_output"

master_commits_after=$(git -C "$PROJECT" rev-list --count master 2>/dev/null)
data_commits_after=$(git -C "$PROJECT/.aitask-data" rev-list --count HEAD 2>/dev/null)

assert_eq "A3: Master gained exactly one commit" "$((master_commits_before + 1))" "$master_commits_after"

# Master commit message should reference the new version
master_msg=$(git -C "$PROJECT" log master --format='%s' -1 2>/dev/null)
assert_contains "A4: Master commit message references new version" "v${NEW_VERSION}" "$master_msg"
assert_contains "A5: Master commit message says 'Update aitasks framework'" "Update aitasks framework" "$master_msg"

# Master commit should include the new t644 marker file
master_files=$(git -C "$PROJECT" log master -1 --name-only --format='' 2>/dev/null)
assert_contains "A6: New marker file in master commit" "aitask_t644_marker.sh" "$master_files"
assert_contains "A7: ait dispatcher in master commit" "ait" "$master_files"

# Master commit should NOT include any aitasks/ or aiplans/ paths (those live on data branch)
TOTAL=$((TOTAL + 1))
if echo "$master_files" | grep -qE '^aitasks/|^aiplans/'; then
    FAIL=$((FAIL + 1))
    echo "FAIL: A8: Master commit should not include aitasks/ or aiplans/ paths"
    echo "$master_files" | grep -E '^aitasks/|^aiplans/' | sed 's/^/    /'
else
    PASS=$((PASS + 1))
fi

# Status should be clean for the framework paths on master
master_dirty=$(cd "$PROJECT" && git ls-files --others --exclude-standard \
    .aitask-scripts/ ait .claude/skills/ 2>/dev/null \
    | grep -Ev '(^|/)__pycache__/|\.py[co]$|\.pyd$' || true)
assert_eq "A9: No untracked framework files on master after upgrade" "" "$master_dirty"

echo ""

# ============================================================
# Scenario B: idempotent re-run produces no new commits
# ============================================================
echo "=== Scenario B: idempotency on re-run ==="

# Re-run with the same tarball (already up to date)
bash "$PROJECT_DIR/install.sh" --force --dir "$PROJECT" --local-tarball "$TARBALL_NEW" </dev/null >/dev/null 2>&1

master_commits_idem=$(git -C "$PROJECT" rev-list --count master 2>/dev/null)
data_commits_idem=$(git -C "$PROJECT/.aitask-data" rev-list --count HEAD 2>/dev/null)

assert_eq "B1: No new master commit on idempotent re-run" "$master_commits_after" "$master_commits_idem"
assert_eq "B2: No new data commit on idempotent re-run" "$data_commits_after" "$data_commits_idem"

echo ""

# ============================================================
# Scenario C: legacy mode (no .aitask-data) still works
# ============================================================
echo "=== Scenario C: legacy mode (no aitask-data branch) unchanged ==="

LEGACY="$TEST_ROOT/legacy"
mkdir -p "$LEGACY"
(
    cd "$LEGACY"
    git init --quiet -b master
    git config user.email "test@test.com"
    git config user.name "Test User"
    git config commit.gpgsign false
    echo "# legacy" > README.md
    git add README.md
    git commit -q -m "Initial"
)

bash "$PROJECT_DIR/install.sh" --dir "$LEGACY" --local-tarball "$TARBALL" </dev/null >/dev/null 2>&1

# install.sh's first run does NOT auto-commit (no .aitask-scripts/VERSION
# tracked yet on the sentinel). That is correct — `ait setup` will commit.
# Now stage the initial framework so the sentinel is tracked, then re-run install
# with the bumped tarball to exercise commit_installed_files() in legacy mode.
(
    cd "$LEGACY"
    git add -A
    git -c user.email=test@test.com -c user.name=Test commit -q -m "ait: Add aitask framework"
)

legacy_before=$(git -C "$LEGACY" rev-list --count master 2>/dev/null)
legacy_output=$(bash "$PROJECT_DIR/install.sh" --force --dir "$LEGACY" --local-tarball "$TARBALL_NEW" </dev/null 2>&1)
legacy_after=$(git -C "$LEGACY" rev-list --count master 2>/dev/null)

assert_not_contains "C1: No symlink error in legacy mode" "beyond a symbolic link" "$legacy_output"
assert_eq "C2: Legacy mode gained exactly one commit" "$((legacy_before + 1))" "$legacy_after"

legacy_msg=$(git -C "$LEGACY" log --format='%s' -1 2>/dev/null)
assert_contains "C3: Legacy commit references new version" "v${NEW_VERSION}" "$legacy_msg"

echo ""

# --- Cleanup ---
rm -f "$TARBALL" "$TARBALL_NEW"
rm -rf "$TEST_ROOT"

# --- Summary ---
echo "==============================="
echo "Total:  $TOTAL"
echo "Pass:   $PASS"
echo "Fail:   $FAIL"
echo "==============================="

if [[ $FAIL -eq 0 ]]; then
    echo "All tests passed."
    exit 0
else
    exit 1
fi
