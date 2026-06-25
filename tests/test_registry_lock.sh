#!/usr/bin/env bash
# test_registry_lock.sh — unit tests for the fail-safe registry mutex (t1073).
#
# Drives lib/registry_lock.sh directly against a temp lock dir (no registry
# needed). Pins the three non-negotiable invariants:
#   1. Never proceed unlocked — a live holder makes acquire FAIL (return 1).
#   2. Owner-token release — release deletes the lock ONLY if we still own it.
#   3. Steal only a provably-dead holder.
#
# Run: bash tests/test_registry_lock.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
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

# --- Case 3: dead holder → acquire STEALS --------------------------------
d3="$TMPROOT/lock3.d"
mkdir "$d3"
sleep 60 &
dead_pid=$!
kill "$dead_pid" 2>/dev/null
wait "$dead_pid" 2>/dev/null      # dead_pid is now a reaped (dead) PID
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

# --- Summary ------------------------------------------------------------
echo
echo "=========================================="
echo "Tests: $TOTAL  Passed: $PASS  Failed: $FAIL"
echo "=========================================="

[[ "$FAIL" -eq 0 ]]
