#!/usr/bin/env bash
# test_gate_lock_characterization.sh - Characterization tests for the gate
# mutex in aitask_gate.sh (t1183, risk-mitigation "before" for t635_30).
#
# Pins the CURRENT mutual-exclusion behavior of acquire_gate_lock /
# release_gate_lock (aitask_gate.sh:68-97) and the lock-key derivation
# `key="${task_id//\//_}"` (raw argument) used by `append` and
# `materialize-active`, so t635_30's switch to a resolved-file-derived key
# (`_gate_lock_key <resolved-file>` = basename sans `.md`) is a provable flip
# rather than an unverified swap.
#
# FLIP CONTRACT (t635_30) — what each test must do after the key change lands:
#
#   Test 1  (same-spelling concurrent appends)      must still pass
#   Test 2a (held raw-id lock blocks append)        FLIPS: no longer blocks
#   Test 2b (held file-basename lock is ignored)    FLIPS: blocks -> die
#   Test 3  (t-spelling dies at resolve, pre-lock)  must still pass while no
#           alias spelling resolves; if an alias is EVER made resolvable this
#           test fails loudly — replace it with an alias lock-convergence
#           test: pre-hold basename_lock_dir <id> and assert EVERY accepted
#           spelling blocks, plus a live cross-spelling concurrent-append
#           serialization check (all blocks land, attempts unique).
#   Test 4  (materialize-active shares append's lock) must still pass
#   Test 4b (deterministic append/materialize contention) must still pass
#   Test 5  (trap releases lock on die)             must still pass
#   Test 6  (stale >120s lock reclaimed with warn)  must still pass
#   Test 6b (stale reclaim under contention)        must still pass
#   Test 7  (vanished-dir stat-fail -> clean retry) must still pass
#
#   Tests 1/4/4b/5/6/6b/7 build their pre-held and asserted lock paths through
#   the key_for_id() helper below — after t635_30 lands, update that ONE helper
#   to the resolved-basename derivation (for this fixture: `t<id>_x`) and they
#   keep passing. Only 2a/2b/3 name a spelling explicitly, deliberately, via
#   raw_lock_dir / basename_lock_dir / alias_lock_dir: they ARE the
#   characterization of the derivation and must have their outcomes swapped,
#   not re-keyed.
#
# NOTE: acquire_gate_lock is a NON-REENTRANT mkdir lock (nested acquisition of
# the same key retries 20x at 0.3s and dies) — no test here nests acquisitions.
# Its lock path is hardcoded under a fixed prefix (mirrored here as
# GATE_LOCK_BASE) and is not TMPDIR-scoped, and there is no env seam for it —
# so the task id is the ONLY isolation lever this suite has. The fixture ids in
# IDS are therefore derived per run from $$ (t1485): fixed ids kept the suite
# out of other suites' key space but gave zero isolation from a second instance
# of ITSELF, which made two concurrent runs read each other's locks as the
# "foreign" lock these tests characterize. The exit trap removes every lock dir
# it may have touched.
#
# Run: bash tests/test_gate_lock_characterization.sh
# Expected runtime: ~15s (two ~6s lock-exhaustion tests).

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"

# Resolve a python interpreter for the materialize-active paths (may be empty).
PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; resolve_python 2>/dev/null || true)"

# The lock key aitask_gate.sh derives for a task id — TODAY: the raw argument
# (`key="${task_id//\//_}"`). After t635_30 switches to the resolved-file
# basename, update this ONE line to `printf 't%s_x' "$1"` (this fixture's
# basename shape) and tests 1/4/4b/5/6 keep passing unchanged.
key_for_id() {
    printf '%s' "$1"
}

# The one place this file spells the gate lock path. Mirrors the hardcoded
# construction in acquire_gate_lock (aitask_gate.sh) — there is no env seam for
# it, which is why the task id is the only isolation lever available below.
GATE_LOCK_BASE='/tmp/aitask_gate_lock_'

# Tests 2a/2b/3 characterize the key derivation itself, so they name each
# spelling explicitly rather than routing through key_for_id().
raw_lock_dir()      { printf '%s%s'    "$GATE_LOCK_BASE" "$1"; }
basename_lock_dir() { printf '%st%s_x' "$GATE_LOCK_BASE" "$1"; }
alias_lock_dir()    { printf '%st%s'   "$GATE_LOCK_BASE" "$1"; }

lock_dir_for_id() { raw_lock_dir "$(key_for_id "$1")"; }

