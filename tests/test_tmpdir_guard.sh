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
# shellcheck source=lib/proc_fixtures.sh
. "$PROJECT_DIR/tests/lib/proc_fixtures.sh"
PASS=0; FAIL=0; TOTAL=0

WRAPPER="$PROJECT_DIR/tests/run_shell_test.sh"
GUARD_LIB="$PROJECT_DIR/tests/lib/tmpdir_guard.sh"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/test_tmpdir_guard_XXXXXX")"
cleanup() {
    # Belt and braces: any stub process a failing case left behind.
    if [[ -f "$WORK/pids" ]]; then
        while IFS= read -r p; do kill -KILL "$p" 2>/dev/null || true; done < "$WORK/pids"
    fi
    chmod -R u+rwX "$WORK" 2>/dev/null || true   # rwX: case (w) makes mode-000 dirs
    rm -rf "$WORK"
}
trap cleanup EXIT

# Default-mode cases must not inherit the caller's strict setting (this suite
# itself may run under `AIT_TMPDIR_GUARD_STRICT=1 run_shell_test.sh`); the
# strict cases set it explicitly (t2302).
unset AIT_TMPDIR_GUARD_STRICT

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

echo "=== (f) a dead owner's guard dir WITHOUT run metadata is reported, never deleted ==="
dead_pid="$(bash -c 'echo $$')"
stale="$BASE/ait_shrun_${dead_pid}_OLDRUN"
mkdir -p "$stale"; echo keep > "$stale/data"
sleep 300 & live_pid=$!
live="$BASE/ait_shrun_${live_pid}_LIVERN"
mkdir -p "$live"
rc="$(run_guarded "$WORK/f.out" f 0 0 clean)"
kill "$live_pid" 2>/dev/null; wait "$live_pid" 2>/dev/null
assert_contains "f: the dead owner's dir is reported" "ait_shrun_${dead_pid}_OLDRUN" "$(cat "$WORK/f.out")"
assert_contains "f: with the no-metadata reason" "ait_shrun_${dead_pid}_OLDRUN(no-metadata)" "$(cat "$WORK/f.out")"
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

echo "=== (n) strict mode: exit 0 means inspected and clean (t2302) ==="
rc="$(AIT_TMPDIR_GUARD_STRICT=1 run_guarded "$WORK/k1.out" k1 0 0)"
assert_eq "n: a passing run with a leftover fails under strict" "1" "$rc"
assert_contains "n: strict names the reason" "strict mode — leftovers" "$(cat "$WORK/k1.out")"
assert_eq "n: the guard dir is still removed" "0" "$(guard_dirs)"
rc="$(AIT_TMPDIR_GUARD_STRICT=1 run_guarded "$WORK/k2.out" k2 0 0 clean)"
assert_eq "n: a clean passing run passes under strict" "0" "$rc"
rc="$(AIT_TMPDIR_GUARD_STRICT=1 run_guarded "$WORK/k3.out" k3 0 3 clean)"
assert_eq "n: a failing run keeps its own status under strict" "3" "$rc"
rc="$(run_guarded "$WORK/k4.out" k4 0 0)"
assert_eq "n: the default stays warn-only" "0" "$rc"
# A guard that cannot start must not let strict run the test unguarded.
MARK_STUB="$WORK/mark.sh"
printf ': > "%s"\n' "$WORK/k_marker" > "$MARK_STUB"
rm -f "$WORK/k_marker"
out="$(TMPDIR="$WORK/no/such/dir" AIT_TMPDIR_GUARD_STRICT=1 bash "$WRAPPER" "$MARK_STUB" </dev/null 2>&1)"; rc=$?
assert_eq "n: strict refuses when the guard cannot start" "2" "$rc"
assert_contains "n: the refusal is explained" "strict mode needs the guard" "$out"
assert_eq "n: the test did not run" "absent" "$([[ -e "$WORK/k_marker" ]] && echo present || echo absent)"
out="$(TMPDIR="$WORK/no/such/dir" bash "$WRAPPER" "$MARK_STUB" </dev/null 2>&1)"; rc=$?
assert_eq "n: default mode still runs unguarded" "0" "$rc"
assert_eq "n: and the test did run" "present" "$([[ -e "$WORK/k_marker" ]] && echo present || echo absent)"

echo "=== (o) a guard dir replaced by a file or link is not attested clean (t2302) ==="
# Each stub swaps the guard directory itself for something else, then passes.
o_run() {  # o_run <tag> <body>; prints rc
    local stub="$WORK/o_$1.sh"
    printf '%s\n' "$2" > "$stub"
    TMPDIR="$BASE" AIT_TMPDIR_GUARD_STRICT=1 bash "$WRAPPER" "$stub" </dev/null >"$WORK/o_$1.out" 2>&1
    echo "$?"
}
o_left() { find "$BASE" -mindepth 1 -maxdepth 1 \( -name 'ait_shrun_*' \) | wc -l | tr -d ' '; }
# shellcheck disable=SC2016  # the body expands inside the stub, not here
rc="$(o_run file 'rmdir "$TMPDIR" && printf leftover > "$TMPDIR"')"
assert_eq "o: replaced by a regular file -> strict fails" "1" "$rc"
assert_contains "o: the replacement is reported" "replaced by a symlink or non-directory" "$(cat "$WORK/o_file.out")"
assert_eq "o: the regular file is removed" "0" "$(o_left)"
# shellcheck disable=SC2016  # the body expands inside the stub, not here
rc="$(o_run dangling 'rmdir "$TMPDIR" && ln -s /nonexistent/t2302 "$TMPDIR"')"
assert_eq "o: replaced by a dangling symlink -> strict fails" "1" "$rc"
assert_eq "o: the dangling link is removed" "0" "$(o_left)"
mkdir -p "$WORK/o_target"; : > "$WORK/o_target/keep"
rc="$(o_run dirlink "rmdir \"\$TMPDIR\" && ln -s '$WORK/o_target' \"\$TMPDIR\"")"
assert_eq "o: replaced by a symlink to a directory -> strict fails" "1" "$rc"
assert_eq "o: the link is removed" "0" "$(o_left)"
assert_eq "o: the link's target is never touched" "yes" "$([[ -e "$WORK/o_target/keep" ]] && echo yes || echo no)"
# shellcheck disable=SC2016  # the body expands inside the stub, not here
rc="$(o_run gone 'rmdir "$TMPDIR"')"
assert_eq "o: a guard dir that is truly gone left nothing -> strict passes" "0" "$rc"

# ---------------------------------------------------------------------------
# Killed runs (t2301): run metadata, and reclaim only on positive evidence.
#
# Every KEEP case below runs its probe against a fake proc root on which the
# holder scan (step 4) would succeed, so the only thing that can keep the dir
# is the guard the case targets — against the real /proc a non-root host keeps
# everything (uninspectable processes) and the assertion would pass vacuously.
# Cases that need the real /proc assert the specific reason instead.
# ---------------------------------------------------------------------------

META_SUFFIX=".ait_guard_meta"

# probe <label> <proc-root|-> <outfile> — one guarded begin/end under $BASE
# ("-" keeps the real /proc). Neither the probe's cmdline nor its environment
# names a candidate dir: the holder scan would find the probe itself.
probe() {
    TMPDIR="$BASE" GUARD_LIB="$GUARD_LIB" P_LABEL="$1" P_ROOT="$2" bash -c '
        . "$GUARD_LIB"
        [[ "$P_ROOT" == - ]] || _TG_PROC_ROOT="$P_ROOT"
        [[ -z "${P_EUID:-}" ]] || _TG_EUID="$P_EUID"
        [[ -z "${P_OSTYPE:-}" ]] || _TG_OSTYPE="$P_OSTYPE"
        [[ -z "${P_SELF_MOUNTS:-}" ]] || _TG_SELF_MOUNTS="$P_SELF_MOUNTS"
        [[ -z "${P_PRELUDE:-}" ]] || eval "$P_PRELUDE"
        tmpdir_guard_begin "$P_LABEL" || exit 9
        tmpdir_guard_end
    ' </dev/null >"$3" 2>&1
}

