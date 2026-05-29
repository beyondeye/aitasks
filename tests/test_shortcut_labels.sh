#!/usr/bin/env bash
# test_shortcut_labels.sh — Golden-file coverage for lib/shortcut_labels.py.
#
# Each case renders one (text, key, style) tuple via render_label and diffs
# the result against a committed golden file under
# tests/test_shortcut_labels_golden/. New cases require both a python case
# entry below AND a matching golden file in that directory.
#
# Run: bash tests/test_shortcut_labels.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GOLDEN_DIR="$SCRIPT_DIR/test_shortcut_labels_golden"
LIB_DIR="$PROJECT_DIR/.aitask-scripts/lib"

# shellcheck source=lib/venv_python.sh
source "$SCRIPT_DIR/lib/venv_python.sh"

PASS=0
FAIL=0
TOTAL=0

# Case format: <golden_name>|<style>|<text>|<key>
# Empty key is encoded as <KEY_EMPTY> so the field separator stays usable.
CASES=(
    "wrap_pick_p|wrap|Pick|p"
    "wrap_pick_uppercase_P|wrap|Pick|P"
    "wrap_pick_o|wrap|Pick|o"
    "wrap_new_task_zero|wrap|New Task|0"
    "wrap_toggle_children_x|wrap|Toggle Children|x"
    "wrap_edit_i|wrap|Edit|i"
    "wrap_move_right_ctrl_r|wrap|Move Right|ctrl+r"
    "wrap_empty_key|wrap|Foo|<KEY_EMPTY>"
    "lead_locked_l|leading|Locked|l"
    "lead_locked_uppercase_L|leading|Locked|L"
    "lead_locked_o|leading|Locked|o"
    "lead_all_a|leading|All|a"
    "lead_move_right_ctrl_r|leading|Move Right|ctrl+r"
    "lead_empty_key|leading|Foo|<KEY_EMPTY>"
)

run_case() {
    local name="$1" style="$2" text="$3" key="$4"
    if [[ "$key" == "<KEY_EMPTY>" ]]; then
        key=""
    fi
    PYTHONPATH="$LIB_DIR" "$AITASK_PYTHON" -c "
import sys
from shortcut_labels import render_label
print(render_label(sys.argv[1], sys.argv[2], style=sys.argv[3]), end='')
" "$text" "$key" "$style"
}

for entry in "${CASES[@]}"; do
    IFS='|' read -r name style text key <<<"$entry"
    TOTAL=$((TOTAL + 1))
    actual=$(run_case "$name" "$style" "$text" "$key")
    golden_file="$GOLDEN_DIR/${name}.txt"
    if [[ ! -f "$golden_file" ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $name — golden file missing: $golden_file"
        continue
    fi
    expected=$(cat "$golden_file")
    if [[ "$actual" == "$expected" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $name"
        echo "  expected: $expected"
        echo "  actual:   $actual"
    fi
done

echo
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ $FAIL -eq 0 ]] || exit 1
