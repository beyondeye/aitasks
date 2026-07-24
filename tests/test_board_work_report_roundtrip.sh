#!/usr/bin/env bash
# test_board_work_report_roundtrip.sh - Board `w` flow ↔ gatherer round-trip
# equivalence (t1162_4).
#
# On a shared fixture tree (Unsorted tasks, boardidx ties, archived tasks, a
# parent with children, a task missing boardcol, a phantom layout stub, and a
# stale column_order entry) the oracle computes the exact --columns/--tasks
# args the board `w` flow would launch (via the flow's real code paths), runs
# the real gatherer CLI with them, and asserts identical membership AND order
# per column. See tests/lib/work_report_flow_equiv.py.
#
# Run: bash tests/test_board_work_report_roundtrip.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

FLOW_EQUIV="$PROJECT_DIR/tests/lib/work_report_flow_equiv.py"
PYTHON="$(require_ait_python)"

make_task() {  # <path> <boardcol|-> <boardidx|-> [extra frontmatter lines...]
    local path="$1" col="$2" idx="$3"
    shift 3
    {
        echo "---"
        echo "priority: high"
        echo "effort: medium"
        echo "status: Ready"
        [[ "$col" != "-" ]] && echo "boardcol: $col"
        [[ "$idx" != "-" ]] && echo "boardidx: $idx"
        local line
        for line in "$@"; do echo "$line"; done
        echo "---"
        echo ""
        echo "## Context"
        echo "fixture"
    } > "$path"
}

test_flow_roundtrip() {
    TOTAL=$((TOTAL + 1))
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_wr_flow_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    export TASK_DIR="$tmp/aitasks"
    mkdir -p "$TASK_DIR/metadata" "$TASK_DIR/archived" "$TASK_DIR/t20"

    # "ghost" is a stale column_order entry with no columns definition: the
    # board drops it, the flow must not offer it, the gatherer would reject it.
    printf '%s\n' '{"columns":[{"id":"now","title":"Now"},{"id":"next","title":"Next"}],"column_order":["now","ghost","next"]}' \
        > "$TASK_DIR/metadata/board_config.json"

    # boardidx tie (10/10) → filename tie-break; parent with children;
    # missing boardcol → unordered; archived + child + phantom excluded.
    make_task "$TASK_DIR/t11_bravo.md" now 10
    make_task "$TASK_DIR/t10_alpha.md" now 10
    make_task "$TASK_DIR/t12_charlie.md" next 5
    make_task "$TASK_DIR/t20_parent.md" now 2 "children_to_implement: [t20_1]"
    make_task "$TASK_DIR/t20/t20_1_child.md" now 1
    make_task "$TASK_DIR/t30_unsorted.md" - -
    make_task "$TASK_DIR/archived/t40_done.md" now 1
    {
        echo "---"
        echo "boardcol: now"
        echo "boardidx: 3"
        echo "---"
    } > "$TASK_DIR/t99_phantom.md"

    local out rc
    out="$("$PYTHON" "$FLOW_EQUIV" "$PROJECT_DIR" 2>&1)"
    rc=$?
    if [[ $rc -eq 0 ]] && [[ "$out" == *"FLOW_EQUIV_OK"* ]]; then
        PASS=$((PASS + 1))
        echo "PASS: flow_roundtrip"
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: flow_roundtrip (rc=$rc)"
        echo "$out"
    fi
    unset TASK_DIR
}

test_flow_roundtrip

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
