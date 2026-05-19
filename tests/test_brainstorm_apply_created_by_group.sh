#!/usr/bin/env bash
# Regression test for t792: apply paths must force-canonicalize
# created_by_group from the agent name, ignoring whatever the agent
# emitted in its NODE_YAML / METADATA block. Covers both the explorer
# (and synthesizer, shared code path) and patcher apply functions.

set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$THIS_DIR/.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0

# ---------------------------------------------------------------------------
# Case 1: explorer apply ignores agent-emitted created_by_group
# ---------------------------------------------------------------------------
TASK_NUM_EX="999741"
CREW_EX=".aitask-crews/crew-brainstorm-${TASK_NUM_EX}"
AGENT_EX="explorer_001a"
SOURCE_EX="n000_init"

cleanup_explorer() { rm -rf "$CREW_EX"; }

rm -rf "$CREW_EX"
mkdir -p "$CREW_EX/br_nodes" "$CREW_EX/br_proposals" "$CREW_EX/br_plans"

cat > "$CREW_EX/br_nodes/${SOURCE_EX}.yaml" <<'EOF'
node_id: n000_init
parents: []
description: Source node
proposal_file: br_proposals/n000_init.md
created_at: "2026-01-01 00:00"
created_by_group: bootstrap
EOF

cat > "$CREW_EX/br_proposals/${SOURCE_EX}.md" <<'EOF'
<!-- section: overview -->
## Overview
Source proposal body for explorer apply test.
<!-- /section: overview -->
EOF

cat > "$CREW_EX/br_graph_state.yaml" <<EOF
current_head: ${SOURCE_EX}
history:
- ${SOURCE_EX}
next_node_id: 2
active_dimensions: []
EOF

# Explorer output with INTENTIONALLY WRONG created_by_group
# (simulates the t792 drift where one parallel explorer wrote
# "op_explore_001" instead of "explore_001").
cat > "$CREW_EX/${AGENT_EX}_output.md" <<'EOF'
--- NODE_YAML_START ---
node_id: n002_test_explore
parents: [n000_init]
description: Test explorer node
proposal_file: br_proposals/n002_test_explore.md
created_at: "2026-05-18 19:00"
created_by_group: op_explore_001
reference_files: []
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<!-- section: overview -->
## Overview
Explorer-generated proposal body.
<!-- /section: overview -->
--- PROPOSAL_END ---
EOF

# Invoke apply via CLI wrapper.
trap cleanup_explorer EXIT
if out=$(./.aitask-scripts/aitask_brainstorm_apply_explorer.sh \
            "$TASK_NUM_EX" "$AGENT_EX" 2>&1); then
    :
else
    echo "FAIL: explorer apply failed unexpectedly: $out"
    FAIL=$((FAIL + 1))
fi

NEW_NODE_EX="$CREW_EX/br_nodes/n002_test_explore.yaml"
if [[ -f "$NEW_NODE_EX" ]]; then
    actual=$(grep -E '^created_by_group:' "$NEW_NODE_EX" | head -1 | awk '{print $2}')
    if [[ "$actual" == "explore_001" ]]; then
        echo "PASS: explorer apply force-canonicalized created_by_group (op_explore_001 → explore_001)"
        PASS=$((PASS + 1))
    else
        echo "FAIL: explorer apply preserved drifted value (got '$actual', expected 'explore_001')"
        FAIL=$((FAIL + 1))
    fi
else
    echo "FAIL: explorer apply did not produce node file"
    FAIL=$((FAIL + 1))
fi

cleanup_explorer
trap - EXIT

# ---------------------------------------------------------------------------
# Case 2: patcher apply ignores agent-emitted created_by_group
# ---------------------------------------------------------------------------
TASK_NUM_PA="999742"
CREW_PA=".aitask-crews/crew-brainstorm-${TASK_NUM_PA}"
AGENT_PA="patcher_001"
SOURCE_PA="n000_init"

cleanup_patcher() { rm -rf "$CREW_PA"; }

rm -rf "$CREW_PA"
mkdir -p "$CREW_PA/br_nodes" "$CREW_PA/br_proposals" "$CREW_PA/br_plans"

cat > "$CREW_PA/br_nodes/${SOURCE_PA}.yaml" <<'EOF'
node_id: n000_init
parents: []
description: Source node
proposal_file: br_proposals/n000_init.md
created_at: "2026-01-01 00:00"
created_by_group: bootstrap
EOF

cat > "$CREW_PA/br_proposals/${SOURCE_PA}.md" <<'EOF'
## Overview
Source proposal for patcher apply test.
EOF

cat > "$CREW_PA/br_graph_state.yaml" <<EOF
current_head: ${SOURCE_PA}
history:
- ${SOURCE_PA}
next_node_id: 1
active_dimensions: []
EOF

# Patcher output with WRONG created_by_group (faithfully copied
# parent metadata, which had 'bootstrap'). Apply must overwrite
# this with the canonical 'patch_001'.
cat > "$CREW_PA/${AGENT_PA}_output.md" <<'EOF'
--- PATCHED_PLAN_START ---
# Patched plan body
--- PATCHED_PLAN_END ---
--- IMPACT_START ---
**NO_IMPACT**
Justification: trivial test patch.
--- IMPACT_END ---
--- METADATA_START ---
node_id: n001_test_patch
parents: [n000_init]
description: Test patcher node
proposal_file: br_proposals/n000_init.md
created_at: "2026-05-04 12:52"
created_by_group: bootstrap
component_x: bar
--- METADATA_END ---
EOF

trap cleanup_patcher EXIT
if out=$(./.aitask-scripts/aitask_brainstorm_apply_patcher.sh \
            "$TASK_NUM_PA" "$AGENT_PA" "$SOURCE_PA" 2>&1); then
    :
else
    echo "FAIL: patcher apply failed unexpectedly: $out"
    FAIL=$((FAIL + 1))
fi

NEW_NODE_PA="$CREW_PA/br_nodes/n001_test_patch.yaml"
if [[ -f "$NEW_NODE_PA" ]]; then
    actual=$(grep -E '^created_by_group:' "$NEW_NODE_PA" | head -1 | awk '{print $2}')
    if [[ "$actual" == "patch_001" ]]; then
        echo "PASS: patcher apply force-canonicalized created_by_group (bootstrap → patch_001)"
        PASS=$((PASS + 1))
    else
        echo "FAIL: patcher apply preserved drifted value (got '$actual', expected 'patch_001')"
        FAIL=$((FAIL + 1))
    fi
else
    echo "FAIL: patcher apply did not produce node file"
    FAIL=$((FAIL + 1))
fi

cleanup_patcher
trap - EXIT

echo
echo "Total: $((PASS + FAIL))   Passed: $PASS   Failed: $FAIL"
[[ $FAIL -eq 0 ]]
