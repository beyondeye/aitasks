#!/usr/bin/env bash
# test_tmpdir_guard.sh - Tests for tests/lib/tmpdir_guard.sh and the
# tests/run_shell_test.sh wrapper (t2290).
#
# The guard runs a test phase under a private per-run TMPDIR, reports what the
# phase left there, and removes it — on normal completion, on a non-zero exit,
# and on INT/TERM (after the phase's whole process group is stopped, so nothing
# still writes into the directory being removed).
#
# Every case runs the REAL wrapper against a stub "test" in a scratch base
# directory, so no guard dir of this file ever lands in the real /tmp.
#
# Run: bash tests/test_tmpdir_guard.sh

set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0; FAIL=0; TOTAL=0

WRAPPER="$PROJECT_DIR/tests/run_shell_test.sh"
GUARD_LIB="$PROJECT_DIR/tests/lib/tmpdir_guard.sh"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/test_tmpdir_guard_XXXXXX")"
cleanup() {
    # Belt and braces: any stub process a failing case left behind.
    if [[ -f "$WORK/pids" ]]; then
        while IFS= read -r p; do kill -KILL "$p" 2>/dev/null || true; done < "$WORK/pids"
    fi
    chmod -R u+w "$WORK" 2>/dev/null || true
    rm -rf "$WORK"
}
trap cleanup EXIT

BASE="$WORK/base"          # the "original TMPDIR" every guarded run sees
mkdir -p "$BASE"

# The stub test. Args: <tag> <sleep-seconds> <exit-status> [writer|readonly|clean]
STUB="$WORK/stub.sh"
cat > "$STUB" <<'EOF'
tag="$1"; nap="$2"; status="$3"; mode="${4:-}"
echo "$$" >> "$STUB_PIDS"
case "$mode" in
    clean)    : ;;
    readonly) mkdir -p "$TMPDIR/ro_$tag/sub"; touch "$TMPDIR/ro_$tag/sub/f"
              chmod a-w "$TMPDIR/ro_$tag/sub" "$TMPDIR/ro_$tag" ;;
    *)        touch "$TMPDIR/leak_$tag" ;;
esac
if [[ "$mode" == writer ]]; then
    ( while :; do echo x >> "$TMPDIR/writer_$tag.log" 2>/dev/null; sleep 0.1; done ) &
    echo "$!" >> "$STUB_PIDS"
fi
sleep "$nap"
exit "$status"
EOF
export STUB_PIDS="$WORK/pids"

# run_guarded <outfile> <stub args...> — run the wrapper synchronously; prints rc.
run_guarded() {
    local out="$1"; shift
    TMPDIR="$BASE" bash "$WRAPPER" "$STUB" "$@" </dev/null >"$out" 2>&1
    echo "$?"
}

guard_dirs() { find "$BASE" -mindepth 1 -maxdepth 1 -name 'ait_shrun_*' | wc -l | tr -d ' '; }

no_live_stub_pids() {
    local p alive=""
    [[ -f "$STUB_PIDS" ]] || { echo yes; return; }
    while IFS= read -r p; do kill -0 "$p" 2>/dev/null && alive="$alive $p"; done < "$STUB_PIDS"
    [[ -z "$alive" ]] && echo yes || echo "no:$alive"
}

echo "=== (a) a leftover is reported, removed, and the status passes through ==="
rc="$(run_guarded "$WORK/a0.out" a0 0 0)"
assert_eq "a: exit 0 passes through" "0" "$rc"
assert_contains "a: report names the leftover" "TMPDIR LEFTOVERS (1): leak_a0" "$(cat "$WORK/a0.out")"
assert_eq "a: guard dir removed" "0" "$(guard_dirs)"
rc="$(run_guarded "$WORK/a3.out" a3 0 3)"
assert_eq "a: exit 3 passes through" "3" "$rc"
assert_contains "a: report on a failing run too" "leak_a3" "$(cat "$WORK/a3.out")"
assert_eq "a: guard dir removed after a failing run" "0" "$(guard_dirs)"

