#!/usr/bin/env bash
# test_registry_lock.sh — unit tests for the fail-safe registry mutex (t1073),
# now an adapter over lib/stale_lock.sh (t1507).
#
# Drives lib/registry_lock.sh directly against a temp lock dir (no registry
# needed). Cases 1-5 pin the three non-negotiable invariants, unchanged across
# the conversion:
#   1. Never proceed unlocked — a live holder makes acquire FAIL (return 1).
#   2. Owner-token release — release deletes the lock ONLY if we still own it.
#   3. Steal only a provably-dead holder.
#
# Cases 6-7 are CHARACTERIZATION: they were written against the pre-conversion
# lib and passed there first, so they pin preserved behavior rather than
# describing whatever the adapter happens to do — the quantized deadline (see
# case 6 on why a naive elapsed check cannot fail) and the busy path's silence,
# which two consumer suites depend on.
#
# Cases 8-14 pin what the shared core adds or changes: guard hygiene, the
# fail-closed leaked guard, the forced observe→destruct interleaving that is the
# whole point of the conversion (case 10, with case 11 as its negative control
# on the OLD algorithm), tokenless age reclaim, the clock-free deadline re-arm,
# and release's always-0 contract.
#
# Run: bash tests/test_registry_lock.sh
# Expected runtime: ~11s.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/proc_fixtures.sh
. "$PROJECT_DIR/tests/lib/proc_fixtures.sh"
# The lib delegates to stale_lock.sh, which needs warn() from terminal_compat.sh
# (every production caller sources it first — same as tests/test_stale_lock.sh).
. "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
# shellcheck source=../.aitask-scripts/lib/registry_lock.sh
. "$PROJECT_DIR/.aitask-scripts/lib/registry_lock.sh"

PASS=0
FAIL=0
TOTAL=0

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

# --- Case 1: basic acquire/release --------------------------------------
d1="$TMPROOT/lock1.d"
rc=0
registry_lock_acquire "$d1" 5 || rc=$?
assert_exit_zero_rc "case1: acquire on free lock succeeds" "$rc"
assert_dir_exists "case1: lock dir created" "$d1"
assert_file_exists "case1: pid file written" "$d1/pid"
assert_file_exists "case1: owner file written" "$d1/owner"
registry_lock_release "$d1"
assert_dir_not_exists "case1: release removes the lock dir" "$d1"

# --- Case 2: live holder → acquire FAILS, does NOT steal -----------------
# Invariant #1 (never proceed unlocked) + #3 (never steal a live holder).
d2="$TMPROOT/lock2.d"
mkdir "$d2"
sleep 60 &
live_pid=$!
printf '%s\n' "$live_pid" > "$d2/pid"
printf '%s\n' "someone-elses-token" > "$d2/owner"
rc=0
registry_lock_acquire "$d2" 1 || rc=$?   # 1s timeout against a live holder
assert_exit_nonzero_rc "case2: acquire fails (does not proceed) vs live holder" "$rc"
assert_dir_exists "case2: live holder's lock left intact" "$d2"
assert_eq "case2: live holder's pid untouched (not stolen)" \
    "$live_pid" "$(cat "$d2/pid")"
kill "$live_pid" 2>/dev/null
wait "$live_pid" 2>/dev/null
rm -rf "$d2"

# dead_pid_fixture() comes from tests/lib/proc_fixtures.sh (sourced above).

# --- Case 3: dead holder → acquire STEALS --------------------------------
d3="$TMPROOT/lock3.d"
mkdir "$d3"
dead_pid="$(dead_pid_fixture)"
printf '%s\n' "$dead_pid" > "$d3/pid"
printf '%s\n' "dead-holder-token" > "$d3/owner"
rc=0
registry_lock_acquire "$d3" 5 || rc=$?
assert_exit_zero_rc "case3: acquire steals a provably-dead holder" "$rc"
# shellcheck disable=SC2154  # _registry_lock_token is set by the sourced lib
assert_eq "case3: we now own the stolen lock" \
    "$_registry_lock_token" "$(cat "$d3/owner")"
registry_lock_release "$d3"
assert_dir_not_exists "case3: release after steal removes the dir" "$d3"

