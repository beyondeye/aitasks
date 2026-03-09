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

# --- Test 12: --source flag parsing ---
echo "--- Test 12: --source flag parsing ---"
# Valid sources should be accepted in dry-run mode
output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh \
    --dry-run --source github --area scripts \
    --files ".aitask-scripts/original_script.sh" \
    --title "Source test" --motivation "Testing" \
    --scope enhancement --merge-approach "clean merge" 2>&1)
exit_code=$?
assert_eq "source github accepted" "0" "$exit_code"

output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh \
    --dry-run --source gitlab --area scripts \
    --files ".aitask-scripts/original_script.sh" \
    --title "Source test" --motivation "Testing" \
    --scope enhancement --merge-approach "clean merge" 2>&1)
exit_code=$?
assert_eq "source gitlab accepted" "0" "$exit_code"

output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh \
    --dry-run --source bitbucket --area scripts \
    --files ".aitask-scripts/original_script.sh" \
    --title "Source test" --motivation "Testing" \
    --scope enhancement --merge-approach "clean merge" 2>&1)
exit_code=$?
assert_eq "source bitbucket accepted" "0" "$exit_code"

# Invalid source should fail
assert_exit_nonzero "invalid source rejected" \
    bash -c "cd '$LOCAL_DIR' && ./.aitask-scripts/aitask_contribute.sh --dry-run --source foobar --area scripts --files foo --title test"

# --- Test 13: Help output includes --source ---
echo "--- Test 13: Help output includes --source ---"
output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh --help 2>&1)
assert_contains "help shows --source" "--source" "$output"
assert_contains "help mentions gitlab" "gitlab" "$output"
assert_contains "help mentions bitbucket" "bitbucket" "$output"
assert_contains "help mentions glab" "glab" "$output"

# --- Test 14: Platform dry-run (github) ---
echo "--- Test 14: Platform dry-run (github) ---"
output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh \
    --dry-run --source github --area scripts \
    --files ".aitask-scripts/original_script.sh" \
    --title "GitHub test" --motivation "Testing" \
    --scope enhancement --merge-approach "clean merge" 2>&1)
assert_contains "github dry-run has contribution heading" "## Contribution:" "$output"
assert_contains "github dry-run has metadata" "<!-- aitask-contribute-metadata" "$output"

# --- Test 15: Platform dry-run (gitlab) ---
echo "--- Test 15: Platform dry-run (gitlab) ---"
output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh \
    --dry-run --source gitlab --area scripts \
    --files ".aitask-scripts/original_script.sh" \
    --title "GitLab test" --motivation "Testing" \
    --scope enhancement --merge-approach "clean merge" 2>&1)
assert_contains "gitlab dry-run has contribution heading" "## Contribution:" "$output"
assert_contains "gitlab dry-run has metadata" "<!-- aitask-contribute-metadata" "$output"

# --- Test 16: Platform dry-run (bitbucket) ---
echo "--- Test 16: Platform dry-run (bitbucket) ---"
output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh \
    --dry-run --source bitbucket --area scripts \
    --files ".aitask-scripts/original_script.sh" \
    --title "Bitbucket test" --motivation "Testing" \
    --scope enhancement --merge-approach "clean merge" 2>&1)
assert_contains "bitbucket dry-run has contribution heading" "## Contribution:" "$output"
assert_contains "bitbucket dry-run has metadata" "<!-- aitask-contribute-metadata" "$output"

# ============================================================
# parse_code_areas() and aitask_codemap.sh tests
# ============================================================

# --- Test 17: parse_code_areas with valid YAML ---
echo "--- Test 17: parse_code_areas with valid YAML ---"
mkdir -p "$LOCAL_DIR/aitasks/metadata"
cat > "$LOCAL_DIR/aitasks/metadata/code_areas.yaml" <<'YAML'
version: 1

areas:
  - name: backend
    path: src/backend/
    description: REST API and business logic
    children:
      - name: auth
        path: src/backend/auth/
        description: Authentication and JWT handling
      - name: models
        path: src/backend/models/
        description: Database models and migrations
  - name: frontend
    path: src/web/
    description: React frontend application
  - name: tests
    path: tests/
    description: Test suites
YAML

output=$(cd "$LOCAL_DIR" && source .aitask-scripts/aitask_contribute.sh 2>/dev/null; parse_code_areas 2>&1)
exit_code=$?
assert_eq "parse_code_areas exits 0" "0" "$exit_code"
assert_contains "has backend area" "AREA|backend|src/backend/|REST API and business logic|" "$output"
assert_contains "has auth child" "AREA|auth|src/backend/auth/|Authentication and JWT handling|backend" "$output"
assert_contains "has models child" "AREA|models|src/backend/models/|Database models and migrations|backend" "$output"
assert_contains "has frontend area" "AREA|frontend|src/web/|React frontend application|" "$output"
assert_contains "has tests area" "AREA|tests|tests/|Test suites|" "$output"

