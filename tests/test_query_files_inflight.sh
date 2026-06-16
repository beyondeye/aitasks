#!/usr/bin/env bash
# test_query_files_inflight.sh - Tests for the `inflight` subcommand (t635_7).
#
# `aitask_query_files.sh inflight` enumerates in-flight gated tasks — status
# Implementing AND a recorded "## Gate Runs" ledger — across BOTH active parents
# and active children, emitting:
#     INFLIGHT:<id>|<path>|<resume_point>|<archive_status>
# or NO_INFLIGHT when none match. It delegates the derived state to
# aitask_gate.sh (resume-point / archive-ready) — it does not re-implement it.
#
# Coverage:
#   - empty tree                                  -> NO_INFLIGHT
#   - parent Implementing + ledger (plan_approved) -> INFLIGHT, resume IMPLEMENT
#   - child  Implementing + ledger (plan+review)   -> INFLIGHT, resume POSTIMPL
#   - parent Implementing, NO ledger               -> excluded
#   - Ready task WITH a ledger                     -> excluded (status gate)
#   - archive_status with no declared gates        -> NO_GATES
#   - line shape INFLIGHT:<id>|<path>|<rp>|<as>
#
# Run: bash tests/test_query_files_inflight.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

QF="$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh"
GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"

# Export a throwaway TASK_DIR so both aitask_query_files.sh (scan) and the
# delegated aitask_gate.sh (resume-point / archive-ready) resolve into it.
setup_tree() {
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_inflight_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    export TASK_DIR="$tmp/aitasks"
    mkdir -p "$TASK_DIR/metadata"
}

make_task() {  # <id> <status>
    local id="$1" st="$2"
    {
        echo "---"
        echo "priority: high"
        echo "status: $st"
        echo "---"
        echo
        echo "Body for t${id}."
    } > "$TASK_DIR/t${id}_demo.md"
}

make_child() {  # <parent> <child> <status>
    local parent="$1" child="$2" st="$3"
    mkdir -p "$TASK_DIR/t${parent}"
    {
        echo "---"
        echo "priority: high"
        echo "status: $st"
        echo "---"
        echo
        echo "Body for t${parent}_${child}."
    } > "$TASK_DIR/t${parent}/t${parent}_${child}_demo.md"
}

# --- Test: empty tree -> NO_INFLIGHT ---
test_empty() {
    echo "=== empty tree -> NO_INFLIGHT ==="
    setup_tree
    assert_eq_trim "no tasks -> NO_INFLIGHT" "NO_INFLIGHT" "$("$QF" inflight)"
}

# --- Test: include/exclude predicate + derived state ---
test_predicate() {
    echo "=== include/exclude predicate + derived state ==="
    setup_tree

    # (include) parent Implementing + ledger, plan approved -> IMPLEMENT.
    make_task 500 Implementing
    "$GATE" append 500 plan_approved pass type=human >/dev/null

    # (include) child Implementing + ledger, plan + review -> POSTIMPL.
    make_child 502 3 Implementing
    "$GATE" append 502_3 plan_approved pass type=human >/dev/null
    "$GATE" append 502_3 review_approved pass type=human >/dev/null

    # (exclude) parent Implementing but NO ledger.
    make_task 501 Implementing

    # (exclude) Ready task WITH a ledger (status gate must drop it).
    make_task 503 Ready
    "$GATE" append 503 plan_approved pass type=human >/dev/null

    local out
    out="$("$QF" inflight)"

    # Included: exact line shape with derived resume_point + archive_status.
    assert_contains "parent 500 included (IMPLEMENT, NO_GATES)" \
        "INFLIGHT:500|$TASK_DIR/t500_demo.md|IMPLEMENT|NO_GATES" "$out"
    assert_contains "child 502_3 included (POSTIMPL, NO_GATES)" \
        "INFLIGHT:502_3|$TASK_DIR/t502/t502_3_demo.md|POSTIMPL|NO_GATES" "$out"

    # Excluded: no-ledger Implementing, and Ready-with-ledger.
    assert_not_contains "parent 501 (no ledger) excluded" "INFLIGHT:501|" "$out"
    assert_not_contains "task 503 (Ready) excluded" "INFLIGHT:503|" "$out"

    # Not the empty marker when matches exist.
    assert_not_contains "non-empty -> no NO_INFLIGHT marker" "NO_INFLIGHT" "$out"
}

# --- Run ---
test_empty
test_predicate

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
