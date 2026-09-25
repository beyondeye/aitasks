#!/usr/bin/env bash
# test_opencode_models_reserved.sh - aitask_opencode_models.sh refuses the
# reserved `unregistered_` model-name prefix BEFORE writing anything (t1884).
#
# The prefix is reserved for agent-string fallbacks of unregistered models
# (aitask_resolve_detected_agent.sh). A conflict must fail the run with the
# registry byte-identical: no skip, no rename, no deletion of existing rows
# (which would lose their verified scores / usage history).
#
# Runs the real script against a stub `opencode` on PATH that prints canned
# `opencode models --verbose` output.
# Run: bash tests/test_opencode_models_reserved.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

# Build a throwaway project: the script, its one lib, a stub opencode that
# emits the verbose listing in $1, and (optionally) an existing registry.
setup_fixture() {
    local listing="$1"
    FIX="$(mktemp -d)"
    mkdir -p "$FIX/.aitask-scripts/lib" "$FIX/bin" "$FIX/aitasks/metadata" "$FIX/seed"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_opencode_models.sh" "$FIX/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" "$FIX/.aitask-scripts/lib/"
    printf '%s\n' "$listing" > "$FIX/listing.txt"
    cat > "$FIX/bin/opencode" <<EOF
#!/usr/bin/env bash
cat "$FIX/listing.txt"
EOF
    chmod +x "$FIX/bin/opencode"
}

run_refresh() {
    (cd "$FIX" && PATH="$FIX/bin:$PATH" bash ./.aitask-scripts/aitask_opencode_models.sh --sync-seed "$@" 2>&1)
}

EXISTING_OK='{
  "models": [
    {
      "name": "opencode_foo",
      "cli_id": "opencode/foo",
      "notes": "Foo",
      "status": "active",
      "verified": {"pick": 90},
      "verifiedstats": {"pick": {"all_time": {"runs": 3, "score_sum": 270}}}
    }
  ]
}'

LISTING_OK='opencode/foo
{
  "name": "Foo"
}'

# --- Test 1: a discovered reserved name fails closed, registry byte-identical ---
echo "=== Test 1: discovered unregistered/foo is refused before any write ==="
setup_fixture "$LISTING_OK
unregistered/foo
{
  \"name\": \"Reserved\"
}"
printf '%s\n' "$EXISTING_OK" > "$FIX/aitasks/metadata/models_opencode.json"
cp "$FIX/aitasks/metadata/models_opencode.json" "$FIX/snapshot.json"
rc=0
out=$(run_refresh) || rc=$?
assert_exit_nonzero_rc "discovered conflict exits non-zero" "$rc"
assert_contains "message lists the discovered conflict" "Discovered models whose provider id derives a reserved name" "$out"
assert_contains "message names the conflicting model" "unregistered_foo (unregistered/foo)" "$out"
assert_contains "message explains the reserved prefix" "starting with 'unregistered_' are reserved" "$out"
# A discovered conflict has no registry row to edit: the fix is the provider id.
assert_contains "discovered conflict is told to fix the provider id" "Rename that provider in your OpenCode configuration" "$out"
assert_not_contains "discovered-only conflict gets no existing-row advice" "Existing rows in" "$out"
assert_contains "message says nothing was written" "Nothing was written" "$out"
rc=0; cmp -s "$FIX/snapshot.json" "$FIX/aitasks/metadata/models_opencode.json" || rc=$?
assert_exit_zero_rc "registry byte-identical after discovered conflict" "$rc"
assert_file_not_exists "seed not written after discovered conflict" "$FIX/seed/models_opencode.json"
rm -rf "$FIX"

# --- Test 2: an existing reserved row fails closed and keeps its stats ---
echo "=== Test 2: existing unregistered_bar row is refused, not deleted ==="
setup_fixture "$LISTING_OK"
jq '.models += [{"name": "unregistered_bar", "cli_id": "unregistered/bar", "notes": "Bar",
                 "verified": {"pick": 80},
                 "verifiedstats": {"pick": {"all_time": {"runs": 7, "score_sum": 560}}}}]' \
    <<< "$EXISTING_OK" > "$FIX/aitasks/metadata/models_opencode.json"
cp "$FIX/aitasks/metadata/models_opencode.json" "$FIX/snapshot.json"
rc=0
out=$(run_refresh) || rc=$?
assert_exit_nonzero_rc "existing conflict exits non-zero" "$rc"
assert_contains "message lists the existing conflict" "Existing rows in aitasks/metadata/models_opencode.json with a reserved name" "$out"
assert_contains "message names the existing row" "unregistered_bar (unregistered/bar)" "$out"
assert_contains "existing row is told to rename it by hand, keeping stats" "rename or remove each listed row by hand, carrying its verified and verifiedstats" "$out"
assert_not_contains "existing-only conflict gets no provider advice" "Discovered models whose provider id" "$out"
rc=0; cmp -s "$FIX/snapshot.json" "$FIX/aitasks/metadata/models_opencode.json" || rc=$?
assert_exit_zero_rc "registry byte-identical after existing conflict" "$rc"
assert_eq "existing reserved row keeps its verifiedstats" "7" \
    "$(jq -r '.models[] | select(.name == "unregistered_bar") | .verifiedstats.pick.all_time.runs' \
        "$FIX/aitasks/metadata/models_opencode.json")"
rm -rf "$FIX"

# --- Test 3: dry-run is guarded too ---
echo "=== Test 3: --dry-run also refuses a reserved name ==="
setup_fixture "unregistered/foo
{
  \"name\": \"Reserved\"
}"
rc=0
out=$(run_refresh --dry-run) || rc=$?
assert_exit_nonzero_rc "dry-run conflict exits non-zero" "$rc"
assert_contains "dry-run names the conflicting row" "unregistered_foo" "$out"
rm -rf "$FIX"

# --- Test 4: no reserved names -> normal write, stats preserved ---
echo "=== Test 4: a clean run writes as before ==="
setup_fixture "$LISTING_OK
opencode/unregistered-foo
{
  \"name\": \"Not reserved\"
}"
printf '%s\n' "$EXISTING_OK" > "$FIX/aitasks/metadata/models_opencode.json"
rc=0
out=$(run_refresh) || rc=$?
assert_exit_zero_rc "clean run exits 0" "$rc"
assert_eq "verified stats preserved for opencode_foo" "3" \
    "$(jq -r '.models[] | select(.name == "opencode_foo") | .verifiedstats.pick.all_time.runs' \
        "$FIX/aitasks/metadata/models_opencode.json")"
assert_eq "opencode/unregistered-foo keeps its derived name (not a conflict)" "opencode/unregistered-foo" \
    "$(jq -r '.models[] | select(.name == "opencode_unregistered_foo") | .cli_id' \
        "$FIX/aitasks/metadata/models_opencode.json")"
assert_file_exists "seed synced on a clean run" "$FIX/seed/models_opencode.json"
rm -rf "$FIX"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
