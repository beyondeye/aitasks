#!/usr/bin/env bash
# test_aitask_projects_update.sh - Coverage for `ait projects update`.
#
# Run: bash tests/test_aitask_projects_update.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

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

# Original alpha root (will be the registered path).
ALPHA_ROOT_OLD="$TMPROOT/projects/alpha"
mkdir -p "$ALPHA_ROOT_OLD/aitasks/metadata"
cat > "$ALPHA_ROOT_OLD/aitasks/metadata/project_config.yaml" <<EOF
project:
  name: alpha
  git_remote: https://example.test/alpha.git
EOF

# New alpha root with the marker file present (will be the update target).
ALPHA_ROOT_NEW="$TMPROOT/moved/alpha"
mkdir -p "$ALPHA_ROOT_NEW/aitasks/metadata"
touch "$ALPHA_ROOT_NEW/aitasks/metadata/project_config.yaml"

# A directory without the marker file (must be rejected).
BARE_DIR="$TMPROOT/empty/bare"
mkdir -p "$BARE_DIR"

PROJECTS_SH="$PROJECT_DIR/.aitask-scripts/aitask_projects.sh"

"$PROJECTS_SH" add "$ALPHA_ROOT_OLD" >/dev/null 2>&1

# --- Tests --------------------------------------------------------------

# 1. Happy path: update alpha to ALPHA_ROOT_NEW.
out=$("$PROJECTS_SH" update alpha "$ALPHA_ROOT_NEW" 2>&1)
assert_contains "update emits Updated message" "Updated alpha" "$out"
body=$(cat "$REGISTRY_FILE")
assert_contains "registry now points to new path" "path: $ALPHA_ROOT_NEW" "$body"
# git_remote must be preserved verbatim (still from old project_config).
assert_contains "git_remote preserved across update" \
    "git_remote: https://example.test/alpha.git" "$body"
# last_opened must be today's UTC date.
today=$(date -u +"%Y-%m-%d")
assert_contains "last_opened refreshed to today" "last_opened: $today" "$body"
# Old path must no longer be in the registry (single-row replacement).
TOTAL=$((TOTAL + 1))
if ! grep -qF "path: $ALPHA_ROOT_OLD" "$REGISTRY_FILE"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: old path should be removed from registry"
fi

# 2. Missing-marker path: registry untouched, exit non-zero.
before_body=$(cat "$REGISTRY_FILE")
set +e
out=$("$PROJECTS_SH" update alpha "$BARE_DIR" 2>&1)
rc=$?
set -e
after_body=$(cat "$REGISTRY_FILE")
TOTAL=$((TOTAL + 1))
if [[ "$rc" -ne 0 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: update to non-aitasks path must exit non-zero"
fi
assert_contains "update rejects non-aitasks path" "Not an aitasks project" "$out"
assert_eq "registry untouched on missing-marker rejection" "$before_body" "$after_body"

# 3. Missing entry: registry untouched, exit non-zero.
before_body=$(cat "$REGISTRY_FILE")
set +e
out=$("$PROJECTS_SH" update ghost "$ALPHA_ROOT_NEW" 2>&1)
rc=$?
set -e
after_body=$(cat "$REGISTRY_FILE")
TOTAL=$((TOTAL + 1))
if [[ "$rc" -ne 0 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: update of unregistered name must exit non-zero"
fi
assert_contains "update reports name not registered" "is not registered" "$out"
assert_eq "registry untouched when entry missing" "$before_body" "$after_body"

# 4. Path-does-not-exist: registry untouched, exit non-zero.
before_body=$(cat "$REGISTRY_FILE")
set +e
out=$("$PROJECTS_SH" update alpha "$TMPROOT/does/not/exist" 2>&1)
rc=$?
set -e
after_body=$(cat "$REGISTRY_FILE")
TOTAL=$((TOTAL + 1))
if [[ "$rc" -ne 0 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: update to non-existent path must exit non-zero"
fi
assert_contains "update reports missing path" "Path does not exist" "$out"
assert_eq "registry untouched when path missing" "$before_body" "$after_body"

# --- Summary ------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