# --- Test 18: parse_code_areas --parent filter ---
echo "--- Test 18: parse_code_areas --parent filter ---"
output=$(cd "$LOCAL_DIR" && source .aitask-scripts/aitask_contribute.sh 2>/dev/null; parse_code_areas --parent backend 2>&1)
exit_code=$?
assert_eq "parse_code_areas --parent exits 0" "0" "$exit_code"
assert_contains "filter returns auth child" "AREA|auth|src/backend/auth/" "$output"
assert_contains "filter returns models child" "AREA|models|src/backend/models/" "$output"
assert_not_contains "filter excludes frontend" "AREA|frontend|" "$output"
assert_not_contains "filter excludes tests" "AREA|tests|" "$output"

# --- Test 19: parse_code_areas with missing file ---
echo "--- Test 19: parse_code_areas with missing file ---"
# Remove code_areas.yaml to test missing file behavior
rm -f "$LOCAL_DIR/aitasks/metadata/code_areas.yaml"
output=$(cd "$LOCAL_DIR" && source .aitask-scripts/aitask_contribute.sh; parse_code_areas 2>&1)
exit_code=$?
assert_eq "parse_code_areas missing file exits 1" "1" "$exit_code"
assert_contains "missing file outputs NO_CODE_AREAS" "NO_CODE_AREAS" "$output"

# --- Test 20: parse_code_areas with empty areas ---
echo "--- Test 20: parse_code_areas with empty areas ---"
cat > "$LOCAL_DIR/aitasks/metadata/code_areas.yaml" <<'YAML'
version: 1

areas: []
YAML
output=$(cd "$LOCAL_DIR" && source .aitask-scripts/aitask_contribute.sh 2>/dev/null; parse_code_areas 2>&1)
exit_code=$?
assert_eq "parse_code_areas empty areas exits 0" "0" "$exit_code"
assert_eq "parse_code_areas empty areas has no AREA lines" "" "$output"

# --- Test 21: aitask_codemap.sh --scan ---
echo "--- Test 21: aitask_codemap.sh --scan ---"
# Create a temp git repo with some directories
CODEMAP_DIR="$TMPDIR_TEST/codemap_test"
mkdir -p "$CODEMAP_DIR/src/backend/auth" "$CODEMAP_DIR/src/backend/models" "$CODEMAP_DIR/src/backend/api" "$CODEMAP_DIR/src/frontend" "$CODEMAP_DIR/src/shared"
mkdir -p "$CODEMAP_DIR/tests" "$CODEMAP_DIR/docs"
mkdir -p "$CODEMAP_DIR/.aitask-scripts" "$CODEMAP_DIR/aitasks/metadata"
# Copy scripts needed by codemap
cp "$PROJECT_DIR/.aitask-scripts/aitask_codemap.sh" "$CODEMAP_DIR/.aitask-scripts/"
cp -r "$PROJECT_DIR/.aitask-scripts/lib" "$CODEMAP_DIR/.aitask-scripts/"
chmod +x "$CODEMAP_DIR/.aitask-scripts/aitask_codemap.sh"
# Create some tracked files
echo "code" > "$CODEMAP_DIR/src/backend/auth/login.py"
echo "code" > "$CODEMAP_DIR/src/backend/models/user.py"
echo "code" > "$CODEMAP_DIR/src/backend/api/routes.py"
echo "code" > "$CODEMAP_DIR/src/frontend/app.js"
echo "code" > "$CODEMAP_DIR/src/shared/utils.js"
echo "code" > "$CODEMAP_DIR/tests/test_login.py"
echo "code" > "$CODEMAP_DIR/docs/readme.md"
echo "code" > "$CODEMAP_DIR/.aitask-scripts/script.sh"
(cd "$CODEMAP_DIR" && git init --quiet && git config user.email "test@test.com" && git config user.name "Test" && git add -A && git commit -m "init" --quiet)

output=$(cd "$CODEMAP_DIR" && ./.aitask-scripts/aitask_codemap.sh --scan 2>&1)
exit_code=$?
assert_eq "codemap --scan exits 0" "0" "$exit_code"
assert_contains "codemap outputs version" "version: 1" "$output"
assert_contains "codemap has src area" "name: src" "$output"
assert_contains "codemap has tests area" "name: tests" "$output"
assert_contains "codemap has docs area" "name: docs" "$output"
assert_not_contains "codemap excludes .aitask-scripts" "name: .aitask-scripts" "$output"
assert_not_contains "codemap excludes aitasks" "name: aitasks" "$output"

