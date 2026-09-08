#!/usr/bin/env bash
# test_shadow_snapshot.sh - Tests for the shadow round-snapshot verbs
# (`snapshot` / `snapshots`) of aitask_shadow_rejected.sh (t1734).
#
# A review round's "Where this is heading" preamble compares the current plan
# (or code change) against what earlier rounds read. The plan is often only on
# the followed pane at round 1, so the shadow saves what it read as
# `<kind>_r<N>.md` under the same per-task store the rejection entries use —
# same task-id validation, same mutex, same atomic write, same archive-time
# prune. These tests pin that contract end to end, plus the line protocol the
# producers parse (`SNAPSHOT:<kind>|<round>|<complete|partial>|<path>`, path
# LAST because it is the only field that can carry `|`).
#
# Modelled on tests/test_shadow_rejected.sh: everything is scoped to a temp
# store via AITASK_SHADOW_DIR (the helper derives its lock dir from it), a
# live-pid lock holder exercises LOCK_BUSY, and no test body runs in a `( … )`
# subshell, so the in-process PASS/FAIL counters are accurate.
#
# Run: bash tests/test_shadow_snapshot.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

H="$PROJECT_DIR/.aitask-scripts/aitask_shadow_rejected.sh"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/ait_shadow_snap_XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

export AITASK_SHADOW_DIR="$TMP/shadow"

# --- helpers ----------------------------------------------------------------

snap_of()   { printf '%s/%s/%s_r%s.md' "$AITASK_SHADOW_DIR" "$1" "$2" "$3"; }
store_of()  { printf '%s/%s/rejected.md' "$AITASK_SHADOW_DIR" "$1"; }
lockd_of()  { printf '%s.lockd' "$(store_of "$1")"; }
reset_store() { rm -rf "$AITASK_SHADOW_DIR"; }

# Hold a task's lock with a LIVE pid so registry_lock.sh refuses to steal it.
hold_lock() {
    local lockd; lockd="$(lockd_of "$1")"
    mkdir -p "$lockd"
    sleep 30 &
    HOLDER_PID=$!
    echo "$HOLDER_PID" > "$lockd/pid"
    echo "held-by-test" > "$lockd/owner"
}
release_held_lock() {
    kill "$HOLDER_PID" 2>/dev/null || true
    wait "$HOLDER_PID" 2>/dev/null || true
    rm -rf "$(lockd_of "$1")"
}

echo "=== Test 1: snapshot writes the text and reports the protocol line ==="
reset_store
out="$(printf '# Plan\n\nline one\nline two\n' | "$H" snapshot 1734 1 2>&1)"; rc=$?
assert_eq "snapshot exits 0" "0" "$rc"
assert_eq "snapshot reports kind|round|state|path" \
    "SNAPSHOT:plan|1|complete|$(snap_of 1734 plan 1)" "$out"
assert_file_exists "plan_r1.md written" "$(snap_of 1734 plan 1)"
assert_eq "file content equals the input" "# Plan

line one
line two" "$(cat "$(snap_of 1734 plan 1)")"
assert_dir_not_exists "lock dir released after normal exit" "$(lockd_of 1734)"

echo
echo "=== Test 2: a repeat of the same round overwrites in place ==="
out="$(printf 'second reading\n' | "$H" snapshot 1734 1 2>&1)"; rc=$?
assert_eq "overwrite exits 0" "0" "$rc"
assert_eq "overwrite reports the same line" \
    "SNAPSHOT:plan|1|complete|$(snap_of 1734 plan 1)" "$out"
assert_eq "file holds the newest reading" "second reading" "$(cat "$(snap_of 1734 plan 1)")"
assert_eq "still exactly one plan snapshot" "1" \
    "$(find "$AITASK_SHADOW_DIR/1734" -maxdepth 1 -name 'plan_r*.md' | wc -l | tr -d ' ')"
assert_eq "snapshots lists exactly one entry" \
    "SNAPSHOT:plan|1|complete|$(snap_of 1734 plan 1)" "$("$H" snapshots 1734)"

echo
echo "=== Test 3: listing is kind-grouped and numeric within a kind ==="
reset_store
echo p10 | "$H" snapshot 42 10 >/dev/null
echo p2  | "$H" snapshot 42 2  >/dev/null
echo d2  | "$H" snapshot 42 2 --kind diff >/dev/null
echo p1  | "$H" snapshot 42 1  >/dev/null
echo d1  | "$H" snapshot 42 1 --kind diff >/dev/null
assert_eq "plan 1,2,10 then diff 1,2 — never lexical (r10 before r2)" \
"SNAPSHOT:plan|1|complete|$(snap_of 42 plan 1)
SNAPSHOT:plan|2|complete|$(snap_of 42 plan 2)
SNAPSHOT:plan|10|complete|$(snap_of 42 plan 10)
SNAPSHOT:diff|1|complete|$(snap_of 42 diff 1)
SNAPSHOT:diff|2|complete|$(snap_of 42 diff 2)" "$("$H" snapshots 42)"
assert_eq "--kind diff lands in its own file" "d2" "$(cat "$(snap_of 42 diff 2)")"

echo
echo "=== Test 4: --partial is recorded in the file and reported by both verbs ==="
reset_store
out="$(printf 'tail of a capture\n' | "$H" snapshot 7 1 --partial 2>&1)"
assert_eq "snapshot reports partial" "SNAPSHOT:plan|1|partial|$(snap_of 7 plan 1)" "$out"
assert_eq "first line is the partial marker" "<!-- partial -->" "$(head -n1 "$(snap_of 7 plan 1)")"
assert_eq "content follows the marker" "tail of a capture" "$(tail -n1 "$(snap_of 7 plan 1)")"
assert_eq "snapshots reports partial" "SNAPSHOT:plan|1|partial|$(snap_of 7 plan 1)" "$("$H" snapshots 7)"
printf 'the whole plan\n' | "$H" snapshot 7 1 >/dev/null
assert_eq "a complete overwrite flips the state back" \
    "SNAPSHOT:plan|1|complete|$(snap_of 7 plan 1)" "$("$H" snapshots 7)"
