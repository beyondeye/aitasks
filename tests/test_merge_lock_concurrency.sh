#!/usr/bin/env bash
# test_merge_lock_concurrency.sh - the load-bearing concurrency proofs for the
# Step 9 merge mutex (t1560_1): the red proof, the N>50 case, and the two
# windows force-release must be atomic across.
#
# NO TEST SLEEPS TO REPRODUCE A RACE. Every interleaving is a FIFO rendezvous
# through a documented broker seam, so the ordering is deterministic.
#
# Asserts run at TOP LEVEL (plain PASS/FAIL/TOTAL); only broker invocations are
# subshelled or backgrounded.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

BROKER="$PROJECT_DIR/.aitask-scripts/aitask_merge_task.sh"

AITASKS_LOCK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/test_mergeconc_XXXXXX")"
export AITASKS_LOCK_DIR
LOCKD="$AITASKS_LOCK_DIR/merge"
: > "$AITASKS_LOCK_DIR/.ait_merge_test_seams"        # seams on for this file
TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_mergeconcfx_XXXXXX")"

ANCHORS=""
BGPIDS=""
cleanup() {
    local p
    for p in $BGPIDS  ; do kill "$p" 2>/dev/null || true; done
    for p in $ANCHORS ; do kill "$p" 2>/dev/null || true; done
    rm -rf "$TMP" "$AITASKS_LOCK_DIR"
}
trap cleanup EXIT

spawn_anchor() {
    # stdout/stderr redirected: a background child that inherits the
    # command-substitution pipe would block `$(...)` until it exits.
    sleep 900 >/dev/null 2>&1 &
    local p=$!
    ANCHORS="$ANCHORS $p"
    printf '%s' "$p"
}
free_lock() { rm -rf "$LOCKD" "$LOCKD.gc"; }

# repo <name> <n_clean_branches> — main plus N independent, cleanly-mergeable
# task branches (each touches only its own file).
new_repo() {
    local r="$TMP/$1" n="${2:-2}" i
    rm -rf "$r"; mkdir -p "$r"
    (
        cd "$r" || exit 1
        git init -q -b main .
        git config user.email t@t; git config user.name t
        printf 'base\n' > shared.txt
        git add -A; git commit -qm base
        for (( i=1; i<=n; i++ )); do
            git checkout -q -b "aitask/t$i" main
            printf 'f%s\n' "$i" > "f$i.txt"
            git add -A; git commit -qm "t$i"
        done
        git checkout -q main
        # Diverge main AFTER branching: otherwise the first merge fast-forwards
        # and produces no merge commit, so "one merge commit per caller" would
        # be off by one for reasons that have nothing to do with the mutex.
        printf 'diverged\n' >> shared.txt
        git add -A; git commit -qm diverge
    ) >/dev/null 2>&1
    printf '%s' "$r"
}

echo "========================="
echo "Merge mutex concurrency proofs (t1560_1)"
echo "========================="

