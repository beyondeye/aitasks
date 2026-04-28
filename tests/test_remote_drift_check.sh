#!/usr/bin/env bash
# test_remote_drift_check.sh - Automated tests for aitask_remote_drift_check.sh
# Run: bash tests/test_remote_drift_check.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$PROJECT_DIR/.aitask-scripts/aitask_remote_drift_check.sh"

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
        echo "FAIL: $desc"
        echo "  expected: $expected"
        echo "  got     : $actual"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  expected substring: $expected"
        echo "  got               : ${actual:0:300}"
    fi
}

assert_not_contains() {
    local desc="$1" forbidden="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF "$forbidden"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (output unexpectedly contained '$forbidden')"
        echo "  got: ${actual:0:300}"
    else
        PASS=$((PASS + 1))
    fi
}

# --- Fixtures ---

# Build a scratch "remote" bare repo + a "local" clone.
# In branch-mode emulation: create a .aitask-data/.git stub so
# _ait_detect_data_worktree returns ".aitask-data" (i.e., the helper does NOT
# short-circuit as legacy mode).
make_branch_mode_pair() {
    local root
    root=$(mktemp -d "${TMPDIR:-/tmp}/aitask_drift_test_XXXXXX")

    git init --bare --quiet "$root/origin.git"

    git clone --quiet "$root/origin.git" "$root/local" 2>/dev/null
    (
        cd "$root/local"
        git config user.email "test@example.com"
        git config user.name  "Test"
        echo "v1" > README.md
        git add README.md
        git commit --quiet -m "init"
        git push --quiet origin master 2>/dev/null || git push --quiet origin main
    )

    # Determine which branch the repo defaulted to (master vs main).
    local default_branch
    default_branch=$(git -C "$root/local" rev-parse --abbrev-ref HEAD)
    echo "$root|$default_branch"
}

make_legacy_mode_repo() {
    # No .aitask-data subdir → _ait_detect_data_worktree returns "."
    local root
    root=$(mktemp -d "${TMPDIR:-/tmp}/aitask_drift_legacy_XXXXXX")
    git init --quiet "$root"
    (
        cd "$root"
        git config user.email "test@example.com"
        git config user.name  "Test"
        echo "v1" > README.md
        git add README.md
        git commit --quiet -m "init"
    )
    echo "$root"
}

# Mark a test repo as branch-mode (creates the .aitask-data stub).
mark_branch_mode() {
    local repo_root="$1"
    mkdir -p "$repo_root/.aitask-data"
    # _ait_detect_data_worktree checks for ".aitask-data/.git" file or dir.
    # An empty dir works fine.
    mkdir -p "$repo_root/.aitask-data/.git"
}

write_plan_file() {
    local target="$1"
    cat > "$target" <<'PLAN'
---
Task: t999_test.md
Base branch: main
---

## Plan

We will modify `.aitask-scripts/aitask_archive.sh` and add tests under
`tests/test_archive.sh`. The skill `.claude/skills/task-workflow/SKILL.md`
will reference the new behavior.
PLAN
}

cleanup_dirs=()
register_cleanup() { cleanup_dirs+=("$1"); }
# shellcheck disable=SC2154  # d is the loop variable in the trap body
trap 'for d in "${cleanup_dirs[@]:-}"; do [[ -n "$d" && -d "$d" ]] && rm -rf "$d"; done' EXIT

# ============================================================
# Test 1: LEGACY_MODE_SKIP
# ============================================================

echo "--- Test 1: legacy mode short-circuit ---"
legacy_repo=$(make_legacy_mode_repo)
register_cleanup "$legacy_repo"
plan_path="$legacy_repo/plan.md"
write_plan_file "$plan_path"

result=$(cd "$legacy_repo" && "$HELPER" main "$plan_path" 2>&1)
assert_eq "legacy mode emits LEGACY_MODE_SKIP" "LEGACY_MODE_SKIP" "$result"

# ============================================================
# Test 2: NO_REMOTE
# ============================================================

echo "--- Test 2: no origin remote ---"
no_remote=$(make_legacy_mode_repo)
register_cleanup "$no_remote"
mark_branch_mode "$no_remote"
plan_path="$no_remote/plan.md"
write_plan_file "$plan_path"

