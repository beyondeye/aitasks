#!/usr/bin/env bash
# aitask_scratchpad.sh - Launcher for the scratchpad notes editor TUI (t2073_2).
#
# The minimonitor spawns this in a pane beside a code agent, so it must start
# fast and must not stall on anything optional — `ait` skips the update check
# for this verb for exactly that reason.
#
# A verbatim clone of `aitask_frozenagent.sh`'s shape: resolve the framework
# python, catch the "venv exists but lacks deps" case, warn on an incapable
# terminal, then exec.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

PYTHON="$(require_ait_python)"

# Catch the "venv exists but lacks deps" case.
missing=()
"$PYTHON" -c "import textual" 2>/dev/null || missing+=(textual)
"$PYTHON" -c "import yaml"    2>/dev/null || missing+=(pyyaml)
if [[ ${#missing[@]} -gt 0 ]]; then
    die "Missing Python packages: ${missing[*]}. Run 'ait setup' to install all dependencies."
fi

# Check terminal capabilities (warn on incapable terminals)
ait_warn_if_incapable_terminal

exec "$PYTHON" "$SCRIPT_DIR/scratchpad/scratchpad_app.py" "$@"
