#!/usr/bin/env bash
# test_create_silent_stdout.sh - Regression test for aitask_create.sh --silent.
#
# Guards against the bug fixed in commit b63a8502: task_git commit inside the
# --batch --commit path ran without --quiet, so git's "[branch hash] subject\n
# N files changed, …" output leaked to stdout. Callers that captured the
# filename via $(... --silent) received a multi-line blob instead, breaking
# the documented contract:
#
#   --silent  Output only the created filename (for scripting)
#
# Reuses the bare-remote + claim-id scaffolding from test_draft_finalize.sh
# so we exercise the real aitask_create.sh --commit path end-to-end.
#
# Run: bash tests/test_create_silent_stdout.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

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

assert_true() {
    local desc="$1" cond_rc="$2"
    TOTAL=$((TOTAL + 1))
    if [[ "$cond_rc" == "0" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
    fi
}

# --- Project setup (mirrors tests/test_draft_finalize.sh:setup_draft_project) ---
setup_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")

    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"

    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir"

    pushd "$local_dir" > /dev/null
    git config user.email "test@test.com"
    git config user.name "Test"

    mkdir -p aitasks/archived aitasks/metadata aitasks/new .aitask-scripts/lib

    cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_ls.sh" .aitask-scripts/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    chmod +x .aitask-scripts/*.sh 2>/dev/null || true

    printf 'bug\nchore\ndocumentation\nfeature\nperformance\nrefactor\nstyle\ntest\n' \
        > aitasks/metadata/task_types.txt

    echo "aitasks/new/" > .gitignore

    # Seed t1 so Test 2 can use it as --parent.
    cat > aitasks/t1_seed_parent.md <<'TASK'
---
priority: medium
effort: low
depends: []
issue_type: feature
status: Ready
labels: []
children_to_implement: []
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Seed parent.
TASK

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null

    ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1

    PROJECT_UNDER_TEST="$local_dir"
}

teardown() {
    popd > /dev/null 2>&1 || true
}

# Count stdout lines in a portable way (macOS `wc -l` pads with spaces).
line_count() {
    printf '%s' "$1" | grep -c '' | tr -d ' '
}

# --- Test 1: silent + commit emits exactly one line = created file path ---
test_silent_commit_single_line() {
    echo "=== Test 1: --batch --commit --silent stdout is exactly the filename ==="
    setup_project

    local stdout rc
    set +e
    stdout=$(./.aitask-scripts/aitask_create.sh --batch --commit --silent \
        --name "silent_smoke" --desc "Silent smoke test" 2>/dev/null)
    rc=$?
    set -e

    assert_eq "exit code 0" "0" "$rc"

    local lines
    lines="$(line_count "$stdout")"
    # Handle the trailing newline case: "foo\n" -> wc reports 1 too. If stdout
    # contained only one line but no newline, line_count still yields 1 via
    # grep -c ''. Accept 1.
    assert_eq "stdout is exactly one line" "1" "$lines"

    TOTAL=$((TOTAL + 1))
    if [[ -n "$stdout" && -f "$stdout" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: stdout line is not an existing file: '$stdout'"
    fi

    # The filename must contain the slug for a cheap sanity check.
    TOTAL=$((TOTAL + 1))
    if [[ "$stdout" == *"silent_smoke"* ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: stdout did not contain slug 'silent_smoke': '$stdout'"
    fi

    teardown
}

# --- Test 2: silent + commit + child task ---
# Guards the sibling code path in aitask_create.sh (child-task commit around
# line 1571) that was also patched by the fix.
test_silent_commit_child_single_line() {
    echo ""
    echo "=== Test 2: --batch --commit --silent --parent stdout is exactly the filename ==="
    setup_project

    local stdout rc
    set +e
    stdout=$(./.aitask-scripts/aitask_create.sh --batch --commit --silent \
        --parent 1 --name "silent_child" --desc "Silent child smoke test" 2>/dev/null)
    rc=$?
    set -e

    assert_eq "exit code 0 (child)" "0" "$rc"

    local lines
    lines="$(line_count "$stdout")"
    assert_eq "child stdout is exactly one line" "1" "$lines"

    TOTAL=$((TOTAL + 1))
    if [[ -n "$stdout" && -f "$stdout" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: child stdout line is not an existing file: '$stdout'"
    fi

    TOTAL=$((TOTAL + 1))
    if [[ "$stdout" == *"silent_child"* ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: child stdout did not contain slug 'silent_child': '$stdout'"
    fi

    teardown
}

# --- Test 3: non-silent control ---
# Non-silent mode is free to print whatever. This test only pins exit=0 and
# non-empty stdout so we notice if the happy path ever breaks — it does NOT
# assert one-line, which would over-constrain the non-silent contract.
test_nonsilent_commit_smoke() {
    echo ""
    echo "=== Test 3: --batch --commit (no --silent) succeeds with non-empty stdout ==="
    setup_project

    local stdout rc
    set +e
    stdout=$(./.aitask-scripts/aitask_create.sh --batch --commit \
        --name "loud_smoke" --desc "Loud smoke test" 2>/dev/null)
    rc=$?
    set -e

    assert_eq "exit code 0 (non-silent)" "0" "$rc"

    TOTAL=$((TOTAL + 1))
    if [[ -n "$stdout" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: non-silent stdout was empty"
    fi

    teardown
}

# --- Run ---
test_silent_commit_single_line
test_silent_commit_child_single_line
test_nonsilent_commit_smoke

for dir in "${CLEANUP_DIRS[@]}"; do
    rm -rf "$dir"
done

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
if [[ "$FAIL" -gt 0 ]]; then
    exit 1
else
    echo "All tests PASSED"
fi
