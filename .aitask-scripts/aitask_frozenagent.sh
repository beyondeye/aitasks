#!/usr/bin/env bash
# aitask_frozenagent.sh - Launcher for the frozen-agent viewer TUI (t1705_6).
#
# This is the command the freeze engine respawns a frozen agent's pane into
# (`lib/agent_sessions.standin_command`), so it must start fast and must not
# stall on anything optional — `ait` skips the update check for this verb for
# exactly that reason.
#
# A verbatim clone of `aitask_diffviewer.sh`'s shape: resolve the framework
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

exec "$PYTHON" "$SCRIPT_DIR/frozenagent/frozenagent_app.py" "$@"
