#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

PYTHON="$(require_ait_python)"

# Catch the "venv exists but lacks deps" case (framework upgraded but setup not re-run).
missing=()
"$PYTHON" -c "import textual" 2>/dev/null || missing+=(textual)
"$PYTHON" -c "import yaml"    2>/dev/null || missing+=(pyyaml)
if [[ ${#missing[@]} -gt 0 ]]; then
    die "Missing Python packages: ${missing[*]}. Run 'ait setup' to install all dependencies."
fi

# Check tmux is available
if ! command -v tmux &>/dev/null; then
    echo "Error: tmux is not installed. The mini monitor TUI requires tmux." >&2
    exit 1
fi

# Check terminal capabilities (warn on incapable terminals)
ait_warn_if_incapable_terminal

# Single-instance guard: skip if another minimonitor/monitor runs in the same window
if [[ -n "${TMUX:-}" ]]; then
    while IFS=: read -r pane_pid pane_cmd; do
        [[ "$pane_pid" == "$$" ]] && continue
        if [[ "$pane_cmd" == *minimonitor* || "$pane_cmd" == *monitor_app* ]]; then
            echo "A monitor is already running in this window. Exiting."
            exit 0
        fi
    done < <(tmux list-panes -F "#{pane_pid}:#{pane_current_command}" 2>/dev/null || true)
fi

exec "$PYTHON" "$SCRIPT_DIR/monitor/minimonitor_app.py" "$@"