assert_eq "the marker line is gone after the overwrite" "the whole plan" "$(head -n1 "$(snap_of 7 plan 1)")"

echo
echo "=== Test 5: no snapshots -> NO_SNAPSHOTS, exit 0 ==="
reset_store
out="$("$H" snapshots 999 2>&1)"; rc=$?
assert_eq "unknown id -> NO_SNAPSHOTS" "NO_SNAPSHOTS" "$out"
assert_eq "unknown id -> exit 0" "0" "$rc"
mkdir -p "$AITASK_SHADOW_DIR/998"
echo '- [low | x] y' | "$H" add 998 >/dev/null
assert_eq "a store with only rejections -> NO_SNAPSHOTS" "NO_SNAPSHOTS" "$("$H" snapshots 998)"

echo
echo "=== Test 6: a held lock reports LOCK_BUSY and writes NOTHING ==="
reset_store
echo seed | "$H" snapshot 3131 1 >/dev/null
hold_lock 3131
out="$(echo fresh | "$H" snapshot 3131 2 2>&1)"; rc=$?
assert_eq "held lock -> LOCK_BUSY on stdout" "LOCK_BUSY" "$out"
assert_eq "held lock -> exit 3" "3" "$rc"
assert_file_not_exists "held lock -> plan_r2.md never written" "$(snap_of 3131 plan 2)"
assert_eq "held lock -> existing snapshot untouched" "seed" "$(cat "$(snap_of 3131 plan 1)")"
release_held_lock 3131
assert_eq "lock released -> snapshot succeeds again" \
    "SNAPSHOT:plan|2|complete|$(snap_of 3131 plan 2)" "$(echo fresh | "$H" snapshot 3131 2)"

echo
echo "=== Test 7: usage-class refusals exit 2 and write nothing ==="
reset_store
for bad in abc 1_2_3 ../x; do
    rc="$(echo text | "$H" snapshot "$bad" 1 >/dev/null 2>&1; echo $?)"
    assert_eq "malformed id '$bad' -> exit 2" "2" "$rc"
done
for badround in 0 07 x; do
    rc="$(echo text | "$H" snapshot 55 "$badround" >/dev/null 2>&1; echo $?)"
    assert_eq "invalid round '$badround' -> exit 2" "2" "$rc"
done
rc="$(echo text | "$H" snapshot 55 1 --kind notes >/dev/null 2>&1; echo $?)"
assert_eq "unknown --kind -> exit 2" "2" "$rc"
rc="$(printf '' | "$H" snapshot 55 1 >/dev/null 2>&1; echo $?)"
assert_eq "empty stdin -> exit 2" "2" "$rc"
rc="$(printf '  \n\t\n' | "$H" snapshot 55 1 >/dev/null 2>&1; echo $?)"
assert_eq "whitespace-only stdin -> exit 2" "2" "$rc"
assert_dir_not_exists "no store dir created by any refusal" "$AITASK_SHADOW_DIR/55"
rc="$("$H" snapshot 55 >/dev/null 2>&1; echo $?)"
assert_eq "missing round -> exit 2" "2" "$rc"
assert_eq "leading t is stripped, not rejected" \
    "SNAPSHOT:plan|1|complete|$(snap_of 56 plan 1)" "$(echo text | "$H" snapshot t56 1)"

echo
echo "=== Test 8: a pipe-bearing store root survives a three-split ==="
reset_store
export AITASK_SHADOW_DIR="$TMP/sh|adow"
out="$(echo text | "$H" snapshot 8 1)"
# Python is the consumer language of the monitor TUIs; mirror its split.
fields="$(printf '%s' "$out" | awk -F'|' '{ n=split($0, a, "|"); print n }')"
assert_eq "raw line has FIVE pipe-separated pieces (one inside the path)" "5" "$fields"
path_field="$(printf '%s' "$out" | cut -d'|' -f4-)"
assert_eq "splitting on at most three separators keeps the path whole" \
    "$TMP/sh|adow/8/plan_r1.md" "$path_field"
assert_eq "snapshots line is identical" "$out" "$("$H" snapshots 8)"
export AITASK_SHADOW_DIR="$TMP/shadow"

echo
echo "=== Test 9: snapshots coexist with rejections and are pruned together ==="
reset_store
echo '- [high | Step 7 guard] The guard double-commits.' | "$H" add 2121 --producer plan-challenge >/dev/null
before="$("$H" list 2121)"
echo plan | "$H" snapshot 2121 1 >/dev/null
echo diff | "$H" snapshot 2121 1 --kind diff >/dev/null
assert_eq "rejection list unchanged by snapshots" "$before" "$("$H" list 2121)"
assert_eq "snapshot listing sees both kinds" "2" "$("$H" snapshots 2121 | grep -c '^SNAPSHOT:')"
out="$("$H" prune 2121 2>&1)"; rc=$?
assert_eq "prune exits 0" "0" "$rc"
assert_eq "prune reports the id" "PRUNED:2121" "$out"
assert_file_not_exists "plan snapshot removed" "$(snap_of 2121 plan 1)"
assert_file_not_exists "diff snapshot removed" "$(snap_of 2121 diff 1)"
assert_dir_not_exists "store dir removed" "$AITASK_SHADOW_DIR/2121"
assert_eq "snapshots after prune -> NO_SNAPSHOTS" "NO_SNAPSHOTS" "$("$H" snapshots 2121)"

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
