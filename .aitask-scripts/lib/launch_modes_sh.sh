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
    # Interpreter order (t2339): the cached resolution, then an executable
    # $AIT_PYTHON, then lib/python_resolve.sh (venv → wrapper → PATH python3),
    # then bare python3 from PATH. An explicit AIT_PYTHON is honoured even when
    # the PATH python3 is the ~/.aitask/bin wrapper of another HOME.
    # python_resolve.sh is sourced lazily and only when HOME is set: every
    # candidate it adds beyond AIT_PYTHON lives under HOME, and its PATH
    # python3 fallback is the one this bridge keeps below. (python_resolve.sh
    # itself tolerates an unset HOME under `set -u` since t2347.) A
    # bridge copied on its own into a test scaffold (no python_resolve.sh
    # beside it) keeps the plain python3 fallback exactly as before.
    local pycmd="${_AIT_RESOLVED_PYTHON:-}"
    if [[ -z "$pycmd" && -n "${AIT_PYTHON:-}" && -x "${AIT_PYTHON:-}" ]]; then
        pycmd="$AIT_PYTHON"
    fi
    if [[ -z "$pycmd" && -n "${HOME:-}" ]]; then
        local _lib_dir
        _lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        if [[ -r "$_lib_dir/python_resolve.sh" ]]; then
            # shellcheck source=lib/python_resolve.sh
            source "$_lib_dir/python_resolve.sh"
            resolve_python >/dev/null
            pycmd="${_AIT_RESOLVED_PYTHON:-}"
        fi
    fi
    pycmd="${pycmd:-python3}"
    "$pycmd" -c "
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