# ===========================================================================
# Case 1 / 1n: THE RED PROOF
#
# A parks between checkout and merge; B merges; A resumes. With the mutex
# DISABLED, A's merge commit's tree contains B's file - the concrete
# misattribution this whole task exists to prevent. With the mutex ENABLED the
# same harness must instead see B refused with BUSY, and A's commit clean.
# ===========================================================================
run_red_proof() {   # <mode: disabled|enabled> -> echoes "<B_verdict>|<contaminated:yes/no>"
    local mode="$1" r fifo_reached fifo_go a_anchor b_anchor bverd contam
    r="$(new_repo "red_$mode" 2)"
    fifo_reached="$TMP/reached_$mode"; fifo_go="$TMP/go_$mode"
    rm -f "$fifo_reached" "$fifo_go"; mkfifo "$fifo_reached" "$fifo_go"
    a_anchor="$(spawn_anchor)"; b_anchor="$(spawn_anchor)"
    free_lock

    local dis=""
    [[ "$mode" == "disabled" ]] && dis=1

    # A: parks in the hook, which sits between the checkout and the merge.
    (
        cd "$r" || exit 1
        AIT_AGENT_PID="$a_anchor" \
        AIT_MERGE_LOCK_DISABLED="$dis" \
        AIT_MERGE_BROKER_HOOK="printf 'x' > '$fifo_reached'; read -r _ < '$fifo_go'" \
        "$BROKER" begin tA main aitask/t1 > "$TMP/a_out_$mode" 2>/dev/null
    ) &
    local apid=$!; BGPIDS="$BGPIDS $apid"

    # Rendezvous 1: blocks until A is parked at the hook. No sleep.
    read -r _ < "$fifo_reached"

    # B runs to completion while A is parked.
    bverd="$( cd "$r" && AIT_AGENT_PID="$b_anchor" AIT_MERGE_LOCK_DISABLED="$dis" \
              "$BROKER" begin tB main aitask/t2 --wait-secs 1 2>/dev/null )"

    # Rendezvous 2: let A finish its merge.
    printf 'x' > "$fifo_go"
    wait "$apid" 2>/dev/null || true

    # Did A's merge commit absorb B's file?
    local asha
    asha="$(sed -n 's/^MERGE_OK://p' "$TMP/a_out_$mode" | head -n1)"
    contam=no
    if [[ -n "$asha" ]] && ( cd "$r" && git cat-file -p "$asha^{tree}" 2>/dev/null | grep -q 'f2.txt' ); then
        contam=yes
    fi
    printf '%s|%s' "${bverd:-NONE}" "$contam"
}

echo "--- Case 1: red proof, mutex DISABLED ---"
res="$(run_red_proof disabled)"
b_verdict="${res%%|*}"; contaminated="${res##*|}"
assert_contains "case1(red): with the mutex disabled B merges rather than being refused" "MERGE_OK:" "$b_verdict"
assert_eq "case1(red): A's merge commit CONTAINS B's file - the merge is contaminated" "yes" "$contaminated"

echo "--- Case 1n: negative control - the SAME harness with the mutex ENABLED ---"
res="$(run_red_proof enabled)"
b_verdict="${res%%|*}"; contaminated="${res##*|}"
# Pin the BOUNDARY: B must be refused by the MUTEX (BUSY naming A), not by some
# earlier pre-flight - otherwise "goes green" would prove nothing about locking.
assert_contains "case1n: B is refused by the MUTEX, naming the holder" "BUSY:tA:" "$b_verdict"
assert_not_contains "case1n: not refused by an earlier pre-flight instead" "PREFLIGHT_" "$b_verdict"
assert_not_contains "case1n: not refused by the dirty-tree check instead" "DIRTY_TREE" "$b_verdict"
assert_eq "case1n: and A's commit is clean - the contamination assertion is what flipped" "no" "$contaminated"

echo "--- Case 5: the guard actually gates ---"
# Case 1 vs 1n IS the gate proof: the only difference between the two runs is
# the documented acquisition seam, and the named contamination assertion flips.
assert_eq "case5: removing the acquisition flips the case-1 contamination assertion" "yes" "$(run_red_proof disabled | sed 's/.*|//')"