# Per-run task-id namespace (t1485). With fixed ids, two concurrent runs of THIS
# file pre-hold, backdate and assert on the same lock dirs, and each reads the
# other's lock as the "foreign" lock these tests characterize. $$ is this file's
# own shell pid — unique among live processes, which is exactly the collision
# window.
ID_BASE="9$$"
ID1="${ID_BASE}1"; ID2="${ID_BASE}2"; ID3="${ID_BASE}3"; ID4="${ID_BASE}4"
ID5="${ID_BASE}5"; ID6="${ID_BASE}6"; ID7="${ID_BASE}7"; ID8="${ID_BASE}8"
IDS=("$ID1" "$ID2" "$ID3" "$ID4" "$ID5" "$ID6" "$ID7" "$ID8")

LOCK_DIRS=()
for id in "${IDS[@]}"; do
    LOCK_DIRS+=( "$(raw_lock_dir "$id")" \
                 "$(basename_lock_dir "$id")" \
                 "$(alias_lock_dir "$id")" )
done

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_gatelock_XXXXXX")"
cleanup() {
    rm -rf "$TMP"
    local d
    for d in "${LOCK_DIRS[@]}"; do
        rmdir "$d" 2>/dev/null || true
        rm -rf "$d".stale.* 2>/dev/null || true
    done
}
trap cleanup EXIT

# Pre-flight clear. Because pids are unique among LIVE processes, anything
# already sitting at one of our paths can only be a leak from a dead run that
# was killed before its trap fired — so removing it is safe, and (unlike the
# former fixed-id scheme) cannot mask a concurrent peer.
cleanup_lock_dir_leaks() {
    local d
    for d in "${LOCK_DIRS[@]}"; do
        rmdir "$d" 2>/dev/null || true
        rm -rf "$d".stale.* 2>/dev/null || true
    done
}
cleanup_lock_dir_leaks

# --- fixture ---------------------------------------------------------------

mkdir -p "$TMP/aitasks/metadata/profiles"
cat > "$TMP/aitasks/metadata/gates.yaml" <<'EOF'
gates:
  tests_pass:
    type: machine
    description: "Run project test suite; must all pass"
EOF
printf 'name: fast\ndefault_gates: [tests_pass]\n' \
    > "$TMP/aitasks/metadata/profiles/fast.yaml"

make_task() {
    local id="$1"
    cat > "$TMP/aitasks/t${id}_x.md" <<EOF
---
status: Implementing
gates: [tests_pass]
---
Body for t${id}.
EOF
}
for id in "${IDS[@]}"; do make_task "$id"; done

run_gate() {
    ( cd "$TMP" && TASK_DIR=aitasks "$GATE" "$@" )
}

marker_count() {  # <id> — number of gate:tests_pass marker lines in the task file
    grep -c 'gate:tests_pass' "$TMP/aitasks/t${1}_x.md"
}

# ============================================================
echo "--- Test 1: same-spelling concurrent appends serialize ---"
# ============================================================
for i in 1 2 3 4; do
    run_gate append "$ID1" tests_pass pass >/dev/null 2>"$TMP/t1_err_$i.log" &
done
wait

# On an anomalous count, surface the contenders' stderr BEFORE the assert so a
# rare loss is diagnosable (e.g. a stale-reclaim warn would implicate the
# stat-fail TOCTOU in acquire_gate_lock's staleness check) instead of being an
# anonymous flake.
if [[ "$(marker_count "$ID1")" != "4" ]]; then
    echo "DIAG: concurrent-append anomaly — contender stderr follows:"
    cat "$TMP"/t1_err_*.log
fi
assert_eq "4 concurrent same-spelling appends -> 4 ledger blocks (no lost update)" \
    "4" "$(marker_count "$ID1")"
for a in 1 2 3 4; do
    assert_eq "attempt=$a present exactly once (appends serialized under the lock)" \
        "1" "$(grep -c "attempt=${a}\$" "$TMP/aitasks/t${ID1}_x.md")"
done
assert_dir_not_exists "lock dir released after normal exits" \
    "$(lock_dir_for_id "$ID1")"

# ============================================================
echo "--- Test 2a: held RAW-id lock blocks append (fail-closed exhaustion, ~6s) ---"
# ============================================================
mkdir "$(raw_lock_dir "$ID2")"
out="$(run_gate append "$ID2" tests_pass pass 2>&1)"; rc=$?
assert_exit_nonzero_rc "append dies when the raw-argument lock is held" "$rc"
assert_contains "die names the raw-id key and the 20-attempt budget" \
    "Failed to acquire gate append lock for ${ID2} after 20 attempts" "$out"
assert_not_contains "no ledger block written while blocked (no unlocked proceed)" \
    "## Gate Runs" "$(cat "$TMP/aitasks/t${ID2}_x.md")"
assert_dir_exists "die leaves the foreign lock dir intact (never releases an unowned lock)" \
    "$(raw_lock_dir "$ID2")"
rmdir "$(raw_lock_dir "$ID2")"

