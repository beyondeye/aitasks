#!/usr/bin/env bash
# test_opencode_models_merge.sh - aitask_opencode_models.sh carries every field
# it does not regenerate across a refresh (t1919).
#
# Discovery owns name/cli_id/notes/status. Everything else on an existing row —
# verified, verifiedstats, usagestats, any future counter — is written by other
# updaters (aitask_usage_update.sh, aitask_verified_update.sh) and must survive,
# including a write that lands while discovery is still running.
#
# Runs the real script against a stub `opencode` on PATH that prints canned
# `opencode models --verbose` output. OPENCODE_MODELS_SCRIPT overrides the
# script under test (used to show these cases fail on the pre-fix merge), and
# REGISTRY_CAS_LIB the compare-and-swap lib (t1928 negative control). Tests 6-8
# drive the lib's AIT_CAS_BEFORE_SWAP_HOOK seam to land a write after the merge.
# Run: bash tests/test_opencode_models_merge.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRIPT_UNDER_TEST="${OPENCODE_MODELS_SCRIPT:-$PROJECT_DIR/.aitask-scripts/aitask_opencode_models.sh}"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

# Build a throwaway project: the script, its libs, a stub opencode that runs
# the optional hook in $2 (simulating a concurrent writer) and then emits the
# verbose listing in $1.
setup_fixture() {
    local listing="$1" hook="${2:-}"
    FIX="$(mktemp -d)"
    mkdir -p "$FIX/.aitask-scripts/lib" "$FIX/bin" "$FIX/aitasks/metadata" "$FIX/seed"
    cp "$SCRIPT_UNDER_TEST" "$FIX/.aitask-scripts/aitask_opencode_models.sh"
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" "$FIX/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/atomic_write.sh" "$FIX/.aitask-scripts/lib/"
    cp "${REGISTRY_CAS_LIB:-$PROJECT_DIR/.aitask-scripts/lib/registry_cas.sh}" "$FIX/.aitask-scripts/lib/registry_cas.sh"
    printf '%s\n' "$listing" > "$FIX/listing.txt"
    printf '%s\n' "$hook" > "$FIX/hook.sh"
    cat > "$FIX/bin/opencode" <<EOF
#!/usr/bin/env bash
bash "$FIX/hook.sh"
cat "$FIX/listing.txt"
EOF
    chmod +x "$FIX/bin/opencode"
}

run_refresh() {
    (cd "$FIX" && PATH="$FIX/bin:$PATH" bash ./.aitask-scripts/aitask_opencode_models.sh --sync-seed 2>&1)
}

REGISTRY="aitasks/metadata/models_opencode.json"

# The non-generated part of a row, canonicalised for comparison.
kept_fields() {
    jq -S --arg n "$2" '.models[] | select(.name == $n) | del(.name, .cli_id, .notes, .status)' "$1"
}

field() {
    jq -r --arg n "$2" ".models[] | select(.name == \$n) | $3" "$1"
}

LISTING_FOO='opencode/foo
{
  "name": "Foo New",
  "limit": {"context": 200000}
}'

# --- Test 1: every non-generated field survives; notes are regenerated ---
echo "=== Test 1: usagestats, verified, verifiedstats and extra fields are kept ==="
setup_fixture "$LISTING_FOO"
cat > "$FIX/$REGISTRY" <<'EOF'
{
  "models": [
    {
      "name": "opencode_foo",
      "cli_id": "opencode/foo",
      "notes": "Foo Old",
      "status": "active",
      "verified": {"pick": 90},
      "verifiedstats": {"pick": {"all_time": {"runs": 3, "score_sum": 270}}},
      "usagestats": {"pick": {"all_time": {"runs": 5}}},
      "extra_field": {"keep": true}
    }
  ]
}
EOF
before="$(kept_fields "$FIX/$REGISTRY" opencode_foo)"
rc=0
run_refresh > "$FIX/refresh.log" || rc=$?
assert_exit_zero_rc "refresh exits 0" "$rc"
assert_eq "non-generated fields unchanged" "$before" "$(kept_fields "$FIX/$REGISTRY" opencode_foo)"
assert_eq "usagestats kept" "5" "$(field "$FIX/$REGISTRY" opencode_foo '.usagestats.pick.all_time.runs')"
assert_eq "notes regenerated from discovery" "Foo New (200k context, opencode provider)" \
    "$(field "$FIX/$REGISTRY" opencode_foo '.notes')"
rc=0; cmp -s "$FIX/$REGISTRY" "$FIX/seed/models_opencode.json" || rc=$?
assert_exit_zero_rc "seed is a byte copy" "$rc"
rm -rf "$FIX"