# Confirm: no origin remote configured (make_legacy_mode_repo uses git init)
result=$(cd "$no_remote" && "$HELPER" main "$plan_path" 2>&1)
assert_eq "no origin remote emits NO_REMOTE" "NO_REMOTE" "$result"

# ============================================================
# Test 3: UP_TO_DATE
# ============================================================

echo "--- Test 3: up-to-date with origin ---"
pair=$(make_branch_mode_pair)
root="${pair%|*}"
default_branch="${pair##*|}"
register_cleanup "$root"
mark_branch_mode "$root/local"

plan_path="$root/local/plan.md"
write_plan_file "$plan_path"

result=$(cd "$root/local" && "$HELPER" "$default_branch" "$plan_path" 2>&1)
assert_eq "aligned local/remote emits UP_TO_DATE" "UP_TO_DATE" "$result"

# ============================================================
# Test 4: AHEAD + NO_OVERLAP (remote touches a file the plan does not reference)
# ============================================================

echo "--- Test 4: remote ahead, no overlap with plan ---"
pair=$(make_branch_mode_pair)
root="${pair%|*}"
default_branch="${pair##*|}"
register_cleanup "$root"

# Make a "second clone" to push from, simulating another PC
git clone --quiet "$root/origin.git" "$root/other" 2>/dev/null
(
    cd "$root/other"
    git config user.email "other@example.com"
    git config user.name  "Other"
    mkdir -p docs
    echo "irrelevant" > docs/unrelated.md
    git add docs/unrelated.md
    git commit --quiet -m "unrelated change"
    git push --quiet origin "$default_branch"
)

mark_branch_mode "$root/local"
plan_path="$root/local/plan.md"
write_plan_file "$plan_path"

result=$(cd "$root/local" && "$HELPER" "$default_branch" "$plan_path" 2>&1)
assert_contains "remote ahead emits AHEAD" "AHEAD:1" "$result"
assert_contains "non-overlapping change emits NO_OVERLAP" "NO_OVERLAP" "$result"
assert_not_contains "no spurious OVERLAP line" "OVERLAP:" "$result"

# ============================================================
# Test 5: AHEAD + OVERLAP (remote touches a file referenced in the plan)
# ============================================================

echo "--- Test 5: remote ahead, overlap with plan-referenced file ---"
pair=$(make_branch_mode_pair)
root="${pair%|*}"
default_branch="${pair##*|}"
register_cleanup "$root"

git clone --quiet "$root/origin.git" "$root/other" 2>/dev/null
(
    cd "$root/other"
    git config user.email "other@example.com"
    git config user.name  "Other"
    mkdir -p .aitask-scripts
    echo "patched" > .aitask-scripts/aitask_archive.sh
    git add .aitask-scripts/aitask_archive.sh
    git commit --quiet -m "patch archive script"
    git push --quiet origin "$default_branch"
)

mark_branch_mode "$root/local"
plan_path="$root/local/plan.md"
write_plan_file "$plan_path"

result=$(cd "$root/local" && "$HELPER" "$default_branch" "$plan_path" 2>&1)
assert_contains "remote ahead emits AHEAD" "AHEAD:1" "$result"
assert_contains "overlap on planned file" "OVERLAP:.aitask-scripts/aitask_archive.sh" "$result"
assert_not_contains "no NO_OVERLAP when there is overlap" "NO_OVERLAP" "$result"

# ============================================================
# Test 6: FETCH_FAILED (unreachable origin)
# ============================================================

echo "--- Test 6: fetch failure ---"
broken=$(make_legacy_mode_repo)
register_cleanup "$broken"
mark_branch_mode "$broken"
(
    cd "$broken"
    git remote add origin "file:///nonexistent_$$_$RANDOM/origin.git"
)
plan_path="$broken/plan.md"
write_plan_file "$plan_path"

result=$(cd "$broken" && "$HELPER" --timeout 2 main "$plan_path" 2>&1)
assert_eq "unreachable origin emits FETCH_FAILED" "FETCH_FAILED" "$result"

# ============================================================
# Test 7: missing-arg behavior
# ============================================================

echo "--- Test 7: invalid CLI args ---"
result=$("$HELPER" 2>&1 || true)
assert_contains "missing args produces error" "<base-branch> is required" "$result"

# ============================================================
# Summary
# ============================================================

echo ""
echo "================================"
echo "Results: $PASS passed, $FAIL failed (of $TOTAL total)"
echo "================================"

if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