# --- Case 4: release does NOT delete another process's lock --------------
# Invariant #2: simulate our lock being stolen while we were presumed dead,
# then call release — it must leave the new owner's lock intact.
d4="$TMPROOT/lock4.d"
rc=0
registry_lock_acquire "$d4" 5 || rc=$?
assert_exit_zero_rc "case4: acquire succeeds" "$rc"
printf '%s\n' "new-owner-token-after-steal" > "$d4/owner"   # owner changed
registry_lock_release "$d4"
assert_dir_exists "case4: release leaves another owner's lock intact" "$d4"
rm -rf "$d4"

# --- Case 5: EXIT trap releases our own lock ----------------------------
d5="$TMPROOT/lock5.d"
# Acquire in a subshell; on its exit the EXIT trap must release the lock.
( registry_lock_acquire "$d5" 5 >/dev/null 2>&1 )
assert_dir_not_exists "case5: EXIT trap released the lock on process exit" "$d5"

# --- Case 6 (characterization): the quantized deadline, measured soundly --
# The timeout is quantized by `date +%s`: deadline = start_second + timeout,
# polled against whole seconds. A call entered at wall-clock 10.999 with
# timeout=1 sets deadline=11 and may legitimately return at 11.001 — a 2 ms
# wait — while a naive t1-t0 still reads 1. An `elapsed >= timeout` check built
# on `date +%s` therefore measures the same rounded quantity it is meant to
# bound and CANNOT FAIL. Starting the measurement immediately after a tick is
# what makes the integer delta a real bound, and it stays portable (no GNU-only
# `date +%s.%N`, no bash-5 $EPOCHREALTIME).
#
# LOWER BOUND ONLY, deliberately. "Returns within ~timeout" is not a property
# this code has, and any `elapsed <= N` assertion is decided by host scheduling
# (this suite runs with parallel workers alongside other agents), so it would
# fail spuriously on a correct implementation. The behavior an upper bound
# would stand in for — the deadline re-arm consuming the REMAINING time rather
# than a fresh full budget — is pinned clock-free in case 10.
wait_for_second_boundary() {
    local s0; s0=$(date +%s)
    while [[ "$(date +%s)" == "$s0" ]]; do sleep 0.01; done
}

d6="$TMPROOT/lock6.d"
mkdir "$d6"
sleep 60 &
live6=$!
printf '%s\n' "$live6" > "$d6/pid"
printf '%s\n' "someone-elses-token" > "$d6/owner"
err6="$TMPROOT/err6.log"

wait_for_second_boundary
t0=$(date +%s)
rc=0
registry_lock_acquire "$d6" 2 2>"$err6" || rc=$?
t1=$(date +%s)
elapsed=$(( t1 - t0 ))
assert_exit_nonzero_rc "case6: busy against a live holder" "$rc"
assert_eq "case6: never reports busy before the quantized deadline" "0" \
    "$([ "$elapsed" -ge 2 ] && echo 0 || echo "1 (returned after ${elapsed}s)")"
# Two consumer suites pin `assert_eq … "LOCK_BUSY" "$out"` on 2>&1-captured
# output (tests/test_shadow_rejected.sh, tests/test_agent_marks_concurrency.sh),
# so ANY stderr line on this path is a consumer-visible break.
assert_eq "case6: the busy path writes nothing to stderr" "" "$(cat "$err6")"
kill "$live6" 2>/dev/null
wait "$live6" 2>/dev/null
rm -rf "$d6"

# --- Case 7 (characterization): dead-holder steal fits a 1s timeout ------
d7="$TMPROOT/lock7.d"
mkdir "$d7"
dead7="$(dead_pid_fixture)"
printf '%s\n' "$dead7" > "$d7/pid"
printf '%s\n' "dead-holder-token" > "$d7/owner"
rc=0
registry_lock_acquire "$d7" 1 || rc=$?
assert_exit_zero_rc "case7: dead-holder steal succeeds within a 1s timeout" "$rc"
registry_lock_release "$d7"
assert_dir_not_exists "case7: release removes the stolen lock" "$d7"

# --- Case 8: guard hygiene ----------------------------------------------
d8="$TMPROOT/lock8.d"
registry_lock_acquire "$d8" 5
assert_dir_not_exists "case8: no guard dir remains while the lock is held" "$d8.gc"
registry_lock_release "$d8"
assert_dir_not_exists "case8: no guard dir remains after release" "$d8.gc"

