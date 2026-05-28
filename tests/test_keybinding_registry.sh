#!/usr/bin/env bash
# test_keybinding_registry.sh — Coverage for lib/keybinding_registry.py and
# lib/shortcut_persist.py (the t848_1 shortcut-customisation foundation).
#
# Run: bash tests/test_keybinding_registry.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/venv_python.sh
source "$SCRIPT_DIR/lib/venv_python.sh"

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
        echo "FAIL: $desc"
        echo "  expected: $expected"
        echo "  actual:   $actual"
    fi
}

assert_contains() {
    local desc="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if grep -qE -- "$needle" <<< "$haystack"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  expected match (regex): $needle"
        echo "  actual: $haystack"
    fi
}

# --- Setup --------------------------------------------------------------

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

LIB_DIR="$PROJECT_DIR/.aitask-scripts/lib"

# Each test runs in a fresh subdirectory with its own aitasks/metadata/
# tree, so userconfig.yaml writes don't pollute the real repo or each
# other. We also pass an explicit PYTHONPATH so the modules import as
# top-level (matching the runtime layout in board/aitask_board.py).

run_py() {
    # Args: <subdir> <python_code>
    local subdir="$1"
    local code="$2"
    local work="$TMPROOT/$subdir"
    mkdir -p "$work/aitasks/metadata"
    (
        cd "$work"
        PYTHONPATH="$LIB_DIR" "$AITASK_PYTHON" -c "$code"
    )
}

write_userconfig() {
    # Args: <subdir> <yaml_body>
    local subdir="$1"
    local body="$2"
    local work="$TMPROOT/$subdir"
    mkdir -p "$work/aitasks/metadata"
    printf '%s\n' "$body" > "$work/aitasks/metadata/userconfig.yaml"
}

# --- Case 1: empty overrides — register returns binding unchanged ------

OUT=$(run_py "case1" '
import keybinding_registry as kr
from textual.binding import Binding
kr._reset_for_tests()
b = Binding("p", "pick_task", "Pick")
result = kr.register_app_bindings("board", [b])
assert len(result) == 1, result
assert result[0].key == "p", result[0]
assert result[0].action == "pick_task"
assert ("board", "pick_task") in kr._DEFAULTS
print("OK")
')
assert_eq "case1: empty overrides return unchanged" "OK" "$OUT"

# --- Case 2: override present — returned binding has overridden key ----

write_userconfig "case2" 'shortcuts:
  board:
    pick_task: o'
OUT=$(run_py "case2" '
import keybinding_registry as kr
from textual.binding import Binding
kr._reset_for_tests()
b = Binding("p", "pick_task", "Pick")
result = kr.register_app_bindings("board", [b])
assert result[0].key == "o", result[0]
assert result[0].action == "pick_task"
assert result[0].description == "Pick"
print("OK")
')
assert_eq "case2: override applied at registration time" "OK" "$OUT"

# --- Case 3: coherence_lint flags divergent quit binding ---------------

OUT=$(run_py "case3" '
import keybinding_registry as kr
from textual.binding import Binding
kr._reset_for_tests()
kr.register_app_bindings("scopeA", [Binding("q", "quit", "Quit")])
kr.register_app_bindings("scopeB", [Binding("x", "quit", "Quit")])
warnings = kr.coherence_lint()
assert len(warnings) == 1, warnings
print(warnings[0])
')
assert_contains "case3: lint reports divergent quit binding" "quit.*q.*x" "$OUT"

# --- Case 4: coherence_lint silent when shared action agrees -----------

OUT=$(run_py "case4" '
import keybinding_registry as kr
from textual.binding import Binding
kr._reset_for_tests()
kr.register_app_bindings("scopeA", [Binding("j", "tui_switcher", "Switch")])
kr.register_app_bindings("scopeB", [Binding("j", "tui_switcher", "Switch")])
warnings = kr.coherence_lint()
print("LEN=" + str(len(warnings)))
')
assert_eq "case4: no warning when shared key matches" "LEN=0" "$OUT"

# --- Case 5: save_override round-trip preserves sibling top-level keys -

write_userconfig "case5" 'email: someone@example.test
last_used_labels: [ui]'
OUT=$(run_py "case5" '
import keybinding_registry as kr
import shortcut_persist as sp
import yaml
kr._reset_for_tests()
sp.save_override("board", "pick_task", "o")
overrides = kr.load_user_overrides()
assert overrides == {"board": {"pick_task": "o"}}, overrides
# Sibling keys survive
with open("aitasks/metadata/userconfig.yaml", "r", encoding="utf-8") as f:
    data = yaml.safe_load(f)
assert data.get("email") == "someone@example.test", data
assert data.get("last_used_labels") == ["ui"], data
print("OK")
')
assert_eq "case5: round-trip preserves email + last_used_labels" "OK" "$OUT"

# --- Case 6: reset_scope removes a scope subtree, others intact --------

write_userconfig "case6" 'email: someone@example.test
shortcuts:
  board:
    pick_task: o
  monitor:
    refresh: x'
OUT=$(run_py "case6" '
import keybinding_registry as kr
import shortcut_persist as sp
import yaml
kr._reset_for_tests()
sp.reset_scope("board")
with open("aitasks/metadata/userconfig.yaml", "r", encoding="utf-8") as f:
    data = yaml.safe_load(f)
assert "board" not in data.get("shortcuts", {}), data
assert data["shortcuts"]["monitor"] == {"refresh": "x"}, data
assert data["email"] == "someone@example.test", data
print("OK")
')
assert_eq "case6: reset_scope removes board, monitor intact" "OK" "$OUT"

# --- Summary -----------------------------------------------------------

echo
echo "PASSED: $PASS / $TOTAL"
if [[ $FAIL -gt 0 ]]; then
    echo "FAILED: $FAIL"
    exit 1
fi
