#!/usr/bin/env bash
# test_xdeps_validation.sh - Verify validate_xdeps_pair in aitask_create.sh
# (originally t832_3; xdeprepo-alone allowance added in t832_10).
#
# Covers:
#   - --xdeps alone fails (xdeps without a project context).
#   - --xdeprepo alone SUCCEEDS (intent-only mode added in t832_10) and
#     emits `xdeprepo:` without `xdeps:`.
#   - --xdeprepo not registered → die-with-hint.
#   - --xdeprepo registered but stale path → die-with-stale-hint.
#   - --xdeps id not present cross-repo → die.
#   - happy path: both present and valid → succeeds, both emitted.
#
# Run: bash tests/test_xdeps_validation.sh

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
    fi
}

# --- Setup --------------------------------------------------------------

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

# Registry pointing at a sister project (live) and a stale entry.
SISTER_ROOT="$TMPROOT/sister"
mkdir -p "$SISTER_ROOT/aitasks/metadata"
touch "$SISTER_ROOT/aitasks/metadata/project_config.yaml"

# Create real task files in the sister so task-status finds them.
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

# The sister must have its own copy of the helpers (because the
# re-exec runs them locally). Use the real ones via symlink.
mkdir -p "$SISTER_ROOT/.aitask-scripts"
for f in aitask_query_files.sh lib; do
    ln -s "$PROJECT_DIR/.aitask-scripts/$f" "$SISTER_ROOT/.aitask-scripts/$f"
done

STALE_ROOT="$TMPROOT/stale"
mkdir -p "$STALE_ROOT"  # missing aitasks/metadata/project_config.yaml

REGISTRY="$TMPROOT/projects.yaml"
export AITASKS_PROJECTS_INDEX="$REGISTRY"
cat > "$REGISTRY" <<EOF
projects:
  - name: sister
    path: $SISTER_ROOT
  - name: stale_one
    path: $STALE_ROOT
EOF

# Local project where we run aitask_create.sh --batch.
LOCAL_ROOT="$TMPROOT/local"
mkdir -p "$LOCAL_ROOT/aitasks/metadata"
cat > "$LOCAL_ROOT/aitasks/metadata/project_config.yaml" <<'EOF'
project:
  name: local
EOF
# Required metadata files.
echo -e "feature\nbug\nchore" > "$LOCAL_ROOT/aitasks/metadata/task_types.txt"
echo -e "ui\nbackend" > "$LOCAL_ROOT/aitasks/metadata/labels.txt"

CREATE="$PROJECT_DIR/.aitask-scripts/aitask_create.sh"

run_create() {
    # Args appended after --name foo --desc bar in draft mode (no --commit).
    set +e
    local out
    out=$(cd "$LOCAL_ROOT" && "$CREATE" --batch --name "tname" --desc "tdesc" "$@" 2>&1)
    local rc=$?
    set -e
    LAST_OUT="$out"
    LAST_RC="$rc"
}

# --- Case 1: only --xdeps → fails -----------------------------------------
run_create --xdeps "1"
assert_exits_nonzero "only --xdeps fails"          "$LAST_RC"
assert_contains    "xdeps-without-xdeprepo error surfaces" \
    "--xdeps requires --xdeprepo" "$LAST_OUT"

# --- Case 2: only --xdeprepo → succeeds (intent-only mode, t832_10) ------
rm -f "$LOCAL_ROOT/aitasks/new/"*.md
run_create --xdeprepo sister
assert_exits_zero  "only --xdeprepo succeeds (intent-only)" "$LAST_RC"

# Inspect the draft: xdeprepo line present, xdeps line absent.
draft_only_xdeprepo=$(ls "$LOCAL_ROOT/aitasks/new/"*.md 2>/dev/null | head -1)
TOTAL=$((TOTAL + 1))
if [[ -n "$draft_only_xdeprepo" ]] \
        && grep -q '^xdeprepo: sister$' "$draft_only_xdeprepo" \
        && ! grep -q '^xdeps:' "$draft_only_xdeprepo"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: intent-only draft should have xdeprepo: but no xdeps:"
    [[ -n "$draft_only_xdeprepo" ]] && cat "$draft_only_xdeprepo"
fi

# --- Case 3: --xdeprepo not registered → die with hint --------------------
run_create --xdeps "1" --xdeprepo "not_registered_xxx"
assert_exits_nonzero "unregistered project fails"   "$LAST_RC"
assert_contains    "NOT_FOUND hint emitted"         "is not registered" "$LAST_OUT"

# --- Case 4: --xdeprepo stale → die with stale hint ----------------------
run_create --xdeps "1" --xdeprepo "stale_one"
assert_exits_nonzero "stale project fails"          "$LAST_RC"
assert_contains    "STALE hint emitted"             "stale" "$LAST_OUT"

# --- Case 5: --xdeps id not in sister → fails -----------------------------
run_create --xdeps "999" --xdeprepo "sister"
assert_exits_nonzero "missing cross-repo id fails"  "$LAST_RC"
assert_contains    "missing id surfaced"            "999" "$LAST_OUT"

# --- Case 6: valid pair → succeeds, frontmatter includes xdeps/xdeprepo ---
rm -f "$LOCAL_ROOT/aitasks/new/"*.md
run_create --xdeps "1,2" --xdeprepo "sister"
assert_exits_zero    "valid pair succeeds" "$LAST_RC"

# Inspect the created draft and verify emission.
draft=$(ls "$LOCAL_ROOT/aitasks/new/"*.md 2>/dev/null | head -1)
TOTAL=$((TOTAL + 1))
if [[ -n "$draft" ]] && grep -q '^xdeps: \[1, 2\]$' "$draft" && grep -q '^xdeprepo: sister$' "$draft"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: created draft should contain xdeps + xdeprepo lines"
    [[ -n "$draft" ]] && cat "$draft"
fi

# --- Case 7: neither set → succeeds without emitting fields --------------
rm -f "$LOCAL_ROOT/aitasks/new/"*.md
run_create
assert_exits_zero "no xdeps/xdeprepo still creates" "$LAST_RC"

draft=$(ls "$LOCAL_ROOT/aitasks/new/"*.md 2>/dev/null | head -1)
TOTAL=$((TOTAL + 1))
if [[ -n "$draft" ]] && ! grep -q '^xdeps:' "$draft" && ! grep -q '^xdeprepo:' "$draft"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: bare draft should NOT emit xdeps / xdeprepo lines"
    [[ -n "$draft" ]] && cat "$draft"
fi

# --- Summary ------------------------------------------------------------

echo
echo "=========================================="
echo "Tests: $TOTAL  Passed: $PASS  Failed: $FAIL"
echo "=========================================="

[[ "$FAIL" -eq 0 ]]