# make_stale <label> <name_pid> <suffix> [meta-line...] — a guard dir as a
# killed run leaves it (with a data file), plus its control dir and metadata
# when lines are given (each newline-terminated). Sets STALE_DIR, STALE_CTL and
# STALE_META; `put_meta` writes STALE_META from stdin.
make_stale() {
    local label="$1" pid="$2" suffix="$3"; shift 3
    STALE_DIR="$BASE/ait_${label}_${pid}_${suffix}"
    STALE_CTL="$BASE/.ait_${label}_${pid}_${suffix}${META_SUFFIX}"
    STALE_META="$STALE_CTL/meta"
    mkdir -p "$STALE_DIR"; echo keep > "$STALE_DIR/data"
    if (( $# > 0 )); then printf '%s\n' "$@" | put_meta; fi
}
put_meta() { [[ -d "$STALE_CTL" ]] || mkdir -m 700 "$STALE_CTL"; cat > "$STALE_META"; }

# A well-formed metadata body for a dead owner and a dead (empty) pgid.
dead_meta() {  # dead_meta <owner_pid> <pgid>
    printf '%s\n' "ait_tmpdir_guard_meta 1" "owner $1 proc 1" "phase_start 1" "phase 1 $2"
}

clear_probe_stale() {
    chmod -R u+rwX "$BASE" 2>/dev/null || true
    rm -rf "$BASE"/ait_probe_* "$BASE"/.ait_probe_* "$BASE"/ait_shrun_* "$BASE"/.ait_shrun_*
}

# fx_proc <root> <pid> <cwd> <fd0> <environ-entry> [state] [cmdline-arg] — one
# fake process: inspectable unless a case breaks it.
fx_proc() {
    local d="$1/$2"
    mkdir -p "$d/task/$2" "$d/fd"
    printf '%s (fixt proc) %s 1 %s 0 0\n' "$2" "${6:-S}" "$2" > "$d/stat"
    ln -s "$3" "$d/task/$2/cwd"
    ln -s "$4" "$d/fd/0"
    printf '%s\0PATH=/usr/bin\0' "$5" > "$d/environ"
    printf 'fixt\0%s\0' "${7:---flag}" > "$d/cmdline"
}
# fx_net <root> <socket-path> — a net/unix with one bound socket.
fx_net() {
    mkdir -p "$1/net"
    printf 'Num       RefCount Protocol Flags    Type St Inode Path\n0000000000000000: 00000002 00000000 00010000 0001 01 12345 %s\n' "$2" > "$1/net/unix"
}
# fx_mounts <root> <options> — the root's own proc mount entry.
fx_mounts() {
    printf 'proc %s proc %s 0 0\n' "$(cd "$1" && pwd -P)" "$2" > "$1/mounts"
}
# fresh_root <root> — one unrelated, fully inspectable process; an unrelated
# socket; a proc mount without hidepid.
fresh_root() {
    chmod -R u+rwX "$1" 2>/dev/null || true
    rm -rf "$1"; mkdir -p "$1"
    fx_proc "$1" 4242 / /dev/null HOME=/nowhere
    fx_net "$1" /run/unrelated.sock
    fx_mounts "$1" rw,nosuid,nodev,noexec,relatime
}
FX="$WORK/fxroot"

echo "=== (p) a run records its owner and each phase's pgid BESIDE its dir (t2301) ==="
out="$(TMPDIR="$BASE" GUARD_LIB="$GUARD_LIB" bash -c '
    . "$GUARD_LIB"
    tmpdir_guard_begin probe || exit 9
    c="${TMPDIR%/*}/.${TMPDIR##*/}.ait_guard_meta"
    echo "inside=$(ls -A "$TMPDIR" | wc -l | tr -d " ")"
    echo "ctlmode=$(find "$c" -prune -perm 700 -type d | wc -l | tr -d " ")"
    tmpdir_guard_run true
    tmpdir_guard_run true
    echo "self=$$"
    sed "s/^/META:/" "$c/meta"
    tmpdir_guard_end
    [[ -e "$c" ]] && echo meta_left || echo meta_gone
' 2>&1)"
p_self="$(printf '%s\n' "$out" | sed -n 's/^self=//p')"
assert_contains "p: the header is written" "META:ait_tmpdir_guard_meta 1" "$out"
TOTAL=$((TOTAL + 1))
if printf '%s\n' "$out" | grep -qE "^META:owner $p_self (proc|bsdinfo|ps) [[:graph:]]+$"; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: p: owner line with a real identity for pid $p_self"; printf '%s\n' "$out"; fi
assert_contains "p: phase 1 announced before its fork" "META:phase_start 1" "$out"
assert_contains "p: phase 2 announced before its fork" "META:phase_start 2" "$out"
TOTAL=$((TOTAL + 1))
if [[ "$(printf '%s\n' "$out" | grep -cE '^META:phase [12] [0-9]+$')" == 2 ]]; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: p: both phases recorded with a pgid"; printf '%s\n' "$out"; fi
assert_contains "p: the phase sees an empty TMPDIR (metadata is not inside it)" "inside=0" "$out"
assert_contains "p: the control dir is a private (0700) directory" "ctlmode=1" "$out"
assert_contains "p: end removes the metadata with the dir" "meta_gone" "$out"
assert_not_contains "p: a clean run reports nothing" "TMPDIR" "$(printf '%s\n' "$out" | grep -v '^META:\|^inside=\|^self=\|^ctlmode=')"
assert_eq "p: nothing left under the base" "0" "$(find "$BASE" -mindepth 1 -maxdepth 1 -name '*ait_probe_*' | wc -l | tr -d ' ')"

echo "=== (q) reclaimed when owner, pgid and every process are verifiably gone ==="
clear_probe_stale; fresh_root "$FX"
q_owner="$(dead_pid_fixture)"; q_pg="$(dead_pid_fixture)"
make_stale probe "$q_owner" QDEAD
dead_meta "$q_owner" "$q_pg" | put_meta
q_dir="$STALE_DIR"; q_meta="$STALE_CTL"
orphan="$BASE/.ait_probe_${q_pg}_ORPHAN${META_SUFFIX}"    # metadata whose dir was removed by hand
mkdir -m 700 "$orphan"; dead_meta "$q_pg" "$q_pg" > "$orphan/meta"
probe probe "$FX" "$WORK/q.out"
assert_eq "q: the stale dir is reclaimed" "gone" "$([[ -e "$q_dir" ]] && echo present || echo gone)"
assert_eq "q: its metadata goes with it" "gone" "$([[ -e "$q_meta" ]] && echo present || echo gone)"
assert_contains "q: the reclaim is reported" "reclaimed 1 guard dir(s) left by killed runs" "$(cat "$WORK/q.out")"
assert_contains "q: by name" "ait_probe_${q_owner}_QDEAD" "$(cat "$WORK/q.out")"
assert_eq "q: orphaned metadata (dir gone) is dropped" "gone" "$([[ -e "$orphan" ]] && echo present || echo gone)"

echo "=== (r) a recycled owner pid reads dead; the real owner reads live ==="
clear_probe_stale; fresh_root "$FX"
sleep 300 & r_pid=$!; echo "$r_pid" >> "$STUB_PIDS"
r_ident="$(bash -c '. "$1"; get_pid_identity "$2"' _ "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh" "$r_pid")"
r_pg="$(dead_pid_fixture)"
make_stale probe "$r_pid" RWRONG "ait_tmpdir_guard_meta 1" "owner $r_pid proc 999999999999" "phase_start 1" "phase 1 $r_pg"
r_wrong="$STALE_DIR"
probe probe "$FX" "$WORK/r1.out"
assert_eq "r: a live pid with the wrong start-time token is a recycled pid -> reclaimed" "gone" "$([[ -e "$r_wrong" ]] && echo present || echo gone)"
make_stale probe "$r_pid" RREAL "ait_tmpdir_guard_meta 1" "owner $r_pid $r_ident" "phase_start 1" "phase 1 $r_pg"
r_real="$STALE_DIR"
probe probe "$FX" "$WORK/r2.out"
assert_eq "r: control — the real owner (matching token) keeps its dir" "keep" "$(cat "$r_real/data" 2>/dev/null)"
assert_not_contains "r: control — a live run is not reported" "RREAL" "$(cat "$WORK/r2.out")"
kill "$r_pid" 2>/dev/null; wait "$r_pid" 2>/dev/null

echo "=== (t) a killed wrapper whose writer survives keeps its dir until the writer dies ==="
clear_probe_stale; fresh_root "$FX"
: > "$STUB_PIDS"
TMPDIR="$BASE" bash "$WRAPPER" "$STUB" t 300 0 writer </dev/null >"$WORK/t.out" 2>&1 &
t_wrap=$!
t_meta=""; t_pg=""
for _ in $(seq 1 100); do
    t_meta="$(find "$BASE" -mindepth 1 -maxdepth 1 -type d -name ".ait_shrun_${t_wrap}_*${META_SUFFIX}" | head -n1)"
    [[ -n "$t_meta" ]] && t_pg="$(sed -n 's/^phase 1 \([0-9][0-9]*\)$/\1/p' "$t_meta/meta" 2>/dev/null)"
    [[ -n "$t_pg" && "$(wc -l < "$STUB_PIDS" | tr -d ' ')" -ge 2 ]] && break
    sleep 0.1
done
t_dir="$(find "$BASE" -mindepth 1 -maxdepth 1 -type d -name "ait_shrun_${t_wrap}_*" | head -n1)"
kill -KILL "$t_wrap"; wait "$t_wrap" 2>/dev/null
sleep 0.3
TOTAL=$((TOTAL + 1))
if [[ -n "$t_pg" ]] && kill -0 -- "-$t_pg" 2>/dev/null; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: t: setup — the writer's group ($t_pg) should outlive the SIGKILLed wrapper"; fi
probe shrun "$FX" "$WORK/t1.out"
assert_contains "t: kept while the recorded pgid has members" "${t_dir##*/}(pgid-live:$t_pg)" "$(cat "$WORK/t1.out")"
assert_eq "t: the dir and the writer's data are intact" "yes" "$([[ -s "$t_dir/writer_t.log" ]] && echo yes || echo no)"
kill -KILL -- "-$t_pg" 2>/dev/null
for _ in $(seq 1 50); do kill -0 -- "-$t_pg" 2>/dev/null || break; sleep 0.1; done
probe shrun "$FX" "$WORK/t2.out"
assert_contains "t: once the group is gone the next run reclaims it" "reclaimed 1 guard dir(s)" "$(cat "$WORK/t2.out")"
assert_eq "t: the dir is gone" "gone" "$([[ -e "$t_dir" ]] && echo present || echo gone)"
assert_eq "t: its metadata is gone" "gone" "$([[ -e "$t_meta" ]] && echo present || echo gone)"

echo "=== (u) a process whose cwd is inside the dir keeps it (real /proc) ==="
clear_probe_stale
if [[ -d /proc/self/fd ]]; then
    u_owner="$(dead_pid_fixture)"; u_pg="$(dead_pid_fixture)"
    make_stale probe "$u_owner" UCWD
    dead_meta "$u_owner" "$u_pg" | put_meta
    u_dir="$STALE_DIR"
    ( cd "$u_dir" && exec sleep 300 ) & u_hold=$!
    echo "$u_hold" >> "$STUB_PIDS"
    for _ in $(seq 1 50); do [[ "$(readlink "/proc/$u_hold/cwd" 2>/dev/null)" == "$(cd "$u_dir" && pwd -P)" ]] && break; sleep 0.1; done
    probe probe - "$WORK/u.out"
    # The holder is only reachable when this host's /proc lists every process;
    # with hidepid=2/4 (or no readable proc entry) the guard keeps the dir
    # BEFORE scanning, by design. Both branches also run on fixtures: v/cwd, (y).
    if [[ -r /proc/mounts ]] && grep -qE '^[^ ]+ /proc proc ' /proc/mounts \
       && ! grep -qE '^[^ ]+ /proc proc [^ ]*hidepid=(2|4|invisible|ptraceable)([, ]|$)' /proc/mounts; then
        u_want="held:$u_hold"
    else
        u_want="proc-view-incomplete"
        echo "NOTE: u: this host's /proc may hide processes — expecting $u_want"
    fi
    assert_contains "u: kept ($u_want)" "ait_probe_${u_owner}_UCWD($u_want)" "$(cat "$WORK/u.out")"
    assert_eq "u: the dir is intact" "keep" "$(cat "$u_dir/data" 2>/dev/null)"
    kill "$u_hold" 2>/dev/null; wait "$u_hold" 2>/dev/null
else
    echo "SKIP: u: no /proc on this host"
fi

echo "=== (v) a cwd, an fd, an environ entry or a cmdline argument under the dir keeps it ==="
for kind in cwd fd environ cmdline; do
    clear_probe_stale; fresh_root "$FX"
    v_owner="$(dead_pid_fixture)"; v_pg="$(dead_pid_fixture)"
    make_stale probe "$v_owner" "V${kind}"
    dead_meta "$v_owner" "$v_pg" | put_meta
    case "$kind" in
        cwd)     fx_proc "$FX" 5151 "$STALE_DIR" /dev/null HOME=/nowhere; want="held:5151" ;;
        fd)      fx_proc "$FX" 5151 / "$STALE_DIR/data" HOME=/nowhere; want="held:5151" ;;
        environ) fx_proc "$FX" 5151 / /dev/null "TMPDIR=$STALE_DIR"; want="held:5151" ;;
        cmdline) fx_proc "$FX" 5151 / /dev/null HOME=/nowhere S "$STALE_DIR/x.log"; want="held:5151" ;;
        badrow)  printf 'Num       RefCount Protocol Flags    Type St Inode Path\ngarbage row\n' > "$FX/net/unix"; want="holder-unverified:1" ;;
    esac
    P_PRELUDE="${v_prelude:-}" probe probe "$FX" "$WORK/v_$kind.out"; v_prelude=""
    assert_contains "v/$kind: kept with $want" "ait_probe_${v_owner}_V${kind}($want)" "$(cat "$WORK/v_$kind.out")"
    assert_eq "v/$kind: the dir is intact" "keep" "$(cat "$STALE_DIR/data" 2>/dev/null)"
