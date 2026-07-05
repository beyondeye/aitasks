#!/usr/bin/env bash
# test_monitor_rename_window_target.sh - Verify that the monitor's on_mount
# window rename targets monitor's OWN pane (via $TMUX_PANE) rather than tmux's
# ambiguous "current window".
#
# Regression guard for t941 / t1130: an untargeted `tmux rename-window monitor`
# resolves to the attached client's *active* window and — with automatic-rename
# off — permanently mislabels an unrelated window (a board, or an agent-explore
# window) as `monitor`. The fix pins the rename to $TMUX_PANE; when $TMUX_PANE is
# unset/empty the monitor's own window cannot be identified, so `_rename_window_argv`
# returns an EMPTY argv (fail safe: no rename at all) rather than the untargeted
# form. t1130 tightened this: the falsy-pane cases previously fell back to the
# untargeted rename, which is exactly the mislabel this test now forbids.
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
assert_eq "pane None -> no rename (empty argv, fail safe)" \
    "" "$line2"
assert_eq "pane empty -> no rename (empty argv, fail safe)" \
    "" "$line3"

echo
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
