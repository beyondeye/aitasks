#!/usr/bin/env bash
# test_stale_lock.sh - Unit tests for lib/stale_lock.sh (t1496), sourcing the
# lib directly. Pins the helper's invariants:
#   1. all lock-dir mutations serialized by the .gc guard
#   2. .gc fail-closed, never auto-stolen
#   3. live PID never displaced; dead PID reclaimable; tokenless age-gated
#   4. release requires the owner token
#   5. per-user / per-repo / AITASKS_LOCK_DIR-overridable paths
#   6. cleanup failures propagated (verified removals)
#
# Run: bash tests/test_stale_lock.sh
# Expected runtime: ~3s (several sub-second exhaustion budgets + one 2s
# release guard-wait). A run of ~60s+ against near-zero CPU means a fixture is
# blocked in `wait` on a child that never received its kill — see
# tests/lib/proc_fixtures.sh (t1512).

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/proc_fixtures.sh"

PASS=0
FAIL=0
TOTAL=0

# The lib needs warn() from terminal_compat.sh (callers source it first).
. "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
. "$PROJECT_DIR/.aitask-scripts/lib/stale_lock.sh"

T="$(mktemp -d "${TMPDIR:-/tmp}/test_stalelock_XXXXXX")"
HOLDER_PID=""
cleanup() {
    rm -rf "$T"
    [[ -n "$HOLDER_PID" ]] && kill "$HOLDER_PID" 2>/dev/null
}
trap cleanup EXIT

# All lock dirs in this file live under the test's own base via the documented
# seam (invariant 5 is itself tested further below with scoped values).
export AITASKS_LOCK_DIR="$T/locks"

backdate() {  # <path> — push mtime well past the 120s stale window
    touch -t 202001010000 "$1"
}

# ============================================================
echo "--- acquire/release round-trip + owner token ---"
# ============================================================
L="$(ait_lock_dir rt)"
stale_lock_acquire "$L" 3 0.05 "rt lock"; rc=$?
assert_exit_zero_rc "fresh acquire succeeds" "$rc"
assert_dir_exists "lock dir exists while held" "$L"
tok="$STALE_LOCK_TOKEN"
assert_eq "pid file records this shell" "$$" "$(cat "$L/pid")"
assert_eq "owner file records the returned token" "$tok" "$(cat "$L/owner")"

stale_lock_release "$L" "wrong-token"; rc=$?
assert_exit_zero_rc "wrong-token release is a no-op, not a failure" "$rc"
assert_dir_exists "wrong-token release leaves the lock intact" "$L"

stale_lock_release "$L" ""; rc=$?
assert_dir_exists "empty-token release leaves the lock intact" "$L"

stale_lock_release "$L" "$tok"; rc=$?
assert_exit_zero_rc "owner release succeeds" "$rc"
assert_dir_not_exists "owner release removes the lock" "$L"
assert_dir_not_exists "no guard dir left behind" "$L.gc"

stale_lock_release "$L" "$tok"; rc=$?
assert_exit_zero_rc "releasing an already-gone lock is a no-op success" "$rc"

# ============================================================
echo "--- N independent locks in one process (no shared token state) ---"
# ============================================================
LA="$(ait_lock_dir multi_a)"; LB="$(ait_lock_dir multi_b)"
stale_lock_acquire "$LA" 3 0.05 "lock A"
tok_a="$STALE_LOCK_TOKEN"
stale_lock_acquire "$LB" 3 0.05 "lock B"
tok_b="$STALE_LOCK_TOKEN"
stale_lock_release "$LA" "$tok_a"; rc=$?
assert_exit_zero_rc "lock A releases with its own token after B was acquired" "$rc"
assert_dir_not_exists "lock A gone" "$LA"
assert_dir_exists "lock B still held" "$LB"
stale_lock_release "$LB" "$tok_b"; rc=$?
assert_exit_zero_rc "lock B releases cleanly" "$rc"
assert_dir_not_exists "lock B gone" "$LB"

# ============================================================
echo "--- live-PID holder is never displaced ---"
# ============================================================
sleep 120 &
HOLDER_PID=$!
L="$(ait_lock_dir live)"
mkdir "$L"
printf '%s\n' "$HOLDER_PID" > "$L/pid"
printf '%s\n' "sometoken" > "$L/owner"
backdate "$L"   # even WAY past the stale window: pid liveness wins over age

