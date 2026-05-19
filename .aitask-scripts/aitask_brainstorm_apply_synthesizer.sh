#!/usr/bin/env bash
# aitask_brainstorm_apply_synthesizer.sh - Re-run apply on a brainstorm synthesizer.
#
# Usage: ait brainstorm apply-synthesizer <task_num> <agent_name>
#
# Re-parses <agent_name>_output.md and creates a new hybrid node parented on
# every source node listed in the synthesizer's NODE_YAML. Useful when the
# TUI's auto-apply didn't run (or didn't get a chance).
#
# Output:
#   APPLIED:<new_node_id>    Apply succeeded
#   APPLY_FAILED:<error>     Apply failed (stderr; see also
#                            <agent_name>_apply_error.log in the crew worktree)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

PYTHON="$(require_ait_python)"
if ! "$PYTHON" -c "import yaml" 2>/dev/null; then
    die "Missing Python package: pyyaml. Run 'ait setup' or: pip install pyyaml"
fi

if [[ $# -ne 2 ]]; then
    echo "Usage: ait brainstorm apply-synthesizer <task_num> <agent_name>" >&2
    exit 2
fi

NUM="$1"
AGENT="$2"

cd "$SCRIPT_DIR/.."
exec "$PYTHON" - "$NUM" "$AGENT" <<'PY'
import sys
sys.path.insert(0, '.aitask-scripts')
from brainstorm.brainstorm_session import apply_synthesizer_output

num, agent = sys.argv[1], sys.argv[2]
try:
    new_id = apply_synthesizer_output(num, agent)
    print(f'APPLIED:{new_id}')
except Exception as exc:
    print(f'APPLY_FAILED:{exc}', file=sys.stderr)
    sys.exit(1)
PY
