#!/usr/bin/env bash
# test_aitask_projects_prune.sh - Coverage for `ait projects prune`.
#
# Run: bash tests/test_aitask_projects_prune.sh

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

PROJECTS_SH="$PROJECT_DIR/.aitask-scripts/aitask_projects.sh"

# Create a real project (will remain OK throughout).
OK_ROOT="$TMPROOT/projects/ok"
mkdir -p "$OK_ROOT/aitasks/metadata"
cat > "$OK_ROOT/aitasks/metadata/project_config.yaml" <<EOF
project:
  name: ok
  git_remote: https://example.test/ok.git
EOF

# Helper: seed a registry entry whose project root then gets nuked, so the
# registry retains the row but classify_registry_entry returns STALE.
seed_stale_entry() {
    local name="$1"
    local root="$TMPROOT/projects/$name"
    mkdir -p "$root/aitasks/metadata"
    cat > "$root/aitasks/metadata/project_config.yaml" <<EOF
project:
  name: $name
EOF
    "$PROJECTS_SH" add "$root" >/dev/null 2>&1
    rm -rf "$root"
}

# --- Test 1: no stale entries -------------------------------------------

"$PROJECTS_SH" add "$OK_ROOT" >/dev/null 2>&1
before_body=$(cat "$REGISTRY_FILE")
out=$("$PROJECTS_SH" prune --yes 2>&1)
after_body=$(cat "$REGISTRY_FILE")
assert_contains "no-stale prints zero-count header" "Found 0 stale entries." "$out"
assert_eq "no-stale leaves registry unchanged" "$before_body" "$after_body"

# --- Test 2: --dry-run lists stale entries without mutating -------------

seed_stale_entry stale_a
seed_stale_entry stale_b
before_body=$(cat "$REGISTRY_FILE")
out=$("$PROJECTS_SH" prune --dry-run 2>&1)
after_body=$(cat "$REGISTRY_FILE")
assert_contains "dry-run prints header" "Found 2 stale entries." "$out"
assert_contains "dry-run lists stale_a" "stale_a" "$out"
assert_contains "dry-run lists stale_b" "stale_b" "$out"
assert_eq "dry-run leaves registry unchanged" "$before_body" "$after_body"
# Confirm pruned summary line is NOT printed on dry-run.
assert_not_contains "dry-run does not emit Pruned summary" "Pruned" "$out"

# --- Test 3: --yes removes every stale entry ----------------------------

out=$("$PROJECTS_SH" prune --yes 2>&1)
body=$(cat "$REGISTRY_FILE")
assert_contains "--yes prints header" "Found 2 stale entries." "$out"
assert_contains "--yes prints summary" "Pruned 2 of 2 stale entries." "$out"
assert_contains "--yes preserves ok" "name: ok" "$body"
assert_not_contains "--yes removes stale_a" "name: stale_a" "$body"
assert_not_contains "--yes removes stale_b" "name: stale_b" "$body"

# --- Test 4: interactive y/n keeps only the n'd entry -------------------

seed_stale_entry stale_a
seed_stale_entry stale_b
out=$(printf 'y\nn\n' | "$PROJECTS_SH" prune 2>&1)
body=$(cat "$REGISTRY_FILE")
assert_contains "interactive prints header" "Found 2 stale entries." "$out"
assert_contains "interactive prints summary 1 of 2" "Pruned 1 of 2 stale entries." "$out"
# Exactly one stale row must remain (whichever order the registry yields).
remaining_stale=0
grep -qF "name: stale_a" <<< "$body" && remaining_stale=$((remaining_stale + 1))
grep -qF "name: stale_b" <<< "$body" && remaining_stale=$((remaining_stale + 1))
assert_eq "interactive leaves exactly one stale row" "1" "$remaining_stale"
assert_contains "interactive preserves ok" "name: ok" "$body"

# --- Test 5: unknown flag fails fast ------------------------------------

set +e
out=$("$PROJECTS_SH" prune --bogus 2>&1)
rc=$?
set -e
TOTAL=$((TOTAL + 1))
if [[ "$rc" -ne 0 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: unknown flag must exit non-zero"
fi
assert_contains "unknown flag mentions Unknown argument" "Unknown argument" "$out"

# --- Summary ------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