done

echo "=== (w) a process that cannot be inspected keeps every candidate ==="
if [[ "$(id -u)" -eq 0 ]]; then
    echo "SKIP: w: root reads mode-000 fixtures, so nothing is uninspectable"
else
    for kind in fd environ environdir; do
        clear_probe_stale; fresh_root "$FX"
        w_owner="$(dead_pid_fixture)"; w_pg="$(dead_pid_fixture)"
        make_stale probe "$w_owner" "W${kind}"
        dead_meta "$w_owner" "$w_pg" | put_meta
        fx_proc "$FX" 6161 / /dev/null HOME=/nowhere
        case "$kind" in
            fd)      chmod 000 "$FX/6161/fd" ;;
            environ) chmod 000 "$FX/6161/environ" ;;
            environdir) rm -f "$FX/6161/environ"; mkdir "$FX/6161/environ" ;;
        esac
        probe probe "$FX" "$WORK/w_$kind.out"
        chmod -R u+rwX "$FX"
        assert_contains "w/$kind: kept as holder-unverified" "ait_probe_${w_owner}_W${kind}(holder-unverified:1)" "$(cat "$WORK/w_$kind.out")"
        assert_eq "w/$kind: the dir is intact" "keep" "$(cat "$STALE_DIR/data" 2>/dev/null)"
    done
    # A lone zombie holds nothing, so its unreadable fd dir does not block.
    clear_probe_stale; fresh_root "$FX"
    w_owner="$(dead_pid_fixture)"; w_pg="$(dead_pid_fixture)"
    make_stale probe "$w_owner" WZOMBIE
    dead_meta "$w_owner" "$w_pg" | put_meta
    fx_proc "$FX" 6262 / /dev/null HOME=/nowhere Z
    chmod 000 "$FX/6262/fd"
    probe probe "$FX" "$WORK/w_z.out"
    chmod -R u+rwX "$FX"
    assert_contains "w/zombie: a lone zombie is skipped — the dir is reclaimed" "reclaimed 1 guard dir(s)" "$(cat "$WORK/w_z.out")"
