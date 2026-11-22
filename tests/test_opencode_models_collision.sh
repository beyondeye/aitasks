#!/usr/bin/env bash
# test_opencode_models_collision.sh - aitask_opencode_models.sh refuses any run
# whose merge would fold two models into one row, and seeds only from the
# registry bytes its guards checked (t1885).
#
# convert_to_model_name is not injective (opencode/foo-bar and opencode/foo.bar
# both derive opencode_foo_bar), merge_with_existing selects rows through
# `add`-built name/cli_id maps that keep the last of a repeated key, and the
# aitask-stats history is keyed by name. The row-identity guard refuses:
#   (a) a name repeated in the discovered set, (b) a name repeated in the
#   registry, (c) a name on both sides with different cli_ids, (d) a cli_id
#   repeated in the registry.
# Every refusal leaves the registry byte-identical and writes no seed.
#
# Runs the real script against a stub `opencode` on PATH. OPENCODE_MODELS_SCRIPT
# overrides the script under test (the pre-fix negative control). Post-swap
# changes are injected by a fixture-local `jq` wrapper that runs $FIX/inject.sh
# once when the seed strip (model_stats_strip.jq) starts — no seam in the script.
# Run: bash tests/test_opencode_models_collision.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
abs_path() { case "$1" in /*) printf '%s\n' "$1" ;; *) printf '%s\n' "$PWD/$1" ;; esac; }
SCRIPT_UNDER_TEST="$(abs_path "${OPENCODE_MODELS_SCRIPT:-$PROJECT_DIR/.aitask-scripts/aitask_opencode_models.sh}")"
# ATOMIC_WRITE_LIB overrides lib/atomic_write.sh (a negative control for the
# check-before-rename ordering).
ATOMIC_LIB_UNDER_TEST="$(abs_path "${ATOMIC_WRITE_LIB:-$PROJECT_DIR/.aitask-scripts/lib/atomic_write.sh}")"
# The warning-only assertions describe the fixed script; the pre-fix control
# never prints them.
FIXED_SCRIPT=true
[[ -n "${OPENCODE_MODELS_SCRIPT:-}" ]] && FIXED_SCRIPT=false

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

REAL_JQ="$(command -v jq)"
REAL_MKTEMP="$(command -v mktemp)"
REAL_MV="$(command -v mv)"
STRIP_JQ="$PROJECT_DIR/.aitask-scripts/lib/model_stats_strip.jq"
REGISTRY="aitasks/metadata/models_opencode.json"
SEED="seed/models_opencode.json"

# listing <cli_id>... — canned `opencode models --verbose` output.
listing() {
    local id
    for id in "$@"; do
        printf '%s\n{\n  "name": "%s"\n}\n' "$id" "$id"
    done
}

# setup_fixture <listing> — a throwaway project with the script, its libs, a
# stub opencode (reads $LISTING_FILE, default listing.txt) and the jq wrapper.
setup_fixture() {
    FIX="$(mktemp -d)"
    mkdir -p "$FIX/.aitask-scripts/lib" "$FIX/bin" "$FIX/aitasks/metadata" "$FIX/seed"
    cp "$SCRIPT_UNDER_TEST" "$FIX/.aitask-scripts/aitask_opencode_models.sh"
    local lib
    for lib in terminal_compat.sh registry_cas.sh model_stats_strip.jq; do
        cp "$PROJECT_DIR/.aitask-scripts/lib/$lib" "$FIX/.aitask-scripts/lib/"
    done
    cp "$ATOMIC_LIB_UNDER_TEST" "$FIX/.aitask-scripts/lib/atomic_write.sh"
    printf '%s' "$1" > "$FIX/listing.txt"
    cat > "$FIX/bin/opencode" <<'EOF'
#!/usr/bin/env bash
cat "${LISTING_FILE:-$FIXTURE_DIR/listing.txt}"
EOF
    # Injection points for $FIX/inject.sh, one-shot (inject.done), selected by
    # INJECT_AT: "strip" (default) — when the seed strip (model_stats_strip.jq)
    # starts, via the jq wrapper; "stage" — right after the seed's staging temp
    # is created (the content is not yet written, the rename not yet done), via
    # the mktemp wrapper; "probe" — at the rename-mode probe, via the mv
    # wrapper below. INJECT_ACTIVE stops a refresh run by inject.sh from
    # injecting again.
    cat > "$FIX/bin/jq" <<'EOF'
#!/usr/bin/env bash
if [[ "${INJECT_AT:-strip}" == strip && -z "${INJECT_ACTIVE:-}" && -f "$FIXTURE_DIR/inject.sh" && ! -e "$FIXTURE_DIR/inject.done" ]]; then
    for arg in "$@"; do
        case "$arg" in
            */model_stats_strip.jq)
                : > "$FIXTURE_DIR/inject.done"
                INJECT_ACTIVE=1 bash "$FIXTURE_DIR/inject.sh" >&2
                break ;;
        esac
    done
