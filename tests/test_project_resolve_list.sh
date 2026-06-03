#!/usr/bin/env bash
# test_project_resolve_list.sh - Verify `aitask_project_resolve.sh list`
# emits one PROJECT:<name>:<path>:<status> line per registered entry,
# with RESOLVED or STALE based on whether the path is a valid aitasks
# project root (t832_10).
#
# Run: bash tests/test_project_resolve_list.sh

set -e

SCRIPT_DIR_T="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR_T/.." && pwd)"
RESOLVER="$PROJECT_DIR/.aitask-scripts/aitask_project_resolve.sh"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

# --- Setup --------------------------------------------------------------

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

# A valid sibling project root.
LIVE_ROOT="$TMPROOT/live_project"
mkdir -p "$LIVE_ROOT/aitasks/metadata"
touch "$LIVE_ROOT/aitasks/metadata/project_config.yaml"

# A registered path that no longer holds an aitasks project.
STALE_ROOT="$TMPROOT/stale_project"
mkdir -p "$STALE_ROOT"  # no aitasks/metadata/project_config.yaml

REGISTRY="$TMPROOT/projects.yaml"
export AITASKS_PROJECTS_INDEX="$REGISTRY"
cat > "$REGISTRY" <<EOF
projects:
  - name: live_one
    path: $LIVE_ROOT
  - name: stale_one
    path: $STALE_ROOT
EOF

# --- Case 1: list emits both entries with correct classification --------

OUT=$("$RESOLVER" list)
assert_contains "live entry surfaced as RESOLVED" \
    "PROJECT:live_one:${LIVE_ROOT}:RESOLVED" "$OUT"
assert_contains "stale entry surfaced as STALE" \
    "PROJECT:stale_one:${STALE_ROOT}:STALE" "$OUT"

# Exact line count: one per registered entry.
LINE_COUNT=$(printf '%s\n' "$OUT" | grep -c '^PROJECT:' || true)
assert_eq "list emits exactly 2 PROJECT lines" "2" "$LINE_COUNT"

# --- Case 2: empty registry yields empty output (no error) --------------

EMPTY_REGISTRY="$TMPROOT/empty.yaml"
cat > "$EMPTY_REGISTRY" <<'EOF'
projects:
EOF
AITASKS_PROJECTS_INDEX="$EMPTY_REGISTRY" "$RESOLVER" list > "$TMPROOT/empty_out.txt"
LINES=$(wc -l < "$TMPROOT/empty_out.txt" | tr -d ' ')
assert_eq "empty registry → no PROJECT lines" "0" "$LINES"

# --- Case 3: missing registry file yields empty output (no error) ------

MISSING_REGISTRY="$TMPROOT/missing.yaml"
AITASKS_PROJECTS_INDEX="$MISSING_REGISTRY" "$RESOLVER" list > "$TMPROOT/missing_out.txt"
LINES=$(wc -l < "$TMPROOT/missing_out.txt" | tr -d ' ')
assert_eq "missing registry → no PROJECT lines" "0" "$LINES"

# --- Case 4: list does NOT emit NOT_FOUND (only registry entries) ------

OUT2=$("$RESOLVER" list)
assert_not_contains "list never emits NOT_FOUND" "NOT_FOUND" "$OUT2"

# --- Summary ------------------------------------------------------------

echo
echo "=========================================="
echo "Tests: $TOTAL  Passed: $PASS  Failed: $FAIL"
echo "=========================================="

[[ "$FAIL" -eq 0 ]]
