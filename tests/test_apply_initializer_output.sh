#!/usr/bin/env bash
# test_apply_initializer_output.sh - Tests for brainstorm apply_initializer_output
# Run: bash tests/test_apply_initializer_output.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers (inline; match test_claim_id.sh style) ---

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -q "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_file_exists() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected file to exist: $path)"
    fi
}

# --- Shared driver ---

run_py() {
    local tmp_crew="$1" task_fixture_id="$2"
    (
        cd "$PROJECT_DIR"
        python3 - <<EOF_PY
import sys, pathlib
sys.path.insert(0, ".aitask-scripts")
from brainstorm import brainstorm_session as bs
bs.crew_worktree = lambda n: pathlib.Path("$tmp_crew")
bs.apply_initializer_output("$task_fixture_id")
EOF_PY
    )
}

# --- Test 1: happy path — valid fixture writes n000_init files ---

TMP_CREW="$(mktemp -d)"
mkdir -p "$TMP_CREW/br_nodes" "$TMP_CREW/br_proposals"

cat > "$TMP_CREW/initializer_bootstrap_output.md" <<'EOF'
--- NODE_YAML_START ---
node_id: n000_init
parents: []
description: Example imported proposal
proposal_file: br_proposals/n000_init.md
created_at: 2026-04-23 00:00
created_by_group: bootstrap
reference_files:
  - /tmp/imported.md
assumption_latency: low
component_api: REST
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<!-- section: overview -->
## Overview
An imported proposal.
<!-- /section: overview -->
--- PROPOSAL_END ---
EOF

if run_py "$TMP_CREW" "fixture" 2>/tmp/initializer_err; then
    TOTAL=$((TOTAL + 1))
    PASS=$((PASS + 1))
else
    TOTAL=$((TOTAL + 1))
    FAIL=$((FAIL + 1))
    echo "FAIL: happy-path run_py exited non-zero"
    cat /tmp/initializer_err
fi

assert_file_exists "node YAML written" "$TMP_CREW/br_nodes/n000_init.yaml"
assert_file_exists "proposal MD written" "$TMP_CREW/br_proposals/n000_init.md"
proposal_body="$(cat "$TMP_CREW/br_proposals/n000_init.md")"
assert_contains "proposal contains section marker" "section: overview" "$proposal_body"
node_body="$(cat "$TMP_CREW/br_nodes/n000_init.yaml")"
assert_contains "node yaml has node_id" "node_id: n000_init" "$node_body"
assert_contains "node yaml has reference_files" "reference_files" "$node_body"

rm -rf "$TMP_CREW"

# --- Test 2: negative — missing PROPOSAL_END delimiter must raise ValueError ---

TMP_CREW_BAD="$(mktemp -d)"
mkdir -p "$TMP_CREW_BAD/br_nodes" "$TMP_CREW_BAD/br_proposals"

cat > "$TMP_CREW_BAD/initializer_bootstrap_output.md" <<'EOF'
--- NODE_YAML_START ---
node_id: n000_init
parents: []
description: Incomplete proposal
proposal_file: br_proposals/n000_init.md
created_at: 2026-04-23 00:00
created_by_group: bootstrap
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<!-- section: overview -->
## Overview
Truncated before close delimiter.
<!-- /section: overview -->
EOF

TOTAL=$((TOTAL + 1))
if run_py "$TMP_CREW_BAD" "fixture_bad" 2>/tmp/initializer_err; then
    FAIL=$((FAIL + 1))
    echo "FAIL: truncated output should have raised ValueError but run_py exited zero"
else
    err_out="$(cat /tmp/initializer_err)"
    if echo "$err_out" | grep -q "PROPOSAL_START/PROPOSAL_END"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: expected 'PROPOSAL_START/PROPOSAL_END' in error output, got:"
        echo "$err_out"
    fi
fi

# Files must not have been written for the bad fixture
TOTAL=$((TOTAL + 1))
if [[ ! -f "$TMP_CREW_BAD/br_nodes/n000_init.yaml" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: node YAML written despite malformed output"
fi

rm -rf "$TMP_CREW_BAD"
rm -f /tmp/initializer_err

# --- Summary ---

echo "---"
echo "PASS: $PASS / $TOTAL"
if [[ $FAIL -gt 0 ]]; then
    echo "FAIL: $FAIL"
    exit 1
fi
echo "PASS: apply_initializer_output"