fi
exec "$REAL_JQ" "$@"
EOF
    # mktemp wrapper: logs every template so a test can see where the seed is
    # staged, and is the "stage" injection point (seed staging templates of
    # the fixed and of the pre-fix script).
    cat > "$FIX/bin/mktemp" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$FIXTURE_DIR/mktemp.log"
out="$("$REAL_MKTEMP" "$@")" || exit $?
if [[ "${INJECT_AT:-strip}" == stage && -z "${INJECT_ACTIVE:-}" && -f "$FIXTURE_DIR/inject.sh" && ! -e "$FIXTURE_DIR/inject.done" ]]; then
    case "$*" in
        */seed/.models_opencode.json.*|*aitask_opencode_seed_*)
            : > "$FIXTURE_DIR/inject.done"
            INJECT_ACTIVE=1 bash "$FIXTURE_DIR/inject.sh" >&2 ;;
    esac
fi
printf '%s\n' "$out"
EOF
    # mv wrapper: the "probe" injection point — the nofollow writer's
    # rename-mode probe (`mv --help`), the only --help call in a refresh.
    cat > "$FIX/bin/mv" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == --help && "${INJECT_AT:-strip}" == probe && -z "${INJECT_ACTIVE:-}" \
      && -f "$FIXTURE_DIR/inject.sh" && ! -e "$FIXTURE_DIR/inject.done" ]]; then
    : > "$FIXTURE_DIR/inject.done"
    INJECT_ACTIVE=1 bash "$FIXTURE_DIR/inject.sh" >&2
fi
exec "$REAL_MV" "$@"
EOF
    chmod +x "$FIX/bin/opencode" "$FIX/bin/jq" "$FIX/bin/mktemp" "$FIX/bin/mv"
}

# TASK_DIR is pinned: the script reads its registry from ${TASK_DIR:-aitasks},
# so an inherited TASK_DIR would point every refresh here (and the nested one in
# inject.sh, which inherits this environment) at a real registry.
run_refresh() {
    (cd "$FIX" && TASK_DIR=aitasks FIXTURE_DIR="$FIX" REAL_JQ="$REAL_JQ" REAL_MKTEMP="$REAL_MKTEMP" REAL_MV="$REAL_MV" PATH="$FIX/bin:$PATH" \
        bash ./.aitask-scripts/aitask_opencode_models.sh "$@" 2>&1)
}

# Isolation sentinel: an inherited TASK_DIR naming an outside registry must
# never be touched by any refresh below (checked at the end).
SENTINEL="$(mktemp -d)"
mkdir -p "$SENTINEL/metadata"
printf '%s\n' '{"models": [{"name": "opencode_sentinel", "cli_id": "opencode/sentinel", "notes": "s", "status": "active", "verified": {"pick": 1}}]}' \
    > "$SENTINEL/metadata/models_opencode.json"
