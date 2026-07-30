#!/usr/bin/env bash
# test_agent_marks_concurrency.sh - Concurrent-writer tests for the agent-marks
# store mutex (t1326).
#
# The marks store is per-user and CROSS-REPO: every `ait minimonitor` /
# `ait monitor` instance on the machine, in any repo, is a potential writer of
# the same file. A lost update here silently discards a mark the user set in
# another repo — the t1073 failure mode. `aitask_agent_marks.sh` therefore holds
# the `registry_lock.sh` mutex around a read-modify-write, and this suite is what
# proves the serialization actually happens.
#
# Modelled on tests/test_gate_lock_characterization.sh: N background writers +
# `wait`, then assert BOTH the total count (no lost update) AND that each
# distinct payload appears exactly once (no duplication / interleaved rewrite).
# Per-contender stderr is dumped on an anomaly so a rare race is diagnosable
# rather than an anonymous flake.
#
# Everything is scoped to a temp store via AITASKS_AGENT_MARKS_FILE, which the
# wrapper also uses to derive the lock dir — so this suite never touches the
# real ~/.config/aitasks/agent_marks.json.
#
# Run: bash tests/test_agent_marks_concurrency.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

MARKS_SH="$PROJECT_DIR/.aitask-scripts/aitask_agent_marks.sh"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/ait_marks_conc_XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

export AITASKS_AGENT_MARKS_FILE="$TMP/agent_marks.json"
LOCK_DIR="$AITASKS_AGENT_MARKS_FILE.lockd"
ROOT="$TMP/repo"
mkdir -p "$ROOT"

mark_count() {
    "$MARKS_SH" list 2>/dev/null | grep -c '^MARK:' || true
}

echo "=== Test 1: N concurrent toggles of DISTINCT windows all land ==="
N=6
for i in $(seq 1 "$N"); do
    "$MARKS_SH" toggle "$ROOT" "agent-w$i" >"$TMP/t1_out_$i.log" 2>"$TMP/t1_err_$i.log" &
done
wait

count="$(mark_count)"
if [ "$count" != "$N" ]; then
    echo "DIAG: concurrent-toggle anomaly (got $count, want $N) — contender output follows:"
    for i in $(seq 1 "$N"); do
        echo "--- writer $i stdout ---"; cat "$TMP/t1_out_$i.log"
        echo "--- writer $i stderr ---"; cat "$TMP/t1_err_$i.log"
    done
fi
assert_eq "$N concurrent toggles -> $N marks (no lost update)" "$N" "$count"

for i in $(seq 1 "$N"); do
    n="$("$MARKS_SH" list | grep -c "|agent-w$i|" || true)"
    assert_eq "agent-w$i present exactly once (writes serialized)" "1" "$n"
done
assert_dir_not_exists "lock dir released after normal exits" "$LOCK_DIR"

echo
echo "=== Test 2: concurrent toggles of the SAME window stay consistent ==="
# Each toggle flips the same key, so the final state is on/off by parity. The
# invariant that matters is that the store is never corrupted and never grows a
# duplicate — an unserialized read-modify-write could produce both.
rm -f "$AITASKS_AGENT_MARKS_FILE"
for i in 1 2 3 4; do
    "$MARKS_SH" toggle "$ROOT" "agent-same" >/dev/null 2>"$TMP/t2_err_$i.log" &
done
wait
dupes="$("$MARKS_SH" list | grep -c '|agent-same|' || true)"
if [ "$dupes" -gt 1 ]; then
    echo "DIAG: duplicate entry after concurrent same-key toggles:"
    cat "$TMP"/t2_err_*.log
fi
assert_eq "same-key concurrent toggles never duplicate the entry" "0" \
    "$([ "$dupes" -le 1 ] && echo 0 || echo 1)"
assert_eq "store still parses after same-key contention" "0" \
    "$("$MARKS_SH" list >/dev/null 2>&1; echo $?)"
assert_dir_not_exists "lock dir released after same-key contention" "$LOCK_DIR"

echo
echo "=== Test 3: a held lock reports LOCK_BUSY and writes NOTHING ==="
rm -f "$AITASKS_AGENT_MARKS_FILE"
"$MARKS_SH" toggle "$ROOT" "agent-pre" >/dev/null 2>&1
# cmp(1), not md5sum: macOS ships `md5`, not `md5sum`, and this suite must run
# there too (see aidocs/framework/sed_macos_issues.md).
cp "$AITASKS_AGENT_MARKS_FILE" "$TMP/before_blocked.json"

# Hold the lock with a LIVE pid so registry_lock.sh refuses to steal it
# (it steals only a provably-dead holder, never by age).
mkdir -p "$LOCK_DIR"
sleep 30 &
holder_pid=$!
echo "$holder_pid" > "$LOCK_DIR/pid"
echo "held-by-test" > "$LOCK_DIR/owner"

out="$("$MARKS_SH" toggle "$ROOT" "agent-blocked" 2>&1)"; rc=$?

kill "$holder_pid" 2>/dev/null || true
wait "$holder_pid" 2>/dev/null || true
rm -rf "$LOCK_DIR"

assert_eq "held lock -> LOCK_BUSY on stdout" "LOCK_BUSY" "$out"
assert_eq "held lock -> exit 3" "3" "$rc"
assert_eq "held lock -> store byte-identical (never wrote unlocked)" "0" \
    "$(cmp -s "$TMP/before_blocked.json" "$AITASKS_AGENT_MARKS_FILE"; echo $?)"

echo
echo "=== Test 4: a dead holder's lock IS reclaimed (not a permanent wedge) ==="
rm -f "$AITASKS_AGENT_MARKS_FILE"
mkdir -p "$LOCK_DIR"
# A pid that has certainly exited: spawn and reap it.
sleep 0 &
dead_pid=$!
wait "$dead_pid" 2>/dev/null || true
echo "$dead_pid" > "$LOCK_DIR/pid"
echo "dead-owner" > "$LOCK_DIR/owner"

out="$("$MARKS_SH" toggle "$ROOT" "agent-after-dead" 2>&1)"; rc=$?
assert_eq "dead holder reclaimed -> toggle succeeds" "0" "$rc"
assert_contains "dead holder reclaimed -> mark recorded" "MARKED:" "$out"
assert_dir_not_exists "lock dir released after reclaim" "$LOCK_DIR"

echo
echo "=== Test 5: a corrupt store is refused, not clobbered ==="
echo '{ not json' > "$AITASKS_AGENT_MARKS_FILE"
corrupt_before="$(cat "$AITASKS_AGENT_MARKS_FILE")"
out="$("$MARKS_SH" toggle "$ROOT" "agent-x" 2>&1)"; rc=$?
assert_eq "corrupt store -> exit 4" "4" "$rc"
assert_contains "corrupt store -> ERROR reported" "ERROR:" "$out"
assert_eq "corrupt store left byte-identical (no clobber)" \
    "$corrupt_before" "$(cat "$AITASKS_AGENT_MARKS_FILE")"
assert_dir_not_exists "lock dir released after corrupt-store abort" "$LOCK_DIR"

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
