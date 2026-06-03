#!/usr/bin/env bash
# test_aitask_projects_remove.sh - Coverage for `ait projects remove`.
#
# Run: bash tests/test_aitask_projects_remove.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, assert_not_contains) live in
# tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

# --- Setup --------------------------------------------------------------

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

REGISTRY_FILE="$TMPROOT/projects.yaml"
export AITASKS_PROJECTS_INDEX="$REGISTRY_FILE"

ALPHA_ROOT="$TMPROOT/projects/alpha"
mkdir -p "$ALPHA_ROOT/aitasks/metadata"
cat > "$ALPHA_ROOT/aitasks/metadata/project_config.yaml" <<EOF
project:
  name: alpha
  git_remote: https://example.test/alpha.git
EOF

BETA_ROOT="$TMPROOT/projects/beta"
mkdir -p "$BETA_ROOT/aitasks/metadata"
touch "$BETA_ROOT/aitasks/metadata/project_config.yaml"

PROJECTS_SH="$PROJECT_DIR/.aitask-scripts/aitask_projects.sh"

# Seed registry with alpha and beta.
"$PROJECTS_SH" add "$ALPHA_ROOT" >/dev/null 2>&1
"$PROJECTS_SH" add "$BETA_ROOT" >/dev/null 2>&1

# --- Tests --------------------------------------------------------------

# 1. remove alpha --force succeeds; beta survives.
"$PROJECTS_SH" remove alpha --force >/dev/null 2>&1
body=$(cat "$REGISTRY_FILE")
assert_not_contains "remove --force drops alpha" "name: alpha" "$body"
assert_contains "remove --force keeps beta" "name: beta" "$body"

# Re-seed for subsequent tests.
"$PROJECTS_SH" add "$ALPHA_ROOT" >/dev/null 2>&1

# 2. remove missing entry exits non-zero with helpful message.
set +e
out=$("$PROJECTS_SH" remove ghost --force 2>&1)
rc=$?
set -e
TOTAL=$((TOTAL + 1))
if [[ "$rc" -ne 0 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: remove missing must exit non-zero"
fi
assert_contains "remove missing reports not registered" "is not registered" "$out"
# Registry must be untouched by failed remove.
body=$(cat "$REGISTRY_FILE")
assert_contains "registry intact after failed remove (alpha)" "name: alpha" "$body"
assert_contains "registry intact after failed remove (beta)" "name: beta" "$body"

# 3. Interactive 'n' answer aborts without mutating.
before_body=$(cat "$REGISTRY_FILE")
out=$(printf 'n\n' | "$PROJECTS_SH" remove beta 2>&1)
after_body=$(cat "$REGISTRY_FILE")
assert_eq "interactive 'n' leaves registry unchanged" "$before_body" "$after_body"
assert_contains "interactive 'n' emits Aborted" "Aborted" "$out"

# 4. Interactive 'y' answer proceeds with the deletion.
out=$(printf 'y\n' | "$PROJECTS_SH" remove beta 2>&1)
body=$(cat "$REGISTRY_FILE")
assert_not_contains "interactive 'y' drops beta" "name: beta" "$body"
assert_contains "registry still contains alpha" "name: alpha" "$body"
assert_contains "interactive 'y' emits Removed" "Removed beta" "$out"

# --- Summary ------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