# --- Case 9: a leaked .gc guard makes acquire fail CLOSED ----------------
# The guard is never auto-broken, so a process killed inside it wedges the lock:
# every later acquire reports busy with no holder in existence. That is the
# price of a single-winner reclaim and it must be pinned deliberately, not
# discovered in production. registry_lock_describe is the documented cure's
# signpost.
d9="$TMPROOT/lock9.d"
mkdir "$d9"
dead9="$(dead_pid_fixture)"
printf '%s\n' "$dead9" > "$d9/pid"
printf '%s\n' "stale-token" > "$d9/owner"
mkdir "$d9.gc"                      # leaked guard, held by no live process
err9="$TMPROOT/err9.log"
rc=0
registry_lock_acquire "$d9" 1 2>"$err9" || rc=$?
assert_exit_nonzero_rc "case9: leaked guard makes acquire fail closed" "$rc"
assert_dir_exists "case9: stale lock NOT reclaimed while the guard is held" "$d9"
assert_eq "case9: stale holder's pid untouched" "$dead9" "$(cat "$d9/pid")"
assert_not_contains "case9: no reclaim under a held guard" "Reclaiming" "$(cat "$err9")"
desc9="$(registry_lock_describe "$d9")"
assert_contains "case9: describe names the holder pid" "held by pid $dead9" "$desc9"
assert_contains "case9: describe names the lock dir" "$d9" "$desc9"
assert_contains "case9: describe names the leaked guard" "$d9.gc" "$desc9"
rm -rf "$d9" "$d9.gc"

# --- Case 9b: a re-published LIVE lock is never displaced ----------------
# The same shape as case 10 without the fork barrier: the dead pid is the
# verdict material a contender would have formed, the held guard stands in for
# that contender being inside the guarded reclaim section, and the live
# pid/token is the re-publication that its stale verdict no longer describes.
# Nothing may touch it.
d9b="$TMPROOT/lock9b.d"
mkdir "$d9b"
printf '%s\n' "$(dead_pid_fixture)" > "$d9b/pid"
mkdir "$d9b.gc"
sleep 60 &
live9b=$!
printf '%s\n' "$live9b" > "$d9b/pid"
printf '%s\n' "fresh-owner-token" > "$d9b/owner"
rc=0
registry_lock_acquire "$d9b" 1 >/dev/null 2>&1 || rc=$?
assert_exit_nonzero_rc "case9b: acquire does not displace a re-published live lock" "$rc"
assert_eq "case9b: re-published pid byte-identical" "$live9b" "$(cat "$d9b/pid")"
assert_eq "case9b: re-published owner byte-identical" "fresh-owner-token" "$(cat "$d9b/owner")"
kill "$live9b" 2>/dev/null
wait "$live9b" 2>/dev/null
rm -rf "$d9b" "$d9b.gc"

# --- Case 10: the observe→destruct interleaving, FORCED ------------------
# The defect this lib was converted to close: a contender forms a staleness
# verdict, another reclaims and re-publishes a fresh LIVE lock, and the first
# then destroys it — two holders in the critical section. A free-running
# contention test cannot pin this (nothing forces that order), so the order is
# imposed here. _stale_lock_pid_alive is called by the real code the instant
# after it reads the holder pid, i.e. exactly inside the window; shimming it in
# contender A parks A mid-verdict, with the .gc guard held.
# Case 11 is the negative control proving this construction discriminates.
d10="$TMPROOT/lock10.d"
mkdir "$d10"
dead10="$(dead_pid_fixture)"
printf '%s\n' "$dead10" > "$d10/pid"
printf '%s\n' "stale-token" > "$d10/owner"
parked10="$TMPROOT/parked10"
hold10="$TMPROOT/hold10"
hold10b="$TMPROOT/hold10b"
: > "$hold10"
: > "$hold10b"
(
    # shellcheck disable=SC2329  # invoked indirectly, from inside the sourced lib
    _stale_lock_pid_alive() {
        : > "$parked10"
        while [[ -e "$hold10" ]]; do sleep 0.01; done
        return 1                     # verdict: dead — destruction still pending
    }
    registry_lock_acquire "$d10" 10 >/dev/null 2>&1 || exit 1
    printf '%s\n' "$_registry_lock_token" > "$TMPROOT/a10.token"
    while [[ -e "$hold10b" ]]; do sleep 0.01; done
) &
a10=$!
for _ in $(seq 1 500); do [[ -e "$parked10" ]] && break; sleep 0.01; done
assert_file_exists "case10: contender A parked mid-verdict" "$parked10"