echo "=== (b) a clean run prints no report ==="
rc="$(run_guarded "$WORK/b.out" b 0 0 clean)"
assert_eq "b: exit 0" "0" "$rc"
assert_not_contains "b: no leftover report" "TMPDIR LEFTOVERS" "$(cat "$WORK/b.out")"
assert_eq "b: guard dir removed" "0" "$(guard_dirs)"

echo "=== (c) a read-only leftover is still removed ==="
rc="$(run_guarded "$WORK/c.out" c 0 0 readonly)"
assert_contains "c: report names it" "ro_c" "$(cat "$WORK/c.out")"
assert_eq "c: guard dir removed despite a-w" "0" "$(guard_dirs)"

echo "=== (d) TERM: group stopped, then cleaned, exit 143 ==="
: > "$STUB_PIDS"
TMPDIR="$BASE" bash "$WRAPPER" "$STUB" d 30 0 writer </dev/null >"$WORK/d.out" 2>&1 &
wpid=$!
for _ in $(seq 1 50); do [[ "$(wc -l < "$STUB_PIDS" | tr -d ' ')" -ge 2 ]] && break; sleep 0.1; done
sleep 0.3
kill -TERM "$wpid"
wait "$wpid"; rc=$?
assert_eq "d: exit status is 128+TERM" "143" "$rc"
assert_contains "d: report printed" "TMPDIR LEFTOVERS" "$(cat "$WORK/d.out")"
assert_eq "d: guard dir removed" "0" "$(guard_dirs)"
assert_eq "d: no stub process (leader or writer) survives" "yes" "$(no_live_stub_pids)"
sleep 1
assert_eq "d: nothing recreated after removal" "0" "$(guard_dirs)"

echo "=== (e) INT behaves the same, exit 130 ==="
: > "$STUB_PIDS"
# `set -m` for the launch only: a background job of a non-job-control shell
# starts with SIGINT IGNORED, and bash cannot trap a signal ignored on entry —
# so without it this would test the harness, not the guard. A real Ctrl-C
# reaches a foreground wrapper with INT intact.
set -m
TMPDIR="$BASE" bash "$WRAPPER" "$STUB" e 30 0 writer </dev/null >"$WORK/e.out" 2>&1 &
wpid=$!
set +m
for _ in $(seq 1 50); do [[ "$(wc -l < "$STUB_PIDS" | tr -d ' ')" -ge 2 ]] && break; sleep 0.1; done
sleep 0.3
kill -INT "$wpid"
wait "$wpid"; rc=$?
assert_eq "e: exit status is 128+INT" "130" "$rc"
assert_eq "e: guard dir removed" "0" "$(guard_dirs)"
assert_eq "e: no stub process survives" "yes" "$(no_live_stub_pids)"

echo "=== (s) strays left in the group on NORMAL exit are stopped first ==="
: > "$STUB_PIDS"
rc="$(run_guarded "$WORK/s.out" s 0 0 writer)"
assert_eq "s: exit 0 passes through" "0" "$rc"
assert_contains "s: stray processes are announced" "left process(es) running" "$(cat "$WORK/s.out")"
assert_eq "s: the backgrounded writer was stopped" "yes" "$(no_live_stub_pids)"
sleep 1
assert_eq "s: nothing recreated after removal" "0" "$(guard_dirs)"

echo "=== (f) a dead owner's guard dir is reported, never deleted ==="
dead_pid="$(bash -c 'echo $$')"
stale="$BASE/ait_shrun_${dead_pid}_OLDRUN"
mkdir -p "$stale"; echo keep > "$stale/data"
sleep 300 & live_pid=$!
live="$BASE/ait_shrun_${live_pid}_LIVERN"
mkdir -p "$live"
rc="$(run_guarded "$WORK/f.out" f 0 0 clean)"
kill "$live_pid" 2>/dev/null; wait "$live_pid" 2>/dev/null
assert_contains "f: the dead owner's dir is reported" "ait_shrun_${dead_pid}_OLDRUN" "$(cat "$WORK/f.out")"
assert_not_contains "f: a live (concurrent) run's dir is not reported" "LIVERN" "$(cat "$WORK/f.out")"
assert_eq "f: the stale dir and its contents are left in place" "keep" "$(cat "$stale/data" 2>/dev/null)"
rm -rf "$stale" "$live"