# ============================================================
echo "--- Test 2b: held FILE-BASENAME lock is ignored today (the t635_30 flip) ---"
# ============================================================
mkdir "$(basename_lock_dir "$ID2")"
out="$(run_gate append "$ID2" tests_pass pass 2>&1)"; rc=$?
assert_exit_zero_rc "append proceeds despite a held resolved-basename lock" "$rc"
assert_eq "ledger block written under the raw-id key" "1" "$(marker_count "$ID2")"
assert_dir_exists "the held basename lock dir was never touched" \
    "$(basename_lock_dir "$ID2")"
assert_dir_not_exists "the raw-id lock the script took was released" \
    "$(raw_lock_dir "$ID2")"
rmdir "$(basename_lock_dir "$ID2")"

# ============================================================
echo "--- Test 3: t-spelling dies at resolve, pre-lock (alias tripwire) ---"
# ============================================================
out="$(run_gate append "t${ID2}" tests_pass pass 2>&1)"; rc=$?
assert_exit_nonzero_rc "append t<id> exits nonzero" "$rc"
assert_contains "t-spelling fails task resolution (before any lock)" \
    "No task file found" "$out"
assert_not_contains "t-spelling resolve failure is noise-free (no archive_utils arithmetic crash)" \
    "unbound variable" "$out"
assert_eq "no ledger block appended by the t-spelling call" \
    "1" "$(marker_count "$ID2")"
assert_dir_not_exists "no lock dir was ever created for the t-spelled key" \
    "$(alias_lock_dir "$ID2")"

# ============================================================
echo "--- Test 4: materialize-active honors the same raw-id lock (~6s) ---"
# ============================================================
mkdir "$(lock_dir_for_id "$ID3")"
out="$(run_gate materialize-active "$ID3" --profile aitasks/metadata/profiles/fast.yaml 2>&1)"; rc=$?
assert_exit_nonzero_rc "materialize-active dies when append's raw-id lock is held" "$rc"
assert_contains "materialize-active exhausts the same lock budget" \
    "Failed to acquire gate append lock" "$out"
rmdir "$(lock_dir_for_id "$ID3")"

if [[ -n "$PY" ]]; then
    out="$(run_gate materialize-active "$ID3" --profile aitasks/metadata/profiles/fast.yaml 2>/dev/null)"
    assert_eq "negative control: same call succeeds once the lock is free" \
        "MATERIALIZED:tests_pass" "$out"
else
    echo "SKIP: no python resolvable — materialize-active negative control skipped"
fi

# ============================================================
echo "--- Test 4b: deterministic append/materialize contention (lost-update detector) ---"
# ============================================================
if [[ -n "$PY" ]]; then
    # Hold the mutex OURSELVES so overlap does not depend on process timing:
    # all three contenders below must enter the retry loop (neither verb can
    # touch the file before acquiring the lock).
    mkdir "$(lock_dir_for_id "$ID6")"
    run_gate materialize-active "$ID6" --profile aitasks/metadata/profiles/fast.yaml \
        >/dev/null 2>"$TMP/t4b_err_m.log" &
    run_gate append "$ID6" tests_pass pass >/dev/null 2>"$TMP/t4b_err_1.log" &
    run_gate append "$ID6" tests_pass pass >/dev/null 2>"$TMP/t4b_err_2.log" &
    sleep 1
    # Contention proof: with the lock held for a full second, none of the
    # contenders may have produced any effect yet.
    body="$(cat "$TMP/aitasks/t${ID6}_x.md")"
    assert_not_contains "while the lock is held: no ledger section yet" \
        "## Gate Runs" "$body"
    assert_not_contains "while the lock is held: no active_gates tuple yet" \
        "active_gates:" "$body"
    rmdir "$(lock_dir_for_id "$ID6")"
    wait

    if [[ "$(marker_count "$ID6")" != "2" ]]; then
        echo "DIAG: contention anomaly — contender stderr follows:"
        cat "$TMP"/t4b_err_*.log
    fi
    assert_eq "both appends landed after release (no lost ledger block)" \
        "2" "$(marker_count "$ID6")"
    for a in 1 2; do
        assert_eq "contended attempt=$a present exactly once" \
            "1" "$(grep -c "attempt=${a}\$" "$TMP/aitasks/t${ID6}_x.md")"
    done
    assert_contains "materialize-active's tuple landed too (no lost frontmatter update)" \
        "active_gates: [tests_pass]" "$(cat "$TMP/aitasks/t${ID6}_x.md")"
    run_gate status "$ID6" >/dev/null 2>&1; rc=$?
    assert_exit_zero_rc "task file still parses after contended writes" "$rc"
    assert_dir_not_exists "no lock dir left behind after contention" \
        "$(lock_dir_for_id "$ID6")"
else
    echo "SKIP: no python resolvable — contention test skipped"
