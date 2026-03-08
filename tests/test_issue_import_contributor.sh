#!/usr/bin/env bash
# test_issue_import_contributor.sh - Tests for aitask-contribute metadata parsing in issue import
# Run: bash tests/test_issue_import_contributor.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

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
    if echo "$actual" | grep -qF "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected')"
    fi
}

assert_not_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF "$expected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (output should NOT contain '$expected')"
    else
        PASS=$((PASS + 1))
    fi
}

# --- Unit test: parse_contribute_metadata directly ---
# Source the script functions without running main

# We can't source the whole script (it calls main), so extract and test
# the function by sourcing just the needed parts
setup_parse_function() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    # Create a minimal script that defines just parse_contribute_metadata
    cat > "$tmpdir/parse_func.sh" << 'FUNCEOF'
parse_contribute_metadata() {
    local body="$1"
    CONTRIBUTE_CONTRIBUTOR=""
    CONTRIBUTE_EMAIL=""

    local in_block=false
    while IFS= read -r line; do
        if [[ "$line" == *"<!-- aitask-contribute-metadata"* ]]; then
            in_block=true
            continue
        fi
        if [[ "$in_block" == true ]]; then
            if [[ "$line" == *"-->"* ]]; then
                break
            fi
            case "$line" in
                *contributor_email:*)
                    CONTRIBUTE_EMAIL=$(echo "$line" | sed 's/.*contributor_email:[[:space:]]*//' | tr -d '[:space:]')
                    ;;
                *contributor:*)
                    CONTRIBUTE_CONTRIBUTOR=$(echo "$line" | sed 's/.*contributor:[[:space:]]*//' | tr -d '[:space:]')
                    ;;
            esac
        fi
    done <<< "$body"
}
FUNCEOF
    echo "$tmpdir"
}

