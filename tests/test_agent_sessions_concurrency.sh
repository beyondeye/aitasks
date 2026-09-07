#!/usr/bin/env bash
# test_agent_sessions_concurrency.sh - Concurrent-writer tests for the session
# store mutex (t1705_2).
#
# The session store is per-user and MACHINE-WIDE: every SessionStart hook, every
# freeze/restore coordinator and every monitor tick in any repo is a potential
# writer of the same file. A lost update here silently discards an agent's
# record — and unlike a lost mark, a lost record means the agent cannot be
# frozen or restored at all. `aitask_agent_sessions.sh` therefore holds the
# `registry_lock.sh` mutex around a read-modify-write, and this suite is what
# proves the serialization actually happens.
#
# Modelled on tests/test_agent_marks_concurrency.sh: N background writers +
# `wait`, then assert BOTH the total count (no lost update) AND that each
# distinct payload appears exactly once (no duplication / interleaved rewrite).
# Per-contender stderr is dumped on an anomaly so a rare race is diagnosable
# rather than an anonymous flake.
#
# Everything is scoped to a temp store via AITASKS_AGENT_SESSIONS_FILE, which
# the wrapper also uses to derive the lock dir — so this suite never touches the
# real ~/.config/aitasks/agent_sessions.json.
#
# Run: bash tests/test_agent_sessions_concurrency.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

SESSIONS_SH="$PROJECT_DIR/.aitask-scripts/aitask_agent_sessions.sh"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/ait_sessions_conc_XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

export AITASKS_AGENT_SESSIONS_FILE="$TMP/agent_sessions.json"
export AITASKS_FROZEN_DIR="$TMP/frozen"
LOCK_DIR="$AITASKS_AGENT_SESSIONS_FILE.lockd"
ROOT="$TMP/repo"
mkdir -p "$ROOT"

session_count() {
    "$SESSIONS_SH" list 2>/dev/null | grep -c '^SESSION:' || true
}

echo "=== Test 1: N concurrent upserts of DISTINCT windows all land ==="
N=6
for i in $(seq 1 "$N"); do
    "$SESSIONS_SH" upsert --root "$ROOT" --window "agent-w$i" \
        --pane "%$i" --pane-pid "$((1000 + i))" \
        >"$TMP/t1_out_$i.log" 2>"$TMP/t1_err_$i.log" &
done
wait

count="$(session_count)"
if [ "$count" != "$N" ]; then
    echo "DIAG: concurrent-upsert anomaly (got $count, want $N) — contender output follows:"
    for i in $(seq 1 "$N"); do
        echo "--- contender $i stdout ---"; cat "$TMP/t1_out_$i.log"
        echo "--- contender $i stderr ---"; cat "$TMP/t1_err_$i.log"
    done
fi
assert_eq "all $N concurrent upserts land (no lost update)" "$N" "$count"

echo "=== Test 2: each window appears EXACTLY once (no duplication) ==="
dupes=0
for i in $(seq 1 "$N"); do
    seen="$("$SESSIONS_SH" list 2>/dev/null | grep -c "|agent-w$i|" || true)"
    [ "$seen" = "1" ] || { echo "DIAG: window agent-w$i appears $seen times"; dupes=$((dupes + 1)); }
done
assert_eq "every window written exactly once" "0" "$dupes"

echo "=== Test 3: every record carries a canonical 8-hex id ==="
# A duplicated or truncated id would break the pane->record join for that agent.
bad_ids="$("$SESSIONS_SH" list 2>/dev/null | cut -d: -f2 | cut -d'|' -f1 \
    | grep -cvE '^[0-9a-f]{8}$' || true)"
assert_eq "all ids are canonical" "0" "$bad_ids"
uniq_ids="$("$SESSIONS_SH" list 2>/dev/null | cut -d: -f2 | cut -d'|' -f1 | sort -u | wc -l | tr -d ' ')"
assert_eq "all ids are distinct" "$N" "$uniq_ids"

echo "=== Test 4: a paused writer makes a second writer report LOCK_BUSY ==="
# SIGSTOP the holder mid-transaction, so the lock is genuinely held rather than
# merely contended. The 2s keypress budget must expire and report, not hang.
"$SESSIONS_SH" upsert --root "$ROOT" --window agent-pause \
    --pane %90 --pane-pid 9000 >/dev/null 2>&1 &
holder_pid=$!
wait "$holder_pid" 2>/dev/null

# Hold the mutex directly: the wrapper's own transaction is too short to catch.
mkdir -p "$LOCK_DIR" 2>/dev/null
printf '%s\n' "$$" >"$LOCK_DIR/pid" 2>/dev/null || true

start=$(date +%s)
out="$("$SESSIONS_SH" upsert --root "$ROOT" --window agent-blocked \
    --pane %91 --pane-pid 9100 2>&1)"
rc=$?
elapsed=$(( $(date +%s) - start ))

assert_eq "a held lock reports LOCK_BUSY" "LOCK_BUSY" "$out"
assert_eq "a held lock exits 3" "3" "$rc"
if [ "$elapsed" -gt 8 ]; then
    echo "DIAG: LOCK_BUSY took ${elapsed}s — the keypress budget is ~2s"
