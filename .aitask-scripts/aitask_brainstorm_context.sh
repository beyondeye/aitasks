#!/usr/bin/env bash
# aitask_brainstorm_context.sh - Resolve brainstorm ids to paths (read-only).
#
# Thin wrapper over `brainstorm_cli.py paths`. The brainstorm-discuss skill
# receives only ids on argv (<task_num> <node_id>...) and calls this helper to
# turn them into the session path, the brainstormed task file and each node's
# proposal / metadata paths, optionally with every ancestor of each node.
# It never writes to the session.
#
# Usage:
#   ./.aitask-scripts/aitask_brainstorm_context.sh [--lineage] <task_num> [<node_id>...]
#
#   <task_num>    Brainstormed task number (N or N_M)
#   <node_id>     Zero or more node ids (default: every node in the session)
#   --lineage     Also emit ANCESTOR lines: BFS over all parents, crossing
#                 module boundaries
#
# Output (stdout; all resolution outcomes exit 0 - parse the lines, not the
# exit code):
#   SESSION_PATH:<path>|NOT_FOUND          (NOT_FOUND ends the output)
#   TASK_FILE:<path>|NOT_FOUND|INVALID
#   NODE:<id>|PROPOSAL:<path|NOT_FOUND>|META:<path|NOT_FOUND>|PARENTS:<tokens>
#   ANCESTOR:<node>|<token>|DEPTH:<n>|MODULE:<token>|PARENTS:<tokens>|PROPOSAL:<path|NOT_FOUND>
#
# A token is a node id matching [A-Za-z0-9_.-]+ or a "!"-prefixed sentinel
# (!INVALID: present but unsafe; !MISSING: owning YAML unreadable). <tokens> is
# comma-joined. Values read from session YAML are never emitted unless they
# pass their field's charset, so a field can never carry "|", "," or a newline.
# Paths are repo-relative. TASK_FILE is INVALID unless it is exactly the task's
# own file (aitasks/t<N>_<slug>.md or aitasks/t<P>/t<P>_<C>_<slug>.md).
#
# A malformed task number or node id is the one hard error (exit 2).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh disable=SC1091
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh disable=SC1091
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/terminal_compat.sh disable=SC1091
source "$SCRIPT_DIR/lib/terminal_compat.sh"

show_help() {
    cat <<'EOF'
Usage: aitask_brainstorm_context.sh [--lineage] <task_num> [<node_id>...]

Resolve a brainstorm session's task file and node proposal/metadata paths
(read-only).

Arguments:
  <task_num>    Brainstormed task number (N or N_M)
  <node_id>     Node ids (default: all nodes)
  --lineage     Also emit every ancestor of each node

Output lines:
  SESSION_PATH:<path>|NOT_FOUND
  TASK_FILE:<path>|NOT_FOUND|INVALID
  NODE:<id>|PROPOSAL:<path|NOT_FOUND>|META:<path|NOT_FOUND>|PARENTS:<tokens>
  ANCESTOR:<node>|<token>|DEPTH:<n>|MODULE:<token>|PARENTS:<tokens>|PROPOSAL:<path|NOT_FOUND>
EOF
}

# --- Argument parsing ---
lineage=()
task_num=""
node_ids=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --lineage) lineage=(--lineage); shift ;;
        -h|--help) show_help; exit 0 ;;
        -*)        die "Unknown option: $1" ;;
        *)
            if [[ -z "$task_num" ]]; then
                task_num="$1"
            else
                node_ids+=("$1")
            fi
            shift ;;
    esac
done

[[ -n "$task_num" ]] || { show_help >&2; die "task_num required"; }

PYTHON="$(require_ait_python)"

# Crew paths are repo-relative (.aitask-crews/...), so resolve from the root
# regardless of the caller's working directory.
cd "$SCRIPT_DIR/.."

exec "$PYTHON" "$SCRIPT_DIR/brainstorm/brainstorm_cli.py" paths \
    --task-num "$task_num" ${lineage[@]+"${lineage[@]}"} \
    -- ${node_ids[@]+"${node_ids[@]}"}
