#!/usr/bin/env bash
# test_contribute.sh - Automated tests for aitask_contribute.sh
# Run: bash tests/test_contribute.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
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
    if echo "$actual" | grep -F -q -- "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected')"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -F -q -- "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (output should NOT contain '$unexpected')"
    else
        PASS=$((PASS + 1))
    fi
}

assert_exit_zero() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (command exited non-zero)"
    fi
}

assert_exit_nonzero() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected non-zero exit, got 0)"
    else
        PASS=$((PASS + 1))
    fi
}

# --- Setup ---

TMPDIR_TEST=""

setup() {
    TMPDIR_TEST="$(mktemp -d)"
    local upstream_dir="$TMPDIR_TEST/upstream"
    local local_dir="$TMPDIR_TEST/local"

    # Create upstream baseline files
    mkdir -p "$upstream_dir/.aitask-scripts/lib"
    echo '#!/usr/bin/env bash' > "$upstream_dir/.aitask-scripts/original_script.sh"
    echo 'echo "original version"' >> "$upstream_dir/.aitask-scripts/original_script.sh"
    echo 'echo "line 2"' >> "$upstream_dir/.aitask-scripts/original_script.sh"

    # Create a large upstream file (for large diff test)
    {
        echo '#!/usr/bin/env bash'
        for i in $(seq 1 100); do
            echo "echo \"original line $i\""
        done
    } > "$upstream_dir/.aitask-scripts/large_script.sh"

    # Create local project with modifications
    mkdir -p "$local_dir/.aitask-scripts/lib"
    mkdir -p "$local_dir/.claude/skills"
    mkdir -p "$local_dir/aitasks/metadata"

    # Copy the script under test and its dependencies
    cp "$PROJECT_DIR/.aitask-scripts/aitask_contribute.sh" "$local_dir/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" "$local_dir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" "$local_dir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/repo_fetch.sh" "$local_dir/.aitask-scripts/lib/"
    chmod +x "$local_dir/.aitask-scripts/aitask_contribute.sh"

    # Create VERSION file
    echo "0.9.0" > "$local_dir/.aitask-scripts/VERSION"

    # Create a modified script (differs from upstream)
    echo '#!/usr/bin/env bash' > "$local_dir/.aitask-scripts/original_script.sh"
    echo 'echo "modified version"' >> "$local_dir/.aitask-scripts/original_script.sh"
    echo 'echo "line 2"' >> "$local_dir/.aitask-scripts/original_script.sh"
    echo 'echo "new line 3"' >> "$local_dir/.aitask-scripts/original_script.sh"

    # Create a large modified file (>50 line diff)
    {
        echo '#!/usr/bin/env bash'
        for i in $(seq 1 100); do
            echo "echo \"modified line $i\""
        done
        for i in $(seq 101 160); do
            echo "echo \"new line $i\""
        done
    } > "$local_dir/.aitask-scripts/large_script.sh"

    # Init git repo with beyondeye/aitasks remote for clone mode detection
    # Set up main branch with upstream files, working branch with modifications
    (
        cd "$local_dir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"
        git remote add origin "https://github.com/beyondeye/aitasks.git"

        # Copy upstream files as the main branch baseline
        cp "$upstream_dir/.aitask-scripts/original_script.sh" ".aitask-scripts/original_script.sh"
        cp "$upstream_dir/.aitask-scripts/large_script.sh" ".aitask-scripts/large_script.sh"

        git add -A
        git commit -m "Initial upstream baseline" --quiet
        git branch -M main

        # Create working branch with modifications
        git checkout -b working --quiet

        # Modify original_script.sh
        {
            echo '#!/usr/bin/env bash'
            echo 'echo "modified version"'
            echo 'echo "line 2"'
            echo 'echo "new line 3"'
        } > ".aitask-scripts/original_script.sh"

        # Modify large_script.sh with >50 line diff
        {
            echo '#!/usr/bin/env bash'
            for i in $(seq 1 100); do
                echo "echo \"modified line $i\""
            done
            for i in $(seq 101 160); do
                echo "echo \"new line $i\""
            done
        } > ".aitask-scripts/large_script.sh"

        git add -A
        git commit -m "Local modifications" --quiet
    )

    export AITASK_CONTRIBUTE_UPSTREAM_DIR="$upstream_dir"
    export LOCAL_DIR="$local_dir"
}

cleanup() {
    if [[ -n "$TMPDIR_TEST" && -d "$TMPDIR_TEST" ]]; then
        rm -rf "$TMPDIR_TEST"
    fi
    unset AITASK_CONTRIBUTE_UPSTREAM_DIR
    unset LOCAL_DIR
}

trap cleanup EXIT

# Disable strict mode for test error handling
set +e

setup

echo "=== aitask_contribute.sh Tests ==="
echo ""

# --- Test 1: --help output ---
echo "--- Test 1: --help output ---"
output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh --help 2>&1)
exit_code=$?
assert_eq "help exits 0" "0" "$exit_code"
assert_contains "help shows usage" "Usage:" "$output"
assert_contains "help shows --area" "--area" "$output"
assert_contains "help shows --dry-run" "--dry-run" "$output"