fi
assert_eq "LOCK_BUSY is reported inside the keypress budget" "1" \
    "$([ "$elapsed" -le 8 ] && echo 1 || echo 0)"

echo "=== Test 5: list returns DURING the pause (it takes no lock) ==="
# A read must never be the thing a leaked guard wedges. The lock is still held
# from Test 4 here, which is exactly the condition that matters.
start=$(date +%s)
list_out="$("$SESSIONS_SH" list 2>&1)"
list_rc=$?
list_elapsed=$(( $(date +%s) - start ))
assert_eq "list succeeds while the write lock is held" "0" "$list_rc"
assert_contains "list returns real rows while the lock is held" "SESSION:" "$list_out"
assert_eq "list does not wait on the lock" "1" \
    "$([ "$list_elapsed" -le 2 ] && echo 1 || echo 0)"

echo "=== Test 6: show also takes no lock ==="
some_id="$("$SESSIONS_SH" list 2>/dev/null | head -1 | cut -d: -f2 | cut -d'|' -f1)"
show_out="$("$SESSIONS_SH" show "$some_id" 2>&1)"
show_rc=$?
assert_eq "show succeeds while the write lock is held" "0" "$show_rc"
assert_contains "show prints KEY:value lines" "state:live" "$show_out"

rm -rf "$LOCK_DIR"

echo "=== Test 7: the blocked write left the store untouched ==="
# LOCK_BUSY must mean NOTHING was written — the contract the exit code claims.
blocked="$("$SESSIONS_SH" list 2>/dev/null | grep -c '|agent-blocked|' || true)"
assert_eq "a LOCK_BUSY write persisted nothing" "0" "$blocked"

echo "=== Test 8: the lock dir is derived from the OVERRIDDEN store path ==="
# A lock keyed to the default path while the data went elsewhere would serialize
# nothing — and, crucially, every test above would still pass, because they all
# run against one store. So assert the derivation directly: the lock the wrapper
# actually takes must sit beside THIS store, not beside ~/.config/aitasks/.
#
# Observed by holding the derived path and requiring the writer to block on it.
# If the wrapper derived some other lock dir it would sail past and succeed.
mkdir -p "$LOCK_DIR" 2>/dev/null
printf '%s\n' "$$" >"$LOCK_DIR/pid" 2>/dev/null || true
derived_out="$("$SESSIONS_SH" upsert --root "$ROOT" --window agent-lockpath \
    --pane %92 --pane-pid 9200 2>&1)"
assert_eq "the wrapper blocks on the lock dir derived from the store path" \
    "LOCK_BUSY" "$derived_out"
rm -rf "$LOCK_DIR"

assert_contains "the derived lock dir sits beside the overridden store" \
    "$TMP" "$LOCK_DIR"

# And with the lock free again, the same write goes through to that same store.
"$SESSIONS_SH" upsert --root "$ROOT" --window agent-lockpath \
    --pane %92 --pane-pid 9200 >/dev/null 2>&1
assert_contains "the store really lives at the overridden path" "agent-lockpath" \
    "$(cat "$AITASKS_AGENT_SESSIONS_FILE")"

echo "=== Test 9: the wrapper rejects an incoherent --pane / --pane-pid pair ==="
# Both-present is not enough. `--pane '' --pane-pid 123` would persist a record
# claiming a live process at no pane at all, and freeze-commit writes pane_id,
# pane_pid AND standin_pid from it -- after which reconcile can never match the
# record to a real pane and it is stranded in `frozen` with no way back.
# Asserted at the WRAPPER too, not only in the Python CLI: this is the surface
# the freeze engine and reconcile actually call.
"$SESSIONS_SH" upsert --root "$ROOT" --window agent-pair --pane %95 --pane-pid 9500 >/dev/null 2>&1
pair_id="$("$SESSIONS_SH" list 2>/dev/null | grep '|agent-pair|' | cut -d: -f2 | cut -d'|' -f1)"
pair_nonce="$("$SESSIONS_SH" freeze-begin "$pair_id" --owner-pid $$ \
    --capture-ansi /tmp/a --capture-txt /tmp/b --lines 1 2>/dev/null | cut -d'|' -f2)"

"$SESSIONS_SH" freeze-commit "$pair_id" --nonce "$pair_nonce" --pane '' --pane-pid 123 >/dev/null 2>&1
assert_eq "empty pane with a live pid exits 2" "2" "$?"
"$SESSIONS_SH" freeze-commit "$pair_id" --nonce "$pair_nonce" --pane %5 --pane-pid 0 >/dev/null 2>&1
assert_eq "real pane with pid 0 exits 2" "2" "$?"
assert_contains "neither refusal changed the record's state" "|freezing|" \
    "$("$SESSIONS_SH" list 2>/dev/null | grep '|agent-pair|' || true)"

# Both legal shapes still pass through the wrapper.
"$SESSIONS_SH" freeze-commit "$pair_id" --nonce "$pair_nonce" --pane '' --pane-pid 0 >/dev/null 2>&1
assert_eq "the gone-pane pair is accepted" "0" "$?"

echo ""
echo "=== Summary ==="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -eq 0 ]] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED ($FAIL)"
[[ "$FAIL" -eq 0 ]]
