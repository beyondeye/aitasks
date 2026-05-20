#!/usr/bin/env bash
# aitask_brainstorm_apply_detailer.sh - Re-run apply on a brainstorm detailer.
#
# Usage: ait brainstorm apply-detailer <task_num> <agent_name> <target_node_id>
#
# Re-parses <agent_name>_output.md, writes the detailer's plan to
# br_plans/<target_node_id>_plan.md, and sets plan_file on the target node.
# Useful when the TUI's auto-apply didn't run.
#
# Output:
#   APPLIED:<plan_rel>     Apply succeeded (relative plan path written)
#   APPLY_FAILED:<error>   Apply failed (stderr; see also
#                          <agent_name>_apply_error.log in the crew worktree)

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
    echo "Usage: ait brainstorm apply-detailer <task_num> <agent_name> <target_node_id>" >&2
    exit 2
fi

NUM="$1"
AGENT="$2"
TARGET="$3"

cd "$SCRIPT_DIR/.."
exec "$PYTHON" - "$NUM" "$AGENT" "$TARGET" <<'PY'
import sys
sys.path.insert(0, '.aitask-scripts')
from brainstorm.brainstorm_session import apply_detailer_output

num, agent, target = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    plan_rel = apply_detailer_output(num, agent, target)
    print(f'APPLIED:{plan_rel}')
except Exception as exc:
    print(f'APPLY_FAILED:{exc}', file=sys.stderr)
    sys.exit(1)
PY
