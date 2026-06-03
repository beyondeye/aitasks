#!/usr/bin/env bash
# test_parallel_cross_repo_planning_procedure.sh - Cover t832_5: the Parallel
# Cross-Repo Planning Procedure
# (.claude/skills/task-workflow/parallel-cross-repo-planning.md) and its
# dispatch wire-in inside planning.md.
#
# The procedure itself is agent-interpreted markdown, so the bash-checkable
# surface is three layers:
#
#   A. Document contract — the procedure file and the planning.md wire-in
#      carry the load-bearing instructions: metadata-only trigger, cross-repo
#      parent created first, both-or-neither --xdeps/--xdeprepo omission, the
#      push-failure warning, and the return contract. These guard against a
#      future edit silently dropping a contract the agent depends on.
#
#   B. Trigger primitive — read_xdeprepo (task_utils.sh) is metadata-only: it
#      returns the project for a task whose frontmatter sets xdeprepo, and
#      EMPTY for a task that merely mentions a registered project name or the
#      aitasks#N_M notation in its body. This is the scriptable core of the
#      procedure's Step 0 / "incidental mention does not trip the trigger".
#
#   C. Orchestrated plumbing — the exact aitask_create.sh command shapes the
#      procedure issues in Steps 4-5 produce correctly-wired tasks end-to-end
#      (local child carrying both in-repo --deps and cross-repo
#      --xdeps/--xdeprepo; bare create emitting neither).
#
# Run: bash tests/test_parallel_cross_repo_planning_procedure.sh

SCRIPT_DIR_T="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR_T/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

pass() { PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1)); }
fail() { FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); echo "FAIL: $1"; }

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

assert_file_contains() {
    local desc="$1" needle="$2" file="$3"
    if [[ -f "$file" ]] && grep -qF -- "$needle" "$file"; then
        pass
    else
        fail "$desc"
        echo "  expected substring: $needle"
        echo "  in file: $file"
    fi
}

# ===========================================================================
# Part A — Document contract
# ===========================================================================

# Cross-repo planning is split into two procedures: the design (read-only,
# runs during planning) and the child-assignment/creation (runs after the
# plan is approved, from Step 7).
DESIGN="$PROJECT_DIR/.claude/skills/task-workflow/planning-cross-repo.md"
CREATE_PROC="$PROJECT_DIR/.claude/skills/task-workflow/cross-repo-child-assignment.md"
OLD_PROC="$PROJECT_DIR/.claude/skills/task-workflow/parallel-cross-repo-planning.md"
PLANNING="$PROJECT_DIR/.claude/skills/task-workflow/planning.md"
SKILL="$PROJECT_DIR/.claude/skills/task-workflow/SKILL.md"

if [[ -f "$DESIGN" ]]; then pass; else fail "design procedure exists at $DESIGN"; fi
if [[ -f "$CREATE_PROC" ]]; then pass; else fail "child-assignment procedure exists at $CREATE_PROC"; fi
if [[ ! -e "$OLD_PROC" ]]; then pass; else fail "old combined procedure should be removed"; fi

# --- Design procedure (planning-cross-repo.md): read-only, metadata-only trigger ---
assert_file_contains "trigger uses read_xdeprepo"            "read_xdeprepo"            "$DESIGN"
assert_file_contains "trigger is described metadata-only"    "metadata-only"           "$DESIGN"
assert_file_contains "trigger explicitly does not scan body" "Do NOT scan the task body" "$DESIGN"
assert_file_contains "design creates nothing"                "No task is created in this phase" "$DESIGN"
assert_file_contains "creation deferred to after approval"   "after the plan is approved" "$DESIGN"
assert_file_contains "design return flag present"            "cross_repo_planned: true" "$DESIGN"
assert_file_contains "design points to the creation procedure" "cross-repo-child-assignment.md" "$DESIGN"

# --- Child-assignment procedure (cross-repo-child-assignment.md): creation contract ---
assert_file_contains "runs only after the plan is approved"  "runs only after the paired plan is approved" "$CREATE_PROC"
assert_file_contains "cross-repo parent is created first"    "Create the cross-repo parent first" "$CREATE_PROC"
assert_file_contains "both-or-neither omission rule present" "omit both"               "$CREATE_PROC"
assert_file_contains "push-failure warning template present" "cross-repo commits landed in" "$CREATE_PROC"
assert_file_contains "local parent demoted after creation"   "parent-of-children"      "$CREATE_PROC"
assert_file_contains "execution return flag present"         "cross_repo_executed: true" "$CREATE_PROC"
assert_file_contains "return contract parent id present"     "cross_repo_parent_id"     "$CREATE_PROC"

