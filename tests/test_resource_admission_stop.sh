#!/usr/bin/env bash
# test_resource_admission_stop.sh - the STATE a resource-admission park leaves
# behind (t1597), driven end to end.
#
# WHY THIS EXISTS SEPARATELY. tests/test_resource_admission.sh proves the helper
# renders the right verdict and that the workflow prose calls it in the right
# place; tests/test_plan_approved_marker_contract.sh proves the prose selects the
# stamping command. Both can be green while the park itself is broken -- a typo
# in the stop-sequence arguments, or a marker disposition that looks right in
# prose and does the opposite on disk. This is the third link: prose ⇄ command is
# pinned there, command ⇄ state is pinned here.
#
# Shape (mirroring tests/test_plan_approved_marker_drift.sh's fixture):
#   1. A real origin/clone pair with an approved, externalized plan and a task
#      claimed exactly as Step 4 claims one (Implementing + assigned).
#   2. Apply the documented stop_reason=resource_admission revert and assert the
#      whole parked contract: Ready, unassigned, marker STAMPED, plan kept and
#      committed, visible to `ait ls -v` / `ait ls --plan-approved`, and nothing
#      forked -- no aitask/<task_name> branch, no aiwork/ worktree.
#   3. The admitted re-entry prerequisite: on that same parked fixture, an
#      admitting hook returns exit 0, which is the state the workflow resumes
#      from.
#   4. NEGATIVE CONTROL -- the stop_reason=drift revert on the same fixture
#      clears the marker, so step 2's assertions can fail.
#
# Run: bash tests/test_resource_admission_stop.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

UPD="$PROJECT_DIR/.aitask-scripts/aitask_update.sh"
LS="$PROJECT_DIR/.aitask-scripts/aitask_ls.sh"
HELPER="$PROJECT_DIR/.aitask-scripts/aitask_resource_admission.sh"

TASK_NAME="t70_admission_parked"
TASK_NUM=70

cleanup_dirs=()
# shellcheck disable=SC2154
trap 'for d in "${cleanup_dirs[@]:-}"; do [[ -n "$d" && -d "$d" ]] && rm -rf "$d"; done' EXIT

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

