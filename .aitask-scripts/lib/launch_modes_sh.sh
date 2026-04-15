#!/usr/bin/env bash
# launch_modes_sh.sh - Shell bridge to lib/launch_modes.py.
#
# Sources cleanly into a caller shell script and exports:
#   LAUNCH_MODES_PIPE   - e.g. "headless|interactive|openshell_headless|openshell_interactive" (sorted)
#   LAUNCH_MODES_REGEX  - e.g. "^(headless|interactive|openshell_headless|openshell_interactive)$"
#
# Both values are derived at runtime by shelling out to
# lib/launch_modes.py, so adding a mode there automatically propagates
# to every shell consumer without any shell-side edit.
#
# Test hook: set AIT_LAUNCH_MODES_DIR=/path to override the Python
# module search path (used by test_launch_modes.py extensibility test).

[[ -n "${_AIT_LAUNCH_MODES_LOADED:-}" ]] && return 0
_AIT_LAUNCH_MODES_LOADED=1

_ait_launch_modes_compute_pipe() {
    local dir="${AIT_LAUNCH_MODES_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
    python3 -c "
import sys
sys.path.insert(0, '$dir')
from launch_modes import launch_modes_pipe
sys.stdout.write(launch_modes_pipe())
"
}

if ! LAUNCH_MODES_PIPE="$(_ait_launch_modes_compute_pipe)"; then
    echo "error: failed to load launch_modes vocabulary from lib/launch_modes.py" >&2
    exit 1
fi
LAUNCH_MODES_REGEX="^(${LAUNCH_MODES_PIPE})$"
# shellcheck disable=SC2034  # exported to caller scripts (LAUNCH_MODES_PIPE, LAUNCH_MODES_REGEX)
readonly LAUNCH_MODES_PIPE LAUNCH_MODES_REGEX
unset -f _ait_launch_modes_compute_pipe
