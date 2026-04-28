#!/usr/bin/env bash
# aitask_brainstorm_apply_initializer.sh - Re-run apply on a brainstorm session.
#
# Usage: ait brainstorm apply-initializer <task_num>
#
# Re-parses initializer_bootstrap_output.md and rewrites n000_init.
# Useful when the TUI's auto-retry didn't run (or didn't get a chance).
#
# Output:
#   APPLIED:n000_init        Apply succeeded
#   APPLY_FAILED:<error>     Apply failed (stderr; see also
#                            initializer_bootstrap_apply_error.log in the crew worktree)

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

SESSION="${1:-}"
if [[ -z "$SESSION" ]]; then
    echo "Usage: ait brainstorm apply-initializer <task_num>" >&2
    exit 2
fi

NUM="${SESSION#brainstorm-}"

cd "$SCRIPT_DIR/.."
exec "$PYTHON" - "$NUM" <<'PY'
import sys
sys.path.insert(0, '.aitask-scripts')
from brainstorm.brainstorm_session import apply_initializer_output

num = sys.argv[1]
try:
    apply_initializer_output(num)
    print('APPLIED:n000_init')
except Exception as exc:
    print(f'APPLY_FAILED:{exc}', file=sys.stderr)
    sys.exit(1)
PY