fi

echo "=== (x) missing, malformed or incomplete metadata keeps the dir ==="
x_case() {  # x_case <suffix> <want-reason> — STALE_* already built
    probe probe "$FX" "$WORK/x_$1.out"
    assert_contains "x/$1: kept with $2" "ait_probe_${x_owner}_X$1($2)" "$(cat "$WORK/x_$1.out")"
    assert_eq "x/$1: the dir is intact" "keep" "$(cat "$STALE_DIR/data" 2>/dev/null)"
}
clear_probe_stale; fresh_root "$FX"
x_owner="$(dead_pid_fixture)"; x_pg="$(dead_pid_fixture)"; x_other="$(dead_pid_fixture)"
make_stale probe "$x_owner" Xnometa
x_case nometa no-metadata
make_stale probe "$x_owner" Xversion "ait_tmpdir_guard_meta 2" "owner $x_owner proc 1"
x_case version metadata-unreadable
make_stale probe "$x_owner" Xpidmismatch "ait_tmpdir_guard_meta 1" "owner $x_other proc 1"
x_case pidmismatch metadata-unreadable
make_stale probe "$x_owner" Xunknownline "ait_tmpdir_guard_meta 1" "owner $x_owner proc 1" "pgid $x_pg"
x_case unknownline metadata-unreadable
make_stale probe "$x_owner" Xunterminated "ait_tmpdir_guard_meta 1" "owner $x_owner proc 1" "phase_start 1"
printf 'phase 1 %s' "$x_pg" >> "$STALE_META"           # an append cut short
x_case unterminated metadata-unreadable
make_stale probe "$x_owner" Xunrecorded "ait_tmpdir_guard_meta 1" "owner $x_owner proc 1" "phase_start 1" "phase 1 $x_pg" "phase_start 2"
x_case unrecorded phase-unrecorded
clear_probe_stale          # the report names at most 5 dirs
# A token of the wrong shape for its kind would make a live owner compare
# unequal, i.e. read as recycled (dead).
make_stale probe "$x_owner" Xbadtoken "ait_tmpdir_guard_meta 1" "owner $x_owner proc invalid" "phase_start 1" "phase 1 $x_pg"
x_case badtoken metadata-unreadable
make_stale probe "$x_owner" Xbadbsd "ait_tmpdir_guard_meta 1" "owner $x_owner bsdinfo 12345" "phase_start 1" "phase 1 $x_pg"
x_case badbsd metadata-unreadable
# Metadata that is not this run's own private record.
mkdir -m 700 "$WORK/elsewhere"; dead_meta "$x_owner" "$x_pg" > "$WORK/elsewhere/meta"
make_stale probe "$x_owner" Xctllink
ln -s "$WORK/elsewhere" "$STALE_CTL"
x_case ctllink metadata-unreadable
make_stale probe "$x_owner" Xmetalink
mkdir -m 700 "$STALE_CTL"; ln -s "$WORK/elsewhere/meta" "$STALE_META"
x_case metalink metadata-unreadable
clear_probe_stale
# A record the writer invalidated by chmod (it could not remove it) — also as root.
make_stale probe "$x_owner" Xmode000 "ait_tmpdir_guard_meta 1" "owner $x_owner proc 1" "phase_start 1" "phase 1 $x_pg"
chmod 000 "$STALE_META"
x_case mode000 metadata-unreadable
make_stale probe "$x_owner" Xreadonly "ait_tmpdir_guard_meta 1" "owner $x_owner proc 1" "phase_start 1" "phase 1 $x_pg"
chmod 400 "$STALE_META"
x_case readonly metadata-unreadable
clear_probe_stale
# A read error after the header (simulated: cat yields the first two lines, then
# fails) must not parse as a complete record with no process group in it.
make_stale probe "$x_owner" Xreaderror "ait_tmpdir_guard_meta 1" "owner $x_owner proc 1" "phase_start 1" "phase 1 $x_pg"
P_PRELUDE='cat() { command cat "$@" | head -n 2; return 1; }' x_case readerror metadata-unreadable
clear_probe_stale
sleep 300 & x_live2=$!; echo "$x_live2" >> "$STUB_PIDS"
make_stale probe "$x_live2" Xlivebad "ait_tmpdir_guard_meta 1" "owner $x_live2 proc invalid" "phase_start 1" "phase 1 $x_pg"
probe probe "$FX" "$WORK/x_livebad.out"
assert_eq "x/livebad: a live owner with a malformed token is never reclaimed" "keep" "$(cat "$STALE_DIR/data" 2>/dev/null)"
kill "$x_live2" 2>/dev/null; wait "$x_live2" 2>/dev/null
clear_probe_stale
# A live owner recorded without a usable identity token cannot be told from a
# recycled pid: neither alive nor dead.
sleep 300 & x_live=$!; echo "$x_live" >> "$STUB_PIDS"
x_owner="$x_live"
make_stale probe "$x_live" Xweak "ait_tmpdir_guard_meta 1" "owner $x_live none -" "phase_start 1" "phase 1 $x_pg"
x_case weak owner-unverified
kill "$x_live" 2>/dev/null; wait "$x_live" 2>/dev/null
clear_probe_stale

echo "=== (y) a process list that may be incomplete (hidepid) keeps every candidate ==="
for opts in rw,hidepid=invisible rw,hidepid=2 rw,hidepid=ptraceable rw,hidepid=4 none-listed unreadable readerror readpartial rw,hidepid=noaccess; do
    clear_probe_stale; fresh_root "$FX"
    y_owner="$(dead_pid_fixture)"; y_pg="$(dead_pid_fixture)"
    make_stale probe "$y_owner" Yview
    dead_meta "$y_owner" "$y_pg" | put_meta
    case "$opts" in
        none-listed) printf 'proc /proc proc rw 0 0\n' > "$FX/mounts" ;;   # not THIS root's mount
        unreadable)  rm -f "$FX/mounts" ;;
        readerror)   rm -f "$FX/mounts"; mkdir "$FX/mounts" ;;
        readpartial) fx_mounts "$FX" rw,hidepid=invisible       # the hiding entry is cut off:
                     printf 'proc %s proc rw 0 0\n' "$(cd "$FX" && pwd -P)" > "$FX/mounts.head"
                     cat "$FX/mounts" >> "$FX/mounts.head"; mv "$FX/mounts.head" "$FX/mounts"
                     y_prelude='cat() { if [[ "$*" == */mounts* ]]; then command cat "$@" | head -n 1; return 1; fi; command cat "$@"; }' ;;
        *)           fx_mounts "$FX" "$opts" ;;
    esac
    P_PRELUDE="${y_prelude:-}" probe probe "$FX" "$WORK/y.out"; y_prelude=""
    if [[ "$opts" == rw,hidepid=noaccess ]]; then
        # Control: noaccess still LISTS every process (the scan inspects or
        # counts each one), so the view is complete.
        assert_contains "y/$opts: control — a listing mount is complete, reclaimed" "reclaimed 1 guard dir(s)" "$(cat "$WORK/y.out")"
    else
        assert_contains "y/$opts: kept as proc-view-incomplete" "ait_probe_${y_owner}_Yview(proc-view-incomplete)" "$(cat "$WORK/y.out")"
        assert_eq "y/$opts: the dir is intact" "keep" "$(cat "$STALE_DIR/data" 2>/dev/null)"
    fi
done

echo "=== (z) off Linux: lsof is believed only as root, with warnings on, and silent ==="
clear_probe_stale
mkdir -p "$WORK/noproc" "$WORK/fakebin"
cat > "$WORK/fakebin/lsof" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$LSOF_ARGS"
case "$LSOF_MODE" in
    silent)  exit 1 ;;
    warning) echo "lsof: WARNING: can't stat() fuse.gvfsd-fuse file system /run/user/1000/gvfs" >&2; exit 1 ;;
    holder)  printf 'p777\n'; exit 0 ;;