cp "$SENTINEL/metadata/models_opencode.json" "$SENTINEL/snapshot.json"
export TASK_DIR="$SENTINEL"

# write_registry <json rows> — the registry with these rows.
write_registry() {
    "$REAL_JQ" -n --argjson rows "$1" '{models: $rows}' > "$FIX/$REGISTRY"
    cp "$FIX/$REGISTRY" "$FIX/snapshot.json"
}

row() { # row <name> <cli_id> [<verified.pick>]
    "$REAL_JQ" -nc --arg n "$1" --arg c "$2" --argjson p "${3:-0}" \
        '{name: $n, cli_id: $c, notes: $n, status: "active", verified: {pick: $p}}'
}

assert_registry_unchanged() {
    local rc=0
    cmp -s "$FIX/snapshot.json" "$FIX/$REGISTRY" || rc=$?
    assert_exit_zero_rc "$1: registry byte-identical" "$rc"
}

# --- Test 1: (a) two discovered models derive one name ---
echo "=== Test 1: discovered opencode/foo-bar + opencode/foo.bar are refused ==="
setup_fixture "$(listing opencode/foo-bar opencode/foo.bar)"
write_registry "[$(row opencode_baz opencode/baz 70)]"
rc=0; out=$(run_refresh --sync-seed) || rc=$?
assert_exit_nonzero_rc "T1 exits non-zero" "$rc"
assert_contains "T1 names the colliding pair" \
    "opencode_foo_bar: opencode/foo-bar (discovered), opencode/foo.bar (discovered)" "$out"
assert_contains "T1 gives the discovered-pair advice" "the naming scheme cannot tell these apart" "$out"
assert_not_contains "T1 gives no registry-row advice" "take over the name of a registry row" "$out"
assert_contains "T1 says nothing was written" "Nothing was written" "$out"
assert_registry_unchanged "T1"
assert_file_not_exists "T1 writes no seed" "$FIX/$SEED"
rm -rf "$FIX"

# --- Test 2: (c) a discovered model would take over a registry row's name ---
echo "=== Test 2: discovered opencode/foo-bar vs registry opencode_foo_bar=opencode/foo.bar ==="
setup_fixture "$(listing opencode/foo-bar)"
write_registry "[$("$REAL_JQ" -c '. + {verifiedstats: {pick: {all_time: {runs: 7, score_sum: 560}}}}' <<< "$(row opencode_foo_bar opencode/foo.bar 80)")]"
rc=0; out=$(run_refresh --sync-seed) || rc=$?
assert_exit_nonzero_rc "T2 exits non-zero" "$rc"
assert_contains "T2 names both sides" \
    "opencode_foo_bar: opencode/foo-bar (discovered), opencode/foo.bar (registry)" "$out"
assert_contains "T2 advises keeping the name" "keep its name" "$out"
assert_contains "T2 says renaming would not move the history" "would not move that history" "$out"
assert_not_contains_ci "T2 never advises renaming the row" "rename the row" "$out"
assert_not_contains "T2 does not reuse the reserved guard's rename advice" "rename or remove each listed row" "$out"
assert_registry_unchanged "T2"
assert_eq "T2 registry row keeps its verifiedstats" "7" \
    "$("$REAL_JQ" -r '.models[0].verifiedstats.pick.all_time.runs' "$FIX/$REGISTRY")"
assert_file_not_exists "T2 writes no seed" "$FIX/$SEED"
rm -rf "$FIX"