rc=0
registry_lock_acquire "$d10" 1 >/dev/null 2>&1 || rc=$?
assert_exit_nonzero_rc "case10: B is excluded while A holds the guard" "$rc"
assert_eq "case10: B never re-published — the observed lock is unchanged" \
    "$dead10" "$(cat "$d10/pid")"

rm -f "$hold10"
for _ in $(seq 1 500); do [[ -s "$TMPROOT/a10.token" ]] && break; sleep 0.01; done
# Non-empty guard first: without it, "A failed to acquire at all" would compare
# "" against "" and pass vacuously.
a10_token="$(cat "$TMPROOT/a10.token" 2>/dev/null)"
assert_eq "case10: A actually acquired (non-empty token)" "0" \
    "$([ -n "$a10_token" ] && echo 0 || echo "1 (A never acquired)")"
assert_eq "case10: A's own token is the sole owner after it resumes" \
    "$a10_token" "$(cat "$d10/owner" 2>/dev/null)"
rm -f "$hold10b"
wait "$a10" 2>/dev/null
assert_dir_not_exists "case10: A's EXIT trap released the lock" "$d10"

# --- Case 11 (NEGATIVE CONTROL): the old algorithm loses the fresh lock ---
# Fixture-only reproduction of the pre-t1507 acquire body, with a park hook at
# the same seam. If this passes the property that case 10 asserts, the
# construction proves nothing and case 10 must be rewritten.
_negctrl_park() { :; }
old_registry_lock_acquire() {          # <dir> <timeout>
    local dir="$1" timeout="$2" deadline
    deadline=$(( $(date +%s) + timeout ))
    while ! mkdir "$dir" 2>/dev/null; do
        local holder
        holder=$(cat "$dir/pid" 2>/dev/null || echo "")
        if [[ -n "$holder" ]] && ! kill -0 "$holder" 2>/dev/null; then
            _negctrl_park              # verdict formed, destruction not yet done
            local dead="$dir.dead.$$.$RANDOM"
            mv "$dir" "$dead" 2>/dev/null && rm -rf "$dead"
            continue
        fi
        if (( $(date +%s) >= deadline )); then return 1; fi
        sleep 0.05
    done
    printf '%s\n' "$$" > "$dir/pid"
    printf '%s\n' "a-old-token" > "$dir/owner"
    return 0
}

d11="$TMPROOT/lock11.d"
mkdir "$d11"
dead11="$(dead_pid_fixture)"
printf '%s\n' "$dead11" > "$d11/pid"
printf '%s\n' "stale-token" > "$d11/owner"
parked11="$TMPROOT/parked11"
hold11="$TMPROOT/hold11"
: > "$hold11"
(
    _negctrl_park() {
        : > "$parked11"
        while [[ -e "$hold11" ]]; do sleep 0.01; done
    }
    old_registry_lock_acquire "$d11" 10 >/dev/null 2>&1
) &
a11=$!
for _ in $(seq 1 500); do [[ -e "$parked11" ]] && break; sleep 0.01; done
assert_file_exists "case11: old-algorithm contender A parked mid-verdict" "$parked11"

# B does what nothing excluded it from doing: reclaim, then publish a fresh
# LIVE lock — the state A's stale verdict no longer describes.
rm -rf "$d11"
mkdir "$d11"
sleep 60 &
live11=$!
printf '%s\n' "$live11" > "$d11/pid"
printf '%s\n' "b-fresh-token" > "$d11/owner"

rm -f "$hold11"
wait "$a11" 2>/dev/null
# Exact, not "!= b-fresh-token": an A that failed to acquire would leave no
# owner file at all, and a `!=` check would read that absence as displacement.
assert_eq "case11 (negative control): the old algorithm DISPLACES B's live lock" \
    "a-old-token" "$(cat "$d11/owner" 2>/dev/null)"