# --- Test 22: aitask_codemap.sh --scan with children ---
echo "--- Test 22: aitask_codemap.sh --scan with children ---"
# src/ has 3 subdirs (backend, frontend + we need to check), so it should generate children
assert_contains "codemap generates children for src" "children:" "$output"
assert_contains "codemap has backend child" "name: backend" "$output"
assert_contains "codemap has frontend child" "name: frontend" "$output"

# --- Test 23: aitask_codemap.sh --scan --existing ---
echo "--- Test 23: aitask_codemap.sh --scan --existing ---"
cat > "$CODEMAP_DIR/aitasks/metadata/code_areas.yaml" <<'YAML'
version: 1

areas:
  - name: src
    path: src/
    description: Source code
  - name: tests
    path: tests/
    description: Test suites
YAML
output=$(cd "$CODEMAP_DIR" && ./.aitask-scripts/aitask_codemap.sh --scan --existing aitasks/metadata/code_areas.yaml 2>&1)
exit_code=$?
assert_eq "codemap --existing exits 0" "0" "$exit_code"
assert_not_contains "codemap --existing excludes mapped src" "name: src" "$output"
assert_not_contains "codemap --existing excludes mapped tests" "name: tests" "$output"
assert_contains "codemap --existing shows unmapped docs" "name: docs" "$output"

# --- Test 24: aitask_codemap.sh --write refuses if exists ---
echo "--- Test 24: aitask_codemap.sh --write refuses if exists ---"
output=$(cd "$CODEMAP_DIR" && ./.aitask-scripts/aitask_codemap.sh --write 2>&1)
exit_code=$?
assert_eq "codemap --write exits 1 when file exists" "1" "$exit_code"
assert_contains "codemap --write shows already exists error" "already exists" "$output"

# --- Test 25: aitask_codemap.sh --write creates file ---
echo "--- Test 25: aitask_codemap.sh --write creates file ---"
rm "$CODEMAP_DIR/aitasks/metadata/code_areas.yaml"
output=$(cd "$CODEMAP_DIR" && ./.aitask-scripts/aitask_codemap.sh --write 2>&1)
exit_code=$?
assert_eq "codemap --write exits 0" "0" "$exit_code"
assert_eq "codemap --write creates file" "true" "$(test -f "$CODEMAP_DIR/aitasks/metadata/code_areas.yaml" && echo true || echo false)"
written_content=$(cat "$CODEMAP_DIR/aitasks/metadata/code_areas.yaml")
assert_contains "written file has version" "version: 1" "$written_content"
assert_contains "written file has areas" "areas:" "$written_content"

# Restore valid code_areas.yaml for LOCAL_DIR tests
cat > "$LOCAL_DIR/aitasks/metadata/code_areas.yaml" <<'YAML'
version: 1

areas:
  - name: backend
    path: src/backend/
    description: REST API and business logic
    children:
      - name: auth
        path: src/backend/auth/
        description: Authentication and JWT handling
      - name: models
        path: src/backend/models/
        description: Database models and migrations
  - name: frontend
    path: src/web/
    description: React frontend application
YAML

# ============================================================
# Project mode tests (--target project)
# ============================================================

# Setup a project-mode test directory (non-aitasks remote)
PROJECT_TEST_DIR="$TMPDIR_TEST/project_test"
mkdir -p "$PROJECT_TEST_DIR/.aitask-scripts/lib"
mkdir -p "$PROJECT_TEST_DIR/aitasks/metadata"
mkdir -p "$PROJECT_TEST_DIR/src/backend/auth" "$PROJECT_TEST_DIR/src/backend/models"
mkdir -p "$PROJECT_TEST_DIR/src/web"

# Copy scripts
cp "$PROJECT_DIR/.aitask-scripts/aitask_contribute.sh" "$PROJECT_TEST_DIR/.aitask-scripts/"
cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" "$PROJECT_TEST_DIR/.aitask-scripts/lib/"
cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" "$PROJECT_TEST_DIR/.aitask-scripts/lib/"
cp "$PROJECT_DIR/.aitask-scripts/lib/repo_fetch.sh" "$PROJECT_TEST_DIR/.aitask-scripts/lib/"
chmod +x "$PROJECT_TEST_DIR/.aitask-scripts/aitask_contribute.sh"
echo "1.0.0" > "$PROJECT_TEST_DIR/.aitask-scripts/VERSION"

# Create code_areas.yaml for project mode
cat > "$PROJECT_TEST_DIR/aitasks/metadata/code_areas.yaml" <<'YAML'
version: 1