esac
EOF
chmod +x "$WORK/fakebin/lsof"
export LSOF_ARGS="$WORK/lsof.args"
for mode in silent warning holder notroot; do
    clear_probe_stale; : > "$LSOF_ARGS"
    z_owner="$(dead_pid_fixture)"; z_pg="$(dead_pid_fixture)"
    make_stale probe "$z_owner" Zlsof
    dead_meta "$z_owner" "$z_pg" | put_meta
    z_euid=0; [[ "$mode" == notroot ]] && z_euid=1000
    PATH="$WORK/fakebin:$PATH" LSOF_MODE="$mode" P_EUID="$z_euid" probe probe "$WORK/noproc" "$WORK/z.out"
    case "$mode" in
        silent)  assert_contains "z/silent: exit 1 with no output at all -> reclaimed" "reclaimed 1 guard dir(s)" "$(cat "$WORK/z.out")" ;;
        warning) assert_contains "z/warning: a coverage warning keeps it" "Zlsof(holder-unverified:lsof-failed)" "$(cat "$WORK/z.out")" ;;
        holder)  assert_contains "z/holder: a holder line keeps it" "Zlsof(held:777)" "$(cat "$WORK/z.out")" ;;
        notroot) assert_contains "z/notroot: a non-root negative is never believed" "Zlsof(holder-unverified:lsof-not-root)" "$(cat "$WORK/z.out")" ;;
    esac
    if [[ "$mode" != notroot ]]; then
        assert_not_contains "z/$mode: lsof runs with warnings enabled (no -w)" "-w" "$(cat "$LSOF_ARGS")"
        assert_contains "z/$mode: warnings are forced on (+w), not left to the build default" "+w" "$(cat "$LSOF_ARGS")"
        assert_contains "z/$mode: lsof scans the dir recursively" "+D $STALE_DIR" "$(cat "$LSOF_ARGS")"
    fi
done
unset LSOF_ARGS

echo "=== (aa) a phase whose intent cannot be recorded leaves a dir that is never reclaimed ==="
if [[ "$(id -u)" -eq 0 ]]; then
    echo "SKIP: aa: root writes through read-only modes, so the appends cannot be made to fail"
else
    FW="$WORK/fault_wrap.sh"
    cat > "$FW" <<'EOF'
. "$GUARD_LIB"
tmpdir_guard_begin shrun || exit 9
c="${TMPDIR%/*}/.${TMPDIR##*/}.ait_guard_meta"
chmod a-w "$c/meta"                              # every append now fails...
[[ "$FW_MODE" == both ]] && chmod a-w "$c"       # ...and so does the removal
tmpdir_guard_run bash "$STUB" aa 300 0 writer
EOF
    for fw_mode in file both; do
        clear_probe_stale; fresh_root "$FX"; : > "$STUB_PIDS"
        TMPDIR="$BASE" GUARD_LIB="$GUARD_LIB" STUB="$STUB" FW_MODE="$fw_mode" bash "$FW" </dev/null >"$WORK/aa.out" 2>&1 &
        aa_wrap=$!
        for _ in $(seq 1 100); do [[ "$(wc -l < "$STUB_PIDS" | tr -d ' ')" -ge 2 ]] && break; sleep 0.1; done
        aa_dir="$(find "$BASE" -mindepth 1 -maxdepth 1 -type d -name "ait_shrun_${aa_wrap}_*" | head -n1)"
        aa_pg="$(ps -o pgid= -p "$(head -n1 "$STUB_PIDS")" 2>/dev/null | tr -d ' ')"
        kill -KILL "$aa_wrap"; wait "$aa_wrap" 2>/dev/null
        assert_contains "aa/$fw_mode: the failed intent write is announced" "run metadata invalidated" "$(cat "$WORK/aa.out")"
        case "$fw_mode" in file) want=no-metadata ;; both) want=metadata-unreadable ;; esac
        probe shrun "$FX" "$WORK/aa1.out"
        assert_contains "aa/$fw_mode: kept while the writer runs ($want)" "${aa_dir##*/}($want)" "$(cat "$WORK/aa1.out")"
        [[ -n "$aa_pg" ]] && kill -KILL -- "-$aa_pg" 2>/dev/null
        for _ in $(seq 1 50); do kill -0 -- "-$aa_pg" 2>/dev/null || break; sleep 0.1; done
        probe shrun "$FX" "$WORK/aa2.out"
        assert_contains "aa/$fw_mode: still kept once it is gone — an unrecorded group is never assumed empty" "${aa_dir##*/}($want)" "$(cat "$WORK/aa2.out")"
        assert_eq "aa/$fw_mode: the dir is intact" "yes" "$([[ -d "$aa_dir" ]] && echo yes || echo no)"
    done
fi
clear_probe_stale

echo "=== (ab) the metadata writer never writes through a path planted beside the dir ==="
ab_out="$(TMPDIR="$BASE" GUARD_LIB="$GUARD_LIB" AB_WORK="$WORK" bash -c '
    . "$GUARD_LIB"
    for kind in dirlink dangling; do
        g="$TMPDIR/ait_abprobe_$$_$kind"; mkdir -p "$g"
        case "$kind" in
            dirlink)  mkdir -p "$AB_WORK/ab_target"; ln -s "$AB_WORK/ab_target" "${g%/*}/.${g##*/}.ait_guard_meta" ;;
            dangling) ln -s "$AB_WORK/ab_nowhere" "${g%/*}/.${g##*/}.ait_guard_meta" ;;
        esac
        if _tg_meta_create "$g"; then echo "$kind:created"; else echo "$kind:refused"; fi
    done
' 2>&1)"
assert_contains "ab: a planted symlink to a directory is refused" "dirlink:refused" "$ab_out"
assert_contains "ab: a planted dangling symlink is refused" "dangling:refused" "$ab_out"
assert_eq "ab: nothing was written into the link's target" "0" "$(find "$WORK/ab_target" -mindepth 1 | wc -l | tr -d ' ')"
assert_eq "ab: nothing was created at the dangling target" "absent" "$([[ -e "$WORK/ab_nowhere" ]] && echo present || echo absent)"
rm -rf "$BASE"/ait_abprobe_* "$BASE"/.ait_abprobe_*

echo "=== (ac) intent unrecorded AND invalidation not CONFIRMED: the phase runs outside the guard ==="
# Fault injection by shadowing: the intent append fails (a printf that refuses
# that one format); AC_FAULTS then breaks the invalidation's mutation (rm,
# chmod fail), its VERIFICATION (find fails), or makes the mutation lie (rm,
# chmod report success and do nothing). The record left behind can be a valid
# header with no process group — what a reader accepts — so unless the
# invalidation is positively confirmed the phase must not use the guard dir.
FN="$WORK/fault_neither.sh"
cat > "$FN" <<'EOF'
. "$GUARD_LIB"
tmpdir_guard_begin shrun || exit 9
printf '%s\n' "$TMPDIR" > "$AC_GUARD"
printf() { if [[ "${1:-}" == 'phase_start %s\n' ]]; then return 1; fi; builtin printf "$@"; }
for f in $AC_FAULTS; do
    case "$f" in
        rm)      rm()    { return 1; } ;;
        rmok)    rm()    { return 0; } ;;
        chmod)   chmod() { return 1; } ;;
        chmodok) chmod() { return 0; } ;;
        find)    find()  { return 1; } ;;
    esac
done
tmpdir_guard_run bash -c 'echo $$ >> "$STUB_PIDS"; printf "%s\n" "${TMPDIR:-<unset>}" > "$AC_SEEN"; [[ "$AC_MODE" == kill ]] && exec sleep 300; exit 0'
unset -f printf rm chmod find
tmpdir_guard_end
echo "count=[${_TG_LEFTOVER_COUNT}]"
EOF
export AC_SEEN="$WORK/ac.seen" AC_GUARD="$WORK/ac.guard"
# (1) each unconfirmed invalidation moves the phase out; the run is not
# attested as inspected.
for faults in "rm chmod" "rm chmod find" "rmok chmodok" "find"; do
    rm -f "$AC_SEEN" "$AC_GUARD"
    out="$(TMPDIR="$BASE" GUARD_LIB="$GUARD_LIB" AC_MODE=normal AC_FAULTS="$faults" bash "$FN" </dev/null 2>&1)"
    assert_contains "ac[$faults]: the unconfirmed invalidation is announced" "could not be removed or made unreadable" "$out"
    assert_contains "ac[$faults]: the phase is announced as outside the guard" "runs OUTSIDE the guard" "$out"
    assert_eq "ac[$faults]: the phase saw the ORIGINAL TMPDIR, not the guard dir" "$BASE" "$(cat "$AC_SEEN" 2>/dev/null)"
    assert_contains "ac[$faults]: the run is not attested as inspected (strict fails it)" "count=[]" "$out"
    clear_probe_stale