err="$(stale_lock_acquire "$L" 3 0.05 "live lock" 2>&1)"; rc=$?
assert_exit_nonzero_rc "acquire against a live holder exhausts and fails" "$rc"
assert_dir_exists "live holder's lock dir intact" "$L"
assert_eq "live holder's pid file intact" "$HOLDER_PID" "$(cat "$L/pid")"
assert_not_contains "no reclaim warn for a live holder" "Reclaiming" "$err"
desc="$(stale_lock_describe "$L")"
assert_contains "describe names the holder pid" "held by pid $HOLDER_PID" "$desc"
assert_contains "describe names the lock dir" "$L" "$desc"
rm -rf "$L"

# ============================================================
echo "--- dead-PID holder is reclaimed with warn ---"
# ============================================================
dead_pid="$(dead_pid_fixture)"
L="$(ait_lock_dir dead)"
mkdir "$L"
printf '%s\n' "$dead_pid" > "$L/pid"
# fresh mtime on purpose: dead-pid reclaim must not depend on age.
# NOTE: acquire must run in THIS shell (stderr to a file, not $(...) capture) —
# a command substitution would strand STALE_LOCK_TOKEN in the subshell.
stale_lock_acquire "$L" 5 0.05 "dead lock" 2>"$T/err"; rc=$?
err="$(cat "$T/err")"
assert_exit_zero_rc "acquire reclaims a dead holder's lock" "$rc"
assert_contains "dead-holder reclaim warns" "Reclaiming dead lock from dead holder pid $dead_pid" "$err"
assert_eq "reclaimed lock now records this shell" "$$" "$(cat "$L/pid")"
stale_lock_release "$L" "$STALE_LOCK_TOKEN"; rc=$?
assert_exit_zero_rc "reclaimed-then-held lock releases with its token" "$rc"
assert_dir_not_exists "reclaimed-then-held lock removed on release" "$L"

# ============================================================
echo "--- tokenless locks: fresh waits, old is reclaimed ---"
# ============================================================
L="$(ait_lock_dir tokenless_fresh)"
mkdir "$L"   # no pid file, fresh mtime: a holder mid-acquire — wait
err="$(stale_lock_acquire "$L" 3 0.05 "fresh foreign lock" 2>&1)"; rc=$?
assert_exit_nonzero_rc "tokenless fresh lock is waited on, then acquire fails" "$rc"
assert_dir_exists "tokenless fresh lock left intact" "$L"
assert_not_contains "no stale warn for a fresh lock" "Removing stale" "$err"
rm -rf "$L"

L="$(ait_lock_dir tokenless_old)"
mkdir "$L"
backdate "$L"
stale_lock_acquire "$L" 5 0.05 "old foreign lock" 2>"$T/err"; rc=$?
err="$(cat "$T/err")"
assert_exit_zero_rc "tokenless old lock is reclaimed" "$rc"
assert_contains "age-based reclaim warns" "Removing stale old foreign lock (age:" "$err"
stale_lock_release "$L" "$STALE_LOCK_TOKEN"; rc=$?
assert_exit_zero_rc "post-reclaim release succeeds" "$rc"
assert_dir_not_exists "post-reclaim release removed the lock" "$L"

# ============================================================
echo "--- malformed pid content routes to the age branch ---"
# ============================================================
L="$(ait_lock_dir malformed_old)"
mkdir "$L"
printf 'not-a-pid\n' > "$L/pid"
backdate "$L"
stale_lock_acquire "$L" 5 0.05 "malformed old lock" 2>"$T/err"; rc=$?
err="$(cat "$T/err")"
assert_exit_zero_rc "malformed-pid old lock is reclaimed age-based" "$rc"
assert_contains "malformed-pid reclaim uses the stale warn" "Removing stale" "$err"
stale_lock_release "$L" "$STALE_LOCK_TOKEN"; rc=$?
assert_dir_not_exists "malformed-old lock removed on release" "$L"