# --- Test 2: a row matched by cli_id under a new name keeps its counters ---
echo "=== Test 2: renamed row (matched by cli_id) keeps usagestats ==="
setup_fixture "$LISTING_FOO"
cat > "$FIX/$REGISTRY" <<'EOF'
{
  "models": [
    {
      "name": "legacy_foo_name",
      "cli_id": "opencode/foo",
      "notes": "Foo",
      "status": "active",
      "verified": {"pick": 70},
      "verifiedstats": {},
      "usagestats": {"pick": {"all_time": {"runs": 2}}}
    }
  ]
}
EOF
rc=0
run_refresh > "$FIX/refresh.log" || rc=$?
assert_exit_zero_rc "refresh exits 0" "$rc"
assert_eq "row takes the discovered name" "opencode/foo" "$(field "$FIX/$REGISTRY" opencode_foo '.cli_id')"
assert_eq "renamed row keeps usagestats" "2" "$(field "$FIX/$REGISTRY" opencode_foo '.usagestats.pick.all_time.runs')"
assert_eq "renamed row keeps verified" "70" "$(field "$FIX/$REGISTRY" opencode_foo '.verified.pick')"
assert_eq "old name is gone" "" "$(field "$FIX/$REGISTRY" legacy_foo_name '.name')"
rm -rf "$FIX"

# --- Test 3: a rediscovered unavailable row reactivates with its counters ---
echo "=== Test 3: unavailable row comes back active, counters kept ==="
setup_fixture "$LISTING_FOO"
cat > "$FIX/$REGISTRY" <<'EOF'
{
  "models": [
    {
      "name": "opencode_foo",
      "cli_id": "opencode/foo",
      "notes": "Foo",
      "status": "unavailable",
      "verified": {"pick": 60},
      "verifiedstats": {},
      "usagestats": {"pick": {"all_time": {"runs": 9}}}
    }
  ]
}
EOF
rc=0
run_refresh > "$FIX/refresh.log" || rc=$?
assert_exit_zero_rc "refresh exits 0" "$rc"
assert_eq "status regenerated to active" "active" "$(field "$FIX/$REGISTRY" opencode_foo '.status')"
assert_eq "usagestats kept on reactivation" "9" "$(field "$FIX/$REGISTRY" opencode_foo '.usagestats.pick.all_time.runs')"
rm -rf "$FIX"

# --- Test 4: a usage write landing during discovery is not erased ---
echo "=== Test 4: concurrent usage write during discovery survives ==="
# The hook runs inside `opencode models --verbose`, i.e. after any pre-run
# snapshot and before the merge reads the registry — the window a snapshot
# check cannot see.
setup_fixture "$LISTING_FOO" "cd \"\$(dirname \"\$0\")\" && jq '(.models[] | select(.name == \"opencode_foo\")).usagestats = {\"pick\": {\"all_time\": {\"runs\": 1}}}' $REGISTRY > reg.tmp && mv reg.tmp $REGISTRY"
cat > "$FIX/$REGISTRY" <<'EOF'
{
  "models": [
    {
      "name": "opencode_foo",
      "cli_id": "opencode/foo",
      "notes": "Foo",
      "status": "active",
      "verified": {"pick": 0},
      "verifiedstats": {}
    }
  ]
}
EOF
rc=0
run_refresh > "$FIX/refresh.log" || rc=$?
assert_exit_zero_rc "refresh exits 0" "$rc"
assert_eq "mid-discovery usage count kept in metadata" "1" \
    "$(field "$FIX/$REGISTRY" opencode_foo '.usagestats.pick.all_time.runs')"
assert_eq "mid-discovery usage count kept in seed" "1" \
    "$(field "$FIX/seed/models_opencode.json" opencode_foo '.usagestats.pick.all_time.runs')"
rm -rf "$FIX"

# --- Test 5: a null existing field still falls back to the discovered default ---
echo "=== Test 5: verified: null falls back to the discovered default ==="
setup_fixture "$LISTING_FOO"
cat > "$FIX/$REGISTRY" <<'EOF'
{
  "models": [
    {
      "name": "opencode_foo",
      "cli_id": "opencode/foo",
      "notes": "Foo",
      "status": "active",
      "verified": null
    }
  ]
}
EOF
rc=0
run_refresh > "$FIX/refresh.log" || rc=$?
assert_exit_zero_rc "refresh exits 0" "$rc"
assert_eq "verified defaulted" "0" "$(field "$FIX/$REGISTRY" opencode_foo '.verified.pick')"
assert_eq "verifiedstats defaulted" "{}" "$(field "$FIX/$REGISTRY" opencode_foo '.verifiedstats | tojson')"
rm -rf "$FIX"