# ===========================================================================
# Case 2: N = 51 concurrent callers, with an explicit operational contract.
# ===========================================================================
echo "--- Case 2: N=51 concurrent callers ---"
N=51
WAIT_SECS=120          # per-caller lock wait budget
ATTEMPT_CAP=10         # begin attempts per caller before it is a failure
CASE_BUDGET=600        # whole-case wall-clock GUARD (not a perf assertion)
free_lock
R2="$(new_repo n51 "$N")"
mkdir -p "$TMP/n51"
worker() {             # <i> <anchor>
    local i="$1" anchor="$2" attempt=0 out rc
    while :; do
        attempt=$((attempt + 1))
        if [[ "$attempt" -gt "$ATTEMPT_CAP" ]]; then
            printf 'CAP_EXHAUSTED\n' > "$TMP/n51/rc_$i"; return
        fi
        rc=0
        out="$( cd "$R2" && AIT_AGENT_PID="$anchor" "$BROKER" \
                begin "t$i" main "aitask/t$i" --wait-secs "$WAIT_SECS" \
                2>"$TMP/n51/err_$i" )" || rc=$?
        printf '%s\n' "$out" >> "$TMP/n51/out_$i"
        if [[ "$rc" -ne 0 ]]; then printf '%s\n' "$rc" > "$TMP/n51/rc_$i"; return; fi
        case "$out" in
            BUSY:*)     continue ;;                 # retry ONLY on BUSY
            MERGE_OK:*) ( cd "$R2" && AIT_AGENT_PID="$anchor" "$BROKER" finish "t$i" \
                          >>"$TMP/n51/out_$i" 2>/dev/null ) || true
                        printf '0\n' > "$TMP/n51/rc_$i"; return ;;
            *)          printf '0\n' > "$TMP/n51/rc_$i"; return ;;   # any other verdict ends the loop
        esac
    done
}
start=$(date +%s)
wpids=""
for (( i=1; i<=N; i++ )); do
    a="$(spawn_anchor)"
    worker "$i" "$a" >/dev/null 2>&1 &
    wpids="$wpids $!"
done
# Wall-clock GUARD: fail with diagnostics rather than hang.
# Completion is polled through the workers' own rc files. `wait` cannot be used
# from a subshell here - a subshell has no claim on the parent's children and
# returns immediately, which would look like instant completion and kill every
# worker mid-merge. This poll is the wall-clock GUARD, not a race reproduction.
timed_out=0
while :; do
    done_n="$(find "$TMP/n51" -maxdepth 1 -name 'rc_*' 2>/dev/null | grep -c . || true)"
    [[ "$done_n" -ge "$N" ]] && break
    if [[ $(( $(date +%s) - start )) -ge "$CASE_BUDGET" ]]; then timed_out=1; break; fi
    sleep 1
done
# Only ever kill leftovers, and only after the guard expired.
if [[ "$timed_out" -eq 1 ]]; then
    for p in $wpids; do kill "$p" 2>/dev/null || true; done
fi

ok_count=0; rc_bad=0; busy_seen=0; cap_hit=0
for (( i=1; i<=N; i++ )); do
    grep -q '^MERGE_OK:' "$TMP/n51/out_$i" 2>/dev/null && ok_count=$((ok_count + 1))
    # Contention is observable as either verdict: a caller that exhausts its
    # wait returns BUSY, while one that waits and then succeeds reports
    # WAITING:<holder>:<elapsed> on STDERR and returns MERGE_OK.
    { grep -q '^BUSY:' "$TMP/n51/out_$i" 2>/dev/null ||
      grep -q '^WAITING:' "$TMP/n51/err_$i" 2>/dev/null ; } && busy_seen=$((busy_seen + 1))
    r="$(cat "$TMP/n51/rc_$i" 2>/dev/null || echo MISSING)"
    [[ "$r" == "CAP_EXHAUSTED" ]] && cap_hit=$((cap_hit + 1))
    [[ "$r" == "0" ]] || rc_bad=$((rc_bad + 1))
done
merge_commits="$( cd "$R2" && git rev-list --count --merges main )"
distinct="$( cd "$R2" && git log --merges --format=%s main | grep -c "aitask/t" || true )"

if [[ "$timed_out" -eq 1 ]]; then
    echo "DIAGNOSTIC: case 2 exceeded its ${CASE_BUDGET}s wall-clock GUARD."
    echo "  This indicates the wait budget was exhausted under load (environment),"
    echo "  NOT necessarily a wrong verdict (defect). First 3 worker logs:"
    for (( i=1; i<=3; i++ )); do
        echo "--- worker $i out ---"; cat "$TMP/n51/out_$i" 2>/dev/null | head -5
        echo "--- worker $i err ---"; cat "$TMP/n51/err_$i" 2>/dev/null | head -5
    done