# --- Test 3: (b) two registry rows share a name, different cli_ids ---
echo "=== Test 3: registry rows opencode_foo=opencode/foo and opencode_foo=opencode/fooz ==="
setup_fixture "$(listing opencode/bar)"
write_registry "[$(row opencode_foo opencode/foo 90), $(row opencode_foo opencode/fooz 40)]"
rc=0; out=$(run_refresh --sync-seed) || rc=$?
assert_exit_nonzero_rc "T3 exits non-zero" "$rc"
assert_contains "T3 lists the duplicate name" "opencode_foo: opencode/foo (registry), opencode/fooz (registry)" "$out"
assert_contains "T3 advises leaving both rows in place" "leave these rows in place" "$out"
assert_contains "T3 forbids deleting before reconciling" "Do not delete either one" "$out"
assert_registry_unchanged "T3"
rm -rf "$FIX"

# --- Test 3b: (b) same name AND same cli_id, unequal verified scores ---
echo "=== Test 3b: two opencode_foo=opencode/foo rows (pick 90 / 40), rediscovered ==="
setup_fixture "$(listing opencode/foo)"
write_registry "[$(row opencode_foo opencode/foo 90), $(row opencode_foo opencode/foo 40)]"
rc=0; out=$(run_refresh --sync-seed) || rc=$?
assert_exit_nonzero_rc "T3b exits non-zero (pre-fix silently keeps one score)" "$rc"
assert_contains "T3b lists the duplicate rows" "opencode_foo: opencode/foo (registry), opencode/foo (registry)" "$out"
assert_registry_unchanged "T3b"
assert_eq "T3b both scores survive" "40,90" \
    "$("$REAL_JQ" -r '[.models[].verified.pick] | sort | map(tostring) | join(",")' "$FIX/$REGISTRY")"
rm -rf "$FIX"

# --- Test 3c: (d) one cli_id under two registry names ---
echo "=== Test 3c: registry legacy_foo=opencode/foo and opencode_foo=opencode/foo ==="
setup_fixture "$(listing opencode/foo)"
write_registry "[$(row legacy_foo opencode/foo 60), $(row opencode_foo opencode/foo 30)]"
rc=0; out=$(run_refresh --sync-seed) || rc=$?
assert_exit_nonzero_rc "T3c exits non-zero" "$rc"
assert_contains "T3c lists the duplicate cli_id" "opencode/foo: legacy_foo (registry), opencode_foo (registry)" "$out"
assert_registry_unchanged "T3c"
rm -rf "$FIX"

# --- Test 4: --dry-run is guarded too ---
echo "=== Test 4: --dry-run refuses a discovered collision ==="
setup_fixture "$(listing opencode/foo-bar opencode/foo_bar)"
rc=0; out=$(run_refresh --dry-run) || rc=$?
assert_exit_nonzero_rc "T4 dry-run exits non-zero" "$rc"
assert_contains "T4 dry-run names the collision" "opencode_foo_bar" "$out"
assert_not_contains "T4 dry-run shows no plan" "[ACTIVE]" "$out"
rm -rf "$FIX"

# --- Test 5: a colliding row lands inside the CAS window ---
echo "=== Test 5: a conflicting row written between the pre-check and the swap ==="
setup_fixture "$(listing opencode/foo)"
write_registry "[$(row opencode_foo opencode/foo 50)]"
cat > "$FIX/swap_hook.sh" <<EOF
[[ "\${AIT_CAS_ATTEMPT:-1}" == 1 ]] || exit 0
"$REAL_JQ" '.models += [{"name": "opencode_foo", "cli_id": "opencode/other", "notes": "x"}]' \
    "$FIX/$REGISTRY" > "$FIX/hooked.json" && cp "$FIX/hooked.json" "$FIX/$REGISTRY"
EOF
rc=0; out=$(AIT_CAS_BEFORE_SWAP_HOOK="$FIX/swap_hook.sh" run_refresh --sync-seed) || rc=$?
assert_exit_nonzero_rc "T5 exits non-zero" "$rc"
# The injected row duplicates opencode_foo inside the registry: class (b).
assert_contains "T5 re-render refuses the collision" \
    "opencode_foo: opencode/foo (registry), opencode/other (registry)" "$out"