echo "=== (g) an existing EXIT trap is chained, not clobbered ==="
out="$(TMPDIR="$BASE" bash -c '
    trap "echo PRIOR_EXIT_RAN" EXIT
    . "'"$GUARD_LIB"'"
    tmpdir_guard_begin probe || exit 9
    touch "$TMPDIR/leak_g"
    exit 4
' 2>&1)"
rc=$?
assert_eq "g: status survives both handlers" "4" "$rc"
assert_contains "g: the guard handler ran" "leak_g" "$out"
assert_contains "g: the prior EXIT handler still ran" "PRIOR_EXIT_RAN" "$out"
assert_eq "g: guard dir removed" "0" "$(find "$BASE" -mindepth 1 -maxdepth 1 -name 'ait_probe_*' | wc -l | tr -d ' ')"

echo "=== (j) existing HUP/INT/TERM handlers are kept, and the guard still exits 128+n ==="
# `trap -p` spells signals its own way (SIGTERM, not TERM) and quotes the action
# ('a'\''b' for an embedded quote). Both used to defeat the composition: the
# eval failed, begin still returned 0, and a signal ran only the old handler and
# carried on (t2290 review).
PROBE_J="$WORK/probe_j.sh"
cat > "$PROBE_J" <<'EOF'
sig="$1"
trap 'echo "PRIOR_${sig}_RAN it'\''s quoted"' "$sig"
trap 'echo "PRIOR_EXIT_RAN it'\''s quoted"' EXIT
. "$GUARD_LIB"
tmpdir_guard_begin probe || exit 9
touch "$TMPDIR/leak_j"
kill -"$sig" $$
sleep 2
echo "CONTINUED_PAST_${sig}"
exit 0
EOF
for pair in HUP:129 INT:130 TERM:143; do
    sig="${pair%%:*}"; want="${pair#*:}"
    out="$(TMPDIR="$BASE" GUARD_LIB="$GUARD_LIB" bash "$PROBE_J" "$sig" 2>&1)"
    rc=$?
    assert_eq "j/$sig: exit is 128+n" "$want" "$rc"
    assert_contains "j/$sig: the prior quoted $sig handler ran intact" "PRIOR_${sig}_RAN it's quoted" "$out"
    assert_contains "j/$sig: the prior quoted EXIT handler ran intact" "PRIOR_EXIT_RAN it's quoted" "$out"
    assert_not_contains "j/$sig: execution did not continue past the signal" "CONTINUED_PAST_${sig}" "$out"
    assert_contains "j/$sig: the leftover was reported" "leak_j" "$out"
    assert_eq "j/$sig: guard dir removed" "0" "$(find "$BASE" -mindepth 1 -maxdepth 1 -name 'ait_probe_*' | wc -l | tr -d ' ')"
done

echo "=== (k) an ignored signal does not make the guarded run uninterruptible ==="
out="$(TMPDIR="$BASE" bash -c '
    trap "" TERM
    . "'"$GUARD_LIB"'"
    tmpdir_guard_begin probe || exit 9
    kill -TERM $$
    sleep 2
    echo CONTINUED_PAST_TERM
' 2>&1)"
rc=$?
assert_eq "k: exit is 143" "143" "$rc"
assert_not_contains "k: execution did not continue" "CONTINUED_PAST_TERM" "$out"
assert_eq "k: guard dir removed" "0" "$(find "$BASE" -mindepth 1 -maxdepth 1 -name 'ait_probe_*' | wc -l | tr -d ' ')"

echo "=== (l) traps that did not install make begin back out, not report success ==="
out="$(TMPDIR="$BASE" bash -c '
    trap "echo PRIOR" TERM
    . "'"$GUARD_LIB"'"
    _tg_append_signal_trap() { :; }     # simulate a composition that installs nothing
    tmpdir_guard_begin probe; echo "begin_rc=$?"
    echo "tmpdir_now=$TMPDIR"
