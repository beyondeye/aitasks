#!/usr/bin/env bash
# CLI round-trip test for ./.aitask-scripts/aitask_brainstorm_apply_patcher.sh
#
# Builds a synthetic crew worktree under .aitask-crews/crew-brainstorm-<num>
# inside the repo root, invokes the wrapper, and checks the structured
# output and resulting on-disk state. Cleans up after itself.

set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$THIS_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Pick a high task number unlikely to collide with real crews.
TASK_NUM="999743"
CREW_DIR=".aitask-crews/crew-brainstorm-${TASK_NUM}"
AGENT="patcher_001"
SOURCE="n000_init"

PASS=0
FAIL=0

cleanup() { rm -rf "$CREW_DIR"; }
trap cleanup EXIT

# Build the crew worktree.
rm -rf "$CREW_DIR"
mkdir -p "$CREW_DIR/br_nodes" "$CREW_DIR/br_proposals" "$CREW_DIR/br_plans"

cat > "$CREW_DIR/br_nodes/${SOURCE}.yaml" <<'EOF'
node_id: n000_init
parents: []
description: Source node
proposal_file: br_proposals/n000_init.md
created_at: "2026-01-01 00:00"
created_by_group: bootstrap
EOF

cat > "$CREW_DIR/br_proposals/${SOURCE}.md" <<'EOF'
## Overview
Source proposal body for CLI round-trip test.
EOF

cat > "$CREW_DIR/br_graph_state.yaml" <<EOF
current_head: ${SOURCE}
history:
- ${SOURCE}
next_node_id: 1
active_dimensions: []
EOF

cat > "$CREW_DIR/${AGENT}_output.md" <<'EOF'
--- PATCHED_PLAN_START ---
# Patched plan
Body line one.
Body line two.
--- PATCHED_PLAN_END ---
--- IMPACT_START ---
**NO_IMPACT**
Justification: small change, no architectural impact.
--- IMPACT_END ---
--- METADATA_START ---
node_id: n001_cli_test
parents: [n000_init]
description: CLI round-trip test patched node
proposal_file: br_proposals/n000_init.md
created_at: "2026-05-04 12:52"
created_by_group: patch_001
component_x: foo
--- METADATA_END ---
EOF

# Positive case.
out=$(./.aitask-scripts/aitask_brainstorm_apply_patcher.sh "$TASK_NUM" "$AGENT" "$SOURCE")
expected="APPLIED:n001_cli_test:NO_IMPACT"
if [[ "$out" == "$expected" ]]; then
    echo "PASS: positive apply prints '$expected'"
    PASS=$((PASS + 1))
else
    echo "FAIL: positive apply — expected '$expected', got '$out'"
    FAIL=$((FAIL + 1))
fi

if [[ -f "$CREW_DIR/br_nodes/n001_cli_test.yaml" ]]; then
    echo "PASS: new node yaml created"
    PASS=$((PASS + 1))
else
    echo "FAIL: new node yaml not created"
    FAIL=$((FAIL + 1))
fi

if [[ -f "$CREW_DIR/br_plans/n001_cli_test_plan.md" ]] \
   && grep -q "Patched plan" "$CREW_DIR/br_plans/n001_cli_test_plan.md"; then
    echo "PASS: patched plan written"
    PASS=$((PASS + 1))
else
    echo "FAIL: patched plan missing or empty"
    FAIL=$((FAIL + 1))
fi

if grep -q "current_head: n001_cli_test" "$CREW_DIR/br_graph_state.yaml" \
   && grep -q "next_node_id: 2" "$CREW_DIR/br_graph_state.yaml"; then
    echo "PASS: graph state advanced"
    PASS=$((PASS + 1))
else
    echo "FAIL: graph state not advanced"
    FAIL=$((FAIL + 1))
fi

# Negative: re-running fails because n001_cli_test already exists.
if out=$(./.aitask-scripts/aitask_brainstorm_apply_patcher.sh \
            "$TASK_NUM" "$AGENT" "$SOURCE" 2>&1); then
    echo "FAIL: re-run unexpectedly succeeded: $out"
    FAIL=$((FAIL + 1))
else
    if [[ "$out" == APPLY_FAILED:* && "$out" == *"already exists"* ]]; then
        echo "PASS: idempotent re-run reports 'already exists'"
        PASS=$((PASS + 1))
    else
        echo "FAIL: re-run produced unexpected error: $out"
        FAIL=$((FAIL + 1))
    fi
fi

# Negative: missing source proposal.
rm -rf "$CREW_DIR/br_nodes/n001_cli_test.yaml" \
       "$CREW_DIR/br_proposals/n001_cli_test.md" \
       "$CREW_DIR/br_plans/n001_cli_test_plan.md" \
       "$CREW_DIR/br_proposals/${SOURCE}.md"
# Reset graph state so retry isn't blocked by head change.
cat > "$CREW_DIR/br_graph_state.yaml" <<EOF
current_head: ${SOURCE}
history:
- ${SOURCE}
next_node_id: 1
active_dimensions: []
EOF

if out=$(./.aitask-scripts/aitask_brainstorm_apply_patcher.sh \
            "$TASK_NUM" "$AGENT" "$SOURCE" 2>&1); then
    echo "FAIL: missing-proposal apply unexpectedly succeeded"
    FAIL=$((FAIL + 1))
else
    if [[ "$out" == APPLY_FAILED:* ]]; then
        echo "PASS: missing source proposal → APPLY_FAILED"
        PASS=$((PASS + 1))
    else
        echo "FAIL: missing-proposal output unexpected: $out"
        FAIL=$((FAIL + 1))
    fi
fi

# Argument validation.
if out=$(./.aitask-scripts/aitask_brainstorm_apply_patcher.sh "$TASK_NUM" 2>&1); then
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