fi
assert_eq "case2: the case completed inside its wall-clock guard" "0" "$timed_out"
assert_eq "case2: exactly $N callers reported MERGE_OK" "$N" "$ok_count"
assert_eq "case2: exactly $N merge commits landed on main" "$N" "$merge_commits"
assert_eq "case2: $N distinct task branches were merged (one per logical caller)" "$N" "$distinct"
assert_eq "case2: zero callers exited non-zero or went missing" "0" "$rc_bad"
assert_eq "case2: no caller exhausted its attempt cap" "0" "$cap_hit"
if [[ "$busy_seen" -eq 0 ]]; then
    echo "FAIL: case2: no BUSY/WAITING naming a real holder was ever observed - the case is vacuous"
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
else
    PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
fi
named="$(cat "$TMP/n51"/err_* 2>/dev/null | sed -n 's/^WAITING:\([^:]*\):.*/\1/p' | grep -c '^t[0-9]\+$' || true)"
if [[ "$busy_seen" -gt 0 && "$named" -eq 0 ]]; then
    echo "FAIL: case2: contention was observed but no WAITING line named a real task id"
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
else
    PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
fi
out="$( cd "$R2" && "$BROKER" status 2>/dev/null )"
assert_eq "case2: the lock is FREE afterwards (a leak would poison later cases)" "FREE" "$out"

# ===========================================================================
# Case 12: force-release is atomic against a reclaim.
# ===========================================================================
echo "--- Case 12: force-release revalidates under the guard ---"
free_lock
R12="$(new_repo fr 3)"
A12="$(spawn_anchor)"; B12="$(spawn_anchor)"; C12="$(spawn_anchor)"
( cd "$R12" && AIT_AGENT_PID="$A12" "$BROKER" begin tA main aitask/t1 >/dev/null 2>&1 )
kill "$A12" 2>/dev/null; wait "$A12" 2>/dev/null || true      # holder now provably dead
# Between Read 1 and the guard, a contender reclaims and republishes.
replace="cd '$R12' && AIT_AGENT_PID='$B12' '$BROKER' begin tB main aitask/t2 >/dev/null 2>&1 || true"
out="$( cd "$R12" && AIT_AGENT_PID="$C12" \
        AIT_MERGE_FORCE_HOOK_PREGUARD="$replace" \
        "$BROKER" force-release --yes 2>/dev/null )"
assert_contains "case12: the replacement is detected under the guard" "HOLDER_CHANGED:" "$out"
assert_dir_exists "case12: the NEW holder's reservation was not deleted" "$LOCKD"
out="$( cd "$R12" && AIT_AGENT_PID="$B12" "$BROKER" status 2>/dev/null )"
assert_contains "case12: the new holder is intact" "HELD:tB|" "$out"
out="$( cd "$R12" && AIT_AGENT_PID="$B12" "$BROKER" finish tB 2>/dev/null )"
assert_eq "case12: the new holder can still finish" "RELEASED" "$out"
# --expect closes the cross-invocation gap too.
free_lock
( cd "$R12" && AIT_AGENT_PID="$B12" "$BROKER" begin tB main aitask/t3 >/dev/null 2>&1 )
out="$( cd "$R12" && AIT_AGENT_PID="$C12" "$BROKER" force-release --yes --expect "not-the-holder" 2>/dev/null )"
assert_contains "case12: an --expect mismatch refuses even when reads 1 and 2 agree" "HOLDER_CHANGED:" "$out"
assert_dir_exists "case12: nothing was deleted on the --expect mismatch" "$LOCKD"
free_lock

