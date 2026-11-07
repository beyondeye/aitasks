#!/usr/bin/env bash
# aitask_sitrep_tui.sh - Launcher for the sitrep TUI (`ait sitrep tui`, t2211_1).
#
#   ait sitrep tui [--root <path>]
#
# Shows the repository's sitrep store read-only: grouped items, details with
# the context map, read-only pointer following and the Q&A log. `--root` is
# checked by the app's parser (`sitrep_cli.root_arg`: empty or a `..` segment
# exits 2); an unresolvable root prints ROOT_FAILED:<why> and exits 1.
#
# The shape of `aitask_frozenagent.sh`: resolve the framework python, catch the
# "venv exists but lacks deps" case, warn on an incapable terminal, then exec.
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

exec "$PYTHON" "$SCRIPT_DIR/sitrep_tui/sitrep_tui_app.py" "$@"
