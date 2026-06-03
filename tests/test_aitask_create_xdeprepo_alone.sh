#!/usr/bin/env bash
# test_aitask_create_xdeprepo_alone.sh - Verify that `aitask_create.sh
# --batch --xdeprepo <name>` (no --xdeps) succeeds and emits only
# `xdeprepo:` in the draft frontmatter (no `xdeps:` line). This is the
# intent-only mode introduced by t832_10 for the metadata-only trigger
# contract (t832_5 will consume it).
#
# Sister test of test_xdeps_validation.sh (which covers the validator
# transitions); this file focuses on the draft-emission side: the
# emitted frontmatter must contain exactly the expected fields.
#
# Run: bash tests/test_aitask_create_xdeprepo_alone.sh

set -e

SCRIPT_DIR_T="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR_T/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

assert_exits_zero() {
    local desc="$1" rc="$2"
    TOTAL=$((TOTAL + 1))
    if [[ "$rc" -eq 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (exit code was $rc)"
    fi
}

# --- Setup --------------------------------------------------------------

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

SISTER_ROOT="$TMPROOT/sister"
mkdir -p "$SISTER_ROOT/aitasks/metadata"
touch "$SISTER_ROOT/aitasks/metadata/project_config.yaml"

# Sister needs the helpers locally so `--project sister` re-exec calls
# from validate_xdeps_pair (even when xdeps is empty, the registry
# resolver still runs against this project root).
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

LOCAL_ROOT="$TMPROOT/local"
mkdir -p "$LOCAL_ROOT/aitasks/metadata"
cat > "$LOCAL_ROOT/aitasks/metadata/project_config.yaml" <<'EOF'
project:
  name: local
EOF
echo -e "feature\nbug\nchore" > "$LOCAL_ROOT/aitasks/metadata/task_types.txt"
echo -e "ui\nbackend" > "$LOCAL_ROOT/aitasks/metadata/labels.txt"

CREATE="$PROJECT_DIR/.aitask-scripts/aitask_create.sh"

# --- Case 1: --xdeprepo alone produces a draft with only xdeprepo: ------

set +e
OUT=$(cd "$LOCAL_ROOT" && "$CREATE" --batch --name "intent_only" --desc "Coordinate with sister" \
    --xdeprepo "sister" 2>&1)
RC=$?
set -e
assert_exits_zero "intent-only create succeeds" "$RC"

DRAFT=$(ls "$LOCAL_ROOT/aitasks/new/"*.md 2>/dev/null | head -1)
TOTAL=$((TOTAL + 1))
if [[ -n "$DRAFT" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: no draft produced — script output was:"
    echo "$OUT"
fi

if [[ -n "$DRAFT" ]]; then
    CONTENT=$(cat "$DRAFT")
    assert_contains    "xdeprepo: sister present" "xdeprepo: sister" "$CONTENT"
    assert_not_contains "no xdeps: line"          "xdeps:"           "$CONTENT"
fi

# --- Case 2: --xdeprepo alone, no name conflict with batch globals ------

# Run again to ensure two consecutive --xdeprepo-alone calls work.
rm -f "$LOCAL_ROOT/aitasks/new/"*.md
set +e
(cd "$LOCAL_ROOT" && "$CREATE" --batch --name "second_intent_only" --desc "Another one" \
    --xdeprepo "sister" >/dev/null 2>&1)
RC2=$?
set -e
assert_exits_zero "second intent-only create succeeds" "$RC2"

DRAFT2=$(ls "$LOCAL_ROOT/aitasks/new/"*.md 2>/dev/null | head -1)
if [[ -n "$DRAFT2" ]]; then
    CONTENT2=$(cat "$DRAFT2")
    assert_contains    "second draft has xdeprepo: sister" "xdeprepo: sister" "$CONTENT2"
    assert_not_contains "second draft has no xdeps:"       "xdeps:"           "$CONTENT2"
fi

# --- Summary ------------------------------------------------------------

echo
echo "=========================================="
echo "Tests: $TOTAL  Passed: $PASS  Failed: $FAIL"
echo "=========================================="

[[ "$FAIL" -eq 0 ]]