# ===========================================================================
# Case 13: interrupted recovery terminates.
# ===========================================================================
echo "--- Case 13: interrupted recovery terminates ---"
free_lock
R13="$(new_repo intr 2)"
A13="$(spawn_anchor)"; C13="$(spawn_anchor)"
( cd "$R13" && AIT_AGENT_PID="$A13" "$BROKER" begin tA main aitask/t1 >/dev/null 2>&1 )
kill "$A13" 2>/dev/null; wait "$A13" 2>/dev/null || true
fr_reached="$TMP/fr_reached"; fr_hold="$TMP/fr_hold"
rm -f "$fr_reached" "$fr_hold"; mkfifo "$fr_reached" "$fr_hold"
# Park INSIDE the guarded section on a FIFO read - a BUILTIN, so the INT trap
# runs the moment the signal lands. Parking on `sleep` instead would defer the
# trap until that child exits, and the section would complete uninterrupted
# (which is exactly the false green this comment exists to prevent).
(
    cd "$R13" || exit 1
    # exec, so this subshell's pid IS the broker's: signalling the subshell
    # instead would leave the broker running and holding the guard, and the
    # case would fail for a reason that has nothing to do with the handler.
    exec env AIT_AGENT_PID="$C13" \
        AIT_MERGE_FORCE_HOOK_INGUARD="printf 'x' > '$fr_reached'; read -r _ < '$fr_hold'" \
        "$BROKER" force-release --yes >/dev/null 2>&1
) &
frpid=$!; BGPIDS="$BGPIDS $frpid"
read -r _ < "$fr_reached"                 # rendezvous: it is inside the guard
assert_dir_exists "case13: the guard is held while the section runs" "$LOCKD.gc"
# SIGTERM, not SIGINT: with job control off bash sets SIGINT to IGNORE for a
# background (&) command, and a signal ignored on entry to a shell cannot be
# trapped at all - the handler would never run and this case would silently
# prove nothing. TERM exercises the identical guard handler.
kill -TERM "$frpid" 2>/dev/null || true
# Bounded reap: never let a wedged child turn a failure into a hung suite.
for _ in $(seq 1 100); do kill -0 "$frpid" 2>/dev/null || break; sleep 0.1; done
kill -KILL "$frpid" 2>/dev/null || true
wait "$frpid" 2>/dev/null || true
assert_dir_not_exists "case13: a catchable signal RELEASES the guard" "$LOCKD.gc"
assert_dir_exists "case13: the lock dir is intact with its original holder" "$LOCKD"
out="$( cd "$R13" && "$BROKER" status 2>/dev/null )"
assert_contains "case13: the original holder is still recorded" "tA" "$out"
out="$( cd "$R13" && AIT_AGENT_PID="$C13" "$BROKER" force-release --yes 2>/dev/null )"
assert_contains "case13: a subsequent force-release succeeds" "FORCE_RELEASED:tA" "$out"
out="$( cd "$R13" && AIT_AGENT_PID="$C13" "$BROKER" begin tV main aitask/t2 2>/dev/null )"
assert_contains "case13: usable again, proved by a different cleanly-mergeable task" "MERGE_OK:" "$out"
( cd "$R13" && AIT_AGENT_PID="$C13" "$BROKER" finish tV >/dev/null 2>&1 )

# (b) an UNCATCHABLE kill leaks the guard - invariant 2, deliberately. The
# published recovery must still terminate.
free_lock
mkdir -p "$LOCKD.gc"                       # the state a SIGKILL would leave
D13="$(spawn_anchor)"
out="$( cd "$R13" && AIT_AGENT_PID="$D13" "$BROKER" status 2>&1 )"
assert_contains "case13b: status names the wedged guard and its path" "$LOCKD.gc" "$out"
rmdir "$LOCKD.gc"                          # the documented cure: rmdir, never rm -rf
out="$( cd "$R13" && AIT_AGENT_PID="$D13" "$BROKER" begin tW main aitask/t1 2>/dev/null )"
assert_contains "case13b: after the documented rmdir the lock is usable again" "MERGE_OK:" "$out"
( cd "$R13" && AIT_AGENT_PID="$D13" "$BROKER" finish tW >/dev/null 2>&1 )

echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