fi

# ============================================================
echo "--- Test 5: lock released on die via the EXIT trap ---"
# ============================================================
# A guaranteed-failing "python": `command -v false` may return the shell
# builtin's bare name (not a path), which resolve_python's -x test rejects,
# silently falling through to a REAL interpreter — so ship our own.
printf '#!/bin/sh\nexit 1\n' > "$TMP/failpy"
chmod +x "$TMP/failpy"
out="$( cd "$TMP" && TASK_DIR=aitasks AIT_GATES_BACKEND=python \
    AIT_PYTHON="$TMP/failpy" "$GATE" append "$ID4" tests_pass pass 2>&1 )"; rc=$?
assert_exit_nonzero_rc "python-backend delegate failure dies" "$rc"
assert_contains "die comes from the delegate, after the lock was acquired" \
    "python gate_ledger append failed" "$out"
assert_dir_not_exists "EXIT trap released the lock on the die path" \
    "$(lock_dir_for_id "$ID4")"

# ============================================================
echo "--- Test 6: stale lock (>120s) reclaimed with warn ---"
# ============================================================
mkdir "$(lock_dir_for_id "$ID5")"
touch -t 202001010000 "$(lock_dir_for_id "$ID5")"
out="$(run_gate append "$ID5" tests_pass pass 2>&1)"; rc=$?
assert_exit_zero_rc "append succeeds after reclaiming the stale lock" "$rc"
assert_contains "stale reclaim warns" "Removing stale gate lock" "$out"
assert_eq "ledger block written after reclaim" "1" "$(marker_count "$ID5")"
assert_dir_not_exists "reclaimed-then-taken lock released on exit" \
    "$(lock_dir_for_id "$ID5")"

# ============================================================
echo "--- Test 6b: stale lock reclaimed under contention (single-winner mv) ---"
# ============================================================
mkdir "$(lock_dir_for_id "$ID7")"
touch -t 202001010000 "$(lock_dir_for_id "$ID7")"
run_gate append "$ID7" tests_pass pass >/dev/null 2>"$TMP/t6b_err_1.log" &
run_gate append "$ID7" tests_pass pass >/dev/null 2>"$TMP/t6b_err_2.log" &
wait

if [[ "$(marker_count "$ID7")" != "2" ]]; then
    echo "DIAG: stale-reclaim contention anomaly — contender stderr follows:"
    cat "$TMP"/t6b_err_*.log
fi
assert_eq "2 contenders through a stale lock -> 2 ledger blocks (no lost update)" \
    "2" "$(marker_count "$ID7")"
for a in 1 2; do
    assert_eq "reclaim-path attempt=$a present exactly once" \
        "1" "$(grep -c "attempt=${a}\$" "$TMP/aitasks/t${ID7}_x.md")"
done
assert_contains "at least one contender reclaimed the stale lock with warn" \
    "Removing stale gate lock" "$(cat "$TMP"/t6b_err_*.log)"
assert_dir_not_exists "stale-reclaimed lock released after both exits" \
    "$(lock_dir_for_id "$ID7")"

# ============================================================
echo "--- Test 7: vanished-dir stat failure -> clean mkdir retry (the TOCTOU) ---"
# ============================================================
# Deterministic reproduction of the observed race: mkdir fails, -d succeeds,
# then the lock dir vanishes before stat runs. A PATH shim intercepts stat for
# this one lock path, removes the dir, and fails — the fixed code must retry
# mkdir immediately instead of classifying age≈now as stale (the old
# `|| echo "0"` fallback warned "Removing stale gate lock" here).
REAL_STAT="$(command -v stat)"
T7_LOCK="$(lock_dir_for_id "$ID8")"
mkdir -p "$TMP/bin"
cat > "$TMP/bin/stat" <<EOF
#!/bin/sh
case "\$*" in
  *${T7_LOCK}*) rmdir "${T7_LOCK}" 2>/dev/null; exit 1 ;;
  *) exec "$REAL_STAT" "\$@" ;;
esac
EOF
chmod +x "$TMP/bin/stat"

mkdir "$T7_LOCK"   # fresh mtime: only the shim can make stat fail on it
out="$( cd "$TMP" && PATH="$TMP/bin:$PATH" TASK_DIR=aitasks \
    "$GATE" append "$ID8" tests_pass pass 2>&1 )"; rc=$?
assert_exit_zero_rc "append succeeds through the vanished-dir stat-fail path" "$rc"
assert_not_contains "stat failure is 'lock vanished — retry', never a stale reclaim" \
    "Removing stale gate lock" "$out"
assert_eq "ledger block written after the clean retry" "1" "$(marker_count "$ID8")"
assert_dir_not_exists "lock released on exit" "$T7_LOCK"

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
