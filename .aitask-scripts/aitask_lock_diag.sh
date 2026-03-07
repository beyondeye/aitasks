#!/usr/bin/env bash
# aitask_lock_diag.sh - Diagnostic script for lock system prerequisites
# Standalone script (not registered in ait dispatcher). Read-only — no state modification.
#
# Usage:
#   ./aiscripts/aitask_lock_diag.sh
#
# Tests all lock system prerequisites with PASS/FAIL output.
# Useful for troubleshooting lock failures in remote/web environments.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRANCH="aitask-locks"

PASS=0
FAIL=0
TOTAL=0

# --- Helpers ---

check_pass() {
    local desc="$1"
    TOTAL=$((TOTAL + 1))
    PASS=$((PASS + 1))
    echo "  PASS: $desc"
}

check_fail() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    FAIL=$((FAIL + 1))
    echo "  FAIL: $desc"
    [[ $# -gt 0 ]] && echo "        $*"
}

check_info() {
    echo "  INFO: $*"
}

echo "=== Lock System Diagnostics ==="
echo ""

# --- 1. Git available + version ---
echo "--- 1. Git ---"
if command -v git &>/dev/null; then
    git_version=$(git --version 2>/dev/null)
    check_pass "Git available ($git_version)"
else
    check_fail "Git not found in PATH"
fi

# --- 2. Origin remote configured ---
echo "--- 2. Remote ---"
if git remote get-url origin &>/dev/null; then
    remote_url=$(git remote get-url origin 2>/dev/null)
    check_pass "Origin remote configured"
    check_info "URL: $remote_url"
else
    check_fail "No git remote 'origin' configured"
fi

# --- 3. Lock branch exists on remote ---
echo "--- 3. Lock branch ---"
if git ls-remote --heads origin "$BRANCH" 2>/dev/null | grep -q "$BRANCH"; then
    check_pass "Lock branch '$BRANCH' exists on remote"
else
    check_fail "Lock branch '$BRANCH' not found on remote" "Run 'ait setup' to initialize"
fi

# --- 4. Fetch lock branch ---
echo "--- 4. Fetch ---"
if git fetch origin "$BRANCH" --quiet 2>/dev/null; then
    check_pass "Fetch lock branch succeeded"
else
    check_fail "Failed to fetch lock branch" "Network issue or branch not initialized"
fi

# --- 5. Parse lock branch tree ---
echo "--- 5. Tree parse ---"
if git rev-parse "origin/$BRANCH^{tree}" &>/dev/null; then
    tree_hash=$(git rev-parse "origin/$BRANCH^{tree}" 2>/dev/null)
    check_pass "Lock branch tree parseable ($tree_hash)"
else
    check_fail "Cannot parse lock branch tree"
fi

# --- 6. Git plumbing ---
echo "--- 6. Git plumbing ---"
if echo "test" | git hash-object --stdin &>/dev/null; then
    check_pass "git hash-object works"
else
    check_fail "git hash-object failed"
fi

if printf '' | git mktree &>/dev/null; then
    check_pass "git mktree works"
else
    check_fail "git mktree failed"
fi

# commit-tree needs a valid tree
if tree=$(printf '' | git mktree 2>/dev/null) && echo "test" | git commit-tree "$tree" &>/dev/null; then
    check_pass "git commit-tree works"
else
    check_fail "git commit-tree failed"
fi

# --- 7. Push test (dry-run) ---
echo "--- 7. Push (dry-run) ---"
if git ls-remote --heads origin "$BRANCH" 2>/dev/null | grep -q "$BRANCH"; then
    current_ref=$(git rev-parse "origin/$BRANCH" 2>/dev/null || echo "")
    if [[ -n "$current_ref" ]]; then
        if git push --dry-run origin "$current_ref:refs/heads/$BRANCH" 2>/dev/null; then
            check_pass "Push dry-run succeeded (write access confirmed)"
        else
            check_fail "Push dry-run failed" "May lack write permissions to remote"
        fi
    else
        check_fail "Cannot resolve lock branch ref for push test"
    fi
else
    check_info "Skipping push test (lock branch does not exist)"
fi

# --- 8. hostname command ---
echo "--- 8. hostname ---"
if command -v hostname &>/dev/null; then
    host=$(hostname 2>/dev/null || echo "failed")
    check_pass "hostname available ($host)"
else
    check_fail "hostname command not found" "Lock files use hostname for identification"
fi

# --- 9. date format ---
echo "--- 9. date ---"
if date '+%Y-%m-%d %H:%M' &>/dev/null; then
    date_out=$(date '+%Y-%m-%d %H:%M')
    check_pass "date format works ($date_out)"
else
    check_fail "date command format failed"
fi

# --- 10. List current locks ---
echo "--- 10. Current locks ---"
if [[ -x "$SCRIPT_DIR/aitask_lock.sh" ]]; then
    lock_list=$("$SCRIPT_DIR/aitask_lock.sh" --list 2>&1) || true
    if [[ -n "$lock_list" ]]; then
        check_pass "Lock list retrieved"
        echo "$lock_list" | while IFS= read -r line; do
            check_info "$line"
        done
    else
        check_pass "Lock list retrieved (empty)"
    fi
else
    check_fail "aitask_lock.sh not found or not executable at $SCRIPT_DIR/aitask_lock.sh"
fi

# --- 11. Environment info ---
echo "--- 11. Environment ---"
check_info "HOME: ${HOME:-unset}"
check_info "GIT_SSH_COMMAND: ${GIT_SSH_COMMAND:-unset}"
check_info "GIT_ASKPASS: ${GIT_ASKPASS:-unset}"
cred_helper=$(git config --get credential.helper 2>/dev/null || echo "none")
check_info "Git credential helper: $cred_helper"
check_info "Shell: ${SHELL:-unset}"
check_info "TERM: ${TERM:-unset}"

# --- 12. Data worktree check (t221 compatibility) ---
echo "--- 12. Data worktree ---"
if [[ -d ".aitask-data" ]]; then
    if git worktree list 2>/dev/null | grep -q ".aitask-data"; then
        data_branch=$(git -C .aitask-data rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
        check_pass "Data worktree exists (branch: $data_branch)"
    else
        check_fail "Directory .aitask-data exists but is not a git worktree"
    fi
else
    check_info "No .aitask-data directory (legacy mode or not yet initialized)"
fi

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL CHECKS PASSED"
else
    echo "SOME CHECKS FAILED"
    exit 1
fi
