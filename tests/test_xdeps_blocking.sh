#!/usr/bin/env bash
# test_xdeps_blocking.sh - Cover the cross-repo xdeps blocking branch added
# to calculate_blocked_status() in aitask_ls.sh (t832_4).
#
# Strategy: build a real fake local repo and a real fake sister repo, symlink
# the project's .aitask-scripts/ into the sister so the cross-repo dispatch
# finds a working aitask_query_files.sh, register the sister under
# AITASKS_PROJECTS_INDEX, then iterate over sister-task statuses and assert
# the local task's display string in `aitask_ls.sh -v`.
#
# Run: bash tests/test_xdeps_blocking.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LS="$PROJECT_DIR/.aitask-scripts/aitask_ls.sh"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

# --- Setup --------------------------------------------------------------

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

REGISTRY_FILE="$TMPROOT/projects.yaml"
export AITASKS_PROJECTS_INDEX="$REGISTRY_FILE"

# Sister: real aitasks/ tree plus a symlinked .aitask-scripts so dispatch
# can run the real aitask_query_files.sh against the sister's tasks.
SISTER_ROOT="$TMPROOT/sister"
mkdir -p "$SISTER_ROOT/aitasks/metadata"
ln -s "$PROJECT_DIR/.aitask-scripts" "$SISTER_ROOT/.aitask-scripts"
touch "$SISTER_ROOT/aitasks/metadata/project_config.yaml"

# Local repo: holds the task carrying xdeps.
LOCAL_ROOT="$TMPROOT/local"
mkdir -p "$LOCAL_ROOT/aitasks/metadata"
touch "$LOCAL_ROOT/aitasks/metadata/project_config.yaml"

# Local target task: xdeps:[1] xdeprepo:sister.
write_local_target() {
    cat > "$LOCAL_ROOT/aitasks/t10_target.md" <<EOF
---
priority: medium
effort: low
status: Ready
issue_type: feature
xdeps: [1]
xdeprepo: sister
---
target
EOF
}
write_local_target

# Sister task whose status we vary.
write_sister_t1() {
    local status="$1"
    cat > "$SISTER_ROOT/aitasks/t1_dep.md" <<EOF
---
priority: medium
effort: low
status: $status
issue_type: feature
---
sister dep
EOF
}

# Register sister.
register_sister() {
    cat > "$REGISTRY_FILE" <<EOF
projects:
  - name: sister
    path: $SISTER_ROOT
EOF
}

# Unregister sister (empty registry).
unregister_sister() {
    cat > "$REGISTRY_FILE" <<'EOF'
projects: []
EOF
}

# Register sister at a stale path (no project_config.yaml marker).
register_sister_stale() {
    local stale="$TMPROOT/stale_sister"
    mkdir -p "$stale"   # no aitasks/metadata/project_config.yaml
    cat > "$REGISTRY_FILE" <<EOF
projects:
  - name: sister
    path: $stale
EOF
}

# Run aitask_ls.sh -v from LOCAL_ROOT and capture the line for t10.
ls_t10_line() {
    ( cd "$LOCAL_ROOT" && "$LS" -v 10 2>&1 ) | grep '^t10_target.md' || true
}

# --- Test 1: Status iteration -------------------------------------------

register_sister
for status in Ready Editing Implementing Postponed Folded; do
    write_sister_t1 "$status"
    line=$(ls_t10_line)
    assert_contains "sister t1 status=$status → t10 blocked" \
        "Status: Blocked (by sister#1)" "$line"
    assert_not_contains "sister t1 status=$status → no UNREACHABLE" \
        "UNREACHABLE" "$line"
done

# Done → unblocked
write_sister_t1 "Done"
line=$(ls_t10_line)
assert_contains "sister t1 status=Done → t10 not blocked" \
    "Status: Ready" "$line"
assert_not_contains "sister t1 status=Done → no Blocked" \
    "Blocked" "$line"

# --- Test 2: UNREACHABLE (sister not registered) ------------------------

unregister_sister
write_sister_t1 "Done"   # status irrelevant when project unresolvable
line=$(ls_t10_line)
assert_contains "sister unregistered → UNREACHABLE" \
    "Blocked (by sister#1 (UNREACHABLE))" "$line"

# --- Test 3: UNREACHABLE (stale registry entry) -------------------------

register_sister_stale
line=$(ls_t10_line)
assert_contains "sister stale path → UNREACHABLE" \
    "Blocked (by sister#1 (UNREACHABLE))" "$line"

# --- Test 4: Sanity — local-only depends still works --------------------

register_sister
write_sister_t1 "Done"
# Create an uncompleted local dep (t99) so the depends loop fires.
cat > "$LOCAL_ROOT/aitasks/t99_uncompleted.md" <<'EOF'
---
priority: medium
effort: low
status: Implementing
issue_type: feature
---
uncompleted
EOF
cat > "$LOCAL_ROOT/aitasks/t11_local_dep.md" <<'EOF'
---
priority: medium
effort: low
status: Ready
issue_type: feature
depends: [99]
---
local dep target
EOF
line=$(( cd "$LOCAL_ROOT" && "$LS" -v 11 2>&1 ) | grep '^t11_local_dep.md' || true)
assert_contains "local depends still blocks (sanity)" \
    "Blocked (by 99)" "$line"

# --- Test 5: Sanity — task with neither xdeps nor depends is Ready ------

cat > "$LOCAL_ROOT/aitasks/t12_no_deps.md" <<'EOF'
---
priority: medium
effort: low
status: Ready
issue_type: feature
---
no deps
EOF
line=$(( cd "$LOCAL_ROOT" && "$LS" -v 12 2>&1 ) | grep '^t12_no_deps.md' || true)
assert_contains "no deps → Ready" "Status: Ready" "$line"
assert_not_contains "no deps → not Blocked" "Blocked" "$line"

# --- Test 6: Child xdep id (N_M form) -----------------------------------

# Sister carries a child task t1_2; local target points at it via xdeps.
mkdir -p "$SISTER_ROOT/aitasks/t1"
cat > "$SISTER_ROOT/aitasks/t1/t1_2_child.md" <<'EOF'
---
priority: medium
effort: low
status: Implementing
issue_type: feature
---
child
EOF
cat > "$LOCAL_ROOT/aitasks/t13_child_xdep.md" <<'EOF'
---
priority: medium
effort: low
status: Ready
issue_type: feature
xdeps: [1_2]
xdeprepo: sister
---
child xdep target
EOF
line=$(( cd "$LOCAL_ROOT" && "$LS" -v 13 2>&1 ) | grep '^t13_child_xdep.md' || true)
# normalize_task_ids prefixes N_M with t; display strips it back.
assert_contains "child xdep blocks with bare N_M id" \
    "Blocked (by sister#1_2)" "$line"

# --- Summary ------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
