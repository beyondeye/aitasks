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
        aiscripts/ \
        aitasks/metadata/labels.txt \
        aitasks/metadata/task_types.txt \
        aitasks/metadata/claude_settings.seed.json \
        aitasks/metadata/profiles/ \
        ait \
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
# Scenario A: install.sh commits files automatically
# ============================================================
echo "=== Scenario A: install.sh auto-commits framework files ==="

bash "$PROJECT_DIR/install.sh" --dir "$TEST_DIR" --local-tarball "$TARBALL" </dev/null 2>&1 | tail -5

# Verify framework files were committed
untracked=$(cd "$TEST_DIR" && git ls-files --others --exclude-standard \
    aiscripts/ aitasks/metadata/ ait .claude/skills/ 2>/dev/null)
assert_eq "A1: No untracked framework files after install.sh" "" "$untracked"

# Verify commit message
commit_msg=$(git -C "$TEST_DIR" log --format='%s' -1 2>/dev/null)
assert_eq "A2: install.sh commit message" "ait: Add aitask framework" "$commit_msg"

# Verify key files are tracked
tracked_files=$(git -C "$TEST_DIR" ls-files 2>/dev/null)
assert_contains "A3: aiscripts/ is tracked" "aiscripts/" "$tracked_files"
assert_contains "A4: ait is tracked" "ait" "$tracked_files"

echo ""

# ============================================================
# Scenario B: ait setup commits late-stage files
# ============================================================
echo "=== Scenario B: commit_framework_files catches late-stage files ==="

# Source the setup script to get access to functions
source "$TEST_DIR/aiscripts/aitask_setup.sh" --source-only
set +euo pipefail
SCRIPT_DIR="$TEST_DIR/aiscripts"

# Run setup_draft_directory (creates .gitignore entry + aitasks/new/)
setup_draft_directory </dev/null >/dev/null 2>&1

# Simulate review guides installation
mkdir -p "$TEST_DIR/aireviewguides"
echo "# test review guide" > "$TEST_DIR/aireviewguides/test_mode.md"

# Run commit_framework_files (this is the key function being tested)
output=$(commit_framework_files 2>&1 </dev/null)

# Verify late-stage files are now committed
untracked=$(cd "$TEST_DIR" && git ls-files --others --exclude-standard \
    aiscripts/ aitasks/metadata/ ait .claude/skills/ .gitignore 2>/dev/null)
assert_eq "B1: No untracked framework files after commit_framework_files" "" "$untracked"

# Verify review guide was committed
tracked_files=$(git -C "$TEST_DIR" ls-files 2>/dev/null)
assert_contains "B2: Review guide file is tracked" "aireviewguides/test_mode.md" "$tracked_files"

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
# Scenario D: Fresh install without existing commit
# ============================================================
echo "=== Scenario D: Fresh install into git repo (no prior framework commit) ==="

# Reset: remove framework files and recommit
rm -rf "$TEST_DIR"
mkdir -p "$TEST_DIR"
(
    cd "$TEST_DIR"
    git init --quiet
    git config user.email "test@test.com"
    git config user.name "Test User"
    echo "# fresh project" > README.md
    git add README.md
    git commit -m "Initial commit" --quiet
)

# Run install.sh again
bash "$PROJECT_DIR/install.sh" --dir "$TEST_DIR" --local-tarball "$TARBALL" </dev/null >/dev/null 2>&1

# Source and run commit_framework_files (simulating ait setup)
source "$TEST_DIR/aiscripts/aitask_setup.sh" --source-only
set +euo pipefail
SCRIPT_DIR="$TEST_DIR/aiscripts"

# Since install.sh already committed, commit_framework_files should find nothing
output=$(commit_framework_files 2>&1 </dev/null)
assert_contains "D1: Says already committed after install.sh" "already committed" "$output"

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