# --- Test 2: --list-areas output ---
echo "--- Test 2: --list-areas output ---"
output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh --list-areas 2>&1)
exit_code=$?
assert_eq "list-areas exits 0" "0" "$exit_code"
assert_contains "list-areas has MODE" "MODE:" "$output"
assert_contains "list-areas has scripts" "AREA|scripts|" "$output"
assert_contains "list-areas has claude-skills" "AREA|claude-skills|" "$output"
assert_contains "list-areas has gemini" "AREA|gemini|" "$output"
assert_contains "list-areas has codex" "AREA|codex|" "$output"
assert_contains "list-areas has opencode" "AREA|opencode|" "$output"

# --- Test 3: Mode detection ---
echo "--- Test 3: Mode detection ---"
output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh --list-areas 2>&1)
assert_contains "clone mode detected" "MODE:clone" "$output"
# Website should be available in clone mode
assert_contains "website available in clone mode" "AREA|website|" "$output"

# --- Test 4: Argument parsing ---
echo "--- Test 4: Argument parsing ---"
# Dry run with proper args should succeed
output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh \
    --dry-run --area scripts \
    --files ".aitask-scripts/original_script.sh" \
    --title "Test contribution" \
    --motivation "Testing" \
    --scope enhancement \
    --merge-approach "clean merge" 2>&1)
exit_code=$?
assert_eq "dry-run with valid args exits 0" "0" "$exit_code"

# --- Test 5: Missing --files error ---
echo "--- Test 5: Missing --files error ---"
assert_exit_nonzero "missing --files" \
    bash -c "cd '$LOCAL_DIR' && ./.aitask-scripts/aitask_contribute.sh --dry-run --area scripts --title 'test'"

# --- Test 6: Missing --title error ---
echo "--- Test 6: Missing --title error ---"
assert_exit_nonzero "missing --title" \
    bash -c "cd '$LOCAL_DIR' && ./.aitask-scripts/aitask_contribute.sh --dry-run --area scripts --files 'foo.sh'"

# --- Test 7: --list-changes output ---
echo "--- Test 7: --list-changes output ---"
output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh --list-changes --area scripts 2>&1)
exit_code=$?
assert_eq "list-changes exits 0" "0" "$exit_code"
assert_contains "list-changes shows modified file" "original_script.sh" "$output"
assert_contains "list-changes shows large modified file" "large_script.sh" "$output"

# --- Test 8: Dry-run output structure ---
echo "--- Test 8: Dry-run output structure ---"
output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh \
    --dry-run --area scripts \
    --files ".aitask-scripts/original_script.sh" \
    --title "Test contribution" \
    --motivation "Testing the workflow" \
    --scope enhancement \
    --merge-approach "clean merge" 2>&1)

assert_contains "has Contribution heading" "## Contribution:" "$output"
assert_contains "has Motivation heading" "### Motivation" "$output"
assert_contains "has Changed Files heading" "### Changed Files" "$output"
assert_contains "has Code Changes heading" "### Code Changes" "$output"
assert_contains "has contribute metadata" "<!-- aitask-contribute-metadata" "$output"

# --- Test 9: Small diff handling ---
echo "--- Test 9: Small diff handling ---"
output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh \
    --dry-run --area scripts \
    --files ".aitask-scripts/original_script.sh" \
    --title "Small diff test" \
    --motivation "Testing" \
    --scope enhancement \
    --merge-approach "clean merge" 2>&1)

# Small diff should NOT have the preview note or full-diff HTML comment
assert_not_contains "small diff has no preview note" "Preview — full diff available" "$output"
assert_not_contains "small diff has no full-diff comment" "<!-- full-diff:" "$output"

# --- Test 10: Large diff handling ---
echo "--- Test 10: Large diff handling ---"
output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh \
    --dry-run --area scripts \
    --files ".aitask-scripts/large_script.sh" \
    --title "Large diff test" \
    --motivation "Testing" \
    --scope enhancement \
    --merge-approach "clean merge" \
    --diff-preview-lines 20 2>&1)

assert_contains "large diff has preview note" "Preview — full diff available" "$output"
assert_contains "large diff has full-diff comment" "<!-- full-diff:" "$output"

# --- Test 11: Contributor metadata ---
echo "--- Test 11: Contributor metadata ---"
output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh \
    --dry-run --area scripts \
    --files ".aitask-scripts/original_script.sh" \
    --title "Metadata test" \
    --motivation "Testing" \
    --scope enhancement \
    --merge-approach "clean merge" 2>&1)

assert_contains "metadata has contributor field" "contributor:" "$output"
assert_contains "metadata has contributor_email field" "contributor_email:" "$output"
assert_contains "metadata has version field" "based_on_version:" "$output"

# --- Summary ---
echo ""
echo "Results: $PASS passed, $FAIL failed out of $TOTAL tests"
[[ "$FAIL" -eq 0 ]] && exit 0 || exit 1
