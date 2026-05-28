#!/usr/bin/env bash
# test_aitask_update_xdeps.sh - Verify --xdeps / --xdeprepo on
# aitask_update.sh (t832_7 local-flag work). Companion to
# test_xdeps_validation.sh which covers the same flags on
# aitask_create.sh.
#
# Covers:
#   - happy path: --xdeps + --xdeprepo writes both YAML fields
#   - both-or-neither: only --xdeps fails, only --xdeprepo fails
#   - clearing: both "" together removes the fields
#   - parser round-trip: read_xdeps / read_xdeprepo see what update wrote
#
# Run: bash tests/test_aitask_update_xdeps.sh

set -e

SCRIPT_DIR_T="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR_T/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

assert_contains() {
    local desc="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if grep -qF -- "$needle" <<< "$haystack"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  expected substring: $needle"
        echo "  actual: $haystack"
    fi
}

assert_exits_nonzero() {
    local desc="$1" rc="$2"
    TOTAL=$((TOTAL + 1))
    if [[ "$rc" -ne 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (exit code was 0)"
    fi
}

assert_exits_zero() {
    local desc="$1" rc="$2"
    TOTAL=$((TOTAL + 1))
    if [[ "$rc" -eq 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (exit code was $rc)"
        [[ -n "${LAST_OUT:-}" ]] && echo "  stdout: $LAST_OUT"
    fi
}

# --- Setup --------------------------------------------------------------

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

# Sister project for xdeps validation (must have real task files so
# task-status resolves the cross-repo ids).
SISTER_ROOT="$TMPROOT/sister"
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

# Sister needs the helpers because the cross-repo task-status query
# re-execs them locally. Use real symlinks.
mkdir -p "$SISTER_ROOT/.aitask-scripts"
for f in aitask_query_files.sh lib; do
    ln -s "$PROJECT_DIR/.aitask-scripts/$f" "$SISTER_ROOT/.aitask-scripts/$f"
done

REGISTRY="$TMPROOT/projects.yaml"
export AITASKS_PROJECTS_INDEX="$REGISTRY"
cat > "$REGISTRY" <<EOF
projects:
  - name: sister
    path: $SISTER_ROOT
EOF

# Local project where we exercise update.sh. Need a real existing
# task file (update refuses unknown ids).
LOCAL_ROOT="$TMPROOT/local"
mkdir -p "$LOCAL_ROOT/aitasks/metadata"
cat > "$LOCAL_ROOT/aitasks/metadata/project_config.yaml" <<'EOF'
project:
  name: local
EOF
echo -e "feature\nbug\nchore" > "$LOCAL_ROOT/aitasks/metadata/task_types.txt"
echo -e "ui\nbackend" > "$LOCAL_ROOT/aitasks/metadata/labels.txt"

TASK_FILE="$LOCAL_ROOT/aitasks/t10_target.md"
cat > "$TASK_FILE" <<'EOF'
---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: []
created_at: 2026-01-01 00:00
updated_at: 2026-01-01 00:00
---

Body.
EOF

UPDATE="$PROJECT_DIR/.aitask-scripts/aitask_update.sh"

run_update() {
    set +e
    LAST_OUT=$(cd "$LOCAL_ROOT" && "$UPDATE" --batch 10 "$@" 2>&1)
    LAST_RC=$?
    set -e
}

# --- Case 1: only --xdeps → fails (both-or-neither) ----------------------
run_update --xdeps "1"
assert_exits_nonzero "only --xdeps fails"             "$LAST_RC"
assert_contains    "both-or-neither error surfaces" "both-or-neither" "$LAST_OUT"

# --- Case 2: only --xdeprepo → fails -------------------------------------
run_update --xdeprepo sister
assert_exits_nonzero "only --xdeprepo fails"          "$LAST_RC"
assert_contains    "both-or-neither error surfaces" "both-or-neither" "$LAST_OUT"

# --- Case 3: --xdeprepo unregistered → die with hint ---------------------
run_update --xdeps "1" --xdeprepo "not_registered_xxx"
assert_exits_nonzero "unregistered project fails"     "$LAST_RC"
assert_contains    "NOT_FOUND hint emitted" "is not registered" "$LAST_OUT"

# --- Case 4: --xdeps id missing in sister → fails ------------------------
run_update --xdeps "999" --xdeprepo "sister"
assert_exits_nonzero "missing cross-repo id fails"    "$LAST_RC"
assert_contains    "missing id surfaced" "999" "$LAST_OUT"

# --- Case 5: happy path → both fields land in YAML -----------------------
run_update --xdeps "1,2" --xdeprepo "sister"
assert_exits_zero  "valid pair updates the task"      "$LAST_RC"

TOTAL=$((TOTAL + 1))
if grep -q '^xdeps: \[1, 2\]$' "$TASK_FILE" && grep -q '^xdeprepo: sister$' "$TASK_FILE"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: updated task should contain xdeps + xdeprepo lines"
    cat "$TASK_FILE"
fi

# --- Case 6: parser round-trip — task_utils.sh reads back the same -----
# Source the helpers in a subshell to use read_xdeps / read_xdeprepo
# against the file we just wrote.
roundtrip=$(bash -c "
    source '$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh'
    source '$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh'
    printf 'XDEPS=%s\nXDEPREPO=%s\n' \"\$(read_xdeps '$TASK_FILE')\" \"\$(read_xdeprepo '$TASK_FILE')\"
")
assert_contains "read_xdeps round-trip"   "XDEPS=1,2"     "$roundtrip"
assert_contains "read_xdeprepo round-trip" "XDEPREPO=sister" "$roundtrip"

# --- Case 7: clearing both → fields removed from YAML --------------------
run_update --xdeps "" --xdeprepo ""
assert_exits_zero "clearing both succeeds" "$LAST_RC"

TOTAL=$((TOTAL + 1))
if ! grep -q '^xdeps:' "$TASK_FILE" && ! grep -q '^xdeprepo:' "$TASK_FILE"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: cleared task should NOT emit xdeps / xdeprepo lines"
    cat "$TASK_FILE"
fi

# --- Case 8: clearing only one side → fails ------------------------------
# First repopulate.
run_update --xdeps "1,2" --xdeprepo "sister"
assert_exits_zero "repopulate xdeps before half-clear" "$LAST_RC"
run_update --xdeps ""
assert_exits_nonzero "half-clear (xdeps only) fails" "$LAST_RC"
assert_contains "half-clear error surfaces" "both-or-neither" "$LAST_OUT"

# --- Summary ------------------------------------------------------------

echo
echo "=========================================="
echo "Tests: $TOTAL  Passed: $PASS  Failed: $FAIL"
echo "=========================================="

[[ "$FAIL" -eq 0 ]]