rc=0; cmp -s "$FIX/hooked.json" "$FIX/$REGISTRY" || rc=$?
assert_exit_zero_rc "T5 registry left as the concurrent writer wrote it" "$rc"
assert_file_not_exists "T5 writes no seed" "$FIX/$SEED"
rm -rf "$FIX"

# --- Test 5b: changes landing after the swap, while the seed renders ---
echo "=== Test 5b-1: a conflicting row injected after the swap never reaches the seed ==="
setup_fixture "$(listing opencode/foo)"
write_registry "[$(row opencode_foo opencode/foo 50)]"
cat > "$FIX/inject.sh" <<EOF
"$REAL_JQ" '.models += [{"name": "opencode_foo", "cli_id": "opencode/other", "notes": "x"}]' \
    "$FIX/$REGISTRY" > "$FIX/injected.json" && cp "$FIX/injected.json" "$FIX/$REGISTRY"
EOF
rc=0; out=$(run_refresh --sync-seed) || rc=$?
assert_exit_zero_rc "T5b-1 the checked registry write succeeds" "$rc"
assert_file_exists "T5b-1 the injection ran" "$FIX/inject.done"
if [[ -f "$FIX/$SEED" ]]; then seed_ids="$("$REAL_JQ" -r '[.models[].cli_id] | join(",")' "$FIX/$SEED")"; else seed_ids=""; fi
assert_not_contains "T5b-1 seed never carries the unchecked row" "opencode/other" "$seed_ids"
if [[ "$FIXED_SCRIPT" == true ]]; then
    assert_file_not_exists "T5b-1 seed not written once the registry diverged" "$FIX/$SEED"
    assert_contains "T5b-1 says the seed was not synced" "not synced; re-run with --sync-seed" "$out"
fi
rm -rf "$FIX"

echo "=== Test 5b-2: a newer complete refresh is not overwritten by the older one ==="
setup_fixture "$(listing opencode/foo)"
write_registry "[$(row opencode_foo opencode/foo 50)]"
listing opencode/foo opencode/newer > "$FIX/listing_newer.txt"
cat > "$FIX/inject.sh" <<EOF
cd "$FIX" && LISTING_FILE="$FIX/listing_newer.txt" \
    bash ./.aitask-scripts/aitask_opencode_models.sh --sync-seed
EOF
rc=0; out=$(run_refresh --sync-seed) || rc=$?
assert_exit_zero_rc "T5b-2 older refresh exits 0" "$rc"
assert_file_exists "T5b-2 the newer refresh ran" "$FIX/inject.done"
# Shared file assertions: hold for the pre-fix script (re-reads the live file)
# and for the fixed one (skips the seed); they pin that the checked-bytes seed
# never rolls the newer seed back.
assert_eq "T5b-2 registry holds the newer models" "opencode/foo,opencode/newer" \
    "$("$REAL_JQ" -r '[.models[].cli_id] | sort | join(",")' "$FIX/$REGISTRY")"
assert_eq "T5b-2 seed matches the live registry" \
    "$("$REAL_JQ" -S -f "$STRIP_JQ" "$FIX/$REGISTRY")" "$("$REAL_JQ" -S . "$FIX/$SEED" 2>/dev/null)"
if [[ "$FIXED_SCRIPT" == true ]]; then
    assert_contains "T5b-2 older run reports the skip" "not synced; re-run with --sync-seed" "$out"
fi
rm -rf "$FIX"

# T5b-3 (stage): the newer refresh completes right after the seed's staging
# temp is created. T5b-4 (probe): it completes during the writer's rename-mode
# probe — which must run before the check, never between check and rename.
for point in stage probe; do
    tag="T5b-3"; [[ "$point" == probe ]] && tag="T5b-4"
    echo "=== Test $tag: a newer refresh completing at the seed writer's $point point is not rolled back ==="
    setup_fixture "$(listing opencode/foo)"
    write_registry "[$(row opencode_foo opencode/foo 50)]"
    listing opencode/foo opencode/newer > "$FIX/listing_newer.txt"
    cat > "$FIX/inject.sh" <<EOF
