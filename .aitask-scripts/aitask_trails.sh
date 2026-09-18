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

# Catch the orthogonal "venv exists but lacks deps" case (user updated framework
# but did not re-run setup, so venv-Python is right version but missing imports).
missing=()
"$PYTHON" -c "import textual"    2>/dev/null || missing+=(textual)
"$PYTHON" -c "import yaml"       2>/dev/null || missing+=(pyyaml)
"$PYTHON" -c "import linkify_it" 2>/dev/null || missing+=(linkify-it-py)
if [[ ${#missing[@]} -gt 0 ]]; then
    die "Missing Python packages: ${missing[*]}. Run 'ait setup' to install all dependencies."
fi

# Check terminal capabilities (warn on incapable terminals)
ait_warn_if_incapable_terminal

# ONE resolved task directory for everything the app touches. trails_app.py
# never resolves it itself (board contract C2), so it is passed as an argument;
# trail discovery and every artifact / agent subprocess read TASK_DIR from the
# environment, so the same value is exported. The flag goes AFTER "$@" so a
# user-supplied --tasks-dir cannot split the two readers — the app refuses a
# conflicting pair rather than silently letting either win.
export TASK_DIR="${TASK_DIR:-aitasks}"
exec "$PYTHON" "$SCRIPT_DIR/board/trails_app.py" "$@" --tasks-dir "$TASK_DIR"
