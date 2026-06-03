#!/usr/bin/env bash
# test_aitask_projects_doctor.sh - Coverage for `ait projects doctor`.
#
# Run: bash tests/test_aitask_projects_doctor.sh

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

PROJECTS_SH="$PROJECT_DIR/.aitask-scripts/aitask_projects.sh"

# Create a real project that stays OK throughout (also used as a local
# git_remote source for the --clone happy path).
OK_ROOT="$TMPROOT/projects/ok"
mkdir -p "$OK_ROOT/aitasks/metadata"
cat > "$OK_ROOT/aitasks/metadata/project_config.yaml" <<EOF
project:
  name: ok
  git_remote: https://example.test/ok.git
EOF
# Initialise OK_ROOT as a git repo so `git clone file://$OK_ROOT ...` works
# in the happy-path test.
(
    cd "$OK_ROOT"
    git init -q
    git config user.email "test@example.test"
    git config user.name "Test"
    git add -A
    git commit -qm "seed"
) >/dev/null 2>&1

# Helper: seed a STALE registry entry. `$2` (optional) sets git_remote
# in the seed project_config.yaml before the row is registered, so the
# resulting registry entry carries that remote.
seed_stale_entry() {
    local name="$1"
    local remote="${2:-}"
    local root="$TMPROOT/projects/$name"
    mkdir -p "$root/aitasks/metadata"
    {
        echo "project:"
        echo "  name: $name"
        [[ -n "$remote" ]] && echo "  git_remote: $remote"
    } > "$root/aitasks/metadata/project_config.yaml"
    "$PROJECTS_SH" add "$root" >/dev/null 2>&1
    rm -rf "$root"
}

reset_registry() {
    rm -f "$REGISTRY_FILE"
    "$PROJECTS_SH" add "$OK_ROOT" >/dev/null 2>&1
}

# --- Test 1: no stale entries -------------------------------------------

reset_registry
before_body=$(cat "$REGISTRY_FILE")
out=$("$PROJECTS_SH" doctor 2>&1 </dev/null)
after_body=$(cat "$REGISTRY_FILE")
assert_contains "no-stale prints zero-count header" "Found 0 stale entries." "$out"
assert_eq "no-stale leaves registry unchanged" "$before_body" "$after_body"

# --- Test 2: prune branch ----------------------------------------------

reset_registry
seed_stale_entry stale_a
out=$(printf 'p\n' | "$PROJECTS_SH" doctor 2>&1)
body=$(cat "$REGISTRY_FILE")
assert_contains "prune prints header" "Found 1 stale entries." "$out"
assert_contains "prune preserves ok" "name: ok" "$body"
assert_not_contains "prune removes stale_a" "name: stale_a" "$body"

# --- Test 3: keep branch -----------------------------------------------

reset_registry
seed_stale_entry stale_a
before_body=$(cat "$REGISTRY_FILE")
out=$(printf 'k\n' | "$PROJECTS_SH" doctor 2>&1)
after_body=$(cat "$REGISTRY_FILE")
assert_contains "keep prints header" "Found 1 stale entries." "$out"
assert_eq "keep leaves registry unchanged" "$before_body" "$after_body"
assert_contains "keep emits Keeping line" "Keeping stale_a" "$out"

# --- Test 4: skip-all breaks the loop ----------------------------------

reset_registry
seed_stale_entry stale_a
seed_stale_entry stale_b
before_body=$(cat "$REGISTRY_FILE")
out=$(printf 's\n' | "$PROJECTS_SH" doctor 2>&1)
after_body=$(cat "$REGISTRY_FILE")
assert_contains "skip-all prints header" "Found 2 stale entries." "$out"
assert_eq "skip-all leaves registry unchanged" "$before_body" "$after_body"
assert_contains "skip-all emits Skipping line" "Skipping remaining entries." "$out"
# The second entry's prompt must NOT have fired.
prompt_count=$(grep -cF 'Action?' <<< "$out" || true)
assert_eq "skip-all only renders one prompt" "1" "$prompt_count"

# --- Test 5: --clone disabled hides `c` even when remote is set --------

reset_registry
seed_stale_entry stale_with_remote "https://example.test/somewhere.git"
out=$(printf 'c\n' | "$PROJECTS_SH" doctor 2>&1)
body=$(cat "$REGISTRY_FILE")
assert_contains "clone-disabled does not list [c]lone" "[p]rune / [u]pdate / [k]eep / [s]kip-all" "$out"
assert_not_contains "clone-disabled action line excludes [c]lone" "[c]lone" "$out"
# The `c` input is rejected with a "Clone not available" warning; entry stays put.
assert_contains "clone-disabled warns on c input" "Clone not available" "$out"
assert_contains "clone-disabled keeps the entry" "name: stale_with_remote" "$body"

# --- Test 6: --clone enabled but entry has no git_remote ---------------

reset_registry
seed_stale_entry stale_no_remote  # no remote arg => no git_remote in registry
out=$(printf 'k\n' | "$PROJECTS_SH" doctor --clone 2>&1)
assert_contains "no-remote even with --clone hides [c]lone" "[p]rune / [u]pdate / [k]eep / [s]kip-all" "$out"
assert_not_contains "no-remote action line excludes [c]lone" "[c]lone" "$out"

# --- Test 7: --clone happy path ----------------------------------------

reset_registry
# Use OK_ROOT (now a real git repo) as the clone source.
seed_stale_entry stale_clonable "file://$OK_ROOT"
TARGET_PATH="$TMPROOT/projects/stale_clonable"
# Make sure the target dir does not exist before the clone.
rm -rf "$TARGET_PATH"
out=$(printf 'c\ny\n' | "$PROJECTS_SH" doctor --clone 2>&1)
assert_contains "clone happy path lists [c]lone" "[c]lone" "$out"
assert_contains "clone happy path emits success line" "Cloned and now OK." "$out"
TOTAL=$((TOTAL + 1))
if [[ -d "$TARGET_PATH" && -f "$TARGET_PATH/aitasks/metadata/project_config.yaml" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: clone happy path materializes the target directory + marker"
    echo "  target: $TARGET_PATH"
fi

# --- Test 8: update branch ---------------------------------------------

reset_registry
seed_stale_entry stale_to_update
# Pre-create a fresh dir with the marker file so cmd_update accepts it.
NEW_LOC="$TMPROOT/projects/new_loc"
mkdir -p "$NEW_LOC/aitasks/metadata"
cat > "$NEW_LOC/aitasks/metadata/project_config.yaml" <<EOF
project:
  name: stale_to_update
EOF
out=$(printf 'u\n%s\n' "$NEW_LOC" | "$PROJECTS_SH" doctor 2>&1)
body=$(cat "$REGISTRY_FILE")
assert_contains "update emits Updated line" "Updated stale_to_update" "$out"
assert_contains "update repoints registry" "path: $NEW_LOC" "$body"

# --- Test 9: unknown flag fails fast -----------------------------------

set +e
out=$("$PROJECTS_SH" doctor --bogus 2>&1)
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

# --- Test 10: --help block lists doctor --------------------------------

help_out=$("$PROJECTS_SH" --help 2>&1)
assert_contains "ait projects --help lists doctor" "doctor [--clone]" "$help_out"

# --- Summary ------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
