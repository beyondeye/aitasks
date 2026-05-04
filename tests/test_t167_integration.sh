#!/usr/bin/env bash
# test_t167_integration.sh - Integration test for framework file commit fix (t167)
# Tests the full install.sh + ait setup workflow using a real test directory.
# Run: bash tests/test_t167_integration.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEST_DIR="$(mktemp -d)/test_t167"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    # Trim leading/trailing whitespace (macOS wc -l pads with spaces)
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
    if echo "$actual" | grep -qi "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected')"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qi "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (output should NOT contain '$unexpected')"
    else
        PASS=$((PASS + 1))
    fi
}

echo "=== Integration Test: Framework File Commit Fix (t167) ==="
echo "Test directory: $TEST_DIR"
echo ""

# --- Setup: Create clean test directory ---
echo "--- Setting up clean test directory ---"
rm -rf "$TEST_DIR"
mkdir -p "$TEST_DIR"

(
    cd "$TEST_DIR"
    git init --quiet
    git config user.email "test@test.com"
    git config user.name "Test User"
    echo "# test project" > README.md
    git add README.md
    git commit -m "Initial commit" --quiet
)

# Create a local tarball from the current project for install.sh
TARBALL="/tmp/aitasks_test_t167.tar.gz"
(
    cd "$PROJECT_DIR"
    # Build tarball matching the release structure (install.sh is NOT in the tarball,
    # just like real releases — it's downloaded separately via curl)
    tar czf "$TARBALL" \
        .aitask-scripts/ \
        aitasks/metadata/labels.txt \
        aitasks/metadata/task_types.txt \
        aitasks/metadata/claude_settings.seed.json \
        aitasks/metadata/profiles/ \
        ait \
        packaging/ \
        2>/dev/null

    # Also include skills and seed directories if they exist
    if [[ -d ".claude/skills" ]]; then
        tar rzf "$TARBALL" .claude/skills/ 2>/dev/null || true
    fi
    if [[ -d "seed" ]]; then
        tar rzf "$TARBALL" seed/ 2>/dev/null || true
    fi
) 2>/dev/null

echo ""

# ============================================================
# Scenario A: fresh install — install.sh skips commit (no VERSION sentinel)
# ============================================================
# Per t637, install.sh's commit_installed_files() now bails out unless
# .aitask-scripts/VERSION is already git-tracked — projects that want
# framework files tracked must commit it once via 'ait setup' (or any
# subsequent install.sh run, which becomes an upgrade). This test verifies
# that bail-out: install.sh extracts but does NOT auto-commit on first install.
echo "=== Scenario A: install.sh skips auto-commit on fresh install (sentinel check) ==="

install_output=$(bash "$PROJECT_DIR/install.sh" --dir "$TEST_DIR" --local-tarball "$TARBALL" </dev/null 2>&1)

# install.sh emits a "skipping auto-commit of framework update" notice when
# the sentinel is missing. Verify that path was taken.
assert_contains "A1: install.sh announces sentinel-skip" "skipping auto-commit" "$install_output"

# Files should be EXTRACTED but NOT committed yet — only the initial commit exists.
commit_count=$(git -C "$TEST_DIR" log --oneline 2>/dev/null | wc -l | tr -d ' ')
assert_eq "A2: Only the initial commit exists post-install" "1" "$commit_count"