L="$(ait_lock_dir malformed_fresh)"
mkdir "$L"
printf 'not-a-pid\n' > "$L/pid"
err="$(stale_lock_acquire "$L" 3 0.05 "malformed fresh lock" 2>&1)"; rc=$?
assert_exit_nonzero_rc "malformed-pid fresh lock is waited on" "$rc"
assert_dir_exists "malformed-pid fresh lock intact" "$L"
rm -rf "$L"

# ============================================================
echo "--- .gc guard: fail-closed, never auto-stolen ---"
# ============================================================
L="$(ait_lock_dir gcheld)"
mkdir "$L"; backdate "$L"     # reclaimable — IF the guard were free
mkdir "$L.gc"; backdate "$L.gc"   # leaked guard, old: still never stolen
err="$(stale_lock_acquire "$L" 3 0.05 "guarded lock" 2>&1)"; rc=$?
assert_exit_nonzero_rc "leaked guard blocks reclaim: acquire fails closed" "$rc"
assert_dir_exists "guard dir never removed" "$L.gc"
assert_dir_exists "stale lock not reclaimed while guard held" "$L"
assert_not_contains "no reclaim happened under a held guard" "Removing stale" "$err"
desc="$(stale_lock_describe "$L")"
assert_contains "describe names the guard dir" "$L.gc" "$desc"

# Release under a held guard: bounded wait, then failure with the lock retained.
printf '%s\n' "$$" > "$L/pid"
printf '%s\n' "tok-gc" > "$L/owner"
err="$(stale_lock_release "$L" "tok-gc" 2>&1)"; rc=$?
assert_exit_nonzero_rc "release under a held guard fails (never silently drops the lock)" "$rc"
assert_dir_exists "lock retained when the guard is busy" "$L"
assert_contains "retained release warns" "NOT released" "$err"
rm -rf "$L.gc"
stale_lock_release "$L" "tok-gc"; rc=$?
assert_exit_zero_rc "release succeeds once the guard is free" "$rc"
assert_dir_not_exists "lock gone after the freed release" "$L"

# ============================================================
echo "--- guard release: rmdir status is authoritative (replacement race) ---"
# ============================================================
# Deterministic reproduction of the guard-replacement race: the guard is the
# one dir another contender may legitimately recreate the instant it is free.
# A rmdir PATH shim performs the REAL removal, instantly recreates the guard
# (the "other contender"), and returns the real rmdir status. Under the old
# "rm -rf + absence check" this misread the replacement as our guard being
# retained: acquire returned 1 and UNWOUND its own valid lock (outside any
# held guard). The fix treats rmdir's own success as authoritative.
L="$(ait_lock_dir gcreplace)"
REAL_RMDIR="$(command -v rmdir)"
mkdir -p "$T/binr"
cat > "$T/binr/rmdir" <<EOF
#!/bin/sh
case "\$*" in
  *"$L.gc")
    "$REAL_RMDIR" "\$@"; rc=\$?
    mkdir "$L.gc" 2>/dev/null   # instant replacement by another contender
    exit \$rc ;;
  *) exec "$REAL_RMDIR" "\$@" ;;
esac
EOF
chmod +x "$T/binr/rmdir"

OLD_PATH="$PATH"
PATH="$T/binr:$PATH"
stale_lock_acquire "$L" 3 0.05 "replacement lock" 2>"$T/err"; rc=$?
PATH="$OLD_PATH"
err="$(cat "$T/err")"
tok="$STALE_LOCK_TOKEN"
assert_exit_zero_rc "acquire succeeds despite an instant guard replacement" "$rc"
assert_dir_exists "the published lock is NOT unwound" "$L"
assert_eq "the lock still records this shell" "$$" "$(cat "$L/pid" 2>/dev/null)"
assert_dir_exists "the replacement guard (another contender's) is left standing" "$L.gc"
assert_not_contains "no spurious retained-guard warn" "retained" "$err"
rm -rf "$L.gc"   # simulate the other contender finishing
stale_lock_release "$L" "$tok"; rc=$?
assert_exit_zero_rc "release with the returned token succeeds afterwards" "$rc"
assert_dir_not_exists "lock gone after release" "$L"