# Wire-in: planning.md §6.1 dispatches the design procedure (design only, no creation).
assert_file_contains "planning.md has the dispatch bullet"   "Cross-repo dispatch check" "$PLANNING"
assert_file_contains "dispatch references the design procedure" "planning-cross-repo.md" "$PLANNING"
assert_file_contains "dispatch is design-only (no creation)" "creates no tasks"         "$PLANNING"
assert_file_contains "dispatch threads cross_repo_planned"   "cross_repo_planned = true" "$PLANNING"
assert_file_contains "dispatch points to creation at Step 7" "cross-repo-child-assignment.md" "$PLANNING"

# Wire-in: SKILL.md Step 7 runs the child-assignment (creation) after approval.
assert_file_contains "SKILL.md Step 7 has the creation hook" "Cross-repo child assignment" "$SKILL"
assert_file_contains "Step 7 hook references the procedure"  "cross-repo-child-assignment.md" "$SKILL"

# The dispatch must run BEFORE the Complexity Assessment branch so the local
# child-creation path is skipped on a cross_repo_planned: true return.
disp_line=$(grep -n "Cross-repo dispatch check" "$PLANNING" | head -1 | cut -d: -f1)
ca_line=$(grep -n -- "- \*\*Complexity Assessment:\*\*" "$PLANNING" | head -1 | cut -d: -f1)
if [[ -n "$disp_line" && -n "$ca_line" && "$disp_line" -lt "$ca_line" ]]; then
    pass
else
    fail "dispatch bullet must precede Complexity Assessment (disp=$disp_line ca=$ca_line)"
fi

# ===========================================================================
# Part B — Trigger primitive (read_xdeprepo is metadata-only)
# ===========================================================================

# Source the real libs so read_xdeprepo resolves its siblings. task_utils.sh
# reads SCRIPT_DIR to locate its sibling libs, so it is consumed cross-file.
# shellcheck disable=SC2034
SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"

TMP_B=$(mktemp -d)
trap 'rm -rf "$TMP_B"' EXIT

# Task whose frontmatter declares xdeprepo → trigger fires.
cat > "$TMP_B/with_xdeprepo.md" <<'EOF'
---
priority: medium
effort: low
issue_type: feature
status: Ready
xdeprepo: sister
xdeps: [1, 2]
---
A normal cross-repo task body.
EOF

# Task with NO xdeprepo frontmatter that only MENTIONS a project name and the
# aitasks#N_M notation in prose → trigger must NOT fire (metadata-only).
cat > "$TMP_B/body_mention_only.md" <<'EOF'
---
priority: medium
effort: low
issue_type: feature
status: Ready
---
This task coordinates with the sister project and references sister#1_2 and
aitasks#3_4 in passing, but declares no xdeprepo of its own.
EOF

assert_eq "read_xdeprepo returns project when frontmatter set" \
    "sister" "$(read_xdeprepo "$TMP_B/with_xdeprepo.md")"
assert_eq "read_xdeprepo is empty when only the body mentions a project" \
    "" "$(read_xdeprepo "$TMP_B/body_mention_only.md")"
# And xdeps reads back normalized when present (sanity on the companion field).
assert_eq "read_xdeps normalizes the list" \
    "1,2" "$(read_xdeps "$TMP_B/with_xdeprepo.md")"

# ===========================================================================
# Part C — Orchestrated plumbing (Step 4-5 command shapes, end-to-end)
# ===========================================================================

TMP_C=$(mktemp -d)
trap 'rm -rf "$TMP_B" "$TMP_C"' EXIT

# Registered sister project holding two tasks so cross-repo xdeps validate.
SISTER_ROOT="$TMP_C/sister"
mkdir -p "$SISTER_ROOT/aitasks/metadata"
touch "$SISTER_ROOT/aitasks/metadata/project_config.yaml"
cat > "$SISTER_ROOT/aitasks/t1_first.md" <<'EOF'
---
priority: medium
effort: medium
issue_type: feature
status: Ready
---
body
EOF
cat > "$SISTER_ROOT/aitasks/t2_second.md" <<'EOF'
---
priority: medium
effort: medium
issue_type: feature
status: Ready
---
body
EOF
# The cross-repo re-exec runs the sister's own helpers — symlink the real ones.
mkdir -p "$SISTER_ROOT/.aitask-scripts"
for f in aitask_query_files.sh lib; do
    ln -s "$PROJECT_DIR/.aitask-scripts/$f" "$SISTER_ROOT/.aitask-scripts/$f"
