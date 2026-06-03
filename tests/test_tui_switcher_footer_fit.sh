#!/usr/bin/env bash
# test_tui_switcher_footer_fit.sh — Regression for t789: ensure the TUI
# switcher overlay's footer hint stays visible in small panes.
#
# Covers:
#   * CSS contract: dock:bottom on #switcher_hint, 1fr on #switcher_list,
#     height:100% + max-height:30 on #switcher_dialog.
#   * Single-session: _render_session_row hides the empty row (display=False)
#     so its padding does not consume a footer row.
#   * Multi-session: _render_session_row shows the row (display=True) and
#     paints both session names.
#
# Run: bash tests/test_tui_switcher_footer_fit.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Shared assertion helpers (see tests/lib/asserts.sh).
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
LIB_DIR="$PROJECT_DIR/.aitask-scripts/lib"

# shellcheck source=lib/venv_python.sh
. "$SCRIPT_DIR/lib/venv_python.sh"

# Logic-only test: no tmux, no Textual runtime. Safe to run from anywhere.

PASS=0
FAIL=0
TOTAL=0

out=$(PYTHONPATH="$LIB_DIR" "$AITASK_PYTHON" <<'PY'
from pathlib import Path
from unittest.mock import MagicMock

import tui_switcher as ts
from agent_launch_utils import AitasksSession


# --- CSS contract ---

css = ts.TuiSwitcherOverlay.DEFAULT_CSS


def _block(selector: str) -> str:
    """Return the CSS body for a single selector (between '{' and '}')."""
    idx = css.find(selector)
    if idx == -1:
        return ""
    brace_open = css.find("{", idx)
    brace_close = css.find("}", brace_open)
    return css[brace_open + 1:brace_close]


hint_block = _block("#switcher_hint")
list_block = _block("#switcher_list")
dialog_block = _block("#switcher_dialog")

print("HINT_DOCK_BOTTOM:" + str("dock: bottom" in hint_block))
print("LIST_HEIGHT_FR:" + str("height: 1fr" in list_block))
print("LIST_MIN_HEIGHT:" + str("min-height: 3" in list_block))
print("DIALOG_HEIGHT_100:" + str("height: 100%" in dialog_block))
print("DIALOG_MAX_HEIGHT_30:" + str("max-height: 30" in dialog_block))


# --- _render_session_row: single-session hides the row ---

ov = ts.TuiSwitcherOverlay(session="s1")
ov._init_multi_state([AitasksSession("s1", Path("/p1"), "p1")])

row_mock = MagicMock()
ov.query_one = MagicMock(return_value=row_mock)
ov._render_session_row()
print("SINGLE_ROW_UPDATE_CALL:" + str(row_mock.update.call_args.args[0]))
print("SINGLE_ROW_DISPLAY:" + str(row_mock.display))


# --- _render_session_row: multi-session shows the row with both names ---

ov = ts.TuiSwitcherOverlay(session="s1")
ov._init_multi_state([
    AitasksSession("s1", Path("/p1"), "p1"),
    AitasksSession("s2", Path("/p2"), "p2"),
])

row_mock = MagicMock()
ov.query_one = MagicMock(return_value=row_mock)
ov._render_session_row()
print("MULTI_ROW_DISPLAY:" + str(row_mock.display))
last_update_text = row_mock.update.call_args.args[0]
print("MULTI_ROW_TEXT_HAS_S1:" + str("s1" in last_update_text))
print("MULTI_ROW_TEXT_HAS_S2:" + str("s2" in last_update_text))
PY
)

# Parse output
while IFS=':' read -r key val; do
    case "$key" in
        HINT_DOCK_BOTTOM)        HINT_DOCK_BOTTOM="$val" ;;
        LIST_HEIGHT_FR)          LIST_HEIGHT_FR="$val" ;;
        LIST_MIN_HEIGHT)         LIST_MIN_HEIGHT="$val" ;;
        DIALOG_HEIGHT_100)       DIALOG_HEIGHT_100="$val" ;;
        DIALOG_MAX_HEIGHT_30)    DIALOG_MAX_HEIGHT_30="$val" ;;
        SINGLE_ROW_UPDATE_CALL)  SINGLE_ROW_UPDATE_CALL="$val" ;;
        SINGLE_ROW_DISPLAY)      SINGLE_ROW_DISPLAY="$val" ;;
        MULTI_ROW_DISPLAY)       MULTI_ROW_DISPLAY="$val" ;;
        MULTI_ROW_TEXT_HAS_S1)   MULTI_ROW_TEXT_HAS_S1="$val" ;;
        MULTI_ROW_TEXT_HAS_S2)   MULTI_ROW_TEXT_HAS_S2="$val" ;;
    esac
done <<< "$out"

assert_eq "hint has dock:bottom"            "True" "$HINT_DOCK_BOTTOM"
assert_eq "list has height:1fr"             "True" "$LIST_HEIGHT_FR"
assert_eq "list has min-height:3"           "True" "$LIST_MIN_HEIGHT"
assert_eq "dialog has height:100%"          "True" "$DIALOG_HEIGHT_100"
assert_eq "dialog keeps max-height:30"      "True" "$DIALOG_MAX_HEIGHT_30"

assert_eq "single-session row.update('')"   ""     "$SINGLE_ROW_UPDATE_CALL"
assert_eq "single-session row hidden"       "False" "$SINGLE_ROW_DISPLAY"

assert_eq "multi-session row visible"       "True" "$MULTI_ROW_DISPLAY"
assert_eq "multi-session text has s1"       "True" "$MULTI_ROW_TEXT_HAS_S1"
assert_eq "multi-session text has s2"       "True" "$MULTI_ROW_TEXT_HAS_S2"

echo
echo "Results: $PASS/$TOTAL passed"
if [[ $FAIL -gt 0 ]]; then
    echo "FAILED: $FAIL"
    exit 1
fi
echo "PASS"