# A repo whose task is claimed exactly as Step 4 leaves it -- Implementing and
# assigned -- with its plan externalized and COMMITTED. Echoes the root.
make_claimed_repo() {
    local root
    root=$(mktemp -d "${TMPDIR:-/tmp}/ra_stop_XXXXXX")
    git init --bare --quiet "$root/origin.git"
    git clone --quiet "$root/origin.git" "$root/local" 2>/dev/null
    (
        cd "$root/local" || exit 1
        git config user.email "test@example.com"
        git config user.name  "Test"
        mkdir -p .aitask-scripts
        echo "v1" > .aitask-scripts/aitask_archive.sh
        git add .aitask-scripts/aitask_archive.sh
        git commit --quiet -m "init"
        git push --quiet origin HEAD 2>/dev/null
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
status: Implementing
labels: []
assigned_to: someone@example.com
created_at: 2026-08-19 09:00
updated_at: 2026-08-20 09:15
---

## Context
Claimed at Step 4, plan approved, about to be admitted.
EOF

    cat > "$root/local/aiplans/p${TASK_NUM}_admission_parked.md" <<PLAN
---
Task: ${TASK_NAME}.md
Base branch: main
Output branch: main
---

## Plan

We will modify \`.aitask-scripts/aitask_archive.sh\`.
PLAN

    ( cd "$root/local" && git add aitasks aiplans >/dev/null 2>&1 \
        && git commit --quiet -m "ait: Add plan for t${TASK_NUM}" ) >/dev/null 2>&1
    printf '%s' "$root"
}

# ============================================================
# 1. Preconditions -- the fixture really is a claimed task
# ============================================================
echo "--- 1: preconditions (claimed, planned, unmarked) ---"

ROOT="$(make_claimed_repo)"; cleanup_dirs+=("$ROOT")
REPO="$ROOT/local"
TASK="$REPO/aitasks/${TASK_NAME}.md"
PLAN="$REPO/aiplans/p${TASK_NUM}_admission_parked.md"

assert_eq "the task starts Implementing (as Step 4 left it)" "Implementing" \
    "$(field "$TASK" status)"
assert_eq "the task starts assigned" "someone@example.com" "$(field "$TASK" assigned_to)"
assert_eq "the task starts UNMARKED, so the stamp below is this stop's doing" \
    "ABSENT" "$(has_field "$TASK" plan_approved_at)"

# ============================================================
# 2. The park: stop_reason=resource_admission
# ============================================================
echo "--- 2: the parked contract ---"

# The documented stop_reason=resource_admission revert (plan-approved-stop.md:
# it shares the `deferred` command -- the plan is intact and awaiting
# implementation, merely unaffordable right now).
( cd "$REPO" && TASK_DIR=aitasks "$UPD" --batch "$TASK_NUM" --status Ready \
    --assigned-to "" --plan-approved-at now --silent ) >/dev/null 2>&1

assert_eq "the park returns the task to Ready (a stop, not an abort)" "Ready" \
    "$(field "$TASK" status)"
assert_eq_trim "the park clears assigned_to" "" "$(field "$TASK" assigned_to)"
assert_eq "the park STAMPS the marker -- the plan is approved and awaiting work" \
    "PRESENT" "$(has_field "$TASK" plan_approved_at)"

ls_v=$(cd "$REPO" && "$LS" -v 99 2>&1)
assert_contains "the task is still listed after the park" "${TASK_NAME}.md" "$ls_v"
assert_contains "ait ls -v advertises the deferred approved plan" "Plan: approved" "$ls_v"

ls_marked=$(cd "$REPO" && "$LS" --plan-approved 99 2>&1)
assert_eq_trim "ait ls --plan-approved returns exactly this task" \
    "1" "$(count_lines "$ls_marked")"
assert_contains "...and it is the parked one" "${TASK_NAME}.md" "$ls_marked"

# A park is a defer: the plan must survive it, and stay committed, or the
# re-pick has nothing to skip planning with.
TOTAL=$((TOTAL + 1))
if [[ -f "$PLAN" ]]; then
    PASS=$((PASS + 1))
    echo "PASS: the park KEEPS the plan file"
else
    FAIL=$((FAIL + 1))
    echo "FAIL: the park must keep the plan file (it is a stop, not an abort)"
fi
assert_eq_trim "the plan file is committed, not just on disk" "" \
    "$(git -C "$REPO" status --porcelain -- "aiplans/p${TASK_NUM}_admission_parked.md")"

# "Stopped before implementation" concretely: the admission hook is consulted
# BEFORE Step 7's deferred fork, so a refusal strands nothing.
branches=$(git -C "$REPO" branch --list "aitask/${TASK_NAME}")
assert_eq_trim "no aitask/<task_name> branch was cut" "" "$branches"
worktrees=$(git -C "$REPO" worktree list 2>/dev/null | grep -F "aiwork/${TASK_NAME}" || true)
assert_eq_trim "no implementation worktree exists" "" "$worktrees"
assert_dir_not_exists "no aiwork/ directory at all" "$REPO/aiwork"

# ============================================================
# 3. The admitted re-entry prerequisite
# ============================================================
echo "--- 3: the re-pick's admission ---"

# Same repo, hook now admitting: the workflow's next question after a park is
# "does the host allow it yet?", and this is the answer it gets. Driving the
# REAL helper in the REAL parked tree is what makes this a prerequisite rather
# than a restatement of section 1 of the helper test.
cat > "$REPO/probe.sh" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$REPO/probe.sh"
printf 'resource_admission_command: ./probe.sh\n' \
    >> "$REPO/aitasks/metadata/project_config.yaml"

if out=$(cd "$REPO" && "$HELPER" --task-id "$TASK_NUM" --plan "$PLAN" 2>/dev/null); then
    rc=0
else
    rc=$?
fi
assert_eq_trim "an admitting hook returns exit 0 on the parked tree" "0" "$rc"
assert_contains "...with an admit verdict" "VERDICT:admit" "$out"
assert_eq "the task is still Ready and marked, waiting to be re-picked" "Ready" \
    "$(field "$TASK" status)"

# The refusing hook must still refuse here -- otherwise step 3 proves only that
# this fixture admits everything.
cat > "$REPO/probe.sh" <<'EOF'
#!/usr/bin/env bash
echo "ADMISSION_REASON: still short on memory"
exit 2
EOF
if out=$(cd "$REPO" && "$HELPER" --task-id "$TASK_NUM" --plan "$PLAN" 2>/dev/null); then
    rc=0
else
    rc=$?
fi
assert_eq_trim "a refusing hook still refuses on the same tree" "1" "$rc"
assert_contains "...naming the hook's reason" "still short on memory" "$out"

# ============================================================
# 4. Negative control: the drift revert clears the marker
# ============================================================
echo "--- 4: negative control (stop_reason=drift clears it) ---"

ROOT2="$(make_claimed_repo)"; cleanup_dirs+=("$ROOT2")
REPO2="$ROOT2/local"
TASK2="$REPO2/aitasks/${TASK_NAME}.md"

( cd "$REPO2" && TASK_DIR=aitasks "$UPD" --batch "$TASK_NUM" --status Ready \
    --assigned-to "" --plan-approved-at "" --silent ) >/dev/null 2>&1

assert_eq "the drift revert leaves NO marker" "ABSENT" \
    "$(has_field "$TASK2" plan_approved_at)"
ls_marked2=$(cd "$REPO2" && "$LS" --plan-approved 99 2>&1)
assert_eq_trim "ait ls --plan-approved returns 0 tasks after the drift revert" \
    "0" "$(count_lines "$ls_marked2")"

echo ""
echo "===================="
echo "Passed: $PASS / $TOTAL"
if [[ "$FAIL" -ne 0 ]]; then
    echo "Failed: $FAIL"
    echo "===================="
    exit 1
fi
echo "===================="
