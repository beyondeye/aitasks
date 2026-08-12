#!/usr/bin/env bash
# aitask_brainstorm_archive.sh - Finalize and archive a brainstorm session.
#
# Usage: ait brainstorm archive <task_num>
#
# Exports HEAD node's proposal to aiplans/, marks session archived,
# sets crew status to Completed, and cleans up the crew worktree.
#
# Output:
#   PLAN:<path>              Proposal exported to aiplans/
#   ARCHIVED:<task_num>      Session archived and crew cleaned up

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
if ! "$PYTHON" -c "import yaml" 2>/dev/null; then
    die "Missing Python package: pyyaml. Run 'ait setup' or: pip install pyyaml"
fi

# --- Usage ---
show_help() {
    cat <<'HELP'
Usage: ait brainstorm archive <task_num>

Finalize a brainstorm session: export HEAD node's proposal to aiplans/,
mark session as archived, and clean up the crew worktree.

Arguments:
  <task_num>    Task number (required)

Output:
  PLAN:<path>              Proposal exported to aiplans/
  ARCHIVED:<task_num>      Session archived and crew cleaned up

Example:
  ait brainstorm archive 42
HELP
}

# --- Argument parsing ---
TASK_NUM=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            show_help; exit 0 ;;
        -*)
            die "Unknown option: $1. Run 'ait brainstorm archive --help' for usage." ;;
        *)
            if [[ -z "$TASK_NUM" ]]; then
                TASK_NUM="$1"; shift
            else
                die "Unexpected argument: $1"
            fi
            ;;
    esac
done

[[ -z "$TASK_NUM" ]] && die "Missing required <task_num>. Run 'ait brainstorm archive --help' for usage."

# --- Finalize: export HEAD proposal to aiplans/ ---
info "Finalizing brainstorm session for task $TASK_NUM..."
finalize_output=$("$PYTHON" "$SCRIPT_DIR/brainstorm/brainstorm_cli.py" finalize --task-num "$TASK_NUM" 2>&1) || {
    die "Failed to finalize session: $finalize_output"
}

# Surface the exported proposal path (PLAN:<path>) emitted by the CLI. The
# capture merges stderr, so match the line rather than prefix-stripping the
# whole string.
plan_line=$(printf '%s\n' "$finalize_output" | grep '^PLAN:' || true)
if [[ -n "$plan_line" ]]; then
    echo "$plan_line"
fi

# --- Archive session (also sets crew status to Completed) ---
archive_output=$("$PYTHON" "$SCRIPT_DIR/brainstorm/brainstorm_cli.py" archive --task-num "$TASK_NUM") || {
    die "Failed to archive session: $archive_output"
}

# --- Cleanup crew worktree ---
CREW_ID="brainstorm-${TASK_NUM}"
cleanup_output=$(bash "$SCRIPT_DIR/aitask_crew_cleanup.sh" --crew "$CREW_ID" --delete-branch --batch 2>&1) || {
    warn "Crew cleanup returned non-zero (may already be cleaned): $cleanup_output"
}

success "Brainstorm session archived for task $TASK_NUM"
echo "ARCHIVED:${TASK_NUM}"
