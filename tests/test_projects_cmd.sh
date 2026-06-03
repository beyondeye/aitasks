#!/usr/bin/env bash
# test_projects_cmd.sh - Smoke round-trip for `ait projects` verbs
# (list / add / resolve / exec) using an isolated per-user index.
#
# Run: bash tests/test_projects_cmd.sh

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

# Build a fake aitasks project with a named project block.
ALPHA_ROOT="$TMPROOT/projects/alpha"
mkdir -p "$ALPHA_ROOT/aitasks/metadata"
cat > "$ALPHA_ROOT/aitasks/metadata/project_config.yaml" <<EOF
project:
  name: alpha
  git_remote: https://example.test/alpha.git
EOF

# Second project without a `project:` block — name should default to dir basename.
BETA_ROOT="$TMPROOT/projects/beta"
mkdir -p "$BETA_ROOT/aitasks/metadata"
touch "$BETA_ROOT/aitasks/metadata/project_config.yaml"

PROJECTS_SH="$PROJECT_DIR/.aitask-scripts/aitask_projects.sh"

# --- Tests --------------------------------------------------------------

# 1. list on empty index — emits an info-line, registry file untouched
out=$("$PROJECTS_SH" list 2>&1)
assert_contains "list on empty index reports no projects" "No registered projects" "$out"
TOTAL=$((TOTAL + 1))
if [[ ! -f "$REGISTRY_FILE" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: list on empty must not create the registry file"
fi

# 2. add alpha (with project_config block → name=alpha, remote captured)
"$PROJECTS_SH" add "$ALPHA_ROOT" >/dev/null 2>&1
[[ -f "$REGISTRY_FILE" ]] && PASS=$((PASS + 1)) || { FAIL=$((FAIL + 1)); echo "FAIL: registry file created"; }
TOTAL=$((TOTAL + 1))
body=$(cat "$REGISTRY_FILE")
assert_contains "add alpha: name in registry" "name: alpha" "$body"
assert_contains "add alpha: path in registry" "path: $ALPHA_ROOT" "$body"
assert_contains "add alpha: git_remote captured from project_config" \
    "git_remote: https://example.test/alpha.git" "$body"

# 3. add beta (no project_config block → name defaults to basename)
"$PROJECTS_SH" add "$BETA_ROOT" >/dev/null 2>&1
body=$(cat "$REGISTRY_FILE")
assert_contains "add beta: name defaults to basename" "name: beta" "$body"
assert_contains "add beta: path recorded" "path: $BETA_ROOT" "$body"

# 4. add alpha again → idempotent (still only one alpha entry)
"$PROJECTS_SH" add "$ALPHA_ROOT" >/dev/null 2>&1
count=$(grep -c '^  - name: alpha$' "$REGISTRY_FILE")
assert_eq "add is idempotent: exactly one alpha entry" "1" "$count"

# 5. list shows both entries (regardless of status)
out=$("$PROJECTS_SH" list 2>&1)
assert_contains "list shows alpha" "alpha" "$out"
assert_contains "list shows beta" "beta" "$out"

# 6. resolve round-trip
out=$("$PROJECTS_SH" resolve alpha)
assert_eq "resolve alpha" "RESOLVED:$ALPHA_ROOT" "$out"
out=$("$PROJECTS_SH" resolve beta)
assert_eq "resolve beta" "RESOLVED:$BETA_ROOT" "$out"
out=$("$PROJECTS_SH" resolve missing)
assert_eq "resolve NOT_FOUND" "NOT_FOUND:missing" "$out"

# 7. exec runs the command in the resolved root
out=$("$PROJECTS_SH" exec alpha -- pwd)
assert_eq "exec runs in resolved root" "$ALPHA_ROOT" "$out"

# 8. exec on NOT_FOUND fails non-zero
set +e
"$PROJECTS_SH" exec missing -- pwd >/dev/null 2>&1
rc=$?
set -e
TOTAL=$((TOTAL + 1))
if [[ "$rc" -ne 0 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: exec on NOT_FOUND must exit non-zero"
fi

# --- Summary ------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
