#!/usr/bin/env bash
# test_gate_recorded_pass.sh - Unit tests for `aitask_gate.sh recorded-pass` (t1380).
#
# The verb is a DECISION verb over the RECORDED ledger: exit 0 iff the gate's
# current derived run (last-marker-wins) has status `pass`; exit 1 otherwise.
#
# Coverage:
#   1. Decision matrix — absent / pass / pass->fail / fail->pass / skip /
#      pending / running / error, plus a second gate not interfering.
#   2. The strict `== pass` predicate: `skip` is NOT a pass here, even though
#      archive-ready's SATISFIED_STATUSES treats {pass, skip} as satisfied.
#      This is the deliberate divergence recorded-pass shares with resume-point.
#   3. Child-task ids (<parent>_<child>) resolve.
#   4. Usage errors exit non-zero.
#   5. bash <-> python backend agreement on every row (AIT_GATES_BACKEND=python).
#   6. `status` still byte-matches the python backend after the shared
#      _derive_gate_runs_table extraction — including a run with an EMPTY
#      attempt field, which is what a tab-separated table would have collapsed.
#
# Run: bash tests/test_gate_recorded_pass.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"
PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; resolve_python 2>/dev/null || true)"

setup() {
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_recorded_pass_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    export TASK_DIR="$tmp/aitasks"
    mkdir -p "$TASK_DIR/metadata"
}

make_task() {
    local id="$1"
    {
        echo "---"
        echo "priority: high"
        echo "status: Implementing"
        echo "---"
        echo
        echo "Body for t${id}."
    } > "$TASK_DIR/t${id}_demo.md"
}

make_child() {
    local parent="$1" child="$2"
    mkdir -p "$TASK_DIR/t${parent}"
    {
        echo "---"
        echo "priority: high"
        echo "status: Implementing"
        echo "---"
        echo
        echo "Body for t${parent}_${child}."
    } > "$TASK_DIR/t${parent}/t${parent}_${child}_demo.md"
}

# assert_recorded <desc> <expect: yes|no> <task-id> <gate>
# Runs the verb on BOTH backends and asserts they agree with the expectation.
assert_recorded() {
    local desc="$1" expect="$2" id="$3" gate="$4"
    local rc_bash rc_py
    "$GATE" recorded-pass "$id" "$gate" >/dev/null 2>&1; rc_bash=$?
    if [[ "$expect" == "yes" ]]; then
        assert_exit_zero_rc "bash: $desc" "$rc_bash"
    else
        assert_exit_nonzero_rc "bash: $desc" "$rc_bash"
    fi

    if [[ -n "$PY" ]]; then
        AIT_GATES_BACKEND=python "$GATE" recorded-pass "$id" "$gate" >/dev/null 2>&1; rc_py=$?
        # Compare the two backends as booleans, not as raw codes.
        local b p
        b=$([[ "$rc_bash" -eq 0 ]] && echo yes || echo no)
        p=$([[ "$rc_py" -eq 0 ]] && echo yes || echo no)
        assert_eq "backend parity: $desc" "$b" "$p"
    fi
}

test_decision_matrix() {
    echo "=== recorded-pass: decision matrix ==="
    setup

    # Empty ledger -> not recorded.
    make_task 700
    assert_recorded "empty ledger -> not pass" no 700 plan_approved

    # pass -> recorded.
    make_task 701
    "$GATE" append 701 plan_approved pass type=human >/dev/null
    assert_recorded "pass -> recorded" yes 701 plan_approved

    # A different gate on the same task is unaffected.
    assert_recorded "other gate untouched" no 701 review_approved

    # pass -> fail (the abort demotion) -> no longer recorded.
    "$GATE" append 701 plan_approved fail type=human note=aborted >/dev/null
    assert_recorded "pass->fail demotes" no 701 plan_approved

    # fail -> pass (re-approval) -> recorded again.
    "$GATE" append 701 plan_approved pass type=human >/dev/null
    assert_recorded "fail->pass re-records" yes 701 plan_approved

    # skip is NOT a pass — the deliberate divergence from SATISFIED_STATUSES.
    make_task 702
    "$GATE" append 702 plan_approved skip type=human >/dev/null
    assert_recorded "skip is not a pass" no 702 plan_approved

    # pending / running / error are not passes either.
    make_task 703
    "$GATE" append 703 plan_approved pending type=human >/dev/null
    assert_recorded "pending is not a pass" no 703 plan_approved
    "$GATE" append 703 plan_approved running type=machine >/dev/null
    assert_recorded "running is not a pass" no 703 plan_approved
    "$GATE" append 703 plan_approved error type=machine >/dev/null
    assert_recorded "error is not a pass" no 703 plan_approved

    # A gate that was never appended at all on a task WITH a ledger.
    assert_recorded "unrecorded gate on populated ledger" no 703 merge_approved
}

test_child_id() {
    echo "=== recorded-pass: child task ids ==="
    setup
    make_child 704 2
    assert_recorded "child: empty -> not pass" no 704_2 plan_approved
    "$GATE" append 704_2 plan_approved pass type=human >/dev/null
    assert_recorded "child: pass -> recorded" yes 704_2 plan_approved
}

test_usage_errors() {
    echo "=== recorded-pass: usage errors ==="
    setup
    make_task 705
    assert_exit_nonzero "missing both args" "$GATE" recorded-pass
    assert_exit_nonzero "missing gate arg" "$GATE" recorded-pass 705
    assert_exit_nonzero "unresolvable task id" "$GATE" recorded-pass 999999 plan_approved

    local err
    err="$("$GATE" recorded-pass 2>&1 >/dev/null || true)"
    assert_contains "usage message on stderr" "recorded-pass <task-id> <gate>" "$err"
}

test_status_parity_after_extraction() {
    echo "=== status: bash/python byte parity after _derive_gate_runs_table extraction ==="
    if [[ -z "$PY" ]]; then
        echo "(skipping: no interpreter resolved)"
        return
    fi
    setup
    make_task 706
    # `attempt` auto-increments for pass/fail ONLY, so a skip run has an EMPTY
    # attempt field. That empty field is the regression this asserts: a
    # tab-separated derivation table would let `read` collapse it and shift the
    # run id into the attempt column.
    "$GATE" append 706 plan_approved pass type=human >/dev/null
    "$GATE" append 706 review_approved skip type=human >/dev/null
    "$GATE" append 706 merge_approved pending type=human >/dev/null

    local out_bash out_py
    out_bash="$("$GATE" status 706)"
    out_py="$(AIT_GATES_BACKEND=python "$GATE" status 706)"
    assert_eq "status byte parity" "$out_py" "$out_bash"

    # Pin the empty-attempt shape explicitly so the parity assert cannot pass
    # by both backends being wrong in the same way.
    assert_contains_re "skip row renders (run …) with no attempt" \
        '^review_approved: skip \(run [^,]*\)$' "$out_bash"
    assert_contains_re "pass row renders attempt AND run" \
        '^plan_approved: pass \(attempt 1, run .*\)$' "$out_bash"
}

# --- Run ---
test_decision_matrix
test_child_id
test_usage_errors
test_status_parity_after_extraction

for dir in "${CLEANUP_DIRS[@]}"; do
    rm -rf "$dir"
done

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
if [[ "$FAIL" -gt 0 ]]; then
    exit 1
else
    echo "All tests PASSED"
fi
