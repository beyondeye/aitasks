#!/usr/bin/env bash
# test_apply_initializer_tolerant.sh - Tests for _tolerant_yaml_load + error log
# Run: bash tests/test_apply_initializer_tolerant.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/venv_python.sh
. "$SCRIPT_DIR/lib/venv_python.sh"

PASS=0
FAIL=0
TOTAL=0

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

assert_file_missing() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ ! -f "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected file to be absent: $path)"
    fi
}

run_apply() {
    local tmp_crew="$1"
    (
        cd "$PROJECT_DIR"
        "$AITASK_PYTHON" - <<EOF_PY
import sys, pathlib
sys.path.insert(0, ".aitask-scripts")
from brainstorm import brainstorm_session as bs
bs.crew_worktree = lambda n: pathlib.Path("$tmp_crew")
bs.apply_initializer_output("fixture")
EOF_PY
    )
}

# --- Test 1: em-dash YAML loads via tolerant fallback ---

TMP1="$(mktemp -d "${TMPDIR:-/tmp}/aitask_test_apply_XXXXXX")"
mkdir -p "$TMP1/br_nodes" "$TMP1/br_proposals"

cat > "$TMP1/initializer_bootstrap_output.md" <<'EOF'
--- NODE_YAML_START ---
node_id: n000_init
parents: []
description: aitasks/metadata/gates.yaml — per-gate config: verifier skill name
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

if run_apply "$TMP1" 2>/tmp/tolerant_err1; then
    TOTAL=$((TOTAL + 1))
    PASS=$((PASS + 1))
else
    TOTAL=$((TOTAL + 1))
    FAIL=$((FAIL + 1))
    echo "FAIL: em-dash fixture should have parsed via tolerant fallback"
    cat /tmp/tolerant_err1
fi

assert_file_exists "test1: node yaml written" "$TMP1/br_nodes/n000_init.yaml"
assert_file_exists "test1: proposal md written" "$TMP1/br_proposals/n000_init.md"
assert_file_missing "test1: no error log on tolerant success" "$TMP1/initializer_bootstrap_apply_error.log"
node_body="$(cat "$TMP1/br_nodes/n000_init.yaml")"
assert_contains "test1: node yaml preserves the description text" "per-gate config" "$node_body"

rm -rf "$TMP1"

# --- Test 2: truly malformed YAML fails AND writes error log ---

TMP2="$(mktemp -d "${TMPDIR:-/tmp}/aitask_test_apply_XXXXXX")"
mkdir -p "$TMP2/br_nodes" "$TMP2/br_proposals"

cat > "$TMP2/initializer_bootstrap_output.md" <<'EOF'
--- NODE_YAML_START ---
node_id: n000_init
parents: [unbalanced
description: Broken YAML (unbalanced flow list)
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<!-- section: overview -->
## Overview
Body.
<!-- /section: overview -->
--- PROPOSAL_END ---
EOF

TOTAL=$((TOTAL + 1))
if run_apply "$TMP2" 2>/tmp/tolerant_err2; then
    FAIL=$((FAIL + 1))
    echo "FAIL: malformed YAML should have raised but run_apply exited zero"
else
    PASS=$((PASS + 1))
fi

assert_file_exists "test2: error log written on permanent failure" "$TMP2/initializer_bootstrap_apply_error.log"
err_log_body="$(cat "$TMP2/initializer_bootstrap_apply_error.log" 2>/dev/null || true)"
assert_contains "test2: error log mentions apply failure" "apply_initializer_output failed" "$err_log_body"
assert_contains "test2: error log embeds parse error" "Original YAML parse error" "$err_log_body"
assert_contains "test2: error log embeds NODE_YAML excerpt" "NODE_YAML block" "$err_log_body"
assert_file_missing "test2: node yaml NOT written on failure" "$TMP2/br_nodes/n000_init.yaml"

rm -rf "$TMP2"

# --- Test 3: well-formed YAML loads normally without error log ---

TMP3="$(mktemp -d "${TMPDIR:-/tmp}/aitask_test_apply_XXXXXX")"
mkdir -p "$TMP3/br_nodes" "$TMP3/br_proposals"

cat > "$TMP3/initializer_bootstrap_output.md" <<'EOF'
--- NODE_YAML_START ---
node_id: n000_init
parents: []
description: Already-quoted clean fixture
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
Clean.
<!-- /section: overview -->
--- PROPOSAL_END ---
EOF

if run_apply "$TMP3" 2>/tmp/tolerant_err3; then
    TOTAL=$((TOTAL + 1))
    PASS=$((PASS + 1))
else
    TOTAL=$((TOTAL + 1))
    FAIL=$((FAIL + 1))
    echo "FAIL: clean fixture should parse on the first try"
    cat /tmp/tolerant_err3
fi

assert_file_exists "test3: node yaml written" "$TMP3/br_nodes/n000_init.yaml"
assert_file_missing "test3: no error log on clean parse" "$TMP3/initializer_bootstrap_apply_error.log"

rm -rf "$TMP3"
rm -f /tmp/tolerant_err1 /tmp/tolerant_err2 /tmp/tolerant_err3

# --- Test 4: _tolerant_yaml_load unit tests (direct call, no apply) ---

(
    cd "$PROJECT_DIR"
    "$AITASK_PYTHON" - <<'EOF_PY'
import sys
sys.path.insert(0, ".aitask-scripts")
from brainstorm.brainstorm_session import _tolerant_yaml_load

# Em-dash + second colon — must auto-quote and parse
text = "key: aitasks/metadata/gates.yaml — per-gate config: verifier skill\n"
got = _tolerant_yaml_load(text)
assert isinstance(got, dict), f"expected dict, got {type(got)}"
assert "per-gate config" in got["key"], f"unexpected value: {got!r}"

# Already-quoted value containing em-dash — must parse without modification
text2 = 'key: "aitasks/metadata/gates.yaml — per-gate config: verifier"\n'
got2 = _tolerant_yaml_load(text2)
assert got2["key"] == "aitasks/metadata/gates.yaml — per-gate config: verifier"

# Flow list — must NOT be quoted
text3 = "key: [a, b, c]\n"
got3 = _tolerant_yaml_load(text3)
assert got3["key"] == ["a", "b", "c"], f"flow list got mangled: {got3!r}"

# Truly malformed — must raise YAMLError
import yaml
try:
    _tolerant_yaml_load("key: [unbalanced\n")
except yaml.YAMLError:
    pass
else:
    raise AssertionError("expected YAMLError for unbalanced flow list")

print("PY_OK")
EOF_PY
) > /tmp/tolerant_unit.out 2>&1

if grep -q "PY_OK" /tmp/tolerant_unit.out; then
    TOTAL=$((TOTAL + 1)); PASS=$((PASS + 1))
else
    TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
    echo "FAIL: _tolerant_yaml_load unit assertions"
    cat /tmp/tolerant_unit.out
fi
rm -f /tmp/tolerant_unit.out

# --- Summary ---

echo "---"
echo "PASS: $PASS / $TOTAL"
if [[ $FAIL -gt 0 ]]; then
    echo "FAIL: $FAIL"
    exit 1
fi
echo "PASS: apply_initializer_tolerant"