areas:
  - name: backend
    path: src/backend/
    description: REST API and business logic
    children:
      - name: auth
        path: src/backend/auth/
        description: Authentication and JWT handling
      - name: models
        path: src/backend/models/
        description: Database models and migrations
  - name: frontend
    path: src/web/
    description: React frontend application
YAML

# Create source files
echo 'def login(): pass' > "$PROJECT_TEST_DIR/src/backend/auth/login.py"
echo 'class User: pass' > "$PROJECT_TEST_DIR/src/backend/models/user.py"
echo 'const App = () => {}' > "$PROJECT_TEST_DIR/src/web/app.js"

# Init git repo with non-aitasks remote
(
    cd "$PROJECT_TEST_DIR"
    git init --quiet
    git config user.email "test@test.com"
    git config user.name "Test"
    git remote add origin "https://github.com/myorg/myproject.git"
    git add -A
    git commit -m "Initial commit" --quiet
    git branch -M main

    # Create working branch with modifications
    git checkout -b working --quiet

    # Modify a file
    echo 'def login(): return True' > src/backend/auth/login.py
    git add -A
    git commit -m "Update login" --quiet
)

# --- Test 26: --list-areas without --target unchanged (backward compat) ---
echo "--- Test 26: --list-areas without --target unchanged ---"
output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh --list-areas 2>&1)
assert_contains "list-areas without target has MODE:clone" "MODE:clone" "$output"
assert_contains "list-areas without target has scripts area" "AREA|scripts|" "$output"
assert_not_contains "list-areas without target has no MODE:project" "MODE:project" "$output"

# --- Test 27: --list-areas --target framework same as no target ---
echo "--- Test 27: --list-areas --target framework ---"
output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh --list-areas --target framework 2>&1)
assert_contains "framework target has MODE:clone" "MODE:clone" "$output"
assert_contains "framework target has scripts area" "AREA|scripts|" "$output"

# --- Test 28: --list-areas --target project reads code_areas.yaml ---
echo "--- Test 28: --list-areas --target project ---"
output=$(cd "$PROJECT_TEST_DIR" && ./.aitask-scripts/aitask_contribute.sh --list-areas --target project 2>&1)
assert_contains "project target has MODE:project" "MODE:project" "$output"
assert_contains "project target has TARGET:project" "TARGET:project" "$output"
assert_contains "project target has backend area" "AREA|backend|src/backend/" "$output"
assert_contains "project target has frontend area" "AREA|frontend|src/web/" "$output"
assert_not_contains "project target has no scripts area" "AREA|scripts|" "$output"

# --- Test 29: --list-areas --target project --parent filter ---
echo "--- Test 29: --list-areas --target project --parent ---"
output=$(cd "$PROJECT_TEST_DIR" && ./.aitask-scripts/aitask_contribute.sh --list-areas --target project --parent backend 2>&1)
assert_contains "project parent filter has auth" "AREA|auth|src/backend/auth/" "$output"
assert_contains "project parent filter has models" "AREA|models|src/backend/models/" "$output"
assert_not_contains "project parent filter excludes frontend" "AREA|frontend|" "$output"

# --- Test 30: --list-changes --target project --area ---
echo "--- Test 30: --list-changes --target project --area ---"
output=$(cd "$PROJECT_TEST_DIR" && ./.aitask-scripts/aitask_contribute.sh --list-changes --target project --area backend 2>&1)
assert_contains "project list-changes finds login.py" "src/backend/auth/login.py" "$output"

# --- Test 31: --target invalid fails with error ---
echo "--- Test 31: --target invalid fails with error ---"
output=$(cd "$LOCAL_DIR" && ./.aitask-scripts/aitask_contribute.sh --list-areas --target invalid 2>&1)
exit_code=$?
assert_eq "invalid target exits non-zero" "1" "$exit_code"
assert_contains "invalid target shows error" "Unknown target" "$output"

# --- Test 32: project mode auto-detects repo ---
echo "--- Test 32: project mode auto-detects repo ---"
output=$(cd "$PROJECT_TEST_DIR" && ./.aitask-scripts/aitask_contribute.sh \
    --dry-run --target project --area auth \
    --files "src/backend/auth/login.py" \
    --title "Fix login" --motivation "Bug fix" \
    --scope bug_fix --merge-approach "clean merge" 2>&1)
assert_contains "project dry-run has project contribution heading" "## Project Contribution:" "$output"
assert_contains "project dry-run has metadata" "<!-- aitask-contribute-metadata" "$output"

# --- Summary ---
echo ""
echo "Results: $PASS passed, $FAIL failed out of $TOTAL tests"
[[ "$FAIL" -eq 0 ]] && exit 0 || exit 1
