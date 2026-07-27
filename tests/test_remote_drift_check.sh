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

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

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

# A fixture's real default branch. `git init` follows init.defaultBranch, which
# differs per machine (master here, main elsewhere), so tests must never hardcode
# a branch name that may not exist locally.
repo_default_branch() {
    git -C "$1" rev-parse --abbrev-ref HEAD
}

# A legacy-mode clone (no .aitask-data stub) that HAS an origin, plus a second
# branch `dev` whose origin side is ahead of the local side. This is the shape
# the --unsynced bypass exists for: legacy task_sync() pulls only the current
# branch, so `dev` is stale and the drift must still be detectable.
# Echoes "<root>|<default_branch>".
make_legacy_mode_pair_with_stale_dev() {
    local root
    root=$(mktemp -d "${TMPDIR:-/tmp}/aitask_drift_legacy_pair_XXXXXX")
    git init --bare --quiet "$root/origin.git"
    git clone --quiet "$root/origin.git" "$root/local" 2>/dev/null
    local default_branch
    (
        cd "$root/local"
        git config user.email "test@example.com"
        git config user.name  "Test"
        echo "v1" > README.md
        git add README.md
        git commit --quiet -m "init"
        git push --quiet origin HEAD 2>/dev/null
        git branch dev
        git push --quiet origin dev 2>/dev/null
        # Advance origin/dev beyond local dev, touching a plan-referenced file.
        git checkout --quiet dev
        mkdir -p .aitask-scripts
        echo "changed" > .aitask-scripts/aitask_archive.sh
        git add .aitask-scripts/aitask_archive.sh
        git commit --quiet -m "remote-only change on dev"
        git push --quiet origin dev 2>/dev/null
        git reset --hard --quiet HEAD~1
        git checkout --quiet -
    )
    default_branch=$(git -C "$root/local" rev-parse --abbrev-ref HEAD)
    echo "$root|$default_branch"
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

# Confirm: no origin remote configured (make_legacy_mode_repo uses git init).
# The branch must EXIST locally, or LOCAL_BRANCH_MISSING (checked first, since it
# needs no network) would win and this would assert NO_REMOTE for the wrong reason.
no_remote_branch=$(repo_default_branch "$no_remote")
result=$(cd "$no_remote" && "$HELPER" "$no_remote_branch" "$plan_path" 2>&1)
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

broken_branch=$(repo_default_branch "$broken")
result=$(cd "$broken" && "$HELPER" --timeout 2 "$broken_branch" "$plan_path" 2>&1)
assert_eq "unreachable origin emits FETCH_FAILED" "FETCH_FAILED" "$result"

# Signal separation: an EXISTING local branch behind an unreachable remote must
# stay FETCH_FAILED. Collapsing it into LOCAL_BRANCH_MISSING would fire a false
# "the Step 9 merge will fail" warning on every flaky network.
assert_not_contains "unreachable origin is not reported as a missing branch" \
    "LOCAL_BRANCH_MISSING" "$result"

# ============================================================
# Test 8: --unsynced bypasses the legacy short-circuit
# ============================================================

echo "--- Test 8: --unsynced in legacy mode ---"
unsynced_legacy=$(make_legacy_mode_repo)
register_cleanup "$unsynced_legacy"
plan_path="$unsynced_legacy/plan.md"
write_plan_file "$plan_path"
ul_branch=$(repo_default_branch "$unsynced_legacy")

# Negative control: without the flag, legacy mode still short-circuits.
result=$(cd "$unsynced_legacy" && "$HELPER" "$ul_branch" "$plan_path" 2>&1)
assert_eq "legacy without --unsynced still short-circuits" "LEGACY_MODE_SKIP" "$result"

# With the flag the short-circuit is skipped and evaluation continues.
result=$(cd "$unsynced_legacy" && "$HELPER" --unsynced "$ul_branch" "$plan_path" 2>&1)
assert_not_contains "--unsynced skips LEGACY_MODE_SKIP" "LEGACY_MODE_SKIP" "$result"
assert_eq "--unsynced in legacy mode falls through to NO_REMOTE" "NO_REMOTE" "$result"

# --- Test 8b: the payload case — legacy mode, origin/dev ahead of local dev ---
# Reaching NO_REMOTE only proves the short-circuit was skipped. This proves the
# bypass actually DETECTS drift on a branch legacy task_sync() never refreshes,
# which is the entire reason the flag exists.
echo "--- Test 8b: --unsynced detects drift on a stale legacy branch ---"
lpair=$(make_legacy_mode_pair_with_stale_dev)
lroot="${lpair%|*}"
register_cleanup "$lroot"
plan_path="$lroot/local/plan.md"
write_plan_file "$plan_path"

# Negative control first: without the flag the drift is invisible in legacy mode.
result=$(cd "$lroot/local" && "$HELPER" dev "$plan_path" 2>&1)
assert_eq "legacy mode hides dev drift without --unsynced" "LEGACY_MODE_SKIP" "$result"

result=$(cd "$lroot/local" && "$HELPER" --unsynced dev "$plan_path" 2>&1)
assert_contains "--unsynced reports drift on the stale branch" "AHEAD:1" "$result"
assert_contains "--unsynced still detects plan-file overlap" \
    "OVERLAP:.aitask-scripts/aitask_archive.sh" "$result"

# --- Test 8c: --unsynced is accepted in any position ---
echo "--- Test 8c: --unsynced flag position independence ---"
before=$(cd "$lroot/local" && "$HELPER" --unsynced dev "$plan_path" 2>&1)
after=$(cd "$lroot/local" && "$HELPER" dev "$plan_path" --unsynced 2>&1)
assert_eq "--unsynced after the positionals behaves identically" "$before" "$after"
mixed=$(cd "$lroot/local" && "$HELPER" dev --unsynced "$plan_path" 2>&1)
assert_eq "--unsynced between the positionals behaves identically" "$before" "$mixed"

# ============================================================
# Test 9: LOCAL_BRANCH_MISSING precedes NO_REMOTE
# ============================================================

echo "--- Test 9: missing local branch with no remote ---"
nb=$(make_legacy_mode_repo)
register_cleanup "$nb"
plan_path="$nb/plan.md"
write_plan_file "$plan_path"

# No origin AND no such local branch: the merge target cannot exist, which is
# knowable without any network. NO_REMOTE must not swallow that.
result=$(cd "$nb" && "$HELPER" --unsynced nosuchbranch "$plan_path" 2>&1)
assert_eq "missing local branch wins over NO_REMOTE" "LOCAL_BRANCH_MISSING" "$result"

# ============================================================
# Test 10: LOCAL_BRANCH_MISSING is tag-proof
# ============================================================

echo "--- Test 10: a tag must not satisfy the branch check ---"
tagged=$(make_legacy_mode_repo)
register_cleanup "$tagged"
plan_path="$tagged/plan.md"
write_plan_file "$plan_path"
git -C "$tagged" tag dev

# `git rev-parse --verify dev` resolves the TAG (gitrevisions ranks refs/tags
# above refs/heads), and `git checkout dev` would then detach HEAD so the merge
# lands on no branch. The check must be fully qualified to refs/heads/.
result=$(cd "$tagged" && "$HELPER" --unsynced dev "$plan_path" 2>&1)
assert_eq "a tag does not satisfy the local-branch check" "LOCAL_BRANCH_MISSING" "$result"

# ============================================================
# Test 11: an existing branch in branch mode is evaluated normally
# ============================================================

echo "--- Test 11: --unsynced does not otherwise alter the result ---"
pair=$(make_branch_mode_pair)
root="${pair%|*}"
default_branch="${pair##*|}"
register_cleanup "$root"
mark_branch_mode "$root/local"
plan_path="$root/local/plan.md"
write_plan_file "$plan_path"

result=$(cd "$root/local" && "$HELPER" --unsynced "$default_branch" "$plan_path" 2>&1)
assert_eq "--unsynced on an up-to-date branch still emits UP_TO_DATE" "UP_TO_DATE" "$result"

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
