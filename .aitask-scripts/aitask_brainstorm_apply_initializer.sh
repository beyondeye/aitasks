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
#   APPLY_FAILED:<error>     Apply failed (stderr; a NODE_YAML parse failure also
#                            writes initializer_bootstrap_apply_error.log in the
#                            crew worktree — other failures write no log)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

# --- Usage ---
show_help() {
    cat <<'HELP'
Usage: ait brainstorm apply-initializer <task_num>

Re-run the initializer apply for a brainstorm session: re-parse
initializer_bootstrap_output.md and rewrite the first node (n000_init) and
its proposal. Use it when the studio's automatic apply did not run.

The first node and its proposal are overwritten without confirmation, even
if they were edited since the initializer ran (the studio's Ctrl+R does the
same).

Arguments:
  <task_num>    Task number of the session (also accepted as brainstorm-<task_num>)

Output:
  APPLIED:n000_init       Apply succeeded (stdout)
  APPLY_FAILED:<error>    Apply failed (stderr, exit 1)

Not every failure writes a log: only a NODE_YAML block that fails to parse
also leaves details in initializer_bootstrap_apply_error.log in the
session's crew worktree. The APPLY_FAILED line is always the current error.

Example:
  ait brainstorm apply-initializer 42
HELP
}

# Usage errors exit 2 — exit 1 is reserved for APPLY_FAILED.
usage_error() {
    echo "$1" >&2
    echo "Run 'ait brainstorm apply-initializer --help' for usage." >&2
    exit 2
}

# --- Argument parsing (before any Python check, so --help always works) ---
# Positionals are counted, not slotted by emptiness: an empty value must not
# leave its slot free for the next argument.
POSITIONAL=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            show_help; exit 0 ;;
        -*)
            usage_error "Unknown option: $1" ;;
        *)
            POSITIONAL+=("$1"); shift ;;
    esac
done

[[ ${#POSITIONAL[@]} -ge 1 ]] || usage_error "Usage: ait brainstorm apply-initializer <task_num>"
[[ ${#POSITIONAL[@]} -le 1 ]] || usage_error "Unexpected argument: ${POSITIONAL[1]}"
# An empty value — or a bare "brainstorm-" prefix — leaves no task number.
NUM="${POSITIONAL[0]#brainstorm-}"
[[ -n "$NUM" ]] || usage_error "Empty <task_num> argument"

PYTHON="$(require_ait_python)"
if ! "$PYTHON" -c "import yaml" 2>/dev/null; then
    die "Missing Python package: pyyaml. Run 'ait setup' or: pip install pyyaml"
fi

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