cd "$FIX" && LISTING_FILE="$FIX/listing_newer.txt" \
    bash ./.aitask-scripts/aitask_opencode_models.sh --sync-seed
EOF
    # The probe point exists only when the writer actually probes:
    # AIT_ATOMIC_PORTABLE_MV short-circuits ait_atomic_nofollow_native before
    # `mv --help`, so an inherited override is cleared for this case alone.
    portable_mv="${AIT_ATOMIC_PORTABLE_MV:-}"
    [[ "$point" == probe ]] && portable_mv=""
    rc=0; out=$(AIT_ATOMIC_PORTABLE_MV="$portable_mv" INJECT_AT="$point" run_refresh --sync-seed) || rc=$?
    assert_exit_zero_rc "$tag older refresh exits 0" "$rc"
    # The pre-fix script has no probe (plain mv), so the probe point never fires.
    if [[ "$FIXED_SCRIPT" == true || "$point" == stage ]]; then
        assert_file_exists "$tag the newer refresh ran at the $point point" "$FIX/inject.done"
    fi
    # Shared file assertions (pre-fix and fixed alike): the newer registry and
    # its seed both survive.
    assert_eq "$tag registry holds the newer models" "$( [[ -e "$FIX/inject.done" ]] && echo opencode/foo,opencode/newer || echo opencode/foo)" \
        "$("$REAL_JQ" -r '[.models[].cli_id] | sort | join(",")' "$FIX/$REGISTRY")"
    assert_eq "$tag seed matches the live registry" \
        "$("$REAL_JQ" -S -f "$STRIP_JQ" "$FIX/$REGISTRY")" "$("$REAL_JQ" -S . "$FIX/$SEED" 2>/dev/null)"
    if [[ "$FIXED_SCRIPT" == true ]]; then
        assert_contains "$tag older run reports the skip" "not synced; re-run with --sync-seed" "$out"
    fi
    rm -rf "$FIX"
done

# --- Test 6: positive controls ---
echo "=== Test 6a: one matching row per side refreshes normally ==="
setup_fixture "$(listing opencode/foo-bar opencode/baz)"
write_registry "[$(row opencode_foo_bar opencode/foo-bar 75)]"
rc=0; out=$(run_refresh --sync-seed) || rc=$?
assert_exit_zero_rc "T6a exits 0" "$rc"
assert_eq "T6a verified carried" "75" \
    "$("$REAL_JQ" -r '.models[] | select(.name == "opencode_foo_bar") | .verified.pick' "$FIX/$REGISTRY")"
assert_eq "T6a seed matches the registry" \
    "$("$REAL_JQ" -S -f "$STRIP_JQ" "$FIX/$REGISTRY")" "$("$REAL_JQ" -S . "$FIX/$SEED" 2>/dev/null)"
rm -rf "$FIX"

echo "=== Test 6c: the seed is staged beside its destination, not in TMPDIR ==="
# A rename from TMPDIR degrades into a non-atomic copy when TMPDIR is on another
# filesystem. The fixture's mktemp wrapper logs every template.
setup_fixture "$(listing opencode/foo)"
write_registry "[$(row opencode_foo opencode/foo 50)]"
rc=0; out=$(run_refresh --sync-seed) || rc=$?
assert_exit_zero_rc "T6c exits 0" "$rc"
assert_contains "T6c the seed is staged beside its destination" \
    "$FIX/seed/.models_opencode.json." "$(cat "$FIX/mktemp.log" 2>/dev/null)"
assert_not_contains "T6c the seed is never staged in TMPDIR" \
    "aitask_opencode_seed_" "$(cat "$FIX/mktemp.log" 2>/dev/null)"
assert_eq "T6c no staging temp left behind" "" \
    "$(find "$FIX/seed" -name '.models_opencode.json.*' -print)"
