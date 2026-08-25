#!/usr/bin/env bash
# test_plan_approved_marker_drift.sh - The drift-stop half of the
# `plan_approved_at` (t1595) lifecycle, driven end to end.
#
# WHY THIS EXISTS SEPARATELY. The marker's whole justification is
# "visibility, not routing": it must never make a task look implementation-ready
# on the one path that just established the plan needs re-verification. Every
# other test in this task's set covers the happy no-drift re-pick, where a
# broken drift branch is invisible. This one drives the drift path itself.
#
# Shape (mirroring tests/test_remote_drift_check.sh's fixture):
#   1. POSITIVE CONTROL -- a real origin/clone pair whose origin side is ahead
#      on a file the plan references, asserted through the production detector.
#      Without it the rest could "pass" while the drift branch is unreachable
#      and nothing was ever exercised.
#   2. Apply the documented stop_reason=drift revert.
#   3. Assert the state a re-pick would see: marker gone from the task file, no
#      `Plan: approved` in `ait ls -v`, zero hits from `ait ls --plan-approved`,
#      and no implementation fork -- no aitask/<task_name> branch, no worktree.
#   4. NEGATIVE CONTROL -- the same fixture through the stop_reason=deferred
#      revert keeps the marker, so step 3's assertions can fail.
#
# Run: bash tests/test_plan_approved_marker_drift.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

DRIFT="$PROJECT_DIR/.aitask-scripts/aitask_remote_drift_check.sh"
UPD="$PROJECT_DIR/.aitask-scripts/aitask_update.sh"
LS="$PROJECT_DIR/.aitask-scripts/aitask_ls.sh"

cleanup_dirs=()
# shellcheck disable=SC2154
trap 'for d in "${cleanup_dirs[@]:-}"; do [[ -n "$d" && -d "$d" ]] && rm -rf "$d"; done' EXIT

MARKER="2026-08-20 09:15"
TASK_NAME="t70_deferred_plan"

field() { # field <file> <name>
    awk -v f="$2" '$0=="---"{n++; next} n==1 && $0 ~ "^"f":"{sub("^"f":[[:space:]]*",""); print; exit}' "$1"
}
has_field() { # has_field <file> <name>
    if awk -v f="$2" '$0=="---"{n++; next} n==1 && $0 ~ "^"f":"{found=1; exit} END{exit !found}' "$1"; then
        echo PRESENT
    else
        echo ABSENT
    fi
}
count_lines() { printf '%s' "$1" | grep -c . || true; }

# A repo with a real origin that is AHEAD on a file the plan references, plus a
# marked task and its externalized plan. Echoes "<root>|<default_branch>".
make_drifted_repo_with_marked_task() {
    local root
    root=$(mktemp -d "${TMPDIR:-/tmp}/paa_drift_XXXXXX")
    git init --bare --quiet "$root/origin.git"
    git clone --quiet "$root/origin.git" "$root/local" 2>/dev/null
    (
        cd "$root/local"
        git config user.email "test@example.com"
        git config user.name  "Test"
        mkdir -p .aitask-scripts
        echo "v1" > .aitask-scripts/aitask_archive.sh
        git add .aitask-scripts/aitask_archive.sh
        git commit --quiet -m "init"
        git push --quiet origin HEAD 2>/dev/null
        # Advance the ORIGIN side only, touching the plan-referenced file.
        echo "changed upstream" > .aitask-scripts/aitask_archive.sh
        git add .aitask-scripts/aitask_archive.sh
        git commit --quiet -m "remote-only change"
        git push --quiet origin HEAD 2>/dev/null
        git reset --hard --quiet HEAD~1
        # Branch mode, so the helper does not short-circuit as legacy.
        mkdir -p .aitask-data/.git
    )

    mkdir -p "$root/local/aitasks/metadata" "$root/local/aiplans"
    : > "$root/local/aitasks/metadata/labels.txt"
    printf 'feature\nbug\nchore\ntest\nrefactor\n' \
        > "$root/local/aitasks/metadata/task_types.txt"
    : > "$root/local/aitasks/metadata/project_config.yaml"

    cat > "$root/local/aitasks/${TASK_NAME}.md" <<EOF
---
priority: high
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: []
plan_approved_at: $MARKER
created_at: 2026-08-19 09:00
updated_at: 2026-08-20 09:15
---

## Context
Approved and deferred.
EOF

    cat > "$root/local/aiplans/p70_deferred_plan.md" <<'PLAN'
---
Task: t70_deferred_plan.md
Base branch: main
Output branch: main
---

## Plan

We will modify `.aitask-scripts/aitask_archive.sh`.
PLAN

    local default_branch
    default_branch=$(git -C "$root/local" rev-parse --abbrev-ref HEAD)
    echo "$root|$default_branch"
}