# But the framework files must exist on disk
TOTAL=$((TOTAL + 1))
if [[ -f "$TEST_DIR/ait" && -d "$TEST_DIR/.aitask-scripts" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: A3: Framework files extracted to disk"
fi

# Now simulate `ait setup`'s commit_framework_files() — that is what tracks them.
source "$TEST_DIR/.aitask-scripts/aitask_setup.sh" --source-only
set +euo pipefail
SCRIPT_DIR="$TEST_DIR/.aitask-scripts"
setup_output=$(commit_framework_files 2>&1 </dev/null)

tracked_files=$(git -C "$TEST_DIR" ls-files 2>/dev/null)
assert_contains "A4: After ait setup, .aitask-scripts/ is tracked" ".aitask-scripts/" "$tracked_files"
assert_contains "A5: After ait setup, ait is tracked" "ait" "$tracked_files"

setup_commit_msg=$(git -C "$TEST_DIR" log --format='%s' -1 2>/dev/null)
assert_eq "A6: ait setup commit message" "ait: Add aitask framework" "$setup_commit_msg"

echo ""

# ============================================================
# Scenario B: ait setup commits late-stage files
# ============================================================
echo "=== Scenario B: commit_framework_files catches late-stage files ==="

# Source the setup script to get access to functions
source "$TEST_DIR/.aitask-scripts/aitask_setup.sh" --source-only
set +euo pipefail
SCRIPT_DIR="$TEST_DIR/.aitask-scripts"

# Run setup_draft_directory (creates .gitignore entry + aitasks/new/)
setup_draft_directory </dev/null >/dev/null 2>&1

# Simulate review guides installation
mkdir -p "$TEST_DIR/aireviewguides"
echo "# test review guide" > "$TEST_DIR/aireviewguides/test_mode.md"
mkdir -p "$TEST_DIR/.agents/skills/aitask-pick"
echo "# test wrapper" > "$TEST_DIR/.agents/skills/aitask-pick/SKILL.md"
mkdir -p "$TEST_DIR/.codex"
echo "sandbox_mode = \"workspace-write\"" > "$TEST_DIR/.codex/config.toml"
mkdir -p "$TEST_DIR/.aitask-scripts/__pycache__"
echo "bytecode" > "$TEST_DIR/.aitask-scripts/__pycache__/test.cpython-314.pyc"

# Run commit_framework_files (this is the key function being tested)
output=$(commit_framework_files 2>&1 </dev/null)

# Verify late-stage files are now committed
untracked=$(cd "$TEST_DIR" && git ls-files --others --exclude-standard \
    .aitask-scripts/ aitasks/metadata/ ait .claude/skills/ .gitignore 2>/dev/null)
assert_contains "B1: Only pycache remains untracked after commit_framework_files" "__pycache__/test.cpython-314.pyc" "$untracked"

# Verify review guide was committed
tracked_files=$(git -C "$TEST_DIR" ls-files 2>/dev/null)
assert_contains "B2: Review guide file is tracked" "aireviewguides/test_mode.md" "$tracked_files"
assert_contains "B3: Codex wrapper file is tracked" ".agents/skills/aitask-pick/SKILL.md" "$tracked_files"
assert_contains "B4: Codex config file is tracked" ".codex/config.toml" "$tracked_files"
assert_not_contains "B5: Pycache file is not tracked" "__pycache__/test.cpython-314.pyc" "$tracked_files"

echo ""

# ============================================================
# Scenario C: Idempotency — running again does nothing
# ============================================================
echo "=== Scenario C: Idempotency check ==="

commit_count_before=$(git -C "$TEST_DIR" log --oneline 2>/dev/null | wc -l)
output=$(commit_framework_files 2>&1 </dev/null)
commit_count_after=$(git -C "$TEST_DIR" log --oneline 2>/dev/null | wc -l)

assert_eq "C1: No new commits on re-run" "$commit_count_before" "$commit_count_after"
assert_contains "C2: Says already committed" "already committed" "$output"

echo ""

# ============================================================
# Scenario D: re-run install.sh on an existing tracked install (upgrade path)
# ============================================================
# Once .aitask-scripts/VERSION is tracked (after `ait setup`), a subsequent
# install.sh run becomes an upgrade and DOES auto-commit. This tests that
# upgrade path.
echo "=== Scenario D: install.sh on tracked install commits the upgrade ==="

# After Scenario C, the fixture is already committed. Bump VERSION inside
# the tarball to force an upgrade-style content change, then re-run install.sh.
NEW_VERSION="99.0.0-t167test"
TARBALL_BUILD="$(mktemp -d)"
tar -xzf "$TARBALL" -C "$TARBALL_BUILD"
echo "$NEW_VERSION" > "$TARBALL_BUILD/.aitask-scripts/VERSION"
TARBALL_NEW="/tmp/aitasks_test_t167_new.tar.gz"
(cd "$TARBALL_BUILD" && tar czf "$TARBALL_NEW" .)

upgrade_output=$(bash "$PROJECT_DIR/install.sh" --force --dir "$TEST_DIR" --local-tarball "$TARBALL_NEW" </dev/null 2>&1)

assert_contains "D1: Upgrade run reports a commit" "committed to git" "$upgrade_output"

upgrade_commit_msg=$(git -C "$TEST_DIR" log --format='%s' -1 2>/dev/null)
assert_contains "D2: Upgrade commit message references new version" "v${NEW_VERSION}" "$upgrade_commit_msg"

rm -f "$TARBALL_NEW"
rm -rf "$TARBALL_BUILD"

echo ""

# ============================================================
# Scenario E: install.sh in non-git directory (no commit attempted)
# ============================================================
echo "=== Scenario E: install.sh in non-git directory ==="

NON_GIT_DIR="/tmp/test_t167_nogit"
rm -rf "$NON_GIT_DIR"
mkdir -p "$NON_GIT_DIR"

output=$(bash "$PROJECT_DIR/install.sh" --dir "$NON_GIT_DIR" --local-tarball "$TARBALL" </dev/null 2>&1)

# Should NOT contain any git commit messages
assert_not_contains "E1: No git commit in non-git dir" "committed to git" "$output"

# But files should still be installed
TOTAL=$((TOTAL + 1))
if [[ -f "$NON_GIT_DIR/ait" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: E2: ait file should exist in non-git directory"
fi

rm -rf "$NON_GIT_DIR"

echo ""

# --- Cleanup ---
rm -f "$TARBALL"

# --- Summary ---
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
