#!/usr/bin/env bash
# test_gate_lock_single_winner.sh - Production concurrency integration test for
# the gate mutex (t1496), end-to-end through aitask_gate.sh append.
#
# Pins the two behaviors HEAD provably lacked (RED reproduction recorded in
# aiplans p1496, pre-phase 1):
#   - a lock whose holder PID is alive is NEVER displaced, however old its
#     mtime — append exhausts and fails with the holder's lock intact;
#   - K contenders racing through one genuinely stale (tokenless, backdated)
#     lock serialize: exactly K ledger blocks, each attempt number exactly
#     once, exactly ONE reclaim, no lock left behind.
#
# Run: bash tests/test_gate_lock_single_winner.sh
# Expected runtime: ~10s (one ~6s exhaustion against the live holder).

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"

# Per-run lock namespace via the documented seam (t1496).
AITASKS_LOCK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/test_singlewinner_XXXXXX")"
export AITASKS_LOCK_DIR

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_sw_fixture_XXXXXX")"
HOLDER_PID=""
cleanup() {
    rm -rf "$TMP" "$AITASKS_LOCK_DIR"
    [[ -n "$HOLDER_PID" ]] && kill "$HOLDER_PID" 2>/dev/null
}
trap cleanup EXIT

# Fixture repo (same shape as tests/test_gate_lock_characterization.sh).
ID_BASE="9$$"
ID1="${ID_BASE}1"; ID2="${ID_BASE}2"
mkdir -p "$TMP/aitasks/metadata"
cat > "$TMP/aitasks/metadata/gates.yaml" <<'EOF'
gates:
  tests_pass:
    type: machine
    description: "Run project test suite; must all pass"
EOF
for id in "$ID1" "$ID2"; do
    cat > "$TMP/aitasks/t${id}_x.md" <<EOF
---
status: Implementing
gates: [tests_pass]
---
Body for t${id}.
EOF
done

run_gate() {
    ( cd "$TMP" && TASK_DIR=aitasks "$GATE" "$@" )
}

marker_count() {  # <id>
    grep -c 'gate:tests_pass' "$TMP/aitasks/t${1}_x.md"
}

lock_dir_for() { printf '%s/gate_%s' "$AITASKS_LOCK_DIR" "$1"; }

# ============================================================
echo "--- live holder: backdated lock with a live PID is never stolen (~6s) ---"
# ============================================================
# The regression pin for the recorded HEAD defect: HEAD judged staleness by
# mtime alone and displaced a live holder's lock (two holders in the critical
# section). Fixed code must fail this construction closed.
sleep 120 &
HOLDER_PID=$!
L1="$(lock_dir_for "$ID1")"
mkdir "$L1"
printf '%s\n' "$HOLDER_PID" > "$L1/pid"
printf '%s\n' "holders-own-token" > "$L1/owner"
touch -t 202001010000 "$L1"    # far past the 120s window: liveness must win

out="$(run_gate append "$ID1" tests_pass pass 2>&1)"; rc=$?
assert_exit_nonzero_rc "append against a live holder exhausts and fails" "$rc"
assert_contains "die carries the pinned exhaustion prefix" \
    "Failed to acquire gate append lock for ${ID1} after 20 attempts" "$out"
assert_contains "die hint names the holder pid" "held by pid $HOLDER_PID" "$out"
assert_not_contains "no reclaim warn for a live holder" "Removing stale" "$out"
assert_dir_exists "live holder's lock dir intact" "$L1"
assert_eq "holder's pid file untouched" "$HOLDER_PID" "$(cat "$L1/pid")"
assert_eq "holder's owner token untouched" "holders-own-token" "$(cat "$L1/owner")"
assert_eq "no ledger block written while blocked" "0" \
    "$(grep -c 'gate:tests_pass' "$TMP/aitasks/t${ID1}_x.md")"
kill "$HOLDER_PID" 2>/dev/null; wait "$HOLDER_PID" 2>/dev/null; HOLDER_PID=""
rm -rf "$L1"

# ============================================================
echo "--- concurrency: K contenders through one stale lock serialize ---"
# ============================================================
K=4
L2="$(lock_dir_for "$ID2")"
mkdir "$L2"
touch -t 202001010000 "$L2"    # tokenless + old: genuinely reclaimable

for i in $(seq 1 "$K"); do
    run_gate append "$ID2" tests_pass pass >/dev/null 2>"$TMP/sw_err_$i.log" &
done
wait

if [[ "$(marker_count "$ID2")" != "$K" ]]; then
    echo "DIAG: contention anomaly — contender stderr follows:"
    cat "$TMP"/sw_err_*.log
fi
assert_eq "$K contenders through a stale lock -> $K ledger blocks (no lost update)" \
    "$K" "$(marker_count "$ID2")"
for a in $(seq 1 "$K"); do
    assert_eq "attempt=$a present exactly once (single winner per reclaim)" \
        "1" "$(grep -c "attempt=${a}\$" "$TMP/aitasks/t${ID2}_x.md")"
done
reclaims="$(cat "$TMP"/sw_err_*.log | grep -c 'Removing stale')"
assert_eq "exactly one reclaim across all contenders (single-winner)" "1" "$reclaims"
assert_not_contains "no dead-holder reclaim of a contender's fresh lock" \
    "Reclaiming" "$(cat "$TMP"/sw_err_*.log)"
assert_dir_not_exists "no lock dir left behind" "$L2"
assert_dir_not_exists "no guard dir left behind" "$L2.gc"

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