done
# Control: a CONFIRMED invalidation keeps the phase inside the guard.
rm -f "$AC_SEEN" "$AC_GUARD"
out="$(TMPDIR="$BASE" GUARD_LIB="$GUARD_LIB" AC_MODE=normal AC_FAULTS="" bash "$FN" </dev/null 2>&1)"
assert_contains "ac[control]: the invalidation is confirmed" "run metadata invalidated" "$out"
assert_eq "ac[control]: the phase runs inside the guard" "$(cat "$AC_GUARD" 2>/dev/null)" "$(cat "$AC_SEEN" 2>/dev/null)"
assert_not_contains "ac[control]: no outside launch" "OUTSIDE the guard" "$out"
# (2) killed while that phase runs: the record (valid, no group) is accepted and
# the dir reclaimed — which is now correct, because nothing uses it.
clear_probe_stale; fresh_root "$FX"; rm -f "$AC_SEEN" "$AC_GUARD"
: > "$STUB_PIDS"
TMPDIR="$BASE" GUARD_LIB="$GUARD_LIB" AC_MODE=kill AC_FAULTS="rm chmod" bash "$FN" </dev/null >"$WORK/ac.out" 2>&1 &
ac_wrap=$!
for _ in $(seq 1 100); do [[ -s "$AC_SEEN" ]] && break; sleep 0.1; done
ac_dir="$(cat "$AC_GUARD" 2>/dev/null)"
kill -KILL "$ac_wrap"; wait "$ac_wrap" 2>/dev/null
assert_eq "ac/kill: the surviving phase was never inside the guard dir" "$BASE" "$(cat "$AC_SEEN" 2>/dev/null)"
probe shrun "$FX" "$WORK/ac2.out"
assert_contains "ac/kill: the unused dir is reclaimed" "reclaimed 1 guard dir(s)" "$(cat "$WORK/ac2.out")"
assert_eq "ac/kill: gone" "gone" "$([[ -n "$ac_dir" && -e "$ac_dir" ]] && echo present || echo gone)"
ac_phase="$(tail -n1 "$STUB_PIDS")"
TOTAL=$((TOTAL + 1))
if [[ -n "$ac_phase" ]] && kill -0 "$ac_phase" 2>/dev/null; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: ac/kill: setup — the outside phase ($ac_phase) should still be running"; fi
kill -KILL "$ac_phase" 2>/dev/null
unset AC_SEEN AC_GUARD
clear_probe_stale

echo "=== (ad) a mount at or below a dir stops every recursive removal ==="
# Bind mounts share the device, so only the mount table (by path) sees them.
for kind in below at spaced garbled garbledthenbelow; do
    clear_probe_stale; fresh_root "$FX"
    ad_owner="$(dead_pid_fixture)"; ad_pg="$(dead_pid_fixture)"
    case "$kind" in
        spaced) make_stale probe "$ad_owner" "AD sp" ;;
        *)      make_stale probe "$ad_owner" "AD$kind" ;;
    esac
    dead_meta "$ad_owner" "$ad_pg" | put_meta
    mkdir -p "$STALE_DIR/mnt"; echo mounted-data > "$STALE_DIR/mnt/keep"
    ad_esc="$(cd "$STALE_DIR" && pwd -P)"; ad_esc="${ad_esc// /\\040}"
    case "$kind" in
        below|spaced) printf 'tmpfs %s/mnt tmpfs rw 0 0\n' "$ad_esc" >> "$FX/mounts"; want="mounted:$ad_esc/mnt" ;;
        at)           printf '/dev/sda1 %s ext4 rw 0 0\n' "$ad_esc" >> "$FX/mounts"; want="mounted:$ad_esc" ;;
        garbled)      printf 'garbled-row\n' >> "$FX/mounts"; want="mounts-unverified" ;;
        garbledthenbelow) printf 'garbled-row\ntmpfs %s/mnt tmpfs rw 0 0\n' "$ad_esc" >> "$FX/mounts"; want="mounted:$ad_esc/mnt" ;;
    esac
    probe probe "$FX" "$WORK/ad.out"
    assert_contains "ad/$kind: kept ($want)" "($want)" "$(cat "$WORK/ad.out")"
    assert_eq "ad/$kind: the mounted data is untouched" "mounted-data" "$(cat "$STALE_DIR/mnt/keep" 2>/dev/null)"
done
# Control: the same dir with only unrelated mounts is reclaimed.
clear_probe_stale; fresh_root "$FX"
ad_owner="$(dead_pid_fixture)"; ad_pg="$(dead_pid_fixture)"
make_stale probe "$ad_owner" ADnone; dead_meta "$ad_owner" "$ad_pg" | put_meta
printf 'tmpfs /run/unrelated tmpfs rw 0 0\n' >> "$FX/mounts"
probe probe "$FX" "$WORK/ad0.out"
assert_contains "ad/control: no mount below it -> reclaimed" "reclaimed 1 guard dir(s)" "$(cat "$WORK/ad0.out")"
# tmpdir_guard_end, too: a mount found under the run's OWN dir stops its removal.
clear_probe_stale; fresh_root "$FX"
out="$(TMPDIR="$BASE" GUARD_LIB="$GUARD_LIB" FXR="$FX" bash -c '
    . "$GUARD_LIB"
    _TG_PROC_ROOT="$FXR"
    tmpdir_guard_begin probe || exit 9
    mkdir "$TMPDIR/mnt"; echo mounted-data > "$TMPDIR/mnt/keep"
    printf "tmpfs %s/mnt tmpfs rw 0 0\n" "$(cd "$TMPDIR" && pwd -P)" >> "$FXR/mounts"
    d="$TMPDIR"
    tmpdir_guard_end
    echo "count=[${_TG_LEFTOVER_COUNT}]"
    cat "$d/mnt/keep"
' 2>&1)"
assert_contains "ad/end: the removal is refused and explained" "has a mount at or below it" "$out"
assert_contains "ad/end: the mounted data survives" "mounted-data" "$out"
assert_contains "ad/end: the run is not attested as inspected" "count=[]" "$out"
assert_contains "ad/end: the leftovers line reports the observed outcome" "were NOT removed: a mount at or below it" "$out"
assert_not_contains "ad/end: …and never claims a removal" "are now removed" "$out"
clear_probe_stale; fresh_root "$FX"
out="$(TMPDIR="$BASE" GUARD_LIB="$GUARD_LIB" FXR="$FX" bash -c '
    . "$GUARD_LIB"
    _TG_PROC_ROOT="$FXR"
    tmpdir_guard_begin probe || exit 9
    echo leftover > "$TMPDIR/leak_ad"
    printf "garbled-row\n" >> "$FXR/mounts"
    d="$TMPDIR"
    tmpdir_guard_end
    echo "count=[${_TG_LEFTOVER_COUNT}]"
    [[ -e "$d/leak_ad" ]] && echo still-there
