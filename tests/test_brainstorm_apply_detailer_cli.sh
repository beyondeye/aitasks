#!/usr/bin/env bash
# CLI round-trip test for ./.aitask-scripts/aitask_brainstorm_apply_detailer.sh
#
# Builds a synthetic crew worktree under .aitask-crews/crew-brainstorm-<num>
# inside the repo root, invokes the wrapper, and checks the structured
# output and resulting on-disk state. Cleans up after itself.

set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$THIS_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Pick a high task number unlikely to collide with real crews.
TASK_NUM="999741"
CREW_DIR=".aitask-crews/crew-brainstorm-${TASK_NUM}"
AGENT="detailer_001"
TARGET="n000_init"

PASS=0
FAIL=0

cleanup() { rm -rf "$CREW_DIR"; }
trap cleanup EXIT

# Build the crew worktree.
rm -rf "$CREW_DIR"
mkdir -p "$CREW_DIR/br_nodes" "$CREW_DIR/br_proposals" "$CREW_DIR/br_plans"

cat > "$CREW_DIR/br_nodes/${TARGET}.yaml" <<'EOF'
node_id: n000_init
parents: []
description: Target node
proposal_file: br_proposals/n000_init.md
created_at: "2026-01-01 00:00"
created_by_group: bootstrap
EOF

cat > "$CREW_DIR/br_graph_state.yaml" <<EOF
current_head: ${TARGET}
history:
- ${TARGET}
next_node_id: 1
active_dimensions: []
EOF

write_valid_output() {
    cat > "$CREW_DIR/${AGENT}_output.md" <<'EOF'
--- DETAILED_PLAN_START ---
# Implementation Plan
<!-- section: prerequisites -->
### Prerequisites
- Python 3.11
<!-- /section: prerequisites -->
--- DETAILED_PLAN_END ---
EOF
}
write_valid_output

# Positive case.
out=$(./.aitask-scripts/aitask_brainstorm_apply_detailer.sh "$TASK_NUM" "$AGENT" "$TARGET")
expected="APPLIED:br_plans/n000_init_plan.md"
if [[ "$out" == "$expected" ]]; then
    echo "PASS: positive apply prints '$expected'"
    PASS=$((PASS + 1))
else
    echo "FAIL: positive apply — expected '$expected', got '$out'"
    FAIL=$((FAIL + 1))
fi

if [[ -f "$CREW_DIR/br_plans/n000_init_plan.md" ]] \
   && grep -q "Implementation Plan" "$CREW_DIR/br_plans/n000_init_plan.md" \
   && grep -q "section: prerequisites" "$CREW_DIR/br_plans/n000_init_plan.md"; then
    echo "PASS: detailed plan written with section markers preserved"
    PASS=$((PASS + 1))
else
    echo "FAIL: detailed plan missing, empty, or section markers stripped"
    FAIL=$((FAIL + 1))
fi

if grep -q "plan_file: br_plans/n000_init_plan.md" \
        "$CREW_DIR/br_nodes/n000_init.yaml"; then
    echo "PASS: target node plan_file set"
    PASS=$((PASS + 1))
else
    echo "FAIL: target node plan_file not set"
    FAIL=$((FAIL + 1))
fi

# The detailer enriches an existing node — graph state must be untouched.
if grep -q "current_head: n000_init" "$CREW_DIR/br_graph_state.yaml" \
   && grep -q "next_node_id: 1" "$CREW_DIR/br_graph_state.yaml"; then
    echo "PASS: graph state untouched (no head advance, no id consumed)"
    PASS=$((PASS + 1))
else
    echo "FAIL: graph state wrongly modified"
    FAIL=$((FAIL + 1))
fi

# Idempotent re-run: re-applying the same output overwrites the plan and
# succeeds (re-detail semantics) — unlike the patcher it does not error.
if out=$(./.aitask-scripts/aitask_brainstorm_apply_detailer.sh \
            "$TASK_NUM" "$AGENT" "$TARGET"); then
    if [[ "$out" == "$expected" ]]; then
        echo "PASS: idempotent re-run succeeds with same APPLIED output"
        PASS=$((PASS + 1))
    else
        echo "FAIL: re-run output unexpected: $out"
        FAIL=$((FAIL + 1))
    fi
else
    echo "FAIL: re-run unexpectedly failed: $out"
    FAIL=$((FAIL + 1))
fi

# Negative: missing DETAILED_PLAN delimiter.
printf '%s\n' "# plan without delimiters" > "$CREW_DIR/${AGENT}_output.md"
if out=$(./.aitask-scripts/aitask_brainstorm_apply_detailer.sh \
            "$TASK_NUM" "$AGENT" "$TARGET" 2>&1); then
    echo "FAIL: missing-delimiter apply unexpectedly succeeded: $out"
    FAIL=$((FAIL + 1))
else
    if [[ "$out" == APPLY_FAILED:* ]]; then
        echo "PASS: missing delimiter → APPLY_FAILED"
        PASS=$((PASS + 1))
    else
        echo "FAIL: missing-delimiter output unexpected: $out"
        FAIL=$((FAIL + 1))
    fi
fi

# Negative: missing target node.
write_valid_output
rm -f "$CREW_DIR/br_nodes/${TARGET}.yaml"
if out=$(./.aitask-scripts/aitask_brainstorm_apply_detailer.sh \
            "$TASK_NUM" "$AGENT" "$TARGET" 2>&1); then
    echo "FAIL: missing-target apply unexpectedly succeeded: $out"
    FAIL=$((FAIL + 1))
else
    if [[ "$out" == APPLY_FAILED:*"target node"* ]]; then
        echo "PASS: missing target node → APPLY_FAILED"
        PASS=$((PASS + 1))
    else
        echo "FAIL: missing-target output unexpected: $out"
        FAIL=$((FAIL + 1))
    fi
fi

# Argument validation.
if out=$(./.aitask-scripts/aitask_brainstorm_apply_detailer.sh "$TASK_NUM" 2>&1); then
    echo "FAIL: missing args unexpectedly succeeded"
    FAIL=$((FAIL + 1))
else
    if [[ "$out" == *"Usage:"* ]]; then
        echo "PASS: missing args → Usage message"
        PASS=$((PASS + 1))
    else
        echo "FAIL: missing args output unexpected: $out"
        FAIL=$((FAIL + 1))
    fi
fi

echo
echo "Total: $((PASS + FAIL))   Passed: $PASS   Failed: $FAIL"
[[ $FAIL -eq 0 ]]
