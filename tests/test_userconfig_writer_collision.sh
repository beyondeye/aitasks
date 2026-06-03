#!/usr/bin/env bash
# test_userconfig_writer_collision.sh — Regression test for the userconfig.yaml
# writer-style collision (t864).
#
# aitasks/metadata/userconfig.yaml has two writers with different YAML styles:
#   * Python shortcut_persist / userconfig_persist — round-trips the whole file
#     with yaml.safe_dump(default_flow_style=False), which renders a list value
#     in BLOCK style ("last_used_labels:\n- item").
#   * bash set_last_used_labels — historically sed-replaced ONLY the
#     "last_used_labels:" header line, orphaning any block continuation lines
#     ("- item") below it into invalid YAML. A corrupt file then crashes every
#     TUI at import (keybinding_registry.load_user_overrides reads it).
#
# This test reproduces the collision and asserts the bash writer can no longer
# corrupt the file, regardless of whether the value is on disk in flow or block
# style. It FAILS against the pre-fix code (Case 1 leaves invalid YAML) and
# PASSES after the fix.
#
# Run: bash tests/test_userconfig_writer_collision.sh

set -e

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"

# shellcheck source=lib/venv_python.sh
source "$TEST_DIR/lib/venv_python.sh"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

# assert_yaml_valid <desc> <file>
assert_yaml_valid() {
    local desc="$1" file="$2"
    TOTAL=$((TOTAL + 1))
    if "$AITASK_PYTHON" -c 'import sys, yaml; yaml.safe_load(open(sys.argv[1]))' "$file" 2>/dev/null; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc — file is not valid YAML:"
        echo "----- $file -----"
        cat "$file"
        echo "-----------------"
    fi
}

# Write userconfig.yaml exactly as the Python writer would: a whole-file
# yaml.safe_dump(default_flow_style=False, sort_keys=False), which renders
# last_used_labels in BLOCK style. This mirrors
# userconfig_persist._atomic_dump / shortcut_persist._atomic_dump byte-for-byte
# (a realistic on-disk "shortcut-save then label-write" starting point).
py_write_blockstyle() {
    "$AITASK_PYTHON" - "$1" <<'PY'
import sys, yaml
path = sys.argv[1]
data = {
    "email": "x@example.com",
    "last_used_labels": ["agentcrew"],
    "shortcuts": {"board": {"pick": "p"}},
}
with open(path, "w", encoding="utf-8") as f:
    f.write("# Local user configuration (gitignored, not shared)\n")
    yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
PY
}

# --- Setup: temp TASK_DIR so the helpers target an isolated userconfig.yaml ---

TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT

TASK_DIR="$TMPROOT/aitasks"
mkdir -p "$TASK_DIR/metadata"
export TASK_DIR

# task_utils.sh uses SCRIPT_DIR to locate sibling libs; unset any inherited
# value so it computes the right path relative to the sourced file.
unset SCRIPT_DIR || true

# shellcheck source=../.aitask-scripts/lib/task_utils.sh
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"

CONFIG="$TASK_DIR/metadata/userconfig.yaml"

# --- Case 1: Python-then-bash end-to-end ---
# Python writes block style + a shortcuts block, then a bash set_last_used_labels
# (as `ait create` does) must leave the file valid and round-tripping.
py_write_blockstyle "$CONFIG"
assert_contains "precondition: block-style list on disk" "- agentcrew" "$(cat "$CONFIG")"
set_last_used_labels "codexcli"
assert_yaml_valid "valid YAML after Python-then-bash" "$CONFIG"
assert_eq "labels round-trip after Python-then-bash" "codexcli" "$(get_last_used_labels)"
assert_contains "shortcuts block preserved" "pick: p" "$(cat "$CONFIG")"
assert_contains "email preserved" "email: x@example.com" "$(cat "$CONFIG")"
assert_not_contains "orphaned block item removed" "- agentcrew" "$(cat "$CONFIG")"

# --- Case 2: block-then-bash, minimal (no shortcuts) ---
cat > "$CONFIG" <<'EOF'
# Local user configuration (gitignored, not shared)
email: foo@bar.test
last_used_labels:
- one
- two
EOF
set_last_used_labels "three"
assert_yaml_valid "valid YAML after block-then-bash" "$CONFIG"
assert_eq "block value replaced, reads back" "three" "$(get_last_used_labels)"
assert_not_contains "old block item one removed" "- one" "$(cat "$CONFIG")"
assert_not_contains "old block item two removed" "- two" "$(cat "$CONFIG")"
assert_contains "email still present" "email: foo@bar.test" "$(cat "$CONFIG")"

# --- Case 3: get reads BLOCK style ---
cat > "$CONFIG" <<'EOF'
# Local user configuration (gitignored, not shared)
last_used_labels:
- alpha
- beta
EOF
assert_eq "get reads block style" "alpha,beta" "$(get_last_used_labels)"

# --- Case 4: get reads FLOW style ---
cat > "$CONFIG" <<'EOF'
# Local user configuration (gitignored, not shared)
last_used_labels: [gamma, delta]
EOF
assert_eq "get reads flow style" "gamma,delta" "$(get_last_used_labels)"

echo ""
if [[ $FAIL -eq 0 ]]; then
    echo "PASS: $PASS/$TOTAL tests passed"
    exit 0
else
    echo "FAIL: $FAIL/$TOTAL tests failed ($PASS passed)"
    exit 1
fi
