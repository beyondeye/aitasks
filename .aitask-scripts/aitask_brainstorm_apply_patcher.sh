#!/usr/bin/env bash
# aitask_brainstorm_apply_patcher.sh - Re-run apply on a brainstorm patcher.
#
# Usage: ait brainstorm apply-patcher <task_num> <agent_name> <source_node_id>
#
# Re-parses <agent_name>_output.md and creates a new node parented on
# source_node_id. Useful when the TUI's auto-apply didn't run.
#
# Output:
#   APPLIED:<new_node_id>:<impact_type>   Apply succeeded
#   APPLY_FAILED:<error>                  Apply failed (stderr; see also
#                                         <agent_name>_apply_error.log in the
#                                         crew worktree)

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

if [[ $# -ne 3 ]]; then
    echo "Usage: ait brainstorm apply-patcher <task_num> <agent_name> <source_node_id>" >&2
    exit 2
fi

NUM="$1"
AGENT="$2"
SOURCE="$3"

cd "$SCRIPT_DIR/.."
exec "$PYTHON" - "$NUM" "$AGENT" "$SOURCE" <<'PY'
import sys
sys.path.insert(0, '.aitask-scripts')
from brainstorm.brainstorm_session import apply_patcher_output

num, agent, source = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    new_id, impact, _details = apply_patcher_output(num, agent, source)
    print(f'APPLIED:{new_id}:{impact}')
except Exception as exc:
    print(f'APPLY_FAILED:{exc}', file=sys.stderr)
    sys.exit(1)
PY
