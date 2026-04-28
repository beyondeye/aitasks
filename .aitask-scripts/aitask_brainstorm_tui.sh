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

# Catch the "venv exists but lacks deps" case.
missing=()
"$PYTHON" -c "import textual" 2>/dev/null || missing+=(textual)
"$PYTHON" -c "import yaml"    2>/dev/null || missing+=(pyyaml)
if [[ ${#missing[@]} -gt 0 ]]; then
    die "Missing Python packages: ${missing[*]}. Run 'ait setup' to install all dependencies."
fi

# Check terminal capabilities (warn on incapable terminals)
ait_warn_if_incapable_terminal

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: ait brainstorm <task_num>"
    echo ""
    echo "Launch the brainstorm TUI for interactive design exploration."
    exit 0
fi

exec "$PYTHON" "$SCRIPT_DIR/brainstorm/brainstorm_app.py" "$@"