# --- Tests 6-8: writes landing AFTER the merge read the registry (t1928) ---
# AIT_CAS_BEFORE_SWAP_HOOK (lib/registry_cas.sh) runs after the merge rendered
# its result and before the swap — the window Test 4's discovery hook cannot
# reach. Its cwd is the fixture root, and AIT_CAS_DEST names the registry.

REGISTRY_FOO_V0='{
  "models": [
    {
      "name": "opencode_foo",
      "cli_id": "opencode/foo",
      "notes": "Foo",
      "status": "active",
      "verified": {"pick": 0},
      "verifiedstats": {}
    }
  ]
}'

echo "=== Test 6: a usage write between merge and swap is re-merged, not erased ==="
setup_fixture "$LISTING_FOO"
printf '%s\n' "$REGISTRY_FOO_V0" > "$FIX/$REGISTRY"
cat > "$FIX/swap_hook.sh" <<'EOF'
if [[ "$AIT_CAS_ATTEMPT" == 1 ]]; then
    jq '(.models[] | select(.name == "opencode_foo")).usagestats = {"pick": {"all_time": {"runs": 7}}}' \
        "$AIT_CAS_DEST" > reg.tmp && mv reg.tmp "$AIT_CAS_DEST"
fi
EOF
rc=0
AIT_CAS_BEFORE_SWAP_HOOK="$FIX/swap_hook.sh" run_refresh > "$FIX/refresh.log" || rc=$?
assert_exit_zero_rc "refresh exits 0" "$rc"
assert_eq "post-merge usage count kept in metadata" "7" \
    "$(field "$FIX/$REGISTRY" opencode_foo '.usagestats.pick.all_time.runs')"
assert_eq "post-merge usage count kept in seed" "7" \
    "$(field "$FIX/seed/models_opencode.json" opencode_foo '.usagestats.pick.all_time.runs')"
assert_eq "notes still regenerated" "Foo New (200k context, opencode provider)" \
    "$(field "$FIX/$REGISTRY" opencode_foo '.notes')"
assert_contains "re-merge reported" "re-merged" "$(cat "$FIX/refresh.log")"
rm -rf "$FIX"

echo "=== Test 7: a registry that never settles fails closed ==="
setup_fixture "$LISTING_FOO"
printf '%s\n' "$REGISTRY_FOO_V0" > "$FIX/$REGISTRY"
cat > "$FIX/swap_hook.sh" <<'EOF'
jq --argjson n "$AIT_CAS_ATTEMPT" \
    '(.models[] | select(.name == "opencode_foo")).usagestats = {"pick": {"all_time": {"runs": $n}}}' \
    "$AIT_CAS_DEST" > reg.tmp && mv reg.tmp "$AIT_CAS_DEST"
EOF
rc=0
AIT_CAS_BEFORE_SWAP_HOOK="$FIX/swap_hook.sh" run_refresh > "$FIX/refresh.log" || rc=$?
assert_eq "refresh exits non-zero" "1" "$([[ $rc -ne 0 ]] && echo 1 || echo 0)"
assert_contains "refusal says nothing was written" "Nothing was written" "$(cat "$FIX/refresh.log")"
assert_eq "registry notes not regenerated (refresh output never swapped in)" "Foo" \
    "$(field "$FIX/$REGISTRY" opencode_foo '.notes')"
assert_eq "registry keeps the concurrent writer's last value" "5" \
    "$(field "$FIX/$REGISTRY" opencode_foo '.usagestats.pick.all_time.runs')"
assert_file_not_exists "seed not synced" "$FIX/seed/models_opencode.json"
rm -rf "$FIX"

echo "=== Test 8: a registry created mid-run is merged, not overwritten ==="
setup_fixture "$LISTING_FOO"
cat > "$FIX/swap_hook.sh" <<'EOF'
if [[ "$AIT_CAS_ATTEMPT" == 1 ]]; then
    cat > "$AIT_CAS_DEST" <<'JSON'
{"models": [{"name": "opencode_foo", "cli_id": "opencode/foo", "notes": "Foo", "status": "active",
  "verified": {"pick": 0}, "verifiedstats": {}, "usagestats": {"pick": {"all_time": {"runs": 3}}}}]}
JSON
fi
EOF
rc=0
AIT_CAS_BEFORE_SWAP_HOOK="$FIX/swap_hook.sh" run_refresh > "$FIX/refresh.log" || rc=$?
assert_exit_zero_rc "refresh exits 0" "$rc"
assert_eq "usagestats from the mid-run registry kept" "3" \
    "$(field "$FIX/$REGISTRY" opencode_foo '.usagestats.pick.all_time.runs')"
assert_eq "notes regenerated" "Foo New (200k context, opencode provider)" \
    "$(field "$FIX/$REGISTRY" opencode_foo '.notes')"
rm -rf "$FIX"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
