#!/usr/bin/env bash
# test_registry_cas.sh - ait_cas_rewrite (lib/registry_cas.sh) swaps a rendered
# file in only while the target still matches the snapshot it rendered from
# (t1928).
#
# The concurrent writer is simulated deterministically through the lib's
# AIT_CAS_BEFORE_SWAP_HOOK seam, which runs after the render and before the
# compare — the window a plain read-modify-write loses a write in. Every case
# runs under a private TMPDIR so a leaked snapshot dir is detectable, and checks
# the target's directory for leaked staging temps.
#
# REGISTRY_CAS_LIB overrides the lib under test (used for the negative-control
# mutant). Run: bash tests/test_registry_cas.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LIB_UNDER_TEST="${REGISTRY_CAS_LIB:-$PROJECT_DIR/.aitask-scripts/lib/registry_cas.sh}"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

# The lib sources atomic_write.sh from its own directory, so stage both side by
# side (lets the mutant run from a scratch copy).
LIBDIR="$(mktemp -d)"
cp "$PROJECT_DIR/.aitask-scripts/lib/atomic_write.sh" "$LIBDIR/"
cp "$LIB_UNDER_TEST" "$LIBDIR/registry_cas.sh"
# shellcheck source=/dev/null
. "$LIBDIR/registry_cas.sh"

# Fresh work dir + private TMPDIR per case.
setup_case() {
    CASE="$(mktemp -d)"
    mkdir -p "$CASE/tmp" "$CASE/data"
    DEST="$CASE/data/reg.json"
    HOOK="$CASE/hook.sh"
    export TMPDIR="$CASE/tmp"
}

teardown_case() {
    unset AIT_CAS_BEFORE_SWAP_HOOK
    export TMPDIR=/tmp
    rm -rf "$CASE"
}

# Render: increment .n of the snapshot (an absent snapshot starts from 0).
render_inc() {
    if [[ -z "$1" ]]; then
        jq -n '{"n": 1}' || return 1
    else
        jq '.n += 1' "$1" || return 1
    fi
}

render_fail() {
    return 1
}

leftovers() {
    # Staging temps beside the target are dot-prefixed `.reg.json.XXXXXX`.
    find "$CASE/data" -name '.reg.json.*' | wc -l | tr -d ' '
}

tmp_entries() {
    find "$CASE/tmp" -mindepth 1 | wc -l | tr -d ' '
}

# --- (a) unchanged target swaps on the first attempt ---
echo "=== (a) unchanged target: swapped, one attempt, nothing left behind ==="
setup_case
echo '{"n": 0}' > "$DEST"
rc=0; ait_cas_rewrite "$DEST" 5 render_inc || rc=$?
assert_eq "rc 0" "0" "$rc"
assert_eq "rendered value swapped in" "1" "$(jq -r .n "$DEST")"
assert_eq "one attempt" "1" "$AIT_CAS_ATTEMPTS"
assert_eq "no staging temp beside target" "0" "$(leftovers)"
assert_eq "no snapshot dir left in TMPDIR" "0" "$(tmp_entries)"
teardown_case

# --- (b) a write landing between render and swap is re-applied, not erased ---
echo "=== (b) concurrent write on attempt 1: re-rendered from the fresh content ==="
setup_case
echo '{"n": 0}' > "$DEST"
cat > "$HOOK" <<'EOF'
if [[ "$AIT_CAS_ATTEMPT" == 1 ]]; then
    printf '{"n": 100}\n' > "$AIT_CAS_DEST"
fi
EOF
export AIT_CAS_BEFORE_SWAP_HOOK="$HOOK"
rc=0; ait_cas_rewrite "$DEST" 5 render_inc || rc=$?
assert_eq "rc 0" "0" "$rc"
assert_eq "concurrent write kept and incremented (100 + 1)" "101" "$(jq -r .n "$DEST")"
assert_eq "two attempts" "2" "$AIT_CAS_ATTEMPTS"
assert_eq "no staging temp beside target" "0" "$(leftovers)"
teardown_case

# --- (c) a target that never settles fails closed ---
echo "=== (c) target changes on every attempt: rc 2, nothing of ours written ==="
setup_case
echo '{"n": 0}' > "$DEST"
cat > "$HOOK" <<'EOF'
printf '{"n": %s, "by": "hook"}\n' "$((AIT_CAS_ATTEMPT * 1000))" > "$AIT_CAS_DEST"
EOF
export AIT_CAS_BEFORE_SWAP_HOOK="$HOOK"
rc=0; ait_cas_rewrite "$DEST" 3 render_inc || rc=$?
assert_eq "rc 2" "2" "$rc"
assert_eq "target holds the concurrent writer's last value" "3000" "$(jq -r .n "$DEST")"
assert_eq "target is the concurrent writer's file, not ours" "hook" "$(jq -r .by "$DEST")"
assert_eq "all attempts used" "3" "$AIT_CAS_ATTEMPTS"
assert_eq "no staging temp beside target" "0" "$(leftovers)"
assert_eq "no snapshot dir left in TMPDIR" "0" "$(tmp_entries)"
teardown_case

# --- (d) a failing render leaves the target byte-identical ---
echo "=== (d) render failure: rc 1, target untouched ==="
setup_case
echo '{"n": 7}' > "$DEST"
cp "$DEST" "$CASE/before.json"
rc=0; ait_cas_rewrite "$DEST" 5 render_fail || rc=$?
assert_eq "rc 1" "1" "$rc"
rc=0; cmp -s "$CASE/before.json" "$DEST" || rc=$?
assert_eq "target byte-identical" "0" "$rc"
assert_eq "one attempt (no retry on a render failure)" "1" "$AIT_CAS_ATTEMPTS"
assert_eq "no staging temp beside target" "0" "$(leftovers)"
assert_eq "no snapshot dir left in TMPDIR" "0" "$(tmp_entries)"
teardown_case

# --- (e) absent target: created; created concurrently: retried from it ---
echo "=== (e1) absent target is created ==="
setup_case
rc=0; ait_cas_rewrite "$DEST" 5 render_inc || rc=$?
assert_eq "rc 0" "0" "$rc"
assert_eq "created from an empty start" "1" "$(jq -r .n "$DEST")"
teardown_case

echo "=== (e2) absent target created by a concurrent writer: retried from it ==="
setup_case
cat > "$HOOK" <<'EOF'
if [[ "$AIT_CAS_ATTEMPT" == 1 ]]; then
    printf '{"n": 50}\n' > "$AIT_CAS_DEST"
fi
EOF
export AIT_CAS_BEFORE_SWAP_HOOK="$HOOK"
rc=0; ait_cas_rewrite "$DEST" 5 render_inc || rc=$?
assert_eq "rc 0" "0" "$rc"
assert_eq "concurrent creation kept and incremented (50 + 1)" "51" "$(jq -r .n "$DEST")"
assert_eq "two attempts" "2" "$AIT_CAS_ATTEMPTS"
teardown_case

rm -rf "$LIBDIR"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