done

REGISTRY="$TMP_C/projects.yaml"
export AITASKS_PROJECTS_INDEX="$REGISTRY"
cat > "$REGISTRY" <<EOF
projects:
  - name: sister
    path: $SISTER_ROOT
EOF

# Local project where the procedure's create commands run.
LOCAL_ROOT="$TMP_C/local"
mkdir -p "$LOCAL_ROOT/aitasks/metadata"
cat > "$LOCAL_ROOT/aitasks/metadata/project_config.yaml" <<'EOF'
project:
  name: local
EOF
printf 'feature\nbug\nchore\n' > "$LOCAL_ROOT/aitasks/metadata/task_types.txt"
printf 'cross_repo\ntask_workflow\n'   > "$LOCAL_ROOT/aitasks/metadata/labels.txt"

CREATE="$PROJECT_DIR/.aitask-scripts/aitask_create.sh"

run_create() {
    # Draft mode (no --commit) → inspectable file in aitasks/new/.
    local out rc
    out=$(cd "$LOCAL_ROOT" && "$CREATE" --batch --name "$1" --desc "desc" "${@:2}" 2>&1)
    rc=$?
    LAST_OUT="$out"
    LAST_RC="$rc"
}

# Each create is preceded by `rm -f new/*.md`, so exactly one draft remains.
newest_draft() {
    local f=("$LOCAL_ROOT"/aitasks/new/*.md)
    [[ -e "${f[0]}" ]] && printf '%s\n' "${f[0]}"
}

# C1: local-child shape — in-repo --deps AND cross-repo --xdeps/--xdeprepo
#     coexist in a single create (the corrected Step 5 local-child command).
rm -f "$LOCAL_ROOT/aitasks/new/"*.md
run_create local_child --type feature --priority medium --effort low \
    --deps "1" --xdeps "1,2" --xdeprepo sister
if [[ "$LAST_RC" -eq 0 ]]; then pass; else fail "C1 local-child create should succeed (rc=$LAST_RC): $LAST_OUT"; fi
draft=$(newest_draft)
if [[ -n "$draft" ]]; then
    assert_file_contains "C1 draft carries cross-repo xdeps"    "xdeps: [1, 2]"  "$draft"
    assert_file_contains "C1 draft carries cross-repo xdeprepo" "xdeprepo: sister" "$draft"
    # In-repo dependency from --deps lands in the depends field.
    if grep -Eq '^depends:.*\b1\b' "$draft"; then pass; else fail "C1 draft should carry in-repo depends on 1"; cat "$draft"; fi
else
    fail "C1 no draft produced"
fi

# C2: both-or-neither omission — a bare create emits neither field.
rm -f "$LOCAL_ROOT/aitasks/new/"*.md
run_create bare_task --type chore --priority low --effort low
if [[ "$LAST_RC" -eq 0 ]]; then pass; else fail "C2 bare create should succeed (rc=$LAST_RC): $LAST_OUT"; fi
draft=$(newest_draft)
if [[ -n "$draft" ]] && ! grep -q '^xdeps:' "$draft" && ! grep -q '^xdeprepo:' "$draft"; then
    pass
else
    fail "C2 bare draft must not emit xdeps/xdeprepo"
    [[ -n "$draft" ]] && cat "$draft"
fi

# C3: --xdeps without --xdeprepo is rejected (validator enforces the pairing
#     the procedure relies on when it omits both for a no-cross-dep child).
rm -f "$LOCAL_ROOT/aitasks/new/"*.md
run_create lonely_xdeps --type chore --priority low --effort low --xdeps "1"
if [[ "$LAST_RC" -ne 0 ]]; then pass; else fail "C3 --xdeps without --xdeprepo must fail"; fi
assert_contains "C3 surfaces the both-or-neither error" "--xdeps requires --xdeprepo" "$LAST_OUT"

# ===========================================================================
# Summary
# ===========================================================================

echo
echo "=========================================="
echo "Tests: $TOTAL  Passed: $PASS  Failed: $FAIL"
echo "=========================================="
[[ "$FAIL" -eq 0 ]]
