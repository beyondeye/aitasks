#!/usr/bin/env bash
# aitask_brainstorm_apply_synthesizer.sh - Re-run apply on a brainstorm synthesizer.
#
# Usage: ait brainstorm apply-synthesizer <task_num> <agent_name>
#
# Re-parses <agent_name>_output.md and creates a new synthesized node parented
# on every source node listed in the synthesizer's NODE_YAML. Useful when the
# TUI's auto-apply didn't run (or didn't get a chance).
#
# Output:
#   APPLIED:<new_node_id>    Apply succeeded
#   APPLY_FAILED:<error>     Apply failed (stderr; unless the output file is
#                            missing, also logged best-effort to
#                            <agent_name>_apply_error.log in the crew worktree)

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
Usage: ait brainstorm apply-synthesizer <task_num> <agent_name>

Re-run the apply step for a finished synthesizer agent: re-parse
<agent_name>_output.md and add the merged node it describes, parented on
every source node its NODE_YAML block lists. Use it when the studio's
automatic apply did not run.

Arguments:
  <task_num>      Task number of the session
  <agent_name>    Name of the synthesizer agent (e.g. synthesizer_001)

Output:
  APPLIED:<new_node_id>   Apply succeeded (stdout)
  APPLY_FAILED:<error>    Apply failed (stderr, exit 1)

Not every failure writes a log: when the output file exists but cannot be
applied, details are also written (best effort) to
<agent_name>_apply_error.log in the session's crew worktree; a missing
output file writes none. The APPLY_FAILED line is always the current error.

Example:
  ait brainstorm apply-synthesizer 42 synthesizer_001
HELP
}

# Usage errors exit 2 — exit 1 is reserved for APPLY_FAILED.
usage_error() {
    echo "$1" >&2
    echo "Run 'ait brainstorm apply-synthesizer --help' for usage." >&2
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

[[ ${#POSITIONAL[@]} -ge 2 ]] || usage_error "Usage: ait brainstorm apply-synthesizer <task_num> <agent_name>"
[[ ${#POSITIONAL[@]} -le 2 ]] || usage_error "Unexpected argument: ${POSITIONAL[2]}"
NUM="${POSITIONAL[0]}"
AGENT="${POSITIONAL[1]}"
[[ -n "$NUM" ]] || usage_error "Empty <task_num> argument"
[[ -n "$AGENT" ]] || usage_error "Empty <agent_name> argument"

PYTHON="$(require_ait_python)"
if ! "$PYTHON" -c "import yaml" 2>/dev/null; then
    die "Missing Python package: pyyaml. Run 'ait setup' or: pip install pyyaml"
fi

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