# Release-side replacement: same shim, clean acquire first.
L="$(ait_lock_dir gcreplace2)"
stale_lock_acquire "$L" 3 0.05 "replacement lock 2"
tok="$STALE_LOCK_TOKEN"
OLD_PATH="$PATH"
PATH="$T/binr2:$PATH"
mkdir -p "$T/binr2"
cat > "$T/binr2/rmdir" <<EOF
#!/bin/sh
case "\$*" in
  *"$L.gc")
    "$REAL_RMDIR" "\$@"; rc=\$?
    mkdir "$L.gc" 2>/dev/null
    exit \$rc ;;
  *) exec "$REAL_RMDIR" "\$@" ;;
esac
EOF
chmod +x "$T/binr2/rmdir"
stale_lock_release "$L" "$tok" 2>"$T/err"; rc=$?
PATH="$OLD_PATH"
assert_exit_zero_rc "release succeeds despite an instant guard replacement" "$rc"
assert_dir_not_exists "our lock was removed" "$L"
assert_dir_exists "the replacement guard is left standing after release" "$L.gc"
rm -rf "$L.gc" "$T/binr" "$T/binr2"

# ============================================================
echo "--- guard release: genuine rmdir failure fails closed (publish path) ---"
# ============================================================
L="$(ait_lock_dir gcrmfail)"
mkdir -p "$T/binf"
cat > "$T/binf/rmdir" <<EOF
#!/bin/sh
case "\$*" in
  *"$L.gc") exit 1 ;;
  *) exec "$REAL_RMDIR" "\$@" ;;
esac
EOF
chmod +x "$T/binf/rmdir"
OLD_PATH="$PATH"
PATH="$T/binf:$PATH"
stale_lock_acquire "$L" 3 0.05 "gcrmfail lock" 2>"$T/err"; rc=$?
PATH="$OLD_PATH"
err="$(cat "$T/err")"
assert_exit_nonzero_rc "acquire fails closed when the guard cannot be dropped" "$rc"
assert_dir_not_exists "the just-published lock was unwound under the held guard" "$L"
assert_dir_exists "the genuinely retained guard is still present" "$L.gc"
assert_contains "retained-guard warn names the guard" "guard '$L.gc' retained" "$err"
rm -rf "$L.gc" "$T/binf"

# ============================================================
echo "--- cleanup propagation: failed removal is reported, never masked ---"
# ============================================================
L="$(ait_lock_dir rmfail)"
stale_lock_acquire "$L" 3 0.05 "rmfail lock"
tok="$STALE_LOCK_TOKEN"
REAL_RM="$(command -v rm)"
mkdir -p "$T/bin"
cat > "$T/bin/rm" <<EOF
#!/bin/sh
case "\$*" in
  *" $L") exit 1 ;;
  *) exec "$REAL_RM" "\$@" ;;
esac
EOF
chmod +x "$T/bin/rm"
err="$(PATH="$T/bin:$PATH" stale_lock_release "$L" "$tok" 2>&1)"; rc=$?
assert_exit_nonzero_rc "release with a failing rm returns failure" "$rc"
assert_dir_exists "lock still present after the failed removal" "$L"
assert_contains "failed removal warns about the retained dir" "retained" "$err"
stale_lock_release "$L" "$tok"; rc=$?
assert_exit_zero_rc "release succeeds without the shim" "$rc"

# Bounded reclaim against an unremovable dead lock: terminates, lock intact.
L="$(ait_lock_dir rmfail2)"
mkdir "$L"; backdate "$L"
cat > "$T/bin/rm" <<EOF
#!/bin/sh
case "\$*" in
  *" $L") exit 1 ;;
  *) exec "$REAL_RM" "\$@" ;;
esac
EOF
err="$(PATH="$T/bin:$PATH" stale_lock_acquire "$L" 3 0.05 "unremovable lock" 2>&1)"; rc=$?
assert_exit_nonzero_rc "acquire terminates within budget when reclaim removal fails" "$rc"
assert_dir_exists "unremovable lock intact" "$L"
assert_contains "the failed reclaim removal warned" "retained" "$err"
rm -rf "$L" "$T/bin"

# ============================================================
echo "--- AITASKS_LOCK_DIR seam + per-uid/per-repo default base ---"
# ============================================================
assert_eq "AITASKS_LOCK_DIR is honoured verbatim" "$T/locks/seamcheck" "$(ait_lock_dir seamcheck)"

