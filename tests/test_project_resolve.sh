#!/usr/bin/env bash
# test_project_resolve.sh - Cover aitask_project_resolve.sh's three
# resolution paths (per-user index, process env var, STALE) plus
# NOT_FOUND. Live-tmux scan is exercised by manual end-to-end checks
# rather than mocked here.
#
# Run: bash tests/test_project_resolve.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Shared assertion helpers (see tests/lib/asserts.sh).
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0


# --- Setup: build two fake projects + an isolated index file -----------

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

REGISTRY_FILE="$TMPROOT/projects.yaml"
export AITASKS_PROJECTS_INDEX="$REGISTRY_FILE"

# Two fake aitasks projects (just the marker file is enough for the
# resolver's STALE / valid check).
mkdir -p "$TMPROOT/projects/alpha/aitasks/metadata"
touch "$TMPROOT/projects/alpha/aitasks/metadata/project_config.yaml"
mkdir -p "$TMPROOT/projects/beta/aitasks/metadata"
touch "$TMPROOT/projects/beta/aitasks/metadata/project_config.yaml"
# A path we'll reference but not back with the marker file (drives STALE).
mkdir -p "$TMPROOT/projects/gone"

# Hand-write a registry: alpha exists, gone is registered but its
# metadata is missing.
cat > "$REGISTRY_FILE" <<EOF
projects:
  - name: alpha
    path: $TMPROOT/projects/alpha
    git_remote: https://example.test/alpha.git
  - name: gone
    path: $TMPROOT/projects/gone
EOF

RESOLVER="$PROJECT_DIR/.aitask-scripts/aitask_project_resolve.sh"

# Isolate the env-var path against contamination from the live shell.
unset AITASKS_PROJECT_alpha AITASKS_PROJECT_beta AITASKS_PROJECT_gone \
      AITASKS_PROJECT_envonly AITASKS_PROJECT_missing 2>/dev/null || true

# --- Tests --------------------------------------------------------------

# 1. resolve-by-index → RESOLVED:<root>
out=$("$RESOLVER" alpha)
assert_eq "resolve-by-index: alpha resolves to fake root" \
    "RESOLVED:$TMPROOT/projects/alpha" "$out"

# 2. STALE → registered but path missing the marker file
out=$("$RESOLVER" gone)
assert_eq "STALE: gone points at missing aitasks marker" \
    "STALE:gone:$TMPROOT/projects/gone" "$out"

# 3. NOT_FOUND → not in registry and no env var
out=$("$RESOLVER" missing)
assert_eq "NOT_FOUND: missing project name" \
    "NOT_FOUND:missing" "$out"

# 4. Process env-var fallback → RESOLVED via AITASKS_PROJECT_envonly
export AITASKS_PROJECT_envonly="$TMPROOT/projects/beta"
out=$("$RESOLVER" envonly)
assert_eq "env-var fallback: AITASKS_PROJECT_envonly resolves" \
    "RESOLVED:$TMPROOT/projects/beta" "$out"
unset AITASKS_PROJECT_envonly

# 5. Process env-var pointing at a non-aitasks dir → STALE
export AITASKS_PROJECT_envonly="$TMPROOT/projects/gone"
out=$("$RESOLVER" envonly)
assert_eq "env-var fallback: stale path → STALE" \
    "STALE:envonly:$TMPROOT/projects/gone" "$out"
unset AITASKS_PROJECT_envonly

# 6. Registry hit takes precedence over a (would-be) env var fallback
export AITASKS_PROJECT_alpha="$TMPROOT/projects/beta"
out=$("$RESOLVER" alpha)
assert_eq "precedence: registry beats process env var" \
    "RESOLVED:$TMPROOT/projects/alpha" "$out"
unset AITASKS_PROJECT_alpha

# --- Summary ------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