' 2>&1)"
assert_contains "ad/end-unverified: an unreadable mount table stops the removal" "could not verify that nothing is mounted" "$out"
assert_contains "ad/end-unverified: the dir is left" "still-there" "$out"
assert_contains "ad/end-unverified: the leftovers line reports it" "were NOT removed: the mount table could not be read" "$out"
assert_contains "ad/end-unverified: not attested as inspected" "count=[]" "$out"
# Control dirs are removed with nothing recursive: the one `meta` file, then
# rmdir — and not at all with a mount below them.
clear_probe_stale; fresh_root "$FX"
ad_orphan="$BASE/.ait_probe_$(dead_pid_fixture)_ADORPH${META_SUFFIX}"   # its guard dir is gone
mkdir -m 700 "$ad_orphan"; dead_meta 1 1 > "$ad_orphan/meta"
mkdir "$ad_orphan/mnt"; echo mounted-data > "$ad_orphan/mnt/keep"
printf 'tmpfs %s/mnt tmpfs rw 0 0\n' "$(cd "$ad_orphan" && pwd -P)" >> "$FX/mounts"
ad_owner="$(dead_pid_fixture)"; ad_pg="$(dead_pid_fixture)"
make_stale probe "$ad_owner" ADEXTRA; dead_meta "$ad_owner" "$ad_pg" | put_meta
echo stray > "$STALE_CTL/stray"                                      # unexpected entry
ad_extra_ctl="$STALE_CTL"
probe probe "$FX" "$WORK/ad_ctl.out"
assert_eq "ad/ctl: an orphan control dir with a mount below it is not touched" "mounted-data" "$(cat "$ad_orphan/mnt/keep" 2>/dev/null)"
assert_eq "ad/ctl: …nor its record" "yes" "$([[ -f "$ad_orphan/meta" ]] && echo yes || echo no)"
assert_contains "ad/ctl: the guard dir itself is still reclaimed" "reclaimed 1 guard dir(s)" "$(cat "$WORK/ad_ctl.out")"
assert_eq "ad/ctl: an unexpected entry in a control dir survives (rmdir, not rm -r)" "stray" "$(cat "$ad_extra_ctl/stray" 2>/dev/null)"
clear_probe_stale

echo "=== (af) a base path containing a newline: every path survives discovery intact ==="
clear_probe_stale; fresh_root "$FX"
NLB="$WORK/nl"$'\n'"base"
mkdir -p "$NLB"
af_owner="$(dead_pid_fixture)"; af_pg="$(dead_pid_fixture)"
af_dir="$NLB/ait_probe_${af_owner}_AFNL"; af_ctl="$NLB/.ait_probe_${af_owner}_AFNL${META_SUFFIX}"
mkdir -p "$af_dir"; echo keep > "$af_dir/data"
mkdir -m 700 "$af_ctl"; dead_meta "$af_owner" "$af_pg" > "$af_ctl/meta"
af_orphan="$NLB/.ait_probe_${af_pg}_AFORPH${META_SUFFIX}"
mkdir -m 700 "$af_orphan"; dead_meta "$af_pg" "$af_pg" > "$af_orphan/meta"
TMPDIR="$NLB" GUARD_LIB="$GUARD_LIB" P_ROOT="$FX" bash -c '
    . "$GUARD_LIB"; _TG_PROC_ROOT="$P_ROOT"
    tmpdir_guard_begin probe || exit 9
    tmpdir_guard_end
' </dev/null >"$WORK/af.out" 2>&1
assert_contains "af: the stale dir under a newline-bearing base is reclaimed" "reclaimed 1 guard dir(s)" "$(cat "$WORK/af.out")"
assert_eq "af: …the right one, and it is gone" "gone" "$([[ -e "$af_dir" ]] && echo present || echo gone)"
assert_eq "af: its control dir is gone" "gone" "$([[ -e "$af_ctl" ]] && echo present || echo gone)"
assert_eq "af: the orphan control dir is swept" "gone" "$([[ -e "$af_orphan" ]] && echo present || echo gone)"
assert_eq "af: nothing else is left under that base" "0" "$(find "$NLB" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')"
rm -rf "$NLB" "$WORK/nl"
clear_probe_stale

echo "=== (ah) a socket file inside the dir keeps it; the host's socket table is not consulted ==="
# Step 6 scans each candidate's own tree (find -type s) after the mount check.
# A bound unix socket under the dir is a socket file in it; one bound elsewhere
# (relative to another cwd, or abstract) no longer vetoes a reclaim.
# mksock <path> — leave a unix socket FILE at <path>. Binds the short basename
# from inside the parent dir: sun_path holds ~108 bytes, and a long (valid)
# TMPDIR would overflow it with the absolute path.
mksock() {
    ( cd "${1%/*}" && python3 -c 'import socket,sys; s=socket.socket(socket.AF_UNIX); s.bind(sys.argv[1]); s.close()' "${1##*/}" ) 2>/dev/null
}
if ! command -v python3 >/dev/null 2>&1; then
    echo "SKIP: ah: no python3 to bind a unix socket"
else
    for kind in top nested; do
        clear_probe_stale; fresh_root "$FX"
        ah_owner="$(dead_pid_fixture)"; ah_pg="$(dead_pid_fixture)"
        make_stale probe "$ah_owner" "AH$kind"; dead_meta "$ah_owner" "$ah_pg" | put_meta
        case "$kind" in
            top)    ah_sock="$STALE_DIR/s.sock" ;;
            nested) mkdir -p "$STALE_DIR/a/b"; ah_sock="$STALE_DIR/a/b/n.sock" ;;
        esac
        mksock "$ah_sock"
        # Setup is checked BEFORE the probe: without the socket the reaper
        # rightly reclaims the dir, and that would read as a guard failure.
        TOTAL=$((TOTAL + 1))
        if [[ -S "$ah_sock" ]]; then
            PASS=$((PASS + 1))
            probe probe "$FX" "$WORK/ah.out"
            assert_contains "ah/$kind: a socket under the dir keeps it" "AH$kind(socket:$ah_sock)" "$(cat "$WORK/ah.out")"
            assert_eq "ah/$kind: the dir and the socket are intact" "yes" "$([[ -S "$ah_sock" && -f "$STALE_DIR/data" ]] && echo yes || echo no)"
        else
            FAIL=$((FAIL + 1)); echo "FAIL: ah/$kind: setup — could not create the socket fixture $ah_sock"
        fi
    done
fi
# An unrelated abstract socket (and a relative one) in the host table: an
# otherwise eligible dir is reclaimed.
clear_probe_stale; fresh_root "$FX"
printf 'Num       RefCount Protocol Flags    Type St Inode Path\n0000000000000000: 00000002 00000000 00010000 0001 01 12345 @unrelated-abstract\n0000000000000001: 00000002 00000000 00010000 0001 01 12346 rel.sock\n' > "$FX/net/unix"
ah_owner="$(dead_pid_fixture)"; ah_pg="$(dead_pid_fixture)"
make_stale probe "$ah_owner" AHabstract; dead_meta "$ah_owner" "$ah_pg" | put_meta
probe probe "$FX" "$WORK/ah.out"
assert_contains "ah/abstract: an unrelated abstract socket does not block the reclaim" "reclaimed 1 guard dir(s)" "$(cat "$WORK/ah.out")"
assert_eq "ah/abstract: the dir is gone" "gone" "$([[ -e "$STALE_DIR" ]] && echo present || echo gone)"
# A walk that fails keeps the dir: an unreadable subdirectory (real), and an
# injected find failure (works as root too).
for kind in unreadable injected; do
    if [[ "$kind" == unreadable && "$(id -u)" -eq 0 ]]; then echo "SKIP: ah/unreadable: root reads mode-000 dirs"; continue; fi
    clear_probe_stale; fresh_root "$FX"
    ah_owner="$(dead_pid_fixture)"; ah_pg="$(dead_pid_fixture)"
    make_stale probe "$ah_owner" "AH$kind"; dead_meta "$ah_owner" "$ah_pg" | put_meta
    ah_prelude=""
    case "$kind" in
        unreadable) mkdir -p "$STALE_DIR/locked"; echo x > "$STALE_DIR/locked/f"; chmod 000 "$STALE_DIR/locked" ;;
        injected)   ah_prelude='find() { case " $* " in *" -type s "*) return 1 ;; esac; command find "$@"; }' ;;
    esac
    P_PRELUDE="$ah_prelude" probe probe "$FX" "$WORK/ah.out"
    chmod -R u+rwX "$STALE_DIR" 2>/dev/null
    assert_contains "ah/$kind: a failed socket scan keeps the dir" "AH$kind(socket-scan-failed)" "$(cat "$WORK/ah.out")"
    assert_eq "ah/$kind: the dir is intact" "keep" "$(cat "$STALE_DIR/data" 2>/dev/null)"