assert_eq "T6c seed matches the registry" \
    "$("$REAL_JQ" -S -f "$STRIP_JQ" "$FIX/$REGISTRY")" "$("$REAL_JQ" -S . "$FIX/$SEED" 2>/dev/null)"
rm -rf "$FIX"

echo "=== Test 6e: a seed symlink is replaced, never followed into its target ==="
# A seed linked to the live registry: following the link would overwrite the
# registry with the stripped seed and drop its counters.
setup_fixture "$(listing opencode/foo)"
write_registry "[$("$REAL_JQ" -c '. + {verifiedstats: {pick: {all_time: {runs: 4, score_sum: 200}}}}' <<< "$(row opencode_foo opencode/foo 50)")]"
ln -s "../$REGISTRY" "$FIX/$SEED"
rc=0; out=$(run_refresh --sync-seed) || rc=$?
assert_exit_zero_rc "T6e exits 0" "$rc"
assert_eq "T6e live registry keeps its verifiedstats" "4" \
    "$("$REAL_JQ" -r '.models[0].verifiedstats.pick.all_time.runs' "$FIX/$REGISTRY")"
rc=0; [[ -L "$FIX/$SEED" ]] || rc=1
assert_exit_nonzero_rc "T6e the seed link was replaced by a regular file" "$rc"
assert_eq "T6e seed carries no stats counters" "null" \
    "$("$REAL_JQ" -r '.models[0].verifiedstats' "$FIX/$SEED")"
rm -rf "$FIX"

echo "=== Test 6d: a large registry (2400 unavailable rows) still refreshes ==="
# The guard reads the registry as a jq file input; passed as one argv string it
# would exceed the per-argument limit ("Argument list too long").
setup_fixture "$(listing opencode/foo)"
"$REAL_JQ" -n '{models: ([range(2400) | {name: "opencode_old_\(.)", cli_id: "opencode/old-\(.)",
    notes: "an old model that is no longer offered by any connected provider \(.)",
    status: "unavailable", verified: {pick: 0}}] + [{name: "opencode_foo", cli_id: "opencode/foo",
    notes: "Foo", status: "active", verified: {pick: 50}}])}' > "$FIX/$REGISTRY"
reg_bytes=$(wc -c < "$FIX/$REGISTRY")
rc=0; out=$(run_refresh --sync-seed) || rc=$?
assert_exit_zero_rc "T6d exits 0 (registry is $reg_bytes bytes)" "$rc"
assert_not_contains "T6d no argument-length failure" "Argument list too long" "$out"
assert_eq "T6d every row survives" "2401" "$("$REAL_JQ" '.models | length' "$FIX/$REGISTRY")"
rm -rf "$FIX"

echo "=== Test 6b: the cli_id-keyed rename is not a collision ==="
setup_fixture "$(listing opencode/foo-bar)"
write_registry "[$(row legacy_foo_bar opencode/foo-bar 65)]"
rc=0; out=$(run_refresh --sync-seed) || rc=$?
assert_exit_zero_rc "T6b exits 0" "$rc"
assert_eq "T6b row takes the derived name and keeps verified" "65" \
    "$("$REAL_JQ" -r '.models[] | select(.name == "opencode_foo_bar") | .verified.pick' "$FIX/$REGISTRY")"
assert_eq "T6b old name is gone" "0" \
    "$("$REAL_JQ" -r '[.models[] | select(.name == "legacy_foo_bar")] | length' "$FIX/$REGISTRY")"
rm -rf "$FIX"

echo "=== Isolation: the inherited TASK_DIR registry was never touched ==="
rc=0; cmp -s "$SENTINEL/snapshot.json" "$SENTINEL/metadata/models_opencode.json" || rc=$?
assert_exit_zero_rc "outside registry named by the inherited TASK_DIR is byte-identical" "$rc"
rm -rf "$SENTINEL"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
