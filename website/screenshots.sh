#!/usr/bin/env bash
# screenshots.sh - docs screenshot tool (repo-only, never shipped).
#
# Primitives for an agent that drives a real TUI in an isolated tmux session on
# a sample project and captures it as SVG. See `website/screenshots/cli.py` for
# the verbs and `aiplans/p2278_docs_tui_screenshot_generator.md` for the design.
#
# The tool needs Rich and PyYAML, which the framework venv has, so it resolves
# its interpreter the way the framework's own launchers do.
set -euo pipefail

WEBSITE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$WEBSITE_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$REPO_ROOT/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

missing=()
"$PYTHON" -c "import rich" 2>/dev/null || missing+=(rich)
"$PYTHON" -c "import yaml" 2>/dev/null || missing+=(pyyaml)
if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Missing Python packages: ${missing[*]}. Run 'ait setup' to install all dependencies." >&2
    exit 1
fi

# The TUIs in the pane run under a scratch HOME, so they cannot find the
# framework venv by themselves: hand them this interpreter.
export AIT_PYTHON="$PYTHON"

exec "$PYTHON" "$WEBSITE_DIR/screenshots/cli.py" "$@"
