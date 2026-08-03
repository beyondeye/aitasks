#!/usr/bin/env bash
# test_gate_reentry.sh - Tests for ledger-driven re-entry (t635_5).
#
# Unit — the resume-point decision (gate_ledger.resume_point, surfaced as
#        `aitask_gate.sh resume-point` and `gate_ledger.py resume-point`):
#          empty ledger / no plan_approved        -> PLAN
#          plan_approved pass, review pending      -> IMPLEMENT
#          + risk_evaluated pass (not a boundary)  -> IMPLEMENT
#          + review_approved pass                  -> POSTIMPL
#          + merge_approved pass                   -> POSTIMPL
#        Derivation (last-run-wins via derive_status):
#          plan_approved fail->pass                -> IMPLEMENT
#          plan_approved pass->fail (re-opened)    -> PLAN
#          review_approved pending + plan pass     -> IMPLEMENT
#        Child-task id path resolves (<parent>_<child>).
#        Degrade: aitask_gate.sh keeps a `|| echo "PLAN"` python fallback.
#
# Abort demotion (t1380) — task-abort.md's `plan_approved fail note=aborted`
#        re-opens a stale approval, on an Implementing task, so the PLAN result
#        is produced by the LEDGER and not by Check 5's status gate. Also covers
#        an abort after review (POSTIMPL -> PLAN).
# skip semantics (t1380) — `skip` is NOT a pass for re-entry, unlike
#        SATISFIED_STATUSES = {pass, skip} used by archive/deps. `recorded-pass`
#        mirrors this strict predicate, so it stays pinned here.
#
# Run: bash tests/test_gate_reentry.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"
GATE_PY="$PROJECT_DIR/.aitask-scripts/lib/gate_ledger.py"
PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; resolve_python 2>/dev/null || true)"

# ============================================================
# Unit layer: resume-point decision
# ============================================================

unit_setup() {
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_reentry_unit_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    export TASK_DIR="$tmp/aitasks"
    mkdir -p "$TASK_DIR/metadata"
}