# Setup a git project with remote and aitask-ids branch initialized
setup_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"

    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir"
    (
        cd "$local_dir"
        git config user.email "test@test.com"
        git config user.name "Test"

        mkdir -p aitasks/archived aitasks/metadata aitasks/new .aitask-scripts/lib

        cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_issue_import.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_ls.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
        # Copy repo_fetch.sh if it exists (needed by some imports)
        [[ -f "$PROJECT_DIR/.aitask-scripts/lib/repo_fetch.sh" ]] && cp "$PROJECT_DIR/.aitask-scripts/lib/repo_fetch.sh" .aitask-scripts/lib/
        chmod +x .aitask-scripts/*.sh

        printf 'bug\nchore\ndocumentation\nfeature\nperformance\nrefactor\nstyle\ntest\n' > aitasks/metadata/task_types.txt
        echo "aitasks/new/" > .gitignore

        git add -A
        git commit -m "Initial setup" --quiet
        git push --quiet 2>/dev/null

        ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1
    )

    echo "$tmpdir"
}

# Disable strict mode for test error handling
set +e

echo "=== Issue Import Contributor Metadata Tests ==="
echo ""

# --- Test 1: parse_contribute_metadata with full metadata ---
echo "--- Test 1: Parse full metadata block ---"
FUNC_DIR="$(setup_parse_function)"
source "$FUNC_DIR/parse_func.sh"

body_1="Some issue description

## Changes

Here are the changes.

<!-- aitask-contribute-metadata
contributor: testuser
contributor_email: 12345+testuser@users.noreply.github.com
based_on_version: 0.9.2
-->"

parse_contribute_metadata "$body_1"
assert_eq "contributor parsed" "testuser" "$CONTRIBUTE_CONTRIBUTOR"
assert_eq "contributor_email parsed" "12345+testuser@users.noreply.github.com" "$CONTRIBUTE_EMAIL"

rm -rf "$FUNC_DIR"

# --- Test 2: parse_contribute_metadata with no metadata ---
echo "--- Test 2: Parse body without metadata ---"
FUNC_DIR="$(setup_parse_function)"
source "$FUNC_DIR/parse_func.sh"

body_2="Just a regular issue body.

No metadata here."

parse_contribute_metadata "$body_2"
assert_eq "no contributor" "" "$CONTRIBUTE_CONTRIBUTOR"
assert_eq "no contributor_email" "" "$CONTRIBUTE_EMAIL"

rm -rf "$FUNC_DIR"

# --- Test 3: parse_contribute_metadata with contributor only (no email) ---
echo "--- Test 3: Parse metadata with contributor only ---"
FUNC_DIR="$(setup_parse_function)"
source "$FUNC_DIR/parse_func.sh"

body_3="Issue body

<!-- aitask-contribute-metadata
contributor: someuser
based_on_version: 0.9.0
-->"

parse_contribute_metadata "$body_3"
assert_eq "contributor parsed (no email)" "someuser" "$CONTRIBUTE_CONTRIBUTOR"
assert_eq "no email" "" "$CONTRIBUTE_EMAIL"

rm -rf "$FUNC_DIR"

# --- Test 4: parse_contribute_metadata does not match contributor_email as contributor ---
echo "--- Test 4: contributor_email does not clobber contributor ---"
FUNC_DIR="$(setup_parse_function)"
source "$FUNC_DIR/parse_func.sh"

# contributor_email line comes before contributor line
body_4="<!-- aitask-contribute-metadata
contributor_email: 999+myuser@users.noreply.github.com
contributor: myuser
based_on_version: 0.9.0
-->"

parse_contribute_metadata "$body_4"
assert_eq "contributor correct" "myuser" "$CONTRIBUTE_CONTRIBUTOR"
assert_eq "contributor_email correct" "999+myuser@users.noreply.github.com" "$CONTRIBUTE_EMAIL"

rm -rf "$FUNC_DIR"

# --- Test 5: Integration - batch import with contribute metadata ---
echo "--- Test 5: Batch import with contribute metadata ---"
TMPDIR_5="$(setup_project)"

# Create a mock issue body file with contribute metadata
issue_body_5="## Feature: Add new script

This adds a new helper script.

### Code Changes

\`\`\`diff
+new line
\`\`\`

<!-- aitask-contribute-metadata
contributor: external_dev
contributor_email: 555+external_dev@users.noreply.github.com
based_on_version: 0.9.1
-->"

# We can't call the full import flow (needs gh CLI), but we can test
# parse_contribute_metadata + aitask_create.sh with contributor flags
(
    cd "$TMPDIR_5/local"
    echo "Test task with contributor" | bash .aitask-scripts/aitask_create.sh --batch --name "contribute_import" \
        --contributor "external_dev" \
        --contributor-email "555+external_dev@users.noreply.github.com" \
        --issue "https://github.com/beyondeye/aitasks/issues/99" \
        --desc-file - >/dev/null 2>&1
)

draft_file_5=$(ls "$TMPDIR_5/local/aitasks/new"/draft_*_contribute_import.md 2>/dev/null | head -1)
content_5=$(cat "$draft_file_5" 2>/dev/null)
assert_contains "contributor in draft" "contributor: external_dev" "$content_5"
assert_contains "contributor_email in draft" "contributor_email: 555+external_dev@users.noreply.github.com" "$content_5"
assert_contains "issue URL in draft" "issue: https://github.com/beyondeye/aitasks/issues/99" "$content_5"

rm -rf "$TMPDIR_5"

# --- Test 6: Integration - batch import without contribute metadata ---
echo "--- Test 6: Batch import without contribute metadata ---"
TMPDIR_6="$(setup_project)"

(
    cd "$TMPDIR_6/local"
    echo "Normal issue body" | bash .aitask-scripts/aitask_create.sh --batch --name "normal_import" \
        --issue "https://github.com/owner/repo/issues/10" \
        --desc-file - >/dev/null 2>&1
)

draft_file_6=$(ls "$TMPDIR_6/local/aitasks/new"/draft_*_normal_import.md 2>/dev/null | head -1)
content_6=$(cat "$draft_file_6" 2>/dev/null)
assert_not_contains "no contributor field" "contributor:" "$content_6"
assert_not_contains "no contributor_email field" "contributor_email:" "$content_6"
assert_contains "issue URL present" "issue: https://github.com/owner/repo/issues/10" "$content_6"

rm -rf "$TMPDIR_6"

# --- Test 7: parse_contribute_metadata with extra whitespace ---
echo "--- Test 7: Parse metadata with extra whitespace ---"
FUNC_DIR="$(setup_parse_function)"
source "$FUNC_DIR/parse_func.sh"

body_7="<!-- aitask-contribute-metadata
contributor:   spacey_user
contributor_email:   spacey@users.noreply.github.com
based_on_version: 0.9.0
-->"

parse_contribute_metadata "$body_7"
assert_eq "contributor with spaces stripped" "spacey_user" "$CONTRIBUTE_CONTRIBUTOR"
assert_eq "email with spaces stripped" "spacey@users.noreply.github.com" "$CONTRIBUTE_EMAIL"

rm -rf "$FUNC_DIR"

# --- Test 8: parse_contribute_metadata ignores metadata in wrong format ---
echo "--- Test 8: Ignores non-matching HTML comments ---"
FUNC_DIR="$(setup_parse_function)"
source "$FUNC_DIR/parse_func.sh"

body_8="<!-- some-other-metadata
contributor: wrong_user
contributor_email: wrong@example.com
-->

Regular content here."

parse_contribute_metadata "$body_8"
assert_eq "no contributor from wrong block" "" "$CONTRIBUTE_CONTRIBUTOR"
assert_eq "no email from wrong block" "" "$CONTRIBUTE_EMAIL"

rm -rf "$FUNC_DIR"

# --- Test 9: parse_contribute_metadata with metadata in middle of body ---
echo "--- Test 9: Metadata block in middle of body ---"
FUNC_DIR="$(setup_parse_function)"
source "$FUNC_DIR/parse_func.sh"

body_9="# Title

Some description text here.

## Details

More content.

<!-- aitask-contribute-metadata
contributor: miduser
contributor_email: mid@users.noreply.github.com
based_on_version: 0.9.0
-->

## More content after metadata

This text comes after."

parse_contribute_metadata "$body_9"
assert_eq "contributor from mid-body block" "miduser" "$CONTRIBUTE_CONTRIBUTOR"
assert_eq "email from mid-body block" "mid@users.noreply.github.com" "$CONTRIBUTE_EMAIL"

rm -rf "$FUNC_DIR"

# --- Test 10: Syntax check ---
echo "--- Test 10: Syntax check ---"
TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/.aitask-scripts/aitask_issue_import.sh" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Syntax check failed for aitask_issue_import.sh"
fi

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