# Default base: per-uid + repo cksum under TMPDIR. Scope TMPDIR to this test so
# the real /tmp base is never touched.
D1="$T/tmpdir1"; mkdir -p "$D1"
p1="$(unset AITASKS_LOCK_DIR; TMPDIR="$D1" ait_lock_dir defcheck)"
cks="$(printf '%s' "$PROJECT_DIR" | cksum | awk '{print $1}')"
assert_eq "default base is per-uid + repo-cksum under TMPDIR" \
    "$D1/aitask-locks-$(id -u)-$cks/defcheck" "$p1"
perms="$(stat -c %a "$D1/aitask-locks-$(id -u)-$cks" 2>/dev/null || stat -f %Lp "$D1/aitask-locks-$(id -u)-$cks" 2>/dev/null)"
assert_eq "fresh default base is owner-only (0700)" "700" "$perms"

# Two repo roots -> two bases: source a copy of the lib from another root.
FAKE_ROOT="$T/fakerepo"
mkdir -p "$FAKE_ROOT/.aitask-scripts/lib"
cp "$PROJECT_DIR/.aitask-scripts/lib/stale_lock.sh" "$FAKE_ROOT/.aitask-scripts/lib/"
p2="$(unset AITASKS_LOCK_DIR; TMPDIR="$D1" bash -c '
    . "'"$PROJECT_DIR"'/.aitask-scripts/lib/terminal_compat.sh"
    . "'"$FAKE_ROOT"'/.aitask-scripts/lib/stale_lock.sh"
    ait_lock_dir defcheck')"
if [[ "$p1" != "$p2" ]]; then
    assert_eq "two repo roots resolve two distinct bases" "distinct" "distinct"
else
    assert_eq "two repo roots resolve two distinct bases" "distinct" "same:$p2"
fi

# Symlink planted at the predictable base path: refused, target untouched.
D2="$T/tmpdir2"; TARGET="$T/victim"
mkdir -p "$D2" "$TARGET"; chmod 755 "$TARGET"
ln -s "$TARGET" "$D2/aitask-locks-$(id -u)-$cks"
err="$(unset AITASKS_LOCK_DIR; TMPDIR="$D2" ait_lock_dir evil 2>&1)"; rc=$?
assert_exit_nonzero_rc "symlink at the base path is refused" "$rc"
assert_contains "symlink refusal names the problem" "symlink" "$err"
tperms="$(stat -c %a "$TARGET" 2>/dev/null || stat -f %Lp "$TARGET" 2>/dev/null)"
assert_eq "symlink target's permissions untouched" "755" "$tperms"

# ============================================================
echo "--- errexit harness: contention + reclaim cycles under set -euo pipefail ---"
# ============================================================
cat > "$T/harness.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
. "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
. "$PROJECT_DIR/.aitask-scripts/lib/stale_lock.sh"
export AITASKS_LOCK_DIR="$T/locks"
L="\$(ait_lock_dir harness)"
# Cycle 1: reclaim path (pre-staled tokenless lock) -> acquire -> release.
mkdir "\$L"
touch -t 202001010000 "\$L"
stale_lock_acquire "\$L" 5 0.05 "harness lock" 2>/dev/null
stale_lock_release "\$L" "\$STALE_LOCK_TOKEN"
# Cycle 2: bounded contention failure must not kill an errexit script when
# invoked in a condition context (the callers' wrapper shape).
mkdir "\$L"
if stale_lock_acquire "\$L" 2 0.05 "harness lock" 2>/dev/null; then
    echo "UNEXPECTED_ACQUIRE"
    exit 1
fi
rm -rf "\$L"
# Cycle 3: fresh acquire/release round-trip.
stale_lock_acquire "\$L" 3 0.05 "harness lock"
stale_lock_release "\$L" "\$STALE_LOCK_TOKEN"
echo "HARNESS_OK"
EOF
out="$(bash "$T/harness.sh" 2>&1)"; rc=$?
assert_exit_zero_rc "errexit harness completes" "$rc"
assert_contains "errexit harness reaches the end" "HARNESS_OK" "$out"

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