done
clear_probe_stale

echo "=== (ag) on Linux without <proc-root>/mounts: the kernel's table, never \`mount\` stdout ==="
# util-linux prints '<src> on <target> type <fs> (<opts>)'; read as BSD output,
# the target would end in ' type <fs>' and match nothing — a mount AT the dir
# reported as no mount. So Linux reads $_TG_SELF_MOUNTS and never `mount`.
cat > "$WORK/fakebin/mount" <<'EOF'
#!/usr/bin/env bash
printf 'proc on /proc type proc (rw)\ntmpfs on %s type tmpfs (rw)\n' "$MOUNT_TARGET"
EOF
chmod +x "$WORK/fakebin/mount"
export LSOF_ARGS="$WORK/lsof.args"
for gmode in selfhit selfclean selfmissing unknownos; do
    clear_probe_stale
    ag_owner="$(dead_pid_fixture)"; ag_pg="$(dead_pid_fixture)"
    make_stale probe "$ag_owner" AGlinux; dead_meta "$ag_owner" "$ag_pg" | put_meta
    ag_esc="$(cd "$STALE_DIR" && pwd -P)"
    ag_os=linux-gnu; ag_self="$WORK/self_mounts"
    case "$gmode" in
        selfhit)     printf 'proc /proc proc rw 0 0\ntmpfs %s tmpfs rw 0 0\n' "$ag_esc" > "$ag_self" ;;
        selfclean)   printf 'proc /proc proc rw 0 0\n' > "$ag_self" ;;
        selfmissing) ag_self="$WORK/no/such/mounts" ;;
        unknownos)   ag_os=solaris2.11; printf 'proc /proc proc rw 0 0\n' > "$ag_self" ;;
    esac
    PATH="$WORK/fakebin:$PATH" LSOF_MODE=silent MOUNT_TARGET="$STALE_DIR" P_EUID=0 P_OSTYPE="$ag_os" P_SELF_MOUNTS="$ag_self" \
        probe probe "$WORK/noproc" "$WORK/ag.out"
    case "$gmode" in
        selfhit)     assert_contains "ag/selfhit: the kernel table's mount at the dir keeps it" "AGlinux(mounted:$ag_esc)" "$(cat "$WORK/ag.out")" ;;
        selfclean)   assert_contains "ag/selfclean: control — the kernel table is clean -> reclaimed" "reclaimed 1 guard dir(s)" "$(cat "$WORK/ag.out")" ;;
        selfmissing) assert_contains "ag/selfmissing: no kernel table -> kept, \`mount\` stdout is not consulted" "AGlinux(mounts-unverified)" "$(cat "$WORK/ag.out")" ;;
        unknownos)   assert_contains "ag/unknownos: an unknown \`mount\` format -> kept" "AGlinux(mounts-unverified)" "$(cat "$WORK/ag.out")" ;;
    esac
    [[ "$gmode" == selfclean ]] || assert_eq "ag/$gmode: the dir is intact" "keep" "$(cat "$STALE_DIR/data" 2>/dev/null)"
done
# Normal exit, the reviewer's case: no <proc-root>/mounts, a mount AT the run's
# own guard dir in the kernel table -> not removed.
clear_probe_stale
out="$(TMPDIR="$BASE" GUARD_LIB="$GUARD_LIB" NOPROC="$WORK/noproc" SELFM="$WORK/self_mounts" PATH="$WORK/fakebin:$PATH" bash -c '
    . "$GUARD_LIB"
    _TG_PROC_ROOT="$NOPROC"; _TG_OSTYPE=linux-gnu; _TG_SELF_MOUNTS="$SELFM"
    tmpdir_guard_begin probe || exit 9
    echo mounted-data > "$TMPDIR/keep"
    printf "tmpfs %s tmpfs rw 0 0\n" "$(cd "$TMPDIR" && pwd -P)" > "$SELFM"
    export MOUNT_TARGET="$TMPDIR"
    d="$TMPDIR"
    tmpdir_guard_end
    cat "$d/keep"
' 2>&1)"
assert_contains "ag/end: a mount at the run's own dir stops the removal" "has a mount at or below it" "$out"
assert_contains "ag/end: the mounted data survives" "mounted-data" "$out"
unset LSOF_ARGS
clear_probe_stale

echo "=== (ae) off Linux, every \`mount\` row is read, and any reading of one below the dir keeps it ==="
# No proc mounts file: _tg_mounts_under falls back to `mount`, whose rows are
# '<source> on <target> (<options>)', unescaped. The holder step goes through
# the lsof path (an empty proc root, a silent fake lsof, euid 0).
cat > "$WORK/fakebin/mount" <<'EOF'
#!/usr/bin/env bash
case "$MOUNT_MODE" in
    clean)     printf '/dev/disk1s1 on / (apfs, local, journaled)\n' ;;
    nested)    printf '/dev/disk1s1 on / (apfs, local)\n/dev/disk2s1 on %s/mnt (apfs, local)\n' "$MOUNT_TARGET" ;;
    ambiguous) printf '/dev/disk1s1 on / (apfs, local)\nserver:/srv/a on b on %s/mnt (nfs)\n' "$MOUNT_TARGET" ;;
    ambthenclear) printf 'server:/srv/a on b on /Volumes/x (nfs)\n/dev/disk2s1 on %s/mnt (apfs, local)\n' "$MOUNT_TARGET" ;;
    badthenclear) printf 'no-delimiters-here\n/dev/disk2s1 on %s/mnt (apfs, local)\n' "$MOUNT_TARGET" ;;
    ambunrelated) printf '/dev/disk1s1 on / (apfs, local)\nserver:/srv/a on b on /Volumes/x (nfs)\n' ;;
    badrow)    printf '/dev/disk1s1 on / (apfs, local)\nno-delimiters-here\n' ;;
    typesuffix) printf 'proc on /proc type proc (rw)\ntmpfs on %s type tmpfs (rw)\n' "$MOUNT_TARGET" ;;
    fail)      exit 1 ;;
esac
EOF
chmod +x "$WORK/fakebin/mount"
export LSOF_ARGS="$WORK/lsof.args"
for mmode in clean nested ambiguous ambthenclear badthenclear ambunrelated typesuffix badrow fail; do
    clear_probe_stale
    ae_owner="$(dead_pid_fixture)"; ae_pg="$(dead_pid_fixture)"
    make_stale probe "$ae_owner" AEmount; dead_meta "$ae_owner" "$ae_pg" | put_meta
    PATH="$WORK/fakebin:$PATH" LSOF_MODE=silent MOUNT_MODE="$mmode" MOUNT_TARGET="$STALE_DIR" P_EUID=0 P_OSTYPE=darwin23 \
        probe probe "$WORK/noproc" "$WORK/ae.out"
    case "$mmode" in
        clean|ambunrelated)
                   # ambunrelated: no split of the ambiguous row lands below the dir
                   assert_contains "ae/$mmode: no mount below it -> reclaimed" "reclaimed 1 guard dir(s)" "$(cat "$WORK/ae.out")" ;;
        typesuffix)
                   # "<dir> type tmpfs": a suffix the format added — read as a
                   # mount at the dir (the safe reading)
                   assert_contains "ae/typesuffix: kept (possibly mounted)" "AEmount(mounted:$STALE_DIR type tmpfs)" "$(cat "$WORK/ae.out")" ;;
        nested|ambiguous|ambthenclear|badthenclear)
                   # ambiguous: one split of the row lands below the dir; the
                   # *thenclear modes: a clear mount AFTER an unreadable row still wins
                   assert_contains "ae/$mmode: kept (mounted)" "AEmount(mounted:$STALE_DIR/mnt)" "$(cat "$WORK/ae.out")" ;;
        *)         assert_contains "ae/$mmode: kept (mounts-unverified)" "AEmount(mounts-unverified)" "$(cat "$WORK/ae.out")" ;;
    esac
done
unset LSOF_ARGS
clear_probe_stale

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]] || exit 1
echo "ALL TESTS PASSED"