# Write an Implementing parent task file (no gate runs yet).
make_unit_task() {
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

# Write an Implementing child task file under t<parent>/.
make_unit_child() {
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

test_unit_resume_point() {
    echo "=== Unit: resume-point decision ==="
    unit_setup

    # Empty ledger -> PLAN.
    make_unit_task 400
    assert_eq_trim "empty ledger -> PLAN" "PLAN" "$("$GATE" resume-point 400)"

    # plan_approved pass, review pending -> IMPLEMENT.
    make_unit_task 401
    "$GATE" append 401 plan_approved pass type=human >/dev/null
    assert_eq_trim "plan_approved -> IMPLEMENT" "IMPLEMENT" "$("$GATE" resume-point 401)"

    # risk_evaluated is not a re-entry boundary -> still IMPLEMENT.
    "$GATE" append 401 risk_evaluated pass type=machine >/dev/null
    assert_eq_trim "+risk_evaluated -> IMPLEMENT" "IMPLEMENT" "$("$GATE" resume-point 401)"

    # review_approved pass -> POSTIMPL.
    "$GATE" append 401 review_approved pass type=human >/dev/null
    assert_eq_trim "+review_approved -> POSTIMPL" "POSTIMPL" "$("$GATE" resume-point 401)"

    # merge_approved pass (deep in Step 9) -> still POSTIMPL.
    "$GATE" append 401 merge_approved pass type=human >/dev/null
    assert_eq_trim "+merge_approved -> POSTIMPL" "POSTIMPL" "$("$GATE" resume-point 401)"

    # Derivation last-wins: a re-run fail->pass on plan_approved -> IMPLEMENT.
    make_unit_task 402
    "$GATE" append 402 plan_approved fail type=human >/dev/null
    "$GATE" append 402 plan_approved pass type=human >/dev/null
    assert_eq_trim "plan fail->pass -> IMPLEMENT" "IMPLEMENT" "$("$GATE" resume-point 402)"

    # Re-opened checkpoint: a later fail demotes the resume stage -> PLAN.
    "$GATE" append 402 plan_approved fail type=human >/dev/null
    assert_eq_trim "plan re-opened (fail wins) -> PLAN" "PLAN" "$("$GATE" resume-point 402)"

    # review_approved recorded but only pending (not pass) -> IMPLEMENT.
    make_unit_task 403
    "$GATE" append 403 plan_approved pass type=human >/dev/null
    "$GATE" append 403 review_approved pending type=human >/dev/null
    assert_eq_trim "review pending -> IMPLEMENT" "IMPLEMENT" "$("$GATE" resume-point 403)"

    # Child-task id path resolves (<parent>_<child>).
    make_unit_child 404 1
    "$GATE" append 404_1 plan_approved pass type=human >/dev/null
    "$GATE" append 404_1 review_approved pass type=human >/dev/null
    assert_eq_trim "child id -> POSTIMPL" "POSTIMPL" "$("$GATE" resume-point 404_1)"

    # Direct python parity on the same fixtures.
    if [[ -n "$PY" ]]; then
        assert_eq_trim "py: empty -> PLAN" "PLAN" \
            "$("$PY" "$GATE_PY" resume-point "$TASK_DIR/t400_demo.md")"
        assert_eq_trim "py: full -> POSTIMPL" "POSTIMPL" \
            "$("$PY" "$GATE_PY" resume-point "$TASK_DIR/t401_demo.md")"
        assert_eq_trim "py: re-opened -> PLAN" "PLAN" \
            "$("$PY" "$GATE_PY" resume-point "$TASK_DIR/t402_demo.md")"
        assert_eq_trim "py: child -> POSTIMPL" "POSTIMPL" \
            "$("$PY" "$GATE_PY" resume-point "$TASK_DIR/t404/t404_1_demo.md")"
    else
        echo "(skipping python-parity asserts: no interpreter resolved)"
    fi
}

test_abort_demotion_invariant() {
    echo "=== Unit: abort's demotion is an invariant, not an accident (t1380) ==="
    unit_setup

    # An approved plan, then an abort that rejects it. task-abort.md appends
    # `plan_approved fail note=aborted`; the resume point must fall back to
    # PLAN so the next pick re-plans instead of resuming into the rejected plan.
    make_unit_task 410
    "$GATE" append 410 plan_approved pass type=human >/dev/null
    assert_eq_trim "before abort -> IMPLEMENT" "IMPLEMENT" "$("$GATE" resume-point 410)"
    "$GATE" append 410 plan_approved fail type=human note=aborted >/dev/null
    assert_eq_trim "after abort -> PLAN" "PLAN" "$("$GATE" resume-point 410)"

    # The invariant must hold WITHOUT Check 5's `status == Implementing` gate
    # doing the work — that gate is a property of the workflow prose, not of the
    # ledger, and relaxing it must not resurrect the stale approval. The task
    # file here stays `Implementing` precisely so nothing but the demotion can
    # be producing the PLAN result.
    assert_contains "task stayed Implementing (status gate is not what saved us)" \
        "status: Implementing" "$(cat "$TASK_DIR/t410_demo.md")"

    # An abort AFTER review (a Step 8 abort) demotes all the way past POSTIMPL.
    make_unit_task 411
    "$GATE" append 411 plan_approved pass type=human >/dev/null
    "$GATE" append 411 review_approved pass type=human >/dev/null
    assert_eq_trim "reviewed -> POSTIMPL" "POSTIMPL" "$("$GATE" resume-point 411)"
    "$GATE" append 411 plan_approved fail type=human note=aborted >/dev/null
    assert_eq_trim "abort after review -> PLAN" "PLAN" "$("$GATE" resume-point 411)"
}

test_skip_is_not_a_pass() {
    echo "=== Unit: skip is not pass for re-entry (SATISFIED_STATUSES divergence) ==="
    unit_setup

    # resume_point tests `status == "pass"` strictly, unlike archive_status /
    # dependents_status which treat SATISFIED_STATUSES = {pass, skip} as
    # satisfied. Nothing pinned that divergence before; `recorded-pass` mirrors
    # the strict predicate, so it has to stay pinned here.
    make_unit_task 412
    "$GATE" append 412 plan_approved skip type=human >/dev/null
    assert_eq_trim "plan_approved skip -> PLAN (not IMPLEMENT)" "PLAN" "$("$GATE" resume-point 412)"

    make_unit_task 413
    "$GATE" append 413 plan_approved pass type=human >/dev/null
    "$GATE" append 413 review_approved skip type=human >/dev/null
    assert_eq_trim "review_approved skip -> IMPLEMENT (not POSTIMPL)" \
        "IMPLEMENT" "$("$GATE" resume-point 413)"
}

test_degrade_fallback() {
    echo "=== Unit: python-absent degrade shape ==="
    # The bash subcommand must degrade to PLAN when the python delegation fails,
    # mirroring archive-ready's NO_GATES degrade. Assert the fallback is wired
    # (a live no-python run is environment-fragile; the static guard is stable).
    assert_contains "resume-point degrades to PLAN" \
        'delegate_python resume-point "$file" || echo "PLAN"' \
        "$(cat "$GATE")"
}

# --- Run ---
test_unit_resume_point
test_abort_demotion_invariant
test_skip_is_not_a_pass
test_degrade_fallback

# Cleanup
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