assert_eq "case11 (negative control): B's live pid is no longer the holder" "0" \
    "$([ "$(cat "$d11/pid" 2>/dev/null)" != "$live11" ] && echo 0 \
       || echo "1 (fresh lock survived — case 10 does not discriminate)")"
kill "$live11" 2>/dev/null
wait "$live11" 2>/dev/null
rm -rf "$d11"

# --- Case 12: tokenless locks — fresh waited on, aged reclaimed ----------
d12="$TMPROOT/lock12.d"
mkdir "$d12"                        # no pid file: legacy/foreign, and fresh
rc=0
registry_lock_acquire "$d12" 1 >/dev/null 2>&1 || rc=$?
assert_exit_nonzero_rc "case12: a fresh tokenless lock is waited on, not stolen" "$rc"
assert_dir_exists "case12: fresh tokenless lock left intact" "$d12"
touch -t 202001010000 "$d12"        # push past the stale window
rc=0
registry_lock_acquire "$d12" 5 2>/dev/null || rc=$?
assert_exit_zero_rc "case12: a tokenless lock past the window is reclaimed" "$rc"
registry_lock_release "$d12"

# --- Case 13: the deadline re-arm consumes the REMAINING time ------------
# The clock-free counterpart to case 6. An `elapsed <= N` assertion would be
# decided by host scheduling; the property is really about the retry budget
# handed to the core each pass, so observe that directly. Rename-and-wrap the
# real function and force an early exhaustion so the outer loop must re-arm.
budgets="$TMPROOT/budgets.log"
: > "$budgets"
_sla_src="$(declare -f stale_lock_acquire)"
eval "_real_stale_lock_acquire${_sla_src#stale_lock_acquire}"
stale_lock_acquire() { printf '%s\n' "$2" >> "$budgets"; sleep 0.01; return 1; }

wait_for_second_boundary
rc=0
registry_lock_acquire "$TMPROOT/lock13.d" 3 || rc=$?

_sla_src="$(declare -f _real_stale_lock_acquire)"      # restore the real one
eval "stale_lock_acquire${_sla_src#_real_stale_lock_acquire}"

assert_exit_nonzero_rc "case13: a never-succeeding core makes acquire report busy" "$rc"
b_first="$(head -n1 "$budgets")"
b_last="$(tail -n1 "$budgets")"
b_n="$(grep -c '' "$budgets")"
assert_eq "case13: the first pass gets the full window (timeout x attempts/sec)" \
    "60" "$b_first"
assert_eq "case13: the loop re-armed instead of returning on first exhaustion" "0" \
    "$([ "$b_n" -ge 2 ] && echo 0 || echo "1 (only $b_n budget(s) requested)")"
assert_eq "case13: later budgets shrink with the remaining time" "0" \
    "$([ "$b_last" -lt "$b_first" ] && echo 0 \
       || echo "1 (last=$b_last first=$b_first — a fresh full budget per pass)")"
assert_eq "case13: the budget sequence never grows" "0" \
    "$(awk 'NR>1 && $1>prev {bad=1} {prev=$1} END {print bad?1:0}' "$budgets")"

# --- Case 14: release ALWAYS returns 0, even when it removes nothing ------
# Callers are `set -euo pipefail` and call release bare, after their protected
# mutation has already committed — a propagated failure would abort them
# mid-flow. Retention is surfaced as a warn instead.
d14="$TMPROOT/lock14.d"
registry_lock_acquire "$d14" 5
printf '%s\n' "someone-else-after-a-reclaim" > "$d14/owner"
rc=0
registry_lock_release "$d14" 2>/dev/null || rc=$?
assert_exit_zero_rc "case14: release returns 0 although it could not remove the lock" "$rc"
assert_dir_exists "case14: the new owner's lock is left intact" "$d14"
# shellcheck disable=SC2154  # _registry_lock_dir is set by the sourced lib
assert_eq "case14: module state is cleared regardless" "" "$_registry_lock_dir"
rm -rf "$d14"

# --- Summary ------------------------------------------------------------
echo
echo "=========================================="
echo "Tests: $TOTAL  Passed: $PASS  Failed: $FAIL"
echo "=========================================="

[[ "$FAIL" -eq 0 ]]