' 2>&1)"
assert_contains "l: begin returns non-zero" "begin_rc=2" "$out"
assert_contains "l: it says it runs unguarded" "running unguarded" "$out"
assert_contains "l: TMPDIR is restored" "tmpdir_now=$BASE" "$out"
assert_eq "l: no guard dir is left" "0" "$(find "$BASE" -mindepth 1 -maxdepth 1 -name 'ait_probe_*' | wc -l | tr -d ' ')"

echo "=== (m) a prior signal handler that EXITS still gets the phase stopped before cleanup ==="
# The guard's signal action is appended after the caller's handler, so a
# handler that calls `exit` makes it unreachable; the EXIT-path cleanup then
# removed the directory while the phase was still running (t2290 review).
PROBE_M="$WORK/probe_m.sh"
cat > "$PROBE_M" <<'EOF'
trap 'exit 0' TERM
. "$GUARD_LIB"
tmpdir_guard_begin probe || exit 9
printf '%s\n' "$TMPDIR" > "$M_DIR_FILE"
tmpdir_guard_run bash -c 'echo $$ > "$M_PID_FILE"; while :; do touch "$TMPDIR/m_tick_$RANDOM"; sleep 0.1; done'
EOF
M_PID_FILE="$WORK/m.pid"; M_DIR_FILE="$WORK/m.dir"; rm -f "$M_PID_FILE" "$M_DIR_FILE"
TMPDIR="$BASE" GUARD_LIB="$GUARD_LIB" M_PID_FILE="$M_PID_FILE" M_DIR_FILE="$M_DIR_FILE" \
    bash "$PROBE_M" > "$WORK/m.out" 2>&1 </dev/null &
m_wrapper=$!
for _ in $(seq 1 50); do [[ -s "$M_PID_FILE" ]] && break; sleep 0.1; done
sleep 0.3
kill -TERM "$m_wrapper"
wait "$m_wrapper"; rc=$?
m_child="$(cat "$M_PID_FILE" 2>/dev/null)"
m_dir="$(cat "$M_DIR_FILE" 2>/dev/null)"
assert_eq "m: the caller's handler decides the status (exit 0)" "0" "$rc"
TOTAL=$((TOTAL + 1))
if [[ -n "$m_child" ]] && ! kill -0 "$m_child" 2>/dev/null; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: m: the phase child ($m_child) is still alive"; kill -KILL "$m_child" 2>/dev/null; fi
sleep 1
TOTAL=$((TOTAL + 1))
if [[ -n "$m_dir" && ! -e "$m_dir" ]]; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: m: guard dir '$m_dir' exists after the run (left or recreated)"; fi
assert_contains "m: it says it stopped the phase first" "stopping its process group first" "$(cat "$WORK/m.out")"

echo "=== (h) TMPDIR is restored, and pytest's own base is not reported ==="
out="$(TMPDIR="$BASE" bash -c '
    . "'"$GUARD_LIB"'"
    tmpdir_guard_begin probe || exit 9
    mkdir -p "$TMPDIR/pytest-of-someone"
    tmpdir_guard_end
    echo "after=$TMPDIR"
' 2>&1)"
assert_contains "h: TMPDIR restored to the original" "after=$BASE" "$out"
assert_not_contains "h: pytest-of-* is expected, not a leftover" "TMPDIR LEFTOVERS" "$out"

echo "=== (i) a base under /.claude/ is refused, the run proceeds unguarded ==="
mkdir -p "$WORK/home/.claude/x"
out="$(TMPDIR="$WORK/home/.claude/x" bash "$WRAPPER" "$STUB" i 0 0 clean </dev/null 2>&1)"; rc=$?
assert_eq "i: the test still runs and its status passes through" "0" "$rc"
assert_contains "i: the refusal is reported" "refusing a guard directory" "$out"
assert_eq "i: no guard dir was created there" "0" "$(find "$WORK/home/.claude/x" -mindepth 1 -maxdepth 1 -name 'ait_*' | wc -l | tr -d ' ')"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]] || exit 1
echo "ALL TESTS PASSED"