# ============================================================
# 1. Positive control: the drift branch is genuinely reachable
# ============================================================
echo "--- 1: positive control (the production detector really reports drift) ---"

IFS='|' read -r ROOT BRANCH <<< "$(make_drifted_repo_with_marked_task)"
cleanup_dirs+=("$ROOT")
REPO="$ROOT/local"
PLAN="$REPO/aiplans/p70_deferred_plan.md"

detect=$(cd "$REPO" && "$DRIFT" "$BRANCH" "$PLAN" 2>&1)
assert_contains "the detector reports the remote is AHEAD" "AHEAD:" "$detect"
assert_contains "the drift OVERLAPS a file the plan targets" \
    "OVERLAP:.aitask-scripts/aitask_archive.sh" "$detect"

# Precondition: the marker is really there before the stop.
assert_eq "the task starts out marked" "$MARKER" \
    "$(field "$REPO/aitasks/${TASK_NAME}.md" plan_approved_at)"

# ============================================================
# 2 + 3. The drift stop, then the state a re-pick would see
# ============================================================
echo "--- 2/3: stop_reason=drift clears the marker ---"

# The documented stop_reason=drift revert (plan-approved-stop.md).
( cd "$REPO" && TASK_DIR=aitasks "$UPD" --batch 70 --status Ready \
    --assigned-to "" --plan-approved-at "" --silent ) >/dev/null 2>&1

assert_eq "drift stop removes the plan_approved_at key" "ABSENT" \
    "$(has_field "$REPO/aitasks/${TASK_NAME}.md" plan_approved_at)"
assert_eq "drift stop leaves the task Ready (a stop, not an abort)" "Ready" \
    "$(field "$REPO/aitasks/${TASK_NAME}.md" status)"

ls_v=$(cd "$REPO" && "$LS" -v 99 2>&1)
assert_contains "the task is still listed after the drift stop" \
    "${TASK_NAME}.md" "$ls_v"
assert_not_contains "ait ls -v no longer advertises a deferred approved plan" \
    "Plan: approved" "$ls_v"

ls_marked=$(cd "$REPO" && "$LS" --plan-approved 99 2>&1)
assert_eq_trim "ait ls --plan-approved returns 0 tasks after the drift stop" \
    "0" "$(count_lines "$ls_marked")"

ls_unmarked=$(cd "$REPO" && "$LS" --no-plan-approved 99 2>&1)
assert_contains "ait ls --no-plan-approved now returns the task" \
    "${TASK_NAME}.md" "$ls_unmarked"

# "Stopped before implementation" concretely: nothing was forked. The fork is
# deferred to SKILL.md Step 7, which this path never reaches.
branches=$(git -C "$REPO" branch --list "aitask/${TASK_NAME}")
assert_eq_trim "no aitask/<task_name> branch was cut" "" "$branches"
worktrees=$(git -C "$REPO" worktree list 2>/dev/null | grep -F "aiwork/${TASK_NAME}" || true)
assert_eq_trim "no implementation worktree exists" "" "$worktrees"

# The plan itself is kept -- a stop keeps the plan, only an abort may drop it.
TOTAL=$((TOTAL + 1))
if [[ -f "$PLAN" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: the drift stop must KEEP the plan file (it is a stop, not an abort)"
fi

# ============================================================
# 4. Negative control: the deferred stop keeps the marker
# ============================================================
echo "--- 4: negative control (stop_reason=deferred keeps the marker) ---"

IFS='|' read -r ROOT2 BRANCH2 <<< "$(make_drifted_repo_with_marked_task)"
cleanup_dirs+=("$ROOT2")
REPO2="$ROOT2/local"

( cd "$REPO2" && TASK_DIR=aitasks "$UPD" --batch 70 --status Ready \
    --assigned-to "" --plan-approved-at now --silent ) >/dev/null 2>&1

assert_eq "deferred stop KEEPS a plan_approved_at key" "PRESENT" \
    "$(has_field "$REPO2/aitasks/${TASK_NAME}.md" plan_approved_at)"
ls_v2=$(cd "$REPO2" && "$LS" -v 99 2>&1)
assert_contains "ait ls -v advertises the deferred approved plan" \
    "Plan: approved" "$ls_v2"
ls_marked2=$(cd "$REPO2" && "$LS" --plan-approved 99 2>&1)
assert_eq_trim "ait ls --plan-approved returns exactly 1 task" \
    "1" "$(count_lines "$ls_marked2")"

echo ""
echo "===================="
echo "Passed: $PASS / $TOTAL"
if [[ "$FAIL" -ne 0 ]]; then
    echo "Failed: $FAIL"
    echo "===================="
    exit 1
fi
echo "===================="
