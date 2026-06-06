#!/usr/bin/env bash
# test_monitor_rename_window_target.sh - Verify that the monitor's on_mount
# window rename targets monitor's OWN pane (via $TMUX_PANE) rather than tmux's
# ambiguous "current window".
#
# Regression guard for t941: an untargeted `tmux rename-window monitor` resolved
# to the attached client's *active* window and — with automatic-rename off —
# permanently mislabeled an unrelated window (a board) as `monitor`. The fix
# pins the rename to $TMUX_PANE, falling back to the untargeted form only when
# the env var is unset.
#
# Pure-function test: monitor_app._rename_window_argv builds the argv with no
# tmux/Textual side effects, so this runs without a live tmux server.
#
# Run: bash tests/test_monitor_rename_window_target.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

# monitor_app.py self-bootstraps its own sys.path (lib/, board/, monitor pkg),
# so loading it by file path is sufficient. Importing executes module-level
# Textual imports — present in this repo's test env (other tests import
# monitor/board modules).
out=$(python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location(
    'monitor_app', '$PROJECT_DIR/.aitask-scripts/monitor/monitor_app.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print(' '.join(m._rename_window_argv('%7')))
print(' '.join(m._rename_window_argv(None)))
print(' '.join(m._rename_window_argv('')))
")

# bash-3.2-safe line extraction (no mapfile).
line1=$(printf '%s\n' "$out" | sed -n '1p')
line2=$(printf '%s\n' "$out" | sed -n '2p')
line3=$(printf '%s\n' "$out" | sed -n '3p')

assert_eq "pane set -> rename targets that pane" \
    "tmux rename-window -t %7 monitor" "$line1"
assert_eq "pane None -> untargeted fallback" \
    "tmux rename-window monitor" "$line2"
assert_eq "pane empty -> treated as unset (fallback)" \
    "tmux rename-window monitor" "$line3"

echo
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
